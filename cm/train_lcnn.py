"""CPU training loop for the LFCC-LCNN countermeasure.

Random 2 s crops (repeat-padded when shorter), class-balanced BCE, Adam. The checkpoint with the
lowest dev EER is kept; dev is the matching dev pool (never eval), so model selection does not see
eval data. Training rows must already have passed ``eval.protocol.assert_protocol``.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
import torch
from torch import nn

from cm.lcnn import LCNN, pad_frames
from eval.metrics import eer


@dataclass(frozen=True)
class TrainConfig:
    epochs: int = 8
    batch_size: int = 64
    crop_frames: int = 200  # 2 s, the primary decision horizon
    lr: float = 1e-3
    weight_decay: float = 1e-4
    seed: int = 0
    threads: int = 12


def _crop(f: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    if len(f) < n:
        f = np.tile(f, (int(np.ceil(n / len(f))), 1))
    start = rng.integers(0, len(f) - n + 1)
    return f[start : start + n]


@torch.no_grad()
def score_lcnn(model: LCNN, feats: Sequence[np.ndarray]) -> np.ndarray:
    """Score full-length utterances one by one (variable length, no padding artefacts)."""
    model.eval()
    return np.array([float(model(torch.from_numpy(pad_frames(f)[None].astype(np.float32)))) for f in feats])


def train_lcnn(
    train_feats: Sequence[np.ndarray],
    train_labels: np.ndarray,
    dev_feats: Sequence[np.ndarray],
    dev_labels: np.ndarray,
    cfg: TrainConfig = TrainConfig(),
    log: Callable[[str], None] = lambda m: print(m, flush=True),
    hard_labels: np.ndarray | None = None,
) -> tuple[LCNN, list[dict[str, float]]]:
    """labels: 1 = bona fide, 0 = spoof; or soft targets in [0, 1] (distillation) with ``hard_labels`` given
    for the class balance weight."""
    torch.manual_seed(cfg.seed)
    torch.set_num_threads(cfg.threads)
    rng = np.random.default_rng(cfg.seed)
    model = LCNN()
    stacked = np.concatenate(train_feats).astype(np.float64)
    model.feat_mean.copy_(torch.from_numpy(stacked.mean(0)).float())
    model.feat_std.copy_(torch.from_numpy(stacked.std(0) + 1e-5).float())
    del stacked
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=cfg.epochs)
    hard = train_labels if hard_labels is None else hard_labels
    pos_weight = torch.tensor((hard == 0).sum() / max(1, (hard == 1).sum()), dtype=torch.float32)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    best_eer, best_state, history = np.inf, None, []
    dev_bona = dev_labels == 1
    for epoch in range(cfg.epochs):
        model.train()
        t0, losses = time.time(), []
        order = rng.permutation(len(train_feats))
        for b in range(0, len(order), cfg.batch_size):
            idx = order[b : b + cfg.batch_size]
            x = torch.from_numpy(np.stack([_crop(train_feats[i], cfg.crop_frames, rng) for i in idx]).astype(np.float32))
            y = torch.from_numpy(train_labels[idx].astype(np.float32))
            loss = loss_fn(model(x), y)
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss.detach()))
            if (b // cfg.batch_size) % 40 == 0:
                log(f"  epoch {epoch + 1} batch {b // cfg.batch_size} loss {float(loss.detach()):.4f} ({time.time() - t0:.0f}s)")
        sched.step()
        s = score_lcnn(model, dev_feats)
        dev_eer = eer(s[dev_bona], s[~dev_bona])
        history.append({"epoch": epoch + 1, "loss": float(np.mean(losses)), "dev_eer": dev_eer, "sec": time.time() - t0})
        log(f"epoch {epoch + 1}/{cfg.epochs} loss {np.mean(losses):.4f} dev EER {100 * dev_eer:.2f}% ({time.time() - t0:.0f}s)")
        if dev_eer < best_eer:
            best_eer, best_state = dev_eer, {k: v.clone() for k, v in model.state_dict().items()}
    assert best_state is not None
    model.load_state_dict(best_state)
    model.eval()
    return model, history
