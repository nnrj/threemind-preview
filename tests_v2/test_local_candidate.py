"""Version boundary and causal mechanism tests; no organism curriculum or reader fitting."""

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest
from test_causal9_baseline import assert_state_close

from threemind_core import StateImage, Stimulus
from threemind_kernels.local import KERNEL_ID, LocalConfig, LocalEngine
from threemind_kernels.local_native import NativeLocalEngine
from threemind_kernels.retention import RetentionConfig, RetentionEngine
from threemind_kernels.retention_native import NativeRetentionEngine
from threemind_runtime.host import create_engine
from threemind_runtime.inheritance import birth

BACKENDS = [LocalEngine, NativeLocalEngine]


def feed(e):
    for i, t in enumerate((0, 73000, 180000, 610000, 1200000, 2400000, 6000000)):
        e.inject(Stimulus(t, ((10, 0.8), (11, 0.6), (20 + i % 2, 0.4))))


@pytest.mark.parametrize("mode", ["adaptive-half-life", "legacy-stability"])
@pytest.mark.parametrize("phase", ["aligned", "asynchronous"])
@pytest.mark.parametrize("arrival", ["coincident", "sequential"])
@pytest.mark.parametrize("source", ["unified", "legacy-source"])
def test_independent_backends_observation_batching_and_cross_restore(mode, phase, arrival, source):
    c = LocalConfig(
        consolidation_mode=mode,
        propagation_phase=phase,
        arrival_mode=arrival,
        reception_mode=source,
        quiescence_death_us=10**12,
    )
    a, b = LocalEngine(c), NativeLocalEngine(c)
    feed(a)
    feed(b)
    for t in (611337, 1000000, 5000000, 12000000, 120000000):
        a.advance_to(t, lambda _: (a.graph(), a.metrics(), a.capture_state()))
        b.advance_to(t)
        assert_state_close(a.capture_state().to_dict(), b.capture_state().to_dict())
        for factory in BACKENDS:
            restored = factory(state=a.capture_state())
            uninterrupted = factory(state=b.capture_state())
            restored.advance_to(t + 123456)
            uninterrupted.advance_to(t + 123456)
            assert_state_close(restored.capture_state().to_dict(), uninterrupted.capture_state().to_dict())
    one = LocalEngine(c)
    feed(one)
    one.advance_to(120000000)
    assert_state_close(a.capture_state().to_dict(), one.capture_state().to_dict())


@pytest.mark.parametrize("factory", [RetentionEngine, NativeRetentionEngine])
def test_memory3_frozen_before_local4(factory):
    frozen = json.loads((Path(__file__).parent / "fixtures/memory3-before-local4.json").read_text(encoding="utf-8"))
    for mode in ("adaptive-half-life", "legacy-stability"):
        e = factory(RetentionConfig(consolidation_mode=mode, quiescence_death_us=10**12))
        for i, t in enumerate((0, 73000, 180000, 800000, 1400000, 2800000)):
            e.inject(Stimulus(t, ((10, 0.8), (11, 0.6), (20 + i % 2, 0.4))))
        for row in frozen["samples"]:
            if row["mode"] == mode:
                e.advance_to(int(row["time_us"]))
                assert_state_close(e.capture_state().to_dict(), row["state"])


def quiet_fixture(**options):
    c = LocalConfig(
        inhibition=False,
        context_enabled=False,
        stp_enabled=False,
        fast_enabled=False,
        propagation_rate=0.0,
        quiescence_death_us=10**12,
        **options,
    )
    e = LocalEngine(c)
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.8))))
    e.advance_to(2000000)
    return e


@pytest.mark.parametrize("factory", BACKENDS)
def test_idle_expiry_and_retention_learning(factory):
    e = quiet_fixture()
    f = factory(state=e.capture_state())
    f.advance_to(120000000)
    assert f.metrics()["nodes"] == f.metrics()["edges"] == 0
    c = replace(e.config, propagation_rate=4.2, stp_enabled=False, context_enabled=False)
    f = factory(c)
    for i in range(20):
        f.inject(Stimulus(i * 100000, ((1, 1.0), (2, 1.0))))
    f.advance_to(2000000)
    assert any(row["half_life"] > c.memory_half_life_min_s for row in f.capture_state().to_dict()["edges"])


