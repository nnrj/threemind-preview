import random
from dataclasses import asdict, replace

import pytest
from kernel_witnesses import CASES
from test_causal9_baseline import assert_state_close

from threemind_core import Config, Engine, StateImage, Stimulus
from threemind_kernels.continuous import ContinuousConfig, ContinuousEngine
from threemind_kernels.continuous_native import NativeContinuousEngine


@pytest.fixture(params=[ContinuousEngine, NativeContinuousEngine])
def factory(request):
    return request.param


def feed(engine):
    engine.inject(Stimulus(0, ((1, 0.8), (2, 0.7), (3, 0.6))))
    engine.inject(Stimulus(133_713, ((1, 0.7), (2, 0.5))))


@pytest.mark.parametrize("name", CASES)
def test_all_new_operators_disabled_preserve_each_baseline_transition(name):
    case = CASES[name]
    original = Engine(Config(**case["config"]))
    candidate = ContinuousEngine(
        ContinuousConfig(**case["config"], stp_enabled=False, fast_enabled=False, context_enabled=False)
    )
    for action in case["actions"]:
        for engine in (original, candidate):
            if action[0] == "input":
                engine.inject(Stimulus(action[1], tuple(map(tuple, action[2])), action[3]))
            elif action[0] == "intervene":
                engine.intervene(**action[1])
            else:
                engine.advance_to(action[1])
        assert candidate._engine.capture_state().digest == original.capture_state().digest


def test_candidate_partition_and_inflight_restore_are_exact(factory):
    a = factory()
    feed(a)
    a.advance_to(105_131)
    image = a.capture_state()
    assert any("messages" in q["payload"] for q in image.to_dict()["queue"] if q["kind"] == "signal")
    b = factory(state=image)
    assert b.capture_state().digest == image.digest
    for when in (110_001, 199_991, 334_771, 505_759, 900_000):
        b.advance_to(when)
    a.advance_to(900_000)
    assert a.capture_state().digest == b.capture_state().digest


def test_reception_preserves_raw_messages_and_energy_receipts(factory):
    engine = factory(ContinuousConfig(energy_simulation_enabled=True, energy_initial_reserve=1.0))
    feed(engine)
    events = []
    engine.advance_to(110_000, events.append)
    signals = [row["payload"] for row in events if row["kind"] == "signal"]
    assert signals and all("messages" in row and "reception" in row for row in signals)
    for event in signals:
        for item in event["reception"]:
            assert item["raw"] >= item["response"] > 0
            assert sum(item["coefficients"]) == pytest.approx(1.0)
    transport = engine.metrics()["transport"]
    assert transport["received"] == pytest.approx(
        (0.8 + 0.7 + 0.6) * engine.config.direct_gain + sum(v for event in signals for _, v in event["values"])
    )
    assert transport["sent"] > 0
    before = engine.capture_state().digest
    engine.metrics()
    engine.graph()
    engine.observation_nodes()
    assert engine.capture_state().digest == before


def test_transmission_does_not_read_destination_activation(factory):
    config = ContinuousConfig(stp_enabled=False, fast_enabled=False, inhibition=False, activation_decay_enabled=False)
    a = factory(config)
    feed(a)
    a.advance_to(0)
    image = a.capture_state().to_dict()
    image["nodes"][1]["activation"] = 1.0
    b = factory(state=StateImage.from_dict(image))
    for engine in (a, b):
        engine.advance_to(100_000)

    def emission(engine):
        return next(
            m
            for q in engine.capture_state().to_dict()["queue"]
            if q["kind"] == "signal"
            for m in q["payload"]["messages"]
            if m[:2] == [1, 2]
        )

    assert emission(a) == emission(b)


def test_disconnect_clears_operator_history_but_preserves_inflight_messages(factory):
    engine = factory()
    feed(engine)
    engine.advance_to(100_000)
    pending = engine.capture_state().to_dict()["queue"]
    engine.intervene(edges=[(1, 2)], action="disconnect_edges")
    saved = engine.capture_state().to_dict()
    for rows in saved["operator_state"].values():
        assert all((row["source"], row["target"]) != (1, 2) for row in rows)
    assert saved["queue"] == pending
    engine.intervene(nodes=[2], action="delete_nodes")
    engine.inject(Stimulus(103_000, ((2, 0.2),)))
    engine.advance_to(105_000)
    replacement = next(n["id"] for n in engine.graph()["nodes"] if n["channel"] == 2)
    assert replacement != 2
    engine.advance_to(110_000)
    assert all(row["target"] != replacement for row in engine.capture_state().to_dict()["operator_state"]["fast"])


