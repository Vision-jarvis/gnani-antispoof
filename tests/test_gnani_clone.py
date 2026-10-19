from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

import factory.gnani_clone as gc
from gnani_api import GnaniClient
from gnani_api.mock import MockGnaniBackend


@pytest.fixture()
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[list[gc.Job], MockGnaniBackend]:
    monkeypatch.setattr(gc, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(gc, "fleurs_sentences", lambda lang, n, offset=0: [f"{lang} sentence {offset + i}" for i in range(n)])
    ref = tmp_path / "ref.wav"
    sf.write(ref, (0.1 * np.random.default_rng(0).standard_normal(8000 * 10)).astype(np.float32), 8000)
    jobs = gc.plan([{"speaker": "spk1", "language": "kn-IN", "reference_wav": str(ref)}], per_speaker=6, g1_per_voice=3)
    return jobs, MockGnaniBackend(api_key="k")


def test_plan_counts_and_attack_tags(setup) -> None:  # type: ignore[no-untyped-def]
    jobs, _ = setup
    s = gc.summarise(jobs)
    assert s["by_type"]["G2/vc_embed"]["calls"] == 1
    assert s["by_type"]["G2/vc_tts"]["calls"] == 4 and s["by_type"]["G3/vc_tts"]["calls"] == 2
    assert all(j.body["audio_config"]["container"] in ("mulaw", "alaw") for j in jobs if j.attack == "G3")
    assert len({j.key for j in jobs}) == len(jobs)


def test_execute_respects_cap_and_cache(setup) -> None:  # type: ignore[no-untyped-def]
    jobs, backend = setup
    client = GnaniClient(api_key="k", transport=backend.transport())
    assert gc.execute(jobs, max_calls=3, client=client) == 3
    assert len(backend.calls) == 3
    client = GnaniClient(api_key="k", transport=backend.transport())
    made = gc.execute(jobs, max_calls=100, client=client)
    assert made == len(jobs) - 3 and gc.summarise(jobs)["pending_calls"] == 0
    client = GnaniClient(api_key="k", transport=backend.transport())
    assert gc.execute(jobs, max_calls=100, client=client) == 0  # everything cached, nothing spent
    wav = next(j for j in jobs if j.attack == "G2" and j.kind == "vc_tts").out_path.read_bytes()
    assert sf.info(io.BytesIO(wav)).samplerate == 16000
