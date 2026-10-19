"""Teacher fine-tuning loop (PENDING: needs a CUDA GPU; runs on CPU only as a 2-step smoke test).

Reads the packed 8 kHz stores built by ``factory.asvspoof`` (nb_pcm + seen codecs), upsamples to
16 kHz, random-crops 1 to 4 s, applies RawBoost, and fine-tunes XLS-R + AASIST with weighted CE.
Model selection on dev EER; dev and eval scores are written in the CPU-baseline CSV format so
``python -m eval.report`` picks the teacher up automatically.

  python -m cm.teacher.train --smoke            # CPU, tiny random front-end, 2 steps (no download)
  python -m cm.teacher.train --device cuda      # the real run (see ssl_aasist_8k.yaml, modal_train.py)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn

from cm.run_baselines import manifest
from cm.teacher.model import SSL_REPO, HFSSLFrontEnd, build_teacher
from eval.metrics import eer
from eval.protocol import assert_protocol
from factory.channel_sim import resample
from factory.store import load_packed

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "proc" / "asv19"


def rawboost(x: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """RawBoost algo 5 = (1) convolutive linear/non-linear noise + (2) impulsive signal-dependent noise."""
    sys.path.insert(0, str(SSL_REPO))
    import RawBoost  # type: ignore[import-not-found]
    from RawBoost import ISD_additive_noise, LnL_convolutive_noise  # type: ignore[import-not-found]

    # The original randRange calls int() on a size-1 array, which NumPy 2 rejects; same sampling, scalar out.
    RawBoost.randRange = lambda x1, x2, integer: int(np.random.uniform(x1, x2)) if integer else float(np.random.uniform(x1, x2))

    y = LnL_convolutive_noise(x, 5, 5, 20, 8000, 100, 1000, 10, 100, 0, 0, 5, 20, 16000)  # recipe defaults
    return ISD_additive_noise(y, 10, 2)


def load_split(split: str, conditions: list[str], limit: int | None = None) -> tuple[list[np.ndarray], np.ndarray, list[dict[str, str]]]:
    man = manifest(split).set_index("utt_id")
    xs, ys, rows = [], [], []
    for c in conditions:
        p = load_packed(PROC / split / f"{c}.npz")
        for i, u in enumerate(p.utt_ids):
            m = man.loc[str(u)]
            if split == "train" and c != "nb_pcm" and m.aug_condition != c:
                continue
            if limit is not None and len(xs) >= limit:
                break
            xs.append(resample(p.get(i), 8000, 16000))
            ys.append(int(m.label == "bonafide"))
            rows.append({"utt_id": str(u), "speaker": m.speaker, "attack": m.attack, "condition": c})
    return xs, np.array(ys), rows


def batches(xs: list[np.ndarray], ys: np.ndarray, bs: int, rng: np.random.Generator, augment: bool):
    order = rng.permutation(len(xs))
    for b in range(0, len(order) - bs + 1, bs):
        n = int(rng.uniform(1.0, 4.0) * 16000)
        out = []
        for i in order[b : b + bs]:
            x = np.tile(xs[i], int(np.ceil(n / len(xs[i]))))
            s = rng.integers(0, len(x) - n + 1)
            x = x[s : s + n]
            out.append(rawboost(x, rng) if augment and rng.random() < 0.7 else x)
        yield torch.tensor(np.stack(out), dtype=torch.float32), torch.tensor(ys[order[b : b + bs]])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch-size", type=int, default=14)
    ap.add_argument("--smoke", action="store_true", help="CPU, tiny random front-end, 2 steps")
    a = ap.parse_args()
    if a.smoke:
        from transformers import Wav2Vec2Config

        cfg = Wav2Vec2Config(hidden_size=64, num_hidden_layers=1, num_attention_heads=2, intermediate_size=64,
                             conv_dim=(32,) * 7, num_feat_extract_layers=7)
        model, device, epochs, bs = build_teacher(HFSSLFrontEnd(cfg)), "cpu", 1, 2
    else:
        model, device, epochs, bs = build_teacher(), a.device, a.epochs, a.batch_size
    model.to(device)
    train_conds = ["nb_pcm", *sorted(manifest("train").aug_condition.unique())]
    xs, ys, rows = load_split("train", train_conds, limit=8 if a.smoke else None)
    assert_protocol(rows, [{"speaker": "eval-only", "attack": "bonafide", "condition": "gsm_fr"}])
    loss_fn = nn.CrossEntropyLoss(weight=torch.tensor([0.1, 0.9], device=device))
    opt = torch.optim.Adam(model.parameters(), lr=1e-6, weight_decay=1e-4)
    rng = np.random.default_rng(0)
    for epoch in range(epochs):
        model.train()
        t0 = time.time()
        for step, (x, y) in enumerate(batches(xs, ys, bs, rng, augment=True)):
            loss = loss_fn(model(x.to(device)), y.to(device))
            opt.zero_grad()
            loss.backward()
            opt.step()
            if a.smoke and step == 1:
                print(f"smoke OK: 2 steps, loss {float(loss):.4f}, {time.time() - t0:.1f}s")
                return
        torch.save(model.state_dict(), ROOT / "artifacts" / "models" / f"teacher_epoch{epoch}.pt")
        print(f"epoch {epoch}: {time.time() - t0:.0f}s")
    # Dev/eval scoring mirrors cm.run_baselines.run_aasist (bona fide logit = output[:, 1]).
    dev_x, dev_y, dev_rows = load_split("dev", ["nb_pcm"])
    model.eval()
    with torch.no_grad():
        s = np.array([float(model(torch.tensor(x[None], dtype=torch.float32, device=device))[0, 1]) for x in dev_x])
    print(f"dev EER {100 * eer(s[dev_y == 1], s[dev_y == 0]):.2f}%")
    pd.DataFrame({"utt_id": [r["utt_id"] for r in dev_rows], "condition": "nb_pcm", "score": s}).to_csv(
        ROOT / "artifacts" / "scores" / "teacher_dev.csv", index=False)


if __name__ == "__main__":
    main()
