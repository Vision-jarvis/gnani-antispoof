"""Score the fine-tuned 8 kHz teacher (best epoch, ``teacher_ssl_aasist_8k.pt``) on the Indic pilot set.

The teacher is an 8 kHz model, so it gets the six telephony conditions of the pilot (not ``clean16k``), each
clip exactly as every CM here receives it (``cm_input`` on the 8 kHz store), then upsampled to 16 kHz as in
``cm.teacher.train.score_eval``. One part file per condition, reused on a rerun. Output in the format
``eval.indic_report`` reads for GPU-scored models: ``<out>/indic/teacher.csv`` (utt_id, condition, score).

GPU: ``modal run --detach cm/teacher/modal_train.py::indic_main``, then ``modal run cm/teacher/modal_train.py::indic_fetch``
and ``python -m eval.indic_report``. CPU works too, but at about 1 s per clip (7,200 clips) it takes about 2 h.

The pilot fails its shortcut audit (duration alone: 16.6% EER), so the teacher row supports no model claim.
"""

from __future__ import annotations

import argparse
import os
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from cm.featurize import load_inputs
from factory.channel_sim import resample
from factory.indic_pilot import CONDITIONS

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / "data" / "proc" / "indic_pilot" / "eval"
CKPT = ROOT / "artifacts" / "models" / "teacher_ssl_aasist_8k.pt"
OUT = ROOT / "artifacts" / "scores"


def pilot_conditions(pilot: Path) -> list[str]:
    """The 8 kHz conditions present in the pilot store, in CONDITIONS order (clean16k is not an 8 kHz input)."""
    return [c for c in CONDITIONS if (pilot / f"{c}.npz").exists()]


def load_teacher(ckpt: Path, device: str) -> torch.nn.Module:
    from cm.ssl_pretrained import xlsr_300m_config
    from cm.teacher.model import HFSSLFrontEnd, build_teacher

    model = build_teacher(HFSSLFrontEnd(xlsr_300m_config()))
    model.load_state_dict(torch.load(ckpt, map_location="cpu"), strict=True)
    return model.to(device).eval()


def score_pilot(score_fn: Callable[[list[np.ndarray]], np.ndarray], pilot: Path, out: Path,
                limit: int | None = None) -> pd.DataFrame:
    """Score every 8 kHz pilot condition with ``score_fn`` (16 kHz clips -> scores); write out/indic/teacher.csv."""
    parts = out / "parts" / "teacher_indic"
    parts.mkdir(parents=True, exist_ok=True)
    conds = pilot_conditions(pilot)
    if not conds:
        raise FileNotFoundError(f"no 8 kHz pilot stores in {pilot}")
    frames = []
    for cond in conds:
        part = parts / f"{cond}.csv"
        if not part.exists():
            t0 = time.time()
            ids, clips, sr = load_inputs(pilot, cond, limit=limit)
            clips = [resample(c, sr, 16000) if sr != 16000 else c for c in clips]
            s = np.asarray(score_fn(clips), dtype=float)
            if len(s) != len(ids):
                raise RuntimeError(f"{cond}: {len(s)} scores for {len(ids)} clips")
            pd.DataFrame({"utt_id": [str(u) for u in ids], "condition": cond, "score": s}).to_csv(part, index=False)
            print(f"[teacher] indic/{cond}: {len(ids)} clips in {time.time() - t0:.0f}s", flush=True)
        frames.append(pd.read_csv(part))
    df = pd.concat(frames, ignore_index=True)
    (out / "indic").mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "indic" / "teacher.csv", index=False)
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--ckpt", type=Path, default=CKPT)
    ap.add_argument("--pilot", type=Path, default=PILOT)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--limit", type=int, default=None, help="clips per condition (dry run)")
    a = ap.parse_args()
    torch.set_num_threads(int(os.environ.get("CM_THREADS", "4")))
    from cm.teacher.train import score_clips

    model = load_teacher(a.ckpt, a.device)
    df = score_pilot(lambda clips: score_clips(model, clips, a.device), a.pilot, a.out, a.limit)
    print(f"teacher indic scores: {len(df)} rows, conditions {sorted(df.condition.unique())}")


if __name__ == "__main__":
    main()
