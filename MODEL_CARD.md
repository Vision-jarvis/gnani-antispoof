# Model card: 8 kHz LFCC-LCNN countermeasure (`lcnn8_aug`), the current CPU student stand-in

| Field | Value |
|---|---|
| Task | Bona fide vs spoof (TTS / VC) on 8 kHz telephone speech; outputs a calibrated LLR (higher = bona fide) |
| Input | 8 kHz mono waveform, any length >= 1 s; VAD trim and -23 LUFS normalisation are applied inside `cm/scorer.py` |
| Features | 20 LFCC + deltas + delta-deltas, 20 ms / 10 ms, linear filterbank over 0 to 4 kHz (`cm/features.py`) |
| Architecture | LCNN with Max-Feature-Map, mean + std temporal pooling (`cm/lcnn.py`), 170,401 parameters |
| Training data | 5,160 ASVspoof 2019 LA train utterances (2,580 bona fide, A01 to A06), each as plain 8 kHz plus one seen codec (10,320 examples); random 2 s crops; 8 epochs, Adam, class-balanced BCE; CPU |
| Model selection | lowest dev EER on the ASVspoof 2019 LA dev subset (never eval) |
| Calibration | affine LLR map fitted on dev; operating threshold = dev FAR 1% (`artifacts/models/lcnn8_aug_calibration.json`) |
| Never seen in training | held-out codecs (AMR-NB 4.75k, GSM-FR, two-hop chains), ASVspoof eval attacks A07 to A19, any Indic speech, any Gnani audio |
| Export | ONNX (`artifacts/models/cm_student.onnx`), measured by `python -m cm.export_onnx` |
| Results | `artifacts/results.md` (ASVspoof proxy) and `artifacts/indic_pilot.md` (Indic pilot), summarised in README.md |

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
  `EcapaASV` is the intended model.

## Planned teacher (PENDING GPU)
XLS-R 300M + AASIST (`cm/teacher/`), fine-tuned at 8 kHz with codec augmentation and RawBoost; a
distilled student under 5M parameters replaces this LCNN once the teacher exists.
