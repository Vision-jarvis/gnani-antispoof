"""Teacher training wiring (CPU, offline). Guards the bugs behind the first GPU run's 42 to 45% dev EER:
recipe class weights [0.1, 0.9] on a balanced pool, a random AASIST back end at lr 1e-6, and hub SpecAugment /
LayerDrop left on in the front end."""

from __future__ import annotations

import numpy as np
import pytest
import torch
from torch import nn

from cm.teacher import train as T
from cm.teacher.model import SSL_REPO

needs_repo = pytest.mark.skipif(not SSL_REPO.exists(), reason="third_party/SSL_Anti-spoofing not cloned")


def test_class_weights_follow_the_pool() -> None:
    assert T.class_weights(np.array([0] * 9 + [1])).tolist() == pytest.approx([0.1, 0.9])  # recipe pool (9:1)
    assert T.class_weights(np.array([0, 1] * 50)).tolist() == pytest.approx([0.5, 0.5])  # our balanced subset


def test_default_init_is_the_published_model() -> None:
    """A from-scratch AASIST at lr 1e-6 does not learn within our epoch budget; the default must be a trained init."""
    import inspect

    src = inspect.getsource(T.main)
    assert 'default=str(CKPT)' in src and T.CKPT.name == "LA_model.pth"


def test_front_end_masking_off() -> None:
    from cm.ssl_pretrained import xlsr_300m_config

    cfg = xlsr_300m_config()
    assert cfg.mask_time_prob == 0.0 and cfg.layerdrop == 0.0


@needs_repo
def test_pipeline_feeds_16k_and_overfits_16_clips() -> None:
    """Batches are 16 kHz (1 to 4 s = 16k to 64k samples); the tiny teacher drives loss near zero on 16 clips."""
    torch.manual_seed(0)
    rng = np.random.default_rng(0)
    t = np.arange(16000) / 16000
    bona = [np.sin(2 * np.pi * rng.uniform(200, 400) * t).astype(np.float32) * 0.3 for _ in range(8)]
    spoof = [rng.normal(0, 0.3, 16000).astype(np.float32) for _ in range(8)]
    xs, ys = bona + spoof, np.array([1] * 8 + [0] * 8)
    model = T.build(smoke=True, device="cpu")
    loss_fn = nn.CrossEntropyLoss(weight=T.class_weights(ys))
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    losses = []
    for _ in range(6):
        for x, y in T.batches(xs, ys, 8, rng, augment=False):
            assert 16000 <= x.shape[1] <= 64000
            model.train()
            loss = loss_fn(model(x), y)
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss))
    s = T.score_clips(model, xs, "cpu")
    assert np.mean(losses[-2:]) < 0.2 < losses[0]
    assert s[ys == 1].min() > s[ys == 0].max()  # separable, and score = logit(bona fide) - logit(spoof) has the right sign
