Metrics: EER %, minDCF (pi_spf=0.05, C_miss=1, C_fa=10), Cllr (bits, dev-calibrated), FRR@FAR1 % (dev-fixed threshold).

### Pooled results (EER with a 95% utterance-bootstrap interval)

| model | pool | EER % | EER 95% CI | minDCF | Cllr | minCllr | FRR@FAR1 % | FAR at dev tau % |
|---|---|---|---|---|---|---|---|---|
| gmm8_aug | clean (nb_pcm) | 25.59 | 24.08 to 27.19 | 0.597 | 0.804 | 0.713 | 84.10 | 3.40 |
| gmm8_aug | seen | 30.38 | 29.24 to 31.53 | 0.715 | 0.874 | 0.807 | 93.12 | 1.53 |
| gmm8_aug | heldout | 33.63 | 32.29 to 34.81 | 0.781 | 0.874 | 0.860 | 99.28 | 0.16 |
| lcnn8_aug | clean (nb_pcm) | 27.64 | 25.94 to 29.10 | 0.579 | 0.925 | 0.722 | 74.20 | 6.22 |
| lcnn8_aug | seen | 30.70 | 29.45 to 31.83 | 0.706 | 1.017 | 0.801 | 79.03 | 6.05 |
| lcnn8_aug | heldout | 34.42 | 33.04 to 35.60 | 0.799 | 0.976 | 0.873 | 92.47 | 1.81 |

### delta-NB (EER held-out codecs minus EER clean pool, same utterances)

| model | delta-NB (EER points) |
|---|---|
| gmm8_aug | +8.04 |
| lcnn8_aug | +6.78 |

### EER % per channel condition

| condition | gmm8_aug | lcnn8_aug |
|---|---|---|
| amrnb_12k2 | 30.06 | 31.09 |
| amrnb_4k75 (held-out) | 34.81 | 32.85 |
| amrnb_7k95 | 30.92 | 31.45 |
| amrwb_12k65 | 30.49 | 30.71 |
| chain_amrnb_g711u (held-out) | 34.92 | 33.15 |
| chain_gsm_g711a_plc2 (held-out) | 32.42 | 36.06 |
| g711a | 28.55 | 27.97 |
| g711u | 29.05 | 28.15 |
| g711u_plc5 | 28.72 | 27.23 |
| gsm_fr (held-out) | 30.41 | 34.29 |
| nb_pcm | 25.59 | 27.64 |
| opus_16k | 27.50 | 28.23 |
| opus_6k_plc3 | 30.95 | 35.53 |
| opus_8k | 28.09 | 32.02 |

### EER % per ASVspoof 2019 eval attack (clean pool / held-out codec pool)

| attack | gmm8_aug | lcnn8_aug |
|---|---|---|
| A07 | 39.01 / 41.54 | 46.84 / 47.30 |
| A08 | 2.21 / 12.68 | 2.12 / 18.86 |
| A09 | 0.09 / 7.69 | 0.22 / 9.78 |
| A10 | 44.78 / 47.33 | 45.05 / 45.56 |
| A11 | 15.35 / 36.87 | 34.26 / 41.66 |
| A12 | 40.69 / 49.29 | 38.88 / 46.75 |
| A13 | 10.34 / 24.59 | 15.47 / 25.12 |
| A14 | 17.86 / 27.90 | 22.81 / 38.78 |
| A15 | 16.18 / 24.05 | 18.72 / 33.04 |
| A16 | 44.01 / 45.42 | 38.16 / 44.48 |
| A17 | 4.79 / 19.30 | 4.84 / 19.00 |
| A18 | 20.43 / 30.93 | 26.96 / 33.86 |
| A19 | 28.83 / 41.43 | 11.82 / 19.48 |

### Streaming EER % (causal: decision on the first t s of received audio, trim and loudness from that prefix only)

Only clips with at least t s of trimmed speech; in brackets the full-clip EER on the same trials.

| model | horizon | n bona / spoof (clean pool) | clean | seen | held-out |
|---|---|---|---|---|---|
| gmm8_aug | 1s | 934 / 1483 | 28.98 (25.48) | 34.17 (30.34) | 36.73 (33.68) |
| gmm8_aug | 2s | 346 / 852 | 26.91 (24.25) | 31.92 (29.29) | 34.28 (32.43) |
| gmm8_aug | 4s | 4 / 184 | 20.00 (19.89) | 25.50 (27.65) | 22.36 (21.67) |
| lcnn8_aug | 1s | 934 / 1483 | 32.97 (27.68) | 36.89 (30.72) | 39.41 (34.39) |
| lcnn8_aug | 2s | 346 / 852 | 29.59 (27.66) | 32.56 (30.59) | 35.36 (33.53) |
| lcnn8_aug | 4s | 4 / 184 | 19.34 (14.61) | 20.68 (16.23) | 17.18 (9.84) |

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
| Pooled narrowband EER and delta-NB, held-out codecs | 15 | MEASURED (ASVspoof 2019 LA proxy) | gmm8_aug: 33.63%, delta-NB +8.04 pts | English VCTK-based proxy, not Indic |
| FRR@FAR1, dev-fixed threshold | 10 | MEASURED (proxy) | lcnn8_aug: 92.47% on held-out codecs | threshold fixed on dev, never retuned |
| Streaming EER at 2.0 s | 10 | MEASURED (proxy) | gmm8_aug: 34.28% held-out pool | causal prefix scoring, clips with >= 2 s of trimmed speech only (346 bona fide in the clean pool) |
| Student efficiency (RTF, params, RAM) | 10 | MEASURED (inside budget) | lcnn8_aug: RTF 0.0050, 170,401 params, 143 MB | LFCC-LCNN stands in for the distilled student until the teacher is trained |
| End-to-end flow: ASR <= 5%, genuine >= 90% | 10 | PARTIAL (CM gate only, English proxy) | g711u @ far1: genuine 32.5%, attack 11.0%; g711u @ min_dcf: genuine 88.5%, attack 62.5%; g711u @ eer: genuine 84.5%, attack 49.0%; amrnb_4k75 @ far1: genuine 4.5%, attack 1.0%; amrnb_4k75 @ min_dcf: genuine 75.5%, attack 55.5%; amrnb_4k75 @ eer: genuine 57.5%, attack 33.5% | python -m ivr_demo.trials: real ASVspoof clips through verify(), echo STT, identity gate bypassed; Gnani-clone trials PENDING |
| Replay / injection detection (G5, G6 EER) | 5 | PENDING | n/a | G5 simulator in factory/replay_sim.py; G6 needs G2 audio |
| Rigor: shortcut audit, ablations, failure analysis, ITW / 2021 LA | 10 | PARTIAL | shortcut audit passes; codec-aug ablation PENDING | failure cases, In-the-Wild and 2021 LA sanity checks pending |
| Reproducibility: one-command eval, model card, data card | 5 | PARTIAL | run.ps1 quick / run.ps1 report; MODEL_CARD.md; DATA_CARD.md; release/ holds models, calibration and gzipped scores | a fresh clone regenerates every table from release/ (run.ps1 report); rebuilding the audio needs the ASVspoof download |
