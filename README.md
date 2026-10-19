# Telephony-native voice anti-spoofing for Armour365 (Gnani.ai problem 05)

A countermeasure (CM) stack for catching TTS and voice-conversion clones after the audio has gone
through an 8 kHz phone line, plus a random-phrase voice-auth IVR flow built on Gnani Prisma STT and
Timbre TTS that returns Armour365's decision codes. Built for the Great Indian AI Internship
Challenge. What runs today is on CPU; the GPU teacher and the Gnani clone attack set are prepared as
one-command jobs and marked PENDING (see STATUS.md).

## Quickstart (Windows, PowerShell)

```powershell
.\run.ps1 setup        # .venv, CPU torch, requirements, clones clovaai/aasist and SSL_Anti-spoofing into third_party/
.\run.ps1 quick        # under 5 minutes: offline unit tests + mock IVR demo + tables from existing scores
.\run.ps1 pipeline     # full CPU pipeline: subsets, 6 baselines, calibration, report, DET, ONNX, Indic pilot (hours; resumable)
.\run.ps1 serve        # FastAPI on :8000 (/v1/cm/score, WS /v1/cm/stream, /v1/auth/*)
```
Data: `bash scripts/download_data.sh` (resumable). Manual steps for gated sets are in `data/README.md`.
The Gnani key is read from `.env` (`GNANI_API_KEY=...`, git-ignored). No test touches the network;
`.\run.ps1 live-test` makes 2 real calls.

## Results so far (real runs in this repo)

RESULTS_PLACEHOLDER

## Repo map

| Path | What |
|---|---|
| `factory/channel_sim.py` | 14 telephony conditions (G.711 mu/A-law, AMR-NB 12.2/7.95/4.75, AMR-WB, Opus 6/8/16k, GSM-FR, packet loss, two-hop chains) via real ffmpeg codecs, deterministic by seed |
| `factory/normalise.py` | anti-shortcut policy: VAD trim + -23 LUFS, and the second CM-input trim |
| `factory/asvspoof.py`, `factory/indic_pilot.py` | subset builders (ASVspoof 2019 LA; FLEURS vs IndicSynth pilot) |
| `factory/gnani_clone.py` | G1/G2/G3 generator on the Gnani APIs: dry-run cost plan, hard call cap, content-hash cache |
| `factory/replay_sim.py` | G5 replay simulation (loudspeaker, room, phone mic) |
| `gnani_api/` | client for Timbre TTS, voice-clone embeddings + VC TTS, Prisma STT REST + realtime WS; mock backend; G.711 codec |
| `cm/features.py`, `cm/gmm.py`, `cm/lcnn.py`, `cm/train_lcnn.py` | LFCC, LFCC-GMM, LFCC-LCNN |
| `cm/aasist_pretrained.py` | pretrained AASIST / AASIST-L as published |
| `cm/run_baselines.py` | trains and scores every baseline on every condition and streaming horizon |
| `cm/scorer.py`, `cm/calibrate.py`, `cm/export_onnx.py` | runtime CM (LLR, partial scores), dev calibration, ONNX + RTF/RAM |
| `cm/teacher/` | XLS-R 300M + AASIST teacher: config, training loop (CPU smoke test), Modal runner (PENDING GPU) |
| `eval/metrics.py`, `eval/protocol.py`, `eval/shortcut_audit.py` | ROCCH EER, minDCF, Cllr, FRR@FAR1; held-out attack/codec rules; shortcut audit |
| `eval/report.py`, `eval/points.py`, `eval/det.py`, `eval/indic_report.py` | tables, points matrix, DET curves, Indic pilot |
| `ivr_demo/` | challenge phrases, phrase match, ASV stand-in, fused Armour365 decision, demo (mock or live) |
| `service/app.py` | FastAPI with the statement's interfaces |
| `docs/gnani_api_notes.md` | live-verified API shapes and where they differ from the docs |
| `STATUS.md`, `UNDERSTAND.md`, `REPORT.md`, `MODEL_CARD.md`, `DATA_CARD.md` | status and challenge checklist, interview prep, report, cards |

Layout note: the statement's `gnani-armour-cm/` deliverable tree maps onto this repo as `factory/`,
`cm/`, `service/`, `ivr_demo/`, `eval/`, with `gnani_api/` split out of `factory/gnani_clone.py`.
