"""Score the published SOTA countermeasures on every channel condition and the Indic pilot (critique B1).

Models (all trained on clean 16 kHz ASVspoof 2019 LA by their authors, scored exactly as published):
  aasist       clovaai/aasist AASIST.pth
  aasist_l     clovaai/aasist AASIST-L.pth
  ssl_aasist   Tak et al. XLS-R 300M + AASIST, LA_model.pth (``cm.ssl_pretrained``)
Inputs are what every CM here receives (``cm_input``), resampled to 16 kHz: a wideband model behind a phone
line. Each (model, condition) cell is one part file under ``artifacts/scores/parts/<model>/``; finished parts
are reused, so a preempted run resumes. Outputs, in the CPU-baseline format:
  artifacts/scores/<model>.csv, <model>_dev.csv (dev clean16k), <model>.json
  artifacts/scores/indic/<model>.csv (Indic pilot, read by ``eval.indic_report``)
Usage: python -m cm.score_pretrained --device cuda [--models ...] [--limit N]   (GPU: modal run cm/modal_pretrained.py)
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from cm.aasist_pretrained import load_aasist, score_aasist
from cm.featurize import load_inputs
from cm.run_baselines import EVAL_CONDITIONS
from factory.channel_sim import resample

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "proc" / "asv19"
PILOT = ROOT / "data" / "proc" / "indic_pilot" / "eval"
SCORES = ROOT / "artifacts" / "scores"
MODELS = ("aasist", "aasist_l", "ssl_aasist")


def load_model(name: str, device: str) -> torch.nn.Module:
    if name == "ssl_aasist":
        from cm.ssl_pretrained import load_ssl_aasist

        return load_ssl_aasist(device=device)
    return load_aasist("AASIST" if name == "aasist" else "AASIST-L").to(device)


def inputs_16k(split_dir: Path, cond: str, limit: int | None) -> tuple[list[str], list[np.ndarray]]:
    ids, clips, sr = load_inputs(split_dir, cond, limit=limit)
    return [str(u) for u in ids], [resample(c, sr, 16000) if sr != 16000 else c for c in clips]


def run(models: tuple[str, ...], device: str, limit: int | None, indic: bool, out: Path) -> dict[str, float]:
    loaded = {m: load_model(m, device) for m in models}
    batch = 32 if device.startswith("cuda") else 4
    cells: list[tuple[str, Path, str, str]] = [("dev", PROC / "dev", "clean16k", "dev")]
    cells += [("eval", PROC / "eval", c, c) for c in EVAL_CONDITIONS]
    if indic and PILOT.exists():
        cells += [("indic", PILOT, c, f"indic_{c}") for c in sorted(p.stem for p in PILOT.glob("*.npz"))]
    seconds: dict[str, float] = {m: 0.0 for m in models}
    for kind, split_dir, cond, tag in cells:
        todo = [m for m in models if not (out / "parts" / m / f"{tag}.csv").exists()]
        if not todo:
            continue
        ids, xs = inputs_16k(split_dir, cond, limit)  # computed once, scored by every model
        for m in todo:
            t0 = time.time()
            s = score_aasist(loaded[m], xs, batch=batch)
            seconds[m] += time.time() - t0
            part = out / "parts" / m / f"{tag}.csv"
            part.parent.mkdir(parents=True, exist_ok=True)
            df = pd.DataFrame({"utt_id": ids, "condition": cond, "score": s})
            if kind == "eval":
                df["horizon"] = 0.0
            df.to_csv(part, index=False)
            print(f"[{m}] {kind}/{cond}: {len(ids)} clips in {time.time() - t0:.0f}s", flush=True)
    for m in models:
        parts = out / "parts" / m
        pd.read_csv(parts / "dev.csv").to_csv(out / f"{m}_dev.csv", index=False)
        pd.concat([pd.read_csv(parts / f"{c}.csv") for c in EVAL_CONDITIONS], ignore_index=True).to_csv(out / f"{m}.csv", index=False)
        indic_parts = sorted(parts.glob("indic_*.csv"))
        if indic_parts:
            (out / "indic").mkdir(parents=True, exist_ok=True)
            pd.concat([pd.read_csv(p) for p in indic_parts], ignore_index=True).to_csv(out / "indic" / f"{m}.csv", index=False)
        meta = {"model": m, "source": "published checkpoint, scored as published", "device": device,
                "score_seconds_this_run": seconds[m], "limit": limit}
        (out / f"{m}.json").write_text(json.dumps(meta, indent=2))
    return seconds


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--models", nargs="+", default=list(MODELS), choices=MODELS)
    ap.add_argument("--limit", type=int, default=None, help="clips per cell (throughput dry run)")
    ap.add_argument("--no-indic", action="store_true")
    ap.add_argument("--out", type=Path, default=SCORES)
    a = ap.parse_args()
    torch.set_num_threads(int(os.environ.get("CM_THREADS", "4")))
    run(tuple(a.models), a.device, a.limit, not a.no_indic, a.out)


if __name__ == "__main__":
    main()
