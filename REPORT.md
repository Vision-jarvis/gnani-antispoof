# Report: telephony-native anti-spoofing for Armour365 (state on 2026-10-21)

Built with AI coding agents from my problem statement (problems/05-gnani.md); every number here was produced by code in this repo and is reproducible from `release/` (`.\run.ps1 report`). English proxy only: no Indic or Gnani-clone result exists yet.

## 1. Question
How much does an 8 kHz phone channel hurt a voice anti-spoofing countermeasure, does a dev-fixed threshold survive it, and can an IVR flow on Gnani Prisma + Timbre state an honest operating point?

## 2. Data and protocol
- ASVspoof 2019 LA subsets (ODC-By): train 5,160 (A01 to A06), dev 2,020 (thresholds, calibration, model selection only), eval 2,560 (1,000 bona fide; 120 per unseen attack A07 to A19). Speakers disjoint.
- Every clip: energy-VAD trim (50 ms margin), -23 LUFS, then real ffmpeg codecs: 10 seen conditions and 4 held-out (AMR-NB 4.75k, GSM-FR, AMR-NB then G.711, GSM then G.711 A-law with 2% loss). Every CM re-trims its input at 30 dB.
- Metrics: ROCCH EER (BOSARIS ties), minDCF (pi 0.05, C_miss 1, C_fa 10), Cllr/minCllr of dev-calibrated LLRs, FRR at the dev FAR 1% threshold; 95% utterance-bootstrap intervals (200 resamples).
- delta-NB = EER(held-out) minus EER(clean pool), same utterances; the clean pool is nb_pcm (8 kHz) for 8 kHz models and clean 16 kHz for gmm16_clean.

## 3. Results (artifacts/results.md)
| Model | EER clean | EER seen | EER held-out [95% CI] | minDCF held-out | FRR@FAR1 held-out | delta-NB |
|---|---|---|---|---|---|---|
| LFCC-GMM 8 kHz, codec-aug | 25.59 | 30.38 | 33.63 [32.29, 34.81] | 0.781 | 99.28 | +8.04 |
| LFCC-LCNN 8 kHz, codec-aug | 27.64 | 30.70 | 34.42 [33.04, 35.60] | 0.799 | 92.47 | +6.78 |
| LFCC-LCNN, no codec aug (ablation) | 26.59 | 35.17 | 41.84 [40.63, 42.86] | 0.943 | 98.45 | +15.25 |
| LFCC-GMM clean 16 kHz (wideband control) | 24.10 | 41.63 | 44.73 [43.53, 45.97] | 0.998 | 100.00 | +20.63 |

- Per attack (LCNN aug, clean / held-out): A08 2.12/18.86, A09 0.22/9.78, A17 4.84/19.00; attacks never caught (A07, A10, A12, A16) carry no codec signal.
- Streaming, causal, clips with >= t s of speech (full clip on same trials): LCNN held-out 1 s 39.41 (34.39), 2 s 35.36 (33.53); the 4 s row has 4 bona fide clips and is unreadable.

## 4. IVR flow at stated operating points (artifacts/ivr_trials_asvspoof.md)
200 + 200 real eval clips per codec, echo STT, identity gate bypassed. Genuine / attack accepted: G.711 far1 32.5/11.0, min_dcf 88.5/62.5, eer 84.5/49.0; AMR-NB 4.75k far1 4.5/1.0, min_dcf 75.5/55.5, eer 57.5/33.5. No point meets genuine >= 90% with attack <= 5%. Median local latency about 30 ms.

## 5. Rigor
Shortcut audit: raw silence 17.54%; on the CM input every cue >= 37.0% (silence at trim gate 36.95, at 25 dB 38.24, WebRTC VAD silence 43.64, non-speech fraction 40.10, loudness 42.24, duration 40.53). Defects found and fixed: circular audit gate, optimistic EER ties (docs/results_v2_audit_ties.md). Causal streaming shared by batch and WebSocket (tested). Thresholds fixed on dev.

## 6. Efficiency
LCNN in ONNX: 170,401 params, RTF 0.0050 on one thread, 143 MB peak RAM. A stand-in for the distilled student.

## 7. GPU-hours
None yet. Planned: SOTA scoring on A10 (estimate $0.70 to $1.10, cap $2.84), teacher on L40S ($4 to $6.50, cap $15.50); measured cost lands in artifacts/scores/*_cost.json.

## 8. Limitations
Simulated channels; English 2019-era data; small CPU baselines; placeholder ASV; IndicSynth (CC-BY-NC) eval-only. See MODEL_CARD.md, DATA_CARD.md, DATA.md.
