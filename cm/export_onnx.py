"""Export the 8 kHz LCNN to ONNX and measure the statement's student budget on ONE CPU core.

Budget (section 6): RTF <= 0.05 on one laptop core at 8 kHz input, peak RAM <= 200 MB, < 5M params.
RTF covers the whole runtime path (LFCC in numpy + ONNX Runtime inference, intra-op threads = 1)
on a 4 s clip, median of 50 runs. Peak RAM is the peak working set of a fresh process that loads the
model and scores, measured in a subprocess so the exporter's own torch import does not count.

The LCNN is a stand-in for the distilled student (Part B) until the GPU teacher exists; the same
script exports and measures the real student later via --checkpoint.
Usage: python -m cm.export_onnx [--checkpoint artifacts/models/lcnn8_aug.pt]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ONNX_PATH = ROOT / "artifacts" / "models" / "cm_student.onnx"
OUT = ROOT / "artifacts" / "efficiency.json"

_MEASURE = r"""
import json, sys, time, numpy as np, onnxruntime as ort, psutil
sys.path.insert(0, sys.argv[2])
from cm.features import LFCCConfig, lfcc
so = ort.SessionOptions(); so.intra_op_num_threads = 1; so.inter_op_num_threads = 1
sess = ort.InferenceSession(sys.argv[1], so, providers=["CPUExecutionProvider"])
x = (0.1 * np.random.default_rng(0).standard_normal(4 * 8000)).astype(np.float32)
cfg = LFCCConfig(sr=8000)
times = []
for _ in range(50):
    t0 = time.perf_counter(); f = lfcc(x, cfg)[None]; sess.run(None, {"lfcc": f}); times.append(time.perf_counter() - t0)
print(json.dumps({"rtf_1core": float(np.median(times)) / 4.0, "peak_ram_mb": psutil.Process().memory_info().peak_wset / 2**20}))
"""


def export(checkpoint: Path) -> int:
    import torch

    from cm.lcnn import LCNN, n_params

    torch.set_num_threads(1)
    model = LCNN()
    model.load_state_dict(torch.load(checkpoint, map_location="cpu"))
    model.eval()
    dummy = torch.randn(1, 400, 60)
    ONNX_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(model, (dummy,), ONNX_PATH, input_names=["lfcc"], output_names=["logit"],
                      dynamic_axes={"lfcc": {0: "batch", 1: "frames"}, "logit": {0: "batch"}}, opset_version=17, dynamo=False)
    import onnxruntime as ort

    sess = ort.InferenceSession(str(ONNX_PATH), providers=["CPUExecutionProvider"])
    for frames in (101, 400):
        x = torch.randn(1, frames, 60)
        with torch.no_grad():
            ref = float(model(x))
        got = float(sess.run(None, {"lfcc": x.numpy()})[0][0])
        assert abs(ref - got) < 1e-3, f"ONNX mismatch at {frames} frames: {ref} vs {got}"
    return n_params(model)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", type=Path, default=ROOT / "artifacts" / "models" / "lcnn8_aug.pt")
    a = ap.parse_args()
    params = export(a.checkpoint)
    t0 = time.time()
    res = subprocess.run([sys.executable, "-c", _MEASURE, str(ONNX_PATH), str(ROOT)], capture_output=True, text=True, check=True)
    m = json.loads(res.stdout.strip().splitlines()[-1])
    out = {"model": a.checkpoint.stem, "params": params, "onnx_bytes": ONNX_PATH.stat().st_size, **m,
           "measured_on": "this machine, 1 thread, 4 s clip, median of 50", "measure_seconds": round(time.time() - t0, 1)}
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
