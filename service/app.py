"""FastAPI service with the statement's interfaces (section 6).

  POST /v1/cm/score      multipart ``audio`` (WAV, or raw G.711 with ``format=mulaw|alaw``, or AMR)
  WS   /v1/cm/stream     binary 20 ms frames of 8 kHz PCM16 (or mulaw with ?format=mulaw);
                         emits {"t", "llr", "decision"} at 1 s, 2 s and 4 s of received audio
  POST /v1/auth/challenge  {"language"} -> {"session_id", "text"}   (Timbre prompt optional)
  POST /v1/auth/verify   multipart ``audio`` + ``session_id`` + ``speaker_id`` -> Armour365-style codes

Run: uvicorn service.app:app --port 8000   (GNANI_MODE=mock uses the offline mock STT)
"""

from __future__ import annotations

import io
import os
import subprocess
import uuid

import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect

from cm.scorer import HORIZONS_S, SR, CMScorer
from factory.channel_sim import ffmpeg_binary, resample
from gnani_api.g711 import decode_alaw, decode_mulaw
from gnani_api.mock import MockSTTConnect
from ivr_demo.asv import LFCCStatsASV
from ivr_demo.demo import load_cm
from ivr_demo.flow import Challenge, SttFn, new_challenge, prisma_stt, verify

app = FastAPI(title="Telephony anti-spoofing CM", version="0.1.0")
_cm: CMScorer | None = None
_asv = LFCCStatsASV()
_sessions: dict[str, Challenge] = {}
_enrolled: dict[str, np.ndarray] = {}


def cm() -> CMScorer:
    global _cm
    if _cm is None:
        _cm = load_cm()
    return _cm


def stt_fn(expected: str) -> SttFn:
    if os.environ.get("GNANI_MODE", "mock") == "live":
        return prisma_stt()
    # Mock STT echoes the expected phrase: lets the CM and ASV be exercised without credits.
    return prisma_stt(api_key="mock", connect=MockSTTConnect(lambda pcm: expected, api_key="mock"), realtime_pace=False, drain_timeout_s=0.1)


def decode_audio(data: bytes, fmt: str | None) -> np.ndarray:
    """Any supported upload -> 8 kHz mono float32. No metadata other than the audio reaches the CM."""
    if fmt == "mulaw":
        return decode_mulaw(data).astype(np.float32) / 32768.0
    if fmt == "alaw":
        return decode_alaw(data).astype(np.float32) / 32768.0
    if data[:6] == b"#!AMR\n":
        pcm = subprocess.run([ffmpeg_binary(), "-loglevel", "error", "-f", "amr", "-i", "pipe:0", "-f", "s16le", "-ar", str(SR), "-ac", "1", "pipe:1"],
                             input=data, capture_output=True, check=True).stdout
        return np.frombuffer(pcm, "<i2").astype(np.float32) / 32768.0
    try:
        x, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"unsupported audio: {exc}") from exc
    return resample(x.mean(axis=1), sr, SR)


@app.post("/v1/cm/score")
async def cm_score(audio: UploadFile = File(...), format: str | None = Form(None)) -> dict[str, object]:
    x = decode_audio(await audio.read(), format)
    if len(x) < SR:
        raise HTTPException(400, "need at least 1 s of audio")
    return cm().score(x).as_json()


@app.websocket("/v1/cm/stream")
async def cm_stream(ws: WebSocket) -> None:
    await ws.accept()
    mulaw = ws.query_params.get("format") == "mulaw"
    buf = np.zeros(0, np.float32)
    pending = list(HORIZONS_S)
    try:
        while pending:
            data = await ws.receive_bytes()
            frame = decode_mulaw(data) if mulaw else np.frombuffer(data, "<i2")
            buf = np.concatenate([buf, frame.astype(np.float32) / 32768.0])
            while pending and len(buf) >= pending[0] * SR:
                t = pending.pop(0)
                llr = cm().prefix_llr(buf, t)  # same causal path as /v1/cm/score partials: audio up to t only
                await ws.send_json({"t": t, "llr": round(llr, 3), "decision": "bonafide" if llr >= cm().tau else "spoof", "operating_point": cm().operating_point})
        await ws.close()
    except WebSocketDisconnect:
        return


@app.post("/v1/auth/enrol")
async def enrol(speaker_id: str = Form(...), audio: UploadFile = File(...), format: str | None = Form(None)) -> dict[str, object]:
    x = decode_audio(await audio.read(), format)
    if len(x) < 7 * SR:
        return {"StatusCode": 3, "message": "Armour365 needs at least 7 s for enrolment"}
    _enrolled[speaker_id] = _asv.embed(x)
    return {"StatusCode": 0}


@app.post("/v1/auth/challenge")
async def challenge(language: str = Form("kn-IN")) -> dict[str, str]:
    c = new_challenge(language)
    sid = uuid.uuid4().hex
    _sessions[sid] = c
    return {"session_id": sid, "text": c.text, "language": language}


@app.post("/v1/auth/verify")
def auth_verify(session_id: str = Form(...), speaker_id: str = Form(...), audio: UploadFile = File(...),
                      format: str | None = Form(None)) -> dict[str, object]:
    c = _sessions.pop(session_id, None)  # one answer per challenge: no retries on a known phrase
    if c is None:
        raise HTTPException(404, "unknown or used session_id")
    if speaker_id not in _enrolled:
        return {"StatusCode": 6, "DecisionCode": 3, "reason": "no_enrolment"}
    x = decode_audio(audio.file.read(), format)
    # Sync endpoint (runs in FastAPI's thread pool) because verify() drives the STT event loop itself.
    return verify(x, c, _enrolled[speaker_id], cm(), _asv, stt_fn(c.text)).as_json()
