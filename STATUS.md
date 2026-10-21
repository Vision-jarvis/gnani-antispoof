# Status (2026-10-20)

Legend: DONE = built and verified in this repo; PARTIAL = built, part of it blocked; PENDING = blocked, with
the blocker and the exact command; DEFERRED = deliberately not done now, with the reason.

## Response to the critique (`critiques/05-gnani.md`)

| ID | Status | What changed / what is left |
|---|---|---|
| B1 SOTA numbers missing | PARTIAL (tooling FIXED, run PENDING GPU) | `cm/score_pretrained.py` scores AASIST, AASIST-L and SSL+AASIST (`LA_model.pth`, loaded without fairseq by `cm/ssl_pretrained.py`, strict load verified, CPU sanity check 0/50 errors on dev) on all 15 conditions + the Indic pilot, one part file per cell. One command: `.\run.ps1 gpu-pretrained` (about $1, cap $2.84). The hook was rewritten to the measured English-proxy result. |
| B2 demo genuine path | FIXED | Named dev-fixed operating points (`cm.calibrate`: far1, min_dcf, eer, bayes). `python -m ivr_demo.trials` runs `verify()` on real ASVspoof clips: G.711 far1 genuine 32.5% / attack 11.0%, min_dcf 88.5% / 62.5%; AMR-NB 4.75 far1 4.5% / 1.0%, min_dcf 75.5% / 55.5% (`artifacts/ivr_trials_asvspoof.md`). The demo uses real clips, prints its operating point and these rates, and is not scripted (at far1 the genuine caller is rejected; at min_dcf the spoof gets in). |
| B3 circular audit | FIXED | Audit cues now use gates tighter than the trim gate, WebRTC VAD silence and non-speech fraction, low-energy fraction, loudness and duration. Also fixed: EER broke ties optimistically (a constant score had 0% EER). Rerun: every CM-input cue >= 37.0% (`artifacts/results.md`); the critique's 28.2% was the tie bug (38.2% with BOSARIS ties). No retrain needed; record in `docs/results_v2_audit_ties.md`. |
| B4 cloning corpus speakers | FIXED (plan) / DEFERRED (Kathbath cloning) | `factory/gnani_clone.py` refuses any speakers row without `consent` = self or written. G1/G3 from Timbre stock voices via `--languages`. Kathbath-speaker cloning DEFERRED pending written consent clearance from Gnani (ask on the challenge support channel). Statement Part A and section 9 updated. |
| M1 weak baselines | PARTIAL | Bootstrap 95% CIs on every pooled EER; `lcnn8_noaug` ablation and wideband `gmm16_clean` run on CPU (see README table). DEFERRED: official-size GMM (512 components, all frames; CPU overnight: edit `cm/gmm.py` defaults, delete `artifacts/models/gmm8_aug.npz`, `python -m cm.run_baselines --models gmm8_aug`). |
| M2 causality | FIXED | `causal_cm_input` on the prefix only; `CMScorer.prefix_llr` used by batch partials and the WebSocket; streaming eval recomputed with prefix-first processing; test pins batch == WS and future-independence. |
| M3 teacher script | FIXED (code) / PENDING (GPU run) | `cm/teacher/train.py` checkpoints per epoch, early-stops, scores dev, all eval conditions x (full, causal 1/2/4 s) and the train pool, writes GPU hours; smoke test covers scoring. `cm/distil.py` (soft-BCE LCNN student) written and smoke-tested. Yaml fixed. One command: `.\run.ps1 gpu-teacher` (about $4 to $6.50, cap $15.50). |
| M4 reproducibility | FIXED | `release/` (9.3 MB): ONNX, LCNN, GMM, calibration, gzipped scores, manifests, audit, 120-clip G.711 pack. Verified: a fresh `git clone` + `.\run.ps1 report` reproduces `artifacts/results.md` byte for byte; the demo and `ivr_demo.trials --pack` run from a clone. REPORT.md expanded. |
| M5 Indic / Gnani gap | PARTIAL | Indic pilot report runs as soon as the GPU scoring job returns the SOTA columns (`python -m eval.indic_report`, CPU part 10 min). G1/G3 Timbre plan: 240 calls (dry run). Own-voice G2: needs the student's 15 s recording. |
| M6 schedule | FIXED | Statement header: Nov 1-3, submit by Nov 5 to 8 (deadline Nov 10, 11:59 PM IST). |
| M7 challenge rules | PARTIAL | Checklist below. Live run needs `GNANI_MODE=live` and 2 to 4 live calls; Evon not used (no public API page). |
| M8 streaming trials | FIXED | Streaming rows only on clips with >= t s of trimmed speech, with the full-clip EER on the same trials; the 4 s row has 4 bona fide clips and is flagged unreadable. |
| M9 DM / tweet | FIXED | Section 11 rewritten: measured proxy hook, 4-line DM, GPU and own-voice lines gated on the real runs. |
| m1 delta-NB definition | FIXED | Stated in REPORT.md next to the number. |
| m2 minCllr | FIXED | Copied into every cell and shown in the pooled table. |
| m3 statement facts | FIXED | Ganesh Gopalan, Kathbath licence note; Evon noted as having no public API page. |
| m4 hygiene | FIXED | "about 30 cases" for the simulator tests; user paths scrubbed from tracked logs; `gnani_probe.json` stays tracked on purpose (no secrets: transcripts, request ids, header names) as evidence for the API list. |
| m5 crash resilience | FIXED | Per-cell part files, reused on rerun, for LFCC models, AASIST, the SOTA job and the teacher. |
| m6 ASV placeholder | PARTIAL / DEFERRED | Demo and trials bypass the identity gate and print no ASV score. DEFERRED: ECAPA needs a matching torchaudio wheel and a model download (`pip install speechbrain torchaudio`, then use `EcapaASV`). |
| m7 config drift | FIXED | Yaml marks PENDING sets; UNDERSTAND.md sections 6 and 9 rewritten. |
| m8 codec-native packet loss | DEFERRED | Needs a new eval condition (ffmpeg libopus `-packet_loss`/`-fec`) and a store rebuild (about 1 h CPU); it does not change any current claim. |

