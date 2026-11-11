"""Synthetic rule witnesses for memory/5; no formal organism is restored."""

import hashlib
import math
from dataclasses import replace

import pytest

from threemind_core import StateImage, Stimulus
from threemind_core.engine import canonical_bytes
from threemind_kernels.local import LocalConfig, LocalEngine
from threemind_kernels.local5 import KERNEL_ID, Local5Config, Local5Edge, Local5Engine
from threemind_kernels.novelty import NoveltyConfig, NoveltyEngine

# Captured from memory/4 before any memory/5 shared hooks were changed.
FROZEN4 = {
    "adaptive-half-life": (
        "f9207940af6b465e97899abd109d98bad1306f0c09c6fbeea482efab78040318",
        "3c0b424378629c7c05ce9ff4fb1a87d5e7a804c433dd42c5293228740d7ab0e8",
        "800f615a9730038e641576d134b54b60b25df79d78c378730952c38a8a4e0522",
        "44f2f811a5f23c603627d256e169c01a7b7121e0e47c5a067f74fa5864e03bf3",
    ),
    "legacy-stability": (
        "8705785d68b0476995ef5f8f24e1c3ef6b952cfdac8fa11288f9ed28f4037f2c",
        "d5021d026bd8e5da5fd4fb0ad19768c60423c92136a4875ca38cffabe9bd97e5",
        "d164d09bc27d67f3a88d040f4dd789e12a347f4c06197a86a17a2f968cc7f345",
        "f8058ba90c770d3eef3776a6bfdc7d3ef39d53cba94121a1526ab52077baec94",
    ),
}


def feed(engine):
    for i, t in enumerate((0, 73000, 180000, 610000, 1200000)):
        engine.inject(Stimulus(t, ((10, 0.8), (11, 0.6), (20 + i % 2, 0.4))))


@pytest.mark.parametrize("mode", FROZEN4)
def test_memory4_frozen_states_remain_byte_identical(mode):
    e = LocalEngine(LocalConfig(consolidation_mode=mode, quiescence_death_us=10**12))
    feed(e)
    for when, expected in zip((0, 180000, 611337, 2000000), FROZEN4[mode]):
        e.advance_to(when)
        assert hashlib.sha256(canonical_bytes(e.capture_state().to_dict())).hexdigest() == expected


def test_memory5_identity_defaults_and_wrong_identity_restore():
    c = Local5Config()
    assert (c.reception_mode, c.arrival_mode, c.propagation_phase) == ("legacy-source", "sequential", "aligned")
    e = Local5Engine(c)
    assert e.dynamics == e.metrics()["kernel_id"] == e.graph()["kernel_id"] == KERNEL_ID
    with pytest.raises(ValueError):
        Local5Engine(state=LocalEngine().capture_state())
    with pytest.raises(ValueError):
        LocalEngine(state=e.capture_state())


@pytest.mark.parametrize("mode", ["legacy-source", "unified"])
@pytest.mark.parametrize("arrival", ["sequential", "coincident"])
def test_internal_fanout_never_invents_recipient_contacts(mode, arrival):
    e = Local5Engine(Local5Config(reception_mode=mode, arrival_mode=arrival, context_enabled=False))
    for channel in (1, 2):
        e._birth(channel)
    e._receive([(0, [[50, 0, 0.2, [0.0] * 4], [50, 1, 0.2, [0.0] * 4]], False, 1.0)])
    assert all(n.activation > 0 for n in e.nodes.values())
    assert e.edges == {}


@pytest.mark.parametrize("arrival", ["sequential", "coincident"])
def test_distinct_external_packets_do_not_become_one_observation(arrival):
    e = Local5Engine(Local5Config(arrival_mode=arrival))
    e.inject(Stimulus(0, ((1, 0.8),)))
    e.inject(Stimulus(0, ((2, 0.8),)))
    e.advance_to(0)
    assert len(e.nodes) == 2 and not e.edges


def edge_values(engine):
    state = engine.capture_state().to_dict()
    channels = {n["id"]: n["channel"] for n in state["nodes"]}
    return {
        (channels[r["source"]], channels[r["target"]]): (r["weight"], r["eligibility"], r["stability"], r["touches"])
        for r in state["edges"]
    }


def test_external_repeated_learning_matches_memory2_at_the_same_time():
    options = {"inhibition": False, "context_enabled": False, "quiescence_death_us": 10**12}
    old = NoveltyEngine(NoveltyConfig(**options))
    new = Local5Engine(Local5Config(**options, node_retention_mode="manual", strong_fatigue_enabled=False))
    for channels in (((1, 0.8), (2, 0.6)), ((1, 0.05), (2, 0.05)), ((1, 0.2), (3, 0.1))):
        for e in (old, new):
            e.inject(Stimulus(0, channels))
            e.advance_to(0)
        assert edge_values(new) == edge_values(old)


def test_first_packet_novelty_eligibility_is_frozen_before_any_birth():
    e = Local5Engine(Local5Config())
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.8), (3, 0.8))))
    e.advance_to(0)
    assert len(e.edges) == 6
    assert all(edge.novelty_deadline_us is None for edge in e.edges.values())
    assert not e.pending_novelty


