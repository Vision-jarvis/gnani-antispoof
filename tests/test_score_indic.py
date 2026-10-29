"""Teacher scoring on the Indic pilot (cm/teacher/score_indic.py), CPU only: synthetic pilot stores, stub scorer."""

from __future__ import annotations

import numpy as np
import pandas as pd

from cm.teacher import score_indic as S
from eval import indic_report
from factory.store import save_packed


def _pilot(tmp_path, conds, n=3, sr=8000):
    rng = np.random.default_rng(0)
    for c in conds:
        clips = [rng.normal(0, 0.1, sr).astype(np.float32) for _ in range(n)]
        save_packed(tmp_path / f"{c}.npz", [f"u{i}" for i in range(n)], clips, sr)
    return tmp_path


def test_only_8k_conditions_are_scored(tmp_path) -> None:
    pilot = _pilot(tmp_path / "pilot", ["clean16k", "nb_pcm", "g711u"])
    assert S.pilot_conditions(pilot) == ["nb_pcm", "g711u"]


def test_scores_are_16k_inputs_written_in_indic_report_format(tmp_path) -> None:
    pilot = _pilot(tmp_path / "pilot", ["clean16k", "nb_pcm", "gsm_fr"])
    seen = []

    def stub(clips):
        seen.extend(len(c) for c in clips)
        return np.arange(len(clips), dtype=float)

    df = S.score_pilot(stub, pilot, tmp_path / "out")
    out = pd.read_csv(tmp_path / "out" / "indic" / "teacher.csv")
    assert list(out.columns) == ["utt_id", "condition", "score"]
    assert sorted(out.condition.unique()) == ["gsm_fr", "nb_pcm"] and len(out) == len(df) == 6
    assert seen and all(n > 8000 for n in seen)  # upsampled from 8 kHz (1 s of 8 kHz -> about 2x samples)


def test_finished_parts_are_reused(tmp_path) -> None:
    pilot = _pilot(tmp_path / "pilot", ["nb_pcm"])
    calls = []
    stub = lambda clips: (calls.append(1), np.zeros(len(clips)))[1]  # noqa: E731
    S.score_pilot(stub, pilot, tmp_path / "out")
    S.score_pilot(stub, pilot, tmp_path / "out")
    assert len(calls) == 1


def test_indic_report_reads_the_teacher_as_a_gpu_scored_model() -> None:
    assert "teacher" in indic_report.GPU_SCORED
