"""Modal job 1 (critique B1): published AASIST, AASIST-L and SSL+AASIST on all 15 conditions + the Indic pilot.

One command, after the one-time setup in ``scripts/modal_setup.sh``:
  modal run cm/modal_pretrained.py --limit 20     # throughput dry run, 20 clips per cell: a few cents
  modal run cm/modal_pretrained.py                # the full job; pulls the scores back into artifacts/scores/
  python -m eval.report && python -m eval.indic_report

Cost (prices checked on modal.com/pricing, 2026-10-20: A10 $1.1016/h, CPU $0.04716/core/h, memory
$0.007992/GiB/h): the job asks for 1 x A10, 4 cores and 16 GiB, i.e. $1.42 per hour. Work: 3 models x
(2,020 dev + 15 x 2,560 eval + 7 x ~1,200 Indic) = about 49k clips per model at a fixed 4 s (64,600 samples).
Measured on this machine's CPU: input preparation 1.7 s per 2,560-clip cell, SSL+AASIST about 1 s per clip
at 4 threads. On the A10 the estimate is 30 to 45 minutes in total, about $0.70 to $1.10; the function
timeout (2 h) caps the worst case at $2.84. ``--limit 20`` measures the real clips/s first; the job prints
wall hours and dollars at the end and writes them to artifacts/scores/pretrained_cost.json.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import modal

GPU, PRICE_PER_H = "A10", 1.1016 + 4 * 0.04716 + 16 * 0.007992
TIMEOUT_H = 2
app = modal.App("gnani-cm-pretrained")
volume = modal.Volume.from_name("gnani-cm-data")
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "git")
    .pip_install("torch==2.5.1", "transformers==4.46.3", "numpy==2.1.3", "scipy", "pandas", "pyarrow", "soundfile",
                 "pyloudnorm", "scikit-learn", "gdown", "webrtcvad-wheels", "tabulate")
    .run_commands(
        "git clone https://github.com/clovaai/aasist /opt/third_party/aasist",
        "git clone https://github.com/TakHemlata/SSL_Anti-spoofing /opt/third_party/SSL_Anti-spoofing",
        "mkdir -p /opt/third_party/ssl_ckpt && python -m gdown 11vFBNKzYUtWqdK358_JEygawFzmmaZjO -O /opt/third_party/ssl_ckpt/LA_model.pth",
    )
    .add_local_dir(".", "/repo", ignore=["data", ".venv", "artifacts", "third_party", ".git", ".env", ".env.*"])  # never ship the key
)


@app.function(gpu=GPU, cpu=4, memory=16384, image=image, volumes={"/vol": volume}, timeout=TIMEOUT_H * 3600)
def score(limit: int = 0) -> float:
    t0 = time.time()
    out = "/vol/artifacts/scores_dryrun" if limit else "/vol/artifacts/scores"
    subprocess.run("mkdir -p /repo/data/proc /repo/artifacts && ln -sfn /opt/third_party /repo/third_party && ln -sfn /vol/asv19 /repo/data/proc/asv19 && "
                   "ln -sfn /vol/indic_pilot /repo/data/proc/indic_pilot", shell=True, check=True)
    cmd = ["python", "-m", "cm.score_pretrained", "--device", "cuda", "--out", out]
    subprocess.run(cmd + (["--limit", str(limit)] if limit else []), cwd="/repo", check=True, env={**os.environ, "CM_THREADS": "4"})
    volume.commit()
    return (time.time() - t0) / 3600


@app.local_entrypoint()
def main(limit: int = 0) -> None:
    hours = score.remote(limit)
    cost = {"gpu": GPU, "wall_hours": round(hours, 3), "usd": round(hours * PRICE_PER_H, 2), "limit": limit}
    print(f"pretrained scoring done: {cost}")
    if not limit:
        for m in ("aasist", "aasist_l", "ssl_aasist"):
            for f in (f"{m}.csv", f"{m}_dev.csv", f"{m}.json", f"indic/{m}.csv"):
                Path(f"artifacts/scores/{f}").parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["modal", "volume", "get", "--force", "gnani-cm-data", f"/artifacts/scores/{f}", f"artifacts/scores/{f}"], check=True)
        Path("artifacts/scores/pretrained_cost.json").write_text(json.dumps(cost, indent=2))
