"""Compute and cache LFCC for every packed (split, condition) store.

Features are cached as float16 (T, 60) matrices concatenated with offsets, under
data/proc/asv19/<split>/feats/<condition>[_<horizon>].npz. ``horizon_s`` truncates each clip to its
first N seconds before feature extraction (the streaming evaluation: a decision at time t only sees
audio up to t).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cm.features import LFCCConfig, lfcc
from factory.channel_sim import resample
from factory.store import load_packed


@dataclass
class FeatureSet:
    utt_ids: np.ndarray
    offsets: np.ndarray
    feats: np.ndarray

    def get(self, i: int) -> np.ndarray:
        return self.feats[self.offsets[i] : self.offsets[i + 1]].astype(np.float32)

    def all(self) -> list[np.ndarray]:
        return [self.get(i) for i in range(len(self.utt_ids))]


def _lfcc_job(args: tuple[np.ndarray, int]) -> np.ndarray:
    x, sr = args
    return lfcc(x, LFCCConfig(sr=sr)).astype(np.float16)


def feature_path(split_dir: Path, condition: str, horizon_s: float | None) -> Path:
    suffix = f"_{horizon_s:g}s" if horizon_s else ""
    return split_dir / "feats" / f"{condition}{suffix}.npz"


def load_features(split_dir: Path, condition: str, horizon_s: float | None = None, resample_to: int | None = None) -> FeatureSet:
    """LFCC for ``condition``; computed once and cached. ``resample_to`` re-rates audio first (e.g. 8k -> 16k)."""
    tag = condition if resample_to is None else f"{condition}@{resample_to}"
    path = feature_path(split_dir, tag, horizon_s)
    if not path.exists():
        packed = load_packed(split_dir / f"{condition}.npz")
        sr = packed.sr if resample_to is None else resample_to
        clips = []
        for i in range(len(packed)):
            x = packed.get(i)
            if resample_to is not None and resample_to != packed.sr:
                x = resample(x, packed.sr, resample_to)
            if horizon_s:
                x = x[: int(horizon_s * sr)]
            clips.append(x)
        # In-process: LFCC costs ~5 ms per clip, less than spawning workers on Windows.
        feats = [_lfcc_job((c, sr)) for c in clips]
        path.parent.mkdir(parents=True, exist_ok=True)
        offsets = np.concatenate([[0], np.cumsum([len(f) for f in feats])]).astype(np.int64)
        np.savez(path, utt_ids=packed.utt_ids, offsets=offsets, feats=np.concatenate(feats))
    z = np.load(path)
    return FeatureSet(z["utt_ids"], z["offsets"], z["feats"])
