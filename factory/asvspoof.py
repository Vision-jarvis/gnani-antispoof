"""Build the ASVspoof 2019 LA subsets used by the CPU baselines.

Source: the HF mirror ``Bisher/ASVspoof_2019_LA`` (train 25,380 / dev 24,844 / eval 71,237 rows, the
exact official counts, with speaker and system IDs). The Edinburgh DataShare host refused
connections from this machine; the original licence is ODC-By 1.0.

For every selected utterance:
  raw 16 kHz flac -> shortcut statistics on the RAW audio (silences, loudness, duration)
  -> ``normalise`` (VAD trim + -23 LUFS) -> ``clean16k`` -> every requested channel condition (8 kHz).
Train and dev get ``nb_pcm`` plus ONE seen codec drawn per utterance (codec augmentation); eval gets
every condition (seen and held-out). Selection and codec draws are deterministic hashes of utt_id.

Usage:
  python -m factory.asvspoof --split train --n-bona 2580 --n-spoof-per-attack 430
  python -m factory.asvspoof --split eval --n-bona 1200 --n-spoof-per-attack 150
"""

from __future__ import annotations

import argparse
import hashlib
import io
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pyloudnorm
import soundfile as sf

from factory.channel_sim import CONDITIONS, TRAIN_CONDITIONS, apply_condition
from factory.normalise import normalise, silence_stats
from factory.store import save_packed

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "asvspoof2019_la"
PROC = ROOT / "data" / "proc" / "asv19"
PARQUET = {"train": "train.parquet", "dev": "validation.parquet", "eval": "test.parquet"}
AUG_CONDITIONS = tuple(c for c in TRAIN_CONDITIONS if c != "nb_pcm")


def stable_hash(s: str) -> int:
    return int.from_bytes(hashlib.sha1(s.encode()).digest()[:8], "little")


def select(meta: pd.DataFrame, n_bona: int, n_spoof_per_attack: int) -> pd.DataFrame:
    meta = meta.assign(h=meta.utt_id.map(stable_hash)).sort_values("h")
    parts = [meta[meta.attack == "bonafide"].head(n_bona)]
    parts += [g.head(n_spoof_per_attack) for a, g in meta[meta.attack != "bonafide"].groupby("attack")]
    return pd.concat(parts).drop(columns="h").sort_values("utt_id").reset_index(drop=True)


def read_meta(split: str) -> pd.DataFrame:
    t = pq.read_table(RAW / PARQUET[split], columns=["speaker_id", "audio_file_name", "system_id", "key"]).to_pandas()
    return pd.DataFrame({
        "utt_id": t.audio_file_name,
        "speaker": t.speaker_id,
        "attack": t.system_id.where(t.system_id != "-", "bonafide"),
        "label": np.where(t.key == 0, "bonafide", "spoof"),
    })


def _process(args: tuple[str, bytes, tuple[str, ...]]) -> tuple[str, dict[str, float], dict[str, np.ndarray]]:
    utt_id, flac, conditions = args
    x, sr = sf.read(io.BytesIO(flac), dtype="float32")
    lead, trail = silence_stats(x, sr)
    lufs = pyloudnorm.Meter(sr).integrated_loudness(x.astype(np.float64)) if len(x) >= 0.4 * sr else np.nan
    stats = {"raw_dur_s": len(x) / sr, "raw_lead_sil_s": lead, "raw_trail_sil_s": trail, "raw_lufs": lufs}
    y = normalise(x, sr)
    stats["norm_dur_s"] = len(y) / sr
    out = {"clean16k": y}
    seed = stable_hash(utt_id) % (2**31)
    for c in conditions:
        out[c] = apply_condition(y, sr, c, seed=seed)
    return utt_id, stats, out


def build(split: str, n_bona: int, n_spoof_per_attack: int, workers: int) -> None:
    meta = select(read_meta(split), n_bona, n_spoof_per_attack)
    if split == "eval":
        cond_of = {u: tuple(c for c in CONDITIONS) for u in meta.utt_id}
    else:
        meta["aug_condition"] = [AUG_CONDITIONS[stable_hash(u + "aug") % len(AUG_CONDITIONS)] for u in meta.utt_id]
        cond_of = {u: ("nb_pcm", a) for u, a in zip(meta.utt_id, meta.aug_condition, strict=True)}
    wanted = set(meta.utt_id)
    pf = pq.ParquetFile(RAW / PARQUET[split])
    results: dict[str, tuple[dict[str, float], dict[str, np.ndarray]]] = {}
    t0 = time.time()
    with ProcessPoolExecutor(workers) as pool:
        futures = []
        for rg in range(pf.num_row_groups):
            tbl = pf.read_row_group(rg, columns=["audio_file_name", "audio"]).to_pylist()
            jobs = [(r["audio_file_name"], r["audio"]["bytes"], cond_of[r["audio_file_name"]])
                    for r in tbl if r["audio_file_name"] in wanted]
            futures += [pool.submit(_process, j) for j in jobs]
        for i, f in enumerate(futures):
            u, stats, out = f.result()
            results[u] = (stats, out)
            if (i + 1) % 500 == 0:
                print(f"[{split}] {i + 1}/{len(futures)} utts, {time.time() - t0:.0f}s", flush=True)
    missing = wanted - set(results)
    if missing:
        raise RuntimeError(f"{len(missing)} selected utterances not found in parquet")
    stats_df = pd.DataFrame([{"utt_id": u, **results[u][0]} for u in meta.utt_id])
    meta = meta.merge(stats_df, on="utt_id")
    out_dir = PROC / split
    out_dir.mkdir(parents=True, exist_ok=True)
    meta.to_csv(out_dir / "manifest.csv", index=False)
    all_conds = sorted({c for v in results.values() for c in v[1]})
    for c in all_conds:
        ids = [u for u in meta.utt_id if c in results[u][1]]
        save_packed(out_dir / f"{c}.npz", ids, [results[u][1][c] for u in ids], 16000 if c == "clean16k" else 8000)
    print(f"[{split}] wrote {len(meta)} utts x {len(all_conds)} conditions to {out_dir} in {time.time() - t0:.0f}s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=list(PARQUET), required=True)
    ap.add_argument("--n-bona", type=int, required=True)
    ap.add_argument("--n-spoof-per-attack", type=int, required=True)
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    build(a.split, a.n_bona, a.n_spoof_per_attack, a.workers)


if __name__ == "__main__":
    main()
