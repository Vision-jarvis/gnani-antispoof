"""Indic pilot eval set (a stand-in until Kathbath and the Gnani clones exist).

  bona fide: FLEURS test read speech, Hindi + Kannada (CC-BY-4.0, ungated)
  spoof (G4): IndicSynth FreeVC voice conversion, Hindi + Kannada, first shard each (CC-BY-NC-4.0)
Every clip gets the same normalisation and channel conditions as the ASVspoof eval. Unseen on three
axes for every model here (language, generator, corpus). Known confound: bona fide and spoof come
from different corpora, which is exactly the shortcut the statement warns about (3.4); the shortcut
audit in eval.indic_report quantifies it, and the numbers are labelled a pilot.

Usage: python -m factory.indic_pilot --per-class-per-lang 300
"""

from __future__ import annotations

import argparse
import csv
import io
import tarfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pyloudnorm
import soundfile as sf

from factory.asvspoof import stable_hash
from factory.channel_sim import apply_condition, resample
from factory.normalise import normalise, silence_stats
from factory.store import save_packed

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "proc" / "indic_pilot" / "eval"
CONDITIONS = ("nb_pcm", "g711u", "amrnb_12k2", "amrnb_4k75", "gsm_fr", "chain_amrnb_g711u")
LANGS = {"hi-IN": ("hi_in", "Hindi"), "kn-IN": ("kn_in", "Kannada")}


def fleurs_clips(code: str, n: int) -> list[tuple[str, bytes, str]]:
    with (RAW / "fleurs" / code / "test.tsv").open(encoding="utf-8") as f:
        rows = list(csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE))
    wanted = sorted(rows, key=lambda r: stable_hash(r[1]))[:n]
    names = {f"test/{r[1]}": r for r in wanted}
    out = []
    with tarfile.open(RAW / "fleurs" / code / "test.tar.gz") as tar:
        for m in tar:
            if m.name in names:
                out.append((f"fleurs_{code}_{Path(m.name).stem}", tar.extractfile(m).read(), names[m.name][2]))  # type: ignore[union-attr]
    return out


def indicsynth_clips(lang_name: str, n: int) -> list[tuple[str, bytes, str]]:
    t = pq.read_table(next((RAW / "indicsynth").glob(f"{lang_name}-*.parquet")), columns=["audio", "Target Speaker ID", "TTS Transcript"]).to_pylist()
    t = sorted(t, key=lambda r: stable_hash(r["audio"]["path"]))[:n]
    return [(f"isynth_{lang_name}_{Path(r['audio']['path']).stem}", r["audio"]["bytes"], str(r["Target Speaker ID"])) for r in t]


def _process(args: tuple[str, bytes]) -> tuple[str, dict[str, float], dict[str, np.ndarray]]:
    utt, data = args
    x, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    x = resample(x.mean(axis=1), sr, 16000)
    lead, trail = silence_stats(x, 16000)
    lufs = pyloudnorm.Meter(16000).integrated_loudness(x.astype(np.float64)) if len(x) >= 6400 else np.nan
    y = normalise(x, 16000)
    out = {"clean16k": y} | {c: apply_condition(y, 16000, c, seed=stable_hash(utt) % 2**31) for c in CONDITIONS}
    return utt, {"raw_dur_s": len(x) / 16000, "raw_lead_sil_s": lead, "raw_trail_sil_s": trail, "raw_lufs": lufs}, out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-class-per-lang", type=int, default=300)
    a = ap.parse_args()
    meta, jobs = [], []
    for lang, (code, name) in LANGS.items():
        for utt, data, _text in fleurs_clips(code, a.per_class_per_lang):
            meta.append({"utt_id": utt, "speaker": f"fleurs_{code}", "attack": "bonafide", "label": "bonafide", "language": lang, "corpus": "fleurs"})
            jobs.append((utt, data))
        for utt, data, spk in indicsynth_clips(name, a.per_class_per_lang):
            meta.append({"utt_id": utt, "speaker": f"isynth_{spk}", "attack": "G4", "label": "spoof", "language": lang, "corpus": "indicsynth"})
            jobs.append((utt, data))
    with ProcessPoolExecutor(16) as pool:
        results = {u: (s, o) for u, s, o in pool.map(_process, jobs, chunksize=8)}
    man = pd.DataFrame(meta).merge(pd.DataFrame([{"utt_id": u, **s} for u, (s, _) in results.items()]), on="utt_id")
    OUT.mkdir(parents=True, exist_ok=True)
    man.to_csv(OUT / "manifest.csv", index=False)
    for c in ("clean16k", *CONDITIONS):
        save_packed(OUT / f"{c}.npz", list(man.utt_id), [results[u][1][c] for u in man.utt_id], 16000 if c == "clean16k" else 8000)
    print(man.groupby(["language", "label"]).size())


if __name__ == "__main__":
    main()
