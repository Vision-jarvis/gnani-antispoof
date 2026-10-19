"""eval.report on a synthetic score set laid out exactly like the real pipeline output."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import eval.report as rep
from eval.points import points_matrix
from factory.channel_sim import CONDITIONS


@pytest.fixture()
def fake_scores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    rng = np.random.default_rng(0)
    proc, scores = tmp_path / "proc", tmp_path / "scores"
    for split, n in (("dev", 200), ("eval", 300)):
        (proc / split).mkdir(parents=True)
        lab = np.where(np.arange(n) < n // 3, "bonafide", "spoof")
        attack = np.where(lab == "bonafide", "bonafide", np.array(["A07", "A08"])[np.arange(n) % 2])
        pd.DataFrame({"utt_id": [f"{split}{i}" for i in range(n)], "label": lab, "attack": attack}).to_csv(proc / split / "manifest.csv", index=False)
    man = pd.read_csv(proc / "eval" / "manifest.csv")
    scores.mkdir()
    for model, clean in (("gmm16_clean", "clean16k"), ("lcnn8_aug", "nb_pcm")):
        recs = []
        for c in ["clean16k", *CONDITIONS]:
            shift = 3.0 if c in (clean,) else 1.5
            for h in (0.0, 2.0) if model == "lcnn8_aug" else (0.0,):
                s = rng.normal(0, 1, len(man)) + shift * (man.label == "bonafide")
                recs += [{"utt_id": u, "condition": c, "horizon": h, "score": v} for u, v in zip(man.utt_id, s)]
        pd.DataFrame(recs).to_csv(scores / f"{model}.csv", index=False)
        dman = pd.read_csv(proc / "dev" / "manifest.csv")
        pd.DataFrame({"utt_id": dman.utt_id, "condition": clean, "score": rng.normal(0, 1, len(dman)) + 3 * (dman.label == "bonafide")}).to_csv(scores / f"{model}_dev.csv", index=False)
    monkeypatch.setattr(rep, "PROC", proc)
    monkeypatch.setattr(rep, "SCORES", scores)
    return tmp_path


def test_model_tables_and_points(fake_scores: Path) -> None:
    man = pd.read_csv(fake_scores / "proc" / "eval" / "manifest.csv")
    t = rep.model_tables("lcnn8_aug", man)
    assert t["clean_pool"] == "nb_pcm"
    assert t["pools"]["clean"]["eer"] < t["pools"]["heldout"]["eer"]  # built-in narrowband penalty
    assert t["delta_nb"] > 0 and "2s" in t["streaming_eer"]
    assert set(t["per_attack_eer"]) == {"A07", "A08"}
    res = {"models": {"lcnn8_aug": t, "gmm16_clean": rep.model_tables("gmm16_clean", man)}, "shortcut_audit": [], "points": []}
    kpis = points_matrix(res)
    assert sum(k["weight"] for k in kpis) == 100
    res["points"] = kpis
    md = rep.to_markdown(res)
    assert "delta-NB" in md and "gsm_fr (held-out)" in md
