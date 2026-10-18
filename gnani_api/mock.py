"""In-process mock of the Gnani endpoints, following the documented request and response shapes.

``MockGnaniBackend.transport()`` plugs into ``GnaniClient(transport=...)``; ``mock_stt_connect``
replaces ``websockets.connect`` in ``stt_stream``. No network is touched. The synthetic "speech"
is a deterministic harmonic signal, enough to exercise codecs, the CM and the flow plumbing.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
from collections.abc import Callable
from datetime import datetime, timezone
from email.parser import BytesParser
from email.policy import HTTP
from typing import Any

import httpx
import numpy as np
import soundfile as sf

from gnani_api.g711 import encode_alaw, encode_mulaw
from gnani_api.schemas import AUTH_HEADER, STT_PATH, STT_WS_FRAME_BYTES, TTS_PATH, VC_EMBED_PATH, GnaniAPIError

_CONTENT_TYPES = {"wav": "audio/wav", "raw": "application/octet-stream", "mulaw": "audio/basic", "alaw": "audio/alaw"}


def synth_speechlike(seed_text: str, sr: int, n_chars: int) -> np.ndarray:
    """Deterministic voiced-speech-like signal: harmonics on a drifting f0 with a syllabic envelope."""
    rng = np.random.default_rng(int.from_bytes(hashlib.sha256(seed_text.encode()).digest()[:8], "little"))
    dur = float(np.clip(0.06 * n_chars, 0.5, 15.0))
    t = np.arange(int(dur * sr)) / sr
    f0 = rng.uniform(120, 220) * (1 + 0.1 * np.sin(2 * np.pi * rng.uniform(0.5, 2.0) * t))
    phase = 2 * np.pi * np.cumsum(f0) / sr
    x = sum((0.6 / k) * np.sin(k * phase) for k in range(1, int(0.45 * sr / 220)))
    env = 0.5 * (1 - np.cos(2 * np.pi * rng.uniform(3, 5) * t)) * np.minimum(1.0, 10 * t) * np.minimum(1.0, 10 * (dur - t))
    y = env * np.asarray(x) + 0.003 * rng.standard_normal(len(t))
    return (0.3 * y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32)


def _encode(x: np.ndarray, sr: int, container: str) -> bytes:
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    if container == "wav":
        buf = io.BytesIO()
        sf.write(buf, pcm, sr, format="WAV", subtype="PCM_16")
        return buf.getvalue()
    if container == "raw":
        return pcm.tobytes()
    return encode_mulaw(pcm) if container == "mulaw" else encode_alaw(pcm)


def _json_error(status: int, err_type: str, message: str) -> httpx.Response:
    return httpx.Response(status, json={"success": False, "error": {"type": err_type, "message": message}})


def parse_multipart(request: httpx.Request) -> dict[str, bytes]:
    """Form fields of a multipart/form-data request, values as raw bytes (binary safe)."""
    head = f"Content-Type: {request.headers['content-type']}\r\n\r\n".encode()
    msg = BytesParser(policy=HTTP).parsebytes(head + request.content)
    return {part.get_param("name", header="content-disposition"): part.get_payload(decode=True) for part in msg.iter_parts()}


class MockGnaniBackend:
    def __init__(self, api_key: str = "test-key", stt_transcript_fn: Callable[[bytes, str], str] | None = None) -> None:
        self.api_key = api_key
        self.stt_transcript_fn = stt_transcript_fn or (lambda audio, lang: "")
        self.calls: list[dict[str, Any]] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get(AUTH_HEADER) != self.api_key:
            return httpx.Response(401, json={"detail": "Unauthorized"})
        routes = {TTS_PATH: self._tts, VC_EMBED_PATH: self._embed, STT_PATH: self._stt}
        handler = routes.get(request.url.path)
        if request.method != "POST" or handler is None:
            return httpx.Response(404, json={"detail": "Not Found"})
        return handler(request)

    def _tts(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.calls.append({"path": TTS_PATH, "json": body})
        cfg = body.get("audio_config", {})
        container = cfg.get("container", "wav")
        if "speaker_embedding" in body:
            if list(body["speaker_embedding"].get("shape", [])) != [1, 768] or not body.get("text"):
                return _json_error(400, "INVALID_REQUEST_ERROR", "Invalid text or audio configuration.")
            seed = body["speaker_embedding"]["embedding"][:64] + body["text"]
        else:
            if not all(body.get(k) for k in ("text", "voice", "model", "language")):
                return _json_error(400, "INVALID_REQUEST_ERROR", "text, voice, model and language are required")
            seed = body["voice"] + body["text"]
        if container not in _CONTENT_TYPES:
            return _json_error(400, "INVALID_REQUEST_ERROR", f"container {container!r} not supported by mock")
        sr = 8000 if container in ("mulaw", "alaw") else int(cfg.get("sample_rate", 48000))
        audio = _encode(synth_speechlike(seed, sr, len(body["text"])), sr, container)
        return httpx.Response(200, content=audio, headers={"Content-Type": _CONTENT_TYPES[container]})

    def _embed(self, request: httpx.Request) -> httpx.Response:
        form = parse_multipart(request)
        self.calls.append({"path": VC_EMBED_PATH, "fields": sorted(form)})
        if "audio_file" not in form:
            return _json_error(400, "INVALID_REQUEST_ERROR", "audio_file is required")
        rng = np.random.default_rng(int.from_bytes(hashlib.sha256(form["audio_file"]).digest()[:8], "little"))
        emb = base64.b64encode(rng.standard_normal(768).astype(np.float16).tobytes()).decode()
        return httpx.Response(
            200,
            json={
                "success": True,
                "message": "Voice embeddings generated successfully",
                "data": {"voice_clone_embedding": {"embedding": emb, "shape": [1, 768], "dtype": "torch.bfloat16"}},
            },
        )

    def _stt(self, request: httpx.Request) -> httpx.Response:
        form = parse_multipart(request)
        self.calls.append({"path": STT_PATH, "fields": sorted(form)})
        if "audio_file" not in form or "language_code" not in form:
            return _json_error(400, "INVALID_REQUEST_ERROR", "audio_file and language_code are required")
        lang = form["language_code"].decode()
        now = datetime.now(timezone.utc)
        return httpx.Response(
            200,
            json={
                "success": True,
                "request_id": f"mock_{len(self.calls)}",
                "timestamp": now.strftime("%Y%m%d_%H%M%S.") + f"{now.microsecond // 1000:03d}",
                "transcript": self.stt_transcript_fn(form["audio_file"], lang),
            },
        )


class MockSTTWebSocket:
    """Emulates the realtime STT server: a segment closes after ``min_silence_frames`` zero frames."""

    def __init__(self, headers: dict[str, str], transcript_fn: Callable[[bytes], str], min_silence_frames: int = 8) -> None:
        self.headers = headers
        self.transcript_fn = transcript_fn
        self.min_silence_frames = min_silence_frames
        self.sample_rate = int(headers.get("x-sample-rate", "16000"))
        self.frame_sizes: list[int] = []
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._speech = bytearray()
        self._silent_run = 0
        self._segment_index = 0

    async def __aenter__(self) -> MockSTTWebSocket:
        self._put("connected", message="STT service ready (mock)", config={"sample_rate": self.sample_rate, "chunk_size": 512})
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def send(self, frame: bytes | str) -> None:
        if isinstance(frame, str):
            return  # control frames (update_settings) are accepted and ignored
        self.frame_sizes.append(len(frame))
        if len(frame) != STT_WS_FRAME_BYTES:
            raise ValueError(f"frames must be exactly {STT_WS_FRAME_BYTES} bytes, got {len(frame)}")
        if any(frame):
            self._speech += frame
            self._silent_run = 0
            return
        self._silent_run += 1
        if self._speech and self._silent_run >= self.min_silence_frames:
            self._put("processing")
            n_samples = len(self._speech) // 2
            self._put(
                "transcript",
                text=self.transcript_fn(bytes(self._speech)),
                audio_duration_ms=int(1000 * n_samples / self.sample_rate),
                segment_id=f"mock-seg-{self._segment_index}",
                segment_index=self._segment_index,
                latency=0,
            )
            self._segment_index += 1
            self._speech.clear()

    async def recv(self) -> str:
        return await self._queue.get()

    async def close(self) -> None:
        return None

    def _put(self, msg_type: str, **fields: Any) -> None:
        msg = {"type": msg_type, "timestamp": datetime.now(timezone.utc).isoformat(), **fields}
        self._queue.put_nowait(json.dumps(msg))


class MockSTTConnect:
    """Drop-in for ``websockets.connect``; keeps the last socket for inspection."""

    def __init__(self, transcript_fn: Callable[[bytes], str], api_key: str = "test-key") -> None:
        self.transcript_fn = transcript_fn
        self.api_key = api_key
        self.last: MockSTTWebSocket | None = None

    def __call__(self, url: str, additional_headers: dict[str, str]) -> MockSTTWebSocket:
        if additional_headers.get("x-api-key-id") != self.api_key:
            raise GnaniAPIError(401, "Unauthorized")
        if "lang_code" not in additional_headers:
            raise ValueError("lang_code header is required")
        self.last = MockSTTWebSocket(additional_headers, self.transcript_fn)
        return self.last
