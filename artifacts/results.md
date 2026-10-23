Metrics: EER %, minDCF (pi_spf=0.05, C_miss=1, C_fa=10), Cllr (bits, dev-calibrated), FRR@FAR1 % (dev-fixed threshold).

### Pooled results (EER with a 95% utterance-bootstrap interval)

| model | pool | EER % | EER 95% CI | minDCF | Cllr | minCllr | FRR@FAR1 % | FAR at dev tau % |
|---|---|---|---|---|---|---|---|---|
| aasist | clean (clean16k) | 23.65 | 22.14 to 25.14 | 0.593 | 0.868 | 0.689 | 44.70 | 14.23 |
| aasist | seen | 37.30 | 35.81 to 38.55 | 0.819 | 1.186 | 0.873 | 89.42 | 1.81 |
| aasist | heldout | 39.22 | 37.63 to 40.20 | 0.855 | 1.366 | 0.909 | 92.17 | 1.94 |
| aasist_l | clean (clean16k) | 21.57 | 19.97 to 23.19 | 0.546 | 0.823 | 0.657 | 44.70 | 12.18 |
| aasist_l | seen | 34.32 | 32.92 to 35.62 | 0.793 | 1.271 | 0.855 | 94.38 | 0.60 |
| aasist_l | heldout | 37.13 | 35.89 to 38.35 | 0.869 | 1.616 | 0.907 | 96.78 | 0.29 |
| ssl_aasist | clean (clean16k) | 9.15 | 8.02 to 10.02 | 0.157 | 1.217 | 0.278 | 0.00 | 20.19 |
| ssl_aasist | seen | 18.45 | 17.65 to 19.06 | 0.530 | 1.460 | 0.609 | 36.16 | 6.02 |
| ssl_aasist | heldout | 20.97 | 19.93 to 21.96 | 0.572 | 2.298 | 0.638 | 71.60 | 1.04 |
| gmm16_clean | clean (clean16k) | 24.10 | 22.49 to 25.53 | 0.553 | 0.740 | 0.663 | 88.50 | 1.35 |
| gmm16_clean | seen | 41.63 | 40.36 to 43.13 | 0.954 | 3.079 | 0.959 | 100.00 | 0.00 |
| gmm16_clean | heldout | 44.73 | 43.53 to 45.97 | 0.998 | 3.142 | 0.983 | 100.00 | 0.00 |
| gmm8_aug | clean (nb_pcm) | 25.59 | 24.08 to 27.19 | 0.597 | 0.804 | 0.713 | 84.10 | 3.40 |
| gmm8_aug | seen | 30.38 | 29.24 to 31.53 | 0.715 | 0.874 | 0.807 | 93.12 | 1.53 |
| gmm8_aug | heldout | 33.63 | 32.29 to 34.81 | 0.781 | 0.874 | 0.860 | 99.28 | 0.16 |
| lcnn8_noaug | clean (nb_pcm) | 26.59 | 24.95 to 27.94 | 0.594 | 0.792 | 0.716 | 82.90 | 3.72 |
| lcnn8_noaug | seen | 35.17 | 34.05 to 36.23 | 0.800 | 0.995 | 0.877 | 91.80 | 3.20 |
| lcnn8_noaug | heldout | 41.84 | 40.63 to 42.86 | 0.943 | 1.114 | 0.958 | 98.45 | 0.72 |
| lcnn8_aug | clean (nb_pcm) | 27.64 | 25.94 to 29.10 | 0.579 | 0.925 | 0.722 | 74.20 | 6.22 |
| lcnn8_aug | seen | 30.70 | 29.45 to 31.83 | 0.706 | 1.017 | 0.801 | 79.03 | 6.05 |
| lcnn8_aug | heldout | 34.42 | 33.04 to 35.60 | 0.799 | 0.976 | 0.873 | 92.47 | 1.81 |

### delta-NB (EER held-out codecs minus EER clean pool, same utterances)

| model | delta-NB (EER points) |
|---|---|
| aasist | +15.57 |
| aasist_l | +15.56 |
| ssl_aasist | +11.83 |
| gmm16_clean | +20.63 |
| gmm8_aug | +8.04 |
| lcnn8_noaug | +15.25 |
| lcnn8_aug | +6.78 |

### EER % per channel condition

