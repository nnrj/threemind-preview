"""Restoration evidence: frozen old operators + approved counterexamples.

These fixtures compare local laws, not the obsolete frame-driven scheduler.
"""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from threemind_core import Config, Engine, StateImage, Stimulus
from threemind_runtime.host import NativeEngine

ORACLE = json.loads((Path(__file__).parent / "fixtures/v3-restoration.json").read_text(encoding="utf-8"))["samples"]


@pytest.fixture(params=[Engine, NativeEngine], ids=["python", "rust"])
def backend(request):
    return request.param


def image(engine):
    return engine.capture_state().to_dict()


def assert_old_local(engine, name, nodes=True):
    actual, old = image(engine), ORACLE[name]
    assert len(actual["edges"]) == len(old["edges"])
    for left, right in zip(actual["edges"], sorted(old["edges"], key=lambda e: (e["source"], e["target"]))):
        for key in ("source", "target", "weight", "stability", "eligibility"):
            assert left[key] == pytest.approx(right[key], abs=1e-14)
        assert left["touches"] == right["touch_count"]
    if nodes:
        for left, right in zip(actual["nodes"], old["nodes"]):
            for key in ("activation", "trace", "stability", "support"):
                assert left[key] == pytest.approx(right[key], abs=1e-14)
            assert left["local_plasticity"] == pytest.approx(right["plasticity"])
            assert left["touches"] == right["touch_count"]


def test_birth_repeat_novelty_and_forget_match_git_operators(backend):
    e = backend(Config(inhibition=False, propagation_rate=0))
    for name in ("local_birth", "local_repeat"):
        e.inject(Stimulus(0, ((11, 0.7), (22, 0.5))))
        e.advance_to(0)
        assert_old_local(e, name)
    state = image(e)
    for n in state["nodes"]:
        n["associative"] = 0.05
    e = backend(state=StateImage.from_dict(state))
    e.inject(Stimulus(0, ((11, 0.3), (33, 0.6))))
    e.advance_to(0)
    assert_old_local(e, "local_novelty", nodes=False)
    e.advance_to(100_000)
    assert_old_local(e, "local_forget", nodes=False)


def network(backend, config, weights, activations):
    e = Engine(config)
    e.inject(Stimulus(0, tuple((i, 0.5) for i in range(1, len(activations) + 1))))
    e.advance_to(0)
    state = image(e)
    state["edges"] = [
        {
            "source": s,
            "target": t,
            "weight": w,
            "stability": 0.0,
            "eligibility": 0.0,
            "touches": 0,
            "birth_us": "0",
            "last_touch_us": "0",
        }
        for s, t, w in weights
    ]
    state["queue"] = []
    for n, a in zip(state["nodes"], activations):
        n.update(activation=a, inhibition=0.0, pending_inhibition=0.0, generated_inhibition=0.0)
    return backend(state=StateImage.from_dict(state))


def test_saturated_target_cost_touch_and_independent_consolidation(backend):
    c = Config(inhibition=False, activation_decay_enabled=False, energy_simulation_enabled=True)
    e = network(backend, c, [(1, 2, 0.5)], [1.0, 1.0])
    before = image(e)
    e.advance_to(100_000)
    emitted = image(e)
    assert emitted["transport"]["sent"] == pytest.approx(0.21)
    assert before["energy"]["reserve"] - emitted["energy"]["reserve"] == pytest.approx(0.21 * c.energy_associative_cost)
    assert emitted["edges"][0]["weight"] == pytest.approx(0.5 + c.associative_gain * 0.21)
    assert emitted["edges"][0]["touches"] == 1
    e.advance_to(110_000)
    received = image(e)
    assert received["energy"]["reserve"] == emitted["energy"]["reserve"]
    assert received["transport"]["activated"] == emitted["transport"]["activated"]
    assert received["transport"]["received"] - emitted["transport"]["received"] == pytest.approx(0.21)
    assert received["nodes"][1]["touches"] == before["nodes"][1]["touches"] + 1


@pytest.mark.parametrize("step", [5_000, 10_000, 20_000])
def test_single_edge_threshold_cannot_be_rescued_by_fanin(backend, step):
    c = Config(step_us=step, inhibition=False, plasticity=False, activation_decay_enabled=False)
    e = network(backend, c, [(1, 3, 0.005), (2, 3, 0.005)], [1, 1, 0])
    e.advance_to(110_000)
    assert image(e)["nodes"][2]["activation"] == 0
    assert image(e)["transport"]["sent"] == 0
    f = network(backend, c, [(1, 3, 0.01), (2, 3, 0.01)], [1, 1, 0])
    f.advance_to(110_000)
    assert image(f)["nodes"][2]["activation"] == pytest.approx(0.0084)


