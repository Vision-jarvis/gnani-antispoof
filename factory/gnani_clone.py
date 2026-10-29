"""Gnani attack generators G1 (Timbre stock voices), G2 (vachana-vc-v1 clones), G3 (born narrowband).

Plan first, spend later. ``plan`` builds every request without calling anything; ``--dry-run`` (the
default) prints call and character counts. Real calls need ``--execute`` AND ``--max-calls N``; the
run stops at the cap. Each request is keyed by the SHA-256 of its JSON body plus, for clone jobs, the
reference path and the SHA-256 of the reference audio bytes (so a re-recorded reference never reuses a
stale embedding), and its output is cached under artifacts/gnani_cache/, so a rerun never pays twice and
an interrupted run resumes.

Inputs
  --speakers CSV: speaker,language,reference_wav,consent[,texts]  (5 to 30 s reference). ``consent`` must be
      ``self`` (the builder's own voice) or ``written`` (a friend who signed a consent note); any other row is
      refused before planning. Cloning corpus speakers (Kathbath) is DEFERRED until Gnani confirms in writing
      that it is allowed: corpus licences cover the audio, not the person's voice likeness (critique B4).
      Optional ``texts``: a takes manifest (``factory/manifests/own_voice_takes.csv``); the clone then says
      exactly the rows marked ``clone=yes`` (the builder's genuine IVR answers), so real and clone are
      text-matched and duration-comparable. Without it, FLEURS test transcripts are used.
  --languages kn-IN hi-IN: G1/G3 from Timbre stock voices only (no cloning, no consent question). G1 is
      planned ONLY for languages given here, never implicitly for a speaker's language.
  sentences: FLEURS test transcripts for the language (text-disjoint from the references, CC-BY-4.0)
Per speaker: one embedding call, then ``--per-speaker`` sentences: two thirds as 16 kHz WAV (G2, the
channel simulator is applied later) and one third as container=mulaw (G3; the VC REST doc lists no
alaw, so A-law G3 variants are transcoded from mu-law offline). G1: ``--g1-per-voice`` sentences per
Timbre voice of the language (the same transcripts as the bona fide pool, so text is matched), a third requested as mulaw/alaw (G3, alternating).

Privacy (honesty rule 7): no cloned clip is ever published or committed. Every output of this script
(audio, embeddings, the job manifest ``artifacts/gnani_cache/jobs_<tag>.csv``, the call ledger) lands in
git-ignored paths; only scores and this script are committed.

Credits: the API returns no usage data and the price per call or character is not published
(docs/gnani_api_notes.md), so the plan prints calls and characters only; read the balance on
app.gnani.ai before and after a run.

Usage
  python -m factory.gnani_clone --speakers factory/manifests/demo_builder_voice.csv        # own voice, dry run (16 calls)
  python -m factory.gnani_clone --speakers factory/manifests/demo_builder_voice.csv --execute --max-calls 16
  python -m factory.gnani_clone --languages kn-IN hi-IN                                   # G1/G3 dry run (240 calls)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gnani_api import AudioConfig, GnaniClient, SpeakerEmbedding
from gnani_api.schemas import GnaniAPIError

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "artifacts" / "gnani_cache"
LEDGER = ROOT / "artifacts" / "gnani_usage.jsonl"
FLEURS = ROOT / "data" / "raw" / "fleurs"
FLEURS_CODE = {"hi-IN": "hi_in", "kn-IN": "kn_in", "ta-IN": "ta_in", "bn-IN": "bn_in"}
# Timbre v2.5 voices by preferred language (docs/gnani_api_snapshots/TTS_available-voices.md).
TIMBRE_V25_VOICES = {"hi-IN": ("Nalini", "Deepak", "Chitra", "Vikrant"), "kn-IN": ("Saanvi", "Kavin"),
                     "ta-IN": ("Asmita", "Brinda"), "bn-IN": ("Kirra", "Dhruva")}
REF_MIN_S, REF_MAX_S = 5.0, 30.0  # voice-clone embeddings: 5 to 30 s of reference audio (VC docs)


@dataclass(frozen=True)
class Job:
    attack: str  # G1 | G2 | G3
    kind: str  # tts | vc_embed | vc_tts
    speaker: str
    language: str
    text: str
    body: dict[str, Any] = field(hash=False)
    reference_wav: str = ""
    reference_sha: str = ""  # SHA-256 of the reference audio bytes ("" if not recorded yet)

    @property
    def key(self) -> str:
        blob = json.dumps(self.body, sort_keys=True, ensure_ascii=False) + self.reference_wav + self.reference_sha
        return hashlib.sha256(blob.encode()).hexdigest()[:24]

    @property
    def out_path(self) -> Path:
        ext = {"wav": "wav", "mulaw": "mulaw", "alaw": "alaw"}.get(self.body.get("audio_config", {}).get("container", ""), "json")
        return CACHE / self.attack / f"{self.key}.{ext}"


def resolve(path: str | Path) -> Path:
    """Repo-relative paths in manifests resolve against the repo root, whatever the working directory."""
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def reference_sha(path: str | Path) -> str:
    p = resolve(path)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else ""


def fleurs_sentences(language: str, n: int, offset: int = 0) -> list[str]:
    path = FLEURS / FLEURS_CODE[language] / "test.tsv"
    seen: list[str] = []
    with path.open(encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if row[2] not in seen:
                seen.append(row[2])
    return seen[offset : offset + n]


def manifest_texts(path: str | Path, alt: bool = False) -> list[str]:
    """Texts the clone says: rows of a takes manifest with ``clone=yes``, in file order (``alt_text`` if asked and set)."""
    with resolve(path).open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("clone", "").strip().lower() == "yes"]
    return [(r.get("alt_text") or r["text"]) if alt else r["text"] for r in rows]


CONSENT_OK = {"self", "written"}


def check_consent(speakers: list[dict[str, str]]) -> None:
    bad = [s.get("speaker", "?") for s in speakers if s.get("consent", "").strip().lower() not in CONSENT_OK]
    if bad:
        raise SystemExit(f"refusing to clone {bad}: consent must be 'self' or 'written' (corpus speakers are DEFERRED)")


def embed_job(spk: dict[str, str]) -> Job:
    """The embedding request of one speaker (its cache file is what the live IVR demo reuses for the clone)."""
    return Job("G2", "vc_embed", spk["speaker"], spk["language"], "", {"endpoint": "embeddings"}, spk["reference_wav"],
               reference_sha(spk["reference_wav"]))


def plan(speakers: list[dict[str, str]], per_speaker: int, g1_per_voice: int, languages: tuple[str, ...] = (),
         alt_text: bool = False) -> list[Job]:
    check_consent(speakers)
    jobs: list[Job] = []
    for i, spk in enumerate(speakers):
        lang = spk["language"]
        emb = embed_job(spk)
        jobs.append(emb)
        texts = (manifest_texts(spk["texts"], alt_text)[:per_speaker] if spk.get("texts")
                 else fleurs_sentences(lang, per_speaker, offset=i * per_speaker))
        for j, text in enumerate(texts):
            born_nb = j % 3 == 2
            cfg = AudioConfig(sample_rate=8000, container="mulaw") if born_nb else AudioConfig(sample_rate=16000, container="wav")
            # "speaker" only makes the cache key unique per target; it is not sent to the API.
            body = {"text": text, "model": "vachana-vc-v1", "audio_config": cfg.to_json(), "speaker": spk["speaker"]}
            jobs.append(Job("G3" if born_nb else "G2", "vc_tts", spk["speaker"], lang, text, body, spk["reference_wav"],
                            emb.reference_sha))
    for lang in sorted(set(languages)):
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


def reference_problems(speakers: list[dict[str, str]]) -> list[str]:
    """Why a speaker's reference cannot be sent yet (missing file, unreadable, outside 5 to 30 s); empty if fine."""
    import soundfile as sf

    out = []
    for spk in speakers:
        p = resolve(spk["reference_wav"])
        if not p.is_file():
            out.append(f"{spk['speaker']}: reference not recorded yet ({spk['reference_wav']}); see docs/RECORDING.md")
            continue
        try:
            info = sf.info(p)
        except (RuntimeError, sf.LibsndfileError) as exc:
            out.append(f"{spk['speaker']}: {spk['reference_wav']} is not a readable WAV ({exc}); run scripts/prep_own_voice.py")
            continue
        dur = info.frames / info.samplerate
        if not REF_MIN_S <= dur <= REF_MAX_S:
            out.append(f"{spk['speaker']}: reference is {dur:.1f} s, the API needs {REF_MIN_S:.0f} to {REF_MAX_S:.0f} s")
    return out


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
            calls += 1  # counted before the request: a failed request may still be billed
            if job.kind == "vc_embed":
                emb = client.vc_embedding(resolve(job.reference_wav).read_bytes())
                job.out_path.write_text(json.dumps(emb.to_json()))
                embeddings[job.speaker] = emb
            elif job.kind == "vc_tts":
                cfg = AudioConfig(**job.body["audio_config"])
                job.out_path.write_bytes(client.vc_tts(job.text, embeddings[job.speaker], audio_config=cfg))
            else:
                b = job.body
                job.out_path.write_bytes(client.tts(b["text"], b["voice"], model=b["model"], language=b["language"],
                                                    audio_config=AudioConfig(**b["audio_config"])))
    return calls


