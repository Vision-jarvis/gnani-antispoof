# Superseded v1 results (failed the shortcut audit, rule 4)

Kept for the record. These were produced before the CM-input trim (factory/normalise.py: CM_INPUT_POLICY). The silence cue on the CM input (nb_pcm) reached 24.32% EER, below the 35% bar, so per honesty rule 4 these numbers are NOT reported as results. See artifacts/results.md for the rerun.

Metrics: EER %, minDCF (pi_spf=0.05, C_miss=1, C_fa=10), Cllr (bits, dev-calibrated), FRR@FAR1 % (dev-fixed threshold).

### Pooled results

| model | pool | EER % | minDCF | Cllr | FRR@FAR1 % | FAR at dev tau % |
|---|---|---|---|---|---|---|
| gmm8_aug | clean (nb_pcm) | 22.51 | 0.539 | 0.742 | 78.90 | 2.37 |
| gmm8_aug | seen | 27.57 | 0.677 | 0.827 | 89.87 | 1.42 |
| gmm8_aug | heldout | 30.52 | 0.737 | 0.826 | 98.85 | 0.13 |
| lcnn8_aug | clean (nb_pcm) | 24.83 | 0.565 | 0.957 | 58.60 | 10.45 |
| lcnn8_aug | seen | 28.85 | 0.669 | 1.029 | 67.74 | 7.74 |
| lcnn8_aug | heldout | 32.48 | 0.781 | 0.979 | 84.85 | 3.56 |

### delta-NB (EER held-out codecs minus EER clean pool, same utterances)

| model | delta-NB (EER points) |
|---|---|
| gmm8_aug | +8.01 |
| lcnn8_aug | +7.65 |

### EER % per channel condition

| condition | gmm8_aug | lcnn8_aug |
|---|---|---|
| amrnb_12k2 | 25.89 | 28.49 |
| amrnb_4k75 (held-out) | 30.66 | 30.95 |
| amrnb_7k95 | 27.74 | 29.37 |
| amrwb_12k65 | 27.85 | 29.07 |
| chain_amrnb_g711u (held-out) | 31.55 | 31.54 |
| chain_gsm_g711a_plc2 (held-out) | 29.57 | 32.72 |
| g711a | 24.88 | 25.48 |
| g711u | 25.23 | 25.94 |
| g711u_plc5 | 25.33 | 26.59 |
| gsm_fr (held-out) | 28.68 | 32.55 |
| nb_pcm | 22.51 | 24.83 |
| opus_16k | 24.84 | 26.70 |
| opus_6k_plc3 | 27.50 | 34.00 |
| opus_8k | 26.17 | 30.53 |

### EER % per ASVspoof 2019 eval attack (clean pool / held-out codec pool)

| attack | gmm8_aug | lcnn8_aug |
|---|---|---|
| A07 | 34.69 / 34.17 | 42.99 / 44.98 |
| A08 | 2.26 / 11.04 | 1.73 / 21.37 |
| A09 | 0.00 / 5.48 | 0.29 / 10.53 |
| A10 | 40.74 / 40.80 | 40.17 / 40.81 |
| A11 | 10.67 / 32.54 | 26.68 / 37.94 |
| A12 | 27.27 / 40.46 | 31.86 / 39.65 |
| A13 | 4.73 / 19.64 | 10.77 / 18.12 |
| A14 | 15.19 / 24.31 | 30.41 / 41.57 |
| A15 | 13.54 / 20.35 | 18.66 / 31.04 |
| A16 | 37.69 / 41.03 | 28.12 / 37.64 |
| A17 | 8.23 / 23.83 | 8.95 / 20.97 |
| A18 | 19.86 / 31.32 | 26.49 / 35.51 |
| A19 | 33.26 / 45.47 | 14.77 / 22.50 |

### Streaming EER % (decision on the first t seconds of trimmed speech only)

| model | horizon | clean | seen | held-out |
|---|---|---|---|---|
| gmm8_aug | 1s | 26.50 | 29.93 | 31.93 |
| gmm8_aug | 2s | 23.23 | 28.53 | 31.36 |
| gmm8_aug | 4s | 22.51 | 27.56 | 30.56 |
| gmm8_aug | full | 22.51 | 27.57 | 30.52 |
| lcnn8_aug | 1s | 31.41 | 33.74 | 35.61 |
| lcnn8_aug | 2s | 25.83 | 29.81 | 33.19 |
| lcnn8_aug | 4s | 24.95 | 28.93 | 32.52 |
| lcnn8_aug | full | 24.83 | 28.85 | 32.48 |

### Shortcut audit (single-cue classifiers, direction fixed on dev; rule: must be >= 35% EER)

| stage | cue | eval EER % | passes |
|---|---|---|---|
| raw (before normalisation) | silence | 17.54 | NO |
| raw (before normalisation) | loudness | 49.86 | yes |
| raw (before normalisation) | duration | 40.70 | yes |
| CM input (nb_pcm) | silence | 24.32 | NO (this triggered the fix) |
| CM input (nb_pcm) | loudness | 46.86 | yes |
| CM input (nb_pcm) | duration | 44.21 | yes |
| CM input (g711u) | silence | 49.07 | yes |
| CM input (g711u) | loudness | 48.70 | yes |
| CM input (g711u) | duration | 44.21 | yes |

### Points matrix (statement section 7)

| KPI | weight | status | value | note |
|---|---|---|---|---|
| Unseen-Indic EER (G2+G3 after channel) | 25 | PENDING | n/a | needs Kathbath bona fide (gated) + Gnani clone set (factory/gnani_clone.py, awaiting approval) |
| Pooled narrowband EER and delta-NB, held-out codecs | 15 | MEASURED (ASVspoof 2019 LA proxy) | gmm8_aug: 30.52%, delta-NB +8.01 pts | English VCTK-based proxy, not Indic |
| FRR@FAR1, dev-fixed threshold | 10 | MEASURED (proxy) | lcnn8_aug: 84.85% on held-out codecs | threshold fixed on dev, never retuned |
| Streaming EER at 2.0 s | 10 | MEASURED (proxy) | gmm8_aug: 31.36% held-out pool | prefix-only scoring |
| Student efficiency (RTF, params, RAM) | 10 | MEASURED (inside budget) | lcnn8_aug: RTF 0.0158, 170,401 params, 142 MB | LFCC-LCNN stands in for the distilled student until the teacher is trained |
| End-to-end flow: ASR <= 5%, genuine >= 90% | 10 | PENDING | n/a | flow runs end to end on mocks; real G2/G5/G6 attack trials need the approved clone run |
| Replay / injection detection (G5, G6 EER) | 5 | PENDING | n/a | G5 simulator in factory/replay_sim.py; G6 needs G2 audio |
| Rigor: shortcut audit, ablations, failure analysis, ITW / 2021 LA | 10 | PARTIAL | shortcut audit FAILS; codec-augmentation ablation done | failure cases, In-the-Wild and 2021 LA sanity checks pending |
| Reproducibility: one-command eval, model card, data card | 5 | MEASURED | run.ps1 quick / run.ps1 eval; MODEL_CARD.md; DATA_CARD.md |  |
