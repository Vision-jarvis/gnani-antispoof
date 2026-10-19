"""End-to-end IVR voice-auth demo. Default: fully offline on the mock Gnani backend.

Scenarios (mock mode):
  genuine   the enrolled caller says the fresh challenge phrase
  replay    an old recording: right voice, but it says LAST session's phrase (STT shows the mismatch)
  clone     a voice-clone (mock VC) saying the right phrase: only the CM can stop it
Mock audio is synthetic, so the CM and ASV numbers here exercise plumbing, not accuracy.

Live mode (spends credits; run only when you mean to):
  python -m ivr_demo.demo --live --caller my_answer_8k.wav --enrol my_enrol_8k.wav --language kn-IN
  It makes 1 Timbre call (the prompt, saved to artifacts/ivr_prompt.wav) and 1 Prisma realtime session.
"""

from __future__ import annotations

import argparse
import json
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

ROOT = Path(__file__).resolve().parents[1]


def load_cm() -> CMScorer:
    try:
        return CMScorer.load()
    except FileNotFoundError:
        print("[demo] no trained CM at artifacts/models/lcnn8_aug.pt: using an UNTRAINED LCNN (plumbing only)")
        torch.manual_seed(0)
        return CMScorer(LCNN(), Calibration())


def run_mock(language: str) -> list[dict[str, object]]:
    backend = MockGnaniBackend(api_key="mock-key")
    client = GnaniClient(api_key="mock-key", transport=backend.transport())
    cm, asv = load_cm(), LFCCStatsASV()
    voice = lambda seed, n: apply_condition(synth_speechlike(seed, 16000, n), 16000, "amrnb_12k2")  # noqa: E731
    enrol = asv.embed(voice("caller-A enrolment", 160))
    old, fresh = new_challenge(language, seed=1), new_challenge(language, seed=2)
    prompt = prompt_audio(client, fresh, voice="Saanvi" if language == "kn-IN" else "Nalini")
    print(f"[demo] challenge: {fresh.text!r}; Timbre prompt {len(prompt) / SR:.1f} s at 8 kHz mu-law")
    scenarios = {
        "genuine": (voice("caller-A answer", 60), fresh.text),
        "replay": (voice("caller-A old call", 60), old.text),
        "clone": (voice("vc-clone-of-A", 60), fresh.text),
    }
    out = []
    for name, (audio, spoken) in scenarios.items():
        stt = prisma_stt(api_key="mock-key", connect=MockSTTConnect(lambda pcm, s=spoken: s, api_key="mock-key"),
                         realtime_pace=False, drain_timeout_s=0.2)
        res = verify(audio, fresh, enrol, cm, asv, stt).as_json()
        out.append({"scenario": name, **res})
        print(json.dumps(out[-1], ensure_ascii=False))
    return out


def run_live(language: str, caller: Path, enrol_wav: Path) -> None:
    cm, asv = load_cm(), LFCCStatsASV()
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--language", default="kn-IN")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--caller", type=Path)
    ap.add_argument("--enrol", type=Path)
    a = ap.parse_args()
    if a.live:
        run_live(a.language, a.caller, a.enrol)
    else:
        run_mock(a.language)


if __name__ == "__main__":
    np.set_printoptions(precision=3)
    main()
