"""Audit cues must see silence that the CM-input trim leaves behind, independently of the trim gate."""

from __future__ import annotations

import numpy as np

from eval.shortcut_audit import clip_cues, vad_flags


def _speechlike(sr: int, seconds: float, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(int(sr * seconds)) / sr
    env = 0.5 + 0.5 * np.sin(2 * np.pi * 3 * t) ** 2  # syllable-rate envelope
    return (0.3 * env * (np.sin(2 * np.pi * 180 * t) + 0.3 * rng.standard_normal(len(t)))).astype(np.float32)


def test_padded_silence_is_measured_by_independent_cues() -> None:
    sr = 8000
    x = _speechlike(sr, 1.5)
    pad = np.zeros(int(0.5 * sr), np.float32) + 1e-4 * np.random.default_rng(1).standard_normal(int(0.5 * sr)).astype(np.float32)
    padded = np.concatenate([pad, x, pad])
    c0, c1 = clip_cues(x, sr), clip_cues(padded, sr)
    assert c1["vad_silence_s"] > c0["vad_silence_s"] + 0.5
    assert c1["silence_tight10_s"] > c0["silence_tight10_s"] + 0.5
    assert c1["dur_s"] > c0["dur_s"]


def test_vad_flags_frame_count() -> None:
    sr = 16000
    flags = vad_flags(_speechlike(sr, 1.0), sr)
    assert len(flags) == 50  # 1 s at 20 ms frames after re-rating to 8 kHz