def test_local_access_is_independent_of_unrelated_graph_and_scan_control():
    c = LocalConfig(retain_nodes=True, inhibition=False, context_enabled=False, quiescence_death_us=10**12)
    samples = []
    for size in (2, 1002):
        e = LocalEngine(c)
        for i in range(size):
            e._birth(1000 + i)
        e.inject(Stimulus(0, ((1000, 0.8), (1001, 0.8))))
        e.advance_to(100000)
        samples.append(e.audit.copy())
    assert samples[0] == samples[1]
    a = LocalEngine(c)
    b = LocalEngine(replace(c, propagation_mode="scan-control"))
    feed(a)
    feed(b)
    a.advance_to(5000000)
    b.advance_to(5000000)
    assert_state_close(a.graph(), b.graph())
    assert b.audit["scan_visits"] > 0 and a.audit["scan_visits"] == 0


def test_source_independence_and_arrival_integration_are_explicit():
    c = LocalConfig(context_enabled=False, inhibition=False, quiescence_death_us=10**12)
    a, b = LocalEngine(c), LocalEngine(c)
    for e in (a, b):
        e._birth(1)
        e._birth(2)
    a._receive([(0, [[-1, 0, 0.2, [0.0] * 4], [-1, 1, 0.2, [0.0] * 4]], True, 1.0)])
    b._receive([(0, [[50, 0, 0.2, [0.0] * 4], [50, 1, 0.2, [0.0] * 4]], False, 1.0)])
    for left, right in zip(a.observation_nodes(), b.observation_nodes()):
        for k in ("direct", "associative"):
            left.pop(k)
            right.pop(k)
        assert left == right
    assert a.induced_edges([0, 1]) == b.induced_edges([0, 1])
    values = []
    for mode in ("coincident", "sequential"):
        e = LocalEngine(replace(c, context_enabled=True, arrival_mode=mode))
        e._birth(1)
        e._receive([(0, [[-1, 0, 0.1, [0.0] * 4], [-1, 0, 0.1, [0.0] * 4]], True, 1.0)])
        values.append(e.nodes[0].activation)
    assert values == pytest.approx([0.1, 0.2])


@pytest.mark.parametrize("distribution", ["counter-random", "stream-random"])
def test_local_energy_conservation_fair_uptake_and_independent_rng(distribution):
    c = LocalConfig(
        energy_simulation_enabled=True,
        energy_initial_reserve=0.0,
        energy_region_count=1,
        energy_distribution=distribution,
        energy_direct_cost=0.0,
        quiescence_death_us=10**12,
    )
    a, b = LocalEngine(c), NativeLocalEngine(c)
    for e in (a, b):
        e.inject(Stimulus(0, ((1, 0.1), (2, 0.1))))
        e.supply_energy(0.8, time_us=0)
        e.advance_to(0)
    assert_state_close(a.capture_state().to_dict(), b.capture_state().to_dict())
    assert [n["reserve"] for n in a.observation_nodes()] == pytest.approx([0.4, 0.4])
    for e in (a, b):
        e.supply_energy(0.5, time_us=200000)
        e.advance_to(1000000)
        m = e.metrics()["energy"]
        consumed = sum(
            m[k] for k in ("consumed_direct", "consumed_associative", "consumed_inhibition", "consumed_maintenance")
        )
        assert m["initial_total"] + m["offered_total"] == pytest.approx(m["reserve"] + consumed + m["discarded_total"])
    assert_state_close(a.capture_state().to_dict(), b.capture_state().to_dict())
    restored = NativeLocalEngine(state=a.capture_state())
    restored.supply_energy(0.3, time_us=2000000)
    a.supply_energy(0.3, time_us=2000000)
    restored.advance_to(2000000)
    a.advance_to(2000000)
    assert_state_close(a.capture_state().to_dict(), restored.capture_state().to_dict())


