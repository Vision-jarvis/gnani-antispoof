# What you must understand to defend this work

Read with the code open. Each item names the file and function that implements it, and ends with the
hard question a Gnani engineer is likely to ask, plus a good answer.

## 1. Why the phone line destroys the evidence (the core claim)
G.711 and AMR-NB run at 8 kHz, so everything above 4 kHz is gone (Nyquist), and the PSTN band-pass
(300 to 3400 Hz, `factory/channel_sim.py: BandLimit`) removes more. Many vocoder artefacts (HiFi-GAN
periodic ripple, phase incoherence) live at 4 to 8 kHz. After the channel, a wideband detector's best
cue is gone and codec quantisation noise is added to bona fide and spoof alike.
`tests/test_channel_sim.py::test_narrowband_removes_4_to_8_khz` proves the 6 kHz tone vanishes and does
not alias down.
*Q: "Could you not just train at 16 kHz and upsample phone audio?"* A: You can, and `gmm16_clean` and the
pretrained AASIST models do exactly that. The upsampled input has an empty top band the model never saw
in training, so its scores shift (see the clean vs held-out rows in `artifacts/results.md`). The teacher
config still upsamples to 16 kHz for XLS-R, but trains on channel-degraded audio so the empty band is
the normal case, not a surprise.

## 2. The channel simulator and its determinism (`factory/channel_sim.py`)
Each `Condition` is a chain of steps: `Resample`, `BandLimit`, `FfmpegCodec` (real encoder, then
decoder, via ffmpeg pipes), `PacketLoss`. Randomness only enters through `numpy.random.default_rng(seed)`
(packet-loss pattern) and the seed is a hash of the utterance ID (`factory/asvspoof.py: stable_hash`), so
any trial can be regenerated bit for bit. Output length is trimmed or padded to the input duration;
codec delay is not compensated (`test_speech_codecs_keep_waveform_alignment` bounds it at 10 ms).
Held-out conditions (AMR-NB 4.75k, GSM-FR, the two chains) are tagged `heldout` and
`eval/protocol.py: assert_protocol` refuses any training manifest that contains them.
*Q: "Is ffmpeg's G.711 the real G.711?"* A: Yes. `test_ffmpeg_g711_matches_reference_codec` compares it
with our bit-exact numpy codec (`gnani_api/g711.py`, verified against Python's `audioop` on all 65,536
inputs). ffmpeg rounds to the nearest codeword where the Sun reference truncates; every output is the same
or an adjacent quantisation level.
*Q: "Packet loss after decoding is not how a real jitter buffer works."* A: Correct, it is a
simplification: real PLC lives inside the decoder and is codec-specific (AMR has its own). Ours is
repeat-last-frame with 0.5 gain per lost frame, which gives the same signature (frame-periodic
discontinuities), but it is not bit-exact to any network. This is in the limitations.

## 3. EER via the ROC convex hull (`eval/metrics.py: rocch, eer`)
EER is where FAR = FRR. With finite scores the empirical ROC is a staircase and "the crossing" depends
on interpolation. BOSARIS (the ASVspoof reference toolkit) instead takes the convex hull of the ROC
(computed with pool-adjacent-violators, `pavx`) and intersects it with FAR = FRR. The hull EER is never
worse than the best empirical crossing (`test_eer_brute_force_agreement`) and matches the Gaussian
theory value Phi(-d/2) for equal-variance classes (`test_eer_matches_gaussian_theory`).
*Q: "Why the hull?"* A: It is the EER of the best system obtainable by randomising between two
thresholds, it is well defined with ties, and it is what the statement asks for.

