"""G5 replay simulation: bona fide played through a loudspeaker into a room, re-captured by a phone mic.

All responses are synthetic and seeded (no measured impulse responses are bundled):
  loudspeaker: small-driver band-pass (about 200 Hz to 7 kHz) with a soft-clipping nonlinearity
  room:        exponentially decaying noise RIR (Polack's model), RT60 drawn from ``rt60_range``,
               with a direct path and a random direct-to-reverberant ratio
  phone mic:   band-pass 100 Hz to 7.5 kHz with a mild presence peak, plus room noise at ``snr_db``
The output stays at the input rate; the telephony channel (``channel_sim``) is applied afterwards,
identically to every other trial. G6 (injection) is the opposite case: G2 audio goes straight to
``channel_sim`` with no acoustic path, so it needs no simulator of its own.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, fftconvolve, iirpeak, lfilter, sosfilt


@dataclass(frozen=True)
class ReplayConfig:
    rt60_range: tuple[float, float] = (0.2, 0.6)
    drr_db_range: tuple[float, float] = (0.0, 10.0)
    snr_db_range: tuple[float, float] = (15.0, 35.0)
    drive: float = 2.0  # loudspeaker overdrive before tanh


def room_ir(sr: int, rt60: float, drr_db: float, rng: np.random.Generator) -> np.ndarray:
    n = int(sr * min(1.2 * rt60, 1.0))
    t = np.arange(n) / sr
    tail = rng.standard_normal(n) * np.exp(-6.9078 * t / rt60)  # 60 dB decay at rt60
    tail[: int(0.002 * sr)] = 0.0
    tail *= 10 ** (-drr_db / 20) / (np.sqrt(np.sum(tail**2)) + 1e-12)
    tail[0] = 1.0
    return tail


def simulate_replay(x: np.ndarray, sr: int, seed: int, cfg: ReplayConfig = ReplayConfig()) -> np.ndarray:
    rng = np.random.default_rng(seed)
    nyq = sr / 2
    spk = butter(4, [200 / nyq, min(7000, 0.95 * nyq) / nyq], btype="bandpass", output="sos")
    y = np.tanh(cfg.drive * sosfilt(spk, x)) / np.tanh(cfg.drive)
    y = fftconvolve(y, room_ir(sr, rng.uniform(*cfg.rt60_range), rng.uniform(*cfg.drr_db_range), rng))[: len(x)]
    mic = butter(2, [100 / nyq, min(7500, 0.97 * nyq) / nyq], btype="bandpass", output="sos")
    y = sosfilt(mic, y)
    b, a = iirpeak(min(2500, 0.6 * nyq) / nyq, Q=2.0)
    y = y + 0.3 * lfilter(b, a, y)
    noise = rng.standard_normal(len(y))
    snr = rng.uniform(*cfg.snr_db_range)
    y = y + noise * np.sqrt(np.mean(y**2) / 10 ** (snr / 10))
    y *= np.max(np.abs(x)) / (np.max(np.abs(y)) + 1e-12)  # keep the input peak level
    return y.clip(-1, 1).astype(np.float32)