def manifest_path(speakers_csv: Path | None, languages: list[str]) -> Path:
    tag = "_".join(([speakers_csv.stem] if speakers_csv else []) + (["g1"] + sorted(languages) if languages else []))
    return CACHE / f"jobs_{tag}.csv"


def write_manifest(jobs: list[Job], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["attack", "kind", "speaker", "language", "text", "path", "done"])
        for j in jobs:
            w.writerow([j.attack, j.kind, j.speaker, j.language, j.text, j.out_path.relative_to(ROOT).as_posix(), j.out_path.exists()])


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # Hindi / Kannada texts on a Windows console
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--speakers", type=Path, help="consented speakers CSV (G2/G3 clones)")
    ap.add_argument("--languages", nargs="*", default=[], help="Timbre stock-voice languages (G1/G3, no cloning)")
    ap.add_argument("--per-speaker", type=int, default=15)
    ap.add_argument("--g1-per-voice", type=int, default=40)
    ap.add_argument("--alt-text", action="store_true", help="clone texts: use the manifest's alt_text (English words in Devanagari)")
    ap.add_argument("--execute", action="store_true", help="make real (credit-spending) calls")
    ap.add_argument("--max-calls", type=int, default=0, help="hard cap on real calls in this run (required with --execute)")
    a = ap.parse_args()
    speakers: list[dict[str, str]] = []
    if a.speakers:
        with resolve(a.speakers).open(encoding="utf-8") as f:
            speakers = list(csv.DictReader(f))
    if not speakers and not a.languages:
        raise SystemExit("give --speakers (consented) and/or --languages")
    jobs = plan(speakers, a.per_speaker, a.g1_per_voice, tuple(a.languages), a.alt_text)
    summary = summarise(jobs)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"credits: not computable here (the API returns no usage; price per call/char is unpublished). "
          f"Read the balance on app.gnani.ai before and after. This run: {summary['pending_calls']} calls, "
          f"{summary['pending_chars']} characters of text.")
    out = manifest_path(a.speakers, a.languages)
    write_manifest(jobs, out)
    print(f"job manifest (git-ignored): {out.relative_to(ROOT).as_posix()}")
    problems = reference_problems(speakers)
    for p in problems:
        print(f"WARNING: {p}")
    if not a.execute:
        print("dry run only: nothing was sent. Add --execute --max-calls N to spend credits.")
        return
    if a.max_calls <= 0:
        raise SystemExit("--execute requires --max-calls N (a hard cap)")
    if problems:
        raise SystemExit("not sending anything: fix the reference problems above first")
    before = summary["pending_calls"]
    try:
        execute(jobs, a.max_calls)
    except (GnaniAPIError, OSError) as exc:  # a failed call stops the run; cached outputs are kept
        write_manifest(jobs, out)
        made = before - summarise(jobs)["pending_calls"]
        raise SystemExit(f"stopped after {made} successful calls: {type(exc).__name__}: {exc}. "
                         "Cached outputs are kept; fix the cause and rerun the same command to resume.") from None
    write_manifest(jobs, out)
    print(f"made {before - summarise(jobs)['pending_calls']} calls")


if __name__ == "__main__":
    main()
