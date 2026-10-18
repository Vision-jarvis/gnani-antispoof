"""Packed audio store: one ``.npz`` per (split, condition) holding int16 audio concatenated with offsets.

Tens of thousands of short clips load in one read instead of tens of thousands of file opens.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class PackedAudio:
    utt_ids: np.ndarray
    offsets: np.ndarray  # len(utt_ids) + 1
    audio: np.ndarray  # int16
    sr: int

    def __len__(self) -> int:
        return len(self.utt_ids)

    def get(self, i: int) -> np.ndarray:
        return self.audio[self.offsets[i] : self.offsets[i + 1]].astype(np.float32) / 32768.0

    def __iter__(self) -> Iterator[tuple[str, np.ndarray]]:
        for i, u in enumerate(self.utt_ids):
            yield str(u), self.get(i)

    def index(self) -> dict[str, int]:
        return {str(u): i for i, u in enumerate(self.utt_ids)}


def save_packed(path: Path, utt_ids: Sequence[str], clips: Sequence[np.ndarray], sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = [(np.clip(c, -1.0, 1.0 - 1 / 32768) * 32768).round().astype(np.int16) for c in clips]
    offsets = np.concatenate([[0], np.cumsum([len(c) for c in pcm])]).astype(np.int64)
    audio = np.concatenate(pcm) if pcm else np.zeros(0, np.int16)
    np.savez(path, utt_ids=np.asarray(utt_ids), offsets=offsets, audio=audio, sr=np.int64(sr))


def load_packed(path: Path) -> PackedAudio:
    z = np.load(path, allow_pickle=False)
    return PackedAudio(z["utt_ids"], z["offsets"], z["audio"], int(z["sr"]))
