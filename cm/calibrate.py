"""Fit the runtime calibration of an 8 kHz model on its DEV scores only and save it next to the checkpoint.

llr = a * raw + b (prior-weighted logistic regression, prior 0.5). Named operating points, all fixed on dev
and mapped into LLR units (accept as bona fide when llr >= tau):
  far1     dev FAR = 1% (the FRR@FAR1 point; the default ``tau_llr``)
  min_dcf  the dev threshold attaining minDCF (pi_spf = 0.05, C_miss = 1, C_fa = 10)
  eer      the dev EER threshold
  bayes    log(C_fa pi / (C_miss (1 - pi))): the Bayes threshold if the calibration transfers
Usage: python -m cm.calibrate --model lcnn8_aug
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from cm.scorer import Calibration
import numpy as np

from eval.metrics import C_FA, C_MISS, PI_SPF, AffineCalibration, threshold_at_eer, threshold_at_far, threshold_min_dcf

ROOT = Path(__file__).resolve().parents[1]


def fit(name: str) -> Calibration:
    dev = pd.read_csv(ROOT / "artifacts" / "scores" / f"{name}_dev.csv")
    man = pd.read_csv(ROOT / "data" / "proc" / "asv19" / "dev" / "manifest.csv")[["utt_id", "label"]]
    dev = dev.merge(man, on="utt_id")
    b = dev.label.eq("bonafide").to_numpy()
    s = dev.score.to_numpy(float)
    aff = AffineCalibration.fit(s[b], s[~b])
    tau = threshold_at_far(s[b], s[~b], 0.01)
    ops = {"far1": float(aff(tau)), "min_dcf": float(aff(threshold_min_dcf(s[b], s[~b]))),
           "eer": float(aff(threshold_at_eer(s[b], s[~b]))), "bayes": float(np.log(C_FA * PI_SPF / (C_MISS * (1 - PI_SPF))))}
    return Calibration(a=aff.a, b=aff.b, tau_llr=ops["far1"], source=f"dev scores of {name}, FAR=1% operating point", operating_points=ops)


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
