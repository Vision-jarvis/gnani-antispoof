from __future__ import annotations

import numpy as np
import pytest
import torch

from cm.lcnn import LCNN
from cm.scorer import Calibration, CMScorer
from gnani_api.mock import MockSTTConnect, synth_speechlike
from factory.channel_sim import apply_condition
from ivr_demo.asv import LFCCStatsASV
from ivr_demo.flow import new_challenge, prisma_stt, verify
from ivr_demo.phrases import normalise_text, phrase_distance, phrase_matches


def test_challenges_are_random_and_spoken_digits() -> None:
    a, b = new_challenge("kn-IN", 1), new_challenge("kn-IN", 2)
    assert a.text != b.text and not any(ch.isdigit() for ch in a.text)
    assert new_challenge("hi-IN", 5) == new_challenge("hi-IN", 5)


def test_phrase_match_normalisation() -> None:
    assert normalise_text("Hello, World!! 42") == "hello world four two"
    assert phrase_matches("मेरी आवाज़ ही मेरी पहचान है", "मेरी आवाज़ ही मेरी पहचान है।", "hi-IN")
    assert phrase_matches("one two three four my voice", "1 2 3 4 my voice", "en-IN")
    assert phrase_distance("one two three four", "five six seven eight", "en-IN") > 0.5


def _scorer(tau: float) -> CMScorer:
    torch.manual_seed(0)
    return CMScorer(LCNN(), Calibration(tau_llr=tau))


@pytest.mark.parametrize(("tau", "spoken_fresh", "expected"), [
    (-1e9, True, (0, 0, "accepted")),
    (-1e9, False, (0, 1, "phrase_mismatch")),
    (1e9, True, (0, 1, "cm_spoof")),
])
def test_decision_codes(tau: float, spoken_fresh: bool, expected: tuple[int, int, str]) -> None:
    ch, old = new_challenge("hi-IN", 3), new_challenge("hi-IN", 4)
    audio = apply_condition(synth_speechlike("caller", 16000, 50), 16000, "g711u")
    asv = LFCCStatsASV()
    spoken = ch.text if spoken_fresh else old.text
    stt = prisma_stt(api_key="k", connect=MockSTTConnect(lambda pcm: spoken, api_key="k"), realtime_pace=False, drain_timeout_s=0.1)
    r = verify(audio, ch, asv.embed(audio), _scorer(tau), asv, stt)
    assert (r.StatusCode, r.DecisionCode, r.reason) == expected
    if r.reason == "accepted":
        assert r.cm_partial and r.cm_partial[0]["t"] == 1.0


def test_voice_mismatch_and_status_codes() -> None:
    ch = new_challenge("hi-IN", 3)
    asv = LFCCStatsASV()
    stt = prisma_stt(api_key="k", connect=MockSTTConnect(lambda pcm: ch.text, api_key="k"), realtime_pace=False, drain_timeout_s=0.1)
    audio = apply_condition(synth_speechlike("caller", 16000, 50), 16000, "g711u")
    impostor = -asv.embed(audio)  # opposite direction: cosine -1
    assert verify(audio, ch, impostor, _scorer(-1e9), asv, stt).DecisionCode == 2
    assert verify(np.zeros(8000, np.float32), ch, impostor, _scorer(0), asv, stt).StatusCode == 4
    short = audio[:2400]
    assert verify(short, ch, impostor, _scorer(0), asv, stt).StatusCode == 3