@pytest.mark.parametrize("factory", BACKENDS)
def test_identity_configuration_and_inheritance(factory):
    e = factory(LocalConfig(quiescence_death_us=10**12))
    feed(e)
    e.advance_to(611337)
    child = birth(e.capture_state())
    born = factory(state=child)
    assert born.time_us == 0 and born.life == "waiting"
    assert born.metrics()["nodes"] == e.metrics()["nodes"]
    assert all(a == 0 for _, a in born.activations())
    with pytest.raises(ValueError):
        factory(state=RetentionEngine().capture_state())
    with pytest.raises(ValueError):
        e.reconfigure(replace(e.config, arrival_mode="sequential"))
    with pytest.raises(ValueError):
        e.modulate_input()
    assert create_engine(kernel_id=KERNEL_ID, backend="reference").dynamics == KERNEL_ID


@pytest.mark.parametrize("factory", BACKENDS)
def test_missing_expiry_and_corrupt_values_rejected(factory):
    e = quiet_fixture()
    for corrupt in ("timers", "node", "clock"):
        d = e.capture_state().to_dict()
        if corrupt == "timers":
            d["timers"] = [row for row in d["timers"] if row[0] != 2]
        if corrupt == "node":
            d["nodes"][0]["support"] = -0.1
        if corrupt == "clock":
            d["nodes"][0]["energy_us"] = str(e.time_us + 1)
        with pytest.raises(ValueError):
            factory(state=StateImage.from_dict(d))


@pytest.mark.parametrize("factory", BACKENDS)
def test_zero_edge_floor_is_restorable_and_missing_local_emission_is_rejected(factory):
    e = quiet_fixture(prune_weight=0.0)
    assert not any(row[0] == 2 for row in e.capture_state().to_dict()["timers"])
    restored = factory(state=e.capture_state())
    restored.advance_to(120000000)
    assert restored.metrics()["edges"] == 2
    active = LocalEngine(LocalConfig())
    active.inject(Stimulus(0, ((1, 0.8), (2, 0.8))))
    active.advance_to(0)
    bad = active.capture_state().to_dict()
    bad["timers"] = [row for row in bad["timers"] if row[0] != 0]
    with pytest.raises(ValueError):
        factory(state=StateImage.from_dict(bad))


@pytest.mark.parametrize("factory", BACKENDS)
@pytest.mark.parametrize(
    "kind,payload",
    [
        ("signal", {"messages": [[-1, 0, -0.1, [0.0] * 4]]}),
        ("inhibition", {"values": [[0, -0.1]]}),
        ("wake", {"edge": [0, 1], "sender": 2, "value": 0.1}),
    ],
)
def test_malformed_queued_signals_rejected_on_restore(factory, kind, payload):
    e = quiet_fixture()
    e._event(e.time_us + 1, kind, payload)
    with pytest.raises(ValueError):
        factory(state=e.capture_state())


def test_optional_spatial_gate_is_backend_consistent():
    c = LocalConfig(spatial_embedding=True, spatial_radius=0.8, quiescence_death_us=10**12)
    a, b = LocalEngine(c), NativeLocalEngine(c)
    feed(a)
    feed(b)
    a.advance_to(5000000)
    b.advance_to(5000000)
    assert_state_close(a.capture_state().to_dict(), b.capture_state().to_dict())
    assert_state_close(a.spatial_geometry(), b.spatial_geometry())


def test_exported_defaults_and_lab_catalog_are_consistent():
    from threemind_lab.configuration import catalogue, default_spec, validate_configuration

    d = json.loads(Path("crates/threemind-core/src/local-defaults.json").read_text(encoding="utf-8"))
    assert d == LocalConfig().to_dict()
    spec = default_spec()
    spec.update(kernel_id=KERNEL_ID, config=d)
    assert validate_configuration(spec)["valid"]
    cat = catalogue()
    fields = {x["path"] for x in cat["fields"] if KERNEL_ID in x.get("kernels", [])}
    for key in ("propagation_mode", "arrival_mode", "energy_model", "energy_seed", "consolidation_mode"):
        assert "config." + key in fields


@pytest.mark.parametrize("factory", BACKENDS)
@pytest.mark.parametrize(
    "mode,threshold,wait", [("automatic", 0.006, 80000000), ("manual", 0.3, 80000000), ("manual", 0.0, 3000000)]
)
def test_reclamation_modes_and_retouch(factory, mode, threshold, wait):
    e = quiet_fixture(
        node_retention_mode=mode, prune_support=threshold, dead_node_retention_us=wait, node_prune_after_us=0
    )
    for key in tuple(e.edges):
        e._remove_edge(key, True)
    f = factory(state=e.capture_state())
    if mode == "manual" and threshold == 0:
        f.advance_to(4900000)
        assert f.metrics()["nodes"] == 2
        f.inject(Stimulus(4900000, ((1, 0.5),)))
        f.advance_to(5100000)
        assert f.metrics()["nodes"] == 1
    f.advance_to(120000000)
    assert f.metrics()["nodes"] == 0