def test_reconfigure_settles_old_rates_before_new_ones_and_restores(factory):
    a = factory()
    feed(a)
    a.advance_to(123_456)
    changed = replace(a.config, fast_tau_s=3.0, stp_recovery_tau_s=0.2)
    a.reconfigure(changed)
    b = factory(state=a.capture_state())
    a.advance_to(500_000)
    b.advance_to(500_000)
    assert a.capture_state().digest == b.capture_state().digest
    before = a.capture_state().digest
    with pytest.raises(ValueError):
        a.reconfigure(replace(a.config, seed=a.config.seed + 1))
    assert a.capture_state().digest == before


@pytest.mark.parametrize("damage", ["definition", "operators", "message"])
def test_candidate_refuses_unbound_or_corrupt_recovery(damage, factory):
    engine = factory()
    feed(engine)
    engine.advance_to(100_000)
    state = engine.capture_state().to_dict()
    if damage == "definition":
        state["definition"]["operators"].clear()
    elif damage == "operators":
        state["operator_state"]["short_term"][0]["state"]["time_us"] = "100001"
    else:
        packet = next(q for q in state["queue"] if q["kind"] == "signal")
        packet["payload"]["messages"][0][2] += 0.2
    with pytest.raises(ValueError):
        factory(state=StateImage.from_dict(state))


def test_candidate_configuration_does_not_masquerade_as_original():
    from threemind_runtime.host import create_engine

    with pytest.raises(ValueError):
        create_engine(ContinuousConfig(), kernel_id="threemind.causal/9", backend="reference")
    assert create_engine(ContinuousConfig(), backend="reference").dynamics == "threemind.continuous/1"
    assert Config(**ContinuousConfig().base().to_dict()) == Config()
    assert asdict(ContinuousConfig())["stp_enabled"] is True


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"stp_enabled": False},
        {"fast_enabled": False},
        {"context_enabled": False},
        {"stp_enabled": False, "fast_enabled": False, "context_enabled": False},
        {"plasticity": False, "inhibition": False},
        {"stp_utilization": 0.04, "stp_facilitation_tau_s": 1.0, "context_mix": 0.5},
        {"step_us": 5000, "delay_us": 17311, "energy_simulation_enabled": True, "energy_initial_reserve": 0.5},
        {"spatial_embedding": True},
    ],
)
def test_complete_native_reference_state_and_events_with_cross_backend_restore(changes):
    config = ContinuousConfig(**changes)
    reference, native = ContinuousEngine(config), NativeContinuousEngine(config)
    rng = random.Random(9917)
    for when in sorted(rng.randrange(500_000) for _ in range(25)):
        stimulus = Stimulus(when, tuple((c, rng.uniform(0.1, 0.9)) for c in rng.sample(range(12), 3)))
        reference.inject(stimulus)
        native.inject(stimulus)
    for when in (33_791, 100_000, 113_117, 207_351, 335_991, 599_731):
        events = ([], [])
        reference.advance_to(when, events[0].append)
        native.advance_to(when, events[1].append)
        assert_state_close(events[1], events[0])
        a, b = reference.capture_state(), native.capture_state()
        assert_state_close(b.to_dict(), a.to_dict())
        assert_state_close(native.metrics(), reference.metrics())
        assert_state_close(native.graph(), reference.graph())
        # Restoration must retain exactly the other backend's serialized image.
        reference = ContinuousEngine(state=b)
        native = NativeContinuousEngine(state=a)
        assert reference.capture_state().digest == b.digest
        assert native.capture_state().digest == a.digest


@pytest.mark.parametrize("name", CASES)
def test_native_all_off_matches_preserved_native(name):
    from kernel_witnesses import exercise

    from threemind_runtime.host import NativeEngine

    case = CASES[name]
    neutral = case | {
        "config": case["config"] | {"stp_enabled": False, "fast_enabled": False, "context_enabled": False}
    }
    old = exercise(case, config_type=Config, stimulus_type=Stimulus, factory=NativeEngine)
    new = exercise(neutral, config_type=ContinuousConfig, stimulus_type=Stimulus, factory=NativeContinuousEngine)
    for snapshot in new:
        snapshot["dynamics"] = "threemind.causal/9"
        snapshot["schema"] = "threemind.state/6"
        snapshot["config"] = ContinuousConfig(**snapshot["config"]).base().to_dict()
        for key in ("definition", "definition_hash", "operator_state"):
            snapshot.pop(key)
    assert_state_close(new, old)
