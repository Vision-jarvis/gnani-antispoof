# Status (2026-10-24; own-voice kit and Nov 1 run sheet added 2026-10-29)

Legend: DONE = built and verified in this repo; PARTIAL = built, part of it blocked; PENDING = blocked, with
the blocker and the exact command; DEFERRED = deliberately not done now, with the reason.

## Response to the critique (`critiques/05-gnani.md`)

| ID | Status | What changed / what is left |
|---|---|---|
| B1 SOTA numbers missing | FIXED (measured) | Modal A10, 2026-10-23, $0.60: held-out pooled EER AASIST 39.22%, AASIST-L 37.13%, SSL+AASIST 20.97% [19.93, 21.96] (clean 16 kHz 23.65 / 21.57 / 9.15). Rows in `artifacts/results.md`, REPORT.md section 3, score files in `release/scores/`. |
| B2 demo genuine path | FIXED | Named dev-fixed operating points (`cm.calibrate`: far1, min_dcf, eer, bayes). `python -m ivr_demo.trials` runs `verify()` on real ASVspoof clips: G.711 far1 genuine 32.5% / attack 11.0%, min_dcf 88.5% / 62.5%; AMR-NB 4.75 far1 4.5% / 1.0%, min_dcf 75.5% / 55.5% (`artifacts/ivr_trials_asvspoof.md`). The demo uses real clips, prints its operating point and these rates, and is not scripted (at far1 the genuine caller is rejected; at min_dcf the spoof gets in). |
| B3 circular audit | FIXED | Audit cues now use gates tighter than the trim gate, WebRTC VAD silence and non-speech fraction, low-energy fraction, loudness and duration. Also fixed: EER broke ties optimistically (a constant score had 0% EER). Rerun: every CM-input cue >= 37.0% (`artifacts/results.md`); the critique's 28.2% was the tie bug (38.2% with BOSARIS ties). No retrain needed; record in `docs/results_v2_audit_ties.md`. |
| B4 cloning corpus speakers | FIXED (plan) / DEFERRED (Kathbath cloning) | `factory/gnani_clone.py` refuses any speakers row without `consent` = self or written. G1/G3 from Timbre stock voices via `--languages`. Kathbath-speaker cloning DEFERRED pending written consent clearance from Gnani (ask on the challenge support channel). Statement Part A and section 9 updated. |
| M1 weak baselines | PARTIAL | Bootstrap 95% CIs on every pooled EER. Run on CPU: ablation `lcnn8_noaug` (held-out EER 41.84%, delta-NB +15.25 vs +6.78 with codec aug) and wideband `gmm16_clean` (held-out 44.73%, delta-NB +20.63 vs clean 16 kHz). DEFERRED: official-size GMM (512 components, all frames; CPU overnight: edit `cm/gmm.py` defaults, delete `artifacts/models/gmm8_aug.npz`, `python -m cm.run_baselines --models gmm8_aug`). |
| M2 causality | FIXED | `causal_cm_input` on the prefix only; `CMScorer.prefix_llr` used by batch partials and the WebSocket; streaming eval recomputed with prefix-first processing; test pins batch == WS and future-independence. |
| M3 teacher script | FIXED (measured) | v1 (2026-10-23, $4.16) did not learn (dev EER 42 to 45%: random back end at lr 1e-6, class weights for a 9:1 pool, SpecAugment on); fixed in 501d698. v2 (2026-10-24, L40S, three segments after local network drops, $4.62): dev EER 8.42% (init) to 2.28% (epoch 9). Eval: clean 8 kHz 23.34%, held-out 21.63% [20.03, 22.71], delta-NB -1.71, minDCF 0.381; not distinguishable from SSL+AASIST on held-out EER; lost unseen attacks A07/A10/A11. Distilled student `lcnn8_distil`: held-out 34.63% vs 34.42% for `lcnn8_aug` (no gain). Weights `artifacts/models/teacher_ssl_aasist_8k.pt` (1.26 GB, git-ignored). PENDING: teacher streaming cells (`--eval all`, about $1.50). |
| M4 reproducibility | FIXED | `release/` (14.5 MB): ONNX, LCNN, distilled student, GMM, calibration, gzipped scores of every model including the GPU rows (SOTA, teacher), manifests, audit, 120-clip G.711 pack. A fresh `git clone` + `.\run.ps1 report` reproduces `artifacts/results.md`; the demo and `ivr_demo.trials --pack` run from a clone. REPORT.md rewritten 2026-10-24. |
| M5 Indic / Gnani gap | PARTIAL | Indic pilot measured (`artifacts/indic_pilot.md`): published models and LCNNs near chance (45 to 50% EER), GMM 18 to 33%, but the set FAILS its shortcut audit (duration alone 16.6% raw, 20.0% on the CM input; rule >= 35%), so no model claim. Needs duration-matched bona fide. Teacher scored 2026-10-29 (A10, $0.16, `modal run --detach cm/teacher/modal_train.py::indic_main`): EER 32.0 to 47.1% (nb_pcm 34.39 [31.94, 36.84], GSM-FR 32.04 [29.22, 34.04]), FAR at its dev threshold 28 to 100%; no model claim (duration alone 16.6%). G1/G3 Timbre plan: 240 calls (dry run). Own-voice G2: needs the student's 15 s recording. |
| M6 schedule | FIXED | Statement header: Nov 1-3, submit by Nov 5 to 8 (deadline Nov 10, 11:59 PM IST). |
| M7 challenge rules | PARTIAL | Checklist below. Live run needs `GNANI_MODE=live` and 2 to 4 live calls; Evon not used (no public API page). |
| M8 streaming trials | FIXED | Streaming rows only on clips with >= t s of trimmed speech, with the full-clip EER on the same trials; the 4 s row has 4 bona fide clips and is flagged unreadable. |
| M9 DM / tweet | FIXED | Section 11 rewritten: measured proxy hook, 4-line DM, GPU and own-voice lines gated on the real runs. |
| m1 delta-NB definition | FIXED | Stated in README.md next to the number. |
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
| `gnani_clone.py` G2/G3 own voice | PENDING (recording, Nov 1) | the takes of `docs/RECORDING.md` (reference at `data/own_voice/builder_15s.wav`); the clone says the 15 answer texts, text-matched to the genuine takes | `python -m factory.gnani_clone --speakers factory/manifests/demo_builder_voice.csv --execute --max-calls 16` (dry run: 16 calls, 644 characters) |
| `gnani_clone.py` Kathbath G2 | DEFERRED | consent clearance from Gnani | none until Gnani answers in writing |
| Channel simulator | DONE | 14 conditions, about 30 test cases | |
| Normalisation and audit | DONE | | `python -m eval.report` |
| Pretrained AASIST / AASIST-L / SSL+AASIST | DONE | | Modal A10, $0.60 (REPORT.md section 8) |
| Teacher fine-tune at 8 kHz | DONE (full clips) | streaming cells not scored | `modal run --detach cm/teacher/modal_train.py --epochs 10 --patience 2 --eval all` (reuses epochs) |
| Distilled student, ONNX, RTF | DONE (no gain) | | `lcnn8_distil` held-out 34.63% vs 34.42%; same architecture as `lcnn8_aug`, so the ONNX budget is unchanged; not exported because it did not win |
| Eval grid, ablation, DET | DONE | | `python -m eval.report`, `python -m eval.det` |
| FastAPI + WebSocket | DONE | | `.\run.ps1 serve` |
| IVR demo with stated operating point | DONE (mock Gnani, real audio); own-voice live path rehearsed in mock | live run needs 4 calls | `docs/DEMO_RUNBOOK.md`, 18:00 |
| Red-team own-voice clone | PENDING (recording, Nov 1) | | own-voice row above, `python scripts/prep_own_voice.py trialsets`, `python -m ivr_demo.trials --bona-dir data/own_voice/trials/g711u/bona --spoof-dir data/own_voice/trials/g711u/spoof --tag ownvoice_g711u` (and `amrnb_4k75`), teacher via `cm/teacher/modal_train.py::ownvoice_main` or `python -m cm.teacher.score_folder --device cpu` |
| REPORT.md, model and data cards | DONE | | REPORT.md rewritten 2026-10-24 with SOTA, teacher, student, Indic pilot caveat and actual GPU cost |

