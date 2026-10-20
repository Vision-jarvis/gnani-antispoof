# Status (3-day cut from the problem statement, section 9)

Legend: DONE = built and verified in this repo; PARTIAL = built, but part of the item is blocked;
PENDING = blocked, with the blocker and the exact command to finish.

## Day 1: data and "the baseline breaks"

| Item | Status | Notes / blocker | Command to finish |
|---|---|---|---|
| Register for challenge credits; measure credit cost per call | PARTIAL | Registered, key in `.env`. 5 probe calls made (TTS, STT REST, STT realtime, VC embedding, VC TTS mu-law); shapes verified, see `docs/gnani_api_notes.md`. The API returns no credit information in responses. | Read the balance on app.gnani.ai now, divide by the 5 probe calls (or by the ledger rows in `artifacts/gnani_usage.jsonl`) |
| Pull ASVspoof 2019 LA | DONE | HF mirror (DataShare refused connections; manual browser step in `data/README.md`) | |
| Pull ASVspoof 2021 LA eval + keys | PARTIAL | keys done; 7.8 GB audio download in progress / resumable | `bash scripts/download_data.sh` |
| Pull Kathbath Hindi + Kannada | PENDING | gated on HF (accept terms while logged in) | see `data/README.md`, step 2 |
| Pull an IndicSynth Hindi/Kannada slice | DONE | first shard each (FreeVC); used as G4 in the Indic pilot | |
| `gnani_clone.py`: G2 for 40 speakers x 2 languages, G3 a third as mulaw, 300 G1 clips | PARTIAL | Generator, dry-run cost plan, hard cap, cache and tests done. Real generation not run: needs Kathbath eval speakers and student approval of the credit spend. | `python -m factory.gnani_clone --speakers factory/manifests/eval_speakers.csv` (dry run), then add `--execute --max-calls N` |
| `channel_sim.py` with 8 codec conditions + 2 chains | DONE | 14 conditions incl. 2 two-hop chains, packet loss, band-limit; deterministic by seed; 31 unit tests | |
| Normalisation and silence audit | DONE | VAD trim + -23 LUFS, plus a second 30 dB trim at the CM input after the first version failed rule 4 (silence cue 24.3% EER); now 38.1% | `python -m eval.report` |
| Run pretrained AASIST / AASIST-L on the channel set | PENDING | Wrapper done and checkpoints load; CPU scoring takes about 15 min per condition and was killed by a machine crash after 4 of 9 conditions (no partial scores kept). Do not rerun on the shared CPU; run on the GPU box. | `python -m cm.run_baselines --models aasist aasist_l` (GPU or an idle machine) |
| Run pretrained SSL + AASIST | PENDING | checkpoint is on Google Drive (TakHemlata README, manual) and XLS-R is too slow for CPU at this scale | download `LA_model.pth` by hand, then score with `cm/teacher/model.py: build_teacher` on a GPU |
| Day-1 tweet table "SOTA vs Indic phone clones" | PARTIAL | ASVspoof-proxy table exists for the 8 kHz GMM and LCNN; AASIST columns, Indic pilot scoring and the Gnani-clone column are pending | `python -m eval.indic_report` after the AASIST run |

## Day 2: train the telephony-native CM

| Item | Status | Notes / blocker | Command to finish |
|---|---|---|---|
| Fine-tune XLS-R 300M + AASIST at 8 kHz with codec aug + RawBoost | PENDING (GPU) | config `cm/teacher/ssl_aasist_8k.yaml`, loop `cm/teacher/train.py` (CPU smoke test passes), Modal runner | `modal run cm/teacher/modal_train.py` (setup steps in its docstring) |
| Distil to a small 8 kHz student, streaming crops, ONNX, RTF | PARTIAL | No teacher yet, so no distillation. The 8 kHz LFCC-LCNN (trained on CPU with 2 s crops) stands in: ONNX export and one-core RTF / RAM measured | after the teacher: train the student on teacher soft labels; `python -m cm.export_onnx --checkpoint <student.pt>` |
| Full eval grid, ablation (with vs without codec aug), DET curves | PARTIAL | DONE on the ASVspoof proxy for gmm8_aug and lcnn8_aug: per-condition, per-attack, pooled, streaming tables, shortcut audit, DET curves (`artifacts/det_asvspoof.png`). PENDING: the no-codec-aug ablation (`lcnn8_noaug`), wideband `gmm16_clean`, Indic grid. CPU LCNN training starved other jobs, so further CNN training moves to the GPU plan. | `modal run cm/teacher/modal_train.py` for the teacher; `python -m cm.run_baselines --models lcnn8_noaug gmm16_clean` on a GPU/idle box; then `python -m eval.report` |

