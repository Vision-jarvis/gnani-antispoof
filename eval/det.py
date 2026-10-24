"""DET curves (FRR vs FAR on probit axes) for each model: clean pool vs held-out codec pool.

Usage: python -m eval.det   -> artifacts/det_asvspoof.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import norm  # noqa: E402

from eval.report import EIGHT_K_MODELS, HELDOUT, PROC, SCORES, score_models  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TICKS = [0.001, 0.01, 0.05, 0.2, 0.5]


def det_points(bona: np.ndarray, spoof: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    taus = np.unique(np.concatenate([bona, spoof]))
    far = np.array([np.mean(spoof >= t) for t in taus])
    frr = np.array([np.mean(bona < t) for t in taus])
    eps = 1e-4
    return norm.ppf(np.clip(far, eps, 1 - eps)), norm.ppf(np.clip(frr, eps, 1 - eps))


def main() -> None:
    man = pd.read_csv(PROC / "eval" / "manifest.csv")[["utt_id", "label"]]
    names = score_models()
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharex=True, sharey=True)
    for ax, pool in zip(axes, ("clean", "heldout"), strict=True):
        for n in names:
            df = pd.read_csv(SCORES / f"{n}.csv").merge(man, on="utt_id")
            df = df[df.horizon == 0]
            conds = HELDOUT if pool == "heldout" else ["nb_pcm" if n in EIGHT_K_MODELS else "clean16k"]
            g = df[df.condition.isin(conds)]
            b = g.label.eq("bonafide").to_numpy()
            x, y = det_points(g.score.to_numpy()[b], g.score.to_numpy()[~b])
            ax.plot(x, y, label=n)
        ax.plot(norm.ppf([1e-3, 0.6]), norm.ppf([1e-3, 0.6]), "k:", lw=0.8)
        ax.set_title({"clean": "clean pool (no codec)", "heldout": "held-out codecs (AMR-NB 4.75k, GSM-FR, chains)"}[pool])
        ax.set_xticks(norm.ppf(TICKS), [f"{100 * t:g}" for t in TICKS])
        ax.set_yticks(norm.ppf(TICKS), [f"{100 * t:g}" for t in TICKS])
        ax.set_xlabel("FAR, spoofs accepted (%)")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("FRR, bona fide rejected (%)")
    axes[1].legend(fontsize=8)
    fig.suptitle("DET curves on ASVspoof 2019 LA eval subset (unseen attacks A07 to A19)")
    fig.tight_layout()
    out = ROOT / "artifacts" / "det_asvspoof.png"
    fig.savefig(out, dpi=120)
    print(out)


if __name__ == "__main__":
    main()
