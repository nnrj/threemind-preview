import json
from copy import deepcopy
from dataclasses import replace
from functools import partial
from pathlib import Path

import pytest

from threemind_core import Config, StateImage, Stimulus
from threemind_core.attention import Attention, modulation_payload
from threemind_core.spec import MAX_TIME
from threemind_runtime import create_engine


@pytest.fixture(params=["reference", "native"])
def make_engine(request):
    return partial(create_engine, backend=request.param)


def test_attention_preserves_frozen_causal4_default_and_upgrades_without_refilling(make_engine):
    from threemind_runtime.codec import ArtifactCodec

    fixture = json.loads((Path(__file__).parent / "fixtures/causal4-continuation.json").read_text(encoding="utf-8"))
    before = StateImage.from_dict(fixture["before"])
    assert before.digest == fixture["before_hash"]
    for format in ("json", "tmind"):
        assert ArtifactCodec.decode(ArtifactCodec.encode(before, format)).digest == before.digest
    with pytest.raises(ValueError, match="read-only"):
        make_engine(state=before)


def test_attention_selects_per_frame_at_delivery_and_ties_preserve_input_order(make_engine):
    config = Config(attention_competition_enabled=True, attention_budget=1, inhibition=False, propagation_rate=0)
    engine = make_engine(config)
    first = Stimulus(1000, ((9, 0.4), (7, 0.8), (4, 0.8), (2, 0.1)))
    second = Stimulus(1000, ((9, 0.4), (4, 0.8), (7, 0.8), (2, 0.1)))
    engine.inject(first)
    engine.inject(second)
    events = []
    engine.advance_to(1000, events.append, inputs_only=True)
    assert {n["channel"] for n in engine.capture_state().to_dict()["nodes"]} == {4, 7}
    assert engine.capture_state().to_dict()["edges"] == []  # frames were not merged into a co-touch
    assert events[0]["payload"] == first.to_dict()
    assert events[0]["input_gate"]["effective_stimulus"]["channels"] == [[7, 0.8]]
    assert events[1]["input_gate"]["effective_stimulus"]["channels"] == [[4, 0.8]]
    assert engine.metrics()["attention"]["suppressed_channels"] == "6"
    # Gate changes affect still-pending raw frames at their real delivery time.
    engine.inject(Stimulus(2000, ((12, 0.7), (13, 0.6))))
    engine.reconfigure(replace(config, attention_budget=0))
    engine.advance_to(2000, events.append, inputs_only=True)
    assert events[-1]["input_gate"]["passed_channels"] == 0
    assert len(engine.capture_state().to_dict()["nodes"]) == 2


def test_attention_scalar_is_not_implicit_competition_and_expiry_is_causal(make_engine):
    engine = make_engine(Config(attention_budget=1, inhibition=False, propagation_rate=0))
    engine.modulate_input(time_us=1000, source="test-physical-gain", gain=0.5, budget_multiplier=0, ttl_us=1000)
    stimulus = Stimulus(1000, ((8, 0.6), (2, 0.8)))
    engine.inject(stimulus)
    engine.inject(Stimulus(2000, ((9, 0.7), (3, 0.9))))
    events = []
    engine.advance_to(1501, events.append, inputs_only=True)
    assert events[0]["kind"] == "modulation" and events[0]["payload"]["status"] == "applied"
    selected = events[1]["input_gate"]
    assert selected["passed_channels"] == 2 and not selected["competition_enabled"]
    assert selected["effective_stimulus"]["intensity"] == 0.5
    saved = engine.capture_state()
    before = deepcopy(saved.to_dict())
    engine.metrics()
    assert engine.capture_state().to_dict() == before
    resumed = make_engine(state=saved)
    engine.advance_to(1807)
    engine.advance_to(3001, events.append, inputs_only=True)
    resumed.advance_to(3001)
    assert engine.capture_state().digest == resumed.capture_state().digest
    assert "input_gate" not in events[-1]  # exact expiry boundary is already transparent
    assert engine.metrics()["attention"]["effective"]["sources"] == []


def test_attention_bounded_sources_do_not_create_activity_and_reject_at_delivery(make_engine):
    engine = make_engine()
    for i in range(65):
        engine.modulate_input(time_us=1000, source=f"device-{i}", ttl_us=5000)
    records = []
    engine.advance_to(1000, records.append, inputs_only=True)
    assert len(engine.capture_state().to_dict()["nodes"]) == 0
    assert records[-1]["payload"]["status"] == "rejected"
    assert records[-1]["payload"]["reason"] == "active_modulator_limit"
    assert len(engine.metrics()["attention"]["modulators"]) == 64
    engine.modulate_input(time_us=6000, source="fresh-device", gain=0, competition_enabled=True)
    engine.inject(Stimulus(6000, ((3, 0.8),)))
    engine.advance_to(6000, records.append, inputs_only=True)
    assert records[-1]["input_gate"]["passed_channels"] == 0
    assert len(engine.metrics()["attention"]["modulators"]) == 1
    assert not engine.capture_state().to_dict()["nodes"]


def test_attention_validation_saturation_and_restore():
    for value in (-1, True, 100001, 1.5):
        with pytest.raises(ValueError):
            Config(attention_budget=value)
    for values in ({"gain": True}, {"gain": 2.01}, {"ttl_us": 0}, {"competition_enabled": 1}, {"source": ""}):
        with pytest.raises(ValueError):
            modulation_payload(**values)
    ledger = Attention()
    ledger.increment("evaluated_frames", MAX_TIME)
    ledger.increment("evaluated_frames", 1)
    assert ledger.counter_overflowed and ledger.evaluated_frames == str(MAX_TIME)
    assert Attention.restore(ledger.to_dict(), 1000).to_dict() == ledger.to_dict()
    for values in ({"since_us": "1001"}, {"passed_channels": "01"}, {"counter_overflowed": 1}, {"modulators": [{}]}):
        with pytest.raises(ValueError):
            Attention.restore(Attention().to_dict() | values, 1000)
