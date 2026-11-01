"""Turn the builder's own recordings into the WAVs the pipeline expects (docs/RECORDING.md).

  python scripts/prep_own_voice.py                                   # every take in data/own_voice/raw
  python scripts/prep_own_voice.py --root data/own_voice/test --subset test   # the 2-minute test recording
  python scripts/prep_own_voice.py --only live_answer                # one take (the live IVR answer)
  python scripts/prep_own_voice.py trialsets                         # takes + cached Gnani clones -> trial folders

``takes`` (the default): input is whatever the recorder saved, named ``<take>.<ext>`` in ``<root>/raw``
(Windows Sound Recorder saves .m4a; .wav .mp3 .aac .flac .ogg .opus .webm .wma .mp4 also work). WAV, FLAC
and OGG are decoded with soundfile, everything else with ffmpeg. Each take becomes mono, VAD-trimmed and
loudness-normalised to -23 LUFS with the repo's own policy (``factory.normalise.normalise``), written as
PCM16 WAV at 16 kHz (``<root>/16k``) and 8 kHz (``<root>/8k``, a resample of the 16 kHz file: the clean 8 kHz
``nb_pcm`` condition). The reference take is also written to ``<root>/builder_15s.wav``, the path
``factory/manifests/demo_builder_voice.csv`` sends to the voice-clone API.
Checks, with an error message and exit code 1: a required take missing, unreadable audio, no speech, or a
duration outside the take's range (the reference must be 5 to 30 s after trimming, as the clone API
requires). Warnings: clipping, a very quiet take, a source below 16 kHz, a duration outside the
recommended range. A summary goes to ``<root>/prep_report.json``.

``trialsets``: genuine takes (kinds answer and hinglish, from ``<root>/16k``) and their text-matched Gnani
clones (from the clone job manifest in artifacts/gnani_cache, or ``--spoof-src DIR`` of stand-in WAVs for a
rehearsal) are each normalised, sent through every ``--conditions`` codec of the channel simulator, and
written as 8 kHz WAVs to ``<root>/trials/<condition>/{bona,spoof}``: the folders ``ivr_demo.trials`` and
``cm.teacher.score_folder`` read.

Everything under data/ and artifacts/gnani_cache/ is git-ignored: no recording or clone is ever committed.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import zlib
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from factory.channel_sim import CONDITIONS, apply_condition, resample  # noqa: E402
from factory.normalise import DEFAULT_POLICY, frame_energy_db, normalise  # noqa: E402
from gnani_api.g711 import decode_mulaw  # noqa: E402

TAKES = ROOT / "factory" / "manifests" / "own_voice_takes.csv"
OWN = ROOT / "data" / "own_voice"
JOBS = ROOT / "artifacts" / "gnani_cache" / "jobs_demo_builder_voice.csv"
AUDIO_EXTS = (".m4a", ".wav", ".mp3", ".aac", ".flac", ".ogg", ".opus", ".webm", ".wma", ".mp4", ".3gp")
SOUNDFILE_EXTS = (".wav", ".flac", ".ogg")
REFERENCE_NAME = "builder_15s"
# kind -> (hard min s, hard max s, recommended min s, recommended max s), durations after VAD trimming
DURATION = {"reference": (5.0, 30.0, 12.0, 20.0), "answer": (1.0, 15.0, 2.0, 8.0), "hinglish": (1.0, 15.0, 2.0, 8.0),
            "enrol": (3.0, 30.0, 6.0, 15.0), "live": (1.0, 15.0, 2.0, 8.0)}
TRIAL_KINDS = ("answer", "hinglish")
DEFAULT_CONDITIONS = ("g711u", "amrnb_4k75")


class PrepError(Exception):
    """A take cannot be used; the message says why and what to do."""


@dataclass
class TakeReport:
    take: str
    kind: str
    source: str
    decoder: str = ""
    source_sr: int = 0
    channels: int = 0
    raw_s: float = 0.0
    trimmed_s: float = 0.0
    noise_floor_dbfs: float = 0.0
    peak_dbfs: float = 0.0
    clipped_pct: float = 0.0
    warnings: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)


def read_takes(path: Path = TAKES) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _ffprobe(path: Path) -> tuple[int, int]:
    """(sample rate, channels) of the first audio stream, (0, 0) if ffprobe is unavailable."""
    exe = shutil.which("ffprobe")
    if exe is None:
        return 0, 0
    out = subprocess.run([exe, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate,channels",
                          "-of", "json", str(path)], capture_output=True, check=False)
    try:
        s = json.loads(out.stdout or b"{}")["streams"][0]
        return int(s["sample_rate"]), int(s["channels"])
    except (KeyError, IndexError, ValueError, json.JSONDecodeError):
        return 0, 0


def load_any(path: Path) -> tuple[np.ndarray, int, dict[str, object]]:
    """Mono float32 audio at its source rate, from any container the recorder may have produced."""
    if path.suffix.lower() in SOUNDFILE_EXTS:
        try:
            x, sr = sf.read(path, dtype="float32", always_2d=True)
            return x.mean(axis=1), int(sr), {"decoder": "soundfile", "source_sr": int(sr), "channels": int(x.shape[1])}
        except (RuntimeError, sf.LibsndfileError):
            pass  # e.g. a WAV with an unusual codec: let ffmpeg try
    exe = shutil.which("ffmpeg")
    if exe is None:
        raise PrepError(f"{path.name}: needs ffmpeg to decode {path.suffix} (winget install Gyan.FFmpeg), or save as WAV")
    sr, ch = _ffprobe(path)
    sr = sr or 48000
    args = [exe, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(path), "-vn", "-f", "f32le", "-acodec", "pcm_f32le",
            "-ar", str(sr)] + (["-ac", "1"] if ch == 0 else [])
    proc = subprocess.run(args + ["-"], capture_output=True, check=False)
    if proc.returncode != 0 or not proc.stdout:
        raise PrepError(f"{path.name}: ffmpeg could not decode it ({proc.stderr.decode(errors='replace')[-300:].strip()})")
    x = np.frombuffer(proc.stdout, dtype="<f4")
    if ch > 1:
        x = x[: len(x) // ch * ch].reshape(-1, ch).mean(axis=1)
    return x.astype(np.float32), sr, {"decoder": "ffmpeg", "source_sr": sr, "channels": ch or 1}


def find_raw(raw_dir: Path, take: str) -> Path | None:
    hits = sorted(p for p in raw_dir.glob(f"{take}.*") if p.suffix.lower() in AUDIO_EXTS)
    if len(hits) > 1:
        raise PrepError(f"{take}: several recordings found ({', '.join(p.name for p in hits)}); keep one")
    return hits[0] if hits else None


def prepare(path: Path, kind: str, take: str, out_root: Path) -> TakeReport:
    """Decode, check and normalise one take; write <out_root>/16k/<take>.wav and <out_root>/8k/<take>.wav."""
    rep = TakeReport(take=take, kind=kind, source=path.name)
    x, sr, info = load_any(path)
    rep.decoder, rep.source_sr, rep.channels = str(info["decoder"]), int(info["source_sr"]), int(info["channels"])
    rep.raw_s = round(len(x) / sr, 2) if sr else 0.0
    if rep.raw_s < 0.5:
        raise PrepError(f"{take}: {rep.raw_s:.2f} s of audio: the file is empty or was cut off; record it again")
    if not np.all(np.isfinite(x)):
        raise PrepError(f"{take}: the decoded audio contains NaN/inf samples; re-save the recording")
    peak = float(np.max(np.abs(x)))
    rep.peak_dbfs = round(20 * np.log10(peak + 1e-12), 1)
    rep.clipped_pct = round(100 * float(np.mean(np.abs(x) >= 0.99)), 3)
    if frame_energy_db(x, sr).max() < -60:
        raise PrepError(f"{take}: no speech found (the loudest 20 ms frame is below -60 dBFS); check the microphone input")
    if rep.clipped_pct > 0.1:
        rep.warnings.append(f"clipping on {rep.clipped_pct}% of samples: lower the input level or move back from the mic")
    if rep.peak_dbfs < -30:
        rep.warnings.append(f"very quiet (peak {rep.peak_dbfs} dBFS): move closer or raise the input level")
    if sr < 16000:
        rep.warnings.append(f"source is {sr} Hz: the 16 kHz output is upsampled; record at 16 kHz or more if you can")
    x16 = resample(x, sr, 16000)
    # Phone and laptop mics leave a hiss floor (about -37 dBFS here) that sits inside the default 40 dB window
    # below the loudest frame, so the default trim keeps seconds of hiss as "speech". Clones from an API are
    # silent there, so that padding would be a duration shortcut. Trim at 10 dB above this take's own noise
    # floor (10th percentile of 20 ms frame energies) instead, never wider than the default window.
    e = frame_energy_db(x16, 16000)
    noise_db = float(np.percentile(e, 10))
    rel_db = float(min(DEFAULT_POLICY.rel_db, max(12.0, e.max() - (noise_db + 10.0))))
    rep.noise_floor_dbfs = round(noise_db, 1)
    y16 = normalise(x16, 16000, replace(DEFAULT_POLICY, rel_db=rel_db, margin_s=0.15))
    rep.trimmed_s = round(len(y16) / 16000, 2)
    lo, hi, rec_lo, rec_hi = DURATION[kind]
    if not lo <= rep.trimmed_s <= hi:
        raise PrepError(f"{take} ({kind}): {rep.trimmed_s:.1f} s of speech after trimming silence; it must be {lo:g} to {hi:g} s"
                        + (" (the voice-clone API takes 5 to 30 s)" if kind == "reference" else ""))
    if not rec_lo <= rep.trimmed_s <= rec_hi:
        rep.warnings.append(f"{rep.trimmed_s:.1f} s of speech; {rec_lo:g} to {rec_hi:g} s is recommended for a {kind} take")
    y8 = resample(y16, 16000, 8000)
    for sub, y, rate in (("16k", y16, 16000), ("8k", y8, 8000)):
        out = out_root / sub / f"{take}.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        sf.write(out, y, rate, subtype="PCM_16")
        rep.outputs.append(out.as_posix())
    if kind == "reference":
        out = out_root / f"{REFERENCE_NAME}.wav"
        sf.write(out, y16, 16000, subtype="PCM_16")
        rep.outputs.append(out.as_posix())
    return rep


def run_takes(root: Path, takes: list[dict[str, str]], only: list[str] | None = None, subset: str | None = None,
              allow_missing: bool = False) -> tuple[list[TakeReport], list[str]]:
    """Prepare every selected take found in <root>/raw; returns (reports, errors)."""
    raw = root / "raw"
    rows = [t for t in takes if (not only or t["take"] in only) and (subset != "test" or t.get("test_subset") == "yes")]
    if only:
        unknown = sorted(set(only) - {t["take"] for t in takes})
        if unknown:
            return [], [f"unknown take name(s) {unknown}; names are listed in factory/manifests/own_voice_takes.csv"]
    reports, errors = [], []
    for t in rows:
        try:
            path = find_raw(raw, t["take"])
        except PrepError as e:
            errors.append(str(e))
            continue
        if path is None:
            optional = t["kind"] == "live" and not only
            if not (optional or allow_missing):
                errors.append(f"{t['take']}: no recording at {raw.as_posix()}/{t['take']}.m4a (or .wav)")
            continue
        try:
            reports.append(prepare(path, t["kind"], t["take"], root))
        except PrepError as e:
            errors.append(str(e))
    return reports, errors


# -- trial sets ------------------------------------------------------------------------------------------------
def _seed(name: str) -> int:
    return zlib.crc32(name.encode())


def _load_clone(path: Path) -> tuple[np.ndarray, int]:
    if path.suffix == ".mulaw":
        return decode_mulaw(path.read_bytes()).astype(np.float32) / 32768.0, 8000
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    return x.mean(axis=1), int(sr)


def clone_sources(jobs_csv: Path, takes: list[dict[str, str]], speaker: str = "builder_self") -> list[tuple[str, str, Path]]:
    """(take, attack, cached audio path) of every finished clone of ``speaker``, matched to its take by text."""
    by_text = {}
    for t in takes:
        for col in ("text", "alt_text"):
            if t.get(col):
                by_text[t[col]] = t["take"]
    out = []
    with jobs_csv.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            p = ROOT / r["path"]
            if r["kind"] == "vc_tts" and r["speaker"] == speaker and p.is_file():
                out.append((by_text.get(r["text"], p.stem), r["attack"], p))
    return out


def build_trialsets(root: Path, takes: list[dict[str, str]], conditions: tuple[str, ...], jobs_csv: Path = JOBS,
                    spoof_src: Path | None = None) -> list[dict[str, str]]:
    """Write <root>/trials/<condition>/{bona,spoof}/*.wav (8 kHz) and <root>/trials/index.csv; returns the index rows."""
    bona = [(t["take"], root / "16k" / f"{t['take']}.wav") for t in takes if t["kind"] in TRIAL_KINDS]
    bona = [(n, p) for n, p in bona if p.is_file()]
    if not bona:
        raise PrepError(f"no prepared genuine takes in {(root / '16k').as_posix()}: run the takes step first")
    if spoof_src is not None:
        spoofs = [(p.stem, "standin", p) for p in sorted(spoof_src.iterdir()) if p.suffix.lower() in AUDIO_EXTS]
    else:
        if not jobs_csv.is_file():
            raise PrepError(f"no clone job manifest at {jobs_csv.as_posix()}: run python -m factory.gnani_clone first")
        spoofs = clone_sources(jobs_csv, takes)
    if not spoofs:
        raise PrepError("no clone audio found (the clone run made no clips yet?)")
    index = []
    for cond in conditions:
        if cond not in CONDITIONS:
            raise PrepError(f"unknown condition {cond!r}; choose from {sorted(CONDITIONS)}")
        for label, items in (("bona", [(n, "bonafide", p) for n, p in bona]), ("spoof", spoofs)):
            d = root / "trials" / cond / label
            d.mkdir(parents=True, exist_ok=True)
            for name, attack, path in items:
                if label == "bona":
                    x, sr = sf.read(path, dtype="float32")
                elif path.suffix.lower() in SOUNDFILE_EXTS + (".mulaw",):
                    x, sr = _load_clone(path)
                else:
                    x, sr, _ = load_any(path)
                x = normalise(x, sr)  # the same policy as the genuine takes, before the line
                y = apply_condition(x, sr, cond, seed=_seed(f"{cond}/{name}"))
                stem = name if label == "bona" else f"clone_{name}"
                out = d / f"{stem}.wav"
                sf.write(out, y, 8000, subtype="PCM_16")
                index.append({"file": out.relative_to(root).as_posix(), "label": "bonafide" if label == "bona" else "spoof",
                              "take": name, "attack": attack, "condition": cond, "source": path.name})
    with (root / "trials" / "index.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(index[0]))
        w.writeheader()
        w.writerows(index)
    return index


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", nargs="?", default="takes", choices=["takes", "trialsets"])
    ap.add_argument("--root", type=Path, default=OWN, help="own-voice folder (raw/ inside it holds the recordings)")
    ap.add_argument("--takes", type=Path, default=TAKES, help="takes manifest")
    ap.add_argument("--only", nargs="+", help="process only these take names")
    ap.add_argument("--subset", choices=["test"], help="only the takes marked test_subset=yes (the 2-minute test recording)")
    ap.add_argument("--allow-missing", action="store_true", help="skip takes that have no recording instead of failing")
    ap.add_argument("--conditions", nargs="+", default=list(DEFAULT_CONDITIONS), help="trialsets: channel conditions")
    ap.add_argument("--jobs", type=Path, default=JOBS, help="trialsets: clone job manifest written by factory.gnani_clone")
    ap.add_argument("--spoof-src", type=Path, help="trialsets: folder of stand-in spoof WAVs (rehearsal) instead of the Gnani cache")
    a = ap.parse_args(argv)
    root = a.root if a.root.is_absolute() else Path.cwd() / a.root
    takes = read_takes(a.takes)
    try:
        if a.step == "trialsets":
            index = build_trialsets(root, takes, tuple(a.conditions), a.jobs, a.spoof_src)
            for cond in a.conditions:
                nb = sum(r["condition"] == cond and r["label"] == "bonafide" for r in index)
                ns = sum(r["condition"] == cond and r["label"] == "spoof" for r in index)
                print(f"{cond}: {nb} genuine + {ns} clone WAVs (8 kHz) in {(root / 'trials' / cond).as_posix()}")
            return 0
        reports, errors = run_takes(root, takes, a.only, a.subset, a.allow_missing)
    except PrepError as e:
        print(f"ERROR: {e}")
        return 1
    for r in reports:
        print(f"{r.take:12s} {r.kind:9s} {r.source:20s} {r.decoder:9s} {r.source_sr:6d} Hz {r.channels} ch  "
              f"raw {r.raw_s:5.1f} s  speech {r.trimmed_s:5.1f} s  peak {r.peak_dbfs:6.1f} dBFS")
        for w in r.warnings:
            print(f"    warning: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    if reports:
        report = {"root": root.as_posix(), "n_prepared": len(reports), "errors": errors, "takes": [asdict(r) for r in reports]}
        (root / "prep_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{len(reports)} take(s) prepared -> {(root / '16k').as_posix()} and {(root / '8k').as_posix()}"
              f"{'; reference -> ' + (root / (REFERENCE_NAME + '.wav')).as_posix() if any(r.kind == 'reference' for r in reports) else ''}")
    if not reports and not errors:
        print(f"nothing to do: no recordings in {(root / 'raw').as_posix()}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
