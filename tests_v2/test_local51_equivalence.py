"""Per-boundary /5.1 optimization witnesses; no restored formal research subject."""

import copy
import importlib.util
import math
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from local51_baseline import FROZEN_NATIVE, FROZEN_PYTHON
from test_local5_interop import assert_equivalent

from threemind_core import StateImage, Stimulus
from threemind_kernels.local5 import Local5Config, Local5Engine
from threemind_kernels.local51 import Local51Config, Local51Engine

_spec = importlib.util.spec_from_file_location(
    "memory51_witnesses", Path(__file__).resolve().parents[1] / "tools/memory51_witnesses.py"
)
witnesses = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = witnesses
_spec.loader.exec_module(witnesses)


def need_native51():
    native = pytest.importorskip("_threemind_native")
    if not hasattr(native, "NativeLocal51"):
        pytest.skip("the /5.1 native extension must be built in the isolated verification environment")


@pytest.mark.parametrize("backend", ["python", "native"])
@pytest.mark.parametrize("name,options", list(witnesses.cases().items()))
def test_old_five_still_matches_the_independently_frozen_full_trace(backend, name, options):
    if backend == "native":
        pytest.importorskip("_threemind_native")
    frozen = FROZEN_PYTHON if backend == "python" else FROZEN_NATIVE
    assert witnesses.digest(witnesses.trace("5", backend, options)) == frozen[name]


@pytest.mark.parametrize("backend", ["python", "native"])
@pytest.mark.parametrize("name,options", list(witnesses.cases().items()))
def test_each_input_phase_restore_and_configuration_change_is_exact(backend, name, options):
    if backend == "native":
        need_native51()
    before = witnesses.trace("5", backend, options)
    after = witnesses.trace("5.1", backend, options)
    assert len(before) == len(after) == 18
    for left, right in zip(before, after):
        assert left["label"] == right["label"]
        assert witnesses.normalize(left) == witnesses.normalize(right), (name, left["label"])


@pytest.mark.parametrize("name,options", list(witnesses.cases().items()))
def test_independent_python_native_trajectories_match_existing_float_tolerance(name, options):
    need_native51()
    for left, right in zip(witnesses.trace("5.1", "python", options), witnesses.trace("5.1", "native", options)):
        assert_equivalent(left, right, path=name + "/" + left["label"])


@pytest.mark.parametrize("backend", ["python", "native"])
def test_cross_version_state_is_rejected_not_migrated(backend):
    if backend == "native":
        need_native51()
    _, old = witnesses.factories("5", backend)
    _, new = witnesses.factories("5.1", backend)
    for source, target in ((old, new), (new, old)):
        with pytest.raises(ValueError, match="identity|schema"):
            target(state=source().capture_state())


@pytest.mark.parametrize("backend", ["python", "native"])
@pytest.mark.parametrize("mode", ["adaptive-half-life", "legacy-stability"])
@pytest.mark.parametrize("phase", ["aligned", "asynchronous"])
def test_batching_observation_and_extreme_wall_clock_do_not_change_state(backend, mode, phase, monkeypatch):
    if backend == "native":
        need_native51()
    config_type, factory = witnesses.factories("5.1", backend)
    config = config_type(consolidation_mode=mode, propagation_phase=phase, quiescence_death_us=10**12)
    one, batched = factory(config), factory(config)
    for e in (one, batched):
        for i, when in enumerate((0, 73000, 180000, 611337, 1200000)):
            e.inject(Stimulus(when, ((10, 0.8), (11, 0.6), (20 + i % 2, 0.4))))
    one.advance_to(2300000)
    for when in (0, 1, 180000, 300000, 611337, 700000, 1200000, 2300000):
        batched.advance_to(when)
        before = batched.capture_state().payload
        # No waiting: a synthetic host clock jump cannot become simulated time.
        monkeypatch.setattr("time.time", lambda: 60_000_000_000 * 365 * 86400.0)
        batched.metrics()
        batched.graph()
        batched.activations()
        assert batched.capture_state().payload == before
        batched = factory(state=batched.capture_state())
    assert batched.capture_state().to_dict() == one.capture_state().to_dict()


