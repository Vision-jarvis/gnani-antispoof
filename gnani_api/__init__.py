"""Client, schemas and mock backend for the Gnani speech APIs (Prisma STT, Timbre TTS, voice cloning)."""

from gnani_api.client import GnaniClient, load_api_key
from gnani_api.schemas import AudioConfig, GnaniAPIError, SpeakerEmbedding, StreamTranscript, STTResult
from gnani_api.stream import stt_stream

__all__ = [
    "AudioConfig",
    "GnaniAPIError",
    "GnaniClient",
    "STTResult",
    "SpeakerEmbedding",
    "StreamTranscript",
    "load_api_key",
    "stt_stream",
]