def test_soft_inhibition_is_not_applied_every_solver_step(backend):
    results = []
    for step in (5_000, 10_000, 20_000):
        c = Config(step_us=step, inhibition_gain=0, inhibition_diffusion_rate=0, propagation_rate=0)
        e = network(backend, c, [], [0.5])
        state = image(e)
        state["nodes"][0]["inhibition"] = 0.5
        e = backend(state=StateImage.from_dict(state))
        e.advance_to(100_000)
        results.append(image(e)["nodes"][0]["inhibition"])
    import math

    assert results == pytest.approx([math.tanh(0.5 * 0.65)] * 3)


def test_two_inhibition_phases_and_finite_pool_match_old_operators(backend):
    e = Engine(Config(propagation_rate=0))
    e.inject(Stimulus(0, ((11, 0.7), (22, 0.5))))
    e.advance_to(0)
    s = image(e)
    for n, q in zip(s["nodes"], (0.5, 0.7)):
        n.update(inhibition=q, pending_inhibition=0.0, generated_inhibition=0.1 * e.config.inhibition_gain)
    e = backend(state=StateImage.from_dict(s))
    e.advance_to(100_000)
    actual = image(e)
    old = ORACLE["inhibition_two_phases"]["state"]["nodes"]
    for n, expected in zip(actual["nodes"], old):
        assert n["inhibition"] == pytest.approx(expected["inhibition"], abs=1e-14)
        incoming = sum(
            amount
            for event in actual["queue"]
            if event["kind"] == "inhibition"
            for target, amount in event["payload"]["values"]
            if target == n["id"]
        )
        assert incoming == pytest.approx(expected["pending_inhibition"], abs=1e-14)


def test_zero_support_isolated_node_survives_until_joint_prune_boundary(backend):
    c = Config(energy_simulation_enabled=True, energy_initial_reserve=0)
    e = backend(c)
    e.inject(Stimulus(0, ((1, 0.5),)))
    e.advance_to(80_000_000)
    assert len(image(e)["nodes"]) == 1
    assert image(e)["life"] == "waiting"
    e.advance_to(80_100_000)
    assert image(e)["nodes"] == []


def test_quiescence_deadline_arrivals_and_no_automatic_resurrection(backend):
    e = network(backend, Config(inhibition=False, propagation_rate=0), [], [0])
    s = image(e)
    s["quiet_since_us"] = "0"
    s["next_event"] += 1
    s["queue"] = [{"time_us": "1000000", "id": s["next_event"], "kind": "signal", "payload": {"values": [[1, 0.5]]}}]
    e = backend(state=StateImage.from_dict(s))
    e.advance_to(1_000_000)
    assert image(e)["life"] == "active"
    assert image(e)["quiet_since_us"] is None
    s["queue"] = []
    e = backend(state=StateImage.from_dict(s))
    e.advance_to(999_999)
    assert image(e)["life"] == "active"
    e = backend(state=e.capture_state())
    e.advance_to(1_000_000)
    assert image(e)["life"] == "dead"
    assert len(image(e)["nodes"]) == 1
    with pytest.raises(ValueError):
        e.inject(Stimulus(1_000_000, ((1, 0.5),)))


def test_external_input_without_activation_does_not_prevent_death(backend):
    e = network(backend, Config(direct_gain=0, inhibition=False), [], [0])
    # Build a born, quiescent consciousness, then send real external carriers.
    s = image(e)
    s["life"] = "active"
    s["quiet_since_us"] = "0"
    e = backend(state=StateImage.from_dict(s))
    for t in (100_000, 500_000, 1_000_000):
        e.inject(Stimulus(t, ((99, 0.5),)))
    e.advance_to(1_000_000)
    assert image(e)["life"] == "dead"


