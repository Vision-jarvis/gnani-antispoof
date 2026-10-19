from __future__ import annotations

import io

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from factory.channel_sim import apply_condition
from gnani_api.g711 import encode_mulaw
from gnani_api.mock import synth_speechlike
from service.app import app

client = TestClient(app)
VOICE = apply_condition(synth_speechlike("svc caller", 16000, 160), 16000, "nb_pcm")


def _wav(x: np.ndarray, sr: int = 8000) -> bytes:
    b = io.BytesIO()
    sf.write(b, x, sr, format="WAV")
    return b.getvalue()


def test_cm_score_wav_and_mulaw_shapes() -> None:
    r = client.post("/v1/cm/score", files={"audio": ("a.wav", _wav(VOICE[:24000]))}).json()
    assert set(r) >= {"llr", "p_spoof", "family", "partial", "rtf"} and [p["t"] for p in r["partial"]] == [1.0, 2.0]
    mu = encode_mulaw((VOICE[:24000] * 32767).astype(np.int16))
    r2 = client.post("/v1/cm/score", files={"audio": ("a.raw", mu)}, data={"format": "mulaw"}).json()
    assert abs(r2["llr"] - r["llr"]) < 0.5  # same audio up to G.711 quantisation


def test_cm_stream_emits_at_horizons() -> None:
    pcm = (VOICE[: 8000 * 5] * 32767).astype("<i2").tobytes()
    with client.websocket_connect("/v1/cm/stream") as ws:
        msgs = []
        for i in range(0, len(pcm), 320):  # 20 ms frames
            ws.send_bytes(pcm[i : i + 320])
            if i in (8000 * 2 - 320, 16000 * 2 - 320, 32000 * 2 - 320):
                msgs.append(ws.receive_json())
    assert [m["t"] for m in msgs] == [1.0, 2.0, 4.0]


def test_auth_flow_codes() -> None:
    assert client.post("/v1/auth/enrol", data={"speaker_id": "u1"}, files={"audio": ("e.wav", _wav(VOICE[:16000]))}).json()["StatusCode"] == 3
    assert client.post("/v1/auth/enrol", data={"speaker_id": "u1"}, files={"audio": ("e.wav", _wav(VOICE))}).json()["StatusCode"] == 0
    sid = client.post("/v1/auth/challenge", data={"language": "hi-IN"}).json()["session_id"]
    r = client.post("/v1/auth/verify", data={"session_id": sid, "speaker_id": "u1"}, files={"audio": ("v.wav", _wav(VOICE[:24000]))}).json()
    assert r["StatusCode"] == 0 and r["DecisionCode"] in (0, 1) and r["phrase_match"] is True
    again = client.post("/v1/auth/verify", data={"session_id": sid, "speaker_id": "u1"}, files={"audio": ("v.wav", _wav(VOICE[:24000]))})
    assert again.status_code == 404  # a challenge can be answered once
