# Report

**Setup.** ASVspoof 2019 LA subsets:
- Train: 5,160 utts (A01-A06).
- Dev: 2,020 utts (thresholds and calibration only).
- Eval: 2,560 utts (1,000 bona fide, 120 per attack A07-A19).

Preprocessing: VAD trim, -23 LUFS, a second 30 dB trim at the CM input, then the channel. Training uses plain 8 kHz plus one seen codec per utterance; the 4 held-out codecs are eval-only. minDCF uses pi=0.05, C_miss=1, C_fa=10.

**Results.**

| Model | EER clean | EER seen | EER held-out | minDCF held-out | Cllr held-out | FRR@FAR1 held-out |
|---|---|---|---|---|---|---|
| GMM | 25.59 | 30.38 | 33.63 | 0.781 | 0.874 | 99.28 |
| LCNN | 27.64 | 30.70 | 34.42 | 0.799 | 0.976 | 92.47 |

- Streaming EER, held-out pool, at 1/2/4 s: GMM 35.5/34.1/33.6, LCNN 37.7/34.8/34.4.
- The phone line hurts most on attacks that were easy in clean narrowband: LCNN A08 2.1 -> 18.9, A09 0.2 -> 9.8.
- A threshold fixed on dev does not survive a codec change.
- Shortcut audit on the CM input: silence 38.1, loudness 42.2, duration 40.4 (raw silence was 17.5).

**Limitations.** Simulated channels only, English proxy data, small CPU-trained models, non-commercial training data, placeholder ASV.
