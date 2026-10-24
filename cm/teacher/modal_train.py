"""Modal job 2 (critique M3): fine-tune the XLS-R 300M + AASIST teacher at 8 kHz, then score dev, every eval
condition x (full, causal 1/2/4 s) and the train pool (soft targets for ``cm.distil``).

One command, after the one-time setup in ``scripts/modal_setup.sh``:
  modal run cm/teacher/modal_train.py --epochs 10 --patience 2 --eval full   # cheap first pass (see below)
  modal run cm/teacher/modal_train.py --epochs 10 --patience 2 --eval all    # later: adds the 1/2/4 s cells, reuses epochs
  modal run cm/teacher/modal_train.py                 # the full recipe (20 epochs max, patience 4, every cell)
  python -m eval.report                               # the teacher appears next to the CPU baselines
  python -m cm.distil                                 # CPU: LCNN student on the teacher's soft targets

Starts from the published LA_model.pth (downloaded into the image, as in cm/modal_pretrained.py) and writes to
/vol/artifacts_teacher_v2, so the v1 epochs (random AASIST, did not learn) on the volume are never resumed.

Cost (prices checked on modal.com/pricing, 2026-10-20: L40S $1.9512/h, CPU $0.04716/core/h, memory
$0.007992/GiB/h): 1 x L40S, 8 cores, 32 GiB = $2.58 per hour. Measured on the v1 runs: about 7 min of training
per epoch (737 steps) plus about 2 min of dev scoring (4,040 clips at about 33 clips/s); eval scoring about 18 min
for the 14 full-clip cells and about 26 min more for the 1/2/4 s prefixes; train pool about 5 min; start-up a few
minutes. Corrected run: init dev check 2 min + 4 to 8 epochs x 9 min + final scoring. --eval full with patience
2: about 1.2 to 1.6 h, $3 to $4. --eval none (only what cm.distil needs): about 0.9 to 1.3 h. Full recipe
(patience 4, all cells): about 1.9 to 2.5 h, $5 to $6.50. The 6 h timeout caps the worst case at $15.50;
checkpoints and score parts live on the volume, so a rerun resumes instead of starting over. Wall hours and
dollars are printed and written to artifacts/scores/teacher_cost.json.
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
                 "pyloudnorm", "scikit-learn", "gdown", "webrtcvad-wheels", "tabulate")
    .run_commands(
        "git clone https://github.com/TakHemlata/SSL_Anti-spoofing /opt/third_party/SSL_Anti-spoofing",
        # init checkpoint (published SSL+AASIST LA model), same download as cm/modal_pretrained.py
        "mkdir -p /opt/third_party/ssl_ckpt && python -m gdown 11vFBNKzYUtWqdK358_JEygawFzmmaZjO -O /opt/third_party/ssl_ckpt/LA_model.pth",
    )
    .add_local_dir(".", "/repo", ignore=["data", ".venv", "artifacts", "third_party", ".git", ".env", ".env.*"])  # never ship the key
)


@app.function(gpu=GPU, cpu=8, memory=32768, image=image, volumes={"/vol": volume}, timeout=TIMEOUT_H * 3600)
def train(epochs: int = 20, patience: int = 4, eval: str = "all") -> float:
    t0 = time.time()
    subprocess.run("mkdir -p /repo/data/proc /vol/artifacts_teacher_v2 && ln -sfn /opt/third_party /repo/third_party && ln -sfn /vol/asv19 /repo/data/proc/asv19", shell=True, check=True)
    subprocess.run(["python", "-m", "cm.teacher.train", "--device", "cuda", "--epochs", str(epochs), "--out", "/vol/artifacts_teacher_v2",
                    "--patience", str(patience), "--eval", eval],
                   cwd="/repo", check=True, env={**os.environ, "CM_THREADS": "8"})
    hours = (time.time() - t0) / 3600
    cost = {"gpu": GPU, "epochs_max": epochs, "wall_hours": round(hours, 3), "usd": round(hours * PRICE_PER_H, 2)}
    Path("/vol/artifacts_teacher_v2/teacher_cost.json").write_text(json.dumps(cost, indent=2))
    volume.commit()
    return hours


def _fetch(eval: str) -> None:
    """Copy the teacher's scores, weights and cost from the volume into artifacts/."""
    for f in ("teacher.csv", "teacher_dev.csv", "teacher_train.csv", "teacher.json")[eval == "none":]:
        subprocess.run(["modal", "volume", "get", "--force", "gnani-cm-data", f"/artifacts_teacher_v2/scores/{f}", f"artifacts/scores/{f}"], check=True)
    subprocess.run(["modal", "volume", "get", "--force", "gnani-cm-data", "/artifacts_teacher_v2/models/teacher_ssl_aasist_8k.pt",
                    "artifacts/models/teacher_ssl_aasist_8k.pt"], check=True)
    subprocess.run(["modal", "volume", "get", "--force", "gnani-cm-data", "/artifacts_teacher_v2/teacher_cost.json",
                    "artifacts/scores/teacher_cost.json"], check=True)


@app.local_entrypoint()
def main(epochs: int = 20, patience: int = 4, eval: str = "all", wait: bool = False) -> None:
    """Spawn the training call so it survives a dropped local connection (run with `modal run --detach`).

    Results land on the volume; fetch them later with `modal run cm/teacher/modal_train.py::fetch`.
    `--wait` blocks until done and fetches (only on a stable connection)."""
    call = train.spawn(epochs, patience, eval)
    print(f"teacher spawned: call id {call.object_id}; fetch later with: modal run cm/teacher/modal_train.py::fetch --eval {eval}")
    if wait:
        call.get()
        _fetch(eval)


@app.local_entrypoint()
def fetch(eval: str = "all") -> None:
    _fetch(eval)
    print("teacher artifacts fetched:", Path("artifacts/scores/teacher_cost.json").read_text())
