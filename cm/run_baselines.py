"""Train and score the CPU baselines on the ASVspoof 2019 LA subsets; writes artifacts/scores/*.csv.

Models
  gmm16_clean   LFCC-GMM on clean 16 kHz (the classic wideband recipe); 8 kHz eval audio is resampled to 16 kHz
  gmm8_aug      LFCC-GMM at 8 kHz, trained on nb_pcm + one seen codec per utterance
  lcnn8_aug     LFCC-LCNN at 8 kHz, same training data as gmm8_aug
  lcnn8_noaug   ablation: LFCC-LCNN at 8 kHz on nb_pcm only (no codec augmentation)
  aasist, aasist_l  pretrained clovaai checkpoints (16 kHz, clean training), scored as published

Every model's dev scores (for thresholds and calibration) come from the dev split only.
Usage: python -m cm.run_baselines [--models lcnn8_aug gmm8_aug ...] [--epochs 12]
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from cm.aasist_pretrained import load_aasist, score_aasist
from cm.featurize import FeatureSet, load_features
from cm.gmm import LFCCGMM
from cm.lcnn import LCNN, n_params
from cm.train_lcnn import TrainConfig, score_lcnn, train_lcnn
from eval.protocol import assert_protocol
from factory.channel_sim import CONDITIONS, resample
from factory.normalise import cm_input
from factory.store import load_packed

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "proc" / "asv19"
SCORES = ROOT / "artifacts" / "scores"
MODELS = ROOT / "artifacts" / "models"
EVAL_CONDITIONS = ["clean16k", *CONDITIONS]
HORIZONS = (1.0, 2.0, 4.0)
ALL_MODELS = ("gmm16_clean", "gmm8_aug", "lcnn8_aug", "lcnn8_noaug", "aasist", "aasist_l")


def manifest(split: str) -> pd.DataFrame:
    return pd.read_csv(PROC / split / "manifest.csv")


def pool_8k(split: str, augmented: bool, horizon: float | None = None) -> tuple[list[np.ndarray], list[dict[str, str]]]:
    """Features + rows for nb_pcm (and, if ``augmented``, each utterance's drawn seen codec)."""
    man = manifest(split).set_index("utt_id")
    conds = ["nb_pcm"] + (sorted(man.aug_condition.unique()) if augmented else [])
    feats: list[np.ndarray] = []
    rows: list[dict[str, str]] = []
    for c in conds:
        fs = load_features(PROC / split, c, horizon)
        for i, u in enumerate(fs.utt_ids):
            m = man.loc[str(u)]
            feats.append(fs.get(i))
            rows.append({"utt_id": str(u), "speaker": m.speaker, "attack": m.attack, "label": m.label, "condition": c})
    return feats, rows


def labels_of(rows: Sequence[dict[str, str]]) -> np.ndarray:
    return np.array([r["label"] == "bonafide" for r in rows], dtype=np.int64)


def eval_rows(cond: str) -> list[dict[str, str]]:
    man = manifest("eval")
    return [{"utt_id": u, "speaker": s, "attack": a, "label": lab, "condition": cond}
            for u, s, a, lab in zip(man.utt_id, man.speaker, man.attack, man.label, strict=True)]


def write_scores(name: str, records: list[dict[str, object]], dev_records: list[dict[str, object]], meta: dict[str, object]) -> None:
    SCORES.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(SCORES / f"{name}.csv", index=False)
    pd.DataFrame(dev_records).to_csv(SCORES / f"{name}_dev.csv", index=False)
    (SCORES / f"{name}.json").write_text(json.dumps(meta, indent=2))


def _records(fs: FeatureSet, scores: np.ndarray, cond: str, horizon: float) -> list[dict[str, object]]:
    return [{"utt_id": str(u), "condition": cond, "horizon": horizon, "score": float(s)}
            for u, s in zip(fs.utt_ids, scores, strict=True)]


def score_feature_model(name: str, scorer: Callable[[list[np.ndarray]], np.ndarray], eight_k: bool, streaming: bool) -> list[dict[str, object]]:
    recs: list[dict[str, object]] = []
    for cond in EVAL_CONDITIONS:
        if eight_k and cond == "clean16k":
            continue
        resample_to = 16000 if (not eight_k and cond != "clean16k") else None
        for horizon in (None, *(HORIZONS if streaming else ())):
            fs = load_features(PROC / "eval", cond, horizon, resample_to=resample_to)
            recs += _records(fs, scorer(fs.all()), cond, horizon or 0.0)
        print(f"[{name}] scored eval/{cond}", flush=True)
    return recs


def run_gmm(name: str) -> None:
    t0 = time.time()
    if name == "gmm16_clean":
        tr, dv = load_features(PROC / "train", "clean16k"), load_features(PROC / "dev", "clean16k")
        tr_rows = [{**r, "condition": "clean16k"} for r in manifest("train").to_dict("records")]
        tr_feats, tr_lab = tr.all(), (manifest("train").set_index("utt_id").loc[tr.utt_ids.astype(str), "label"] == "bonafide").to_numpy()
        dev_feats, dev_ids, dev_conds = dv.all(), dv.utt_ids.astype(str), ["clean16k"] * len(dv.utt_ids)
    else:
        tr_feats, tr_rows = pool_8k("train", augmented=True)
        tr_lab = labels_of(tr_rows).astype(bool)
        dev_feats, dev_rows = pool_8k("dev", augmented=True)
        dev_ids, dev_conds = [r["utt_id"] for r in dev_rows], [r["condition"] for r in dev_rows]
    assert_protocol(tr_rows, eval_rows("any"))
    gmm_path = MODELS / f"{name}.npz"
    if gmm_path.exists():
        gmm = LFCCGMM.load(gmm_path)
    else:
        gmm = LFCCGMM.train([f for f, b in zip(tr_feats, tr_lab, strict=True) if b], [f for f, b in zip(tr_feats, tr_lab, strict=True) if not b])
        gmm.save(gmm_path)
    train_s = time.time() - t0
    scorer = gmm.score_many
    dev = [{"utt_id": u, "condition": c, "score": s} for u, c, s in zip(dev_ids, dev_conds, scorer(dev_feats), strict=True)]
    recs = score_feature_model(name, scorer, eight_k=name != "gmm16_clean", streaming=name == "gmm8_aug")
    write_scores(name, recs, dev, {"model": name, "train_seconds": train_s, "components": 128, "n_train": len(tr_feats)})


def run_lcnn(name: str, epochs: int, train_only: bool = False) -> None:
    """Train (or reuse artifacts/models/<name>.pt) and score. ``train_only`` stops before eval scoring."""
    augmented = name == "lcnn8_aug"
    dev_feats, dev_rows = pool_8k("dev", augmented=True)
    ckpt, hist_path = MODELS / f"{name}.pt", MODELS / f"{name}_history.json"
    if ckpt.exists():
        model = LCNN()
        model.load_state_dict(torch.load(ckpt))
        model.eval()
        info = json.loads(hist_path.read_text())
    else:
        tr_feats, tr_rows = pool_8k("train", augmented)
        assert_protocol(tr_rows, eval_rows("any"))
        cfg = TrainConfig(epochs=epochs)
        t0 = time.time()
        model, history = train_lcnn(tr_feats, labels_of(tr_rows), dev_feats, labels_of(dev_rows), cfg)
        info = {"train_seconds": time.time() - t0, "history": history, "n_train": len(tr_feats), "config": cfg.__dict__}
        MODELS.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), ckpt)
        hist_path.write_text(json.dumps(info, indent=2))
    if train_only:
        return
    scorer = lambda feats: score_lcnn(model, feats)  # noqa: E731
    dev = [{"utt_id": r["utt_id"], "condition": r["condition"], "score": float(s)} for r, s in zip(dev_rows, scorer(dev_feats), strict=True)]
    recs = score_feature_model(name, scorer, eight_k=True, streaming=augmented)
    write_scores(name, recs, dev, {"model": name, "params": n_params(model), **info})


