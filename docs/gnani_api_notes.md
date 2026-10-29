# Gnani API notes (verified against the live API)

Doc snapshots used to build `gnani_api/`: `docs/gnani_api_snapshots/*.md`, fetched 18 Oct 2026 from
docs.gnani.ai (pages marked "Last verified: 5 August 2026"). Armour365 status and decision codes come
from `docs/gnani_api_snapshots/armour365_README.md` (GitHub Gnani-AI/voicebiometric-api-armour365).

## Live probe, 18 Oct 2026 (`python scripts/gnani_live_probe.py --yes`)

Exactly 5 real calls were made with the student's challenge key (loaded from `.env`, never logged).
Raw results: `artifacts/gnani_probe.json` (tracked on purpose: shapes, request ids, header names and the Timbre
transcript; no key, no audio, no embedding values); per-call ledger: `artifacts/gnani_usage.jsonl` (git-ignored).

| # | Endpoint | Request | Result | Latency |
|---|---|---|---|---|
| 1 | `POST /api/v1/tts/inference` (Timbre v2.5) | voice `Nalini`, `hi-IN`, 77-char Hindi sentence, `sample_rate=8000`, `container=wav` | 200, `audio/wav`, 8000 Hz, 4.80 s | 2.05 s |
| 2 | `POST /stt/v3` (Prisma v2.5 REST) | the call-1 WAV, `language_code=hi-IN`, `format=verbatim` | 200, transcript identical to the input text | 0.62 s |
| 3 | `wss://api.vachana.ai/stt/v3/stream` (Prisma realtime) | same audio as 8 kHz PCM16, 1024-byte frames at 64 ms cadence, VAD `0.7/200/400` | one `transcript` segment, identical text, server `latency` 265 ms; 0.90 s from last audio frame to transcript (includes the 400 ms silence window) | |
| 4 | `POST /api/v1/tts/voice-clone/embeddings` | the call-1 Timbre audio as reference (synthetic voice, no real person) | 200, `shape [1, 768]`, `dtype torch.bfloat16`, embedding string of 4,096 chars | 0.72 s |
| 5 | `POST /api/v1/tts/inference` (`vachana-vc-v1`) | text `नमस्ते`, `container=mulaw`, `sample_rate=8000` | 200, `audio/basic`, 3,689 bytes of headerless G.711 mu-law (0.46 s) | 1.35 s |

## Where the live API differs from the docs (the client handles both)

- **STT REST response** has keys `success, request_id, transcript, model, processing_time, end_to_end_latency`.
  The documented `timestamp` field was not present. `STTResult.timestamp` is therefore empty for live calls.
- **Realtime `transcript` message** carries extra fields `utterance_id`, `is_final`, `output.literal`;
  `audio_duration_ms` is a float (5056.0); the first `segment_index` was **1**, not 0 as documented.
- **No credit information is returned.** No response header mentions credits, usage or quota (only
  `x-api-request-id` and `x-audio-container`). Credit cost per call must be read from the dashboard at
  app.gnani.ai before and after a run. Action for the student: note the dashboard balance now, since
  these 5 calls are the only spend so far, and divide.
- A 4.8 s reference was accepted by the embeddings endpoint although the docs ask for 5 to 30 s. The
  client warns below 5 s rather than refusing.
- VC REST docs list containers `raw, mp3, wav, mulaw, ogg` (no `alaw`); `AudioConfig.validate_for_vc`
  rejects `alaw` so G3 A-law variants are made by requesting mu-law and transcoding (documented in
  `factory/gnani_clone.py`).

## Prisma v3.0 (opt-in since 2026-10-22; read from the docs on 2026-10-29, not called yet)

From https://docs.gnani.ai/api/STT/models/prisma-v3.md: on REST (`POST /stt/v3`) the opt-in is the form field
`model=prisma-v3.0`; `language_code` stays required (a normal code such as `hi-IN`, or `indic-auto`, v3.0 only); the
response adds `detected_language_code` and reports the serving model in `model`; REST takes at most 30 s per
request. The page shows a 16 kHz realtime example and does not state 8 kHz support, so the 8 kHz phrase check
(`ivr_demo/phrase_check.py`, REST) records any rejection per clip, and treats the comparison as void unless every
v3.0 response reports `prisma-v3.0`. `GnaniClient.stt(..., model="prisma-v3.0")` sends the field; v2.5 calls send
no `model` field (server default).

## Budget rules in this repo

- Tests never touch the network (`MockGnaniBackend`, `MockSTTConnect`). `pytest -m live` runs the
  opt-in live tests in `tests/test_gnani_live.py` (2 tiny calls).
- `factory/gnani_clone.py` prints a dry-run plan with call and character counts and refuses to run
  without `--execute` and a `--max-calls` cap; every generated clip is cached by content hash so a rerun
  never spends twice.
