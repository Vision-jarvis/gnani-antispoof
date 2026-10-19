"""Fit the runtime calibration of an 8 kHz model on its DEV scores only and save it next to the checkpoint.

llr = a * raw + b (prior-weighted logistic regression, prior 0.5), and the operating threshold
tau_llr is the dev threshold giving FAR = 1% (the FRR@FAR1 operating point), mapped into LLR units.
Usage: python -m cm.calibrate --model lcnn8_aug
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from cm.scorer import Calibration
from eval.metrics import AffineCalibration, threshold_at_far

ROOT = Path(__file__).resolve().parents[1]


def fit(name: str) -> Calibration:
    dev = pd.read_csv(ROOT / "artifacts" / "scores" / f"{name}_dev.csv")
    man = pd.read_csv(ROOT / "data" / "proc" / "asv19" / "dev" / "manifest.csv")[["utt_id", "label"]]
    dev = dev.merge(man, on="utt_id")
    b = dev.label.eq("bonafide").to_numpy()
    s = dev.score.to_numpy(float)
    aff = AffineCalibration.fit(s[b], s[~b])
    tau = threshold_at_far(s[b], s[~b], 0.01)
    return Calibration(a=aff.a, b=aff.b, tau_llr=float(aff(tau)), source=f"dev scores of {name}, FAR=1% operating point")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="lcnn8_aug")
    a = ap.parse_args()
    cal = fit(a.model)
    out = ROOT / "artifacts" / "models" / f"{a.model}_calibration.json"
    out.write_text(json.dumps(asdict(cal), indent=2))
    print(out, asdict(cal))


if __name__ == "__main__":
    main()
