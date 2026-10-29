# Model card: 8 kHz LFCC-LCNN countermeasure (`lcnn8_aug`), the shipped CPU countermeasure

| Field | Value |
|---|---|
| Task | Bona fide vs spoof (TTS / VC) on 8 kHz telephone speech; outputs a calibrated LLR (higher = bona fide) |
| Input | 8 kHz mono waveform, any length >= 1 s; VAD trim and -23 LUFS normalisation are applied inside `cm/scorer.py` (`causal_cm_input`), on the received prefix only for streaming partials |
| Features | 20 LFCC + deltas + delta-deltas, 20 ms / 10 ms, linear filterbank over 0 to 4 kHz (`cm/features.py`) |
| Architecture | LCNN with Max-Feature-Map, mean + std temporal pooling (`cm/lcnn.py`), 170,401 parameters |
| Training data | 5,160 ASVspoof 2019 LA train utterances (2,580 bona fide, A01 to A06), each as plain 8 kHz plus one seen codec (10,320 examples); random 2 s crops; 8 epochs, Adam, class-balanced BCE; CPU |
| Model selection | lowest dev EER on the ASVspoof 2019 LA dev subset (never eval) |
| Calibration | affine LLR map fitted on dev; named dev-fixed operating points far1 (default, tau 3.027), min_dcf (-0.715), eer (0.490), bayes (-0.642) in `release/models/lcnn8_aug_calibration.json` |
| Never seen in training | held-out codecs (AMR-NB 4.75k, GSM-FR, two-hop chains), ASVspoof eval attacks A07 to A19, any Indic speech, any Gnani audio |
| Export | ONNX (`release/models/cm_student.onnx`), measured by `python -m cm.export_onnx` |
| Results | `artifacts/results.md` (ASVspoof proxy) and `artifacts/ivr_trials_asvspoof.md` (IVR flow on real clips), summarised in README.md. Held-out codecs: EER 34.42% [33.04, 35.60], delta-NB +6.78. Indic pilot (`artifacts/indic_pilot.md`): 40 to 50% EER (the XLS-R teacher: 32 to 47%), and the pilot fails its shortcut audit (duration alone 16.6%), so it is not evidence either way |

## Intended use
A research baseline that shows how much an 8 kHz-native, codec-augmented countermeasure recovers
versus wideband models behind a simulated phone line, and the runtime shape (ONNX, RTF, RAM) of a CPU
student. Not a production anti-spoofing system.

## Not intended for
Any real authentication decision. It has never seen Indic speech in training, real PSTN audio, replay
(G5) or injection (G6) trials, or any commercial cloner. The attack-family output is not implemented
(`family = "unclassified"`).

## Known limitations
- English, VCTK-derived training data with 2019-era generators.
- Simulated channels only.
- Small CPU training budget (8 epochs, subset); see STATUS.md for full-run commands.
- The ASV component used in the IVR demo (`LFCCStatsASV`) is a placeholder, not a speaker verifier;
  `EcapaASV` is the intended model. The mock demo and `ivr_demo.trials` bypass the identity gate and print no ASV score.
- Causality: a partial score at t uses only samples before t; LFCC deltas look 2 frames (20 ms) ahead inside the prefix.
- Operating point: at far1 the CM accepts 32.5% of genuine G.711 callers (11.0% of spoofs); at min_dcf 88.5% (62.5%). No point meets the statement's end-to-end target.

## Teacher and distilled student (measured, REAL runs)
Teacher: XLS-R 300M + AASIST (`cm/teacher/`), initialised from the published `LA_model.pth` and fine-tuned at
8 kHz on the same codec-augmented train pool (Modal L40S, 10 epochs, dev EER 8.42% before and 2.28% after).
Eval: 23.34% clean 8 kHz, 21.63% [20.03, 22.71] on held-out codecs, delta-NB -1.71, minDCF 0.381; it lost
unseen attacks A07, A10 and A11 in fine-tuning, and its dev threshold gives 27% FAR on held-out codecs. Weights
(1.26 GB) are not in the repo.

Student: `python -m cm.distil` trained the same LCNN on alpha = 0.5 teacher soft targets (T = 2) with the
`lcnn8_aug` recipe (`lcnn8_distil`, 34 min on 4 CPU threads). Held-out 34.63% [33.35, 35.86] vs 34.42% for this
model: no gain, so this model stays the shipped one. `lcnn8_distil.pt` and its calibration are in `release/models/`.
