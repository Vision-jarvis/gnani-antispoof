"""Telephony channel simulator (Part A.3).

Every condition is a short chain of deterministic steps applied identically to bona fide and spoof
audio. The output is always 8 kHz mono float32 in [-1, 1], with exactly the duration of the input
(codec delay is not compensated, the decoded stream is trimmed or zero padded to length).

Codecs run through the system ffmpeg (encode to the real bitstream, then decode), so the artefacts
are those of the reference encoders (libopencore_amrnb, libvo_amrwbenc, libopus, libgsm,
pcm_mulaw, pcm_alaw), not an approximation. Packet loss is applied after decoding, on 20 ms frames,
with a choice of zero insertion or previous-frame repetition as concealment. Randomness (packet
loss pattern) comes only from ``numpy.random.default_rng(seed)``, so a (condition, seed) pair always
gives the same output.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal, Protocol

import numpy as np
from scipy.signal import butter, resample_poly, sosfiltfilt

SR_NB = 8000
SR_WB = 16000
_RAW_CONTAINERS = frozenset({"mulaw", "alaw"})


class Step(Protocol):
    """One transformation of a mono float32 signal. ``sr`` is the input rate; returns (signal, rate)."""

    def __call__(self, x: np.ndarray, sr: int, rng: np.random.Generator) -> tuple[np.ndarray, int]: ...


def resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    """Polyphase resampling with the default Kaiser anti-aliasing filter of ``resample_poly``."""
    if sr_in == sr_out:
        return x.astype(np.float32, copy=False)
    g = np.gcd(sr_in, sr_out)
    return resample_poly(x, sr_out // g, sr_in // g).astype(np.float32)


@dataclass(frozen=True)
class Resample:
    sr_out: int

    def __call__(self, x: np.ndarray, sr: int, rng: np.random.Generator) -> tuple[np.ndarray, int]:
        return resample(x, sr, self.sr_out), self.sr_out


@dataclass(frozen=True)
class BandLimit:
    """Telephone band-pass (default 300 to 3400 Hz, the ITU-T G.712 voice band), zero phase."""

    lo_hz: float = 300.0
    hi_hz: float = 3400.0
    order: int = 4

    def __call__(self, x: np.ndarray, sr: int, rng: np.random.Generator) -> tuple[np.ndarray, int]:
        sos = butter(self.order, [self.lo_hz, min(self.hi_hz, 0.49 * sr)], btype="bandpass", fs=sr, output="sos")
        return sosfiltfilt(sos, x).astype(np.float32), sr


@dataclass(frozen=True)
class FfmpegCodec:
    """Encode with an ffmpeg encoder into its native container, then decode back to PCM.

    ``codec_sr`` is the rate the codec runs at (the input is resampled to it first). The decoded
    signal is returned at ``codec_sr``.
    """

    encoder: str
    container: str
    codec_sr: int = SR_NB
    bitrate: str | None = None
    extra: tuple[str, ...] = ()

    def __call__(self, x: np.ndarray, sr: int, rng: np.random.Generator) -> tuple[np.ndarray, int]:
        y = resample(x, sr, self.codec_sr)
        pcm = _to_pcm16(y)
        enc_args = ["-c:a", self.encoder, *(["-b:a", self.bitrate] if self.bitrate else []), *self.extra]
        bitstream = _ffmpeg(
            ["-f", "s16le", "-ar", str(self.codec_sr), "-ac", "1", "-i", "pipe:0", *enc_args, "-f", self.container, "pipe:1"],
            pcm,
        )
        raw_in = ["-ar", str(self.codec_sr), "-ac", "1"] if self.container in _RAW_CONTAINERS else []
        decoded = _ffmpeg(
            ["-f", self.container, *raw_in, "-i", "pipe:0", "-f", "s16le", "-ar", str(self.codec_sr), "-ac", "1", "pipe:1"],
            bitstream,
        )
        out = np.frombuffer(decoded, dtype="<i2").astype(np.float32) / 32768.0
        return _fit_length(out, len(y)), self.codec_sr


@dataclass(frozen=True)
class PacketLoss:
    """Drop 20 ms frames i.i.d. with probability ``rate``; conceal by zeros or by repeating the last good frame."""

    rate: float
    frame_ms: int = 20
    concealment: Literal["zero", "repeat"] = "repeat"

    def __call__(self, x: np.ndarray, sr: int, rng: np.random.Generator) -> tuple[np.ndarray, int]:
        if self.rate <= 0:
            return x, sr
        n = sr * self.frame_ms // 1000
        y = x.copy()
        lost = rng.random(int(np.ceil(len(x) / n))) < self.rate
        last_good = np.zeros(n, dtype=np.float32)
        for i, is_lost in enumerate(lost):
            seg = slice(i * n, min((i + 1) * n, len(x)))
            width = seg.stop - seg.start
            if not is_lost:
                last_good = np.pad(x[seg], (0, n - width))
            elif self.concealment == "zero":
                y[seg] = 0.0
            else:
                # Repeat with a 0.5 gain per consecutive loss, as simple PLC implementations do.
                last_good = 0.5 * last_good
                y[seg] = last_good[:width]
        return y, sr


@dataclass(frozen=True)
class Condition:
    """A named channel: a chain of steps that always ends at 8 kHz."""

    name: str
    steps: tuple[Step, ...]
    description: str = ""
    tags: frozenset[str] = field(default_factory=frozenset)

    def apply(self, x: np.ndarray, sr: int, seed: int = 0) -> np.ndarray:
        rng = np.random.default_rng(seed)
        y = np.asarray(x, dtype=np.float32)
        for step in self.steps:
            y, sr = step(y, sr, rng)
        if sr != SR_NB:
            y = resample(y, sr, SR_NB)
        return np.clip(y, -1.0, 1.0)


def _amrnb(br: str) -> FfmpegCodec:
    return FfmpegCodec("libopencore_amrnb", "amr", SR_NB, br, ("-dtx", "0"))


_G711U = FfmpegCodec("pcm_mulaw", "mulaw", SR_NB)
_G711A = FfmpegCodec("pcm_alaw", "alaw", SR_NB)
_AMRWB = FfmpegCodec("libvo_amrwbenc", "amr", SR_WB, "12.65k")
_GSM = FfmpegCodec("libgsm", "gsm", SR_NB)


def _opus(br: str) -> FfmpegCodec:
    # Opus at an 8 kHz input rate runs in narrowband mode (4 kHz audio bandwidth).
    return FfmpegCodec("libopus", "ogg", SR_NB, br, ("-application", "voip", "-vbr", "off"))


_NB = (Resample(SR_NB),)
_PSTN = (Resample(SR_NB), BandLimit())

CONDITIONS: dict[str, Condition] = {
    c.name: c
    for c in [
        Condition("nb_pcm", _NB, "8 kHz resample only (no codec)"),
        Condition("g711u", (*_PSTN, _G711U), "PSTN band-limit + G.711 mu-law"),
        Condition("g711a", (*_PSTN, _G711A), "PSTN band-limit + G.711 A-law"),
        Condition("amrnb_12k2", (*_NB, _amrnb("12.2k")), "AMR-NB 12.2 kbps"),
        Condition("amrnb_7k95", (*_NB, _amrnb("7.95k")), "AMR-NB 7.95 kbps"),
        Condition("amrnb_4k75", (*_NB, _amrnb("4.75k")), "AMR-NB 4.75 kbps", frozenset({"heldout"})),
        Condition("amrwb_12k65", (_AMRWB,), "AMR-WB 12.65 kbps then down to 8 kHz"),
        Condition("opus_8k", (*_NB, _opus("8k")), "Opus narrowband 8 kbps"),
        Condition("opus_16k", (*_NB, _opus("16k")), "Opus narrowband 16 kbps"),
        Condition("opus_6k_plc3", (*_NB, _opus("6k"), PacketLoss(0.03)), "Opus 6 kbps + 3% packet loss"),
        Condition("g711u_plc5", (*_PSTN, _G711U, PacketLoss(0.05)), "G.711 mu-law + 5% packet loss"),
        Condition("gsm_fr", (*_NB, _GSM), "GSM full rate 13 kbps", frozenset({"heldout"})),
        Condition(
            "chain_amrnb_g711u",
            (*_NB, _amrnb("7.95k"), BandLimit(), _G711U),
            "two hops: mobile AMR-NB 7.95k then PSTN G.711 mu-law",
            frozenset({"heldout", "chain"}),
        ),
        Condition(
            "chain_gsm_g711a_plc2",
            (*_NB, _GSM, BandLimit(), _G711A, PacketLoss(0.02)),
            "two hops: GSM-FR then G.711 A-law with 2% packet loss",
            frozenset({"heldout", "chain"}),
        ),
    ]
}

HELDOUT_CONDITIONS: frozenset[str] = frozenset(n for n, c in CONDITIONS.items() if "heldout" in c.tags)
TRAIN_CONDITIONS: tuple[str, ...] = tuple(n for n in CONDITIONS if n not in HELDOUT_CONDITIONS)


def apply_condition(x: np.ndarray, sr: int, name: str, seed: int = 0) -> np.ndarray:
    """Run ``x`` (mono, rate ``sr``) through condition ``name``; returns 8 kHz float32."""
    return CONDITIONS[name].apply(x, sr, seed)


@lru_cache(maxsize=1)
def ffmpeg_binary() -> str:
    path = shutil.which("ffmpeg")
    if path is None:
        raise RuntimeError("ffmpeg not found on PATH; the channel simulator needs it for codecs")
    return path


def _ffmpeg(args: list[str], stdin: bytes) -> bytes:
    cmd = [ffmpeg_binary(), "-hide_banner", "-loglevel", "error", "-nostdin", "-threads", "1", *args]
    proc = subprocess.run(cmd, input=stdin, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({' '.join(args[:12])}...): {proc.stderr.decode(errors='replace')[-400:]}")
    return proc.stdout


def _to_pcm16(x: np.ndarray) -> bytes:
    return (np.clip(x, -1.0, 1.0 - 1.0 / 32768) * 32768.0).round().astype("<i2").tobytes()


def _fit_length(x: np.ndarray, n: int) -> np.ndarray:
    return x[:n] if len(x) >= n else np.pad(x, (0, n - len(x)))
