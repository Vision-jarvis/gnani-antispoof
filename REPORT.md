# Report: telephony-native anti-spoofing for Armour365 (state on 2026-10-24)

Built with AI coding agents from my problem statement (problems/05-gnani.md); every number here was produced by code in this repo. CPU tables reproduce from `release/` (`.\run.ps1 report`); the GPU rows (published SOTA, teacher) were measured on Modal and their score files are in `release/scores/`. Main results are an English proxy (ASVspoof 2019 LA). The one Indic set (section 6) fails its shortcut audit, so it supports no model ranking. No Gnani-clone result exists yet.

## 1. Question
How much does an 8 kHz phone channel hurt a voice anti-spoofing countermeasure, does a dev-fixed threshold survive it, and can an IVR flow on Gnani Prisma + Timbre state an honest operating point?

## 2. Data and protocol
- ASVspoof 2019 LA subsets (ODC-By): train 5,160 (A01 to A06), dev 2,020 (thresholds, calibration, model selection only), eval 2,560 (1,000 bona fide; 120 per unseen attack A07 to A19). Speakers disjoint.
- Every clip: energy-VAD trim (50 ms margin), -23 LUFS, then real ffmpeg codecs: 10 seen conditions and 4 held-out (AMR-NB 4.75k, GSM-FR, AMR-NB then G.711, GSM then G.711 A-law with 2% loss). Every CM re-trims its input at 30 dB.
- Metrics: ROCCH EER (BOSARIS ties), minDCF (pi 0.05, C_miss 1, C_fa 10), Cllr/minCllr of dev-calibrated LLRs, FRR at the dev FAR 1% threshold (and the FAR that threshold actually gives on eval); 95% utterance-bootstrap intervals (200 resamples).
- delta-NB = EER(held-out) minus EER(clean pool), same utterances; the clean pool is nb_pcm (8 kHz) for 8 kHz models and clean 16 kHz for the 16 kHz models (published SOTA, gmm16_clean).

## 3. Results (artifacts/results.md, all REAL runs)
| Model | EER clean | EER seen | EER held-out [95% CI] | minDCF held-out | FRR@FAR1 held-out (eval FAR at that threshold) | delta-NB |
|---|---|---|---|---|---|---|
| AASIST, published, 16 kHz | 23.65 | 37.30 | 39.22 [37.63, 40.20] | 0.855 | 92.17 (1.94) | +15.57 |
| AASIST-L, published, 16 kHz | 21.57 | 34.32 | 37.13 [35.89, 38.35] | 0.869 | 96.78 (0.29) | +15.56 |
| SSL+AASIST (XLS-R), published, 16 kHz | 9.15 | 18.45 | **20.97 [19.93, 21.96]** | 0.572 | 71.60 (1.04) | +11.83 |
| Teacher: SSL+AASIST fine-tuned at 8 kHz with codec aug | 23.34 | 24.23 | 21.63 [20.03, 22.71] | **0.381** | 7.35 (27.00) | **-1.71** |
| LFCC-GMM 8 kHz, codec-aug | 25.59 | 30.38 | 33.63 [32.29, 34.81] | 0.781 | 99.28 (0.16) | +8.04 |
| LFCC-LCNN 8 kHz, codec-aug (shipped CPU CM) | 27.64 | 30.70 | 34.42 [33.04, 35.60] | 0.799 | 92.47 (1.81) | +6.78 |
| Distilled student: same LCNN on teacher soft targets | 26.79 | 30.58 | 34.63 [33.35, 35.86] | 0.836 | 91.17 (2.80) | +7.84 |
| LFCC-LCNN, no codec aug (ablation) | 26.59 | 35.17 | 41.84 [40.63, 42.86] | 0.943 | 98.45 (0.72) | +15.25 |
| LFCC-GMM clean 16 kHz (wideband control) | 24.10 | 41.63 | 44.73 [43.53, 45.97] | 0.998 | 100.00 (0.00) | +20.63 |

