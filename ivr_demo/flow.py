"""Random-phrase voice authentication with Armour365-style codes (Part C).

  1. Timbre speaks a fresh challenge phrase at 8 kHz (container=mulaw, as an IVR plays it).
  2. The caller answers; Prisma realtime STT at 8000 Hz transcribes; the phrase must match.
  3. The CM scores liveness on the caller audio; the ASV stand-in scores the claimed identity.
  4. Fused decision with the Armour365 codes (docs/gnani_api_snapshots/armour365_README.md):
     StatusCode 0 Success, 3 Short Audio, 4 No Audio, 5 Internal Error;
     DecisionCode 0 Success, 1 Spoof Failure, 2 Voice Failure, 3 Internal Error.
     A phrase mismatch is a failed liveness challenge, so it maps to DecisionCode 1 (reason recorded).

``latency_ms`` is local compute from end of caller speech to decision (CM + ASV + fusion), as the
statement's 300 ms budget defines it; Prisma network time is reported separately as ``stt_ms``.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import numpy as np

from cm.scorer import MIN_SPEECH_S, CMScorer
from factory.normalise import frame_energy_db
from gnani_api import AudioConfig, GnaniClient
from gnani_api.g711 import decode_mulaw
from ivr_demo.asv import ASV
from ivr_demo.phrases import Challenge, make_challenge, phrase_distance, phrase_matches

SR = 8000
SttFn = Callable[[bytes, str], Awaitable[str]]  # (pcm16 8 kHz, language) -> transcript


@dataclass
class VerifyResult:
    StatusCode: int
    DecisionCode: int
    reason: str
    phrase_match: bool | None = None
    phrase_distance: float | None = None
    transcript: str | None = None
    asv_score: float | None = None
    cm_llr: float | None = None
    cm_partial: list[dict[str, float]] | None = None
    latency_ms: float | None = None
    stt_ms: float | None = None

    def as_json(self) -> dict[str, object]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


def prompt_audio(client: GnaniClient, challenge: Challenge, voice: str) -> np.ndarray:
    """Timbre prompt as the caller hears it: raw G.711 mu-law at 8 kHz, decoded to float."""
    mu = client.tts(challenge.text, voice, language=challenge.language, audio_config=AudioConfig(sample_rate=8000, container="mulaw"))
    return decode_mulaw(mu).astype(np.float32) / 32768.0


def prisma_stt(api_key: str | None = None, **kwargs: object) -> SttFn:
    """Realtime Prisma STT at 8 kHz as an ``SttFn``; extra kwargs go to ``stt_stream`` (e.g. a mock connect).

    ``run.stats`` keeps the last session's ``final_delay_s`` (end of caller audio to the last transcript, the
    server VAD silence window included) and ``segments``, so the demo can report Prisma's share of the latency.
    """
    from gnani_api.stream import IVR_VAD_8K, stt_stream

    stats: dict[str, float] = {}

    async def run(pcm16: bytes, language: str) -> str:
        transcripts, delay = await stt_stream(pcm16, language_code=language, api_key=api_key, sample_rate=SR, vad=IVR_VAD_8K, **kwargs)  # type: ignore[arg-type]
        stats.update(final_delay_s=float(delay), segments=float(len(transcripts)))
        return " ".join(t.text for t in transcripts)

    run.stats = stats  # type: ignore[attr-defined]
    return run


def verify(
    caller_8k: np.ndarray,
    challenge: Challenge,
    enrol_embedding: np.ndarray,
    cm: CMScorer,
    asv: ASV,
    stt: SttFn,
) -> VerifyResult:
    try:
        x = np.asarray(caller_8k, dtype=np.float32)
        if len(x) == 0 or frame_energy_db(x, SR).max() < -60:
            return VerifyResult(4, 3, "no_audio")
        pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
        t_stt = time.perf_counter()
        transcript = asyncio.run(stt(pcm, challenge.language))
        stt_ms = 1000 * (time.perf_counter() - t_stt)
        t0 = time.perf_counter()
        cm_res = cm.score(x)
        if cm_res.speech_s < MIN_SPEECH_S:
            return VerifyResult(3, 3, "short_audio", transcript=transcript, stt_ms=stt_ms)
        dist = phrase_distance(challenge.text, transcript, challenge.language)
        match = phrase_matches(challenge.text, transcript, challenge.language)
        asv_score = asv.score(enrol_embedding, asv.embed(x))
        if not match:
            code, reason = 1, "phrase_mismatch"
        elif cm_res.decision == "spoof":
            code, reason = 1, "cm_spoof"
        elif asv_score < asv.threshold:
            code, reason = 2, "voice_mismatch"
        else:
            code, reason = 0, "accepted"
        return VerifyResult(0, code, reason, match, round(dist, 3), transcript, round(asv_score, 3), round(cm_res.llr, 3),
                            cm_res.partial, round(1000 * (time.perf_counter() - t0), 1), round(stt_ms, 1))
    except Exception as exc:  # noqa: BLE001 - any failure must still produce an Armour365-shaped answer
        return VerifyResult(5, 3, f"internal_error: {type(exc).__name__}: {exc}")


def new_challenge(language: str, seed: int | None = None) -> Challenge:
    return make_challenge(language, np.random.default_rng(seed))
