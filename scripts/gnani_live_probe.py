"""One-off live probe: the minimum number of real Gnani calls to confirm the documented shapes.

Calls (5 total): Timbre TTS (one ~6 s Hindi sentence, 8 kHz WAV), Prisma STT REST on that audio,
Prisma realtime STT at 8 kHz on the same audio, VC embedding using the Timbre audio as the reference
(a synthetic voice, not a real person), VC TTS of one word requested as container=mulaw (the G3
born-narrowband format). Results go to artifacts/gnani_probe.json; audio to artifacts/gnani_cache/.
Every response header whose name mentions credit/usage/quota/limit is recorded, to find out whether
the API reports credit cost. The key is never printed or stored.

Usage:  python scripts/gnani_live_probe.py --yes
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gnani_api import AudioConfig, GnaniClient, load_api_key, stt_stream  # noqa: E402
from gnani_api.g711 import decode_mulaw  # noqa: E402
from gnani_api.stream import IVR_VAD_8K  # noqa: E402

CACHE = ROOT / "artifacts" / "gnani_cache"
LEDGER = ROOT / "artifacts" / "gnani_usage.jsonl"
OUT = ROOT / "artifacts" / "gnani_probe.json"
TTS_TEXT = "मेरी आवाज़ ही मेरी पहचान है, कृपया इस वाक्य को ध्यान से सुनिए और फिर दोहराइए।"
VC_TEXT = "नमस्ते"
INTERESTING = ("credit", "usage", "quota", "limit", "cost", "billing", "request-id", "x-request")


class HeaderSpy(httpx.HTTPTransport):
    """Records response headers of interest (values never contain our key; checked anyway)."""

    def __init__(self, key: str) -> None:
        super().__init__()
        self.key = key
        self.seen: list[dict[str, object]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        resp = super().handle_request(request)
        hdrs = {k: v for k, v in resp.headers.items() if any(s in k.lower() for s in INTERESTING) and self.key not in v}
        self.seen.append({"path": request.url.path, "status": resp.status_code,
                          "content_type": resp.headers.get("content-type"), "headers_of_interest": hdrs,
                          "all_header_names": sorted(resp.headers.keys())})
        return resp


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="confirm spending credits on 5 small calls")
    if not ap.parse_args().yes:
        sys.exit("refusing to spend credits without --yes")
    key = load_api_key()
    if not key:
        sys.exit("no GNANI_API_KEY in env or .env")
    CACHE.mkdir(parents=True, exist_ok=True)
    spy = HeaderSpy(key)
    report: dict[str, object] = {"date": time.strftime("%Y-%m-%d %H:%M:%S %z")}
    with GnaniClient(api_key=key, transport=spy, ledger_path=LEDGER) as client:
        t0 = time.perf_counter()
        wav = client.tts(TTS_TEXT, "Nalini", model="timbre-v2.5", language="hi-IN",
                         audio_config=AudioConfig(sample_rate=8000, container="wav"))
        x, sr = sf.read(io.BytesIO(wav), dtype="float32")
        (CACHE / "probe_tts_nalini_8k.wav").write_bytes(wav)
        report["tts"] = {"bytes": len(wav), "sr": sr, "seconds": round(len(x) / sr, 2), "chars": len(TTS_TEXT),
                         "latency_s": round(time.perf_counter() - t0, 2)}

        stt = client.stt(wav, "hi-IN")
        report["stt_rest"] = {"keys": sorted(stt.raw), "transcript": stt.transcript, "reference": TTS_TEXT}

        pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
        transcripts, delay = asyncio.run(stt_stream(pcm, language_code="hi-IN", api_key=key, sample_rate=8000,
                                                    vad=IVR_VAD_8K, drain_timeout_s=4.0))
        report["stt_ws"] = {"segments": [t.raw for t in transcripts], "end_of_audio_to_transcript_s": delay}

        emb = client.vc_embedding(wav, filename="timbre_reference.wav")
        report["vc_embedding"] = {"shape": list(emb.shape), "dtype": emb.dtype, "embedding_chars": len(emb.embedding)}

        mu = client.vc_tts(VC_TEXT, emb, audio_config=AudioConfig(sample_rate=8000, container="mulaw"))
        (CACHE / "probe_vc_mulaw.raw").write_bytes(mu)
        y = decode_mulaw(mu)
        sf.write(CACHE / "probe_vc_mulaw_decoded.wav", y, 8000)
        report["vc_tts_mulaw"] = {"bytes": len(mu), "seconds_if_8k_1byte": round(len(mu) / 8000, 2),
                                  "starts_with_riff": mu[:4] == b"RIFF"}
    report["http"] = spy.seen
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    assert key not in OUT.read_text(encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