## 4. minDCF with the bank prior (`eval/metrics.py: min_dcf`)
pi_spf = 0.05, C_miss = 1, C_fa = 10, normalised by min(C_miss (1 - pi), C_fa pi) = min(0.95, 0.5) = 0.5.
So minDCF = 1 means "no better than always accepting". Because C_fa pi = 0.5 is smaller than
C_miss (1 - pi) = 0.95, the default system the normaliser compares against is accept-all, and the
optimal threshold sits where false rejects are rarer than false accepts.
*Q: "Your minDCF is near 1 in some cells, does the model do nothing?"* A: It means at this prior and
cost no threshold beats accept-all by much: with spoofs only 5% of calls, a model must be very sure
to reject. EER can still be informative in the same cell.

## 5. Calibration, Cllr and the dev-fixed threshold (`AffineCalibration`, `threshold_at_far`, `cm/calibrate.py`)
Raw CM scores are not LLRs. An affine map llr = a s + b is fitted on dev by prior-weighted logistic
regression; Cllr measures how good those LLRs are as probabilities (1 bit = useless, 0 = perfect),
min Cllr is the same after the best monotone recalibration (discrimination only). FRR@FAR1 fixes the
threshold on dev (FAR = 1%) and applies it unchanged to eval; `far_at_dev_tau` shows how far the real
FAR drifted. Under codec shift the scores move, so a dev threshold that gave 1% FAR can give a very
different FAR on held-out codecs. This is the "calibration honesty" KPI.
*Q: "Why not calibrate per codec?"* A: That needs a codec label at inference, which honesty rule 3
forbids, and in the field you do not know the codec chain.

## 6. The shortcut audit (`eval/shortcut_audit.py`, `factory/normalise.py`)
ASVspoof 2019 bona fide files have longer silences than spoofs (Muller et al. 2021). A one-number
classifier on silence duration gets far below 50% EER on raw audio. Every clip is therefore VAD-trimmed
(keeping 50 ms of real context, never inserting digital zeros) and normalised to -23 LUFS before
anything else. The audit fixes each cue's direction on dev, then measures eval EER; rule 4 requires
>= 35% on what the CM actually sees. See the audit table in `artifacts/results.md`: compare the raw
rows with the "CM input" rows.
*Q: "Your VAD is a 40 dB energy gate, isn't that crude?"* A: Yes, deliberately: it is deterministic and
identical for both classes. The audit is the check that it was good enough. A residual duration cue
remains (spoofed utterances in ASVspoof have different lengths); it is reported, not hidden.

## 7. Why LFCC and not CQCC or MFCC (`cm/features.py`)
Mel filters are coarse at high frequencies, where artefacts live, so ASVspoof baselines use linear
filters (LFCC) or constant-Q (CQCC). At 8 kHz, CQCC's geometry spends most of its bins on the top
octaves, which a narrowband signal does not have, so LFCC was chosen for both baselines.
*Q: "Did you try CQCC?"* A: No; it is a cheap ablation to add (`cm/features.py` is the only file to touch),
and it is listed as future work.

## 8. The baselines and what each one isolates (`cm/run_baselines.py`)
- `aasist`, `aasist_l`: the published checkpoints, trained on clean 16 kHz. Our "SOTA vs phone line"
  measurement. The scoring follows the official code (first 64,600 samples, repeat-padded).
- `gmm16_clean`: classic wideband LFCC-GMM, the 2019 B2 recipe at CPU scale (128 components, 300k frames).
- `gmm8_aug`, `lcnn8_aug`: 8 kHz native, trained on nb_pcm plus one seen codec per utterance.
- `lcnn8_noaug`: same LCNN with no codec augmentation: the codec-augmentation ablation.
*Q: "Your GMM is much smaller than the official one."* A: Yes (128 vs 512 components, subsampled frames)
to train in minutes on a laptop; numbers are labelled as such. Run with more components via
`LFCCGMM.train(n_components=512, max_frames=...)` if time allows.