@pytest.mark.parametrize("factory", BACKENDS)
def test_two_end_local_wake_preserves_weight_and_silence(factory):
    e = quiet_fixture(
        retain_nodes=True,
        dormant_traces_enabled=True,
        revival_enabled=True,
        node_wake_threshold=0.05,
        edge_wake_threshold=0.13,
    )
    for key in tuple(e.edges):
        e.edges[key].weight = 0.007
        e._remove_edge(key)
    key = (0, 1)
    for sender, value in ((0, 0.06), (1, 0.08)):
        e._event(e.time_us + 1, "wake", {"edge": list(key), "sender": sender, "value": value})
    original = e.capture_state()
    f = factory(state=original)
    f.advance_to(e.time_us + 1)
    d = f.capture_state().to_dict()
    assert d["audit"]["edges_awakened"] == 1 and d["audit"]["nodes_awakened"] == 2
    assert next(edge["weight"] for edge in d["edges"] if (edge["source"], edge["target"]) == key) < 0.008
    f.advance_to(e.time_us + 100000)
    assert next(
        edge["sleeping"] for edge in f.capture_state().to_dict()["edges"] if (edge["source"], edge["target"]) == key
    )
    f = factory(state=original)
    f.intervene(edges=[key])
    f.advance_to(e.time_us + 1)
    assert f.capture_state().to_dict()["audit"]["edges_awakened"] == 0
    f.reconfigure(replace(f.config, dormant_traces_enabled=False))
    assert not f.config.revival_enabled and not f.capture_state().to_dict()["edges"]


@pytest.mark.parametrize("formula", ["log-saturating", "linear-saturating"])
@pytest.mark.parametrize("energy_model", ["local-field", "global-ledger"])
def test_optional_energy_maintenance_and_formula_reconfigure(formula, energy_model):
    c = LocalConfig(
        memory_growth_formula=formula,
        energy_model=energy_model,
        energy_simulation_enabled=True,
        energy_starvation_damage_enabled=True,
        energy_initial_reserve=0.02,
        energy_maintenance_cost_per_node=0.1,
        energy_region_count=2,
        quiescence_death_us=10**12,
    )
    a, b = LocalEngine(c), NativeLocalEngine(c)
    feed(a)
    feed(b)
    for e in (a, b):
        e.supply_energy(0.1, time_us=1300000)
        e.advance_to(2600000)
    assert_state_close(a.capture_state().to_dict(), b.capture_state().to_dict())
    for e in (a, b):
        e.reconfigure(replace(c, plasticity=False, context_enabled=False, stp_recovery_tau_s=0.5))
    for e in (a, b):
        e.advance_to(8000000)
    assert_state_close(a.capture_state().to_dict(), b.capture_state().to_dict())


@pytest.mark.parametrize(
    "policy",
    [
        "homeostasis_enabled",
        "attention_competition_enabled",
        "propagation_limit",
        "edge_adaptation_limit",
        "edge_birth_policy",
    ],
)
def test_unsupported_global_policies_are_rejected(policy):
    value = {
        "homeostasis_enabled": True,
        "attention_competition_enabled": True,
        "propagation_limit": 1,
        "edge_adaptation_limit": 1,
        "edge_birth_policy": "temporal",
    }[policy]
    with pytest.raises(ValueError):
        LocalConfig(**{policy: value})


def test_local_config_model_choices_are_locked_in_lab():
    from threemind_lab.configuration import default_spec, validate_configuration

    spec = default_spec()
    spec.update(kernel_id=KERNEL_ID, config=LocalConfig().to_dict())
    for key, value in [
        ("arrival_mode", "sequential"),
        ("energy_model", "global-ledger"),
        ("energy_seed", 1),
        ("propagation_interval_us", 200000),
    ]:
        new = copy.deepcopy(spec)
        new["config"][key] = value
        result = validate_configuration(new, current=spec)
        assert not result["valid"] and any(x["path"] == "config." + key for x in result["errors"])


