"""Prisma v2.5 realtime STT over WebSocket (``wss://api.vachana.ai/stt/v3/stream``).

Protocol (STT_stt-websocket.md): configuration travels in the upgrade headers; the client sends
binary frames of exactly 1024 bytes (512 PCM16LE mono samples, one every 64 ms at 8 kHz); the
server answers with JSON messages typed ``connected``, ``processing``, ``transcript`` and ``error``.

The docs define no explicit end-of-stream message. Segments are closed by the server VAD after
``x-min-silence-ms`` of silence, so this client appends ``tail_silence_s`` of zero frames after the
audio and then waits until no message has arrived for ``drain_timeout_s`` before closing.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import math
import time
from collections.abc import Callable
from typing import Any

import websockets

from gnani_api.client import load_api_key
from gnani_api.schemas import STT_LANGUAGE_CODES, STT_WS_FRAME_BYTES, STT_WS_SAMPLE_RATES, STT_WS_URL, GnaniAPIError, StreamTranscript

# Telephony preset from the docs, with a shorter silence window for IVR answers.
IVR_VAD_8K = {"x-vad-threshold": "0.7", "x-min-speech-ms": "200", "x-min-silence-ms": "400"}


def frames_1024(pcm16: bytes, sample_rate: int, tail_silence_s: float) -> list[bytes]:
    """Split PCM16 into exact 1024-byte frames (zero padded) and append trailing silence frames."""
    padded = pcm16 + b"\x00" * (-len(pcm16) % STT_WS_FRAME_BYTES)
    frames = [padded[i : i + STT_WS_FRAME_BYTES] for i in range(0, len(padded), STT_WS_FRAME_BYTES)]
    n_tail = int(math.ceil(tail_silence_s * sample_rate / (STT_WS_FRAME_BYTES // 2)))
    return frames + [b"\x00" * STT_WS_FRAME_BYTES] * n_tail


async def stt_stream(
    pcm16: bytes,
    *,
    language_code: str,
    api_key: str | None = None,
    sample_rate: int = 8000,
    vad: dict[str, str] | None = None,
    url: str = STT_WS_URL,
    connect: Callable[..., Any] = websockets.connect,
    realtime_pace: bool = True,
    tail_silence_s: float = 1.0,
    drain_timeout_s: float = 5.0,
) -> tuple[list[StreamTranscript], float]:
    """Stream ``pcm16`` and return (transcripts sorted by segment, seconds from last audio frame to last transcript)."""
    if sample_rate not in STT_WS_SAMPLE_RATES:
        raise ValueError(f"x-sample-rate must be one of {STT_WS_SAMPLE_RATES}")
    if language_code not in STT_LANGUAGE_CODES:
        raise ValueError(f"lang_code must be one of {STT_LANGUAGE_CODES}")
    key = api_key or load_api_key()
    if not key:
        raise RuntimeError("No Gnani API key: set GNANI_API_KEY or add it to .env")
    headers = {"x-api-key-id": key, "lang_code": language_code, "x-sample-rate": str(sample_rate), **(vad or {})}
    frame_period = (STT_WS_FRAME_BYTES // 2) / sample_rate
    transcripts: list[StreamTranscript] = []
    last_msg = time.perf_counter()
    last_transcript_at = 0.0

    async with connect(url, additional_headers=headers) as ws:
        first = json.loads(await ws.recv())
        if first.get("type") == "error":
            raise GnaniAPIError(0, first.get("message", "stream error"), json.dumps(first))
        if first.get("type") != "connected":
            raise GnaniAPIError(0, f"expected 'connected', got {first.get('type')!r}", json.dumps(first))

        async def receive() -> None:
            nonlocal last_msg, last_transcript_at
            while True:
                msg = json.loads(await ws.recv())
                last_msg = time.perf_counter()
                if msg.get("type") == "transcript":
                    transcripts.append(StreamTranscript.from_message(msg))
                    last_transcript_at = last_msg
                elif msg.get("type") == "error":
                    raise GnaniAPIError(0, msg.get("message", "stream error"), json.dumps(msg))

        receiver = asyncio.create_task(receive())
        try:
            n_audio = math.ceil(len(pcm16) / STT_WS_FRAME_BYTES)
            audio_end = time.perf_counter()
            for i, frame in enumerate(frames_1024(pcm16, sample_rate, tail_silence_s)):
                await ws.send(frame)
                if i == n_audio - 1:
                    audio_end = time.perf_counter()
                await asyncio.sleep(frame_period if realtime_pace else 0)
                if receiver.done():
                    break
            while not receiver.done() and time.perf_counter() - last_msg < drain_timeout_s:
                await asyncio.sleep(0.02)
            if receiver.done() and receiver.exception() is not None:
                raise receiver.exception()  # type: ignore[misc]
        finally:
            receiver.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await receiver
    delay = max(0.0, last_transcript_at - audio_end) if transcripts else float("nan")
    return sorted(transcripts, key=lambda t: t.segment_index), delay
