"""Countermeasure metrics, exactly as parameterised in the problem statement (section 7).

Score convention everywhere: higher score = more bona fide. A CM accepts a trial when
score >= tau. Hence FAR(tau) = share of spoofs with score >= tau, FRR(tau) = share of bona fide
with score < tau.

- EER via the ROC convex hull (ROCCH), a port of BOSARIS ``rocch``/``rocch2eer``. Unlike "the
  threshold where FAR and FRR cross", it is well defined for ties and small sets and does not depend
  on threshold interpolation.
- minDCF with pi_spf = 0.05, C_miss = 1, C_fa = 10, normalised by min(C_miss (1 - pi), C_fa pi).
- Cllr / minCllr for natural-log LLR scores (bona fide vs spoof).
- FRR@FAR1: threshold fixed on dev at FAR = 1%, applied unchanged to eval.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

PI_SPF = 0.05
C_MISS = 1.0
C_FA = 10.0
DCF_PARAMS = f"pi_spf={PI_SPF}, C_miss={C_MISS:g}, C_fa={C_FA:g}"


def pavx(y: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pool-adjacent-violators: isotonic (non-decreasing) fit. Returns (fit, block widths, block heights)."""
    n = len(y)
    index = np.zeros(n, dtype=np.int64)
    length = np.zeros(n, dtype=np.int64)
    ghat = np.zeros(n, dtype=np.float64)
    ci = 0
    index[ci], length[ci], ghat[ci] = 0, 1, y[0]
    for j in range(1, n):
        ci += 1
        index[ci], length[ci], ghat[ci] = j, 1, y[j]
        while ci >= 1 and ghat[max(ci - 1, 0)] >= ghat[ci]:
            nw = length[ci - 1] + length[ci]
            ghat[ci - 1] += (length[ci] / nw) * (ghat[ci] - ghat[ci - 1])
            length[ci - 1] = nw
            ci -= 1
    height = ghat[: ci + 1].copy()
    width = length[: ci + 1].copy()
    fit = np.repeat(height, width)
    return fit, width, height


