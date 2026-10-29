"""Score folders of 8 kHz WAVs with the fine-tuned teacher: the own-voice red team (docs/DEMO_RUNBOOK.md).

Input: ``<root>/<condition>/{bona,spoof}/*.wav`` as written by ``scripts/prep_own_voice.py trialsets``. Each clip
gets exactly the teacher's eval input (``cm_input`` at 8 kHz, then 16 kHz, as ``cm.teacher.train.score_eval``).
Output CSV, one row per clip: file, condition, label, score (logit difference, higher = bona fide), and the
decision at the teacher's dev-fixed thresholds, computed as ``eval.report`` does (FAR 1%, minDCF and EER points
on the teacher's ASVspoof dev scores, ``release/scores/teacher_dev.csv.gz`` with the dev manifest). Nothing is
tuned on these clips.

GPU (Modal A10, about 5 min and $0.10 to $0.20 for 30 to 60 clips; 20 min timeout caps it at about $0.50):
  modal volume put gnani-cm-data data/own_voice/trials /ownvoice/trials --force
  modal run --detach cm/teacher/modal_train.py::ownvoice_main      # spawns and returns
  modal run cm/teacher/modal_train.py::ownvoice_fetch              # -> artifacts/ownvoice_teacher_scores.csv
  modal volume rm -r gnani-cm-data /ownvoice                       # then delete the voice from the volume
CPU (no upload; needs artifacts/models/teacher_ssl_aasist_8k.pt, 1.26 GB):
  python -m cm.teacher.score_folder --root data/own_voice/trials --device cpu
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf
import torch

from factory.channel_sim import resample
from factory.normalise import cm_input

ROOT = Path(__file__).resolve().parents[2]
CKPT = ROOT / "artifacts" / "models" / "teacher_ssl_aasist_8k.pt"
TRIALS = ROOT / "data" / "own_voice" / "trials"
OUT = ROOT / "artifacts" / "ownvoice_teacher_scores.csv"  # scores only, no audio: committed as evidence
DEV_SCORES = (ROOT / "artifacts" / "scores" / "teacher_dev.csv", ROOT / "release" / "scores" / "teacher_dev.csv.gz")
DEV_MANIFESTS = (ROOT / "data" / "proc" / "asv19" / "dev" / "manifest.csv", ROOT / "release" / "manifests" / "dev_manifest.csv")


def _first(paths: tuple[Path, ...]) -> Path:
    for p in paths:
        if p.is_file():
            return p
    raise FileNotFoundError(f"none of {[p.as_posix() for p in paths]} exists (python -m cm.release restore)")


def teacher_thresholds() -> dict[str, float]:
    """The teacher's dev-fixed thresholds on its raw score (accept as bona fide when score >= tau)."""
    from eval.metrics import threshold_at_eer, threshold_at_far, threshold_min_dcf

    dev = pd.read_csv(_first(DEV_SCORES)).merge(pd.read_csv(_first(DEV_MANIFESTS))[["utt_id", "label"]], on="utt_id")
    b = dev.label.eq("bonafide").to_numpy()
    s = dev.score.to_numpy(float)
    return {"far1": float(threshold_at_far(s[b], s[~b], 0.01)), "min_dcf": float(threshold_min_dcf(s[b], s[~b])),
            "eer": float(threshold_at_eer(s[b], s[~b]))}


def folder_clips(root: Path) -> list[tuple[str, str, str, np.ndarray]]:
    """(relative file, condition, label, 16 kHz teacher input) for every WAV under root/<condition>/{bona,spoof}."""
    out = []
    for cond_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for sub, label in (("bona", "bonafide"), ("spoof", "spoof")):
            for wav in sorted((cond_dir / sub).glob("*.wav")):
                x, sr = sf.read(wav, dtype="float32", always_2d=True)
                if sr != 8000:
                    raise SystemExit(f"{wav} is {sr} Hz; the trial folders must be 8 kHz (scripts/prep_own_voice.py trialsets)")
                out.append((wav.relative_to(root).as_posix(), cond_dir.name, label, resample(cm_input(x.mean(axis=1), 8000), 8000, 16000)))
    if not out:
        raise SystemExit(f"no WAVs under {root}/<condition>/(bona|spoof)/")
    return out


def score_folder(root: Path, score_fn, out: Path) -> pd.DataFrame:  # noqa: ANN001 - list of 16 kHz clips -> scores
    clips = folder_clips(root)
    t0 = time.time()
    s = np.asarray(score_fn([c[3] for c in clips]), dtype=float)
    taus = teacher_thresholds()
    df = pd.DataFrame({"file": [c[0] for c in clips], "condition": [c[1] for c in clips], "label": [c[2] for c in clips], "score": s})
    for op, tau in taus.items():
        df[f"tau_{op}"] = tau
        df[f"accept_{op}"] = df.score >= tau
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"[teacher] {len(df)} clips scored in {time.time() - t0:.0f} s -> {out}; dev thresholds {taus}", flush=True)
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=TRIALS)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--ckpt", type=Path, default=CKPT)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    torch.set_num_threads(int(os.environ.get("CM_THREADS", "4")))
    from cm.teacher.score_indic import load_teacher
    from cm.teacher.train import score_clips

    model = load_teacher(a.ckpt, a.device)
    score_folder(a.root, lambda clips: score_clips(model, clips, a.device), a.out)


if __name__ == "__main__":
    main()
