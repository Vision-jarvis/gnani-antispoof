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

Live mode, the builder's own voice (spends credits; 4 Gnani calls in total; docs/DEMO_RUNBOOK.md):
  1. python -m ivr_demo.demo --live --new-challenge --language hi-IN
     1 Timbre call: a fresh random challenge, saved to artifacts/gnani_cache/ivr_challenge.json, and its
     prompt as the caller hears it (8 kHz mu-law) in artifacts/gnani_cache/ivr_prompt.wav. Play it, record
     the answer, prepare it (scripts/prep_own_voice.py --only live_answer).
  2. python -m ivr_demo.demo --live --caller data/own_voice/16k/live_answer.wav --clone --operating-point min_dcf
     Genuine caller: the recording through ``--channel`` (default g711u), Prisma realtime STT at 8 kHz
     (1 session), the CM. Clone caller: Gnani VC TTS of the SAME challenge with the cached embedding of the
     builder's reference, requested as 8 kHz mu-law (1 call), then the same checks (1 session). Decisions at
     the other dev-fixed operating points come from the same transcripts (no extra calls). Writes
     artifacts/ivr_live.json.
  Add ``--mock`` to either step to run the identical code offline (no key, no network, no credits): the mock
  STT echoes the challenge and mock Gnani audio is synthetic, so the outcomes mean nothing; mock files get a
  ``_mock`` suffix and stay in the git-ignored artifacts/gnani_cache/.
The identity gate is bypassed unless ``--asv lfcc --enrol <wav>`` (the LFCC stand-in, not a speaker verifier).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from cm.lcnn import LCNN
from cm.scorer import Calibration, CMScorer
from factory.channel_sim import apply_condition, resample
from gnani_api import AudioConfig, GnaniClient
from gnani_api.g711 import decode_mulaw
from gnani_api.mock import MockGnaniBackend, MockSTTConnect, synth_speechlike
from ivr_demo.asv import LFCCStatsASV
from ivr_demo.flow import SR, Challenge, new_challenge, prisma_stt, prompt_audio, verify
from ivr_demo.trials import BypassASV

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "artifacts" / "gnani_cache"  # git-ignored: every Gnani-generated audio and the challenge live here
LEDGER = ROOT / "artifacts" / "gnani_usage.jsonl"
SPEAKERS = ROOT / "factory" / "manifests" / "demo_builder_voice.csv"
OPERATING_POINTS = ("far1", "min_dcf", "eer")
DECISIONS = {0: "Success", 1: "Spoof Failure", 2: "Voice Failure", 3: "Internal Error"}
STATUSES = {0: "Success", 3: "Short Audio", 4: "No Audio", 5: "Internal Error"}


def load_cm(operating_point: str = "far1") -> CMScorer:
    try:
        return CMScorer.load(operating_point=operating_point)
    except FileNotFoundError:
        print("[demo] no trained CM at artifacts/models/lcnn8_aug.pt: using an UNTRAINED LCNN (plumbing only)")
        torch.manual_seed(0)
        return CMScorer(LCNN(), Calibration())


def real_scenario_audio() -> dict[str, np.ndarray] | None:
    """Genuine, replay and clone audio from ASVspoof 2019 LA eval (AMR-NB 12.2, or the G.711 release pack), same target speaker."""
    import pandas as pd

    from factory.store import load_packed

    for d, cond in ((ROOT / "data" / "proc" / "asv19" / "eval", "amrnb_12k2"), (ROOT / "release" / "demo_pack", "g711u")):
        if (d / f"{cond}.npz").exists():
            break
    else:
        return None
    man = pd.read_csv(d / "manifest.csv")
    packed = load_packed(d / f"{cond}.npz")
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


# -- live (and mock-live) path on the builder's own recordings -------------------------------------------------
def _rel(p: Path) -> str:
    """Repo-relative path for messages and JSON (absolute if the file lives outside the repo)."""
    try:
        return p.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def _suffix(mock: bool) -> str:
    return "_mock" if mock else ""


def challenge_path(mock: bool) -> Path:
    return CACHE / f"ivr_challenge{_suffix(mock)}.json"


def open_client(mock: bool) -> GnaniClient:
    if mock:
        return GnaniClient(api_key="mock-key", transport=MockGnaniBackend(api_key="mock-key").transport())
    return GnaniClient(ledger_path=LEDGER)  # key from GNANI_API_KEY or .env, never printed