def rocch(bona: np.ndarray, spoof: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(P_miss, P_fa) at the vertices of the ROC convex hull, P_miss ascending."""
    bona, spoof = np.asarray(bona, float), np.asarray(spoof, float)
    nt, nn = len(bona), len(spoof)
    scores = np.concatenate([bona, spoof])
    ideal = np.concatenate([np.ones(nt), np.zeros(nn)])
    # Among tied scores put bona fide first (below the spoofs) so ties are resolved pessimistically,
    # as BOSARIS does (its stable sort keeps targets ahead of non-targets). A constant score gives 50%.
    order = np.lexsort((-ideal, scores))
    ideal = ideal[order]
    _, width, _ = pavx(ideal)
    cum = np.concatenate([[0], np.cumsum(ideal)])
    edges = np.concatenate([[0], np.cumsum(width)])
    miss = cum[edges]  # bona fide below each hull threshold
    fa = nn - (edges - miss)  # spoofs at or above it
    return miss / nt, fa / nn


def eer(bona: np.ndarray, spoof: np.ndarray) -> float:
    """Equal error rate from the ROC convex hull (BOSARIS rocch2eer)."""
    pmiss, pfa = rocch(bona, spoof)
    best = 0.0
    for i in range(len(pfa) - 1):
        xy = np.array([[pfa[i], pmiss[i]], [pfa[i + 1], pmiss[i + 1]]])
        dd = xy[0] - xy[1]
        if np.min(np.abs(dd)) == 0:
            seg = 0.0
        else:
            sol = np.linalg.solve(xy, np.ones(2))
            seg = 1.0 / sol.sum()
        best = max(best, seg)
    return float(best)


def far_frr(bona: np.ndarray, spoof: np.ndarray, tau: float) -> tuple[float, float]:
    return float(np.mean(np.asarray(spoof) >= tau)), float(np.mean(np.asarray(bona) < tau))


def min_dcf(bona: np.ndarray, spoof: np.ndarray, pi_spf: float = PI_SPF, c_miss: float = C_MISS, c_fa: float = C_FA) -> float:
    """min over tau of [C_miss (1 - pi) FRR + C_fa pi FAR] / min(C_miss (1 - pi), C_fa pi)."""
    bona, spoof = np.sort(np.asarray(bona, float)), np.sort(np.asarray(spoof, float))
    taus = np.concatenate([[-np.inf], np.unique(np.concatenate([bona, spoof])), [np.inf]])
    frr = np.searchsorted(bona, taus, side="left") / len(bona)
    far = 1.0 - np.searchsorted(spoof, taus, side="left") / len(spoof)
    cost = c_miss * (1 - pi_spf) * frr + c_fa * pi_spf * far
    return float(cost.min() / min(c_miss * (1 - pi_spf), c_fa * pi_spf))


def cllr(bona_llr: np.ndarray, spoof_llr: np.ndarray) -> float:
    """Log-likelihood-ratio cost (bits) of natural-log LLR scores."""
    c_b = np.mean(np.logaddexp(0, -np.asarray(bona_llr, float))) / np.log(2)
    c_s = np.mean(np.logaddexp(0, np.asarray(spoof_llr, float))) / np.log(2)
    return float(0.5 * (c_b + c_s))


def min_cllr(bona: np.ndarray, spoof: np.ndarray) -> float:
    """Cllr after the optimal monotone (PAV) recalibration: the discrimination-only part of Cllr."""
    nt, nn = len(bona), len(spoof)
    scores = np.concatenate([bona, spoof])
    labels = np.concatenate([np.ones(nt), np.zeros(nn)])
    order = np.lexsort((labels, scores))
    post, _, _ = pavx(labels[order])
    eps = 1e-6
    post = np.clip(post, eps, 1 - eps)
    llr = np.log(post / (1 - post)) - np.log(nt / nn)
    lab = labels[order].astype(bool)
    return cllr(llr[lab], llr[~lab])


def threshold_at_far(bona: np.ndarray, spoof: np.ndarray, target_far: float = 0.01) -> float:
    """Smallest threshold whose FAR on these (dev) scores is at most ``target_far``."""
    s = np.sort(np.asarray(spoof, float))
    k = int(np.floor(target_far * len(s)))  # at most k spoofs may be accepted
    if k >= len(s):
        return -np.inf
    # Accepting the top k spoofs: tau just above the (k+1)-th highest spoof score.
    return float(np.nextafter(s[len(s) - k - 1], np.inf))


@dataclass(frozen=True)
class AffineCalibration:
    """llr = a * score + b, fitted by prior-weighted logistic regression on dev (BOSARIS style)."""

    a: float
    b: float
    prior: float = 0.5

    def __call__(self, scores: np.ndarray) -> np.ndarray:
        return self.a * np.asarray(scores, float) + self.b

    @classmethod
    def fit(cls, bona: np.ndarray, spoof: np.ndarray, prior: float = 0.5) -> AffineCalibration:
        bona, spoof = np.asarray(bona, float), np.asarray(spoof, float)
        logit_prior = np.log(prior / (1 - prior))
        scale = np.std(np.concatenate([bona, spoof])) + 1e-9

        def objective(p: np.ndarray) -> float:
            a, b = p
            lb = a * bona / scale + b + logit_prior
            ls = a * spoof / scale + b + logit_prior
            return prior * np.mean(np.logaddexp(0, -lb)) + (1 - prior) * np.mean(np.logaddexp(0, ls))

        res = minimize(objective, x0=np.array([1.0, 0.0]), method="L-BFGS-B")
        a, b = res.x
        return cls(a=float(a / scale), b=float(b), prior=prior)


@dataclass(frozen=True)
class CMReport:
    n_bona: int
    n_spoof: int
    eer: float
    min_dcf: float
    cllr: float | None = None
    min_cllr: float | None = None
    frr_at_far1: float | None = None
    far_at_dev_tau: float | None = None

    def as_dict(self) -> dict[str, float | int | None]:
        return dict(self.__dict__)


def evaluate(
    bona: np.ndarray, spoof: np.ndarray, *, llr: bool = False, dev_tau_far1: float | None = None
) -> CMReport:
    """All metrics for one pool. ``llr``: scores are calibrated LLRs (enables Cllr)."""
    bona, spoof = np.asarray(bona, float), np.asarray(spoof, float)
    frr1 = far1 = None
    if dev_tau_far1 is not None:
        far1, frr1 = far_frr(bona, spoof, dev_tau_far1)
    return CMReport(
        n_bona=len(bona),
        n_spoof=len(spoof),
        eer=eer(bona, spoof),
        min_dcf=min_dcf(bona, spoof),
        cllr=cllr(bona, spoof) if llr else None,
        min_cllr=min_cllr(bona, spoof) if llr else None,
        frr_at_far1=frr1,
        far_at_dev_tau=far1,
    )
