from __future__ import annotations

import numpy as np
import pytest

from factory.channel_sim import (
    CONDITIONS,
    HELDOUT_CONDITIONS,
    SR_NB,
    BandLimit,
    FfmpegCodec,
    PacketLoss,
    apply_condition,
)
from factory.normalise import loudness_normalise, normalise, silence_stats
from gnani_api.g711 import decode_alaw, decode_mulaw, encode_alaw, encode_mulaw
from gnani_api.mock import synth_speechlike

SR = 16000


@pytest.fixture(scope="module")
def speech() -> np.ndarray:
    return synth_speechlike("channel test", SR, 30)  # ~1.8 s


def _band_energy(x: np.ndarray, sr: int, lo: float, hi: float) -> float:
    spec = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), 1 / sr)
    return float(spec[(f >= lo) & (f < hi)].sum() / spec.sum())


@pytest.mark.parametrize("name", list(CONDITIONS))
def test_every_condition_runs_to_8k_same_duration(name: str, speech: np.ndarray) -> None:
    y = apply_condition(speech, SR, name, seed=3)
    assert y.dtype == np.float32
    assert len(y) == int(np.ceil(len(speech) * SR_NB / SR))
    assert np.max(np.abs(y)) <= 1.0 and np.sqrt(np.mean(y**2)) > 1e-3


@pytest.mark.parametrize("name", ["g711u", "amrnb_4k75", "opus_6k_plc3", "chain_gsm_g711a_plc2"])
def test_deterministic_by_seed(name: str, speech: np.ndarray) -> None:
    assert np.array_equal(apply_condition(speech, SR, name, 7), apply_condition(speech, SR, name, 7))


def test_packet_loss_seed_changes_pattern_and_rate(speech: np.ndarray) -> None:
    x = np.ones(SR_NB * 20, dtype=np.float32) * 0.1
    rng = np.random.default_rng
    a, _ = PacketLoss(0.05, concealment="zero")(x, SR_NB, rng(1))
    b, _ = PacketLoss(0.05, concealment="zero")(x, SR_NB, rng(2))
    lost = (a.reshape(-1, 160) == 0).all(axis=1).mean()
    assert 0.03 < lost < 0.07
    assert not np.array_equal(a, b)
    c, _ = PacketLoss(0.05, concealment="repeat")(x, SR_NB, rng(1))
    assert np.all(c[a == 0] < 0.1) and np.all(c[a == 0] > 0)  # attenuated repetition, not silence


def test_narrowband_removes_4_to_8_khz() -> None:
    t = np.arange(SR) / SR
    x = (0.2 * np.sin(2 * np.pi * 1000 * t) + 0.2 * np.sin(2 * np.pi * 6000 * t)).astype(np.float32)
    assert _band_energy(x, SR, 5000, 8000) > 0.4
    y = apply_condition(x, SR, "nb_pcm")
    assert _band_energy(y, SR_NB, 3900, 4000) < 1e-3  # 6 kHz is gone, not aliased
    assert _band_energy(y, SR_NB, 900, 1100) > 0.99


def test_band_limit_passband() -> None:
    t = np.arange(SR_NB) / SR_NB
    rng = np.random.default_rng(0)
    for f, keep in [(100, False), (1000, True), (3800, False)]:
        x = np.sin(2 * np.pi * f * t).astype(np.float32)
        y, _ = BandLimit()(x, SR_NB, rng)
        ratio = np.sqrt(np.mean(y[800:-800] ** 2) / np.mean(x[800:-800] ** 2))
        assert (ratio > 0.9) if keep else (ratio < 0.2)


@pytest.mark.parametrize(("encoder", "container", "enc", "dec"), [
    ("pcm_mulaw", "mulaw", encode_mulaw, decode_mulaw),
    ("pcm_alaw", "alaw", encode_alaw, decode_alaw),
])
def test_ffmpeg_g711_matches_reference_codec(encoder, container, enc, dec, speech) -> None:  # type: ignore[no-untyped-def]
    x8 = apply_condition(speech, SR, "nb_pcm")
    y, sr = FfmpegCodec(encoder, container)(x8, SR_NB, np.random.default_rng(0))
    pcm = (np.clip(x8, -1.0, 1.0 - 1 / 32768) * 32768).round().astype(np.int16)
    ref = dec(enc(pcm)).astype(np.float32) / 32768.0
    assert sr == SR_NB
    # ffmpeg rounds to the nearest codeword where the Sun reference truncates (segment edges, and
    # A-law values near zero, common in speech pauses); outputs must be the same or adjacent levels.
    y16 = (y * 32768).round().astype(np.int16)
    assert np.mean(y16 != (ref * 32768).round()) < 0.1
    levels = np.unique(dec(bytes(range(256))))
    rank = lambda v: np.searchsorted(levels, v)  # noqa: E731
    assert np.max(np.abs(rank(y16) - rank(dec(enc(pcm))))) <= 1


@pytest.mark.parametrize("name", ["amrnb_12k2", "amrnb_4k75", "gsm_fr", "opus_8k", "amrwb_12k65"])
def test_speech_codecs_keep_waveform_alignment(name: str, speech: np.ndarray) -> None:
    ref = apply_condition(speech, SR, "nb_pcm")
    y = apply_condition(speech, SR, name)
    lags = np.arange(-80, 81)
    xc = [np.dot(ref[200 + k : len(ref) - 200 + k], y[200 : len(y) - 200]) for k in lags]
    assert abs(int(lags[int(np.argmax(np.abs(xc)))])) <= 80  # codec delay stays within 10 ms


def test_heldout_conditions_match_statement() -> None:
    assert HELDOUT_CONDITIONS == {"amrnb_4k75", "gsm_fr", "chain_amrnb_g711u", "chain_gsm_g711a_plc2"}


def test_normalise_equalises_silence_and_loudness(speech: np.ndarray) -> None:
    quiet_padded = np.concatenate([np.zeros(SR), 0.05 * speech, np.zeros(SR // 2)]).astype(np.float32)
    loud_tight = np.clip(3 * speech, -1, 1)
    a, b = normalise(quiet_padded, SR), normalise(loud_tight, SR)
    la, ta = silence_stats(a, SR)
    lb, tb = silence_stats(b, SR)
    assert abs(la - lb) <= 0.03 and abs(ta - tb) <= 0.03
    import pyloudnorm

    meter = pyloudnorm.Meter(SR)
    assert meter.integrated_loudness(a.astype(float)) == pytest.approx(-23.0, abs=0.5)
    assert meter.integrated_loudness(b.astype(float)) == pytest.approx(-23.0, abs=0.5)
    assert np.max(np.abs(loudness_normalise(speech * 0.001, SR, -3.0))) <= 0.99


def test_replay_adds_reverb_deterministically(speech: np.ndarray) -> None:
    from factory.replay_sim import simulate_replay

    a, b, c = simulate_replay(speech, SR, 1), simulate_replay(speech, SR, 1), simulate_replay(speech, SR, 2)
    assert np.array_equal(a, b) and not np.array_equal(a, c)
    assert a.shape == speech.shape and np.max(np.abs(a)) == pytest.approx(np.max(np.abs(speech)), rel=1e-3)
    # Reverberation smears energy into the pauses: the envelope minimum rises.
    env = lambda z: np.convolve(np.abs(z), np.ones(320) / 320, "same")  # noqa: E731
    assert np.percentile(env(a), 5) > np.percentile(env(speech), 5)