@pytest.mark.parametrize("factory", BACKENDS)
def test_disabling_wake_cancels_inflight_wake_effect(factory):
    e = quiet_fixture(
        retain_nodes=True,
        dormant_traces_enabled=True,
        revival_enabled=True,
        node_wake_threshold=0.05,
        edge_wake_threshold=0.1,
    )
    for key in tuple(e.edges):
        e._remove_edge(key)
    e._event(e.time_us + 1, "wake", {"edge": [0, 1], "sender": 0, "value": 0.2})
    f = factory(state=e.capture_state())
    f.reconfigure(replace(f.config, revival_enabled=False))
    f.advance_to(e.time_us + 1)
    assert f.capture_state().to_dict()["audit"]["edges_awakened"] == 0


def test_local_artifact_extra_columns_cannot_be_dropped_or_replaced():
    from threemind_runtime.codec import join_local_objects, split_local_objects

    d = quiet_fixture().capture_state().to_dict()
    split_local_objects(d)
    # Emulate the base Arrow columns, then require all version-specific columns.
    from dataclasses import fields

    from threemind_core.engine import Edge, Node

    for name, kind in (("nodes", Node), ("edges", Edge)):
        allowed = {f.name for f in fields(kind)}
        d[name] = [{k: v for k, v in row.items() if k in allowed} for row in d[name]]
    for corrupt in ("missing", "truncated", "unknown"):
        bad = copy.deepcopy(d)
        if corrupt == "missing":
            bad.pop("local_object_columns")
        elif corrupt == "truncated":
            bad["local_object_columns"]["edges"].pop()
        else:
            bad["local_object_columns"]["nodes"][0]["new_field"] = 1
        with pytest.raises(ValueError):
            join_local_objects(bad)
    join_local_objects(d)
    assert d == quiet_fixture().capture_state().to_dict()


@pytest.mark.parametrize("factory", BACKENDS)
def test_strong_stimulation_cost_fatigue_and_learning_ablation(factory):
    c = LocalConfig(
        context_enabled=False,
        inhibition=False,
        retain_nodes=True,
        propagation_rate=0.0,
        energy_simulation_enabled=True,
        energy_region_count=1,
        quiescence_death_us=10**12,
    )
    normal, strong = factory(c), factory(c)
    for e, intensity in ((normal, 1.0), (strong, 3.0)):
        e.inject(Stimulus(0, ((1, 0.8),), intensity))
        e.advance_to(0)
    assert strong.metrics()["energy"]["consumed_direct"] > normal.metrics()["energy"]["consumed_direct"]
    assert strong.observation_nodes()[0]["fatigue"] > normal.observation_nodes()[0]["fatigue"] == 0
    strong.advance_to(5000000)
    strong.reconfigure(replace(c, strong_fatigue_enabled=False, plasticity=False))
    h = strong.observation_nodes()[0]["half_life"]
    strong.inject(Stimulus(5000000, ((1, 0.5),)))
    strong.advance_to(5000000)
    assert strong.observation_nodes()[0]["activation"] == pytest.approx(0.45)
    assert strong.observation_nodes()[0]["half_life"] == h


@pytest.mark.parametrize("factory", BACKENDS)
def test_novelty_reinforces_weight_without_becoming_half_life_dose(factory):
    c = LocalConfig(
        context_enabled=False,
        inhibition=False,
        activation_decay_enabled=False,
        propagation_rate=0.0,
        quiescence_death_us=10**12,
    )
    samples = []
    for gain in (0.0, 0.018):
        e = factory(replace(c, local_novelty_gain=gain))
        for t, channels in [(0, ((1, 0.5), (2, 0.5))), (200000, ((1, 0.5), (3, 0.5))), (250000, ((1, 0.01),))]:
            e.inject(Stimulus(t, channels))
        e.advance_to(310001)
        samples.append(next(edge for edge in e.graph()["edges"] if (edge["source"], edge["target"]) == (0, 2)))
    assert samples[1]["weight"] - samples[0]["weight"] == pytest.approx(0.018 * (1 - 0.009 / 0.2), abs=1e-9)
    assert samples[1]["half_life"] == samples[0]["half_life"] == c.memory_half_life_min_s