def test_novelty_uses_next_aligned_pulse_and_existing_associative_history():
    e = Local5Engine(Local5Config(propagation_rate=0.0))
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.8))))
    e.advance_to(0)
    e.nodes[0].associative = 0.07
    e.inject(Stimulus(73000, ((1, 0.8), (3, 0.8))))
    e.advance_to(73000)
    assert e.edges[0, 2].novelty_deadline_us == "110000"
    assert e.edges[0, 2].novelty_source == 0.07
    assert e.edges[2, 0].novelty_target == 0.07


def test_zero_energy_acceptance_adds_no_experience_or_first_touch():
    c = Local5Config(energy_simulation_enabled=True, energy_initial_reserve=0.0)
    e = Local5Engine(c)
    e.inject(Stimulus(0, ((1, 1.0), (2, 1.0))))
    e.advance_to(0)
    assert all(n.touches == 0 and n.stability == 0 and n.support == 0 for n in e.nodes.values())
    assert not e.edges
    assert all((3, n.id, 0) in e.timers.positions for n in e.nodes.values())


def test_partial_energy_scales_external_impulse_and_input_is_clipped():
    common = {
        "energy_simulation_enabled": True,
        "energy_initial_reserve": 0.04,
        "inhibition": False,
        "context_enabled": False,
    }
    # A shared ledger gives both kernels the same sequential energy allocation.
    old = NoveltyEngine(NoveltyConfig(**common))
    new = Local5Engine(Local5Config(**common, energy_model="global-ledger", node_retention_mode="manual"))
    for e in (old, new):
        e.inject(Stimulus(0, ((1, 1.0), (2, 1.0)), intensity=2.0))
        e.advance_to(0)
    assert len(new.edges) == 2
    assert edge_values(old) == edge_values(new)
    assert [n["activation"] for n in new.observation_nodes()] == pytest.approx(
        [n["activation"] for n in old.observation_nodes()]
    )


def test_lazily_projected_eligibility_and_stability_follow_old_discrete_recurrence():
    c = Local5Config()
    e = Local5Engine(c)
    original = Local5Edge(0, 1, 0.8, eligibility=0.63, stability=0.57, half_life=30.0)
    eligibility, stability = original.eligibility, original.stability
    interval = c.propagation_interval_us / 1e6
    for _ in range(73):
        eligibility *= math.exp(-interval / c.eligibility_tau)
        stability = max(0.0, stability - interval / c.stability_tau * (1 - eligibility))
    projected = e._project_edge(original, 73 * c.propagation_interval_us)
    assert projected.eligibility == pytest.approx(eligibility, abs=1e-14)
    assert projected.stability == pytest.approx(stability, abs=1e-14)
    assert original.completed_period_us == "0"


@pytest.mark.parametrize("mode", ["adaptive-half-life", "legacy-stability"])
@pytest.mark.parametrize("phase", ["aligned", "asynchronous"])
def test_observation_batching_and_complete_restore_do_not_change_time_or_state(mode, phase):
    c = Local5Config(consolidation_mode=mode, propagation_phase=phase, quiescence_death_us=10**12)
    e, one = Local5Engine(c), Local5Engine(c)
    feed(e)
    feed(one)
    for when in (180000, 611337, 1200000, 2000000):
        e.advance_to(when)
        before = e.capture_state().payload
        e.graph()
        e.metrics()
        e.activations()
        assert e.time_us == when and e.capture_state().payload == before
        e = Local5Engine(state=e.capture_state())
    one.advance_to(2000000)
    assert one.capture_state().to_dict() == e.capture_state().to_dict()


def test_new_clock_fields_cannot_silently_default_during_restore():
    e = Local5Engine()
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.8))))
    e.advance_to(0)
    for owner, field in (("nodes", "last_emit_us"), ("edges", "completed_period_us")):
        doc = e.capture_state().to_dict()
        del doc[owner][0][field]
        with pytest.raises(ValueError, match="missing memory/5"):
            Local5Engine(state=StateImage.from_dict(doc))


def test_same_time_subfloor_stimuli_accumulate_as_memory2():
    common = {"inhibition": False, "context_enabled": False, "activation_floor": 0.004}
    old = NoveltyEngine(NoveltyConfig(**common))
    new = Local5Engine(Local5Config(**common))
    for e in (old, new):
        for _ in range(3):
            e.inject(Stimulus(0, ((1, 0.002),)))
        e.advance_to(0)
    expected = old.observation_nodes()[0]["activation"]
    assert expected > common["activation_floor"]
    assert new.observation_nodes()[0]["activation"] == expected


def test_legacy_edge_born_on_aligned_boundary_gets_that_period_update():
    common = {"inhibition": False, "context_enabled": False, "propagation_rate": 0.0}
    old = NoveltyEngine(NoveltyConfig(**common))
    new = Local5Engine(Local5Config(**common, consolidation_mode="legacy-stability"))
    for e in (old, new):
        e.inject(Stimulus(100000, ((1, 0.8), (2, 0.7))))
        e.advance_to(100000)
    for key, row in edge_values(old).items():
        assert edge_values(new)[key] == pytest.approx(row, abs=1e-14)
    assert {e.completed_period_us for e in new.edges.values()} == {"100000"}


