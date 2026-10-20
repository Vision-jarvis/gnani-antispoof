"""Compute and cache LFCC for every packed (split, condition) store.

Features are cached as float16 (T, 60) matrices concatenated with offsets, under
data/proc/asv19/<split>/feats_v2/<condition>.npz (full clips, ``cm_input``) and
data/proc/asv19/<split>/feats_causal/<condition>_<horizon>s.npz (streaming). For a horizon t the clip is cut
to its first t seconds FIRST and only then normalised and trimmed (``causal_cm_input``), exactly as the
runtime scorer and the WebSocket endpoint do, so no statistic of the future reaches a partial score
(critique M2). Only clips with at least t seconds of trimmed speech are kept for horizon t (critique M8):
for a shorter clip the "first t seconds" would be the whole clip and the row would not test streaming.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cm.features import LFCCConfig, lfcc
from factory.channel_sim import resample
from factory.normalise import causal_cm_input, cm_input
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
    if horizon_s:
        return split_dir / "feats_causal" / f"{condition}_{horizon_s:g}s.npz"
    return split_dir / "feats_v2" / f"{condition}.npz"  # v2: features of the CM-input trim


def load_inputs(split_dir: Path, condition: str, horizon_s: float | None = None, resample_to: int | None = None,
                limit: int | None = None) -> tuple[np.ndarray, list[np.ndarray], int]:
    """(utt_ids, waveforms, sr) exactly as a CM receives them; shared by LFCC models, AASIST and the teacher.

    Full clip: ``cm_input``. Horizon t: clips with >= t s of trimmed speech only, cut to x[: t * sr] first and
    then ``causal_cm_input`` (no future statistics).
    """
    packed = load_packed(split_dir / f"{condition}.npz")
    sr = packed.sr if resample_to is None else resample_to
    clips, keep = [], []
    for i in range(len(packed)):
        if limit is not None and len(keep) >= limit:
            break
        x = packed.get(i)
        if resample_to is not None and resample_to != packed.sr:
            x = resample(x, packed.sr, resample_to)
        if horizon_s:
            if len(cm_input(x, sr)) < horizon_s * sr:
                continue
            x = causal_cm_input(x[: int(horizon_s * sr)], sr)
        else:
            x = cm_input(x, sr)
        clips.append(x)
        keep.append(i)
    return packed.utt_ids[keep], clips, sr


def load_features(split_dir: Path, condition: str, horizon_s: float | None = None, resample_to: int | None = None) -> FeatureSet:
    """LFCC for ``condition``; computed once and cached. ``resample_to`` re-rates audio first (e.g. 8k -> 16k)."""
    tag = condition if resample_to is None else f"{condition}@{resample_to}"
    path = feature_path(split_dir, tag, horizon_s)
    if not path.exists():
        ids, clips, sr = load_inputs(split_dir, condition, horizon_s, resample_to)
        # In-process: LFCC costs ~5 ms per clip, less than spawning workers on Windows.
        feats = [_lfcc_job((c, sr)) for c in clips]
        path.parent.mkdir(parents=True, exist_ok=True)
        offsets = np.concatenate([[0], np.cumsum([len(f) for f in feats])]).astype(np.int64)
        np.savez(path, utt_ids=ids, offsets=offsets, feats=np.concatenate(feats))
    z = np.load(path)
    return FeatureSet(z["utt_ids"], z["offsets"], z["feats"])
