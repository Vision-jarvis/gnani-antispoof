"""Shortcut audit (honesty rule 4): can a trivial non-speech cue separate bona fide from spoof?

Each audit classifier is a single scalar (total leading + trailing silence, integrated loudness, or
duration). Its direction (does a larger value mean bona fide?) is fixed on dev and never flipped on
eval, so a cue that is uninformative scores about 50% EER and cannot be made to look good by
choosing the sign after the fact. Rule 4: if any audit EER on eval is below 35%, fix the data.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pyloudnorm

from eval.metrics import eer
from factory.normalise import cm_input, silence_stats
from factory.store import PackedAudio

AUDIT_THRESHOLD = 0.35


@dataclass(frozen=True)
class AuditResult:
    cue: str
    stage: str
    dev_direction: int
    eval_eer: float

    @property
    def passes(self) -> bool:
        return self.eval_eer >= AUDIT_THRESHOLD


def cue_table(packed: PackedAudio) -> pd.DataFrame:
    """Silence, loudness and duration of each clip as the CM receives it (after ``cm_input``)."""
    meter = pyloudnorm.Meter(packed.sr)
    rows = []
    for u, x in packed:
        x = cm_input(x, packed.sr)
        lead, trail = silence_stats(x, packed.sr)
        lufs = meter.integrated_loudness(x.astype(np.float64)) if len(x) >= 0.4 * packed.sr else np.nan
        rows.append({"utt_id": u, "silence_s": lead + trail, "lufs": lufs, "dur_s": len(x) / packed.sr})
    return pd.DataFrame(rows)


def audit_cue(dev: pd.DataFrame, evl: pd.DataFrame, col: str, stage: str) -> AuditResult:
    """``dev``/``evl`` need columns ``label`` (bonafide/spoof) and ``col``."""
    def split(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        v = df[col].to_numpy(float)
        v = np.where(np.isfinite(v), v, np.nanmedian(v))
        b = (df.label == "bonafide").to_numpy()
        return v[b], v[~b]

    db, ds = split(dev)
    direction = 1 if eer(db, ds) <= eer(-db, -ds) else -1
    eb, es = split(evl)
    return AuditResult(col, stage, direction, eer(direction * eb, direction * es))


def run_audit(dev: pd.DataFrame, evl: pd.DataFrame, cols: dict[str, str], stage: str) -> list[AuditResult]:
    """``cols`` maps the cue name to the column holding it."""
    out = []
    for name, col in cols.items():
        r = audit_cue(dev, evl, col, stage)
        out.append(AuditResult(name, stage, r.dev_direction, r.eval_eer))
    return out
