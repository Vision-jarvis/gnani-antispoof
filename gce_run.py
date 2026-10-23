"""Plain-VM runner (one rented GPU VM, no Modal) for the two GPU jobs.

Runs exactly the commands the Modal functions run (cm/modal_pretrained.py::score and
cm/teacher/modal_train.py::train): `python -m cm.score_pretrained ...` and `python -m cm.teacher.train ...`,
with the same arguments and CM_THREADS, so the numbers are comparable. The only differences are paths:
data sits in data/proc/ of this checkout instead of a Modal volume, and outputs are written straight to
artifacts/ (what the Modal local entrypoints download).

  python gce_run.py score [--limit 20]       # SOTA scoring (Modal job 1); --limit writes artifacts/scores_dryrun
  python gce_run.py teacher [--epochs 1]     # teacher fine-tune + scoring (Modal job 2); resumes finished epochs
  python gce_run.py smoke                    # CPU wiring check: score --limit 2 (AASIST-L, no Indic) + teacher --smoke

Exit code 3 means required data or third_party files are missing (job skipped, not failed).
Never reads .env: neither job needs the Gnani API.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROC = ROOT / "data" / "proc"
TP = ROOT / "third_party"
MISSING = 3
SPLITS = ("train", "dev", "eval")


def _need(paths: list[Path]) -> None:
    gone = [str(p.relative_to(ROOT)) for p in paths if not p.exists()]
    if gone:
        print(f"SKIP: missing {gone}", file=sys.stderr)
        sys.exit(MISSING)


def _run(cmd: list[str], threads: int) -> float:
    t0 = time.time()
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(ROOT), check=True, env={**os.environ, "CM_THREADS": str(threads)})
    return (time.time() - t0) / 3600


def score(limit: int, device: str = "cuda", models: list[str] | None = None, indic: bool = True,
          out: Path | None = None) -> dict:
    _need([PROC / "asv19" / s / "manifest.csv" for s in ("dev", "eval")] + [TP / "aasist" / "models" / "weights" / "AASIST.pth"]
          + ([TP / "ssl_ckpt" / "LA_model.pth"] if not models or "ssl_aasist" in models else []))
    out = out or ROOT / "artifacts" / ("scores_dryrun" if limit else "scores")
    cmd = [sys.executable, "-m", "cm.score_pretrained", "--device", device, "--out", str(out)]
    cmd += ["--limit", str(limit)] if limit else []
    cmd += ["--models", *models] if models else []
    cmd += [] if indic else ["--no-indic"]
    hours = _run(cmd, 4)
    cost = {"host": "gce", "device": device, "wall_hours": round(hours, 3), "limit": limit, "models": models or "all"}
    (out / "pretrained_cost.json").write_text(json.dumps(cost, indent=2))
    return cost


def teacher(epochs: int, out: Path | None = None) -> dict:
    _need([PROC / "asv19" / s / "manifest.csv" for s in SPLITS] + [TP / "SSL_Anti-spoofing", TP / "ssl_ckpt" / "LA_model.pth"])
    out = out or ROOT / "artifacts_teacher_v2"  # v2: LA_model.pth init; never resume the v1 (from-scratch) epochs
    hours = _run([sys.executable, "-m", "cm.teacher.train", "--device", "cuda", "--epochs", str(epochs), "--out", str(out)], 8)
    # Same files the Modal entrypoint downloads, to the same places.
    for f in ("teacher.csv", "teacher_dev.csv", "teacher_train.csv", "teacher.json"):
        shutil.copy2(out / "scores" / f, ROOT / "artifacts" / "scores" / f)
    (ROOT / "artifacts" / "models").mkdir(parents=True, exist_ok=True)
    shutil.copy2(out / "models" / "teacher_ssl_aasist_8k.pt", ROOT / "artifacts" / "models" / "teacher_ssl_aasist_8k.pt")
    cost = {"host": "gce", "epochs_max": epochs, "wall_hours": round(hours, 3)}
    (ROOT / "artifacts" / "scores" / ("teacher_cost.json" if epochs > 1 else "teacher_check_cost.json")).write_text(json.dumps(cost, indent=2))
    return cost


def smoke() -> dict:
    out = ROOT / "artifacts" / "smoke_pretrained"
    shutil.rmtree(out, ignore_errors=True)  # finished parts are reused, so start empty to really score
    res = {"score": score(2, "cpu", ["aasist_l"], indic=False, out=out)}
    shutil.rmtree(ROOT / "artifacts" / "smoke_teacher", ignore_errors=True)  # finished epochs are reused too
    res["teacher_smoke_hours"] = round(_run([sys.executable, "-m", "cm.teacher.train", "--smoke"], 4), 4)
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score")
    s.add_argument("--limit", type=int, default=0)
    t = sub.add_parser("teacher")
    t.add_argument("--epochs", type=int, default=20)
    sub.add_parser("smoke")
    a = ap.parse_args()
    (ROOT / "artifacts" / "scores").mkdir(parents=True, exist_ok=True)
    res = score(a.limit) if a.cmd == "score" else teacher(a.epochs) if a.cmd == "teacher" else smoke()
    print(json.dumps(res))


if __name__ == "__main__":
    main()
