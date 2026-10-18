"""Synchronous REST client for Gnani Prisma STT, Timbre TTS and the voice-cloning API.

The API key is read from the ``GNANI_API_KEY`` environment variable, or from a ``.env`` file in the
project root. It is only ever placed in the ``X-API-Key-ID`` request header; it is never logged,
written to the usage ledger, or included in exception messages.
"""

from __future__ import annotations

import io
import json
import os
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import soundfile as sf

from gnani_api.schemas import (
    AUTH_HEADER,
    BASE_URL,
    LANGUAGE_CODES,
    STT_FORMATS,
    STT_LANGUAGE_CODES,
    STT_PATH,
    TTS_MODELS,
    TTS_PATH,
    TTS_SPEED_ALIASES,
    VC_EMBED_PATH,
    VC_MODEL,
    AudioConfig,
    GnaniAPIError,
    SpeakerEmbedding,
    STTResult,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_api_key(env_file: Path = PROJECT_ROOT / ".env") -> str | None:
    """``GNANI_API_KEY`` from the environment, else from a KEY=VALUE ``.env`` file, else None."""
    key = os.environ.get("GNANI_API_KEY")
    if key:
        return key.strip()
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, sep, value = line.partition("=")
            if sep and name.strip() == "GNANI_API_KEY":
                return value.strip().strip('"').strip("'") or None
    return None


class GnaniClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = BASE_URL,
        transport: httpx.BaseTransport | None = None,
        timeout_s: float = 60.0,
        ledger_path: Path | None = None,
    ) -> None:
        key = api_key or load_api_key()
        if not key:
            raise RuntimeError("No Gnani API key: set GNANI_API_KEY or add it to .env (see docs/gnani_api_notes.md)")
        self._http = httpx.Client(
            base_url=base_url, headers={AUTH_HEADER: key}, transport=transport, timeout=timeout_s
        )
        self._ledger_path = ledger_path

    def __enter__(self) -> GnaniClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    # Timbre TTS ----------------------------------------------------------------------------------
    def tts(
        self,
        text: str,
        voice: str,
        *,
        model: str = "timbre-v2.5",
        language: str = "auto",
        speed: float | str = 1.0,
        audio_config: AudioConfig = AudioConfig(),
    ) -> bytes:
        if model not in TTS_MODELS:
            raise ValueError(f"model must be one of {TTS_MODELS}")
        if language not in LANGUAGE_CODES:
            raise ValueError(f"language must be one of {LANGUAGE_CODES}")
        speed_value = TTS_SPEED_ALIASES.get(speed, speed) if isinstance(speed, str) else speed
        if not isinstance(speed_value, (int, float)) or not 0.85 <= speed_value <= 1.15:
            raise ValueError("speed must be in 0.85..1.15 or one of slow/medium/fast")
        audio_config.validate_for_tts()
        body = {
            "text": text,
            "voice": voice,
            "model": model,
            "language": language,
            "speed": speed,
            "audio_config": audio_config.to_json(),
        }
        return self._post_audio(TTS_PATH, body, model=model, n_chars=len(text))

    # Voice cloning -------------------------------------------------------------------------------
    def vc_embedding(self, audio: bytes, filename: str = "reference.wav") -> SpeakerEmbedding:
        duration = _wav_duration(audio)
        if duration is not None and not 5.0 <= duration <= 30.0:
            warnings.warn(f"reference audio is {duration:.1f} s; the docs ask for 5 to 30 s", stacklevel=2)
        t0 = time.perf_counter()
        resp = self._http.post(VC_EMBED_PATH, files={"audio_file": (filename, audio, "application/octet-stream")})
        self._log(VC_EMBED_PATH, None, 0, len(audio), len(resp.content), resp.status_code, t0)
        _raise_for_status(resp)
        return SpeakerEmbedding.from_response(resp.json())

    def vc_tts(
        self, text: str, speaker_embedding: SpeakerEmbedding, *, audio_config: AudioConfig = AudioConfig()
    ) -> bytes:
        audio_config.validate_for_vc()
        body = {
            "text": text,
            "model": VC_MODEL,
            "audio_config": audio_config.to_json(),
            "speaker_embedding": speaker_embedding.to_json(),
        }
        return self._post_audio(TTS_PATH, body, model=VC_MODEL, n_chars=len(text))

    # Prisma STT (REST) ---------------------------------------------------------------------------
    def stt(
        self, audio: bytes, language_code: str, *, format: str = "verbatim", filename: str = "audio.wav"
    ) -> STTResult:
        if language_code not in STT_LANGUAGE_CODES:
            raise ValueError(f"language_code must be one of {STT_LANGUAGE_CODES}")
        if format not in STT_FORMATS:
            raise ValueError(f"format must be one of {STT_FORMATS}")
        t0 = time.perf_counter()
        resp = self._http.post(
            STT_PATH,
            files={"audio_file": (filename, audio, "application/octet-stream")},
            data={"language_code": language_code, "format": format},
        )
        self._log(STT_PATH, "prisma-v2.5", 0, len(audio), len(resp.content), resp.status_code, t0)
        _raise_for_status(resp)
        payload = resp.json()
        return STTResult(
            transcript=payload.get("transcript", ""),
            request_id=str(payload.get("request_id", "")),
            timestamp=str(payload.get("timestamp", "")),
            raw=payload,
        )

    # internals -----------------------------------------------------------------------------------
    def _post_audio(self, path: str, body: dict[str, Any], *, model: str, n_chars: int) -> bytes:
        t0 = time.perf_counter()
        raw = json.dumps(body).encode()
        resp = self._http.post(path, content=raw, headers={"Content-Type": "application/json"})
        self._log(path, model, n_chars, len(raw), len(resp.content), resp.status_code, t0)
        _raise_for_status(resp)
        return resp.content

    def _log(
        self, endpoint: str, model: str | None, n_chars: int, bytes_in: int, bytes_out: int, status: int, t0: float
    ) -> None:
        if self._ledger_path is None:
            return
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "model": model,
            "n_chars": n_chars,
            "bytes_in": bytes_in,
            "bytes_out": bytes_out,
            "status": status,
            "latency_ms": round(1000 * (time.perf_counter() - t0), 1),
        }
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self._ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.is_success:
        return
    message = resp.reason_phrase
    try:
        payload = resp.json()
        err = payload.get("error", payload) if isinstance(payload, dict) else payload
        message = err.get("message", message) if isinstance(err, dict) else str(err)
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    raise GnaniAPIError(resp.status_code, str(message), resp.text[:2000])


def _wav_duration(audio: bytes) -> float | None:
    try:
        info = sf.info(io.BytesIO(audio))
    except (RuntimeError, sf.LibsndfileError):
        return None
    return info.frames / info.samplerate