## GPU runs (Modal; prices checked 2026-10-20 on modal.com/pricing)

One-time: `bash scripts/modal_setup.sh` (pip install modal, `modal setup` login, uploads about 4.2 GB of stores
and manifests only; never `.env`). Then:

| Job | Command | GPU | Estimate | Hard cap (timeout x price) |
|---|---|---|---|---|
| Throughput dry run | `modal run cm/modal_pretrained.py --limit 20` | A10 | a few minutes, cents | same |
| SOTA scoring (B1) | DONE 2026-10-23 | A10 | measured 0.40 h, $0.60 (+ $0.04 dry run) | |
| Teacher plumbing check | DONE on v1 (`--epochs 1`: 0.986 h, $2.55; about 7 min training, about 50 min scoring) | L40S + 8 CPU + 32 GiB ($2.58/h) | not needed again | 6 h = $15.50 |
| Teacher v2 (M3), cheap pass | DONE 2026-10-24 (`--epochs 10 --patience 2 --eval full`) | L40S | measured $4.62 over three segments (Modal billing) | |
| Teacher v2, streaming cells | same with `--eval all` (reuses epochs and cells) | same | about 0.5 to 0.7 h, $1.30 to $1.80 (re-scores dev per reused epoch, then 26 min of 1/2/4 s cells) | same |
| Teacher v2, full recipe | `.\run.ps1 gpu-teacher` (patience 4, every cell) | same | 1.9 to 2.5 h, $5 to $6.50 | same |
| Plain VM (one GCE GPU) | `python gce_run.py score` then `python gce_run.py teacher --epochs 1` and `python gce_run.py teacher` | any CUDA GPU | same work as above; estimates above are for A10 / L40S | none (VM billed until deleted) |
| Teacher v2 on own-voice trials | PENDING (Nov 1): `modal volume put gnani-cm-data data/own_voice/trials /ownvoice/trials`, `modal run --detach cm/teacher/modal_train.py::ownvoice_main`, `::ownvoice_fetch`, then `modal volume rm -r gnani-cm-data /ownvoice` | A10 | about 5 to 10 min, $0.10 to $0.20 (CPU alternative: 44 s for 60 clips on the laptop) | 20 min = $0.47 |
| Teacher v2 on the Indic pilot | DONE 2026-10-29 (`modal run --detach cm/teacher/modal_train.py::indic_main`, then `::indic_fetch` and `python -m eval.indic_report`) | A10 | measured 0.084 h, $0.12 by its clock, $0.16 billed | 40 min = $0.95 |
| Distil (CPU) | DONE (`python -m cm.distil`) | none | measured 34 min training + about 30 min scoring at 4 threads | |

