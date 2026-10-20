"""Shortcut audit (honesty rule 4): can a trivial non-speech cue separate bona fide from spoof?

Each audit classifier is a single scalar. Its direction (does a larger value mean bona fide?) is fixed on
dev and never flipped on eval, so an uninformative cue scores about 50% EER. Rule 4: if any audit EER on
eval is below 35%, fix the data.

Non-circularity (critique B3). The CM input is trimmed with an energy gate (``CM_INPUT_POLICY``, 30 dB below
the loudest frame). Measuring silence with a gate that is *looser* than the trim gate only measures the trim
margin, so the audit could not fail. Every silence cue here is therefore measured either with a gate strictly
*tighter* than the trim gate (``silence_tight10_s``, ``silence_tight5_s``), or with an independent detector that
shares nothing with the trim (WebRTC VAD, ``vad_silence_s`` and ``vad_nonspeech_frac``), plus the fraction of
low-energy frames inside the clip (``lowenergy_frac``), loudness and duration. ``silence_s`` at the trim gate
itself is kept for comparison with earlier runs.

Ties: silence values are quantised to 20 ms frames, so most clips tie. EER is computed with BOSARIS tie
handling (ties resolved pessimistically, then the ROC convex hull), which equals random tie-breaking. An
earlier version broke ties optimistically and under-stated audit EERs (``docs/results_v2_audit_ties.md``).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
import pyloudnorm
import webrtcvad

from eval.metrics import eer
from factory.channel_sim import resample
from factory.normalise import CM_INPUT_POLICY, cm_input, frame_energy_db, silence_stats
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


VAD_FRAME_MS = 20
VAD_MODE = 2  # 0 (least) to 3 (most aggressive); 2 is the usual telephony setting
AUDIT_COLS = {
    "silence (trim gate, 30 dB)": "silence_s",
    "silence (gate 20 dB)": "silence_tight10_s",
    "silence (gate 25 dB)": "silence_tight5_s",
    "silence (WebRTC VAD)": "vad_silence_s",
    "non-speech fraction (WebRTC VAD)": "vad_nonspeech_frac",
    "low-energy frame fraction (< max-30 dB)": "lowenergy_frac",
    "loudness": "lufs",
    "duration": "dur_s",
}


def vad_flags(x: np.ndarray, sr: int, mode: int = VAD_MODE) -> np.ndarray:
    """WebRTC VAD speech flag per 20 ms frame (audio re-rated to 8 kHz, 16-bit PCM)."""
    if sr != 8000:
        x, sr = resample(x, sr, 8000), 8000
    n = sr * VAD_FRAME_MS // 1000
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    vad = webrtcvad.Vad(mode)
    return np.array([vad.is_speech(pcm[i : i + n].tobytes(), sr) for i in range(0, len(pcm) - n + 1, n)], dtype=bool)


def clip_cues(x: np.ndarray, sr: int) -> dict[str, float]:
    """All audit cues of one clip, as the CM receives it (call after ``cm_input``)."""
    out: dict[str, float] = {}
    lead, trail = silence_stats(x, sr, CM_INPUT_POLICY)
    out["silence_s"] = lead + trail
    for d in (10, 5):
        lead, trail = silence_stats(x, sr, replace(CM_INPUT_POLICY, rel_db=CM_INPUT_POLICY.rel_db - d))
        out[f"silence_tight{d}_s"] = lead + trail
    e = frame_energy_db(x, sr)
    out["lowenergy_frac"] = float(np.mean(e < e.max() - 30.0))
    v = vad_flags(x, sr)
    if v.any():
        idx = np.flatnonzero(v)
        out["vad_silence_s"] = (idx[0] + len(v) - 1 - idx[-1]) * VAD_FRAME_MS / 1000
    else:
        out["vad_silence_s"] = len(v) * VAD_FRAME_MS / 1000
    out["vad_nonspeech_frac"] = float(1 - v.mean()) if len(v) else 1.0
    out["dur_s"] = len(x) / sr
    return out


def cue_table(packed: PackedAudio) -> pd.DataFrame:
    """Audit cues of each clip as the CM receives it (after ``cm_input``)."""
    meter = pyloudnorm.Meter(packed.sr)
    rows = []
    for u, x in packed:
        x = cm_input(x, packed.sr)
        lufs = meter.integrated_loudness(x.astype(np.float64)) if len(x) >= 0.4 * packed.sr else np.nan
        rows.append({"utt_id": u, **clip_cues(x, packed.sr), "lufs": lufs})
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