def test_cached_factor_tracks_new_config_and_never_escapes_into_saved_state():
    old, new = Local5Engine(), Local51Engine()
    for e in (old, new):
        e.inject(Stimulus(0, ((1, 0.8), (2, 0.7))))
        e.advance_to(100000)
    for tau, enabled in ((0.71, True), (0.19, False), (0.19, True), (0.71, True)):
        for e in (old, new):
            e.reconfigure(replace(e.config, eligibility_tau=tau, eligibility_decay_enabled=enabled))
            e.advance_to(e.time_us + 100000)
        assert witnesses.normalize(old.capture_state().to_dict()) == witnesses.normalize(new.capture_state().to_dict())
        new = Local51Engine(state=new.capture_state())
    assert set(new.config.to_dict()) == set(Local5Config().to_dict())
    assert math.isfinite(new.config.eligibility_tau)


@pytest.mark.parametrize("backend", ["python", "native"])
def test_accepted_leading_zero_object_clocks_keep_saved_representation(backend):
    if backend == "native":
        need_native51()
    pair = []
    for version in ("5", "5.1"):
        config_type, seed_factory = witnesses.factories(version, "python")
        _, factory = witnesses.factories(version, backend)
        seed = seed_factory(config_type(quiescence_death_us=10**12))
        seed.inject(Stimulus(0, ((1, 0.8), (2, 0.7))))
        seed.advance_to(100000)
        document = copy.deepcopy(seed.capture_state().to_dict())
        for group in ("nodes", "edges"):
            for row in document[group]:
                for key, value in row.items():
                    if key.endswith("_us") and isinstance(value, str):
                        row[key] = "00" + value
        pair.append(factory(state=StateImage.from_dict(document)))
    assert witnesses.normalize(pair[0].capture_state().to_dict()) == witnesses.normalize(pair[1].capture_state().to_dict())
    for engine in pair:
        engine.inject(Stimulus(100000, ((1, 0.2), (3, 0.4))))
        engine.advance_to(200000)
    assert witnesses.normalize(pair[0].capture_state().to_dict()) == witnesses.normalize(pair[1].capture_state().to_dict())


@pytest.mark.parametrize("backend", ["python", "native"])
def test_restored_signal_preserves_accepted_opaque_fields_and_queue_clock(backend):
    if backend == "native":
        need_native51()
    pair = []
    for version in ("5", "5.1"):
        config_type, factory = witnesses.factories(version, backend)
        engine = factory(config_type(quiescence_death_us=10**12))
        engine.inject(Stimulus(0, ((1, 0.8), (2, 0.7))))
        engine.advance_to(100000)
        document = engine.capture_state().to_dict()
        pending = [item for item in document["queue"] if item["kind"] == "signal"]
        assert pending, "fixture must contain an emitted signal pending arrival"
        for event in pending:
            event["payload"]["opaque_wire_field"] = {"value": [1, "preserve-me"]}
            event["time_us"] = "000" + event["time_us"]
        restored = factory(state=StateImage.from_dict(document))
        saved = restored.capture_state().to_dict()
        for expected, actual in zip(document["queue"], saved["queue"]):
            assert actual["payload"] == expected["payload"]
            # The established Python heap serializes a canonical clock; Rust
            # retains the Event string. Preserve each backend's own old rule.
            clock = expected["time_us"] if backend == "native" else str(int(expected["time_us"]))
            assert actual["time_us"] == clock
        pair.append(restored)
    assert witnesses.normalize(pair[0].capture_state().to_dict()) == witnesses.normalize(pair[1].capture_state().to_dict())
    observed = [[], []]
    for engine, records in zip(pair, observed):
        engine.advance_to(200000, observer=records.append)
        arrived = [row for row in records if row["kind"] == "signal"]
        assert any("opaque_wire_field" in row["payload"] for row in arrived)
    assert observed[0] == observed[1]
    assert witnesses.normalize(pair[0].capture_state().to_dict()) == witnesses.normalize(pair[1].capture_state().to_dict())


