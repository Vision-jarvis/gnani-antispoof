"""PENDING (needs a Modal account and about $15 to 25 of GPU): run the teacher fine-tune on one GPU.

One-time setup (student):
  pip install modal && modal setup                      # browser login, creates ~/.modal.toml
  modal volume create gnani-cm-data
  modal volume put gnani-cm-data data/proc/asv19 /asv19 # packed 8 kHz stores built by factory.asvspoof
Run:
  modal run cm/teacher/modal_train.py                   # trains, then pulls scores back below
  modal volume get gnani-cm-data /artifacts/scores artifacts/scores
  python -m eval.report                                 # teacher appears next to the CPU baselines
GPU-hours are printed at the end; record them in REPORT.md (statement rule 8: report GPU-hours).
"""

from __future__ import annotations

import subprocess
import time

import modal

GPU = "L40S"  # A100-40GB also fits; batch 14 x 4 s clips uses about 30 GB with XLS-R 300M
app = modal.App("gnani-telephony-cm-teacher")
volume = modal.Volume.from_name("gnani-cm-data")
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "git")
    .pip_install("torch==2.5.1", "transformers", "numpy", "scipy", "pandas", "pyarrow", "soundfile", "pyloudnorm", "scikit-learn")
    .run_commands("git clone https://github.com/TakHemlata/SSL_Anti-spoofing /repo/third_party/SSL_Anti-spoofing")
    .add_local_dir(".", "/repo", ignore=["data", ".venv", "artifacts", "third_party", ".git", ".env"])  # never ship the key
)


@app.function(gpu=GPU, image=image, volumes={"/vol": volume}, timeout=14 * 3600)
def train(epochs: int = 20) -> float:
    t0 = time.time()
    subprocess.run("mkdir -p /repo/data/proc /repo/artifacts/models /repo/artifacts/scores && "
                   "ln -sfn /vol/asv19 /repo/data/proc/asv19", shell=True, check=True)
    subprocess.run(["python", "-m", "cm.teacher.train", "--device", "cuda", "--epochs", str(epochs)], cwd="/repo", check=True)
    subprocess.run("mkdir -p /vol/artifacts && cp -r /repo/artifacts/scores /repo/artifacts/models /vol/artifacts/", shell=True, check=True)
    volume.commit()
    return (time.time() - t0) / 3600


@app.local_entrypoint()
def main(epochs: int = 20) -> None:
    hours = train.remote(epochs)
    print(f"teacher done: {hours:.2f} GPU-hours on {GPU}")
