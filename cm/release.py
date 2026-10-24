"""``release/``: the committed, clone-reproducible slice of the run (critique M4).

  python -m cm.release build     # artifacts/ + data/ -> release/ (models, calibration, gzipped scores,
                                 #   manifests, shortcut-audit table, a 120-clip G.711 eval pack)
  python -m cm.release restore   # release/ -> artifacts/models and artifacts/scores (skips files that exist)
A fresh clone then reproduces artifacts/results.md (``run.ps1 report``), the IVR demo with the trained CM and
``python -m ivr_demo.trials --pack``. ASVspoof 2019 LA is ODC-By: the pack and manifests are redistributed
with attribution (DATA.md); no Indic or Gnani audio is ever put in release/.
"""

from __future__ import annotations

import gzip
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / "release"
ART = ROOT / "artifacts"
PROC = ROOT / "data" / "proc" / "asv19"
MODEL_FILES = ("cm_student.onnx", "lcnn8_aug.pt", "lcnn8_aug_calibration.json", "lcnn8_aug_history.json", "gmm8_aug.npz",
               "lcnn8_distil.pt", "lcnn8_distil_calibration.json", "lcnn8_distil_history.json")
PACK_CONDITION, PACK_PER_CLASS = "g711u", 60


def manifest_path(split: str) -> Path:
    """data/proc manifest if the data is built, else the released copy."""
    p = PROC / split / "manifest.csv"
    return p if p.exists() else REL / "manifests" / f"{split}_manifest.csv"


def build() -> None:
    from factory.store import load_packed, save_packed

    (REL / "models").mkdir(parents=True, exist_ok=True)
    (REL / "scores").mkdir(parents=True, exist_ok=True)
    (REL / "manifests").mkdir(parents=True, exist_ok=True)
    for f in MODEL_FILES:
        shutil.copy2(ART / "models" / f, REL / "models" / f)
    for p in sorted((ART / "scores").glob("*.csv")):
        with open(p, "rb") as src, gzip.open(REL / "scores" / f"{p.name}.gz", "wb", compresslevel=9) as dst:
            shutil.copyfileobj(src, dst)
    for p in sorted((ART / "scores").glob("*.json")):
        shutil.copy2(p, REL / "scores" / p.name)
    for split in ("dev", "eval"):
        shutil.copy2(PROC / split / "manifest.csv", REL / "manifests" / f"{split}_manifest.csv")
    res = json.loads((ART / "results.json").read_text())
    (REL / "shortcut_audit.json").write_text(json.dumps(res["shortcut_audit"], indent=2))
    man = pd.read_csv(PROC / "eval" / "manifest.csv")
    packed = load_packed(PROC / "eval" / f"{PACK_CONDITION}.npz")
    pos = packed.index()
    rng = np.random.default_rng(11)
    ids = [u for lab in ("bonafide", "spoof") for u in rng.choice(man[man.label == lab].utt_id.astype(str), PACK_PER_CLASS, replace=False)]
    save_packed(REL / "demo_pack" / f"{PACK_CONDITION}.npz", ids, [packed.get(pos[u]) for u in ids], packed.sr)
    man[man.utt_id.isin(ids)].to_csv(REL / "demo_pack" / "manifest.csv", index=False)
    print(f"release built: {sum(f.stat().st_size for f in REL.rglob('*') if f.is_file()) / 1e6:.1f} MB")


def restore() -> None:
    (ART / "models").mkdir(parents=True, exist_ok=True)
    (ART / "scores").mkdir(parents=True, exist_ok=True)
    for f in (REL / "models").glob("*"):
        if not (ART / "models" / f.name).exists():
            shutil.copy2(f, ART / "models" / f.name)
    for f in (REL / "scores").glob("*.csv.gz"):
        out = ART / "scores" / f.name[:-3]
        if not out.exists():
            with gzip.open(f, "rb") as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst)
    for f in (REL / "scores").glob("*.json"):
        if not (ART / "scores" / f.name).exists():
            shutil.copy2(f, ART / "scores" / f.name)
    print("release restored into artifacts/")


if __name__ == "__main__":
    {"build": build, "restore": restore}[sys.argv[1] if len(sys.argv) > 1 else "restore"]()