## 3-day cut checklist (statement section 9)

| Item | Status | Blocker | Command to finish |
|---|---|---|---|
| Credits, cost per call | PARTIAL | API returns no usage data; 5 probe calls made | read the balance on app.gnani.ai before and after the G1 run |
| ASVspoof 2019 LA | DONE | | |
| ASVspoof 2021 LA eval | PARTIAL | download interrupted | `bash scripts/download_data.sh` |
| Kathbath Hindi + Kannada | PENDING | gated (accept terms on HF) | `data/README.md` step 2 (bona fide only; cloning DEFERRED) |
| IndicSynth slice | DONE | | |
| `gnani_clone.py` G1/G3 Timbre stock voices | PENDING (credits) | student decision on the spend | `python -m factory.gnani_clone --languages kn-IN hi-IN --execute --max-calls 240` |
| `gnani_clone.py` G2/G3 own voice | PENDING (recording) | 15 s consented recording at `data/own_voice/builder_15s.wav` | `python -m factory.gnani_clone --speakers factory/manifests/demo_builder_voice.csv --execute --max-calls 16` |
| `gnani_clone.py` Kathbath G2 | DEFERRED | consent clearance from Gnani | none until Gnani answers in writing |
| Channel simulator | DONE | 14 conditions, about 30 test cases | |
| Normalisation and audit | DONE | | `python -m eval.report` |
| Pretrained AASIST / AASIST-L / SSL+AASIST | PENDING (GPU) | Modal account | `bash scripts/modal_setup.sh`, then `.\run.ps1 gpu-pretrained` |
| Teacher fine-tune at 8 kHz | PENDING (GPU) | Modal account | `.\run.ps1 gpu-teacher` |
| Distilled student, ONNX, RTF | PARTIAL | teacher | `python -m cm.distil`, then `python -m cm.export_onnx --checkpoint artifacts/models/lcnn8_distil.pt` |
| Eval grid, ablation, DET | PARTIAL | GPU models pending | `python -m eval.report`, `python -m eval.det` |
| FastAPI + WebSocket | DONE | | `.\run.ps1 serve` |
| IVR demo with stated operating point | DONE (mock Gnani, real audio) | live run needs 2 to 4 calls | see the checklist below |
| Red-team own-voice clone | PENDING (recording) | | own-voice row above, then `python -m ivr_demo.trials --bona-dir <own takes> --spoof-dir <clones> --tag ownvoice` |
| REPORT.md, model and data cards | DONE | numbers refresh after the GPU jobs | |