def inhibition_by_channel(engine):
    state = engine.capture_state().to_dict()
    channels = {n["id"]: n["channel"] for n in state["nodes"]}
    packets = [q for q in state["queue"] if q["kind"] == "inhibition"]
    assert len(packets) == 1
    return {channels[node]: value for node, value in packets[0]["payload"]["values"]}


def test_same_round_inhibition_is_saturated_once_before_delivery_as_memory2():
    common = {"context_enabled": False}
    old = NoveltyEngine(NoveltyConfig(**common))
    new = Local5Engine(Local5Config(**common, consolidation_mode="legacy-stability"))
    for e in (old, new):
        e.inject(Stimulus(0, ((1, 0.9), (2, 0.8), (3, 0.7))))
        e.advance_to(100000)
    assert inhibition_by_channel(new) == pytest.approx(inhibition_by_channel(old), abs=1e-14)


def test_disabled_novelty_creates_no_window_or_timer():
    e = Local5Engine(Local5Config(local_novelty_gain=0.0, propagation_rate=0.0))
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.8))))
    e.inject(Stimulus(70000, ((1, 0.8), (3, 0.8))))
    e.advance_to(70000)
    assert len(e.edges) == 4
    assert not e.pending_novelty
    assert all(edge.novelty_deadline_us is None for edge in e.edges.values())
    assert all(key[0] != 4 for key in e.timers.positions)


@pytest.mark.parametrize("reception", ["legacy-source", "unified"])
def test_external_touch_never_counts_as_novelty_reentry(reception):
    e = Local5Engine(Local5Config(reception_mode=reception, context_enabled=False, propagation_rate=0.0))
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.8))))
    e.inject(Stimulus(70000, ((1, 0.8), (3, 0.8))))
    e.advance_to(70000)
    assert e.pending_novelty
    e.inject(Stimulus(80000, ((1, 0.8),)))
    e.advance_to(80000)
    assert all(edge.novelty_source == edge.novelty_target == 0 for edge in e.edges.values())


def test_input_added_after_completed_same_time_pulse_uses_completed_phase():
    common = {
        "inhibition": False,
        "context_enabled": False,
        "stp_enabled": False,
        "fast_enabled": False,
        "propagation_rate": 10.0,
        "forgetting_rate": 0.0,
        "eligibility_decay_enabled": False,
        "stability_decay_enabled": False,
    }
    old = NoveltyEngine(NoveltyConfig(**common))
    new = Local5Engine(Local5Config(**common, consolidation_mode="legacy-stability", node_retention_mode="manual"))
    for e in (old, new):
        e.inject(Stimulus(0, ((1, 1.0), (2, 1.0))))
        e.advance_to(100000)
    new = Local5Engine(state=new.capture_state())
    for e in (old, new):
        e.inject(Stimulus(100000, ((1, 0.1), (2, 0.1))))
        e.advance_to(100000)
        e.inject(Stimulus(100000, ((1, 0.1), (3, 0.1))))
        e.advance_to(100000)
    for key, row in edge_values(old).items():
        assert edge_values(new)[key] == pytest.approx(row, abs=1e-14)
    assert new.edges[0, 2].novelty_deadline_us == "210000"
    assert new.edges[0, 2].completed_period_us == "100000"
    assert new.nodes[2].last_emit_us == "0"


def test_disabling_learning_does_not_defer_eligibility_and_stability_decay():
    e = Local5Engine(Local5Config(propagation_rate=0.0, inhibition=False, quiescence_death_us=10**12))
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.7))))
    e.advance_to(100000)
    e.reconfigure(replace(e.config, plasticity=False))
    before = [(x.eligibility, x.stability, x.weight) for x in e.edges.values()]
    e.advance_to(3000000)
    e.reconfigure(replace(e.config, plasticity=True))
    after = [(x.eligibility, x.stability, x.weight) for x in e.edges.values()]
    assert before == after
    assert all(x.completed_period_us == "3000000" for x in e.edges.values())
    e.advance_to(3100000)
    for edge, (eligibility, stability, _) in zip(e.edges.values(), before):
        projected = e._project_edge(edge, e.time_us)
        expected = eligibility * math.exp(-0.1 / e.config.eligibility_tau)
        assert projected.eligibility == pytest.approx(expected)
        assert projected.stability == pytest.approx(max(0.0, stability - 0.1 / e.config.stability_tau * (1 - expected)))


def test_completed_novelty_index_does_not_retain_historical_node_ids():
    e = Local5Engine(Local5Config(propagation_rate=0.0, retain_nodes=True))
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.8))))
    e.inject(Stimulus(70000, ((1, 0.8), (3, 0.8))))
    e.advance_to(110000)
    assert not e.pending_novelty
    for id in tuple(e.nodes):
        e._delete_node(id)
    assert not e.pending_novelty
