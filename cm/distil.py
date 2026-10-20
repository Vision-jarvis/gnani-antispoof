"""LFCC-LCNN student distilled from the XLS-R + AASIST teacher (statement Part B; critique M3).

Same architecture, data pool, crops and epochs as ``lcnn8_aug``; only the target changes:
  target = alpha * sigmoid(teacher_score / T) + (1 - alpha) * hard label     (soft BCE)
``teacher_score`` = teacher logit(bona fide) - logit(spoof) on the TRAIN pool (artifacts/scores/teacher_train.csv,
written by the GPU job). Model selection on dev EER with hard labels, as for every other model, then the
student is scored like the CPU baselines (``lcnn8_distil.csv``, full clips and causal 1/2/4 s prefixes).
  python -m cm.distil               # needs teacher_train.csv from: modal run cm/teacher/modal_train.py
  python -m cm.distil --smoke       # plumbing only: fake teacher scores from the labels, 200 clips, 1 epoch
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace

import numpy as np
import pandas as pd
import torch

from cm.lcnn import n_params
from cm.run_baselines import MODELS, SCORES, eval_rows, labels_of, pool_8k, score_feature_model, write_scores
from cm.train_lcnn import TrainConfig, score_lcnn, train_lcnn
from eval.protocol import assert_protocol

NAME = "lcnn8_distil"


def soft_targets(rows: list[dict[str, str]], teacher: pd.DataFrame, alpha: float, temperature: float) -> np.ndarray:
    t = teacher.set_index(["utt_id", "condition"]).score
    s = np.array([t[(r["utt_id"], r["condition"])] for r in rows], dtype=np.float64)
    hard = labels_of(rows).astype(np.float64)
    return (alpha / (1 + np.exp(-s / temperature)) + (1 - alpha) * hard).astype(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--alpha", type=float, default=0.5)
    ap.add_argument("--temperature", type=float, default=2.0)
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    tr_feats, tr_rows = pool_8k("train", augmented=True)
    assert_protocol(tr_rows, eval_rows("any"))
    dev_feats, dev_rows = pool_8k("dev", augmented=True)
    hard = labels_of(tr_rows)
    if a.smoke:
        rng = np.random.default_rng(0)
        idx = rng.choice(len(tr_rows), 200, replace=False)
        tr_feats, tr_rows, hard = [tr_feats[i] for i in idx], [tr_rows[i] for i in idx], hard[idx]
        teacher = pd.DataFrame({"utt_id": [r["utt_id"] for r in tr_rows], "condition": [r["condition"] for r in tr_rows],
                                "score": 4 * (hard - 0.5) + rng.standard_normal(len(hard))})
        dev_feats, dev_rows = dev_feats[:100], dev_rows[:100]
    else:
        teacher = pd.read_csv(SCORES / "teacher_train.csv")
    y = soft_targets(tr_rows, teacher, a.alpha, a.temperature)
    cfg = replace(TrainConfig(epochs=1 if a.smoke else a.epochs), threads=4)
    t0 = time.time()
    model, history = train_lcnn(tr_feats, y, dev_feats, labels_of(dev_rows), cfg, hard_labels=hard)
    if a.smoke:
        print(f"distil smoke OK: {len(tr_rows)} clips, soft targets {y.min():.2f} to {y.max():.2f}, dev EER {100 * history[-1]['dev_eer']:.1f}%")
        return
    info = {"train_seconds": time.time() - t0, "history": history, "n_train": len(tr_feats), "config": cfg.__dict__,
            "alpha": a.alpha, "temperature": a.temperature, "teacher": "teacher_train.csv"}
    torch.save(model.state_dict(), MODELS / f"{NAME}.pt")
    (MODELS / f"{NAME}_history.json").write_text(json.dumps(info, indent=2))
    scorer = lambda feats: score_lcnn(model, feats)  # noqa: E731
    dev = [{"utt_id": r["utt_id"], "condition": r["condition"], "score": float(s)} for r, s in zip(dev_rows, scorer(dev_feats), strict=True)]
    recs = score_feature_model(NAME, scorer, eight_k=True, streaming=True)
    write_scores(NAME, recs, dev, {"model": NAME, "params": n_params(model), **info})


if __name__ == "__main__":
    main()
