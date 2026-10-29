"""Own-voice kit: converter, trial sets, clone plan from the takes manifest, phrase check, live demo and Day 30 outputs.

Everything here is offline: synthetic tones, the mock Gnani backend, untrained CM weights, tmp folders.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pyloudnorm
import pytest
import soundfile as sf
import torch

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):  # noqa: ANN202 - a module
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[name] = mod  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


prep = _load_script("prep_own_voice")
day30 = _load_script("day30_outputs")


def tone(seconds: float, sr: int, f0: float = 180.0, stereo: bool = True, gain: float = 0.3) -> np.ndarray:
    """A voiced-speech-like synthetic tone: harmonics with a syllabic envelope, quarter-second silences at both ends."""
    t = np.arange(int(seconds * sr)) / sr
    x = sum((1.0 / k) * np.sin(2 * np.pi * k * f0 * t) for k in range(1, 8))
    env = 0.5 * (1 - np.cos(2 * np.pi * 3.0 * t))
    y = gain * env * x / np.max(np.abs(x))
    pad = np.zeros(int(0.25 * sr))
    y = np.concatenate([pad, y, pad]).astype(np.float32)
    return np.stack([y, 0.8 * y], axis=1) if stereo else y


def _takes_csv(tmp: Path, rows: list[dict[str, str]]) -> Path:
    p = tmp / "takes.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["take", "kind", "language", "clone", "test_subset", "text", "alt_text", "transliteration"])
        w.writeheader()
        for r in rows:
            w.writerow({"language": "hi-IN", "clone": "no", "test_subset": "no", "text": "", "alt_text": "", "transliteration": "", **r})
    return p


@pytest.fixture()
def own_root(tmp_path: Path) -> Path:
    raw = tmp_path / "own" / "raw"
    raw.mkdir(parents=True)
    sf.write(raw / "builder_15s.wav", tone(15.0, 44100), 44100, subtype="PCM_16")
    sf.write(raw / "answer_01.wav", tone(3.0, 48000, f0=150), 48000, subtype="PCM_16")
    return tmp_path / "own"


def test_prep_writes_mono_16k_and_8k_normalised(own_root: Path, tmp_path: Path) -> None:
    takes = prep.read_takes(_takes_csv(tmp_path, [{"take": "builder_15s", "kind": "reference"}, {"take": "answer_01", "kind": "answer"}]))
    reports, errors = prep.run_takes(own_root, takes)
    assert errors == [] and [r.take for r in reports] == ["builder_15s", "answer_01"]
    for take, dur in (("builder_15s", 15.0), ("answer_01", 3.0)):
        for sub, rate in (("16k", 16000), ("8k", 8000)):
            x, sr = sf.read(own_root / sub / f"{take}.wav", dtype="float32")
            assert sr == rate and x.ndim == 1
            assert abs(len(x) / sr - dur) < 0.4  # the quarter-second silences are trimmed (50 ms margins kept)
        x16, _ = sf.read(own_root / "16k" / f"{take}.wav", dtype="float64")
        assert abs(pyloudnorm.Meter(16000).integrated_loudness(x16) + 23.0) < 0.5
    assert sf.info(own_root / "builder_15s.wav").samplerate == 16000  # the path the clone manifest sends
    assert reports[0].channels == 2 and reports[0].source_sr == 44100


def test_prep_clear_errors(own_root: Path, tmp_path: Path) -> None:
    raw = own_root / "raw"
    sf.write(raw / "builder_15s.wav", tone(3.0, 16000), 16000, subtype="PCM_16")  # too short for the clone API
    sf.write(raw / "answer_02.wav", np.zeros(16000 * 3, np.float32), 16000, subtype="PCM_16")  # silence
    takes = prep.read_takes(_takes_csv(tmp_path, [{"take": "builder_15s", "kind": "reference"}, {"take": "answer_02", "kind": "answer"},
                                                  {"take": "hinglish_01", "kind": "hinglish"}]))
    reports, errors = prep.run_takes(own_root, takes)
    assert reports == [] and len(errors) == 3
    assert "5 to 30 s" in errors[0] and "no speech" in errors[1] and "no recording" in errors[2]
    _, errors = prep.run_takes(own_root, takes, only=["hinglish_01"], allow_missing=True)
    assert errors == []
    _, errors = prep.run_takes(own_root, takes, only=["nope"])
    assert "unknown take" in errors[0]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_prep_decodes_m4a_like_sound_recorder(own_root: Path, tmp_path: Path) -> None:
    src = tmp_path / "src.wav"
    sf.write(src, tone(3.0, 48000), 48000, subtype="PCM_16")
    m4a = own_root / "raw" / "answer_01.m4a"
    (own_root / "raw" / "answer_01.wav").unlink()
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-c:a", "aac", "-b:a", "96k", str(m4a)], check=True)
    takes = prep.read_takes(_takes_csv(tmp_path, [{"take": "answer_01", "kind": "answer"}]))
    reports, errors = prep.run_takes(own_root, takes)
    assert errors == [] and reports[0].decoder == "ffmpeg" and reports[0].source_sr == 48000
    assert sf.info(own_root / "8k" / "answer_01.wav").samplerate == 8000


def test_trialsets_from_standin_spoofs(own_root: Path, tmp_path: Path) -> None:
    takes = prep.read_takes(_takes_csv(tmp_path, [{"take": "answer_01", "kind": "answer"}]))
    prep.run_takes(own_root, takes)
    spoofs = tmp_path / "spoofs"
    spoofs.mkdir()
    sf.write(spoofs / "fake1.wav", tone(2.5, 16000, f0=210, stereo=False), 16000, subtype="PCM_16")
    index = prep.build_trialsets(own_root, takes, ("g711u",), spoof_src=spoofs)
    assert {(r["label"], r["file"]) for r in index} == {("bonafide", "trials/g711u/bona/answer_01.wav"),
                                                         ("spoof", "trials/g711u/spoof/clone_fake1.wav")}
    assert sf.info(own_root / "trials" / "g711u" / "spoof" / "clone_fake1.wav").samplerate == 8000
    with pytest.raises(prep.PrepError):
        prep.build_trialsets(own_root, takes, ("g711u",), jobs_csv=tmp_path / "missing.csv")


def test_clone_plan_uses_take_texts_and_reference_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import factory.gnani_clone as gc

    monkeypatch.setattr(gc, "CACHE", tmp_path / "cache")
    takes = _takes_csv(tmp_path, [{"take": "answer_01", "kind": "answer", "clone": "yes", "text": "एक दो तीन चार"},
                                  {"take": "hinglish_01", "kind": "hinglish", "clone": "yes", "text": "मेरी voice", "alt_text": "मेरी वॉइस"},
                                  {"take": "enrol", "kind": "enrol", "clone": "no", "text": "नमूना"}])
    ref = tmp_path / "ref.wav"
    sf.write(ref, tone(10.0, 16000, stereo=False), 16000, subtype="PCM_16")
    spk = {"speaker": "builder_self", "language": "hi-IN", "reference_wav": str(ref), "consent": "self", "texts": str(takes)}
    jobs = gc.plan([spk], per_speaker=15, g1_per_voice=40)
    assert [j.kind for j in jobs] == ["vc_embed", "vc_tts", "vc_tts"]  # no implicit G1 jobs for the speaker's language
    assert [j.text for j in jobs[1:]] == ["एक दो तीन चार", "मेरी voice"]
    assert [j.text for j in gc.plan([spk], 15, 0, alt_text=True)[1:]] == ["एक दो तीन चार", "मेरी वॉइस"]
    keys = [j.key for j in jobs]
    sf.write(ref, tone(10.0, 16000, f0=220, stereo=False), 16000, subtype="PCM_16")  # re-recorded reference
    assert all(a != b for a, b in zip(keys, (j.key for j in gc.plan([spk], 15, 40))))
    assert gc.reference_problems([spk]) == []
    assert "not recorded" in gc.reference_problems([{**spk, "reference_wav": str(tmp_path / "none.wav")}])[0]
    assert gc.manifest_path(Path("demo_builder_voice.csv"), []).name == "jobs_demo_builder_voice.csv"
    assert gc.manifest_path(Path("demo_builder_voice.csv"), []).parent == gc.CACHE  # git-ignored, never factory/manifests


def test_repo_takes_manifest_matches_ivr_format_and_clone_plan() -> None:
    from ivr_demo.phrase_check import hindi_digits
    from ivr_demo.phrases import DIGIT_WORDS

    takes = prep.read_takes()
    kinds = [t["kind"] for t in takes]
    assert kinds.count("reference") == 1 and kinds.count("answer") >= 5 and 8 <= kinds.count("hinglish") <= 10
    assert sum(t["clone"] == "yes" for t in takes) == 15  # = the 15 VC TTS calls of the 16-call own-voice plan
    for t in takes:
        if t["kind"] in ("answer", "hinglish"):
            words = t["text"].split()
            assert all(w in DIGIT_WORDS["hi-IN"] for w in words[:4]) and len(hindi_digits(t["text"])) >= 4
    with (ROOT / "factory" / "manifests" / "demo_builder_voice.csv").open(encoding="utf-8") as f:
        spk = next(csv.DictReader(f))
    assert spk["reference_wav"] == "data/own_voice/builder_15s.wav" and spk["consent"] == "self"
    recording = (ROOT / "docs" / "RECORDING.md").read_text(encoding="utf-8")
    for t in takes:  # every file name the code expects is in the recording guide, with its exact text
        assert t["take"] in recording
        if t["text"]:
            assert t["text"] in recording


def test_phrase_check_scoring_and_mock_run(tmp_path: Path) -> None:
    from ivr_demo import phrase_check as pc

    assert pc.hindi_digits("दो नौ एक पांच मेरी voice") == [2, 9, 1, 5]
    assert pc.hindi_digits("29 15 password") == [2, 9, 1, 5]
    s = pc.score("दो नौ एक पाँच मेरी voice ही मेरा password है", "दो नौ एक पाँच मेरी वॉइस ही मेरा पासवर्ड है",
                 "दो नौ एक पाँच मेरी वॉयस ही मेरा पासवर्ड है")
    assert s["match"] and s["digits_ok"]
    assert not pc.score("दो नौ एक पाँच मेरी आवाज़", "", "चार चार मेरी आवाज़")["digits_ok"]
    audio = tmp_path / "16k"
    audio.mkdir()
    sf.write(audio / "hinglish_01.wav", tone(2.5, 16000, stereo=False), 16000, subtype="PCM_16")
    takes = _takes_csv(tmp_path, [{"take": "hinglish_01", "kind": "hinglish", "text": "दो नौ एक पाँच मेरी voice", "alt_text": "दो नौ एक पाँच मेरी वॉइस"},
                                  {"take": "hinglish_02", "kind": "hinglish", "text": "एक"}])
    answers, missing = pc.load_answers(takes, audio)
    assert [a["take"] for a in answers] == ["hinglish_01"] and missing == ["hinglish_02"]
    res = pc.run(answers, audio, "g711u", "hi-IN", "hi-IN", mock=True, execute=False, max_calls=0)
    assert res["summary"]["v2.5"]["match"] == 1 and res["summary"]["v3.0"]["served_by"] == ["prisma-v3.0"]
    dry = pc.run(answers, audio, "g711u", "hi-IN", "hi-IN", mock=False, execute=False, max_calls=0)
    assert dry["calls_made"] == 0 and dry["summary"]["v2.5"]["n_scored"] == 0


def test_client_stt_model_field() -> None:
    from gnani_api import GnaniClient
    from gnani_api.mock import MockGnaniBackend

    backend = MockGnaniBackend(api_key="k", stt_transcript_fn=lambda a, lang: "ok")
    with GnaniClient(api_key="k", transport=backend.transport()) as c:
        assert c.stt(b"RIFF", "hi-IN").raw["model"] == "mock-default"
        assert c.stt(b"RIFF", "indic-auto", model="prisma-v3.0").raw["model"] == "prisma-v3.0"
        with pytest.raises(ValueError):
            c.stt(b"RIFF", "indic-auto")  # indic-auto exists only on v3.0
    assert "model" in backend.calls[1]["fields"]


@pytest.fixture()
def untrained_cm(monkeypatch: pytest.MonkeyPatch) -> None:
    from cm.lcnn import LCNN
    from cm.scorer import Calibration, CMScorer

    def fake_load(name: str = "lcnn8_aug", models_dir: Path | None = None, operating_point: str = "far1") -> CMScorer:
        torch.manual_seed(0)
        ops = {"far1": 1e9, "min_dcf": -1e9, "eer": 0.0}
        return CMScorer(LCNN(), Calibration(tau_llr=ops["far1"], operating_points=ops), operating_point=operating_point)

    monkeypatch.setattr(CMScorer, "load", staticmethod(fake_load))


def test_live_demo_mock_two_steps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, untrained_cm: None) -> None:
    from ivr_demo import demo

    monkeypatch.setattr(demo, "CACHE", tmp_path / "cache")
    challenge = demo.new_live_challenge("hi-IN", mock=True, path=tmp_path / "challenge.json")
    assert json.loads((tmp_path / "challenge.json").read_text(encoding="utf-8"))["text"] == challenge.text
    assert sf.info(tmp_path / "cache" / "ivr_prompt_mock.wav").samplerate == 8000
    caller = tmp_path / "live_answer.wav"
    sf.write(caller, tone(3.0, 16000, stereo=False), 16000, subtype="PCM_16")
    out = tmp_path / "live.json"
    res = demo.run_live_pair(caller, True, None, "min_dcf", "g711u", True, challenge_file=tmp_path / "challenge.json",
                             reference=tmp_path / "none.wav", out=out)
    assert [c["caller"] for c in res["callers"]] == ["genuine", "clone"]
    genuine = res["callers"][0]
    assert (genuine["StatusCode"], genuine["DecisionCode"], genuine["reason"]) == (0, 0, "accepted")  # min_dcf tau = -inf here
    assert genuine["other_operating_points"]["far1"]["DecisionCode"] == 1  # same transcript, stricter point
    assert "asv_score" not in genuine and res["gnani_calls_this_step"] == {"vc_tts": 1, "prisma_realtime": 2}
    assert json.loads(out.read_text(encoding="utf-8"))["mode"] == "mock"
    with pytest.raises(SystemExit):  # no challenge yet: refuses before any call
        demo.run_live_pair(caller, False, None, "far1", "g711u", True, challenge_file=tmp_path / "missing.json")


def test_day30_outputs_reads_runs_and_draws(tmp_path: Path) -> None:
    rows = [{"utt_id": f"a{i}", "label": lab, "cm_llr": v, "code_far1": int(v < 3), "tau_far1": 3.0, "code_min_dcf": int(v < -0.7),
             "tau_min_dcf": -0.7, "code_eer": 0, "tau_eer": 0.5} for i, (lab, v) in enumerate([("bonafide", 3.5), ("bonafide", 0.1), ("spoof", -2.0)])]
    for c in ("g711u", "amrnb_4k75"):
        with (tmp_path / f"ivr_trials_ownvoice_{c}_scores.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    teacher = tmp_path / "teacher.csv"
    teacher.write_text("file,condition,label,score,tau_far1,accept_far1,tau_min_dcf,accept_min_dcf\n"
                       "g711u/bona/a.wav,g711u,bonafide,8.0,7.1,True,1.8,True\ng711u/spoof/b.wav,g711u,spoof,7.5,7.1,True,1.8,True\n")
    live = tmp_path / "live.json"
    live.write_text(json.dumps({"mode": "live", "challenge": "x", "operating_point": "min_dcf", "tau_llr": -0.7, "channel": "g711u",
                                "asv": "bypass", "callers": [{"caller": "genuine", "DecisionCode": 0, "StatusCode": 0, "reason": "accepted",
                                                              "latency_ms": 30.0, "stt_final_delay_ms": 900.0, "other_operating_points": {}}]}))
    png = tmp_path / "chart.png"
    args = ["--trials-dir", str(tmp_path), "--teacher", str(teacher), "--live", str(live), "--phrase", str(tmp_path / "none.json"),
            "--jobs", str(tmp_path / "none.csv"), "--png", str(png)]
    assert day30.main(args) == 0 and png.stat().st_size > 10_000
    cpu = day30.cpu_scores(tmp_path, ("g711u",), "ownvoice")
    assert day30.counts(cpu.label, cpu.code_far1.eq(0)) == (1, 2, 0, 1)
    live.write_text(live.read_text().replace('"live"', '"mock"'))
    assert day30.main(args[:-2]) == 1  # mock input: the default posts/img path is refused
