"""LFCC-GMM countermeasure (the ASVspoof 2019 B2 / 2021 B01 recipe, CPU sized).

Two diagonal-covariance GMMs, one on bona fide frames and one on spoof frames. The utterance score is
the mean per-frame log-likelihood ratio log p(x|bona) - log p(x|spoof), so higher = more bona fide.
The official baseline uses 512 components on all frames; here the default is 128 components on a
random subsample of frames so that training fits in a few CPU minutes. The trade-off is reported.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.mixture import GaussianMixture


def _fit_gmm(frames: np.ndarray, n_components: int, seed: int) -> GaussianMixture:
    gmm = GaussianMixture(n_components, covariance_type="diag", max_iter=40, reg_covar=1e-3, random_state=seed)
    return gmm.fit(frames)


def _subsample(feats: Sequence[np.ndarray], max_frames: int, rng: np.random.Generator) -> np.ndarray:
    allf = np.concatenate(feats)
    if len(allf) > max_frames:
        allf = allf[rng.choice(len(allf), max_frames, replace=False)]
    return allf


@dataclass
class LFCCGMM:
    bona: GaussianMixture
    spoof: GaussianMixture

    @classmethod
    def train(
        cls,
        bona_feats: Sequence[np.ndarray],
        spoof_feats: Sequence[np.ndarray],
        n_components: int = 128,
        max_frames: int = 300_000,
        seed: int = 0,
    ) -> LFCCGMM:
        rng = np.random.default_rng(seed)
        return cls(
            bona=_fit_gmm(_subsample(bona_feats, max_frames, rng), n_components, seed),
            spoof=_fit_gmm(_subsample(spoof_feats, max_frames, rng), n_components, seed + 1),
        )

    def score(self, feat: np.ndarray) -> float:
        return float(self.score_many([feat])[0])

    def score_many(self, feats: Sequence[np.ndarray], chunk: int = 200_000) -> np.ndarray:
        """Vectorised: one score_samples pass over all frames, then a per-utterance mean."""
        allf = np.concatenate(feats)
        llr = np.concatenate([self.bona.score_samples(allf[i : i + chunk]) - self.spoof.score_samples(allf[i : i + chunk])
                              for i in range(0, len(allf), chunk)])
        starts = np.concatenate([[0], np.cumsum([len(f) for f in feats])[:-1]])
        return np.add.reduceat(llr, starts) / np.array([len(f) for f in feats])

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        arrays = {}
        for name, g in (("bona", self.bona), ("spoof", self.spoof)):
            arrays |= {f"{name}_w": g.weights_, f"{name}_mu": g.means_, f"{name}_var": g.covariances_}
        np.savez(path, **arrays)

    @classmethod
    def load(cls, path: Path) -> LFCCGMM:
        z = np.load(path)

        def rebuild(name: str) -> GaussianMixture:
            g = GaussianMixture(len(z[f"{name}_w"]), covariance_type="diag")
            g.weights_, g.means_, g.covariances_ = z[f"{name}_w"], z[f"{name}_mu"], z[f"{name}_var"]
            g.precisions_cholesky_ = 1.0 / np.sqrt(g.covariances_)
            return g

        return cls(bona=rebuild("bona"), spoof=rebuild("spoof"))