- Published SOTA through the phone line: SSL+AASIST is the best pooled held-out model (20.97%), but it loses 11.8 points from clean 16 kHz, and AASIST / AASIST-L lose 15.6 points and end up worse than the 170k-parameter codec-augmented CPU LCNN (39.22 and 37.13 vs 34.42).
- Teacher (XLS-R 300M + AASIST initialised from `LA_model.pth`, fine-tuned at 8 kHz on the 10,320-example codec-augmented train pool, L40S, 10 epochs; dev EER 8.42% before fine-tuning, 2.28% at the best epoch 9). On eval it is channel-flat (delta-NB -1.71; best of all models on AMR-NB 4.75k, 15.93 vs 25.26 for SSL+AASIST, and on Opus 6k with loss, 21.99 vs 38.14) and has the best threshold-free cost (minDCF 0.381). Its pooled held-out EER (21.63%) is not distinguishable from the published SSL+AASIST (intervals overlap), and its clean EER got worse (23.34 vs 8.47 on nb_pcm): fine-tuning on A01 to A06 cost it unseen attacks (A11 7.16 to 49.84, A07 3.68 to 27.50, A10 36.05 to 49.72) while it gained on A13, A16, A17, A19 under codecs. A dev EER of 2.28% (seen attacks) says nothing about eval (unseen attacks).
- Dev thresholds do not transfer: the teacher's FAR 1% dev threshold gives 27.0% FAR on held-out codecs (FRR 7.35%); the LFCC and published models keep FAR near 1% but reject 72 to 100% of genuine callers.
- Distilled student (`lcnn8_distil`, alpha 0.5, T 2, same recipe as `lcnn8_aug`, 34 min on 4 CPU threads): no gain. Held-out 34.63% vs 34.42% (intervals overlap), clean 26.79 vs 27.64. The teacher's strength (unseen codecs) did not carry into an LFCC student; `lcnn8_aug` stays the shipped model.
- Per attack (LCNN aug, clean / held-out): A08 2.12/18.86, A09 0.22/9.78, A17 4.84/19.00; attacks never caught by the CPU models (A07, A10, A12, A16) carry no codec signal.
- Streaming, causal, clips with >= t s of speech (full clip on same trials): LCNN held-out 1 s 39.41 (34.39), 2 s 35.36 (33.53); student 2 s 35.86 (34.27); the 4 s row has 4 bona fide clips and is unreadable. The GPU models were scored on full clips only.

## 4. IVR flow at stated operating points (artifacts/ivr_trials_asvspoof.md)
200 + 200 real eval clips per codec, echo STT, identity gate bypassed, shipped `lcnn8_aug`. Genuine / attack accepted: G.711 far1 32.5/11.0, min_dcf 88.5/62.5, eer 84.5/49.0; AMR-NB 4.75k far1 4.5/1.0, min_dcf 75.5/55.5, eer 57.5/33.5. The distilled student on the same trials (`artifacts/ivr_trials_asvspoof_lcnn8_distil.md`, `--model lcnn8_distil`): G.711 far1 35.5/9.0, min_dcf 89.0/61.5, eer 86.5/49.0; AMR-NB 4.75k far1 5.0/2.0, min_dcf 76.5/50.0, eer 56.5/29.5, within a few points of `lcnn8_aug`. No point meets genuine >= 90% with attack <= 5%. Median local latency about 30 ms.

## 5. Rigor
Shortcut audit (ASVspoof): raw silence 17.54%; on the CM input every cue >= 37.0% (silence at trim gate 36.95, at 25 dB 38.24, WebRTC VAD silence 43.64, non-speech fraction 40.10, loudness 42.24, duration 40.53). Defects found and fixed: circular audit gate, optimistic EER ties (docs/results_v2_audit_ties.md), and a first teacher that did not learn (2026-10-23, dev EER 42 to 45%: random back end at lr 1e-6, wrong class weights, SpecAugment on; fixed in commit 501d698, CPU test added). Causal streaming shared by batch and WebSocket (tested). Thresholds fixed on dev.