def test_disconnect_does_not_retract_emission_and_delete_never_reuses_id(backend):
    e = network(backend, Config(inhibition=False, activation_decay_enabled=False), [(1, 2, 0.5)], [1, 0])
    e.advance_to(100_000)
    e.intervene(edges=[(1, 2)], action="disconnect_edges")
    e.advance_to(110_000)
    assert image(e)["nodes"][1]["activation"] == pytest.approx(0.21)
    e.inject(Stimulus(110_000, ((1, 0.5), (2, 0.5))))
    e.advance_to(110_000)
    assert image(e)["edges"]  # natural co-contact can connect again
    e.advance_to(200_000)
    e.intervene(nodes=[2], action="delete_nodes")
    e.inject(Stimulus(200_000, ((2, 0.1),)))
    e.advance_to(200_000)
    new = next(n for n in image(e)["nodes"] if n["channel"] == 2)
    assert new["id"] > 2 and new["touches"] == 1 and new["birth_us"] == "200000"
    e.advance_to(210_000)
    new_after = next(n for n in image(e)["nodes"] if n["id"] == new["id"])
    assert new_after["activation"] == new["activation"]


def test_zero_disables_rates_and_decay_flags_preserve_states(backend):
    c = Config(
        propagation_rate=0,
        inhibition_gain=0,
        inhibition_diffusion_rate=0,
        forgetting_rate=0,
        activation_decay_enabled=False,
        trace_decay_enabled=False,
        inhibition_decay_enabled=False,
        eligibility_decay_enabled=False,
        stability_decay_enabled=False,
        support_decay_enabled=False,
    )
    e = network(backend, c, [(1, 2, 0.5)], [0.8, 0.4])
    before = image(e)
    e.advance_to(250_000)
    after = image(e)
    for key in ("activation", "trace", "support", "stability"):
        assert [n[key] for n in before["nodes"]] == [n[key] for n in after["nodes"]]
    assert after["edges"] == before["edges"]
    assert after["transport"]["sent"] == 0


def test_old_dynamics_are_not_silently_resumed(backend):
    s = image(Engine())
    s.update(dynamics="threemind.causal/7", schema="threemind.state/5")
    with pytest.raises(ValueError, match="read-only"):
        backend(state=StateImage.from_dict(s))


def test_disconnected_subnetworks_are_not_forced_into_existing_component(backend):
    e = backend(Config(inhibition=False))
    e.inject(Stimulus(0, ((1, 0.7), (2, 0.5))))
    e.inject(Stimulus(30_001, ((33, 0.7), (44, 0.5))))
    e.inject(Stimulus(40_001, ((99, 0.7),)))
    e.advance_to(40_001)
    s = image(e)
    assert {(edge["source"], edge["target"]) for edge in s["edges"]} == {(1, 2), (2, 1), (3, 4), (4, 3)}
    assert s["nodes"][4]["activation"] > 0


def test_zero_grace_dies_after_quiescence_without_removing_structure(backend):
    e = backend(Config(quiescence_death_us=0, inhibition=False))
    e.advance_to(5_000_000)
    assert e.life == "waiting"
    e.inject(Stimulus(5_000_000, ((99, 0.7),)))
    e.advance_to(5_000_000)
    assert e.life == "active"
    e.intervene(nodes=[1], action="silence")
    assert e.life == "dead" and len(image(e)["nodes"]) == 1


def test_propagation_clock_reconfiguration_survives_empty_skips_and_restoration(backend):
    e = backend()
    e.advance_to(3500)
    e.reconfigure(replace(e.config, propagation_interval_us=80_000))
    snapshot = e.capture_state()
    a = backend(state=snapshot)
    b = backend(state=snapshot)
    a.advance_to(195_007)
    for t in (4000, 100_003, 195_007):
        b.advance_to(t)
    assert image(a)["next_propagation_us"] == "243500"
    assert a.capture_state().digest == b.capture_state().digest
    for e in (a, b):
        e.inject(Stimulus(200_005, ((1, 0.7), (2, 0.8))))
        e.advance_to(243_500)
        assert any(q["kind"] == "signal" for q in image(e)["queue"])
    assert a.capture_state().digest == b.capture_state().digest


def test_budget_clock_can_be_reconfigured_without_corrupting_saved_state(backend):
    e = backend(Config(edge_adaptation_limit=3, inhibition=False))
    e.inject(Stimulus(100_001, ((1, 0.7), (2, 0.8))))
    e.advance_to(110_001)
    e.reconfigure(replace(e.config, propagation_interval_us=70_000))
    assert image(backend(state=e.capture_state())) == image(e)
