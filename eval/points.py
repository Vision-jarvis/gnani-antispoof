"""The statement's 100-point KPI matrix (section 7), filled from measured results only.

The statement scores most KPIs "relative to best baseline" without a formula, so this module does
not invent points. It reports, per KPI, the weight, whether it is MEASURED / PARTIAL / PENDING, the
measured value, and what blocks the rest. The one hard gate the statement does define (student
efficiency: 0 points if any budget is exceeded) is checked against artifacts/efficiency.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUDGET = {"rtf": 0.05, "params": 5_000_000, "peak_ram_mb": 200.0}


def _best(models: dict[str, Any], key: Any) -> tuple[str, float] | None:
    vals = [(n, key(m)) for n, m in models.items()]
    vals = [(n, v) for n, v in vals if v is not None]
    return min(vals, key=lambda t: t[1]) if vals else None


def efficiency_gate() -> tuple[str, str]:
    path = ROOT / "artifacts" / "efficiency.json"
    if not path.exists():
        return "PENDING", "run python -m cm.export_onnx"
    e = json.loads(path.read_text())
    ok = e["rtf_1core"] <= BUDGET["rtf"] and e["params"] < BUDGET["params"] and e["peak_ram_mb"] <= BUDGET["peak_ram_mb"]
    value = f"{e['model']}: RTF {e['rtf_1core']:.4f}, {e['params']:,} params, {e['peak_ram_mb']:.0f} MB"
    return ("MEASURED (inside budget)" if ok else "MEASURED (OVER budget: 0 points)"), value


def ivr_trials() -> tuple[str, str]:
    path = ROOT / "artifacts" / "ivr_trials_asvspoof.json"
    if not path.exists():
        return "PENDING", "n/a"
    rows = json.loads(path.read_text())
    return "PARTIAL (CM gate only, English proxy)", "; ".join(
        f"{r['source'].split()[-1]} @ {r['operating_point']}: genuine {r['genuine_success_pct']}%, attack {r['attack_success_pct']}%" for r in rows)


def student_note(models: dict[str, Any]) -> str:
    if "lcnn8_distil" not in models or "lcnn8_aug" not in models:
        return "LFCC-LCNN (lcnn8_aug) stands in for the distilled student until python -m cm.distil has run"
    d, a = (models[n]["pools"]["heldout"]["eer"] for n in ("lcnn8_distil", "lcnn8_aug"))
    verdict = "improves on" if d < a else "does not improve on"
    return (f"measured on lcnn8_aug (shipped); the distilled lcnn8_distil has the same architecture and budget and "
            f"{verdict} it on held-out codecs ({100 * d:.2f}% vs {100 * a:.2f}% EER)")


def points_matrix(res: dict[str, Any]) -> list[dict[str, Any]]:
    models: dict[str, Any] = res["models"]
    ho = _best(models, lambda m: m["pools"]["heldout"]["eer"])
    frr = _best(models, lambda m: m["pools"]["heldout"]["frr_at_far1"])
    st = _best(models, lambda m: m.get("streaming_eer", {}).get("2s", {}).get("heldout"))
    audit_ok = all(a["passes_35pct_rule"] for a in res.get("shortcut_audit", []) if a["stage"].startswith("CM input"))
    eff_status, eff_value = efficiency_gate()
    pct = lambda v: f"{100 * v:.2f}%"  # noqa: E731
    return [
        {"kpi": "Unseen-Indic EER (G2+G3 after channel)", "weight": 25, "status": "PENDING",
         "value": "n/a", "note": "G1/G3 from Timbre stock voices + the builder's own consented voice; Kathbath-speaker cloning DEFERRED (consent)"},
        {"kpi": "Pooled narrowband EER and delta-NB, held-out codecs", "weight": 15, "status": "MEASURED (ASVspoof 2019 LA proxy)",
         "value": f"{ho[0]}: {pct(ho[1])}, delta-NB {100 * models[ho[0]]['delta_nb']:+.2f} pts" if ho else "n/a", "note": "English VCTK-based proxy, not Indic"},
        {"kpi": "FRR@FAR1, dev-fixed threshold", "weight": 10, "status": "MEASURED (proxy)",
         "value": f"{frr[0]}: {pct(frr[1])} on held-out codecs" if frr else "n/a", "note": "threshold fixed on dev, never retuned"},
        {"kpi": "Streaming EER at 2.0 s", "weight": 10, "status": "MEASURED (proxy)" if st else "PENDING",
         "value": f"{st[0]}: {pct(st[1])} held-out pool" if st else "n/a",
         "note": "causal prefix scoring, clips with >= 2 s of trimmed speech only (346 bona fide in the clean pool)"},
        {"kpi": "Student efficiency (RTF, params, RAM)", "weight": 10, "status": eff_status, "value": eff_value,
         "note": student_note(models)},
        {"kpi": "End-to-end flow: ASR <= 5%, genuine >= 90%", "weight": 10, "status": ivr_trials()[0], "value": ivr_trials()[1],
         "note": "python -m ivr_demo.trials: real ASVspoof clips through verify(), echo STT, identity gate bypassed; Gnani-clone trials PENDING"},
        {"kpi": "Replay / injection detection (G5, G6 EER)", "weight": 5, "status": "PENDING", "value": "n/a",
         "note": "G5 simulator in factory/replay_sim.py; G6 needs G2 audio"},
        {"kpi": "Rigor: shortcut audit, ablations, failure analysis, ITW / 2021 LA", "weight": 10, "status": "PARTIAL",
         "value": f"shortcut audit {'passes' if audit_ok else 'FAILS'}; codec-aug ablation {'done' if 'lcnn8_noaug' in models else 'PENDING'}",
         "note": "failure cases, In-the-Wild and 2021 LA sanity checks pending"},
        {"kpi": "Reproducibility: one-command eval, model card, data card", "weight": 5, "status": "PARTIAL",
         "value": "run.ps1 quick / run.ps1 report; MODEL_CARD.md; DATA_CARD.md; release/ holds models, calibration and gzipped scores",
         "note": "a fresh clone regenerates every table from release/ (run.ps1 report); rebuilding the audio needs the ASVspoof download"},
    ]