## 6. Indic pilot (artifacts/indic_pilot.md): no model claim possible
FLEURS Hindi + Kannada bona fide (600) vs IndicSynth FreeVC spoofs (600), through 6 codecs. Every published model and the LCNNs are near chance (EER about 45 to 50%; SSL+AASIST 27.38 on AMR-NB 4.75k is the one exception). The distilled student is also near chance (42.7 to 49.4%). The LFCC-GMM looks better (18 to 33%), but the set fails the shortcut audit: duration alone separates the classes at 16.6% EER on raw audio and 20.0% on the CM input (rule: >= 35%), silence 27.7% and loudness 28.3%. A model can score well here by measuring length, so this set supports no ranking; it needs duration-matched bona fide before any Indic number is quoted. The fine-tuned 8 kHz teacher (scored 2026-10-29, Modal A10, $0.16) is at 32.0 to 47.1% EER on the six telephony conditions (nb_pcm 34.39 [31.94, 36.84], G.711 36.87 [34.48, 39.53], GSM-FR 32.04 [29.22, 34.04], AMR-NB 12.2k 43.55, AMR-NB 4.75k 47.08, chain 46.89; 95% utterance-bootstrap intervals) and, at its ASVspoof-dev threshold, accepts 28 to 100% of the spoofs; this is no model claim either, because a duration cue alone (16.6%) beats it.

## 7. Efficiency
LCNN in ONNX: 170,401 params, RTF 0.0050 on one thread, 143 MB peak RAM. The distilled student has the identical architecture, so the same budget applies; it was not exported because it did not beat `lcnn8_aug`.

## 8. GPU-hours and cost (Modal; `artifacts/scores/*_cost.json`, `modal billing report`)
| Job | GPU | Wall | Cost |
|---|---|---|---|
| Published SOTA scoring, 2026-10-23 (plus a 20-clip dry run) | A10 | 0.40 h | $0.60 + $0.04 |
| Teacher v1, 2026-10-23 (did not learn, superseded) | L40S | about 1.6 h | $4.16 |
| Teacher v2, 2026-10-24, three segments after local network drops (last segment 0.52 h, $1.35) | L40S | about 1.8 h | $4.62 |
| Teacher v2 on the Indic pilot (`cm/teacher/score_indic.py`), 2026-10-29 | A10 | 0.08 h | $0.16 |
| Total | | about 3.9 GPU-hours | about $9.58 |

Costs are from `modal billing report` for the two days (2026-10-24 read the same day, so it may still move by cents); wall hours for multi-segment runs are cost divided by the hourly price. Distillation, all LFCC models and every table ran on CPU.

## 9. Limitations
Simulated channels (closest new work on this gap: RealComm, arXiv:2610.27459, 2026-10-20, https://arxiv.org/abs/2610.27459, which shows detectors degrade badly after real mobile-call transmission; RealCommBench and RealComm-Aug are the comparison to run if access is granted; it is not Indic); English 2019-era data for every ranked number; the Indic pilot fails its shortcut audit; small CPU baselines; the teacher was fine-tuned on a subset (5,160 utterances, 10 epochs) and never scored on causal prefixes; placeholder ASV; IndicSynth (CC-BY-NC) eval-only. See MODEL_CARD.md, DATA_CARD.md, DATA.md.

Related work added 2026-10-29: arXiv:2610.07216 (2026-10-05, https://arxiv.org/abs/2610.07216) finds SOTA detectors misclassify legitimately codec-compressed bona fide speech as fake, the same effect our false-reject numbers show on unseen codecs. The IVR flow uses Prisma v2.5 (a qualifying challenge model); Prisma v3.0 (opt-in since 2026-10-22, https://docs.gnani.ai/changelog) has not been run.
