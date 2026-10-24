"""Real-audio trials of the IVR flow at named, dev-fixed operating points (critique B2).

The mock demo's synthetic audio says nothing about accuracy, so this runs the actual ``verify()`` flow on
real clips and reports outcomes per operating point:
  genuine success   share of bona fide trials that end in DecisionCode 0
  attack success    share of spoof trials that end in DecisionCode 0 (the attacker got in)

Sources:
  default        ASVspoof 2019 LA eval clips (English) through a phone channel condition, ``--n`` per class
  --bona-dir/--spoof-dir   folders of 8 kHz WAVs, e.g. the builder's own recordings vs Gnani clones of them

What is and is not measured: the CM gate is real. The phrase check uses an echo STT (the clips do not speak
the challenge phrase), and the identity gate is bypassed because the ASV stand-in is not a speaker verifier
(ECAPA is PENDING), so these numbers are the CM's contribution to the end-to-end KPI, nothing more.
Usage: python -m ivr_demo.trials --conditions g711u amrnb_4k75 --n 200
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf

from cm.scorer import CMScorer
from factory.store import load_packed
from ivr_demo.flow import SR, Challenge, new_challenge, verify

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "proc" / "asv19" / "eval"
OUT = ROOT / "artifacts" / "ivr_trials"
OPERATING_POINTS = ("far1", "min_dcf", "eer")


class BypassASV:
    """Identity gate switched off: every trial is treated as the claimed speaker (reported as such)."""

    threshold = -np.inf

    def embed(self, x8k: np.ndarray) -> np.ndarray:
        return np.zeros(1)

    def score(self, enrol: np.ndarray, test: np.ndarray) -> float:
        return 0.0


def echo_stt(challenge: Challenge):  # noqa: ANN201 - returns an SttFn
    async def run(pcm16: bytes, language: str) -> str:
        await asyncio.sleep(0)
        return challenge.text

    return run


def asvspoof_trials(condition: str, n: int, seed: int, src: Path = PROC) -> list[tuple[str, str, np.ndarray]]:
    man = pd.read_csv(src / "manifest.csv")
    packed = load_packed(src / f"{condition}.npz")
    pos = {str(u): i for i, u in enumerate(packed.utt_ids)}
    rng = np.random.default_rng(seed)
    out = []
    for label in ("bonafide", "spoof"):
        ids = man[man.label == label].utt_id.astype(str).to_numpy()
        for u in rng.choice(ids, size=min(n, len(ids)), replace=False):
            out.append((u, label, packed.get(pos[u])))
    return out


def wav_trials(bona_dir: Path, spoof_dir: Path) -> list[tuple[str, str, np.ndarray]]:
    out = []
    for label, d in (("bonafide", bona_dir), ("spoof", spoof_dir)):
        for p in sorted(d.glob("*.wav")):
            x, sr = sf.read(p, dtype="float32")
            if sr != SR:
                raise SystemExit(f"{p} must be 8 kHz mono")
            out.append((p.stem, label, x if x.ndim == 1 else x.mean(axis=1)))
    return out


def run(trials: list[tuple[str, str, np.ndarray]], source: str, ops: tuple[str, ...], model: str = "lcnn8_aug") -> list[dict[str, object]]:
    asv = BypassASV()
    rows = []
    for op in ops:
        cm = CMScorer.load(model, operating_point=op)
        res = []
        for i, (u, label, x) in enumerate(trials):
            ch = new_challenge("hi-IN", seed=i)
            r = verify(x, ch, asv.embed(x), cm, asv, echo_stt(ch))
            res.append({"utt_id": u, "label": label, "DecisionCode": r.DecisionCode, "reason": r.reason, "latency_ms": r.latency_ms})
        df = pd.DataFrame(res)
        bona, spoof = df[df.label == "bonafide"], df[df.label == "spoof"]
        rows.append({
            "source": source, "operating_point": op, "tau_llr": round(cm.tau, 3),
            "n_bona": len(bona), "n_spoof": len(spoof),
            "genuine_success_pct": round(100 * float((bona.DecisionCode == 0).mean()), 1),
            "attack_success_pct": round(100 * float((spoof.DecisionCode == 0).mean()), 1),
            "short_audio": int((df.reason == "short_audio").sum()),
            "median_latency_ms": float(np.nanmedian(df.latency_ms.astype(float))),
        })
        print(json.dumps(rows[-1]), flush=True)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conditions", nargs="+", default=["g711u", "amrnb_4k75"])
    ap.add_argument("--n", type=int, default=200, help="trials per class per condition")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--operating-points", nargs="+", default=list(OPERATING_POINTS))
    ap.add_argument("--bona-dir", type=Path)
    ap.add_argument("--spoof-dir", type=Path)
    ap.add_argument("--tag", default="asvspoof")
    ap.add_argument("--pack", action="store_true", help="use the committed 60 + 60 clip G.711 pack in release/demo_pack")
    ap.add_argument("--model", default="lcnn8_aug", help="CM checkpoint name in artifacts/models (needs <name>_calibration.json)")
    a = ap.parse_args()
    ops = tuple(a.operating_points)
    if a.pack:
        pack = ROOT / "release" / "demo_pack"
        rows = run(asvspoof_trials("g711u", 60, a.seed, pack), "ASVspoof19 eval g711u (release pack)", ops, a.model)
        a.tag = "pack"
    elif a.bona_dir and a.spoof_dir:
        rows = run(wav_trials(a.bona_dir, a.spoof_dir), f"wav:{a.bona_dir.name} vs {a.spoof_dir.name}", ops, a.model)
    else:
        rows = [r for c in a.conditions for r in run(asvspoof_trials(c, a.n, a.seed), f"ASVspoof19 eval {c}", ops, a.model)]
    if a.model != "lcnn8_aug":
        a.tag = f"{a.tag}_{a.model}"
        for r in rows:
            r["model"] = a.model
    OUT.parent.mkdir(parents=True, exist_ok=True)
    Path(f"{OUT}_{a.tag}.json").write_text(json.dumps(rows, indent=2))
    md = ["# IVR flow on real audio, CM gate only (echo STT, identity gate bypassed)", "",
          "Operating points are fixed on ASVspoof dev scores (`cm.calibrate`); nothing is tuned on these trials.", "",
          pd.DataFrame(rows).to_markdown(index=False)]
    Path(f"{OUT}_{a.tag}.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
