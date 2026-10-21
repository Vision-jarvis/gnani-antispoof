# Telephony-native voice anti-spoofing for Armour365 (Gnani.ai problem 05)

**How this was built.** I wrote the problem statement (problems/05-gnani.md), the metrics and the honesty
rules. AI coding agents (Claude Code) wrote the code to that spec; I reviewed it, re-ran the numbers below on
my machine, and can walk through any module.

A countermeasure (CM) stack for catching TTS and voice-conversion clones after the audio has gone
through an 8 kHz phone line, plus a random-phrase voice-auth IVR flow built on Gnani Prisma STT and
Timbre TTS that returns Armour365's decision codes. Built for the Great Indian AI Internship Challenge.
Everything below ran on CPU; the GPU jobs (published SOTA models, the XLS-R teacher) are one `modal run`
command each and are PENDING (STATUS.md has the commands and verified cost caps).

## Quickstart (Windows, PowerShell)

```powershell
.
un.ps1 setup        # .venv, CPU torch, requirements, clones clovaai/aasist and SSL_Anti-spoofing into third_party/
.
un.ps1 quick        # under 5 minutes: unit tests + teacher smoke + IVR demo (real clips) + tables, works on a fresh clone via release/
.
un.ps1 trials       # IVR flow on real ASVspoof clips at the dev-fixed operating points
.
un.ps1 report       # rebuild artifacts/results.md (restores release/ first on a fresh clone)
.
un.ps1 pipeline     # full CPU pipeline from raw data (hours; resumable)
.
un.ps1 serve        # FastAPI on :8000 (/v1/cm/score, WS /v1/cm/stream, /v1/auth/*)
.
un.ps1 gpu-pretrained   # Modal: AASIST, AASIST-L, SSL+AASIST on every condition (about $1, cap $2.84)
.
un.ps1 gpu-teacher      # Modal: XLS-R + AASIST teacher at 8 kHz (about $4 to $6.50, cap $15.50)
```
`release/` (10.5 MB, committed) holds the trained CPU models, calibration, gzipped scores, manifests and a
120-clip G.711 eval pack, so a fresh clone reproduces `artifacts/results.md` exactly. Raw data:
`bash scripts/download_data.sh`; gated sets in `data/README.md`; licences in `DATA.md`. The Gnani key is
read from `.env` (git-ignored). No test touches the network; `.
un.ps1 live-test` makes 2 real calls.

## Results so far (real runs in this repo)

From `artifacts/results.md` (`python -m eval.report`). Setting: ASVspoof 2019 LA subsets (train 5,160 utts,
A01 to A06; eval 2,560 utts: 1,000 bona fide + 1,560 spoofs from the 13 unseen attacks A07 to A19), every clip
VAD-trimmed and loudness-normalised, then sent through the channel simulator. "Held-out" = AMR-NB 4.75k,
GSM-FR and two two-hop chains, never used in training. This is an **English proxy** for the channel effect,
not the statement's Indic benchmark. Brackets: 95% utterance-bootstrap interval.

| Model (8 kHz native, codec-augmented) | EER clean 8 kHz | EER seen codecs | EER held-out codecs | delta-NB | minDCF held-out | FRR@FAR1 held-out (dev threshold) |
|---|---|---|---|---|---|---|
| LFCC-GMM (`gmm8_aug`, 128 comp.) | 25.59% [24.08, 27.19] | 30.38% | 33.63% [32.29, 34.81] | +8.04 pts | 0.781 | 99.28% |
| LFCC-LCNN (`lcnn8_aug`, 170k params) | 27.64% [25.94, 29.10] | 30.70% | 34.42% [33.04, 35.60] | +6.78 pts | 0.799 | 92.47% |
| Ablation: LFCC-LCNN, no codec augmentation (`lcnn8_noaug`) | 26.59% [24.95, 27.94] | 35.17% | 41.84% [40.63, 42.86] | +15.25 pts | 0.943 | 98.45% |
| Wideband control: LFCC-GMM trained on clean 16 kHz (`gmm16_clean`), 8 kHz audio upsampled | 24.10% (clean 16 kHz) | 41.63% | 44.73% [43.53, 45.97] | +20.63 pts | 0.998 | 100.00% |

delta-NB here is EER(held-out codecs) minus EER(clean **8 kHz**, `nb_pcm`), on the same utterances; the
statement defines it against clean 16 kHz, which only makes sense for wideband models (`gmm16_clean`, the
SOTA models).