## Day 3: product and story

| Item | Status | Notes / blocker | Command to finish |
|---|---|---|---|
| FastAPI service + WebSocket streaming | DONE | `/v1/cm/score`, `WS /v1/cm/stream`, `/v1/auth/enrol`, `/v1/auth/challenge`, `/v1/auth/verify`; tested with TestClient | `.\run.ps1 serve` |
| IVR demo: Timbre prompt, Prisma 8 kHz realtime phrase check, CM, ECAPA, decision codes | PARTIAL | Runs end to end on mocks (`.\run.ps1 demo`); live mode wired (1 Timbre + 1 Prisma call). ECAPA adapter written but speechbrain not installed; a placeholder ASV is used | `pip install speechbrain`, switch `LFCCStatsASV` to `EcapaASV`; `python -m ivr_demo.demo --live --caller my_8k.wav --enrol my_enrol_8k.wav` |
| Red-team: builder's own voice cloned via Gnani VC, attacked live; end-to-end attack success | PENDING (approval + recording) | needs a 15 s recording of the student's own voice and approval to spend VC credits | `python -m factory.gnani_clone --speakers factory/manifests/demo_builder_voice.csv --execute --max-calls 16` |
| REPORT.md, model and data cards | PARTIAL | MODEL_CARD.md and DATA_CARD.md done; REPORT.md text was delivered in the builder's final reply (file write was refused in-session) | paste it into REPORT.md |
| 60-second video, challenge submission, X/LinkedIn post | PENDING (student) | see checklist below | |

## Great Indian AI Internship Challenge: submission checklist (verbatim requirements from the statement, section 8)

- [ ] Deadline **10 November 2026, 11:59 PM IST**. (Internships start 1 January 2027: 6 months, stipend up to Rs 1 lakh/month, up to 100 offers.)
- [ ] Eligible: enrolled at an Indian college/university, 18+, solo or a team of two.
- [ ] Must use **at least one of Prisma v2.5 (STT), Timbre v2.5 (TTS), Evon v3.3 (LLM)**. This build uses Prisma (realtime 8 kHz phrase verification) and Timbre (prompts plus G1 attacks), with the voice-cloning API for G2/G3. Document each call in the write-up.
- [ ] Submission (1): a demo video, publicly posted.
- [ ] Submission (2): a LinkedIn and/or X post with **#GnaniAI** and **#GreatIndianAIInternshipChallenge**, posted before submission.
- [ ] Submission (3): a written explanation (problem, users, contributions).
- [ ] Submission (4): a list of the Gnani models/APIs used.
- [ ] Data rule: no real phone numbers, account numbers, Aadhaar/PAN or recorded calls; use synthetic data only. No bought engagement.
- [ ] Award fit: **Noise Canceller** (telephony audio performance), **Main Character** (regional language), **Solo Ninja**, **Demo Day Drop** (60-second video). Only one award per entrant.

Gnani models and APIs used so far (for item 4): Timbre v2.5 TTS REST (`POST /api/v1/tts/inference`, voice Nalini),
Prisma v2.5 STT REST (`POST /stt/v3`), Prisma v2.5 realtime STT (`wss://api.vachana.ai/stt/v3/stream`, 8000 Hz),
Voice Clone Embeddings (`POST /api/v1/tts/voice-clone/embeddings`), Voice Cloned TTS `vachana-vc-v1` (`container=mulaw`).
