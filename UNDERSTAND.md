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
pretrained AASIST models do exactly that (their runs are PENDING). The upsampled input has an empty top
band the model never saw in training, so its scores are expected to shift; measuring by how much is the
first job for the GPU box. The teacher
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
*Ties (a bug that was found and fixed).* Within a block of tied scores BOSARIS puts the targets (bona fide)
*below* the non-targets before taking the hull, which makes a tie cost what random tie-breaking costs; a
constant score then has EER 50%. The first version sorted the other way round, so ties counted as perfectly
separated (a constant score had EER 0%). Model scores are continuous, so model EERs did not move, but the
shortcut-audit cues are quantised to 20 ms frames and tie constantly: that bug made the audit look *worse*
than it was (`docs/results_v2_audit_ties.md`, `tests/test_metrics.py::test_eer_ties_are_pessimistic`).



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
ASVspoof 2019 bona fide files have longer silences than spoofs (Muller et al. 2021): on raw audio a
silence-only classifier gets 17.5% EER here. Every clip is therefore VAD-trimmed (50 ms of real context
kept, never digital zeros) and normalised to -23 LUFS, and the CM input is trimmed again at 30 dB below
its loudest frame (`cm_input`). Rule 4: every single-cue classifier on what the CM sees must stay >= 35%.
The audit fixes each cue's direction on dev and reports eval EER.
*What went wrong, twice.* (1) v1 had no CM-input trim and its silence cue failed (24.3%,
`docs/results_v1_failed_audit.md`). (2) The v2 audit measured silence with the 40 dB gate on audio already
trimmed at 30 dB: a looser gate on tighter-trimmed audio can only see the 50 ms margin, so the audit could
not fail. That is circular, and a reviewer caught it.
*What the audit does now.* Silence at gates strictly *tighter* than the trim gate (20 and 25 dB), silence
and non-speech fraction from an independent detector (WebRTC VAD, which shares nothing with the energy
trim), the fraction of low-energy frames, loudness and duration, on `nb_pcm` and `g711u`. All pass; the
weakest is silence at the trim gate itself, 37.0% (the margin being cut short at a file edge), then
38.2% at 25 dB. Dropping the margin would raise the floor to about 40% but needs a full rebuild.
*Q: "Your trim gate is 30 dB and your audit gate was 40 dB. What did the audit measure?"* A: Only the
margin; that version was circular. The fixed audit uses tighter gates and an independent VAD. The
reviewer's 28.2% at 25 dB came from the tie bug in section 3: with correct tie handling the same cue is
38.2%. Both fixes and before/after numbers are in `docs/results_v2_audit_ties.md`.

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
- `lcnn8_noaug`: same LCNN with no codec augmentation: the codec-augmentation ablation (code ready, run PENDING).
- Completed so far: `gmm8_aug` and `lcnn8_aug`. AASIST scoring was killed by a crash; `gmm16_clean` and `lcnn8_noaug` were not run.
*Q: "Your GMM is much smaller than the official one."* A: Yes (128 vs 512 components, subsampled frames)
to train in minutes on a laptop; numbers are labelled as such. Run with more components via
`LFCCGMM.train(n_components=512, max_frames=...)` if time allows.

## 9. The LCNN and the streaming score (`cm/lcnn.py`, `cm/scorer.py`, `factory/normalise.py: causal_cm_input`)
Max-Feature-Map halves channels with an element-wise max (a learned competitive selection). The time
axis is pooled by mean and standard deviation, so the model accepts any length; prefixes shorter than
32 frames are repeat-padded (`pad_frames`). Training uses random 2 s crops.
*Causality, done properly.* The partial score at t is `llr(causal_cm_input(x[: t * sr]))`: cut to the
first t seconds of *received* audio first, then trim and loudness-normalise using that prefix only. The
first version trimmed and normalised the whole clip and then cut it, so the trim threshold (loudest frame
of the whole call) and the loudness gain saw the future (mean LLR change 0.49 at 2 s), and the WebSocket
endpoint skipped normalisation altogether (0.83). Now the batch partials, the WebSocket and the streaming
evaluation call the same function (`tests/test_service.py::test_stream_and_batch_partials_are_identical_and_causal`).
Residual look-ahead: LFCC deltas use 2 frames (20 ms) inside the prefix, never beyond t.
*Which trials count.* After trimming, bona fide clips average 1.85 s, so for most of them "the first 2 s"
was the whole clip. The streaming table now uses only clips with at least t s of trimmed speech and prints
the full-clip EER on the same trials next to it. At 2 s that leaves 346 bona fide and 852 spoofs in the
clean pool; at 4 s only 4 bona fide, so the 4 s row is not readable.
*Q: "Is scoring a prefix the same as a streaming model?"* A: Functionally yes (same inputs available at t),
computationally no: we recompute from scratch at 1, 2 and 4 s; at 170k parameters and RTF 0.005 that is
affordable.

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
*Operating points and real outcomes.* `cm.calibrate` fixes four thresholds on dev: far1 (FAR 1%),
min_dcf, eer and bayes. `python -m ivr_demo.trials` runs `verify()` on 200 + 200 real ASVspoof eval clips per
codec (echo STT, identity gate bypassed, so only the CM gate is measured). On G.711: far1 lets 32.5% of
genuine callers through and 11.0% of spoofs; min_dcf 88.5% and 62.5%. On AMR-NB 4.75 (held out): far1
4.5% / 1.0%, min_dcf 75.5% / 55.5%. No operating point of this CM meets "genuine >= 90% and attack <= 5%";
the demo says so on screen instead of scripting a green tick. Every demo line prints its operating point.

## 14. What the numbers do and do not show
Everything measured so far is on ASVspoof 2019 LA (English, VCTK-based, 2019-era generators) after our
simulated channels, plus an Indic pilot whose bona fide and spoof come from different corpora (FLEURS vs
IndicSynth). Neither is the statement's IndicClone-Tel. The headline KPI (unseen-Indic EER on Gnani
clones) is PENDING: the rule-safe version uses Timbre stock voices (G1/G3) and the builder's own consented
voice (G2); cloning Kathbath speakers is DEFERRED until Gnani says in writing that it is allowed. Say this
before anyone asks.

## 15. Likely hard questions with short answers
- "Why not just use the SSL model?" It is 300M parameters, offline-teacher only; the CPU budget needs a
  student under 5M. The teacher is configured and smoke-tested (`python -m cm.teacher.train --smoke`) but
  needs a GPU.
- "What does an EER on a 2,560-utterance subset mean?" Every pooled EER in `artifacts/results.md` now has a
  95% utterance-bootstrap interval (200 resamples): about +-1.5 points (e.g. LCNN held-out 34.42%, 33.04 to
  35.60). Per-attack cells (120 spoofs) are noisier, about +-4 points.
- "Your clean 8 kHz EER is 26%; the official LFCC-GMM gets 8% at 16 kHz. Why trust the codec numbers?"
  Our GMM has 128 components on 300k frames (official: 512 on all frames) and the LCNN trained 8 CPU
  epochs. The codec effect is only readable on attacks the model catches in clean narrowband (A08, A09,
  A17). The wideband control `gmm16_clean` and the no-augmentation ablation are in the results table;
  the official-size GMM is a CPU-overnight run (STATUS.md).
- "Why did you not use the 2021 LA real-channel data?" The 7.8 GB download was interrupted; it is the
  first sanity check to add, since its channels are real VoIP/PSTN, not simulated.