| condition | aasist | aasist_l | ssl_aasist | gmm16_clean | gmm8_aug | lcnn8_noaug | lcnn8_aug |
|---|---|---|---|---|---|---|---|
| amrnb_12k2 | 33.03 | 29.44 | 8.70 | 39.29 | 30.06 | 32.65 | 31.09 |
| amrnb_4k75 (held-out) | 39.42 | 37.54 | 25.26 | 42.24 | 34.81 | 37.80 | 32.85 |
| amrnb_7k95 | 34.85 | 31.89 | 13.01 | 41.04 | 30.92 | 34.89 | 31.45 |
| amrwb_12k65 | 32.94 | 31.04 | 8.83 | 39.41 | 30.49 | 32.97 | 30.71 |
| chain_amrnb_g711u (held-out) | 37.90 | 34.82 | 19.31 | 45.59 | 34.92 | 40.49 | 33.15 |
| chain_gsm_g711a_plc2 (held-out) | 42.33 | 37.70 | 22.12 | 45.94 | 32.42 | 42.89 | 36.06 |
| clean16k | 23.65 | 21.57 | 9.15 | 24.10 | n/a | n/a | n/a |
| g711a | 34.81 | 32.92 | 10.47 | 43.37 | 28.55 | 30.38 | 27.97 |
| g711u | 35.01 | 32.94 | 10.74 | 42.92 | 29.05 | 30.23 | 28.15 |
| g711u_plc5 | 41.85 | 37.64 | 16.52 | 42.78 | 28.72 | 31.66 | 27.23 |
| gsm_fr (held-out) | 33.51 | 30.08 | 10.22 | 42.35 | 30.41 | 38.98 | 34.29 |
| nb_pcm | 27.18 | 24.35 | 8.47 | 39.39 | 25.59 | 26.59 | 27.64 |
| opus_16k | 30.22 | 26.98 | 8.58 | 39.46 | 27.50 | 29.59 | 28.23 |
| opus_6k_plc3 | 48.47 | 45.32 | 38.14 | 42.21 | 30.95 | 41.59 | 35.53 |
| opus_8k | 37.27 | 32.38 | 15.50 | 40.02 | 28.09 | 37.36 | 32.02 |

### EER % per ASVspoof 2019 eval attack (clean pool / held-out codec pool)

| attack | aasist | aasist_l | ssl_aasist | gmm16_clean | gmm8_aug | lcnn8_noaug | lcnn8_aug |
|---|---|---|---|---|---|---|---|
| A07 | 38.76 / 42.20 | 34.93 / 42.19 | 3.68 / 24.45 | 26.33 / 47.58 | 39.01 / 41.54 | 45.87 / 49.35 | 46.84 / 47.30 |
| A08 | 1.66 / 11.25 | 2.13 / 15.35 | 0.76 / 17.68 | 4.14 / 45.61 | 2.21 / 12.68 | 1.14 / 38.63 | 2.12 / 18.86 |
| A09 | 0.28 / 12.71 | 0.54 / 12.35 | 0.00 / 15.18 | 1.98 / 36.13 | 0.09 / 7.69 | 0.47 / 31.66 | 0.22 / 9.78 |
| A10 | 47.40 / 48.62 | 47.64 / 48.87 | 36.05 / 39.77 | 36.33 / 47.55 | 44.78 / 47.33 | 44.95 / 45.72 | 45.05 / 45.56 |
| A11 | 18.16 / 35.97 | 9.94 / 31.98 | 7.16 / 27.74 | 1.84 / 34.83 | 15.35 / 36.87 | 26.27 / 41.96 | 34.26 / 41.66 |
| A12 | 42.52 / 47.92 | 45.10 / 48.15 | 15.76 / 27.36 | 41.08 / 49.35 | 40.69 / 49.29 | 37.94 / 45.71 | 38.88 / 46.75 |
| A13 | 19.54 / 48.09 | 20.19 / 47.13 | 0.00 / 11.63 | 31.35 / 45.96 | 10.34 / 24.59 | 19.87 / 38.61 | 15.47 / 25.12 |
| A14 | 7.28 / 22.16 | 3.09 / 19.29 | 0.34 / 20.40 | 12.65 / 45.34 | 17.86 / 27.90 | 26.10 / 49.85 | 22.81 / 38.78 |
| A15 | 33.43 / 35.29 | 24.19 / 34.73 | 10.13 / 23.69 | 4.22 / 47.58 | 16.18 / 24.05 | 16.59 / 47.69 | 18.72 / 33.04 |
| A16 | 13.72 / 39.16 | 17.50 / 42.11 | 1.19 / 16.89 | 39.33 / 49.91 | 44.01 / 45.42 | 44.60 / 46.68 | 38.16 / 44.48 |
| A17 | 15.75 / 45.02 | 11.30 / 39.41 | 0.83 / 11.26 | 5.14 / 32.92 | 4.79 / 19.30 | 7.02 / 33.62 | 4.84 / 19.00 |
| A18 | 11.51 / 27.54 | 10.70 / 24.16 | 1.65 / 12.26 | 30.36 / 41.27 | 20.43 / 30.93 | 16.31 / 30.50 | 26.96 / 33.86 |
| A19 | 18.28 / 48.00 | 14.84 / 44.56 | 4.57 / 10.05 | 14.81 / 41.36 | 28.83 / 41.43 | 10.08 / 28.04 | 11.82 / 19.48 |

### Streaming EER % (causal: decision on the first t s of received audio, trim and loudness from that prefix only)

Only clips with at least t s of trimmed speech; in brackets the full-clip EER on the same trials.

