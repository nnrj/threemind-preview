"""Mechanism regression, not evidence of learned motor control or brain areas.

All connections in these checks arise from delivered stimuli. No fixture edits
node potentials or inserts an edge to obtain the expected selective response.
"""

from dataclasses import replace

import pytest

from threemind_core import Config, Stimulus
from threemind_runtime import ArtifactCodec, create_engine


def by_channel(engine):
    return {node["channel"]: node for node in engine.observation_nodes()}


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_local_inhibition_uses_model_rhythm_and_reduces_response_without_input_filtering(backend):
    config = Config(propagation_rate=0)
    enabled = create_engine(config, backend=backend)
    disabled = create_engine(replace(config, inhibition=False), backend=backend)
    for engine in (enabled, disabled):
        engine.inject(Stimulus(0, ((17, 0.3),)))
        engine.advance_to(0)
    assert by_channel(enabled)[17]["inhibition"] == 0
    assert enabled.capture_state().to_dict()["nodes"][0]["generated_inhibition"] > 0
    for engine in (enabled, disabled):
        engine.advance_to(config.propagation_interval_us - 1)
        assert by_channel(engine)[17]["inhibition"] == 0
        engine.advance_to(config.propagation_interval_us)
    assert by_channel(enabled)[17]["inhibition"] > 0
    assert by_channel(disabled)[17]["inhibition"] == 0
    before = [by_channel(engine)[17]["activation"] for engine in (enabled, disabled)]
    for engine in (enabled, disabled):
        engine.inject(Stimulus(config.propagation_interval_us, ((17, 0.3),)))
        engine.advance_to(config.propagation_interval_us)
        assert engine.metrics()["attention"]["evaluated_frames"] == "0"
    after = [by_channel(engine)[17]["activation"] for engine in (enabled, disabled)]
    assert 0 < after[0] - before[0] < after[1] - before[1]


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_inhibition_follows_stimulus_formed_topology_and_survives_model_exchange(backend):
    engine = create_engine(Config(propagation_rate=0), backend=backend)
    engine.inject(Stimulus(0, ((11, 0.2), (22, 0.2))))
    engine.inject(Stimulus(0, ((33, 0.2),)))
    engine.inject(Stimulus(50_000, ((11, 0.45),)))
    # The first pulse redistributes finite potential, temporarily reducing the
    # connected receiver's own field. Its incoming packet is applied next pulse.
    engine.advance_to(200_000)
    state = engine.capture_state()
    channels = {n["id"]: n["channel"] for n in state.to_dict()["nodes"]}
    assert {(channels[e["source"]], channels[e["target"]]) for e in state.to_dict()["edges"]} == {(11, 22), (22, 11)}
    rows = by_channel(engine)
    assert rows[22]["inhibition"] > rows[33]["inhibition"] > 0
    restored = create_engine(state=ArtifactCodec.decode(ArtifactCodec.encode(state)), backend=backend)
    assert restored.capture_state().digest == state.digest
    before = {channel: rows[channel]["activation"] for channel in (22, 33)}
    for instance in (engine, restored):
        for channel in (22, 33):
            instance.inject(Stimulus(200_000, ((channel, 0.1),)))
        instance.advance_to(200_000)
    rows = by_channel(engine)
    assert 0 < rows[22]["activation"] - before[22] < rows[33]["activation"] - before[33]
    assert engine.capture_state().digest == restored.capture_state().digest
    # Observing more often does not create additional inhibition or propagation.
    for when in (200_001, 204_713, 210_000, 227_891):
        restored.advance_to(when)
        restored.observation_nodes()
    engine.advance_to(227_891)
    assert engine.capture_state().digest == restored.capture_state().digest


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_stimulus_history_protects_edges_and_plasticity_ablation_freezes_slow_state(backend):
    engine = create_engine(Config(propagation_rate=0), backend=backend)
    engine.inject(Stimulus(0, ((11, 0.2), (22, 0.2))))
    engine.inject(Stimulus(0, ((33, 0.2), (44, 0.2))))
    for when in (100_000, 200_000, 300_000):
        engine.inject(Stimulus(when, ((11, 0.4), (22, 0.4))))
    engine.advance_to(300_000)
    before = engine.capture_state().to_dict()
    frozen = create_engine(state=engine.capture_state(), backend=backend)
    frozen.reconfigure(replace(frozen.config, plasticity=False))
    for instance in (engine, frozen):
        instance.advance_to(2_300_000)
    after = engine.capture_state().to_dict()
    edges_before = {(e["source"], e["target"]): e for e in before["edges"]}
    ratios = {
        key: e["weight"] / edges_before[key]["weight"] for e in after["edges"] for key in [(e["source"], e["target"])]
    }
    assert 0 < ratios[3, 4] < ratios[1, 2] < 1
    assert frozen.capture_state().to_dict()["edges"] == before["edges"]
    assert by_channel(frozen)[11]["activation"] < before["nodes"][0]["activation"]
