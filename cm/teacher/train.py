"""Teacher fine-tuning and scoring (PENDING: needs a CUDA GPU; on CPU it runs only as a smoke test).

Reads the packed 8 kHz stores built by ``factory.asvspoof`` (nb_pcm + each utterance's seen codec), upsamples
to 16 kHz, random-crops 1 to 4 s, applies RawBoost, and fine-tunes XLS-R + AASIST with class-balanced CE.

Initialisation: the published SSL+AASIST LA model (``third_party/ssl_ckpt/LA_model.pth``, Tak et al., trained on
the same ASVspoof 2019 LA train set at 16 kHz for up to 100 epochs). The first runs started instead from hub
XLS-R + a random AASIST back end at the recipe lr of 1e-6, which moved the back end almost nowhere in 737 steps
per epoch (dev EER 42 to 45% after 6 epochs; the recipe gets there in about 100 epochs x 1,812 steps).
``--init none`` keeps that from-scratch path. Class weights come from the pool's label counts: the recipe's
[0.1, 0.9] was for a 9:1 spoof:bona fide train set; on this balanced subset it weighted bona fide 9x.

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
from cm.ssl_pretrained import CKPT, convert_state_dict, xlsr_300m_config
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


def class_weights(ys: np.ndarray) -> torch.Tensor:
    """Inverse class frequency, normalised to sum 1: [0.1, 0.9] on a 9:1 spoof:bona fide pool, [0.5, 0.5] balanced."""
    counts = np.bincount(ys, minlength=2).astype(float)
    w = 1.0 / np.maximum(counts, 1.0)
    return torch.tensor(w / w.sum(), dtype=torch.float32)


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


def score_eval(model: nn.Module, device: str, scores_dir: Path, limit: int | None = None,
               horizons: tuple[float, ...] = HORIZONS) -> pd.DataFrame:
    """Every 8 kHz eval condition x (full, causal 1/2/4 s), one part file per cell, existing parts reused."""
    parts = scores_dir / "parts" / "teacher"
    parts.mkdir(parents=True, exist_ok=True)
    frames = []
    for cond in EVAL_CONDITIONS:
        if cond == "clean16k":
            continue  # 8 kHz model: its clean pool is nb_pcm
        for horizon in (None, *horizons):
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


def build(smoke: bool, device: str, init: Path | None = None) -> nn.Module:
    if not smoke:
        if init is None:
            return build_teacher().to(device)  # hub XLS-R + random AASIST (needs far more than 20 epochs at 1e-6)
        # Published LA model, renamed from fairseq; dropout 0.1 as in the fairseq XLS-R fine-tuning config.
        cfg = xlsr_300m_config()
        cfg.hidden_dropout = cfg.attention_dropout = cfg.feat_proj_dropout = 0.1
        model = build_teacher(HFSSLFrontEnd(cfg))
        hf_keys = {k[len("ssl_model.model."):] for k in model.state_dict() if k.startswith("ssl_model.model.")}
        sd = torch.load(init, map_location="cpu", weights_only=False)
        model.load_state_dict(convert_state_dict(sd, hf_keys), strict=True)
        return model.to(device)
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
    ap.add_argument("--init", default=str(CKPT), help="SSL+AASIST checkpoint to start from, or 'none' (hub XLS-R + random AASIST)")
    ap.add_argument("--lr", type=float, default=1e-6, help="XLS-R front end (recipe value)")
    ap.add_argument("--head-lr", type=float, default=None,
                    help="AASIST back end; default = --lr with a trained init, 1e-4 with --init none (a random back end "
                         "at 1e-6 stays at chance: CPU check on frozen XLS-R features, 300 steps, dev EER 45%% vs 5%% at 1e-4)")
    ap.add_argument("--eval", choices=("all", "full", "none"), default="all",
                    help="eval scoring: all (full + causal 1/2/4 s, about 44 min on an L40S), full (full clips only, about "
                         "18 min) or none (dev + train pool only, enough for cm.distil); finished cells are reused on a rerun")
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
    init = None if a.smoke or a.init == "none" else Path(a.init)
    if init is not None and not init.exists():
        sys.exit(f"missing {init}: python -m gdown 11vFBNKzYUtWqdK358_JEygawFzmmaZjO -O {init}  (or pass --init none)")
    model = build(a.smoke, device, init)
    xs, ys, rows = load_pool("train", limit=8 if a.smoke else None)
    assert_protocol(rows, [{"speaker": "eval-only", "attack": "bonafide", "condition": "gsm_fr"}])
    dev_x, dev_y, dev_rows = load_pool("dev", limit=6 if a.smoke else None)
    weights = class_weights(ys)
    print(f"train pool: {len(ys)} clips, {int(ys.sum())} bona fide; class weights (spoof, bona fide) {weights.tolist()}; init {init}", flush=True)
    loss_fn = nn.CrossEntropyLoss(weight=weights.to(device))
    head_lr = a.head_lr if a.head_lr is not None else (a.lr if init is not None or a.smoke else 1e-4)
    ssl_params = list(model.ssl_model.parameters())
    ssl_ids = {id(q) for q in ssl_params}
    opt = torch.optim.Adam([{"params": ssl_params, "lr": a.lr},
                            {"params": [q for q in model.parameters() if id(q) not in ssl_ids], "lr": head_lr}], weight_decay=1e-4)
    rng = np.random.default_rng(0)
    history, best, bad = [], (np.inf, -1), 0
    if init is not None:  # where fine-tuning starts from (the published 16 kHz model on the 8 kHz dev pool)
        s = score_clips(model, dev_x, device)
        history.append({"epoch": -1, "dev_eer": eer(s[dev_y == 1], s[dev_y == 0])})
        print(f"init: dev EER {100 * history[-1]['dev_eer']:.2f}%", flush=True)
    for epoch in range(epochs):
        ckpt = out_models / f"teacher_epoch{epoch}.pt"
        if ckpt.exists():  # resume after preemption: reuse finished epochs
            model.load_state_dict(torch.load(ckpt, map_location=device))
        else:
            model.train()
            t0, losses = time.time(), []
            for step, (x, y) in enumerate(batches(xs, ys, bs, rng, augment=True)):
                loss = loss_fn(model(x.to(device)), y.to(device))
                opt.zero_grad()
                loss.backward()
                opt.step()
                losses.append(float(loss))
                if a.smoke and step == 1:
                    print(f"smoke: 2 steps, loss {float(loss):.4f}, {time.time() - t0:.1f}s")
                    break
            print(f"epoch {epoch}: {len(losses)} steps, train loss {np.mean(losses):.4f}, {time.time() - t0:.0f}s", flush=True)
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
    # train pool first: it is all cm.distil needs, so a timeout during eval scoring does not lose it
    tr_s = score_clips(model, xs, device)
    pd.DataFrame({"utt_id": [r["utt_id"] for r in rows], "condition": [r["condition"] for r in rows], "score": tr_s}).to_csv(
        out_scores / "teacher_train.csv", index=False)
    if a.eval != "none":
        score_eval(model, device, out_scores, limit, horizons=HORIZONS if a.eval == "all" else ()).to_csv(
            out_scores / "teacher.csv", index=False)
    meta = {"model": "teacher", "front_end": "facebook/wav2vec2-xls-r-300m", "back_end": "AASIST (TakHemlata/SSL_Anti-spoofing)",
            "init": str(init.name) if init else "hub XLS-R + random AASIST", "lr": a.lr, "head_lr": head_lr, "class_weights": weights.tolist(),
            "best_epoch": best_epoch, "history": history, "n_train": len(xs), "device": device,
            "wall_hours": (time.time() - t_start) / 3600, "smoke": a.smoke}
    (out_scores / "teacher.json").write_text(json.dumps(meta, indent=2))
    print(f"{'smoke OK' if a.smoke else 'teacher done'}: best epoch {best_epoch}, {meta['wall_hours']:.3f} h, scores in {out_scores}")


if __name__ == "__main__":
    main()
