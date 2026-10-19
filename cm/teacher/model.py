"""Teacher CM: wav2vec 2.0 XLS-R 300M front-end + AASIST back-end (Tak et al., Odyssey 2022).

The back-end is the published one, imported unchanged from TakHemlata/SSL_Anti-spoofing (MIT,
cloned into third_party/). Its ``SSLModel`` loads a fairseq checkpoint; here it is replaced by
``HFSSLFrontEnd``, the same XLS-R 300M weights via Hugging Face ``transformers``
(facebook/wav2vec2-xls-r-300m), which avoids the unmaintained fairseq dependency. The interface the
back-end uses (``extract_feat`` returning (B, T, 1024), ``out_dim``) is identical.

8 kHz handling: telephony audio is upsampled to 16 kHz before the front-end (XLS-R was pre-trained
at 16 kHz); the 4 to 8 kHz band is then empty, and fine-tuning on codec-augmented audio teaches the
model not to depend on it.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[2]
SSL_REPO = ROOT / "third_party" / "SSL_Anti-spoofing"
XLSR = "facebook/wav2vec2-xls-r-300m"


class HFSSLFrontEnd(nn.Module):
    def __init__(self, name_or_config: str | object = XLSR) -> None:
        super().__init__()
        from transformers import Wav2Vec2Config, Wav2Vec2Model

        if isinstance(name_or_config, Wav2Vec2Config):
            self.model = Wav2Vec2Model(name_or_config)  # random init (tests, no download)
        else:
            self.model = Wav2Vec2Model.from_pretrained(name_or_config)
        self.out_dim = self.model.config.hidden_size

    def extract_feat(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim == 3:
            x = x[..., 0]
        return self.model(x).last_hidden_state


def build_teacher(front_end: HFSSLFrontEnd | None = None) -> nn.Module:
    """AASIST back-end from the original repo on top of ``front_end`` (default: pretrained XLS-R 300M)."""
    if not SSL_REPO.exists():
        raise FileNotFoundError(f"git clone https://github.com/TakHemlata/SSL_Anti-spoofing {SSL_REPO}")
    sys.modules.setdefault("fairseq", types.ModuleType("fairseq"))  # model.py imports fairseq at top level only for SSLModel
    sys.path.insert(0, str(SSL_REPO))
    import model as ssl_aasist  # type: ignore[import-not-found]

    fe = front_end or HFSSLFrontEnd()
    original = ssl_aasist.SSLModel
    ssl_aasist.SSLModel = lambda device: fe  # the back-end only calls SSLModel(self.device)
    try:
        teacher = ssl_aasist.Model(args=None, device="cpu")
    finally:
        ssl_aasist.SSLModel = original
    return teacher