| model | horizon | n bona / spoof (clean pool) | clean | seen | held-out |
|---|---|---|---|---|---|
| gmm8_aug | 1s | 934 / 1483 | 28.98 (25.48) | 34.17 (30.34) | 36.73 (33.68) |
| gmm8_aug | 2s | 346 / 852 | 26.91 (24.25) | 31.92 (29.29) | 34.28 (32.43) |
| gmm8_aug | 4s (too few bona fide to read) | 4 / 184 | 20.00 (19.89) | 25.50 (27.65) | 22.36 (21.67) |
| lcnn8_aug | 1s | 934 / 1483 | 32.97 (27.68) | 36.89 (30.72) | 39.41 (34.39) |
| lcnn8_aug | 2s | 346 / 852 | 29.59 (27.66) | 32.56 (30.59) | 35.36 (33.53) |
| lcnn8_aug | 4s (too few bona fide to read) | 4 / 184 | 19.34 (14.61) | 20.68 (16.23) | 17.18 (9.84) |

### Shortcut audit (single-cue classifiers, direction fixed on dev; rule: must be >= 35% EER)

| stage | cue | eval EER % | passes |
|---|---|---|---|
| raw (before normalisation) | silence | 17.54 | NO |
| raw (before normalisation) | loudness | 49.86 | yes |
| raw (before normalisation) | duration | 40.73 | yes |
| CM input (nb_pcm) | silence (trim gate, 30 dB) | 36.95 | yes |
| CM input (nb_pcm) | silence (gate 20 dB) | 39.07 | yes |
| CM input (nb_pcm) | silence (gate 25 dB) | 38.24 | yes |
| CM input (nb_pcm) | silence (WebRTC VAD) | 43.64 | yes |
| CM input (nb_pcm) | non-speech fraction (WebRTC VAD) | 40.10 | yes |
| CM input (nb_pcm) | low-energy frame fraction (< max-30 dB) | 50.00 | yes |
| CM input (nb_pcm) | loudness | 42.24 | yes |
| CM input (nb_pcm) | duration | 40.53 | yes |
| CM input (g711u) | silence (trim gate, 30 dB) | 40.18 | yes |
| CM input (g711u) | silence (gate 20 dB) | 41.45 | yes |
| CM input (g711u) | silence (gate 25 dB) | 41.56 | yes |
| CM input (g711u) | silence (WebRTC VAD) | 47.08 | yes |
| CM input (g711u) | non-speech fraction (WebRTC VAD) | 44.51 | yes |
| CM input (g711u) | low-energy frame fraction (< max-30 dB) | 49.98 | yes |
| CM input (g711u) | loudness | 48.16 | yes |
| CM input (g711u) | duration | 40.58 | yes |

### Points matrix (statement section 7)

| KPI | weight | status | value | note |
|---|---|---|---|---|
| Unseen-Indic EER (G2+G3 after channel) | 25 | PENDING | n/a | G1/G3 from Timbre stock voices + the builder's own consented voice; Kathbath-speaker cloning DEFERRED (consent) |
| Pooled narrowband EER and delta-NB, held-out codecs | 15 | MEASURED (ASVspoof 2019 LA proxy) | ssl_aasist: 20.97%, delta-NB +11.83 pts | English VCTK-based proxy, not Indic |
| FRR@FAR1, dev-fixed threshold | 10 | MEASURED (proxy) | ssl_aasist: 71.60% on held-out codecs | threshold fixed on dev, never retuned |
| Streaming EER at 2.0 s | 10 | MEASURED (proxy) | gmm8_aug: 34.28% held-out pool | causal prefix scoring, clips with >= 2 s of trimmed speech only (346 bona fide in the clean pool) |
| Student efficiency (RTF, params, RAM) | 10 | MEASURED (inside budget) | lcnn8_aug: RTF 0.0050, 170,401 params, 143 MB | LFCC-LCNN stands in for the distilled student until the teacher is trained |
| End-to-end flow: ASR <= 5%, genuine >= 90% | 10 | PARTIAL (CM gate only, English proxy) | g711u @ far1: genuine 32.5%, attack 11.0%; g711u @ min_dcf: genuine 88.5%, attack 62.5%; g711u @ eer: genuine 84.5%, attack 49.0%; amrnb_4k75 @ far1: genuine 4.5%, attack 1.0%; amrnb_4k75 @ min_dcf: genuine 75.5%, attack 55.5%; amrnb_4k75 @ eer: genuine 57.5%, attack 33.5% | python -m ivr_demo.trials: real ASVspoof clips through verify(), echo STT, identity gate bypassed; Gnani-clone trials PENDING |
| Replay / injection detection (G5, G6 EER) | 5 | PENDING | n/a | G5 simulator in factory/replay_sim.py; G6 needs G2 audio |
| Rigor: shortcut audit, ablations, failure analysis, ITW / 2021 LA | 10 | PARTIAL | shortcut audit passes; codec-aug ablation done | failure cases, In-the-Wild and 2021 LA sanity checks pending |
| Reproducibility: one-command eval, model card, data card | 5 | PARTIAL | run.ps1 quick / run.ps1 report; MODEL_CARD.md; DATA_CARD.md; release/ holds models, calibration and gzipped scores | a fresh clone regenerates every table from release/ (run.ps1 report); rebuilding the audio needs the ASVspoof download |
