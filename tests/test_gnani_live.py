"""Opt-in live checks against the real Gnani API (spend credits). Run with: pytest -m live"""

from __future__ import annotations

import io

import pytest
import soundfile as sf

from gnani_api import AudioConfig, GnaniClient, load_api_key

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(load_api_key() is None, reason="no GNANI_API_KEY in env or .env"),
]


def test_live_tts_then_stt_roundtrip() -> None:
    with GnaniClient() as c:
        wav = c.tts("नमस्ते", "Nalini", language="hi-IN", audio_config=AudioConfig(sample_rate=8000, container="wav"))
        x, sr = sf.read(io.BytesIO(wav))
        assert sr == 8000 and len(x) > 0
        assert c.stt(wav, "hi-IN").transcript.strip() != ""
