# Shortcut audit v2: the circular audit and the tie bug (critique B3)

Kept for the record. Two problems were found in the audit that `artifacts/results.md` reported in the
first v2 write-up.

## 1. The audit gate was looser than the trim gate (circular)

The CM input is trimmed with a 30 dB energy gate plus a 50 ms margin (`factory/normalise.py`,
`CM_INPUT_POLICY`). The old audit measured silence on that input with the 40 dB build-time gate, which is
looser, so it could only ever see the 50 ms margin. It could not fail by construction.

The fixed audit (`eval/shortcut_audit.py`) measures silence with gates strictly tighter than the trim gate
(20 dB and 25 dB), with an independent detector (WebRTC VAD, mode 2, 20 ms frames), as a WebRTC
non-speech fraction, as a fraction of low-energy frames, and keeps loudness and duration.

## 2. EER broke ties optimistically

Silence values are quantised to 20 ms frames, so most clips tie (on eval `nb_pcm`, 1,724 of 2,560 clips
sit at 0.04, 0.06 or 0.08 s). `eval.metrics.rocch` sorted tied bona fide trials *above* tied spoofs, which
treats every tie as correctly separated. BOSARIS does the opposite (pessimistic ordering, then the convex
hull), which equals random tie-breaking; a constant score then has 50% EER as it should. With the old code
a constant score had 0% EER. Model scores are continuous and almost never tie, so model EERs barely move;
audit cues tie constantly, so audit EERs moved a lot. `tests/test_metrics.py::test_eer_ties_are_pessimistic`
pins the fix.

## Numbers (eval `nb_pcm` after `cm_input`, direction fixed on dev, rule: >= 35%)

| silence cue | old tie handling | BOSARIS tie handling |
|---|---|---|
| gate 40 dB (the old, circular audit) | 38.1 | 44.6 |
| gate 30 dB (the trim gate) | 26.6 | 37.0 |
| gate 25 dB (tighter) | 28.2 | 38.2 |
| gate 20 dB (tighter) | 33.9 | 39.1 |

The critique's 28.2% came from the old tie handling. With correct tie handling every cue, including the
independent VAD cues, is at or above 37% on `nb_pcm` and `g711u` (full table in `artifacts/results.md`),
so rule 4 is met without retraining. The weakest cue is silence at the trim gate itself (37.0%), which is
the 50 ms margin being cut short at a file edge. Dropping the margin (trim at 30 dB with no margin) raises
the weakest cue to 40.4% (duration) in a scratch run, but needs a full feature rebuild and retrain, so it is
listed as an optional hardening step in STATUS.md, not done.

The v1 record (`docs/results_v1_failed_audit.md`, 24.32%) was also measured with the old tie handling and
the circular gate. It stays superseded: its CM input had no second trim at all.
