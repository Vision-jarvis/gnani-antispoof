from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import norm

from eval.metrics import AffineCalibration, cllr, eer, far_frr, min_cllr, min_dcf, pavx, threshold_at_far
from eval.protocol import ProtocolViolation, assert_protocol


def test_eer_separable_and_identical() -> None:
    assert eer(np.array([2.0, 3.0]), np.array([0.0, 1.0])) == 0.0
    rng = np.random.default_rng(0)
    x = rng.standard_normal(20000)
    assert eer(x[:10000], x[10000:]) == pytest.approx(0.5, abs=0.02)


def test_eer_matches_gaussian_theory() -> None:
    rng = np.random.default_rng(1)
    d = 2.0
    bona, spoof = rng.normal(d, 1, 50000), rng.normal(0, 1, 50000)
    assert eer(bona, spoof) == pytest.approx(norm.cdf(-d / 2), abs=0.005)


def test_eer_brute_force_agreement() -> None:
    rng = np.random.default_rng(2)
    bona, spoof = rng.normal(1, 1, 400), rng.normal(0, 1.5, 300)
    taus = np.sort(np.concatenate([bona, spoof]))
    gaps = [abs(far_frr(bona, spoof, t)[0] - far_frr(bona, spoof, t)[1]) for t in taus]
    t = taus[int(np.argmin(gaps))]
    far, frr = far_frr(bona, spoof, t)
    # The convex hull EER is never worse than the best empirical crossing.
    assert eer(bona, spoof) <= max(far, frr) + 1e-9
    assert eer(bona, spoof) == pytest.approx((far + frr) / 2, abs=0.01)


def test_eer_is_label_direction_sensitive() -> None:
    rng = np.random.default_rng(3)
    bona, spoof = rng.normal(2, 1, 2000), rng.normal(0, 1, 2000)
    assert eer(bona, spoof) < 0.2 < eer(spoof, bona)


def test_min_dcf_bounds_and_definition() -> None:
    rng = np.random.default_rng(4)
    bona, spoof = rng.normal(1, 1, 3000), rng.normal(0, 1, 3000)
    v = min_dcf(bona, spoof)
    assert 0 < v <= 1.0  # accept-all costs exactly 1 after normalisation
    assert min_dcf(np.array([1.0]), np.array([0.0])) == 0.0
    # brute force over a grid
    grid = np.linspace(-5, 6, 4001)
    brute = min((0.95 * far_frr(bona, spoof, t)[1] + 0.5 * far_frr(bona, spoof, t)[0]) / 0.5 for t in grid)
    assert v == pytest.approx(brute, abs=2e-3)


def test_cllr_reference_values() -> None:
    assert cllr(np.zeros(10), np.zeros(10)) == pytest.approx(1.0)
    rng = np.random.default_rng(5)
    bona, spoof = rng.normal(2, 2, 5000), rng.normal(-2, 2, 5000)  # well calibrated Gaussian LLRs
    assert min_cllr(bona, spoof) <= cllr(bona, spoof) + 1e-6
    assert cllr(10 * bona, 10 * spoof) > cllr(bona, spoof)  # overconfidence is penalised


def test_affine_calibration_recovers_scale() -> None:
    rng = np.random.default_rng(6)
    bona, spoof = rng.normal(2, 2, 5000), rng.normal(-2, 2, 5000)
    cal = AffineCalibration.fit(5 * bona + 3, 5 * spoof + 3)
    assert cllr(cal(5 * bona + 3), cal(5 * spoof + 3)) == pytest.approx(cllr(bona, spoof), abs=0.02)


def test_threshold_at_far_is_dev_fixed() -> None:
    rng = np.random.default_rng(7)
    bona, spoof = rng.normal(2, 1, 2000), rng.normal(0, 1, 2000)
    tau = threshold_at_far(bona, spoof, 0.01)
    assert far_frr(bona, spoof, tau)[0] <= 0.01
    assert far_frr(bona, spoof, np.nextafter(tau, -np.inf) - 1e-3)[0] > 0.0095


def test_pavx_monotone() -> None:
    fit, width, _ = pavx(np.array([1.0, 0.0, 0.0, 1.0, 0.0, 1.0, 1.0]))
    assert np.all(np.diff(fit) >= 0) and width.sum() == 7


def _row(attack: str, cond: str, spk: str) -> dict[str, str]:
    return {"attack": attack, "condition": cond, "speaker": spk}


def test_protocol_rejects_test_only_attacks_codecs_and_speaker_overlap() -> None:
    ok_train, ok_eval = [_row("A01", "g711u", "s1")], [_row("G2", "gsm_fr", "s2")]
    assert_protocol(ok_train, ok_eval)
    for bad in (_row("G2", "g711u", "s1"), _row("G6", "g711u", "s1"), _row("A01", "gsm_fr", "s1"),
                _row("A01", "chain_amrnb_g711u", "s1"), _row("A01", "g711u", "s2")):
        with pytest.raises(ProtocolViolation):
            assert_protocol([bad], ok_eval)


def test_eer_ties_are_pessimistic() -> None:
    """A constant (or identically distributed, tied) score carries no information: EER 50%, as in BOSARIS."""
    from eval.metrics import eer

    assert eer(np.zeros(10), np.zeros(7)) == pytest.approx(0.5)
    assert eer(np.array([0.0, 1.0]), np.array([0.0, 1.0])) == pytest.approx(0.5)