Actual Modal spend for this build: about $9.58 (SOTA $0.64, teacher v1 $4.16 superseded, teacher v2 $4.62, teacher Indic pilot $0.16), inside the $30 Starter credit and the statement's $50 budget.

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
2. DONE: SOTA scoring, Indic pilot report, teacher v2, distillation; README/REPORT refreshed (2026-10-24). Teacher row on the Indic pilot (2026-10-29).
3. Oct 30: 2-minute test recording (`docs/RECORDING.md`), full mock rehearsal (`docs/DEMO_RUNBOOK.md`). Nov 1: record the real takes, then the timed run sheet in `docs/DEMO_RUNBOOK.md` (clone 16 calls, teacher scoring, trials on G.711 and AMR-NB, Prisma v2.5 vs v3.0 on 10 Hinglish answers (20 calls), live IVR (4 calls)), reading the credit balance before and after.
4. Optional, credits permitting: the 240-call Timbre G1/G3 plan, then score it.
5. Optional: teacher streaming rows (`modal run --detach cm/teacher/modal_train.py --epochs 10 --patience 2 --eval all`), and a duration-matched Indic set before quoting any Indic number.
6. Live demo (Nov 1, 18:00): `python -m ivr_demo.demo --live --new-challenge --language hi-IN` (1 Timbre call), record the answer to that phrase, `python scripts/prep_own_voice.py --only live_answer`, then `python -m ivr_demo.demo --live --caller data/own_voice/16k/live_answer.wav --clone --operating-point min_dcf` (1 VC TTS + 2 Prisma sessions). Record it with the key masked; the operating point is printed on screen; keep the real outcome. The identity gate is bypassed (ECAPA PENDING), so posts must not say a speaker model checks the caller.
7. Post (X + LinkedIn, both hashtags), then submit on gnani.ai/internship with the video, post link, write-up and API list. Award fit: Noise Canceller (telephony audio) or Main Character (regional language); one award per entrant.

Gnani models and APIs used (for the write-up): Timbre v2.5 TTS REST (`POST /api/v1/tts/inference`), Prisma v2.5
STT REST (`POST /stt/v3`), Prisma v2.5 realtime STT (`wss://api.vachana.ai/stt/v3/stream`, 8000 Hz), Voice Clone
Embeddings (`POST /api/v1/tts/voice-clone/embeddings`) and Voice Cloned TTS `vachana-vc-v1` (`container=mulaw`),
the last two listed as extras beyond the required models. Evon v3.3: not used (no public API page).