def stt_fn(mock: bool, challenge: Challenge):  # noqa: ANN201 - an SttFn
    if mock:  # echoes the challenge: the phrase check is not exercised in mock mode
        return prisma_stt(api_key="mock-key", connect=MockSTTConnect(lambda pcm: challenge.text, api_key="mock-key"),
                          realtime_pace=False, drain_timeout_s=0.2)
    return prisma_stt()


def fixed_stt(transcript: str):  # noqa: ANN201 - an SttFn that replays a transcript (no network)
    async def run(pcm16: bytes, language: str) -> str:
        return transcript

    return run


def new_live_challenge(language: str, mock: bool, path: Path | None = None) -> Challenge:
    """Step 1: a fresh random challenge and its Timbre prompt (1 call), both saved under artifacts/gnani_cache."""
    challenge = new_challenge(language)
    path = path or challenge_path(mock)
    for d in (path.parent, CACHE):
        d.mkdir(parents=True, exist_ok=True)
    with open_client(mock) as client:
        prompt = prompt_audio(client, challenge, voice="Saanvi" if language == "kn-IN" else "Nalini")
    wav = CACHE / f"ivr_prompt{_suffix(mock)}.wav"
    sf.write(wav, prompt, SR, subtype="PCM_16")
    path.write_text(json.dumps({"language": challenge.language, "digits": list(challenge.digits), "text": challenge.text,
                                "created": datetime.now(timezone.utc).isoformat(), "mode": "mock" if mock else "live",
                                "prompt_wav": _rel(wav)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"challenge ({'MOCK' if mock else 'live'}): {challenge.text}")
    print(f"prompt: {_rel(wav)} ({len(prompt) / SR:.1f} s, 8 kHz mu-law as the caller hears it)")
    print(f"saved: {_rel(path)}. Play the prompt, record your answer once (docs/RECORDING.md),"
          " then: python scripts/prep_own_voice.py --only live_answer")
    return challenge


def load_challenge(path: Path) -> Challenge:
    if not path.is_file():
        raise SystemExit(f"no challenge at {path}: run step 1 first (python -m ivr_demo.demo --live --new-challenge)")
    d = json.loads(path.read_text(encoding="utf-8"))
    return Challenge(d["language"], tuple(d["digits"]), d["text"])


def line_audio(path: Path, channel: str) -> np.ndarray:
    """A WAV (any rate, mono or stereo) as the IVR receives it: through ``channel`` to 8 kHz, or just resampled."""
    if not path.is_file():
        raise SystemExit(f"missing audio: {path} (see docs/RECORDING.md for names and folders)")
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    return resample(x, sr, SR) if channel == "none" else apply_condition(x, sr, channel, seed=1)


def builder_embedding_path(speakers_csv: Path = SPEAKERS) -> Path:
    from factory.gnani_clone import embed_job

    with speakers_csv.open(encoding="utf-8") as f:
        spk = next(csv.DictReader(f))
    return embed_job(spk).out_path


def clone_answer(client: GnaniClient, challenge: Challenge, mock: bool, reference: Path | None) -> tuple[np.ndarray, str]:
    """The attacker's answer: VC TTS of the challenge in the builder's cloned voice, requested as 8 kHz mu-law."""
    from gnani_api import SpeakerEmbedding

    emb_path = builder_embedding_path()
    if emb_path.is_file():
        d = json.loads(emb_path.read_text())
        emb = SpeakerEmbedding(embedding=d["embedding"], shape=tuple(d["shape"]), dtype=d["dtype"])
        src = _rel(emb_path)
    elif mock:
        ref = reference if reference and reference.is_file() else None
        audio = ref.read_bytes() if ref else b"mock-reference"
        emb, src = client.vc_embedding(audio), "mock embedding"
    else:
        raise SystemExit(f"no cached embedding of the builder's voice at {_rel(emb_path)}: run the "
                         "clone step first (python -m factory.gnani_clone --speakers factory/manifests/demo_builder_voice.csv "
                         "--execute --max-calls 16); this demo never makes an embedding call on its own")
    mu = client.vc_tts(challenge.text, emb, audio_config=AudioConfig(sample_rate=8000, container="mulaw"))
    x = decode_mulaw(mu).astype(np.float32) / 32768.0
    CACHE.mkdir(parents=True, exist_ok=True)
    sf.write(CACHE / f"ivr_clone_answer{_suffix(mock)}.wav", x, SR, subtype="PCM_16")  # for playback; never committed
    return x, f"vachana-vc-v1, 8 kHz mu-law, embedding {src}"


def _clean(v: object) -> object:
    return None if isinstance(v, float) and math.isnan(v) else v


def judge(name: str, x: np.ndarray, source: str, challenge: Challenge, cms: dict[str, CMScorer], primary: str,
          asv: object, enrol: np.ndarray, stt) -> dict[str, object]:  # noqa: ANN001
    """One caller through verify() at the primary point (1 STT session); the other points reuse the transcript."""
    res = verify(x, challenge, enrol, cms[primary], asv, stt)  # type: ignore[arg-type]
    row: dict[str, object] = {"caller": name, "source": source, "operating_point": primary, **res.as_json()}
    if isinstance(asv, BypassASV):
        row.pop("asv_score", None)
    stats = getattr(stt, "stats", {})
    row["stt_final_delay_ms"] = _clean(round(1000 * stats["final_delay_s"], 1)) if "final_delay_s" in stats else None
    row["decision"] = DECISIONS.get(res.DecisionCode, "?")
    row["status"] = STATUSES.get(res.StatusCode, "?")
    others = {}
    for op, cm in cms.items():
        if op != primary:
            r = verify(x, challenge, enrol, cm, asv, fixed_stt(res.transcript or ""))  # type: ignore[arg-type]
            others[op] = {"DecisionCode": r.DecisionCode, "reason": r.reason, "tau_llr": round(cm.tau, 3)}
    row["other_operating_points"] = others
    return row


def run_live_pair(caller: Path | None, clone: bool, clone_file: Path | None, operating_point: str, channel: str, mock: bool,
                  asv_name: str = "bypass", enrol: Path | None = None, challenge_file: Path | None = None,
                  reference: Path | None = None, out: Path | None = None) -> dict[str, object]:
    """Step 2: the genuine answer and/or the clone answer to the saved challenge, decisions written to JSON."""
    challenge = load_challenge(challenge_file or challenge_path(mock))
    cms = {op: CMScorer.load(operating_point=op) for op in dict.fromkeys((operating_point, *OPERATING_POINTS))}
    if asv_name == "lfcc":
        if enrol is None:
            raise SystemExit("--asv lfcc needs --enrol <wav> (data/own_voice/16k/enrol.wav)")
        asv: object = LFCCStatsASV()
        enrol_emb = asv.embed(line_audio(enrol, channel))  # type: ignore[attr-defined]
    else:
        asv, enrol_emb = BypassASV(), np.zeros(1)
    mode = "MOCK (offline; STT echoes the challenge, outcomes mean nothing)" if mock else "LIVE (Gnani calls)"
    print(f"mode: {mode}; Gnani API key: {'mock' if mock else 'loaded from .env or GNANI_API_KEY (never shown)'}")
    print(f"challenge: {challenge.text}")
    print(f"CM: lcnn8_aug at {operating_point} (tau_llr = {cms[operating_point].tau:.3f}, fixed on ASVspoof dev); "
          f"channel: {channel}; identity gate: {'LFCC stand-in (not a speaker verifier)' if asv_name == 'lfcc' else 'bypassed (ECAPA PENDING)'}")
    for r in measured_rates(operating_point):
        print(f"measured at this point on {r['source']}: genuine success {r['genuine_success_pct']}%, attack success {r['attack_success_pct']}%")
    # Preflight: every input is read and checked before the first call, so a missing file never wastes a call.
    genuine_x = line_audio(caller, channel) if caller is not None else None
    clone_x = line_audio(clone_file, channel) if clone_file is not None else None
    if clone and clone_file is None and not mock and not builder_embedding_path().is_file():
        raise SystemExit(f"no cached embedding of the builder's voice at {_rel(builder_embedding_path())}: "
                         "run the clone step first; nothing was sent")
    warm = synth_speechlike("warm-up", SR, 40)  # a running IVR keeps its model warm: no first-call overhead in latency_ms
    for cm in cms.values():
        cm.score(warm)
    print("CM warmed up once on synthetic audio before timing (as a running service would be)")
    callers = []
    calls = {"vc_tts": 0, "prisma_realtime": 0}
    with open_client(mock) as client:
        if genuine_x is not None:
            calls["prisma_realtime"] += 1
            callers.append(judge("genuine", genuine_x, _rel(caller), challenge, cms, operating_point,  # type: ignore[union-attr]
                                 asv, enrol_emb, stt_fn(mock, challenge)))
        if clone or clone_x is not None:
            if clone_x is not None:
                x, src = clone_x, f"pre-made clone file {_rel(clone_file)}"  # type: ignore[union-attr]
            else:
                calls["vc_tts"] += 1
                x8, src = clone_answer(client, challenge, mock, reference)
                x = x8 if channel == "none" else apply_condition(x8, SR, channel, seed=2)
            calls["prisma_realtime"] += 1
            callers.append(judge("clone", x, src, challenge, cms, operating_point, asv, enrol_emb, stt_fn(mock, challenge)))
    for c in callers:
        print(f"{c['caller']:8s} StatusCode {c['StatusCode']} ({c['status']}), DecisionCode {c['DecisionCode']} ({c['decision']}), "
              f"reason {c['reason']}, cm_llr {c.get('cm_llr')}, local decision {c.get('latency_ms')} ms, "
              f"Prisma end-of-speech to transcript {c.get('stt_final_delay_ms')} ms; transcript: {c.get('transcript')!r}")
        for op, o in c["other_operating_points"].items():  # type: ignore[union-attr]
            print(f"         at {op}: DecisionCode {o['DecisionCode']} ({o['reason']})")
    result = {"mode": "mock" if mock else "live", "date": datetime.now(timezone.utc).isoformat(), "challenge": challenge.text,
              "language": challenge.language, "operating_point": operating_point, "tau_llr": round(cms[operating_point].tau, 3),
              "channel": channel, "asv": asv_name, "gnani_calls_this_step": calls,
              "measured_rates_at_point": measured_rates(operating_point), "callers": callers}
    out = out or (CACHE / "ivr_live_mock.json" if mock else ROOT / "artifacts" / "ivr_live.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=_clean), encoding="utf-8")
    print(f"written: {out.as_posix()}")
    return result


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # Kannada / Hindi phrases on a Windows console
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--language", default=None, help="kn-IN (scenario demo default) or hi-IN (own-voice live run)")
    ap.add_argument("--live", action="store_true", help="the builder's own recordings (spends credits unless --mock)")
    ap.add_argument("--mock", action="store_true", help="with --live: same code path, offline mock Gnani backend")
    ap.add_argument("--new-challenge", action="store_true", help="live step 1: challenge + Timbre prompt (1 call)")
    ap.add_argument("--challenge", type=Path, help="challenge JSON (default artifacts/gnani_cache/ivr_challenge.json)")
    ap.add_argument("--caller", type=Path, help="genuine answer WAV (data/own_voice/16k/live_answer.wav)")
    ap.add_argument("--clone", action="store_true", help="also let the clone answer (1 VC TTS call with the cached embedding)")
    ap.add_argument("--clone-file", type=Path, help="use this WAV as the clone's answer instead of synthesizing one")
    ap.add_argument("--reference", type=Path, default=ROOT / "data" / "own_voice" / "builder_15s.wav",
                    help="mock only: reference for the mock embedding when no cached embedding exists")
    ap.add_argument("--channel", default="g711u", help="phone channel applied to both callers (factory.channel_sim name, or none)")
    ap.add_argument("--asv", choices=["bypass", "lfcc"], default="bypass")
    ap.add_argument("--enrol", type=Path, help="enrolment WAV, only used with --asv lfcc")
    ap.add_argument("--out", type=Path, help="result JSON (default artifacts/ivr_live.json, mock: artifacts/gnani_cache/ivr_live_mock.json)")
    ap.add_argument("--operating-point", default="far1", choices=["far1", "min_dcf", "eer", "bayes"])
    a = ap.parse_args()
    if a.mock and not a.live:
        raise SystemExit("--mock goes with --live (the scenario demo without --live is always offline)")
    if a.live and a.new_challenge:
        new_live_challenge(a.language or "hi-IN", a.mock, a.challenge)
    elif a.live:
        if a.caller is None and not (a.clone or a.clone_file):
            raise SystemExit("give --caller and/or --clone (see the module docstring)")
        run_live_pair(a.caller, a.clone, a.clone_file, a.operating_point, a.channel, a.mock, a.asv, a.enrol, a.challenge,
                      a.reference, a.out)
    else:
        run_mock(a.language or "kn-IN", a.operating_point)


if __name__ == "__main__":
    np.set_printoptions(precision=3)
    main()
