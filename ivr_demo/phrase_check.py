"""Prisma v2.5 vs v3.0 phrase check on the builder's own 8 kHz answers (REST, 2 calls per answer).

  python -m ivr_demo.phrase_check                              # dry run: the plan (calls, audio seconds), nothing sent
  python -m ivr_demo.phrase_check --mock                       # the same code offline (rehearsal; outcomes mean nothing)
  python -m ivr_demo.phrase_check --execute --max-calls 20     # live: 10 answers x 2 models

Each answer of kind ``hinglish`` in factory/manifests/own_voice_takes.csv (four digits spoken in Hindi plus a
Hinglish banking phrase, the IVR phrase format), from ``data/own_voice/16k/<take>.wav``, goes through
``--channel`` (default g711u: the phone line) to 8 kHz PCM16 WAV and is sent to ``POST /stt/v3`` twice: with the
server default (Prisma v2.5) and with ``model=prisma-v3.0`` (opt-in since 2026-10-22), both with
``language_code=hi-IN`` and ``format=verbatim``, so the model is the only difference.
Scoring: ``match`` is the IVR's own rule (``ivr_demo.phrases.phrase_matches``: normalised character edit
distance <= 0.25) against the expected text OR its ``alt_text`` (the same words with the English ones written
in Devanagari), so neither model is penalised for the script it writes English words in. ``digits_ok``: the
four digits are recognised in order (the part a replayed recording cannot contain). ``served_by`` is the
``model`` field of each response: if the v3.0 rows do not say prisma-v3.0, the opt-in did not take effect and
the comparison is void (the summary says so).
Live transcripts are cached by (model, language, audio hash) in artifacts/gnani_cache/stt/, so a rerun never
pays twice; mock runs never touch that cache. Output: artifacts/prisma_phrase_check.json (mock and dry runs:
artifacts/gnani_cache/prisma_phrase_check_mock.json). Tiny sample: report it as n answers, never as a rate
with decimals.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf

from factory.channel_sim import apply_condition, resample
from gnani_api import GnaniClient
from gnani_api.mock import MockGnaniBackend
from gnani_api.schemas import GnaniAPIError
from ivr_demo.phrases import DIGIT_WORDS, normalise_text, phrase_distance, phrase_matches

ROOT = Path(__file__).resolve().parents[1]
TAKES = ROOT / "factory" / "manifests" / "own_voice_takes.csv"
AUDIO = ROOT / "data" / "own_voice" / "16k"
CACHE = ROOT / "artifacts" / "gnani_cache" / "stt"
LEDGER = ROOT / "artifacts" / "gnani_usage.jsonl"
OUT = ROOT / "artifacts" / "prisma_phrase_check.json"
OUT_MOCK = ROOT / "artifacts" / "gnani_cache" / "prisma_phrase_check_mock.json"
MODELS = {"v2.5": None, "v3.0": "prisma-v3.0"}  # label -> REST ``model`` form field (None = server default)
FATAL = {401, 402, 403, 429}  # auth, credits, rate limit: stop instead of burning the cap
# Spellings Prisma may use for Hindi digit words, beyond ivr_demo.phrases.DIGIT_WORDS["hi-IN"].
DIGIT_VARIANTS = {"पांच": 5, "छः": 6, "छे": 6, "छ": 6, "नो": 9, "सुन्य": 0, "शुन्य": 0, "ज़ीरो": 0, "जीरो": 0}


def hindi_digits(text: str) -> list[int]:
    """Digits in order of appearance (Hindi digit words or numerals; numerals map to words in normalise_text)."""
    words = {w: i for i, w in enumerate(DIGIT_WORDS["hi-IN"])} | DIGIT_VARIANTS
    return [words[t] for t in normalise_text(text, "hi-IN").split() if t in words]


def score(expected: str, alt: str, heard: str) -> dict[str, object]:
    refs = [r for r in (expected, alt) if r]
    dist = min(phrase_distance(r, heard, "hi-IN") for r in refs)
    want = hindi_digits(expected)
    return {"distance": round(dist, 3), "match": any(phrase_matches(r, heard, "hi-IN") for r in refs),
            "digits_ok": bool(want) and hindi_digits(heard)[: len(want)] == want}


def answer_wav(path: Path, channel: str) -> bytes:
    """The answer as it arrives over the line: 8 kHz PCM16 WAV bytes."""
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    y = resample(x, sr, 8000) if channel == "none" else apply_condition(x, sr, channel, seed=3)
    buf = io.BytesIO()
    sf.write(buf, (np.clip(y, -1, 1) * 32767).astype("<i2"), 8000, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def cache_key(model: str | None, language: str, audio: bytes) -> str:
    return hashlib.sha256(f"{model}|{language}|".encode() + audio).hexdigest()[:24]


def load_answers(takes: Path, audio_dir: Path, kind: str = "hinglish") -> tuple[list[dict[str, str]], list[str]]:
    with takes.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["kind"] == kind]
    found = [r for r in rows if (audio_dir / f"{r['take']}.wav").is_file()]
    return found, [r["take"] for r in rows if r not in found]


def mock_clients() -> dict[str, GnaniClient]:
    """v2.5 mock hears the expected text, v3.0 mock the alt_text (exercises both references); keyed by audio bytes."""
    lookup: dict[str, dict[bytes, str]] = {"v2.5": {}, "v3.0": {}}
    clients = {}
    for label in MODELS:
        backend = MockGnaniBackend(api_key="mock-key", stt_transcript_fn=lambda audio, lang, m=label: lookup[m].get(audio, ""))
        clients[label] = GnaniClient(api_key="mock-key", transport=backend.transport())
    clients["_lookup"] = lookup  # type: ignore[assignment]
    return clients


def run(answers: list[dict[str, str]], audio_dir: Path, channel: str, language: str, v3_language: str, mock: bool,
        execute: bool, max_calls: int) -> dict[str, object]:
    clips = {r["take"]: answer_wav(audio_dir / f"{r['take']}.wav", channel) for r in answers}
    seconds = sum((len(b) - 44) / 16000 for b in clips.values())
    plan_calls = sum(1 for r in answers for m, lang in ((MODELS["v2.5"], language), (MODELS["v3.0"], v3_language))
                     if mock or not (CACHE / f"{cache_key(m, lang, clips[r['take']])}.json").is_file())
    print(f"{len(answers)} answers, {seconds:.1f} s of 8 kHz audio after the {channel} line; {plan_calls} STT calls needed"
          f" ({'mock, offline' if mock else 'live' if execute else 'dry run, nothing sent'})")
    clients: dict[str, GnaniClient] = {}
    if mock:
        clients = mock_clients()
        lookup = clients.pop("_lookup")  # type: ignore[arg-type]
        for r in answers:
            lookup["v2.5"][clips[r["take"]]] = r["text"]  # type: ignore[index]
            lookup["v3.0"][clips[r["take"]]] = r.get("alt_text") or r["text"]  # type: ignore[index]
    elif execute:
        shared = GnaniClient(ledger_path=LEDGER)  # key from GNANI_API_KEY or .env, never printed
        clients = {label: shared for label in MODELS}
    calls, stopped = 0, ""
    per_take = []
    for r in answers:
        row: dict[str, object] = {"take": r["take"], "expected": r["text"], "alt_text": r.get("alt_text", "")}
        for label, model in MODELS.items():
            lang = v3_language if label == "v3.0" else language
            audio = clips[r["take"]]
            cache = CACHE / f"{cache_key(model, lang, audio)}.json"
            cell: dict[str, object] = {"model_param": model, "language_code": lang}
            raw: dict[str, object] | None = None
            if not mock and cache.is_file():
                raw = json.loads(cache.read_text(encoding="utf-8"))
                cell["cached"] = True
            elif (mock or execute) and not stopped:
                if not mock and calls >= max_calls:
                    stopped = f"cap of {max_calls} calls reached"
                else:
                    calls += 0 if mock else 1
                    try:
                        res = clients[label].stt(audio, lang, format="verbatim", filename=f"{r['take']}_8k.wav", model=model)
                        raw = res.raw
                        if not mock:
                            cache.parent.mkdir(parents=True, exist_ok=True)
                            cache.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
                    except GnaniAPIError as exc:
                        cell["error"] = str(exc)
                        if exc.status_code in FATAL:
                            stopped = f"stopped on HTTP {exc.status_code} ({exc.message})"
            if raw is not None:
                heard = str(raw.get("transcript", ""))
                cell |= {"transcript": heard, "served_by": raw.get("model"), "processing_time": raw.get("processing_time"),
                         "end_to_end_latency": raw.get("end_to_end_latency"), **score(r["text"], r.get("alt_text", ""), heard)}
            row[label] = cell
        per_take.append(row)
    for c in {id(c): c for c in clients.values()}.values():
        c.close()
    summary = {}
    for label, model in MODELS.items():
        cells = [t[label] for t in per_take if "transcript" in t[label]]  # type: ignore[operator]
        served = sorted({str(c.get("served_by")) for c in cells})  # type: ignore[union-attr]
        summary[label] = {"n_scored": len(cells), "match": sum(bool(c["match"]) for c in cells),  # type: ignore[index]
                          "digits_ok": sum(bool(c["digits_ok"]) for c in cells),  # type: ignore[index]
                          "mean_distance": round(float(np.mean([c["distance"] for c in cells])), 3) if cells else None,  # type: ignore[index]
                          "errors": sum("error" in t[label] for t in per_take), "served_by": served}  # type: ignore[operator]
    v3_served = summary["v3.0"]["served_by"]
    void = bool(v3_served) and not mock and not all("v3" in s for s in v3_served)  # type: ignore[union-attr]
    return {"mode": "mock" if mock else "live" if execute else "dry_run", "date": datetime.now(timezone.utc).isoformat(),
            "channel": channel, "language_code": language, "v3_language_code": v3_language, "threshold": 0.25,
            "n_answers": len(answers), "calls_made": calls, "stopped": stopped or None,
            "v3_opt_in_confirmed": None if mock or not v3_served else not void,
            "summary": summary, "per_take": per_take}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--takes", type=Path, default=TAKES)
    ap.add_argument("--audio-dir", type=Path, default=AUDIO, help="prepared 16 kHz takes (scripts/prep_own_voice.py)")
    ap.add_argument("--kind", default="hinglish", help="which takes to test (manifest kind)")
    ap.add_argument("--channel", default="g711u", help="phone channel before STT (factory.channel_sim name, or none)")
    ap.add_argument("--language", default="hi-IN")
    ap.add_argument("--v3-language", default="hi-IN", help="language_code for the v3.0 calls (hi-IN keeps the comparison fair)")
    ap.add_argument("--mock", action="store_true", help="offline mock backend, no key, no credits")
    ap.add_argument("--execute", action="store_true", help="make real (credit-spending) calls")
    ap.add_argument("--max-calls", type=int, default=0, help="hard cap on real calls (required with --execute)")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    if a.execute and a.mock:
        raise SystemExit("--execute and --mock are exclusive")
    if a.execute and a.max_calls <= 0:
        raise SystemExit("--execute requires --max-calls N (a hard cap; 2 per answer)")
    answers, missing = load_answers(a.takes, a.audio_dir, a.kind)
    if missing:
        print(f"WARNING: no prepared audio for {missing} in {a.audio_dir.as_posix()} (run scripts/prep_own_voice.py)")
    if not answers:
        raise SystemExit("no answers to test")
    result = run(answers, a.audio_dir, a.channel, a.language, a.v3_language, a.mock, a.execute, a.max_calls)
    out = a.out or (OUT if result["mode"] == "live" else OUT_MOCK)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for label, s in result["summary"].items():  # type: ignore[union-attr]
        print(f"Prisma {label}: phrase match {s['match']}/{s['n_scored']}, digits right {s['digits_ok']}/{s['n_scored']}, "
              f"mean distance {s['mean_distance']}, errors {s['errors']}, served_by {s['served_by']}")
    if result["v3_opt_in_confirmed"] is False:
        print("WARNING: the v3.0 responses do not report prisma-v3.0: the opt-in did not take effect; do not report a comparison")
    if result["stopped"]:
        print(f"STOPPED: {result['stopped']}")
    print(f"calls made: {result['calls_made']}; written: {out.as_posix()}")


if __name__ == "__main__":
    main()
