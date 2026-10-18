"""Light CNN (LCNN) on LFCC, after the ASVspoof 2021 B03 baseline (Wang and Yamagishi, 2021).

Max-Feature-Map (MFM) activations halve the channels by taking an element-wise max of two halves,
which acts as a learned feature selector and keeps the model small. Differences from B03, chosen for
CPU training and streaming: no BLSTM (time is pooled by mean + standard deviation, so any length
works and a prefix of the call can be scored directly), and global CMVN statistics are stored as
buffers so the exported model needs only raw LFCC.
"""

from __future__ import annotations

import torch
from torch import nn


class MFM(nn.Module):
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        a, b = x.chunk(2, dim=1)
        return torch.maximum(a, b)


def _block(c_in: int, c_out: int, k: int) -> list[nn.Module]:
    return [nn.Conv2d(c_in, 2 * c_out, k, padding=k // 2), MFM()]


class LCNN(nn.Module):
    def __init__(self, n_feats: int = 60, width: int = 32, dropout: float = 0.3) -> None:
        super().__init__()
        w = width
        self.register_buffer("feat_mean", torch.zeros(n_feats))
        self.register_buffer("feat_std", torch.ones(n_feats))
        self.body = nn.Sequential(
            *_block(1, w, 5), nn.MaxPool2d(2),
            *_block(w, w, 1), nn.BatchNorm2d(w), *_block(w, int(1.5 * w), 3), nn.MaxPool2d(2), nn.BatchNorm2d(int(1.5 * w)),
            *_block(int(1.5 * w), int(1.5 * w), 1), nn.BatchNorm2d(int(1.5 * w)), *_block(int(1.5 * w), 2 * w, 3), nn.MaxPool2d(2),
            *_block(2 * w, 2 * w, 1), nn.BatchNorm2d(2 * w), *_block(2 * w, w, 3), nn.BatchNorm2d(w),
            *_block(w, w, 1), nn.BatchNorm2d(w), *_block(w, w, 3), nn.MaxPool2d(2),
        )
        f_out = n_feats // 16
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(2 * w * f_out, 64), MFM1d(), nn.Linear(32, 1))

    def forward(self, feats: torch.Tensor) -> torch.Tensor:
        """feats: (B, T, F) raw LFCC -> (B,) logit, higher = more bona fide."""
        x = (feats - self.feat_mean) / self.feat_std
        h = self.body(x.transpose(1, 2).unsqueeze(1))  # (B, C, F', T')
        h = h.flatten(1, 2)  # (B, C*F', T')
        pooled = torch.cat([h.mean(-1), h.std(-1, unbiased=False)], dim=1)
        return self.head(pooled).squeeze(-1)


class MFM1d(nn.Module):
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        a, b = x.chunk(2, dim=-1)
        return torch.maximum(a, b)


def n_params(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())
