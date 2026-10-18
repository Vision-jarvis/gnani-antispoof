"""LFCC front-end (the feature of the ASVspoof 2019/2021 LFCC-GMM and LFCC-LCNN baselines).

Linear (not mel) triangular filters keep the resolution of the high band, where vocoder artefacts
sit. At 8 kHz that band is gone, which is exactly the narrowband penalty this project measures.
Frames: 20 ms Hamming window, 10 ms hop, pre-emphasis 0.97; 20 filters over [0, sr/2]; 20 cepstra
(c0 included) plus deltas and delta-deltas = 60 dims. CQCC is not used: its constant-Q geometry spends
most bins on the top octaves, and at 8 kHz the top octave (4 to 8 kHz) no longer exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from scipy.fft import dct, rfft


@dataclass(frozen=True)
class LFCCConfig:
    sr: int
    win_s: float = 0.02
    hop_s: float = 0.01
    n_filters: int = 20
    n_ceps: int = 20
    preemph: float = 0.97
    delta_width: int = 2

    @property
    def n_fft(self) -> int:
        return 1 << int(np.ceil(np.log2(self.win_s * self.sr)))

    @property
    def dim(self) -> int:
        return 3 * self.n_ceps


@lru_cache(maxsize=8)
def linear_filterbank(sr: int, n_fft: int, n_filters: int) -> np.ndarray:
    """(n_filters, n_fft//2+1) triangular filters with centres equally spaced on a linear Hz axis."""
    freqs = np.linspace(0, sr / 2, n_fft // 2 + 1)
    edges = np.linspace(0, sr / 2, n_filters + 2)
    fb = np.zeros((n_filters, len(freqs)))
    for i in range(n_filters):
        lo, c, hi = edges[i : i + 3]
        fb[i] = np.clip(np.minimum((freqs - lo) / (c - lo), (hi - freqs) / (hi - c)), 0, None)
    return fb


def deltas(x: np.ndarray, width: int) -> np.ndarray:
    """Regression deltas along time (axis 0) with edge padding."""
    pad = np.pad(x, ((width, width), (0, 0)), mode="edge")
    num = sum(k * (pad[width + k : len(x) + width + k] - pad[width - k : len(x) + width - k]) for k in range(1, width + 1))
    return num / (2 * sum(k * k for k in range(1, width + 1)))


def lfcc(x: np.ndarray, cfg: LFCCConfig) -> np.ndarray:
    """(T, 60) float32 LFCC + deltas. Causal except for the delta window (``delta_width`` frames, 20 ms)."""
    win, hop = int(cfg.win_s * cfg.sr), int(cfg.hop_s * cfg.sr)
    x = np.append(x[0], x[1:] - cfg.preemph * x[:-1]) if len(x) else x
    if len(x) < win:
        x = np.pad(x, (0, win - len(x)))
    n = 1 + (len(x) - win) // hop
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    frames = x[idx] * np.hamming(win)
    power = np.abs(rfft(frames, n=cfg.n_fft, axis=1)) ** 2
    fbe = power @ linear_filterbank(cfg.sr, cfg.n_fft, cfg.n_filters).T
    ceps = dct(np.log(fbe + 1e-10), type=2, axis=1, norm="ortho")[:, : cfg.n_ceps]
    d1 = deltas(ceps, cfg.delta_width)
    d2 = deltas(d1, cfg.delta_width)
    return np.concatenate([ceps, d1, d2], axis=1).astype(np.float32)