## 9. The LCNN and the streaming score (`cm/lcnn.py`, `cm/scorer.py`)
Max-Feature-Map halves channels with an element-wise max (a learned competitive selection). The time
axis is pooled by mean and standard deviation, so the model accepts any length; the streaming score at
t is simply the model run on the first t seconds of trimmed speech (causal; LFCC deltas look 20 ms ahead,
inside the 200 ms allowance). Training uses random 2 s crops because 2 s is the primary decision horizon.
*Q: "Is scoring a prefix the same as a streaming model?"* A: Functionally yes (same inputs available at t),
computationally no: we recompute from scratch at 1, 2 and 4 s. At 170k parameters and RTF about 0.01
that is affordable; a real stateful streaming student is part of the distillation work.

## 10. The student budget (`cm/export_onnx.py`)
RTF = compute time / audio duration, on one thread, including LFCC. Peak RAM is measured in a fresh
subprocess (so torch's import does not count). The LCNN stands in for the distilled student: it shows
the budget is reachable, not that a distilled student is accurate.

## 11. The honesty protocol (`eval/protocol.py`)
G2 (Gnani clones), G3 (born-narrowband) and G6 (injection) are test-only; held-out codecs are eval-only;
train and eval speakers are disjoint (ASVspoof splits are speaker-disjoint by design; Kathbath must be
split by speaker). `assert_protocol` is called in every training entry point and has its own tests.
*Q: "How do you know no G2 audio leaked?"* A: Training reads only ASVspoof train stores; the G2
generator writes to `artifacts/gnani_cache/G2|G3`, which no training code reads, and the protocol check
raises on any G2/G3/G6 row.

## 12. Born-narrowband attacks (G3) and why they matter
Timbre returns `container=mulaw` at a forced 8 kHz, and VC returns mu-law too (the VC doc lists no
A-law: `AudioConfig.validate_for_vc`). Audio synthesised directly at 8 kHz never had a wideband artefact,
so "simulate the channel on a 16 kHz fake" training does not cover it. The live probe already produced
one such clip (`docs/gnani_api_notes.md`, call 5).

## 13. The IVR flow and the decision codes (`ivr_demo/flow.py`)
Order of checks: no audio (StatusCode 4) or short audio (3); then phrase match (a fresh random digit
string defeats replay of an old recording), CM liveness, ASV. Phrase mismatch and CM spoof both map to
DecisionCode 1 (Spoof Failure), ASV failure to 2, exceptions to StatusCode 5 / DecisionCode 3. These are
Armour365's published codes (`docs/gnani_api_snapshots/armour365_README.md`). Note Armour365's status
codes (0, 1 connection error, 2 timeout, 3 short audio, 4 no audio, 5 internal error, 6 no enrolment)
are separate from its decision codes.
*Q: "A clone that says the fresh phrase passes the phrase check."* A: Correct, by design: the phrase
check stops replay, the CM must stop clones and injection. The realtime VC WebSocket makes a
fresh-phrase clone cheap, which is why the red-team run uses it.

## 14. What the numbers do and do not show
Everything measured so far is on ASVspoof 2019 LA (English, VCTK-based, 2019-era generators) after our
simulated channels, plus an Indic pilot whose bona fide and spoof come from different corpora (FLEURS vs
IndicSynth). Neither is the statement's IndicClone-Tel. The headline KPI (unseen-Indic EER on Gnani
clones) is PENDING the Kathbath download and the approved clone run. Say this before anyone asks.

## 15. Likely hard questions with short answers
- "Why not just use the SSL model?" It is 300M parameters, offline-teacher only; the CPU budget needs a
  student under 5M. The teacher is configured and smoke-tested (`python -m cm.teacher.train --smoke`) but
  needs a GPU.
- "What does an EER on a 2,560-utterance subset mean?" With about 1,000 bona fide and 1,560 spoof trials
  per pool, the standard error of an EER near 10% is roughly 1 point; per-attack cells (120 spoofs) are
  noisier. Full-set commands are in STATUS.md.
- "Why did you not use the 2021 LA real-channel data?" The 7.8 GB download was interrupted; it is the
  first sanity check to add, since its channels are real VoIP/PSTN, not simulated.
