"""Teacher fine-tuning and scoring (PENDING: needs a CUDA GPU; on CPU it runs only as a smoke test).

Reads the packed 8 kHz stores built by ``factory.asvspoof`` (nb_pcm + each utterance's seen codec), upsamples
to 16 kHz, random-crops 1 to 4 s, applies RawBoost, and fine-tunes XLS-R + AASIST with weighted CE.

Per epoch: checkpoint to ``<out>/models/teacher_epoch<k>.pt``, dev EER on the dev pool (the same pool the CPU
baselines use), early stop on dev EER. Then, with the best epoch:
  <out>/scores/teacher_dev.csv     dev pool scores (calibration and thresholds, as for the CPU baselines)
  <out>/scores/teacher.csv         every eval condition x (full clip, 1 s, 2 s, 4 s causal prefixes), in the
                                   CPU-baseline format, so ``python -m eval.report`` picks it up unchanged
  <out>/scores/teacher_train.csv   train pool scores (the soft targets for ``cm.distil``)
  <out>/scores/teacher.json        epochs, dev EER history, wall-clock GPU hours (statement rule 8)
Eval cells are written one part file at a time under ``<out>/scores/parts/teacher/`` and reused on a rerun,
so a preempted job loses at most one cell. Score = logit(bona fide) - logit(spoof).

  python -m cm.teacher.train --smoke            # CPU, tiny random front-end: 2 steps + scoring of 3 clips/cell
  python -m cm.teacher.train --device cuda      # the real run (modal run cm/teacher/modal_train.py)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn

from cm.featurize import load_inputs
from cm.run_baselines import EVAL_CONDITIONS, HORIZONS, manifest
from cm.teacher.model import SSL_REPO, HFSSLFrontEnd, build_teacher
from eval.metrics import eer
from eval.protocol import assert_protocol
from factory.channel_sim import resample
from factory.normalise import cm_input
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


def load_pool(split: str, limit: int | None = None) -> tuple[list[np.ndarray], np.ndarray, list[dict[str, str]]]:
    """nb_pcm + each utterance's drawn seen codec (the CPU baselines' pool), as the CM receives it, at 16 kHz."""
    man = manifest(split).set_index("utt_id")
    xs, ys, rows = [], [], []
    for c in ["nb_pcm", *sorted(man.aug_condition.unique())]:
        p = load_packed(PROC / split / f"{c}.npz")
        for i, u in enumerate(p.utt_ids):
            m = man.loc[str(u)]
            if c != "nb_pcm" and m.aug_condition != c:
                continue
            if limit is not None and len(xs) >= limit:
                break
            xs.append(resample(cm_input(p.get(i), p.sr), p.sr, 16000))
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


@torch.no_grad()
def score_clips(model: nn.Module, clips: list[np.ndarray], device: str) -> np.ndarray:
    """One clip per forward (variable length, no padding); fp16 autocast on CUDA."""
    model.eval()
    out = []
    for x in clips:
        with torch.autocast("cuda", enabled=device.startswith("cuda")):
            o = model(torch.tensor(x[None], dtype=torch.float32, device=device))
        out.append(float(o[0, 1] - o[0, 0]))
    return np.array(out)


def score_eval(model: nn.Module, device: str, scores_dir: Path, limit: int | None = None) -> pd.DataFrame:
    """Every 8 kHz eval condition x (full, causal 1/2/4 s), one part file per cell, existing parts reused."""
    parts = scores_dir / "parts" / "teacher"
    parts.mkdir(parents=True, exist_ok=True)
    frames = []
    for cond in EVAL_CONDITIONS:
        if cond == "clean16k":
            continue  # 8 kHz model: its clean pool is nb_pcm
        for horizon in (None, *HORIZONS):
            part = parts / f"{cond}_{'full' if horizon is None else f'h{horizon:g}causal'}.csv"
            if not part.exists():
                t0 = time.time()
                ids, clips, sr = load_inputs(PROC / "eval", cond, horizon, limit=limit)
                clips = [resample(c, sr, 16000) for c in clips]
                pd.DataFrame({"utt_id": [str(u) for u in ids], "condition": cond, "horizon": horizon or 0.0,
                              "score": score_clips(model, clips, device)}).to_csv(part, index=False)
                print(f"[teacher] eval/{cond} horizon {horizon or 'full'}: {len(ids)} clips in {time.time() - t0:.0f}s", flush=True)
            frames.append(pd.read_csv(part))
    return pd.concat(frames, ignore_index=True)


def build(smoke: bool, device: str) -> nn.Module:
    if not smoke:
        return build_teacher().to(device)
    from transformers import Wav2Vec2Config

    cfg = Wav2Vec2Config(hidden_size=64, num_hidden_layers=1, num_attention_heads=2, intermediate_size=64,
                         conv_dim=(32,) * 7, num_feat_extract_layers=7)
    return build_teacher(HFSSLFrontEnd(cfg)).to(device)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--patience", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=14)
    ap.add_argument("--out", type=Path, default=None, help="default artifacts/ (smoke: artifacts/smoke_teacher/)")
    ap.add_argument("--smoke", action="store_true", help="CPU, tiny random front-end, 2 steps, 3 clips per scoring cell")
    a = ap.parse_args()
    t_start = time.time()
    device = "cpu" if a.smoke else a.device
    epochs, bs, limit = (1, 2, 3) if a.smoke else (a.epochs, a.batch_size, None)
    out = a.out or (ROOT / "artifacts" / ("smoke_teacher" if a.smoke else ""))
    out_models, out_scores = out / "models", out / "scores"
    out_models.mkdir(parents=True, exist_ok=True)
    out_scores.mkdir(parents=True, exist_ok=True)
    model = build(a.smoke, device)
    xs, ys, rows = load_pool("train", limit=8 if a.smoke else None)
    assert_protocol(rows, [{"speaker": "eval-only", "attack": "bonafide", "condition": "gsm_fr"}])
    dev_x, dev_y, dev_rows = load_pool("dev", limit=6 if a.smoke else None)
    loss_fn = nn.CrossEntropyLoss(weight=torch.tensor([0.1, 0.9], device=device))
    opt = torch.optim.Adam(model.parameters(), lr=1e-6, weight_decay=1e-4)
    rng = np.random.default_rng(0)
    history, best, bad = [], (np.inf, -1), 0
    for epoch in range(epochs):
        ckpt = out_models / f"teacher_epoch{epoch}.pt"
        if ckpt.exists():  # resume after preemption: reuse finished epochs
            model.load_state_dict(torch.load(ckpt, map_location=device))
        else:
            model.train()
            t0 = time.time()
            for step, (x, y) in enumerate(batches(xs, ys, bs, rng, augment=True)):
                loss = loss_fn(model(x.to(device)), y.to(device))
                opt.zero_grad()
                loss.backward()
                opt.step()
                if a.smoke and step == 1:
                    print(f"smoke: 2 steps, loss {float(loss):.4f}, {time.time() - t0:.1f}s")
                    break
            torch.save(model.state_dict(), ckpt)
        s = score_clips(model, dev_x, device)
        dev_eer = eer(s[dev_y == 1], s[dev_y == 0]) if len(set(dev_y)) == 2 else float("nan")
        history.append({"epoch": epoch, "dev_eer": dev_eer})
        print(f"epoch {epoch}: dev EER {100 * dev_eer:.2f}%", flush=True)
        if dev_eer < best[0]:
            best, bad = (dev_eer, epoch), 0
        else:
            bad += 1
            if bad >= a.patience:
                break
    best_epoch = max(best[1], 0)
    model.load_state_dict(torch.load(out_models / f"teacher_epoch{best_epoch}.pt", map_location=device))
    torch.save(model.state_dict(), out_models / "teacher_ssl_aasist_8k.pt")
    dev_s = score_clips(model, dev_x, device)
    pd.DataFrame({"utt_id": [r["utt_id"] for r in dev_rows], "condition": [r["condition"] for r in dev_rows], "score": dev_s}).to_csv(
        out_scores / "teacher_dev.csv", index=False)
    score_eval(model, device, out_scores, limit).to_csv(out_scores / "teacher.csv", index=False)
    tr_s = score_clips(model, xs, device)
    pd.DataFrame({"utt_id": [r["utt_id"] for r in rows], "condition": [r["condition"] for r in rows], "score": tr_s}).to_csv(
        out_scores / "teacher_train.csv", index=False)
    meta = {"model": "teacher", "front_end": "facebook/wav2vec2-xls-r-300m", "back_end": "AASIST (TakHemlata/SSL_Anti-spoofing)",
            "best_epoch": best_epoch, "history": history, "n_train": len(xs), "device": device,
            "wall_hours": (time.time() - t_start) / 3600, "smoke": a.smoke}
    (out_scores / "teacher.json").write_text(json.dumps(meta, indent=2))
    print(f"{'smoke OK' if a.smoke else 'teacher done'}: best epoch {best_epoch}, {meta['wall_hours']:.3f} h, scores in {out_scores}")


if __name__ == "__main__":
    main()