**The IVR flow on real audio** (`python -m ivr_demo.trials`, 200 bona fide + 200 spoof ASVspoof eval clips
per codec, CM gate only: echo STT, identity gate bypassed):

| Codec | Operating point (fixed on dev) | Genuine callers accepted | Spoofs accepted |
|---|---|---|---|
| G.711 mu-law (seen) | far1 (dev FAR 1%) | 32.5% | 11.0% |
| G.711 mu-law (seen) | min_dcf | 88.5% | 62.5% |
| AMR-NB 4.75k (held out) | far1 | 4.5% | 1.0% |
| AMR-NB 4.75k (held out) | min_dcf | 75.5% | 55.5% |

What this shows (and does not):
- Codec augmentation is what holds the line: the same LCNN without it loses 15.25 EER points on held-out codecs
  (41.84% vs 34.42% with it, same recipe and epochs), and a GMM trained on clean 16 kHz loses 20.63 points
  (44.73%, near chance).
- The phone line still costs both augmented CPU baselines 7 to 8 EER points on unseen codecs;
  the damage is concentrated on attacks that were easy in clean narrowband (LCNN A08: 2.1% to 18.9%; A09:
  0.2% to 9.8%; A17: 4.8% to 19.0%).
- A threshold fixed on dev does not survive the channel: at FAR = 1% the CM rejects 92% of genuine callers on
  held-out codecs, and no operating point meets "genuine >= 90% with attack <= 5%". The demo shows this
  honestly and names its operating point; it is not scripted.
- Both baselines are weak (official 16 kHz LFCC-GMM: about 8% EER); the codec effect is only readable on the
  attacks they catch. The SOTA columns come from the GPU job.
- Streaming is causal (trim and loudness from the received prefix only, identical in batch and WebSocket)
  and reported only on clips with at least t s of speech: LCNN at 2 s, held-out pool, 35.36% vs 33.53% for the
  full clip on the same trials.
- Shortcut audit (rule 4): raw silence alone gives 17.5% EER; on the CM input every cue, including an
  independent WebRTC VAD and tighter gates than the trim, is at least 37.0%. An earlier audit was circular
  and EER mishandled ties; both are fixed and documented (`docs/results_v2_audit_ties.md`).
- Student budget: the LCNN in ONNX runs at RTF 0.0050 on one thread, 170,401 parameters, 143 MB peak RAM.
  It is a stand-in; `cm/distil.py` trains the distilled student once the teacher exists.
- Gnani APIs: 5 live calls verified every request/response shape used (Timbre, Prisma REST and realtime
  8 kHz, voice-clone embedding, VC TTS as mu-law); `docs/gnani_api_notes.md`.
- Consent: clones are made only of the builder's own voice and consenting friends; cloning corpus speakers
  is deferred until Gnani confirms in writing that it is allowed. No cloned clip is published.

PENDING (STATUS.md): SOTA columns (GPU), Indic pilot report, Gnani clone set, teacher and distilled student.

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
| `cm/teacher/` | XLS-R 300M + AASIST teacher: training + eval scoring loop (CPU smoke test), Modal runner (PENDING GPU) |
| `eval/metrics.py`, `eval/protocol.py`, `eval/shortcut_audit.py` | ROCCH EER, minDCF, Cllr, FRR@FAR1; held-out attack/codec rules; shortcut audit |
| `eval/report.py`, `eval/points.py`, `eval/det.py`, `eval/indic_report.py` | tables, points matrix, DET curves, Indic pilot |
| `ivr_demo/` | challenge phrases, phrase match, ASV stand-in, fused Armour365 decision, demo (mock or live) |
| `service/app.py` | FastAPI with the statement's interfaces |
| `docs/gnani_api_notes.md` | live-verified API shapes and where they differ from the docs |
| `cm/score_pretrained.py`, `cm/ssl_pretrained.py`, `cm/modal_pretrained.py` | published SOTA scoring (fairseq-free SSL+AASIST loader), Modal job |
| `cm/distil.py`, `cm/release.py`, `ivr_demo/trials.py` | distilled student, committed release slice, IVR trials on real audio |
| `STATUS.md`, `UNDERSTAND.md`, `REPORT.md`, `MODEL_CARD.md`, `DATA_CARD.md`, `DATA.md` | status per critique finding and challenge checklist, interview prep, report, cards, licences |

Layout note: the statement's `gnani-armour-cm/` deliverable tree maps onto this repo as `factory/`,
`cm/`, `service/`, `ivr_demo/`, `eval/`, with `gnani_api/` split out of `factory/gnani_clone.py`.
