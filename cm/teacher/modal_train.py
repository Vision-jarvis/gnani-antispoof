"""Modal job 2 (critique M3): fine-tune the XLS-R 300M + AASIST teacher at 8 kHz, then score dev, every eval
condition x (full, causal 1/2/4 s) and the train pool (soft targets for ``cm.distil``).

One command, after the one-time setup in ``scripts/modal_setup.sh``:
  modal run cm/teacher/modal_train.py --epochs 1      # plumbing check on the GPU: about 25 min, about $1
  modal run cm/teacher/modal_train.py                 # the real run (20 epochs max, early stop patience 4)
  python -m eval.report                               # the teacher appears next to the CPU baselines
  python -m cm.distil                                 # CPU: LCNN student on the teacher's soft targets

Cost (prices checked on modal.com/pricing, 2026-10-20: L40S $1.9512/h, CPU $0.04716/core/h, memory
$0.007992/GiB/h): 1 x L40S, 8 cores, 32 GiB = $2.58 per hour. Work: 10,320 training clips at batch 14 =
737 steps per epoch (1 to 4 s crops, RawBoost on 70%), dev pool 4,040 clips per epoch, then about 91k eval
forwards (14 conditions x 2,560 full clips plus the eligible 1/2/4 s prefixes) and 10,320 train-pool forwards.
Estimate: 5 to 7 min per epoch, early stop after 8 to 15 epochs, plus about 30 min of scoring: 1.5 to 2.5 h,
about $4 to $6.50. The 6 h timeout caps the worst case at $15.50; checkpoints and score parts live on the
volume, so a rerun after a timeout resumes instead of starting over. Wall hours and dollars are printed and
written to artifacts/scores/teacher_cost.json.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import modal

GPU, PRICE_PER_H = "L40S", 1.9512 + 8 * 0.04716 + 32 * 0.007992
TIMEOUT_H = 6
app = modal.App("gnani-telephony-cm-teacher")
volume = modal.Volume.from_name("gnani-cm-data")
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "git")
    .pip_install("torch==2.5.1", "transformers==4.46.3", "numpy==2.1.3", "scipy", "pandas", "pyarrow", "soundfile",
                 "pyloudnorm", "scikit-learn", "webrtcvad-wheels", "tabulate")
    .run_commands("git clone https://github.com/TakHemlata/SSL_Anti-spoofing /opt/third_party/SSL_Anti-spoofing")
    .add_local_dir(".", "/repo", ignore=["data", ".venv", "artifacts", "third_party", ".git", ".env", ".env.*"])  # never ship the key
)


@app.function(gpu=GPU, cpu=8, memory=32768, image=image, volumes={"/vol": volume}, timeout=TIMEOUT_H * 3600)
def train(epochs: int = 20) -> float:
    t0 = time.time()
    subprocess.run("mkdir -p /repo/data/proc /vol/artifacts_teacher && ln -sfn /opt/third_party /repo/third_party && ln -sfn /vol/asv19 /repo/data/proc/asv19", shell=True, check=True)
    subprocess.run(["python", "-m", "cm.teacher.train", "--device", "cuda", "--epochs", str(epochs), "--out", "/vol/artifacts_teacher"],
                   cwd="/repo", check=True, env={**os.environ, "CM_THREADS": "8"})
    volume.commit()
    return (time.time() - t0) / 3600


@app.local_entrypoint()
def main(epochs: int = 20) -> None:
    hours = train.remote(epochs)
    cost = {"gpu": GPU, "epochs_max": epochs, "wall_hours": round(hours, 3), "usd": round(hours * PRICE_PER_H, 2)}
    print(f"teacher done: {cost}")
    for f in ("teacher.csv", "teacher_dev.csv", "teacher_train.csv", "teacher.json"):
        subprocess.run(["modal", "volume", "get", "--force", "gnani-cm-data", f"/artifacts_teacher/scores/{f}", f"artifacts/scores/{f}"], check=True)
    subprocess.run(["modal", "volume", "get", "--force", "gnani-cm-data", "/artifacts_teacher/models/teacher_ssl_aasist_8k.pt",
                    "artifacts/models/teacher_ssl_aasist_8k.pt"], check=True)
    Path("artifacts/scores/teacher_cost.json").write_text(json.dumps(cost, indent=2))
