import itertools
from dataclasses import fields, replace

import pytest
from test_causal9_baseline import assert_state_close

from threemind_core import StateImage, Stimulus
from threemind_core.engine import Edge
from threemind_kernels.continuous import ContinuousConfig, ContinuousEngine
from threemind_kernels.continuous_native import NativeContinuousEngine
from threemind_kernels.memory import KERNEL_ID, MemoryConfig, MemoryDynamics, MemoryEngine
from threemind_kernels.memory_native import NativeMemoryEngine


@pytest.fixture(params=[MemoryEngine, NativeMemoryEngine])
def factory(request):
    return request.param


def neutral_image(engine):
    image = engine.capture_state().to_dict()
    for key in ("dynamics", "schema", "definition", "definition_hash"):
        image.pop(key)
    image["config"].pop("depletion_enabled", None)
    image["config"].pop("edge_consolidation_enabled", None)
    return image


@pytest.mark.parametrize("factories", [(ContinuousEngine, MemoryEngine), (NativeContinuousEngine, NativeMemoryEngine)])
def test_default_restores_all_old_continuous_dynamics(factories):
    old, new = (f() for f in factories)
    for step in range(15):
        for engine in (old, new):
            engine.inject(Stimulus(step * 100_000, ((1, 0.9), (2, 0.6), (step % 4 + 3, 0.8))))
            engine.advance_to(step * 100_000 + 93_771)
        assert neutral_image(new) == neutral_image(old)


@pytest.mark.parametrize("d,f,l", list(itertools.product((False, True), repeat=3)))
def test_eight_conditions_parity_restore_and_batching(d, f, l):
    config = MemoryConfig(depletion_enabled=d, stp_facilitation_tau_s=float(f), edge_consolidation_enabled=l)
    a, b = MemoryEngine(config), NativeMemoryEngine(config)
    for when in (0, 71_771, 135_000, 203_123):
        for engine in (a, b):
            engine.inject(Stimulus(when, ((1, 0.8), (2, 0.9), (3, 0.7))))
    for when in (103_771, 217_777, 1_100_000):
        observed = ([], [])
        a.advance_to(when, observed[0].append)
        b.advance_to(when, observed[1].append)
        assert_state_close(observed[1], observed[0])
        assert_state_close(b.capture_state().to_dict(), a.capture_state().to_dict())
        aa, bb = a.capture_state(), b.capture_state()
        a, b = MemoryEngine(state=bb), NativeMemoryEngine(state=aa)
        assert a.capture_state().digest == bb.digest
        assert b.capture_state().digest == aa.digest
    for engine in (a, b):
        before = engine.capture_state().digest
        engine.graph()
        engine.metrics()
        engine.observation_nodes()
        assert engine.capture_state().digest == before


def test_depletion_and_facilitation_have_matched_first_release():
    values = {}
    for d, f in itertools.product((False, True), repeat=2):
        engine = MemoryDynamics(MemoryConfig(depletion_enabled=d, stp_facilitation_tau_s=float(f)))
        edge = Edge(1, 2, 0.5)
        first = engine.release_fraction(edge)
        engine.time_us = 100_000
        second = engine.release_fraction(edge)
        engine.time_us = 30_000_000
        last = engine.release_fraction(edge)
        assert first == 0.5
        assert last == pytest.approx(0.5, abs=1e-12)
        values[d, f] = second
    assert values[False, False] == 0.5
    assert values[False, True] > 0.5
    assert values[True, False] < 0.5
    assert values[True, True] > values[True, False]


def test_direct_consolidation_gate_keeps_birth_node_history_and_eligibility(factory):
    a, b = factory(), factory(MemoryConfig(edge_consolidation_enabled=False))
    stimulus = Stimulus(0, ((1, 0.8), (2, 0.8)))
    for engine in (a, b):
        engine.inject(stimulus)
        engine.advance_to(0)
    assert a.graph()["edges"] == b.graph()["edges"]
    original = b.graph()["edges"][0]
    for engine in (a, b):
        engine.inject(stimulus)
        engine.advance_to(0)
    x, y = a.graph()["edges"][0], b.graph()["edges"][0]
    assert x["weight"] > y["weight"] == original["weight"]
    assert x["stability"] > y["stability"] == original["stability"]
    assert x["eligibility"] == y["eligibility"] > original["eligibility"]
    assert a.observation_nodes() == b.observation_nodes()


