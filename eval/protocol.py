"""Attack and codec registry plus the honesty-rule checks (statement section 4, "Honesty rules").

Rule 1: G2 (Gnani voice clone) and G3 (born-narrowband Gnani audio) are never in training; G6
(injection) is G2 audio, so it is test-only as well. Rule 2: AMR-NB 4.75 kbps, GSM-FR and two-hop
chains are eval-only. Speakers must be disjoint between train/dev and eval.
``assert_protocol`` raises on any violation and is called by every training entry point.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from factory.channel_sim import HELDOUT_CONDITIONS


@dataclass(frozen=True)
class Attack:
    attack_id: str
    family: str  # tts_vc | replay | injection | bonafide
    source: str
    test_only: bool
    description: str


ATTACKS: dict[str, Attack] = {
    a.attack_id: a
    for a in [
        Attack("bonafide", "bonafide", "any", False, "genuine speech"),
        Attack("G1", "tts_vc", "gnani_timbre", False, "Timbre v2.5/v3.0 stock voices, same transcripts"),
        Attack("G2", "tts_vc", "gnani_vc", True, "Gnani vachana-vc-v1 clones of eval speakers"),
        Attack("G3", "tts_vc", "gnani_vc", True, "G1/G2 requested born-narrowband (container=mulaw/alaw)"),
        Attack("G4", "tts_vc", "indicsynth", False, "open-source Indic clones (XTTS-v2/VITS/FreeVC, IndicSynth)"),
        Attack("G5", "replay", "simulated", False, "loudspeaker + room + phone-mic replay of bona fide"),
        Attack("G6", "injection", "gnani_vc", True, "G2 audio injected straight into the channel"),
        # ASVspoof 2019 LA systems (Wang et al., 2020). A16 = A04 and A19 = A06 algorithms.
        *[Attack(f"A{i:02d}", "tts_vc", "asvspoof2019", False, "ASVspoof 2019 LA train/dev system") for i in range(1, 7)],
        *[Attack(f"A{i:02d}", "tts_vc", "asvspoof2019", False, "ASVspoof 2019 LA eval system") for i in range(7, 20)],
    ]
}
TEST_ONLY_ATTACKS = frozenset(a for a, v in ATTACKS.items() if v.test_only)
# Seen/unseen is relative to what the CM was trained on; for ASVspoof, A07-A19 are unseen except
# A16 and A19, which reuse the A04 and A06 algorithms.
ASVSPOOF_KNOWN_ALGORITHM = {"A16": "A04", "A19": "A06"}


class ProtocolViolation(AssertionError):
    pass


def assert_protocol(train: Iterable[Mapping[str, str]], evaluation: Iterable[Mapping[str, str]]) -> None:
    """Check honesty rules 1 and 2 plus speaker disjointness on manifest rows.

    Rows need ``attack``, ``condition`` and ``speaker`` keys.
    """
    train, evaluation = list(train), list(evaluation)
    bad_attack = sorted({r["attack"] for r in train} & TEST_ONLY_ATTACKS)
    if bad_attack:
        raise ProtocolViolation(f"test-only attacks in training data: {bad_attack}")
    bad_codec = sorted({r["condition"] for r in train} & HELDOUT_CONDITIONS)
    if bad_codec:
        raise ProtocolViolation(f"held-out codecs in training data: {bad_codec}")
    overlap = sorted({r["speaker"] for r in train} & {r["speaker"] for r in evaluation})
    if overlap:
        raise ProtocolViolation(f"{len(overlap)} speakers in both train and eval, e.g. {overlap[:3]}")
    unknown = sorted({r["attack"] for r in train + evaluation} - set(ATTACKS))
    if unknown:
        raise ProtocolViolation(f"unregistered attack ids: {unknown}")
