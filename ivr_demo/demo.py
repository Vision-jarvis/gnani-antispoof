"""End-to-end IVR voice-auth demo. Default: fully offline on the mock Gnani backend.

Scenarios (mock mode; Gnani calls go to the offline mock, the audio is real when data/ exists):
  genuine   a real ASVspoof 2019 LA eval bona fide clip through AMR-NB 12.2 (the "enrolled caller")
  replay    another bona fide clip of the same speaker that says LAST session's phrase (STT shows the mismatch)
  clone     a real ASVspoof eval spoof of the same speaker saying the right phrase: only the CM can stop it
Every line states the operating point (dev-fixed, ``--operating-point``) and the header prints the measured
genuine and attack success at that point from ``python -m ivr_demo.trials``. Outcomes are not scripted: the
genuine caller can fail, and at the FAR = 1% point it usually does. The phrase check uses a mock STT that
returns what the scenario says; the identity gate is bypassed (the ASV stand-in is not a speaker verifier,
ECAPA is PENDING), so no ASV score is printed. Without data/ the audio falls back to synthetic noise and
the CM outcome means nothing.

Live mode (spends credits; run only when you mean to):
  python -m ivr_demo.demo --live --caller my_answer_8k.wav --enrol my_enrol_8k.wav --language kn-IN
  It makes 1 Timbre call (the prompt, saved to artifacts/ivr_prompt.wav) and 1 Prisma realtime session.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from cm.lcnn import LCNN
from cm.scorer import Calibration, CMScorer
from factory.channel_sim import apply_condition
from gnani_api import GnaniClient
from gnani_api.mock import MockGnaniBackend, MockSTTConnect, synth_speechlike
from ivr_demo.asv import LFCCStatsASV
from ivr_demo.flow import SR, new_challenge, prisma_stt, prompt_audio, verify
from ivr_demo.trials import BypassASV

ROOT = Path(__file__).resolve().parents[1]


def load_cm(operating_point: str = "far1") -> CMScorer:
    try:
        return CMScorer.load(operating_point=operating_point)
    except FileNotFoundError:
        print("[demo] no trained CM at artifacts/models/lcnn8_aug.pt: using an UNTRAINED LCNN (plumbing only)")
        torch.manual_seed(0)
        return CMScorer(LCNN(), Calibration())


def real_scenario_audio() -> dict[str, np.ndarray] | None:
    """Genuine, replay and clone audio from ASVspoof 2019 LA eval (AMR-NB 12.2), same target speaker."""
    import pandas as pd

    from factory.store import load_packed

    d = ROOT / "data" / "proc" / "asv19" / "eval"
    if not (d / "amrnb_12k2.npz").exists():
        return None
    man = pd.read_csv(d / "manifest.csv")
    packed = load_packed(d / "amrnb_12k2.npz")
    pos = {str(u): i for i, u in enumerate(packed.utt_ids)}
    for spk, g in man.groupby("speaker", sort=True):
        bona, spoof = g[g.label == "bonafide"].utt_id.astype(str).tolist(), g[g.label == "spoof"].utt_id.astype(str).tolist()
        long_bona = [u for u in bona if len(packed.get(pos[u])) >= 2.5 * SR]
        if len(long_bona) >= 2 and spoof:
            return {"genuine": packed.get(pos[long_bona[0]]), "replay": packed.get(pos[long_bona[1]]), "clone": packed.get(pos[spoof[0]])}
    return None


def measured_rates(operating_point: str) -> list[dict[str, object]]:
    p = ROOT / "artifacts" / "ivr_trials_asvspoof.json"
    return [r for r in json.loads(p.read_text()) if r["operating_point"] == operating_point] if p.exists() else []


def run_mock(language: str, operating_point: str = "far1") -> list[dict[str, object]]:
    backend = MockGnaniBackend(api_key="mock-key")
    client = GnaniClient(api_key="mock-key", transport=backend.transport())
    cm, asv = load_cm(operating_point), BypassASV()
    print(f"[demo] CM operating point: {operating_point} (tau_llr = {cm.tau:.3f}, fixed on ASVspoof dev)")
    for r in measured_rates(operating_point):
        print(f"[demo] measured at this point on {r['source']}: genuine success {r['genuine_success_pct']}% "
              f"(n={r['n_bona']}), attack success {r['attack_success_pct']}% (n={r['n_spoof']})")
    real = real_scenario_audio()
    if real is None:
        print("[demo] data/ missing: SYNTHETIC audio, CM outcomes below are meaningless (plumbing only)")
        voice = lambda seed, n: apply_condition(synth_speechlike(seed, 16000, n), 16000, "amrnb_12k2")  # noqa: E731
        real = {"genuine": voice("caller-A answer", 60), "replay": voice("caller-A old call", 60), "clone": voice("vc-clone-of-A", 60)}
    old, fresh = new_challenge(language, seed=1), new_challenge(language, seed=2)
    prompt = prompt_audio(client, fresh, voice="Saanvi" if language == "kn-IN" else "Nalini")
    print(f"[demo] challenge: {fresh.text!r}; Timbre prompt {len(prompt) / SR:.1f} s at 8 kHz mu-law (mock)")
    spoken = {"genuine": fresh.text, "replay": old.text, "clone": fresh.text}
    out = []
    for name, audio in real.items():
        stt = prisma_stt(api_key="mock-key", connect=MockSTTConnect(lambda pcm, s=spoken[name]: s, api_key="mock-key"),
                         realtime_pace=False, drain_timeout_s=0.2)
        res = verify(audio, fresh, asv.embed(audio), cm, asv, stt).as_json()
        res.pop("asv_score", None)  # identity gate bypassed: no ASV score to show
        out.append({"scenario": name, "operating_point": operating_point, **res})
        print(json.dumps(out[-1], ensure_ascii=False))
    return out


def run_live(language: str, caller: Path, enrol_wav: Path, operating_point: str = "far1") -> None:
    cm, asv = load_cm(operating_point), LFCCStatsASV()
    print(f"CM operating point: {operating_point} (tau_llr = {cm.tau:.3f}); ASV is the LFCC stand-in, its score is not an ASV result")
    x, sr = sf.read(caller, dtype="float32")
    e, sr_e = sf.read(enrol_wav, dtype="float32")
    if sr != SR or sr_e != SR:
        raise SystemExit("caller and enrolment audio must be 8 kHz mono WAV")
    challenge = new_challenge(language)
    with GnaniClient(ledger_path=ROOT / "artifacts" / "gnani_usage.jsonl") as client:
        prompt = prompt_audio(client, challenge, voice="Saanvi" if language == "kn-IN" else "Nalini")
    sf.write(ROOT / "artifacts" / "ivr_prompt.wav", prompt, SR)
    print(f"challenge: {challenge.text}")
    print(json.dumps(verify(x, challenge, asv.embed(e), cm, asv, prisma_stt()).as_json(), ensure_ascii=False, indent=2))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # Kannada / Hindi phrases on a Windows console
    ap = argparse.ArgumentParser()
    ap.add_argument("--language", default="kn-IN")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--caller", type=Path)
    ap.add_argument("--enrol", type=Path)
    ap.add_argument("--operating-point", default="far1", choices=["far1", "min_dcf", "eer", "bayes"])
    a = ap.parse_args()
    if a.live:
        run_live(a.language, a.caller, a.enrol, a.operating_point)
    else:
        run_mock(a.language, a.operating_point)


if __name__ == "__main__":
    np.set_printoptions(precision=3)
    main()