def test_propagation_consolidation_gate_does_not_disable_fast_trace_or_history(factory):
    a = factory(MemoryConfig(birth_weight=0.8))
    a.inject(Stimulus(0, ((1, 0.8), (2, 0.8))))
    a.advance_to(0)
    b = factory(state=a.capture_state())
    b.reconfigure(replace(b.config, edge_consolidation_enabled=False))
    original = b.graph()["edges"][0]
    for engine in (a, b):
        engine.advance_to(100_000)
    x, y = a.graph()["edges"][0], b.graph()["edges"][0]
    assert x["weight"] > y["weight"] == original["weight"]
    assert x["stability"] > y["stability"]
    assert x["touches"] == y["touches"] > original["touches"]
    assert a.capture_state().to_dict()["operator_state"] == b.capture_state().to_dict()["operator_state"]
    assert b.capture_state().to_dict()["operator_state"]["fast"]


def test_forgetting_support_decay_and_pruning_operate_with_consolidation_off(factory):
    config = MemoryConfig(
        edge_consolidation_enabled=False,
        propagation_rate=0,
        forgetting_rate=10,
        prune_weight=0.008,
        node_prune_after_us=0,
    )
    engine = factory(config)
    engine.inject(Stimulus(0, ((1, 0.8), (2, 0.8))))
    engine.advance_to(0)
    before = engine.capture_state().to_dict()
    engine.advance_to(100_000)
    after = engine.capture_state().to_dict()
    assert after["edges"][0]["weight"] < before["edges"][0]["weight"]
    assert after["edges"][0]["stability"] < before["edges"][0]["stability"]
    assert after["nodes"][0]["support"] < before["nodes"][0]["support"]
    engine.advance_to(1_000_000)
    assert not engine.graph()["edges"]
    assert engine.config.inhibition and engine.config.plasticity


def test_switching_and_state_identity_are_explicit(factory):
    a = factory()
    a.inject(Stimulus(0, ((1, 0.8), (2, 0.8))))
    a.advance_to(123_451)
    a.reconfigure(
        replace(a.config, depletion_enabled=False, edge_consolidation_enabled=False, stp_facilitation_tau_s=1)
    )
    image = a.capture_state()
    b = factory(state=image)
    for t in (134_771, 277_911, 700_000):
        b.advance_to(t)
    a.advance_to(700_000)
    assert a.capture_state().digest == b.capture_state().digest
    wrong = ContinuousEngine().capture_state()
    with pytest.raises(ValueError):
        factory(state=wrong)
    damaged = image.to_dict()
    damaged["config"]["depletion_enabled"] = True
    with pytest.raises(ValueError):
        factory(state=StateImage.from_dict(damaged))
    with pytest.raises(TypeError):
        ContinuousConfig(depletion_enabled=False)


def test_configuration_ui_cli_and_definition_bind_same_controls():
    from threemind_kernels.definition import KernelDefinition
    from threemind_lab.configuration import catalogue, validate_configuration
    from threemind_runtime.host import create_engine

    catalog = catalogue()
    visible = [f for f in catalog["fields"] if not f.get("kernels") or KERNEL_ID in f["kernels"]]
    assert {f["path"][7:] for f in visible if f["path"].startswith("config.")} == {f.name for f in fields(MemoryConfig)}
    assert validate_configuration(
        {"kernel_id": KERNEL_ID, "environment": "manual", "config": {"depletion_enabled": False}}
    )["valid"]
    engine = create_engine(kernel_id=KERNEL_ID)
    assert KernelDefinition.parse(engine.capture_state().to_dict()["definition"]).create().dynamics == KERNEL_ID
