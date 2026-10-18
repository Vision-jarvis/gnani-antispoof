"""Gnani client against the in-process mock (no network). Live checks live in test_gnani_live.py."""

from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from gnani_api import AudioConfig, GnaniAPIError, GnaniClient, stt_stream
from gnani_api.g711 import decode_alaw, decode_mulaw, encode_alaw, encode_mulaw
from gnani_api.mock import MockGnaniBackend, MockSTTConnect

KEY = "test-key"


@pytest.fixture()
def backend() -> MockGnaniBackend:
    return MockGnaniBackend(api_key=KEY, stt_transcript_fn=lambda audio, lang: f"heard {len(audio)} bytes in {lang}")


@pytest.fixture()
def client(backend: MockGnaniBackend, tmp_path: Path) -> GnaniClient:
    return GnaniClient(api_key=KEY, transport=backend.transport(), ledger_path=tmp_path / "ledger.jsonl")


@pytest.mark.parametrize(("enc", "dec"), [(encode_mulaw, decode_mulaw), (encode_alaw, decode_alaw)])
def test_g711_roundtrip(enc, dec) -> None:  # type: ignore[no-untyped-def]
    x = (np.sin(np.linspace(0, 200, 8000)) * 20000).astype(np.int16)
    y = dec(enc(x))
    rel = np.abs(y.astype(float) - x) / (np.abs(x) + 128)  # A-law decodes 0 to +-8
    assert rel.max() < 0.07  # 8-bit log companding: ~3% step at large amplitudes
    assert enc(y) == enc(x)  # decode then re-encode is the identity on codewords


def test_g711_bit_exact_against_audioop() -> None:
    audioop = pytest.importorskip("audioop")  # stdlib up to Python 3.12
    x = np.arange(-32768, 32768, dtype=np.int16)
    assert encode_mulaw(x) == audioop.lin2ulaw(x.tobytes(), 2)
    assert encode_alaw(x) == audioop.lin2alaw(x.tobytes(), 2)
    codes = bytes(range(256))
    assert decode_mulaw(codes).tobytes() == audioop.ulaw2lin(codes, 2)
    assert decode_alaw(codes).tobytes() == audioop.alaw2lin(codes, 2)


def test_audio_config_validation() -> None:
    with pytest.raises(ValueError, match="alaw"):
        AudioConfig(container="alaw").validate_for_vc()
    with pytest.raises(ValueError):
        AudioConfig(sample_rate=11025).validate_for_tts()
    with pytest.raises(ValueError):
        AudioConfig(container="wav", bitrate="64k").validate_for_tts()
    assert AudioConfig(sample_rate=48000, container="mulaw").effective_sample_rate() == 8000


def test_tts_body_matches_docs_and_decodes(client: GnaniClient, backend: MockGnaniBackend) -> None:
    cfg = AudioConfig(sample_rate=16000, container="wav")
    audio = client.tts("ನನ್ನ ಧ್ವನಿ ನನ್ನ ಗುರುತು", "Saanvi", language="kn-IN", audio_config=cfg)
    body = backend.calls[-1]["json"]
    assert set(body) == {"text", "voice", "model", "language", "speed", "audio_config"}
    assert body["audio_config"] == {"sample_rate": 16000, "num_channels": 1, "sample_width": 2, "encoding": "linear_pcm", "container": "wav"}
    x, sr = sf.read(io.BytesIO(audio))
    assert sr == 16000 and len(x) > 0.5 * sr
    assert client.tts("ನನ್ನ ಧ್ವನಿ ನನ್ನ ಗುರುತು", "Saanvi", language="kn-IN", audio_config=cfg) == audio


def test_tts_mulaw_is_8k_one_byte_per_sample(client: GnaniClient) -> None:
    text = "x" * 50
    audio = client.tts(text, "Nalini", language="hi-IN", audio_config=AudioConfig(sample_rate=48000, container="mulaw"))
    assert len(audio) == int(0.06 * len(text) * 8000)
    assert decode_mulaw(audio).dtype == np.int16


def test_voice_clone_flow(client: GnaniClient, backend: MockGnaniBackend) -> None:
    ref = io.BytesIO()
    sf.write(ref, np.zeros(8000 * 10, dtype=np.int16), 8000, format="WAV")
    emb = client.vc_embedding(ref.getvalue())
    assert emb.shape == (1, 768) and emb.dtype == "torch.bfloat16"
    audio = client.vc_tts("नमस्ते", emb, audio_config=AudioConfig(container="mulaw"))
    assert len(audio) > 0
    assert backend.calls[-1]["json"]["model"] == "vachana-vc-v1"
    assert backend.calls[-1]["json"]["speaker_embedding"]["shape"] == [1, 768]


def test_short_reference_warns(client: GnaniClient) -> None:
    ref = io.BytesIO()
    sf.write(ref, np.zeros(8000 * 2, dtype=np.int16), 8000, format="WAV")
    with pytest.warns(UserWarning, match="5 to 30 s"):
        client.vc_embedding(ref.getvalue())


def test_wrong_key_raises_401(backend: MockGnaniBackend) -> None:
    with GnaniClient(api_key="wrong", transport=backend.transport()) as c, pytest.raises(GnaniAPIError) as err:
        c.tts("hi", "Kaveri", language="en-IN")
    assert err.value.status_code == 401


def test_stt_rest_and_ledger(client: GnaniClient, tmp_path: Path) -> None:
    res = client.stt(b"\x00" * 100, "kn-IN")
    assert res.transcript == "heard 100 bytes in kn-IN" and res.request_id.startswith("mock_")
    rows = [json.loads(line) for line in (tmp_path / "ledger.jsonl").read_text().splitlines()]
    assert rows[-1]["endpoint"] == "/stt/v3" and rows[-1]["status"] == 200
    assert KEY not in (tmp_path / "ledger.jsonl").read_text()


def test_stt_stream_with_mock() -> None:
    sr = 8000
    tone = (0.3 * np.sin(2 * np.pi * 300 * np.arange(int(1.5 * sr)) / sr) * 32767).astype("<i2").tobytes()
    connect = MockSTTConnect(lambda pcm: f"{len(pcm) // 2} samples", api_key=KEY)
    transcripts, delay = asyncio.run(
        stt_stream(tone, language_code="hi-IN", api_key=KEY, connect=connect, realtime_pace=False, drain_timeout_s=0.2)
    )
    assert len(transcripts) == 1
    assert transcripts[0].audio_duration_ms >= 1500
    assert connect.last is not None and set(connect.last.frame_sizes) == {1024}
    assert delay >= 0


def test_stt_stream_rejects_missing_key_header() -> None:
    connect = MockSTTConnect(lambda pcm: "", api_key=KEY)
    with pytest.raises(GnaniAPIError):
        asyncio.run(stt_stream(b"\x01\x00" * 600, language_code="hi-IN", api_key="nope", connect=connect, realtime_pace=False))
