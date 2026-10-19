"""Speaker verification stand-ins for Armour365 matching (Part C, step 3).

``EcapaASV`` is the intended model (SpeechBrain ECAPA-TDNN, speechbrain/spkrec-ecapa-voxceleb,
Apache-2.0); it needs ``pip install speechbrain`` and a one-time model download, so it is optional.
``LFCCStatsASV`` is a deliberately crude placeholder (cosine similarity of LFCC mean and standard
deviation vectors) that lets the flow run end to end offline. It is NOT a speaker verifier and its
scores must not be reported as ASV results.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from cm.features import LFCCConfig, lfcc

SR = 8000


class ASV(Protocol):
    threshold: float

    def embed(self, x8k: np.ndarray) -> np.ndarray: ...

    def score(self, enrol: np.ndarray, test: np.ndarray) -> float: ...


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


class LFCCStatsASV:
    threshold = 0.9

    def embed(self, x8k: np.ndarray) -> np.ndarray:
        f = lfcc(x8k, LFCCConfig(sr=SR))[:, :20]
        return np.concatenate([f.mean(0), f.std(0)])

    def score(self, enrol: np.ndarray, test: np.ndarray) -> float:
        return cosine(enrol, test)


class EcapaASV:
    """ECAPA-TDNN trained at 16 kHz; 8 kHz input is upsampled (a known mismatch, see UNDERSTAND.md)."""

    threshold = 0.25

    def __init__(self) -> None:
        from speechbrain.inference.speaker import EncoderClassifier  # optional dependency

        self.model = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb")

    def embed(self, x8k: np.ndarray) -> np.ndarray:
        import torch

        from factory.channel_sim import resample

        wav = torch.from_numpy(resample(x8k, SR, 16000))[None]
        return self.model.encode_batch(wav).squeeze().detach().numpy()

    def score(self, enrol: np.ndarray, test: np.ndarray) -> float:
        return cosine(enrol, test)
