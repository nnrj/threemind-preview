"""Local retention contract. Fixtures are instrument calibration, not learned subjects."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from test_causal9_baseline import assert_state_close

from threemind_core import StateImage, Stimulus
from threemind_kernels.novelty import NoveltyConfig, NoveltyEngine
from threemind_kernels.novelty_native import NativeNoveltyEngine
from threemind_kernels.retention import RetentionConfig, RetentionEngine, decay, grow
from threemind_kernels.retention_native import NativeRetentionEngine


@pytest.fixture(params=[RetentionEngine, NativeRetentionEngine])
def factory(request):
    return request.param


@pytest.mark.parametrize("factory", [NoveltyEngine, NativeNoveltyEngine])
def test_memory2_matches_prechange_native_witness(factory):
    frozen = json.loads((Path(__file__).parent / "fixtures/memory2-before-retention3.json").read_text(encoding="utf-8"))
    engine = factory(NoveltyConfig(novelty_mode="arrival-window"))
    rows = []
    for t, channels, intensity in [
        (0, ((1, 0.7), (2, 0.5)), 1.0),
        (70_000, ((1, 0.8), (3, 0.6)), 1.0),
        (173_771, ((1, 0.9), (2, 0.8), (3, 0.4)), 1.5),
    ]:
        engine.inject(Stimulus(t, channels, intensity))
        engine.advance_to(t + 13_731)
        rows.append(engine.capture_state().to_dict())
    engine.advance_to(611_337)
    rows.append(engine.capture_state().to_dict())
    assert_state_close(rows, frozen["snapshots"])


def controlled(factory, *, weight=0.02, half_life=30.0, support=0.1, **overrides):
    p = {
        "propagation_rate": 0.0,
        "inhibition": False,
        "quiescence_death_us": 10**12,
        "retain_nodes": True,
        "stp_enabled": False,
        "fast_enabled": False,
        "context_enabled": False,
    }
    p.update(overrides)
    e = RetentionEngine(RetentionConfig(**p))
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.8))))
    e.advance_to(0)
    for k, edge in e.edges.items():
        edge.weight = weight
        e.memory_edges[k] = [half_life, 0]
        e._engine._schedule_edge(k)
    for n in e.nodes.values():
        n.activation = n.inhibition = n.direct = n.associative = 0.0
        n.support = support
        e.memory_nodes[n.id] = [half_life, 0]
        e._engine._schedule_node(n.id)
    return factory(state=e.capture_state())


@pytest.mark.parametrize("mode", ["adaptive-half-life", "legacy-stability"])
@pytest.mark.parametrize("formula", ["log-saturating", "linear-saturating"])
@pytest.mark.parametrize("context", [False, True])
@pytest.mark.parametrize("node_mode", ["automatic", "manual"])
def test_backends_observers_batching_cross_restore(mode, formula, context, node_mode):
    p = RetentionConfig(
        consolidation_mode=mode,
        memory_growth_formula=formula,
        node_retention_mode=node_mode,
        context_enabled=context,
        stp_enabled=context,
        fast_enabled=context,
        dormant_traces_enabled=True,
        revival_enabled=True,
        node_wake_threshold=0.2,
        edge_wake_threshold=0.2,
    )
    a, b = RetentionEngine(p), NativeRetentionEngine(p)
    for t in (0, 70_771, 217_771, 317_771):
        outputs = ([], [])
        for e, out in zip((a, b), outputs):
            e.inject(Stimulus(t, ((1, 0.8), (2, 0.7), (3, 0.5)), 1.5))
            e.advance_to(t + 11_001, out.append)
        assert_state_close(outputs[0], outputs[1])
        assert_state_close(a.capture_state().to_dict(), b.capture_state().to_dict())
        x, y = a.capture_state(), b.capture_state()
        a, b = RetentionEngine(state=y), NativeRetentionEngine(state=x)
        assert a.capture_state().digest == y.digest
        assert b.capture_state().digest == x.digest
    for e in (a, b):
        e.reconfigure(replace(e.config, memory_learning_gain=0.3, dormant_traces_enabled=False))
    a.advance_to(631_771)
    for t in (333_333, 350_777, 631_771):
        b.advance_to(t)
    assert_state_close(a.capture_state().to_dict(), b.capture_state().to_dict())
    assert_state_close(a.graph(), b.graph())
    assert_state_close(a.observation_nodes(), b.observation_nodes())
    assert_state_close(a.induced_edges([1, 2]), b.induced_edges([1, 2]))
    for e in (a, b):
        s = e.capture_state().digest
        e.metrics()
        e.graph()
        e.observation_nodes()
        e.induced_edges([1, 2])
        assert e.capture_state().digest == s


def test_exact_passive_decay_and_idle_expiry(factory):
    e = controlled(factory, weight=0.1, half_life=3600.0)
    e.advance_to(300_000_000)
    expected, h = decay(0.1, 3600.0, 300.0, e.config)
    assert e.graph()["edges"][0]["weight"] == pytest.approx(expected, rel=1e-12)
    assert e.metrics()["retention"]["half_life_max_s"] == pytest.approx(h)
    # No full-graph materialization occurred during 30,000 solver steps.
    assert e.metrics()["retention"]["edge_settlements"] == 0
    short = controlled(factory, weight=0.009, memory_half_life_min_s=0.1, memory_half_life_max_s=10.0, half_life=0.1)
    short.advance_to(500_000)
    assert short.metrics()["edges"] == 0


@pytest.mark.parametrize("formula", ["log-saturating", "linear-saturating"])
def test_use_extends_half_life_without_weight_replacement(factory, formula):
    e = factory(
        RetentionConfig(
            memory_growth_formula=formula,
            memory_half_life_decay_rate=0.0,
            inhibition=False,
            stp_enabled=False,
            fast_enabled=False,
            context_enabled=False,
        )
    )
    for i in range(20):
        e.inject(Stimulus(i * 100_000, ((1, 1.0), (2, 1.0))))
        e.advance_to(i * 100_000)
    s = e.capture_state().to_dict()
    m = s["operator_state"]["retention"]
    assert all(row[2] > 30 for row in m["edges"])
    assert all(row[1] > 30 for row in m["nodes"])
    assert any(n["stability"] > 0 and n["local_plasticity"] < 1 for n in s["nodes"])
    # The same actual dose split at one time has no per-event fixed reward.
    p = e.config
    assert grow(grow(30, 0.03, p), 0.07, p) == pytest.approx(grow(30, 0.1, p), rel=1e-12)


def test_rejected_emission_and_no_weight_learning_do_not_credit_edges(factory):
    e = factory(RetentionConfig(stp_utilization=0.0, memory_half_life_decay_rate=0.0))
    e.inject(Stimulus(0, ((1, 1.0), (2, 1.0))))
    e.advance_to(500_000)
    assert all(row[2] == 30 for row in e.capture_state().to_dict()["operator_state"]["retention"]["edges"])
    assert e.metrics()["transport"]["sent"] == 0


def test_modes_share_positive_learning_and_novelty(factory):
    snapshots = []
    for mode in ("adaptive-half-life", "legacy-stability"):
        e = factory(RetentionConfig(consolidation_mode=mode, propagation_rate=0.0, inhibition=False))
        for channels in [((1, 0.8), (2, 0.7)), ((1, 0.8), (2, 0.7), (3, 0.5)), ((2, 0.9), (3, 0.8))]:
            e.inject(Stimulus(0, channels))
            e.advance_to(0)
        snapshots.append(e.capture_state().to_dict())
    assert_state_close(snapshots[0]["nodes"], snapshots[1]["nodes"])
    assert_state_close(snapshots[0]["edges"], snapshots[1]["edges"])


def test_novelty_still_awards_weight_without_half_life_bonus():
    e = RetentionEngine(RetentionConfig(propagation_rate=0.0))
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.7))))
    e.advance_to(0)
    e.inject(Stimulus(1, ((1, 0.8), (3, 0.5))))
    e.advance_to(1)
    k = next(iter(e.pending_novelty))
    row = e.pending_novelty[k]
    row["source_touch"] = row["reference"] * 0.2
    before = e.edges[k].weight
    h = e.memory_edges[k][0]
    deadline = int(row["deadline_us"])
    expected, _ = decay(before, h, (deadline - e.memory_edges[k][1]) / 1e6, e.config)
    e.advance_to(deadline)
    assert e.metrics()["novelty"]["weight_bonus"] > 0
    assert e.graph()["edges"][list(e.edges).index(k)]["weight"] > expected
    assert e.memory_edges[k][0] <= h


def test_no_unrelated_retention_visits(factory):
    counts = []
    for size in (2, 202):
        e = factory(RetentionConfig(max_edges=0, retain_nodes=True))
        e.inject(Stimulus(0, tuple((i, 0.1) for i in range(size))))
        e.advance_to(0)
        before = e.capture_state().to_dict()["operator_state"]["retention"]["audit"]
        e.inject(Stimulus(1, ((0, 0.2),)))
        e.advance_to(1)
        after = e.capture_state().to_dict()["operator_state"]["retention"]["audit"]
        counts.append({k: after[k] - before[k] for k in before})
    assert counts[0] == counts[1]
    assert counts[0]["node_settlements"] == 1


@pytest.mark.parametrize("mode,threshold,wait", [("automatic", 1.0, 1), ("manual", 0.5, 1), ("manual", 0.0, 300_000)])
def test_recycling_modes(factory, mode, threshold, wait):
    e = controlled(
        factory,
        weight=0.001,
        support=0.001,
        retain_nodes=False,
        node_retention_mode=mode,
        prune_support=threshold,
        node_prune_after_us=0,
        dead_node_retention_us=wait,
    )
    e.advance_to(200_000)
    if mode == "manual" and threshold == 0:
        assert e.metrics()["nodes"] == 2
        e.advance_to(500_000)
    assert e.metrics()["nodes"] == 0
    assert factory(state=e.capture_state()).capture_state().digest == e.capture_state().digest


def test_retouch_resets_isolated_wait(factory):
    e = controlled(
        factory,
        weight=0.001,
        retain_nodes=False,
        node_retention_mode="manual",
        prune_support=0,
        dead_node_retention_us=500_000,
        activation_tau=0.001,
    )
    e.advance_to(200_000)
    e.inject(Stimulus(400_000, ((1, 0.2),)))
    e.advance_to(800_000)
    assert e.metrics()["nodes"] == 1
    e.advance_to(1_000_000)
    assert e.metrics()["nodes"] == 0


def test_reconnection_starts_a_new_isolated_wait(factory):
    e = controlled(
        factory,
        weight=0.001,
        retain_nodes=False,
        node_retention_mode="manual",
        prune_support=0,
        dead_node_retention_us=500_000,
        activation_tau=0.001,
    )
    e.advance_to(200_000)
    e.inject(Stimulus(400_000, ((1, 0.5), (2, 0.5))))
    e.advance_to(700_000)
    assert e.metrics()["nodes"] == 2 and e.metrics()["edges"] == 2
    keys = [(x["source"], x["target"]) for x in e.graph()["edges"]]
    e.intervene(edges=keys, action="disconnect_edges")
    e = factory(state=e.capture_state())
    e.advance_to(1_100_000)
    assert e.metrics()["nodes"] == 2
    e.advance_to(1_300_000)
    assert e.metrics()["nodes"] == 0


def test_dormancy_interlock_and_no_hidden_contacts(factory):
    off = controlled(factory, weight=0.001)
    off.advance_to(100_000)
    assert not off.capture_state().to_dict()["operator_state"]["retention"]["dormant"]
    on = controlled(
        factory,
        weight=0.001,
        dormant_traces_enabled=True,
        revival_enabled=True,
        node_wake_threshold=0.2,
        edge_wake_threshold=0.2,
    )
    on.advance_to(100_000)
    s = on.capture_state()
    assert len(s.to_dict()["operator_state"]["retention"]["dormant"]) == 2
    on.reconfigure(replace(on.config, dormant_traces_enabled=False))
    assert not on.config.revival_enabled
    assert not on.capture_state().to_dict()["operator_state"]["retention"]["dormant"]
    on.reconfigure(replace(on.config, dormant_traces_enabled=True))
    assert not on.config.revival_enabled
    assert factory(state=s).capture_state().digest == s.digest


def test_wake_is_local_sum_and_never_assigns_weight(factory):
    results = []
    for both in (False, True):
        e = controlled(
            factory,
            weight=0.0079,
            half_life=1000.0,
            dormant_traces_enabled=True,
            revival_enabled=True,
            node_wake_threshold=0.1,
            edge_wake_threshold=0.7,
            activation_decay_enabled=False,
            propagation_rate=10.0,
        )
        e.advance_to(100_000)
        e.inject(Stimulus(100_000, ((1, 0.5), (2, 0.5)) if both else ((1, 0.5),)))
        e.advance_to(200_000)
        results.append(e)
    assert results[0].metrics()["edges"] == 0
    assert results[1].metrics()["edges"] == 2
    assert all(edge["weight"] < 0.0079 for edge in results[1].graph()["edges"])
    assert results[1].metrics()["retention"]["nodes_awakened"] == 2
    assert factory(state=results[1].capture_state()).capture_state().digest == results[1].capture_state().digest


def test_awakened_contact_can_really_transmit_and_still_fade(factory):
    e = controlled(
        factory,
        weight=0.0079,
        half_life=30.0,
        dormant_traces_enabled=True,
        revival_enabled=True,
        node_wake_threshold=0.001,
        edge_wake_threshold=0.1,
        propagation_rate=100.0,
        activation_decay_enabled=False,
    )
    e.advance_to(100_000)
    e.inject(Stimulus(100_000, ((1, 1.0),)))
    e.advance_to(400_000)
    assert e.metrics()["transport"]["sent"] > 0
    assert e.metrics()["retention"]["nodes_awakened"] == 2
    assert any(v > 0 for _, v in e.activations())
    # Stop transmission as an explicit fixture intervention. Actual transmission
    # may already have strengthened the edge, so allow normal forgetting time.
    e.reconfigure(replace(e.config, propagation_rate=0.0, activation_decay_enabled=True))
    e.advance_to(300_000_000)
    assert e.metrics()["edges"] == 0
    assert e.metrics()["retention"]["dormant"] == 2


def test_interventions_delete_only_local_state_and_restore(factory):
    e = factory(
        RetentionConfig(
            dormant_traces_enabled=True, revival_enabled=True, node_wake_threshold=0.2, edge_wake_threshold=0.2
        )
    )
    e.inject(Stimulus(0, ((1, 1.0), (2, 1.0), (3, 1.0))))
    e.advance_to(70_771)
    e.intervene(nodes=[2], action="delete_nodes")
    s = e.capture_state()
    assert factory(state=s).capture_state().digest == s.digest
    assert all(2 not in row[:2] for row in s.to_dict()["operator_state"]["retention"]["edges"])
    e.advance_to(200_000)
    assert all(row["id"] != 2 for row in e.graph()["nodes"])


def test_strong_fatigue_is_local_projected_and_configurable(factory):
    e = factory(RetentionConfig(max_edges=0))
    e.inject(Stimulus(0, ((1, 1.0),), 4.0))
    e.advance_to(0)
    s = e.capture_state()
    fatigue = s.to_dict()["operator_state"]["retention"]["fatigue"]
    assert fatigue[0][1] > 0
    e.advance_to(2_000_000)
    assert e.capture_state().to_dict()["operator_state"]["retention"]["fatigue"] == fatigue
    e.reconfigure(replace(e.config, strong_fatigue_enabled=False))
    assert not e.capture_state().to_dict()["operator_state"]["retention"]["fatigue"]


def test_freeze_no_dose_debt_and_formula_immutable(factory):
    e = factory(RetentionConfig(plasticity=False, max_edges=0))
    e.inject(Stimulus(0, ((1, 1.0),)))
    e.advance_to(500_000)
    row = e.capture_state().to_dict()["operator_state"]["retention"]["nodes"][0]
    assert row[1] == 30
    e.reconfigure(replace(e.config, plasticity=True))
    e.advance_to(600_000)
    assert e.capture_state().to_dict()["operator_state"]["retention"]["nodes"][0][1] == 30
    with pytest.raises(ValueError, match="immutable"):
        e.reconfigure(replace(e.config, memory_growth_formula="linear-saturating"))


def test_configuration_rejects_quotas_missing_thresholds_and_old_state(factory):
    for key in ("propagation_limit", "edge_adaptation_limit"):
        with pytest.raises(ValueError, match="quotas"):
            RetentionConfig(**{key: 1})
    with pytest.raises(ValueError, match="explicit positive"):
        RetentionConfig(dormant_traces_enabled=True, revival_enabled=True)
    e = factory()
    s = e.capture_state().to_dict()
    s["schema"] = "threemind.continuous-memory-state/3"
    with pytest.raises(ValueError):
        factory(state=StateImage.from_dict(s))


def test_local_timer_updates_do_not_accumulate_stale_entries():
    from threemind_kernels.local_deadlines import LocalDeadlines

    q = LocalDeadlines()
    for i in range(1000):
        q.set((0, 1, 0), i)
    assert len(q.heap) == 1
    for i in range(2, 100):
        q.set((0, i, 0), 100 - i)
    for i in range(2, 100, 3):
        q.discard((0, i, 0))
    assert list(q.due(2000)) == [k for _, k in sorted([(100 - i, (0, i, 0)) for i in range(2, 100) if (i - 2) % 3])] + [
        (0, 1, 0)
    ]


def test_corrupt_or_missing_expiry_is_rejected(factory):
    e = controlled(factory)
    for change in ("omit", "late"):
        s = e.capture_state().to_dict()
        m = s["operator_state"]["retention"]
        if change == "omit":
            m["deadlines"].pop()
        else:
            m["deadlines"][0][3] = str(int(m["deadlines"][0][3]) + 10_000_000)
        with pytest.raises(ValueError, match="expiry"):
            factory(state=StateImage.from_dict(s))


def test_optional_old_energy_damage_reschedules_local_expiry():
    p = RetentionConfig(
        energy_simulation_enabled=True,
        energy_starvation_damage_enabled=True,
        energy_initial_reserve=0.1,
        energy_maintenance_cost_per_node=0.5,
        quiescence_death_us=10**12,
    )
    a, b = RetentionEngine(p), NativeRetentionEngine(p)
    for e in (a, b):
        e.inject(Stimulus(0, ((1, 0.8), (2, 0.7))))
        e.advance_to(2_000_000)
    assert_state_close(a.capture_state().to_dict(), b.capture_state().to_dict())
    for factory, e in ((RetentionEngine, a), (NativeRetentionEngine, b)):
        assert factory(state=e.capture_state()).capture_state().digest == e.capture_state().digest


def test_configuration_catalog_exposes_repair_controls():
    from threemind_lab.configuration import catalogue

    fields = {f["path"]: f for f in catalogue()["fields"]}
    assert fields["config.memory_growth_formula"]["immutable"]
    assert fields["config.node_wake_threshold"]["default"] is None
    assert fields["config.node_wake_threshold"]["nullable"]
    assert "threemind.continuous-memory/3" not in fields["config.propagation_limit"]["kernels"]
    assert "config.revival_weight" not in fields
