"""Gnani attack generators G1 (Timbre stock voices), G2 (vachana-vc-v1 clones), G3 (born narrowband).

Plan first, spend later. ``plan`` builds every request without calling anything; ``--dry-run`` (the
default) prints call and character counts. Real calls need ``--execute`` AND ``--max-calls N``; the
run stops at the cap. Each request is keyed by the SHA-256 of its JSON body (plus the reference audio
hash for embeddings), and its output is cached under artifacts/gnani_cache/, so a rerun never pays
twice and an interrupted run resumes.

Inputs
  --speakers CSV: speaker,language,reference_wav  (eval-split speakers only; 5 to 30 s reference)
  sentences: FLEURS test transcripts for the language (text-disjoint from the references, CC-BY-4.0)
Per speaker: one embedding call, then ``--per-speaker`` sentences: two thirds as 16 kHz WAV (G2, the
channel simulator is applied later) and one third as container=mulaw (G3; the VC REST doc lists no
alaw, so A-law G3 variants are transcoded from mu-law offline). G1: ``--g1-per-voice`` sentences per
Timbre voice of the language (the same transcripts as the bona fide pool, so text is matched), a third requested as mulaw/alaw (G3, alternating).

Privacy (honesty rule 7): clones of corpus speakers are for scoring only and are never published;
public demo clones use the builder's own voice (speakers CSV with one row pointing at their recording).

Usage
  python -m factory.gnani_clone --speakers factory/manifests/eval_speakers.csv            # dry run
  python -m factory.gnani_clone --speakers ... --execute --max-calls 20                   # capped
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gnani_api import AudioConfig, GnaniClient, SpeakerEmbedding

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "artifacts" / "gnani_cache"
LEDGER = ROOT / "artifacts" / "gnani_usage.jsonl"
FLEURS = ROOT / "data" / "raw" / "fleurs"
FLEURS_CODE = {"hi-IN": "hi_in", "kn-IN": "kn_in", "ta-IN": "ta_in", "bn-IN": "bn_in"}
# Timbre v2.5 voices by preferred language (docs/gnani_api_snapshots/TTS_available-voices.md).
TIMBRE_V25_VOICES = {"hi-IN": ("Nalini", "Deepak", "Chitra", "Vikrant"), "kn-IN": ("Saanvi", "Kavin"),
                     "ta-IN": ("Asmita", "Brinda"), "bn-IN": ("Kirra", "Dhruva")}


@dataclass(frozen=True)
class Job:
    attack: str  # G1 | G2 | G3
    kind: str  # tts | vc_embed | vc_tts
    speaker: str
    language: str
    text: str
    body: dict[str, Any] = field(hash=False)
    reference_wav: str = ""

    @property
    def key(self) -> str:
        blob = json.dumps(self.body, sort_keys=True, ensure_ascii=False) + self.reference_wav
        return hashlib.sha256(blob.encode()).hexdigest()[:24]

    @property
    def out_path(self) -> Path:
        ext = {"wav": "wav", "mulaw": "mulaw", "alaw": "alaw"}.get(self.body.get("audio_config", {}).get("container", ""), "json")
        return CACHE / self.attack / f"{self.key}.{ext}"


def fleurs_sentences(language: str, n: int, offset: int = 0) -> list[str]:
    path = FLEURS / FLEURS_CODE[language] / "test.tsv"
    seen: list[str] = []
    with path.open(encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if row[2] not in seen:
                seen.append(row[2])
    return seen[offset : offset + n]


def plan(speakers: list[dict[str, str]], per_speaker: int, g1_per_voice: int) -> list[Job]:
    jobs: list[Job] = []
    for i, spk in enumerate(speakers):
        lang = spk["language"]
        jobs.append(Job("G2", "vc_embed", spk["speaker"], lang, "", {"endpoint": "embeddings"}, spk["reference_wav"]))
        for j, text in enumerate(fleurs_sentences(lang, per_speaker, offset=i * per_speaker)):
            born_nb = j % 3 == 2
            cfg = AudioConfig(sample_rate=8000, container="mulaw") if born_nb else AudioConfig(sample_rate=16000, container="wav")
            # "speaker" only makes the cache key unique per target; it is not sent to the API.
            body = {"text": text, "model": "vachana-vc-v1", "audio_config": cfg.to_json(), "speaker": spk["speaker"]}
            jobs.append(Job("G3" if born_nb else "G2", "vc_tts", spk["speaker"], lang, text, body, spk["reference_wav"]))
    for lang in sorted({s["language"] for s in speakers}):
        for v, voice in enumerate(TIMBRE_V25_VOICES[lang]):
            for j, text in enumerate(fleurs_sentences(lang, g1_per_voice, offset=v * g1_per_voice)):
                container = ("mulaw", "alaw")[j % 2] if j % 3 == 2 else "wav"
                cfg = AudioConfig(sample_rate=8000 if container != "wav" else 16000, container=container)
                body = {"text": text, "voice": voice, "model": "timbre-v2.5", "language": lang, "speed": 1.0, "audio_config": cfg.to_json()}
                jobs.append(Job("G3" if container != "wav" else "G1", "tts", f"timbre_{voice}", lang, text, body))
    return jobs


def summarise(jobs: list[Job]) -> dict[str, Any]:
    pending = [j for j in jobs if not j.out_path.exists()]
    by: dict[str, dict[str, int]] = {}
    for j in pending:
        d = by.setdefault(f"{j.attack}/{j.kind}", {"calls": 0, "chars": 0})
        d["calls"] += 1
        d["chars"] += len(j.text)
    return {"total_jobs": len(jobs), "cached": len(jobs) - len(pending), "pending_calls": len(pending),
            "pending_chars": sum(len(j.text) for j in pending), "by_type": by}


def _load_embedding(path: Path) -> SpeakerEmbedding:
    d = json.loads(path.read_text())
    return SpeakerEmbedding(embedding=d["embedding"], shape=tuple(d["shape"]), dtype=d["dtype"])


def execute(jobs: list[Job], max_calls: int, client: GnaniClient | None = None) -> int:
    """Run pending jobs in plan order (each embedding precedes its speaker's VC jobs); returns calls made."""
    calls = 0
    embeddings: dict[str, SpeakerEmbedding] = {}
    with client or GnaniClient(ledger_path=LEDGER) as client:
        for job in jobs:
            if job.kind == "vc_embed" and job.out_path.exists():
                embeddings[job.speaker] = _load_embedding(job.out_path)
            if job.out_path.exists():
                continue
            if calls >= max_calls:
                print(f"cap of {max_calls} calls reached; rerun to continue (cached outputs are kept)")
                break
            job.out_path.parent.mkdir(parents=True, exist_ok=True)
            if job.kind == "vc_embed":
                emb = client.vc_embedding(Path(job.reference_wav).read_bytes())
                job.out_path.write_text(json.dumps(emb.to_json()))
                embeddings[job.speaker] = emb
            elif job.kind == "vc_tts":
                cfg = AudioConfig(**job.body["audio_config"])
                job.out_path.write_bytes(client.vc_tts(job.text, embeddings[job.speaker], audio_config=cfg))
            else:
                b = job.body
                job.out_path.write_bytes(client.tts(b["text"], b["voice"], model=b["model"], language=b["language"],
                                                    audio_config=AudioConfig(**b["audio_config"])))
            calls += 1
    return calls


def write_manifest(jobs: list[Job], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["attack", "kind", "speaker", "language", "text", "path", "done"])
        for j in jobs:
            w.writerow([j.attack, j.kind, j.speaker, j.language, j.text, j.out_path.relative_to(ROOT).as_posix(), j.out_path.exists()])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--speakers", type=Path, required=True)
    ap.add_argument("--per-speaker", type=int, default=15)
    ap.add_argument("--g1-per-voice", type=int, default=40)
    ap.add_argument("--execute", action="store_true", help="make real (credit-spending) calls")
    ap.add_argument("--max-calls", type=int, default=0, help="hard cap on real calls in this run (required with --execute)")
    a = ap.parse_args()
    with a.speakers.open(encoding="utf-8") as f:
        speakers = list(csv.DictReader(f))
    jobs = plan(speakers, a.per_speaker, a.g1_per_voice)
    print(json.dumps(summarise(jobs), indent=2, ensure_ascii=False))
    write_manifest(jobs, ROOT / "factory" / "manifests" / "gnani_jobs.csv")
    if not a.execute:
        print("dry run only: nothing was sent. Add --execute --max-calls N to spend credits.")
        return
    if a.max_calls <= 0:
        raise SystemExit("--execute requires --max-calls N (a hard cap)")
    print(f"made {execute(jobs, a.max_calls)} calls")
    write_manifest(jobs, ROOT / "factory" / "manifests" / "gnani_jobs.csv")


if __name__ == "__main__":
    main()
