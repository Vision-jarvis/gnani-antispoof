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

All numbers below come from `artifacts/results.md` (built by `python -m eval.report`). Setting: ASVspoof
2019 LA subsets (train 5,160 utts on A01 to A06; eval 2,560 utts: 1,000 bona fide + 1,560 spoofs from the
13 unseen attacks A07 to A19), every clip VAD-trimmed and loudness-normalised, then sent through the
channel simulator. "Held-out" = AMR-NB 4.75k, GSM-FR and two two-hop chains, never used in training.
minDCF uses pi_spf = 0.05, C_miss = 1, C_fa = 10. This is an English proxy for the channel effect, not the
statement's Indic benchmark (that needs Kathbath and the Gnani clone set, both PENDING).

| Model (8 kHz native, codec-augmented) | EER clean 8 kHz | EER seen codecs | EER held-out codecs | delta-NB | minDCF held-out | FRR@FAR1 held-out (dev threshold) | EER at 2 s, held-out |
|---|---|---|---|---|---|---|---|
| LFCC-GMM (`gmm8_aug`, 128 comp.) | 25.59% | 30.38% | 33.63% | +8.04 pts | 0.781 | 99.28% | 34.14% |
| LFCC-LCNN (`lcnn8_aug`, 170k params) | 27.64% | 30.70% | 34.42% | +6.78 pts | 0.799 | 92.47% | 34.82% |

What this shows (and does not):
- The phone line costs both CPU baselines 7 to 8 EER points on unseen codecs even though they were
  trained with codec augmentation. Per-attack, the damage is concentrated on attacks that were easy in
  clean narrowband (A08: 2.1% clean to 18.9% held-out for the LCNN; A09: 0.2% to 9.8%).
- The dev-fixed FAR = 1% threshold rejects 92% of genuine callers on held-out codecs: calibration does
  not survive the channel shift. That is the "calibration honesty" KPI, and it is bad for both baselines.
- Shortcut audit (rule 4): on raw ASVspoof audio a silence-duration-only classifier gets 17.5% EER. After
  the first normalisation the CM input still leaked silence (24.3% EER, failed the 35% rule), so a
  second trim was added at the CM input and every model was retrained and rescored; the silence cue is
  now 38.1% (loudness 42.2%, duration 40.4%). The failed first run is kept in `docs/results_v1_failed_audit.md`
  and its numbers are not reported as results.
- Student budget (statement: RTF <= 0.05 on one core, < 5M params, <= 200 MB): the LCNN exported to
  ONNX runs at RTF 0.0050 on one thread (LFCC included, 4 s clip), 170,401 parameters, 143 MB peak RAM
  (`artifacts/efficiency.json`). It is a stand-in for the distilled student, not a distilled model.
- Gnani APIs: 5 live calls verified every request/response shape used here (Timbre TTS, Prisma REST,
  Prisma realtime at 8 kHz, voice-clone embedding, VC TTS as mu-law). Prisma transcribed the Timbre
  sentence exactly; realtime server latency 265 ms. Details and doc discrepancies: `docs/gnani_api_notes.md`.

Not run (PENDING, see STATUS.md): pretrained AASIST / AASIST-L (scoring was killed by a machine crash
after 4 of 9 conditions; no partial scores are reported), wideband `gmm16_clean`, the no-augmentation
LCNN ablation, the Indic pilot scoring, the GPU teacher, and the Gnani clone attack set.

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
| `STATUS.md`, `UNDERSTAND.md`, `MODEL_CARD.md`, `DATA_CARD.md` | status and challenge checklist, interview prep, cards (REPORT.md: text supplied separately, see STATUS.md) |

Layout note: the statement's `gnani-armour-cm/` deliverable tree maps onto this repo as `factory/`,
`cm/`, `service/`, `ivr_demo/`, `eval/`, with `gnani_api/` split out of `factory/gnani_clone.py`.
