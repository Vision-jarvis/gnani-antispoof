"""Request and response shapes for the Gnani speech APIs.

Every field name here comes from the official docs, snapshotted in docs/gnani_api_snapshots/
(fetched 18 Oct 2026; pages say "Last verified: 5 August 2026"):
TTS_tts-inference.md, VC_voice-clone-embeddings.md, VC_vc-inference.md, STT_speech-to-text.md,
STT_stt-websocket.md.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

BASE_URL = "https://api.vachana.ai"
STT_WS_URL = "wss://api.vachana.ai/stt/v3/stream"
TTS_PATH = "/api/v1/tts/inference"  # Timbre TTS and voice-cloned TTS share this path
VC_EMBED_PATH = "/api/v1/tts/voice-clone/embeddings"
STT_PATH = "/stt/v3"
AUTH_HEADER = "X-API-Key-ID"

TTS_MODELS = ("timbre-v2.5", "timbre-v3.0")
VC_MODEL = "vachana-vc-v1"
LANGUAGE_CODES = (
    "auto", "hi-IN", "en-IN", "ta-IN", "te-IN", "kn-IN", "ml-IN", "mr-IN", "pa-IN", "bn-IN", "gu-IN", "hi-en",
)
STT_LANGUAGE_CODES = ("bn-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN", "ml-IN", "mr-IN", "pa-IN", "ta-IN", "te-IN")
STT_FORMATS = ("verbatim", "transcribe")
STT_WS_SAMPLE_RATES = (8000, 16000, 44100, 48000)
STT_WS_FRAME_BYTES = 1024  # 512 PCM16 samples per binary frame, at every sample rate

TTS_SAMPLE_RATES = (8000, 16000, 22050, 24000, 44100, 48000)
TTS_CONTAINERS = ("wav", "raw", "mp3", "ogg", "mulaw", "alaw")
VC_CONTAINERS = ("raw", "mp3", "wav", "mulaw", "ogg")  # the VC REST page does not list alaw
TTS_SPEED_ALIASES = {"slow": 0.85, "medium": 1.0, "fast": 1.15}
G711_CONTAINERS = ("mulaw", "alaw")


class GnaniAPIError(Exception):
    def __init__(self, status_code: int, message: str, body: str = "") -> None:
        super().__init__(f"Gnani API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.body = body


@dataclass(frozen=True)
class AudioConfig:
    """``audio_config`` object of the TTS and VC requests."""

    sample_rate: int = 8000
    num_channels: int = 1
    sample_width: int = 2
    encoding: str = "linear_pcm"
    container: str = "wav"
    bitrate: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    def effective_sample_rate(self) -> int:
        """``container=mulaw``/``alaw`` force 8000 Hz regardless of ``sample_rate`` (TTS doc)."""
        return 8000 if self.container in G711_CONTAINERS else self.sample_rate

    def validate_for_tts(self) -> None:
        if self.sample_rate not in TTS_SAMPLE_RATES:
            raise ValueError(f"TTS sample_rate must be one of {TTS_SAMPLE_RATES}, got {self.sample_rate}")
        if self.container not in TTS_CONTAINERS:
            raise ValueError(f"TTS container must be one of {TTS_CONTAINERS}, got {self.container!r}")
        if self.bitrate is not None and self.container != "mp3":
            raise ValueError("bitrate is only used when container is mp3")

    def validate_for_vc(self) -> None:
        if not 8000 <= self.sample_rate <= 44100:
            raise ValueError(f"VC sample_rate must be in 8000..44100, got {self.sample_rate}")
        if self.container not in VC_CONTAINERS:
            raise ValueError(
                f"VC container must be one of {VC_CONTAINERS}, got {self.container!r} "
                "(the VC REST doc does not list alaw; request mulaw and transcode if A-law is needed)"
            )


@dataclass(frozen=True)
class SpeakerEmbedding:
    """``speaker_embedding`` returned by the embeddings endpoint and sent back to VC TTS."""

    embedding: str
    shape: tuple[int, ...]
    dtype: str

    @classmethod
    def from_response(cls, payload: dict[str, Any]) -> SpeakerEmbedding:
        try:
            e = payload["data"]["voice_clone_embedding"]
            return cls(embedding=e["embedding"], shape=tuple(e["shape"]), dtype=e["dtype"])
        except (KeyError, TypeError) as exc:
            raise GnaniAPIError(200, f"unexpected embeddings response shape: missing {exc}") from exc

    def to_json(self) -> dict[str, Any]:
        return {"embedding": self.embedding, "shape": list(self.shape), "dtype": self.dtype}


@dataclass(frozen=True)
class STTResult:
    transcript: str
    request_id: str
    timestamp: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class StreamTranscript:
    text: str
    audio_duration_ms: int
    segment_id: str
    segment_index: int
    latency: int
    raw: dict[str, Any]

    @classmethod
    def from_message(cls, msg: dict[str, Any]) -> StreamTranscript:
        return cls(
            text=msg.get("text", ""),
            audio_duration_ms=int(msg.get("audio_duration_ms", 0)),
            segment_id=str(msg.get("segment_id", "")),
            segment_index=int(msg.get("segment_index", 0)),
            latency=int(msg.get("latency", 0)),
            raw=msg,
        )