def run_aasist(name: str) -> None:
    torch.set_num_threads(12)
    model = load_aasist("AASIST" if name == "aasist" else "AASIST-L")

    def clips(split: str, cond: str) -> tuple[list[str], list[np.ndarray]]:
        p = load_packed(PROC / split / f"{cond}.npz")
        return [str(u) for u in p.utt_ids], [resample(cm_input(p.get(i), p.sr), p.sr, 16000) for i in range(len(p))]

    ids, xs = clips("dev", "clean16k")
    dev = [{"utt_id": u, "condition": "clean16k", "score": float(s)} for u, s in zip(ids, score_aasist(model, xs), strict=True)]
    recs: list[dict[str, object]] = []
    for cond in EVAL_CONDITIONS:
        t0 = time.time()
        ids, xs = clips("eval", cond)
        recs += [{"utt_id": u, "condition": cond, "horizon": 0.0, "score": float(s)} for u, s in zip(ids, score_aasist(model, xs), strict=True)]
        print(f"[{name}] scored eval/{cond} in {time.time() - t0:.0f}s", flush=True)
    write_scores(name, recs, dev, {"model": name, "params": n_params(model), "source": "clovaai/aasist pretrained"})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=list(ALL_MODELS), choices=ALL_MODELS)
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--train-only", action="store_true", help="LCNN: train and save, skip eval scoring")
    a = ap.parse_args()
    for m in a.models:
        t0 = time.time()
        if m.startswith("gmm"):
            run_gmm(m)
        elif m.startswith("lcnn"):
            run_lcnn(m, a.epochs, a.train_only)
        else:
            run_aasist(m)
        print(f"== {m} done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
