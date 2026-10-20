"""Score every trained baseline on the Indic pilot set (factory.indic_pilot) and tabulate.

Thresholds come from each model's ASVspoof dev scores (dev-fixed, never tuned on this set), so
FRR@FAR1 here also measures calibration drift from English to Indic speech.
Shortcut audit: with no Indic dev split, each cue is given its BEST direction on this set, which
flatters the cue and so makes the audit conservative.
Usage: python -m eval.indic_report
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import torch

from cm.featurize import load_features
from cm.gmm import LFCCGMM
from cm.lcnn import LCNN
from cm.train_lcnn import score_lcnn
from eval.metrics import eer, far_frr, threshold_at_far
from eval.shortcut_audit import AUDIT_COLS, cue_table
from factory.indic_pilot import CONDITIONS
from factory.store import load_packed

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "data" / "proc" / "indic_pilot" / "eval"
MODELS = ROOT / "artifacts" / "models"
SCORES = ROOT / "artifacts" / "scores"
OUT = ROOT / "artifacts" / "indic_pilot.md"
CONDS = ("clean16k", *CONDITIONS)
PRETRAINED = ("aasist", "aasist_l", "ssl_aasist")


def score_model(name: str) -> pd.DataFrame | None:
    pre = SCORES / "indic" / f"{name}.csv"
    if name in PRETRAINED:
        # Published models are scored on the GPU by cm.score_pretrained (modal run cm/modal_pretrained.py).
        return pd.read_csv(pre)[["utt_id", "condition", "score"]] if pre.exists() else None
    recs = []
    if name.startswith("gmm") and (MODELS / f"{name}.npz").exists():
        gmm = LFCCGMM.load(MODELS / f"{name}.npz")
        for c in CONDS:
            if name == "gmm8_aug" and c == "clean16k":
                continue
            rs = 16000 if (name == "gmm16_clean" and c != "clean16k") else None
            fs = load_features(PILOT, c, resample_to=rs)
            recs += [(str(u), c, gmm.score(f)) for u, f in zip(fs.utt_ids, fs.all(), strict=True)]
    elif name.startswith("lcnn") and (MODELS / f"{name}.pt").exists():
        model = LCNN()
        model.load_state_dict(torch.load(MODELS / f"{name}.pt"))
        for c in CONDITIONS:
            fs = load_features(PILOT, c)
            recs += [(str(u), c, float(s)) for u, s in zip(fs.utt_ids, score_lcnn(model, fs.all()), strict=True)]
    else:
        return None
    return pd.DataFrame(recs, columns=["utt_id", "condition", "score"])


def dev_threshold(name: str) -> float:
    dev = pd.read_csv(SCORES / f"{name}_dev.csv").merge(pd.read_csv(ROOT / "data/proc/asv19/dev/manifest.csv")[["utt_id", "label"]], on="utt_id")
    b = dev.label.eq("bonafide").to_numpy()
    return threshold_at_far(dev.score.to_numpy()[b], dev.score.to_numpy()[~b], 0.01)


def main() -> None:
    man = pd.read_csv(PILOT / "manifest.csv")
    torch.set_num_threads(12)
    rows, lang_rows = [], []
    for name in (*PRETRAINED, "gmm16_clean", "gmm8_aug", "lcnn8_noaug", "lcnn8_aug"):
        df = score_model(name)
        if df is None:
            continue
        SCORES.joinpath("indic").mkdir(parents=True, exist_ok=True)
        df.to_csv(SCORES / "indic" / f"{name}.csv", index=False)
        df = df.merge(man[["utt_id", "label", "language"]], on="utt_id")
        tau = dev_threshold(name)
        for c, g in df.groupby("condition"):
            b = g.label.eq("bonafide").to_numpy()
            s = g.score.to_numpy()
            far, frr = far_frr(s[b], s[~b], tau)
            rows.append({"model": name, "condition": c, "eer": eer(s[b], s[~b]), "frr_at_dev_far1": frr, "far_at_dev_tau": far})
            for lang, gl in g.groupby("language"):
                bl = gl.label.eq("bonafide").to_numpy()
                lang_rows.append({"model": name, "condition": c, "language": lang, "eer": eer(gl.score.to_numpy()[bl], gl.score.to_numpy()[~bl])})
        print(f"[indic] scored {name}", flush=True)
    res = pd.DataFrame(rows)
    audit = []
    man["raw_silence_s"] = man.raw_lead_sil_s + man.raw_trail_sil_s
    b = man.label.eq("bonafide").to_numpy()
    for cue, col in (("silence", "raw_silence_s"), ("loudness", "raw_lufs"), ("duration", "raw_dur_s")):
        v = man[col].fillna(man[col].median()).to_numpy()
        audit.append({"cue": cue, "best_direction_eer": min(eer(v[b], v[~b]), eer(-v[b], -v[~b]))})
    for c in ("nb_pcm",):
        cues = cue_table(load_packed(PILOT / f"{c}.npz")).merge(man[["utt_id", "label"]], on="utt_id")
        bb = cues.label.eq("bonafide").to_numpy()
        for cue, col in AUDIT_COLS.items():
            cue = f"{cue} (CM input)"
            v = cues[col].fillna(cues[col].median()).to_numpy()
            audit.append({"cue": cue, "best_direction_eer": min(eer(v[bb], v[~bb]), eer(-v[bb], -v[~bb]))})
    pivot = res.pivot(index="condition", columns="model", values="eer").reindex(list(CONDS))
    frr = res.pivot(index="condition", columns="model", values="frr_at_dev_far1").reindex(list(CONDS))
    lang = pd.DataFrame(lang_rows).pivot_table(index=["language", "condition"], columns="model", values="eer")
    fmt = lambda df: (100 * df).round(2).to_markdown()  # noqa: E731
    md = [f"# Indic pilot: FLEURS bona fide vs IndicSynth FreeVC (G4), Hindi + Kannada, n = {b.sum()} bona fide / {(~b).sum()} spoof", "",
          "## EER % per channel condition", fmt(pivot), "", "## FRR % at the ASVspoof-dev threshold for FAR = 1%", fmt(frr), "",
          "## EER % per language", fmt(lang), "", "## Shortcut audit (single cue, best direction; rule: must stay >= 35%)",
          pd.DataFrame(audit).assign(best_direction_eer=lambda d: (100 * d.best_direction_eer).round(2)).to_markdown(index=False)]
    OUT.write_text("\n".join(md) + "\n", encoding="utf-8")
    (ROOT / "artifacts" / "indic_pilot.json").write_text(json.dumps({"per_condition": rows, "audit": audit}, indent=2, default=float))
    print(OUT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
