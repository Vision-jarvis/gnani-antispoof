"""Build every results table from artifacts/scores/*.csv; writes artifacts/results.json and results.md.

For each model: dev-fixed threshold at FAR = 1% and an affine LLR calibration, both fitted on the
model's dev scores only and then applied unchanged to every eval cell. Reported per cell: EER, minDCF
(pi_spf=0.05, C_miss=1, C_fa=10), Cllr of the calibrated LLRs, FRR@FAR1.

Pools: ``clean`` (clean16k for 16 kHz models; nb_pcm, the same utterances resampled to 8 kHz with no
codec, for 8 kHz models), ``seen`` (train-allowed codecs), ``heldout`` (AMR-NB 4.75, GSM-FR, two-hop
chains; never in training). delta-NB = EER(heldout) - EER(clean) on the same utterances.
Usage: python -m eval.report
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from eval.metrics import DCF_PARAMS, AffineCalibration, evaluate, threshold_at_far
from eval.points import points_matrix
from eval.shortcut_audit import AUDIT_COLS, cue_table, run_audit
from factory.channel_sim import HELDOUT_CONDITIONS, TRAIN_CONDITIONS
from factory.store import load_packed

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "proc" / "asv19"
SCORES = ROOT / "artifacts" / "scores"
OUT_JSON = ROOT / "artifacts" / "results.json"
OUT_MD = ROOT / "artifacts" / "results.md"
SEEN = [c for c in TRAIN_CONDITIONS if c != "nb_pcm"]
HELDOUT = sorted(HELDOUT_CONDITIONS)
EIGHT_K_MODELS = {"gmm8_aug", "lcnn8_aug", "lcnn8_noaug", "lcnn8_distil", "teacher"}


def _cell(df: pd.DataFrame, cal: AffineCalibration, tau: float) -> dict[str, float | int | None]:
    b = df.label.eq("bonafide").to_numpy()
    s = df.score.to_numpy(float)
    r = evaluate(s[b], s[~b], dev_tau_far1=tau).as_dict()
    llr = cal(s)
    r["cllr"] = evaluate(llr[b], llr[~b], llr=True).cllr
    return r


def model_tables(name: str, man: pd.DataFrame) -> dict[str, object]:
    sc = pd.read_csv(SCORES / f"{name}.csv").merge(man[["utt_id", "label", "attack"]], on="utt_id")
    dev = pd.read_csv(SCORES / f"{name}_dev.csv").merge(pd.read_csv(PROC / "dev" / "manifest.csv")[["utt_id", "label"]], on="utt_id")
    db = dev.label.eq("bonafide").to_numpy()
    ds = dev.score.to_numpy(float)
    cal = AffineCalibration.fit(ds[db], ds[~db])
    tau = threshold_at_far(ds[db], ds[~db], 0.01)
    full = sc[sc.horizon == 0]
    clean = "nb_pcm" if name in EIGHT_K_MODELS else "clean16k"
    out: dict[str, object] = {"dev": evaluate(ds[db], ds[~db]).as_dict(), "clean_pool": clean}
    out["per_condition"] = {c: _cell(g, cal, tau) for c, g in full.groupby("condition")}
    pools = {"clean": [clean], "seen": SEEN, "heldout": HELDOUT}
    out["pools"] = {k: _cell(full[full.condition.isin(v)], cal, tau) for k, v in pools.items()}
    out["delta_nb"] = out["pools"]["heldout"]["eer"] - out["pools"]["clean"]["eer"]  # type: ignore[index]
    bona_ho = full[full.condition.isin(HELDOUT) & full.label.eq("bonafide")]
    bona_cl = full[full.condition.eq(clean) & full.label.eq("bonafide")]
    per_attack = {}
    for a, g in full[full.label.eq("spoof")].groupby("attack"):
        per_attack[a] = {
            "clean": _cell(pd.concat([bona_cl, g[g.condition.eq(clean)]]), cal, tau)["eer"],
            "heldout": _cell(pd.concat([bona_ho, g[g.condition.isin(HELDOUT)]]), cal, tau)["eer"],
        }
    out["per_attack_eer"] = per_attack
    streaming = {}
    for h, g in sc[sc.horizon > 0].groupby("horizon"):
        streaming[f"{h:g}s"] = {k: _cell(g[g.condition.isin(v)], cal, tau)["eer"] for k, v in pools.items()}
    if streaming:
        streaming["full"] = {k: out["pools"][k]["eer"] for k in pools}  # type: ignore[index]
        out["streaming_eer"] = streaming
    meta_path = SCORES / f"{name}.json"
    out["meta"] = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    if isinstance(out["meta"], dict):
        out["meta"].pop("history", None)
    return out


def shortcut_audit(man_eval: pd.DataFrame) -> list[dict[str, object]]:
    man_dev = pd.read_csv(PROC / "dev" / "manifest.csv")
    for m in (man_eval, man_dev):
        m["raw_silence_s"] = m.raw_lead_sil_s + m.raw_trail_sil_s
    res = run_audit(man_dev, man_eval, {"silence": "raw_silence_s", "loudness": "raw_lufs", "duration": "raw_dur_s"}, "raw (before normalisation)")
    for cond in ("nb_pcm", "g711u"):
        cues = {s: cue_table(load_packed(PROC / s / f"{cond}.npz")).merge(m[["utt_id", "label"]], on="utt_id")
                for s, m in (("dev", man_dev), ("eval", man_eval))}
        res += run_audit(cues["dev"], cues["eval"], AUDIT_COLS, f"CM input ({cond})")
    return [{"cue": r.cue, "stage": r.stage, "eval_eer": r.eval_eer, "passes_35pct_rule": r.passes} for r in res]


def _pct(v: object) -> str:
    return "n/a" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{100 * float(v):.2f}"


def to_markdown(res: dict[str, object]) -> str:
    models: dict[str, dict] = res["models"]  # type: ignore[assignment]
    lines = [f"Metrics: EER %, minDCF ({DCF_PARAMS}), Cllr (bits, dev-calibrated), FRR@FAR1 % (dev-fixed threshold).", ""]
    lines += ["### Pooled results", "", "| model | pool | EER % | minDCF | Cllr | FRR@FAR1 % | FAR at dev tau % |", "|---|---|---|---|---|---|---|"]
    for n, m in models.items():
        for p in ("clean", "seen", "heldout"):
            c = m["pools"][p]
            label = f"{p} ({m['clean_pool']})" if p == "clean" else p
            lines.append(f"| {n} | {label} | {_pct(c['eer'])} | {c['min_dcf']:.3f} | {c['cllr']:.3f} | {_pct(c['frr_at_far1'])} | {_pct(c['far_at_dev_tau'])} |")
    lines += ["", "### delta-NB (EER held-out codecs minus EER clean pool, same utterances)", "", "| model | delta-NB (EER points) |", "|---|---|"]
    lines += [f"| {n} | {100 * m['delta_nb']:+.2f} |" for n, m in models.items()]
    conds = sorted({c for m in models.values() for c in m["per_condition"]})
    lines += ["", "### EER % per channel condition", "", "| condition | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
    for c in conds:
        tag = " (held-out)" if c in HELDOUT_CONDITIONS else ""
        lines.append(f"| {c}{tag} | " + " | ".join(_pct(m["per_condition"].get(c, {}).get("eer")) for m in models.values()) + " |")
    attacks = sorted({a for m in models.values() for a in m["per_attack_eer"]})
    lines += ["", "### EER % per ASVspoof 2019 eval attack (clean pool / held-out codec pool)", "", "| attack | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
    for a in attacks:
        lines.append(f"| {a} | " + " | ".join(f"{_pct(m['per_attack_eer'][a]['clean'])} / {_pct(m['per_attack_eer'][a]['heldout'])}" for m in models.values()) + " |")
    lines += ["", "### Streaming EER % (decision on the first t seconds of trimmed speech only)", "", "| model | horizon | clean | seen | held-out |", "|---|---|---|---|---|"]
    for n, m in models.items():
        for h, v in m.get("streaming_eer", {}).items():
            lines.append(f"| {n} | {h} | {_pct(v['clean'])} | {_pct(v['seen'])} | {_pct(v['heldout'])} |")
    lines += ["", "### Shortcut audit (single-cue classifiers, direction fixed on dev; rule: must be >= 35% EER)", "", "| stage | cue | eval EER % | passes |", "|---|---|---|---|"]
    lines += [f"| {a['stage']} | {a['cue']} | {_pct(a['eval_eer'])} | {'yes' if a['passes_35pct_rule'] else 'NO'} |" for a in res["shortcut_audit"]]  # type: ignore[union-attr]
    lines += ["", "### Points matrix (statement section 7)", "", "| KPI | weight | status | value | note |", "|---|---|---|---|---|"]
    lines += [f"| {k['kpi']} | {k['weight']} | {k['status']} | {k['value']} | {k['note']} |" for k in res["points"]]  # type: ignore[union-attr]
    return "\n".join(lines) + "\n"


def main() -> None:
    man = pd.read_csv(PROC / "eval" / "manifest.csv")
    names = sorted(p.stem for p in SCORES.glob("*.csv") if not p.stem.endswith("_dev"))
    order = ["aasist", "aasist_l", "ssl_aasist", "teacher", "gmm16_clean", "gmm8_aug", "lcnn8_noaug", "lcnn8_aug"]
    names = [n for n in order if n in names] + [n for n in names if n not in order]
    res: dict[str, object] = {"dcf_params": DCF_PARAMS, "n_eval_bona": int((man.label == "bonafide").sum()),
                              "n_eval_spoof": int((man.label == "spoof").sum()),
                              "models": {n: model_tables(n, man) for n in names}}
    res["shortcut_audit"] = shortcut_audit(man)
    res["points"] = points_matrix(res)
    OUT_JSON.write_text(json.dumps(res, indent=2, default=float))
    OUT_MD.write_text(to_markdown(res), encoding="utf-8")
    print(OUT_MD.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
