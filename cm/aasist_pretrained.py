"""Pretrained AASIST / AASIST-L (clovaai/aasist, MIT licence) as published, for the "SOTA vs phone" table.

The checkpoints were trained on clean 16 kHz ASVspoof 2019 LA. Scoring follows the official
evaluation code: the first 64,600 samples (about 4 s), repeat-padded if shorter, and the score is
the bona fide logit (``output[:, 1]``). Narrowband audio is resampled back to 16 kHz first, which is
what a wideband model deployed behind a phone line would receive.

Repo setup (once): git clone https://github.com/clovaai/aasist third_party/aasist
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
AASIST_DIR = ROOT / "third_party" / "aasist"
NB_SAMP = 64600


def pad_repeat(x: np.ndarray, n: int = NB_SAMP) -> np.ndarray:
    """Official ``data_utils.pad``: truncate to n, or tile the clip until it reaches n."""
    if len(x) >= n:
        return x[:n]
    return np.tile(x, int(np.ceil(n / len(x))))[:n]


def load_aasist(variant: str = "AASIST") -> torch.nn.Module:
    if not AASIST_DIR.exists():
        raise FileNotFoundError(f"clone clovaai/aasist into {AASIST_DIR}")
    sys.path.insert(0, str(AASIST_DIR))
    from models.AASIST import Model  # type: ignore[import-not-found]

    conf = json.loads((AASIST_DIR / "config" / f"{variant}.conf").read_text())
    model = Model(conf["model_config"])
    state = torch.load(AASIST_DIR / "models" / "weights" / f"{variant}.pth", map_location="cpu")
    model.load_state_dict(state)
    return model.eval()


@torch.no_grad()
def score_aasist(model: torch.nn.Module, clips_16k: Iterable[np.ndarray], batch: int = 32) -> np.ndarray:
    out: list[float] = []
    buf: list[np.ndarray] = []

    def flush() -> None:
        if buf:
            x = torch.from_numpy(np.stack(buf).astype(np.float32))
            out.extend(model(x)[1][:, 1].tolist())
            buf.clear()

    for clip in clips_16k:
        buf.append(pad_repeat(clip))
        if len(buf) == batch:
            flush()
    flush()
    return np.asarray(out)
