"""Anti-shortcut normalisation (Part A.4).

ASVspoof 2019 LA bona fide files carry longer leading and trailing silences than spoofs, and a
silence-duration-only classifier reaches about 15% EER on it (Muller et al., arXiv:2106.12914).
Every file therefore goes through the same policy before any channel or feature step:

1. Energy VAD on 20 ms frames: a frame is speech if its energy is within ``rel_db`` of the
   loudest frame and above an absolute floor. Trim to [first speech frame, last speech frame],
   keeping ``margin_s`` of the original signal on each side (never inserting digital silence,
   which would itself be a fingerprint).
2. Integrated loudness (ITU-R BS.1770, via pyloudnorm) normalised to ``target_lufs``; clips shorter
   than the 400 ms BS.1770 gating block fall back to RMS matching. Peaks are limited to 0.99.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyloudnorm

FRAME_S = 0.02


@dataclass(frozen=True)
class NormPolicy:
    rel_db: float = 40.0
    floor_dbfs: float = -60.0
    margin_s: float = 0.05
    target_lufs: float = -23.0


DEFAULT_POLICY = NormPolicy()
# Second trim applied to whatever the CM receives (after the channel, at its own sample rate).
# The 40 dB build-time gate left a residual silence cue (single-cue EER 24% on ASVspoof eval nb_pcm,
# failing rule 4); a 30 dB gate on the CM input brings it to 38% (artifacts/results.md, audit table).
CM_INPUT_POLICY = NormPolicy(rel_db=30.0)


def frame_energy_db(x: np.ndarray, sr: int, frame_s: float = FRAME_S) -> np.ndarray:
    n = max(1, int(sr * frame_s))
    k = len(x) // n
    if k == 0:
        return np.array([10 * np.log10(np.mean(x**2) + 1e-12)])
    frames = x[: k * n].reshape(k, n)
    return 10 * np.log10(np.mean(frames**2, axis=1) + 1e-12)


def speech_bounds(x: np.ndarray, sr: int, policy: NormPolicy = DEFAULT_POLICY) -> tuple[int, int]:
    """Sample indices [start, end) of the region from the first to the last speech frame."""
    e = frame_energy_db(x, sr)
    speech = (e >= e.max() - policy.rel_db) & (e >= policy.floor_dbfs)
    if not speech.any():
        return 0, len(x)
    n = int(sr * FRAME_S)
    idx = np.flatnonzero(speech)
    return int(idx[0] * n), int(min(len(x), (idx[-1] + 1) * n))


def silence_stats(x: np.ndarray, sr: int, policy: NormPolicy = DEFAULT_POLICY) -> tuple[float, float]:
    """(leading, trailing) non-speech duration in seconds, used by the shortcut audit."""
    s, e = speech_bounds(x, sr, policy)
    return s / sr, (len(x) - e) / sr


def vad_trim(x: np.ndarray, sr: int, policy: NormPolicy = DEFAULT_POLICY) -> np.ndarray:
    s, e = speech_bounds(x, sr, policy)
    m = int(policy.margin_s * sr)
    return x[max(0, s - m) : min(len(x), e + m)]


def loudness_normalise(x: np.ndarray, sr: int, target_lufs: float = DEFAULT_POLICY.target_lufs) -> np.ndarray:
    x = x.astype(np.float64)
    if len(x) >= int(0.4 * sr):
        lufs = pyloudnorm.Meter(sr).integrated_loudness(x)
        gain_db = target_lufs - lufs if np.isfinite(lufs) else 0.0
    else:
        rms_db = 20 * np.log10(np.sqrt(np.mean(x**2)) + 1e-12)
        gain_db = target_lufs - rms_db  # LUFS and dBFS RMS are close for speech
    y = x * 10 ** (gain_db / 20)
    peak = np.max(np.abs(y)) if len(y) else 0.0
    if peak > 0.99:
        y *= 0.99 / peak
    return y.astype(np.float32)


def cm_input(x: np.ndarray, sr: int) -> np.ndarray:
    """What every countermeasure scores: the clip re-trimmed with ``CM_INPUT_POLICY``."""
    return vad_trim(np.asarray(x, dtype=np.float32), sr, CM_INPUT_POLICY)


def normalise(x: np.ndarray, sr: int, policy: NormPolicy = DEFAULT_POLICY) -> np.ndarray:
    """The full anti-shortcut policy: VAD trim, then loudness normalisation."""
    return loudness_normalise(vad_trim(np.asarray(x, dtype=np.float32), sr, policy), sr, policy.target_lufs)


def causal_cm_input(prefix: np.ndarray, sr: int) -> np.ndarray:
    """CM input for a streaming decision: normalise, then ``cm_input``, using ``prefix`` and nothing after it.

    The trim threshold (loudest frame so far) and the loudness gain are computed on the samples received up
    to the decision time only, so a partial score never sees the future (honesty rule 5). The runtime scorer,
    the WebSocket endpoint and the streaming evaluation all call this one function on ``x[: t * sr]``.
    """
    return cm_input(normalise(np.asarray(prefix, dtype=np.float32), sr), sr)