## GPU runs (Modal; prices checked 2026-10-20 on modal.com/pricing)

One-time: `bash scripts/modal_setup.sh` (pip install modal, `modal setup` login, uploads about 4.2 GB of stores
and manifests only; never `.env`). Then:

| Job | Command | GPU | Estimate | Hard cap (timeout x price) |
|---|---|---|---|---|
| Throughput dry run | `modal run cm/modal_pretrained.py --limit 20` | A10 | a few minutes, cents | same |
| SOTA scoring (B1) | `.\run.ps1 gpu-pretrained` | A10 + 4 CPU + 16 GiB ($1.42/h) | 30 to 45 min, $0.70 to $1.10 | 2 h = $2.84 |
| Teacher plumbing check | `modal run cm/teacher/modal_train.py --epochs 1` | L40S + 8 CPU + 32 GiB ($2.58/h) | about 25 min, about $1 | 6 h = $15.50 |
| Teacher (M3) | `.\run.ps1 gpu-teacher` | same | 1.5 to 2.5 h, $4 to $6.50 | 6 h = $15.50 |
| Distil (CPU) | `python -m cm.distil` | none | about 1 h at 4 threads | |

Total expected about $6 to $9, inside the $30 Starter credit and the statement's $50 budget. Both jobs print
and save wall hours and dollars (`artifacts/scores/*_cost.json`); put them in REPORT.md.

## Great Indian AI Internship Challenge checklist (deadline Nov 10, 2026, 11:59 PM IST; submit by Nov 5 to 8)

What is real today:
- [x] Uses Prisma v2.5 (REST + realtime 8 kHz) and Timbre v2.5: 5 live calls verified the shapes (`docs/gnani_api_notes.md`); the IVR flow calls both.
- [x] Working application: FastAPI service + IVR flow; the decision logic and CM run on real audio (`ivr_demo.trials`).
- [x] Synthetic-data rule: no real phone numbers, accounts or recorded calls; clones only of consenting voices.
- [ ] Demo video (60 s), publicly posted.
- [ ] X and LinkedIn post with **#GnaniAI** and **#GreatIndianAIInternshipChallenge**, posted BEFORE submitting.
- [ ] Written explanation: problem, users, contributions (solo), plus "built with AI coding agents from my spec".
- [ ] List of Gnani models/APIs used (below).

Exact remaining steps, in order:
1. Rotate the Gnani API key (it has been in agent sessions); put the new one in `.env`.
2. Modal: `bash scripts/modal_setup.sh`, `modal run cm/modal_pretrained.py --limit 20`, then `.\run.ps1 gpu-pretrained` and `python -m eval.indic_report`. Refresh README/REPORT numbers.
3. Record 15 s of your own voice at `data/own_voice/builder_15s.wav` (and 5 or more short answers at 8 kHz for genuine trials). Run the 16-call own-voice plan (STATUS row above) after reading the credit balance.
4. Optional, credits permitting: the 240-call Timbre G1/G3 plan, then score it.
5. Teacher: `modal run cm/teacher/modal_train.py --epochs 1`, then `.\run.ps1 gpu-teacher`, then `python -m cm.distil`.
6. Live demo: `$env:GNANI_MODE="live"; python -m ivr_demo.demo --live --caller <answer_8k.wav> --enrol <enrol_8k.wav> --operating-point min_dcf` (2 calls). Record it with the key masked; say the operating point on screen; keep the real outcome.
7. Post (X + LinkedIn, both hashtags), then submit on gnani.ai/internship with the video, post link, write-up and API list. Award fit: Noise Canceller (telephony audio) or Main Character (regional language); one award per entrant.

Gnani models and APIs used (for the write-up): Timbre v2.5 TTS REST (`POST /api/v1/tts/inference`), Prisma v2.5
STT REST (`POST /stt/v3`), Prisma v2.5 realtime STT (`wss://api.vachana.ai/stt/v3/stream`, 8000 Hz), Voice Clone
Embeddings (`POST /api/v1/tts/voice-clone/embeddings`) and Voice Cloned TTS `vachana-vc-v1` (`container=mulaw`),
the last two listed as extras beyond the required models. Evon v3.3: not used (no public API page).
