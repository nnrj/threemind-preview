from dataclasses import replace

import pytest
from test_causal9_baseline import assert_state_close

from threemind_core import StateImage, Stimulus
from threemind_kernels.memory import MemoryConfig, MemoryEngine
from threemind_kernels.novelty import NoveltyConfig, NoveltyEngine
from threemind_kernels.novelty_native import NativeNoveltyEngine


@pytest.fixture(params=[NoveltyEngine, NativeNoveltyEngine])
def factory(request):
    return request.param


def natural_birth(factory, **config):
    engine = factory(NoveltyConfig(novelty_mode="arrival-window", **config))
    for t, channels in [(0, ((1, 0.4), (2, 0.4))), (70_000, ((1, 0.4), (3, 0.4)))]:
        engine.inject(Stimulus(t, channels))
        engine.advance_to(t)
    return engine


def neutral(engine):
    value = engine.capture_state().to_dict()
    for name in ("dynamics", "schema", "definition", "definition_hash"):
        value.pop(name)
    value["config"].pop("novelty_mode", None)
    value["operator_state"].pop("novelty", None)
    return value


def test_immediate_choice_exactly_preserves_memory1():
    old, new = MemoryEngine(), NoveltyEngine(NoveltyConfig(novelty_mode="immediate"))
    for t in (0, 70_123, 199_999, 213_555, 450_003):
        for engine in (old, new):
            engine.inject(Stimulus(t, ((1, 0.6), (t // 50_000 + 2, 0.7)), 1.5))
            engine.advance_to(t + 11_357)
        assert neutral(old) == neutral(new)


def test_empty_arrival_window_adds_no_numerical_steps(factory):
    old = MemoryEngine(MemoryConfig(propagation_rate=0, delay_us=17_311))
    new = factory(NoveltyConfig(propagation_rate=0, delay_us=17_311, novelty_mode="arrival-window"))
    for t, channels in [(0, ((1, 0.4), (2, 0.4))), (70_000, ((1, 0.4), (3, 0.4)))]:
        for engine in (old, new):
            engine.inject(Stimulus(t, channels))
            engine.advance_to(t)
    for engine in (old, new):
        engine.advance_to(117_311)
    assert_state_close(neutral(new), neutral(old))


def test_no_future_read_and_exact_deadline_arrival(factory):
    engine = natural_birth(factory)
    assert engine.metrics()["novelty"]["pending"] == 2
    engine.advance_to(109_999)
    assert engine.metrics()["novelty"]["awarded"] == 0
    # The queued signal at 110 ms is received before the birth-window settlement.
    engine.advance_to(110_000)
    result = engine.metrics()["novelty"]
    assert result["awarded"] == 2 and result["pending"] == 0
    assert 0 < result["requested_bonus"] < 0.036
    saved = engine.capture_state()
    engine.advance_to(199_999)
    assert engine.metrics()["novelty"]["requested_bonus"] == result["requested_bonus"]
    assert saved.digest != engine.capture_state().digest


def test_pending_restore_cross_backend_and_batches():
    reference = natural_birth(NoveltyEngine)
    native = NativeNoveltyEngine(state=reference.capture_state())
    for t in (100_001, 109_999, 110_000, 321_773):
        reference.advance_to(t)
        native.advance_to(t)
        assert_state_close(native.capture_state().to_dict(), reference.capture_state().to_dict())
        a, b = reference.capture_state(), native.capture_state()
        reference, native = NoveltyEngine(state=b), NativeNoveltyEngine(state=a)
        assert reference.capture_state().digest == b.digest
        assert native.capture_state().digest == a.digest
    whole = natural_birth(NativeNoveltyEngine)
    whole.advance_to(321_773)
    assert_state_close(whole.capture_state().to_dict(), native.capture_state().to_dict())


def test_no_neighbour_no_arrival_disabled_and_strong_reentry(factory):
    empty = factory(NoveltyConfig(novelty_mode="arrival-window"))
    empty.inject(Stimulus(0, ((1, 0.8), (2, 0.8))))
    empty.advance_to(200_000)
    assert empty.metrics()["novelty"]["ineligible"] == 2
    for config, reason in [
        ({"propagation_rate": 0}, "no_reentry"),
        ({"local_novelty_gain": 0}, "disabled"),
        ({"novelty_touch_reference": 0.00001}, "reference_reached"),
    ]:
        engine = natural_birth(factory, **config)
        engine.advance_to(200_000)
        assert engine.metrics()["novelty"][reason] == 2
        assert engine.metrics()["novelty"]["requested_bonus"] == 0


def test_deletion_cancels_birth_and_rebirth_never_reuses_pending(factory):
    engine = natural_birth(factory)
    engine.intervene(edges=[(1, 3)], action="disconnect_edges")
    assert engine.metrics()["novelty"]["cancelled"] == 1
    engine.inject(Stimulus(70_000, ((1, 0.4), (3, 0.4))))
    engine.advance_to(70_000)
    rows = engine.capture_state().to_dict()["operator_state"]["novelty"]["pending"]
    assert next(row for row in rows if row["source"] == 1)["serial"] == 3
    engine.advance_to(110_000)
    assert engine.metrics()["novelty"]["awarded"] == 2
    engine.intervene(nodes=[3], action="delete_nodes")
    assert all(
        row["source"] != 3 and row["target"] != 3
        for row in engine.capture_state().to_dict()["operator_state"]["novelty"]["pending"]
    )


def test_state_validation_and_immutable_mode(factory):
    engine = natural_birth(factory)
    for field, bad in [("deadline_us", "0"), ("serial", 0), ("source", 999), ("gain", -1)]:
        value = engine.capture_state().to_dict()
        value["operator_state"]["novelty"]["pending"][0][field] = bad
        with pytest.raises(ValueError):
            factory(state=StateImage.from_dict(value))
    with pytest.raises(ValueError, match="immutable"):
        engine.reconfigure(replace(engine.config, novelty_mode="immediate"))


def test_strong_impulse_still_works_and_is_not_activation_gain(factory):
    values = []
    for gain in (0, 0.075):
        engine = factory(NoveltyConfig(intensity_gain=gain))
        engine.inject(Stimulus(0, ((1, 1.0), (2, 1.0)), 1.5))
        engine.advance_to(0)
        values.append(engine.capture_state().to_dict())
    assert values[0]["nodes"] == values[1]["nodes"]
    assert values[1]["edges"][0]["stability"] > values[0]["edges"][0]["stability"]


def test_configuration_exposes_choice_and_checks_readonly():
    from threemind_lab.configuration import catalogue, validate_configuration

    # The catalogue contract and JSON save must enforce the same constraint.
    data = catalogue()
    field = next(f for f in data["fields"] if f["path"] == "config.novelty_mode")
    assert field["immutable"] and len(field["choices"]) == 2
    original = validate_configuration({"kernel_id": NoveltyEngine.dynamics, "environment": "manual"})["spec"]
    changed = dict(original, config=original["config"] | {"novelty_mode": "immediate"})
    assert not validate_configuration(changed, current=original)["valid"]


def test_structural_birth_clears_pending_but_keeps_structure(factory):
    from threemind_runtime import birth

    parent = natural_birth(factory)
    child = factory(state=birth(parent.capture_state()))
    assert len(child.graph()["edges"]) == len(parent.graph()["edges"])
    assert child.metrics()["novelty"]["pending"] == 0
    assert child.metrics()["novelty"]["births"] == 0
    assert child.time_us == 0 and child.life == "waiting"


def test_pending_birth_window_is_fixed_when_future_rhythm_is_reconfigured(factory):
    engine = natural_birth(factory)
    before = engine.capture_state().to_dict()["operator_state"]["novelty"]["pending"]
    engine.reconfigure(replace(engine.config, propagation_interval_us=200_000, delay_us=30_000))
    saved = engine.capture_state()
    assert saved.to_dict()["operator_state"]["novelty"]["pending"] == before
    restored = factory(state=saved)
    for copy in (engine, restored):
        copy.advance_to(110_000)
    assert engine.metrics()["novelty"]["pending"] == 0
    assert engine.capture_state().digest == restored.capture_state().digest
