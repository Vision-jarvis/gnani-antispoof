"""Runtime countermeasure: 8 kHz waveform in, calibrated LLR and streaming partial scores out.

Wraps the trained LFCC-LCNN (artifacts/models/lcnn8_aug.pt) and its dev-fitted affine calibration
(artifacts/models/lcnn8_aug_calibration.json, written by ``python -m cm.calibrate``). Inputs are
waveform only (honesty rule 3: no file names, durations, codec or language labels).

Causality (honesty rule 5): the partial score at t is ``llr(causal_cm_input(x[: t * SR]))``: trim
threshold and loudness gain come from the received prefix only, and the WebSocket endpoint calls the same
``prefix_llr``. Residual look-ahead: LFCC deltas look 2 frames (20 ms) ahead, but only inside the prefix, so a
decision at t uses no sample after t. ``t`` counts received audio (callers' leading silence included).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch

from cm.features import LFCCConfig, lfcc
from cm.lcnn import LCNN
from factory.normalise import causal_cm_input

ROOT = Path(__file__).resolve().parents[1]
SR = 8000
HORIZONS_S = (1.0, 2.0, 4.0)
MIN_SPEECH_S = 1.0


@dataclass(frozen=True)
class Calibration:
    a: float = 1.0
    b: float = 0.0
    tau_llr: float = 0.0  # accept as bona fide when llr >= tau_llr (dev-fixed, FAR = 1%)
    source: str = "uncalibrated"
    operating_points: dict[str, float] = field(default_factory=dict)  # name -> dev-fixed LLR threshold (cm.calibrate)

    def threshold(self, operating_point: str = "far1") -> float:
        if operating_point == "far1" and "far1" not in self.operating_points:
            return self.tau_llr
        return self.operating_points[operating_point]


@dataclass
class CMResult:
    llr: float
    p_spoof: float
    decision: str
    family: str
    partial: list[dict[str, float]] = field(default_factory=list)
    rtf: float = 0.0
    speech_s: float = 0.0

    def as_json(self) -> dict[str, object]:
        return {"llr": round(self.llr, 3), "p_spoof": round(self.p_spoof, 4), "decision": self.decision, "family": self.family,
                "partial": self.partial, "rtf": round(self.rtf, 4), "speech_s": round(self.speech_s, 2)}


class CMScorer:
    def __init__(self, model: LCNN, calibration: Calibration, prior_spoof: float = 0.05, operating_point: str = "far1") -> None:
        self.model = model.eval()
        self.cal = calibration
        self.operating_point = operating_point
        self.tau = calibration.threshold(operating_point)
        self.prior_logit = float(np.log((1 - prior_spoof) / prior_spoof))
        self.cfg = LFCCConfig(sr=SR)

    @classmethod
    def load(cls, name: str = "lcnn8_aug", models_dir: Path = ROOT / "artifacts" / "models", operating_point: str = "far1") -> CMScorer:
        model = LCNN()
        model.load_state_dict(torch.load(models_dir / f"{name}.pt", map_location="cpu"))
        cal_path = models_dir / f"{name}_calibration.json"
        cal = Calibration(**json.loads(cal_path.read_text())) if cal_path.exists() else Calibration()
        return cls(model, cal, operating_point=operating_point)

    @torch.no_grad()
    def raw_score(self, x: np.ndarray) -> float:
        f = lfcc(x, self.cfg)
        return float(self.model(torch.from_numpy(f[None])))

    def llr(self, x: np.ndarray) -> float:
        return self.cal.a * self.raw_score(x) + self.cal.b

    def prefix_llr(self, x8k: np.ndarray, t: float | None = None) -> float:
        """Calibrated LLR from the first ``t`` seconds of received audio (all of it if ``t`` is None)."""
        x = np.asarray(x8k, dtype=np.float32)
        return self.llr(causal_cm_input(x if t is None else x[: int(t * SR)], SR))

    def score(self, x8k: np.ndarray, horizons: tuple[float, ...] = HORIZONS_S) -> CMResult:
        t0 = time.perf_counter()
        x = np.asarray(x8k, dtype=np.float32)
        partial = [{"t": h, "llr": round(self.prefix_llr(x, h), 3)} for h in horizons if len(x) >= h * SR]
        speech = causal_cm_input(x, SR)
        llr = self.llr(speech)
        # Posterior with the bank prior pi_spf: logit P(bona) = llr + log((1 - pi)/pi).
        p_spoof = float(1 / (1 + np.exp(llr + self.prior_logit)))
        dur = len(x8k) / SR
        return CMResult(
            llr=llr,
            p_spoof=p_spoof,
            decision="bonafide" if llr >= self.tau else "spoof",
            family="unclassified",  # family head (tts_vc / replay / injection) is PENDING: needs G5/G6 training data
            partial=partial,
            rtf=(time.perf_counter() - t0) / max(dur, 1e-6),
            speech_s=len(speech) / SR,
        )