@pytest.mark.parametrize("backend", ["python", "native"])
@pytest.mark.parametrize("mutation", ["negative-signal", "missing-features", "out-of-range-feature"])
def test_typed_queue_does_not_weaken_historical_signal_validation(backend, mutation):
    if backend == "native":
        need_native51()
    for version in ("5", "5.1"):
        config_type, factory = witnesses.factories(version, backend)
        engine = factory(config_type())
        engine.inject(Stimulus(0, ((1, 0.8), (2, 0.7))))
        engine.advance_to(100000)
        document = engine.capture_state().to_dict()
        event = next(item for item in document["queue"] if item["kind"] == "signal")
        message = event["payload"]["messages"][0]
        if mutation == "negative-signal":
            message[2] = -0.1
        elif mutation == "missing-features":
            message[3] = []
        else:
            message[3][0] = 1.1
        with pytest.raises(ValueError):
            factory(state=StateImage.from_dict(document))


@pytest.mark.parametrize("backend", ["python", "native"])
@pytest.mark.parametrize("mode", ["adaptive-half-life", "legacy-stability"])
@pytest.mark.parametrize("options", [
    {}, {"node_retention_mode": "manual"},
    {"node_retention_mode": "manual", "prune_support": 0.0, "dead_node_retention_us": 80000000},
    {"retain_nodes": True},
])
def test_idle_expiry_recycling_boundaries_stay_identical(backend, mode, options):
    if backend == "native":
        need_native51()
    pair = []
    for version in ("5", "5.1"):
        config_type, factory = witnesses.factories(version, backend)
        pair.append(factory(config_type(
            consolidation_mode=mode, propagation_rate=0.0, inhibition=False,
            context_enabled=False, quiescence_death_us=10**12, **options,
        )))
    for engine in pair:
        engine.inject(Stimulus(0, ((1, 0.8), (2, 0.7))))
    for when in (100000, 1000000, 79999999, 80000000, 80000001, 120000000):
        for engine in pair:
            engine.advance_to(when)
        assert witnesses.normalize(pair[0].capture_state().to_dict()) == witnesses.normalize(pair[1].capture_state().to_dict())


@pytest.mark.parametrize("mode", ["adaptive-half-life", "legacy-stability"])
def test_synthetic_dormant_contact_wakes_locally_without_reviving_deleted_objects(mode):
    pairs = []
    for config_type, factory in ((Local5Config, Local5Engine), (Local51Config, Local51Engine)):
        e = factory(config_type(
            consolidation_mode=mode, retain_nodes=True, dormant_traces_enabled=True, revival_enabled=True,
            node_wake_threshold=0.05, edge_wake_threshold=0.1, inhibition=False, context_enabled=False,
            propagation_rate=0.0, quiescence_death_us=10**12,
        ))
        e.inject(Stimulus(0, ((1, 0.8), (2, 0.8))))
        e.advance_to(2000000)
        for key in tuple(e.edges):
            e._remove_edge(key)
        pairs.append(e)
    for e in pairs:
        # Explicit engineering setup: the two endpoints deliver real local events.
        e._event(e.time_us + 1, "wake", {"edge": [0, 1], "sender": 0, "value": 0.06})
        e._event(e.time_us + 1, "wake", {"edge": [0, 1], "sender": 1, "value": 0.06})
        e.advance_to(e.time_us + 1)
    assert pairs[0].audit["edges_awakened"] > 0
    assert witnesses.normalize(pairs[0].capture_state().to_dict()) == witnesses.normalize(pairs[1].capture_state().to_dict())
    for e in pairs:
        e.intervene(nodes=(0,), action="delete_nodes")
        e._event(e.time_us + 1, "wake", {"edge": [0, 1], "sender": 1, "value": 1.0})
        e.advance_to(e.time_us + 1)
        assert 0 not in e.nodes
    assert witnesses.normalize(pairs[0].capture_state().to_dict()) == witnesses.normalize(pairs[1].capture_state().to_dict())
