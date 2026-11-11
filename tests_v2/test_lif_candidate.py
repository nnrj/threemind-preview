import random
from dataclasses import replace
from itertools import pairwise

import pytest
from test_causal9_baseline import assert_state_close

from threemind_core import StateImage, Stimulus
from threemind_kernels.lif import LifConfig, LifEngine
from threemind_kernels.lif_native import NativeLifEngine
from threemind_kernels.mechanisms import membrane_response


def pulse(engine, when=0, amount=0.8):
    engine.inject(Stimulus(when, ((1, amount), (2, amount * 0.9))))


def test_subthreshold_current_is_life_without_a_spike_and_observers_are_neutral():
    c = LifConfig(inhibition=False)
    engine = LifEngine(c)
    pulse(engine, amount=0.1)
    engine.advance_to(4000)
    assert engine.life == "alive" and engine.metrics()["spikes"] == 0
    actual = engine.physical_nodes()[0]
    expected = membrane_response(c.rest_mv, 0.1, 0.004)
    assert actual["voltage_mv"] == pytest.approx(expected[0])
    assert actual["current_na"] == pytest.approx(expected[1])
    before = engine.capture_state().digest
    engine.metrics()
    engine.graph()
    engine.physical_nodes()
    assert engine.capture_state().digest == before


def test_spiking_refractory_and_independent_decay_clocks():
    engine = LifEngine(LifConfig(input_gain_na=10.0))
    pulse(engine)
    records = []
    engine.advance_to(50_000, records.append)
    spikes = [e for e in records if e["kind"] == "spikes"]
    assert len(spikes) >= 2
    times = [int(e["time_us"]) for e in spikes if 1 in e["payload"]["nodes"]]
    assert all(b - a >= engine.config.refractory_us for a, b in pairwise(times))
    assert engine.nodes[1].adaptation_na > 0
    assert engine.life == "alive"


def test_partition_and_inflight_restore_are_exact():
    a = LifEngine(LifConfig(input_gain_na=5.0))
    pulse(a)
    pulse(a, 19_713)
    a.advance_to(3_003)
    b = LifEngine(state=a.capture_state())
    for time in (3_127, 8_701, 20_006, 70_001):
        b.advance_to(time)
    a.advance_to(70_001)
    assert a.capture_state().digest == b.capture_state().digest
    assert a.metrics()["transport"]["sent_na"] > 0


def test_sending_never_reads_receiver_and_arrival_retains_edge_generation():
    a = LifEngine(LifConfig(input_gain_na=5.0, stp_enabled=False))
    pulse(a)
    a.advance_to(0)
    a.nodes[1].voltage_mv = a.config.threshold_mv
    a.nodes[2].current_na = 0.0
    a.nodes[2].voltage_mv = a.config.rest_mv
    # Inspect the actual local spike emission, independent of receptive saturation.
    a._spikes()
    pending = a.capture_state().to_dict()["queue"]
    packet = next(e for e in pending if e["kind"] == "spike_arrival")
    old_id = a.edges[1, 2].id
    a.intervene(edges=[(1, 2)], action="disconnect_edges")
    pulse(a, 1)
    a.advance_to(1)
    assert a.edges[1, 2].id != old_id
    a.advance_to(int(packet["time_us"]))
    assert a.edges[1, 2].pre == 0  # Old traffic doesn't train the replacement edge.
    assert a.transport["received_na"] >= packet["payload"]["messages"][0][3]


def test_death_waits_for_physical_quiescence_and_dead_inputs_do_not_revive():
    e = LifEngine(LifConfig(spike_gain_na=0.0))
    e.advance_to(10_000_000)
    assert e.life == "waiting"
    pulse(e, e.time_us, amount=0.1)
    e.advance_to(10_010_000)
    assert e.life == "alive"
    e.advance_to(12_000_000)
    assert e.life == "dead" and e.time_us < 12_000_000
    with pytest.raises(ValueError):
        pulse(e, e.time_us)
    assert e.nodes and e.edges


def test_parameter_edits_after_idle_and_during_activity_restore_exactly():
    e = LifEngine()
    e.advance_to(33_791)
    e.reconfigure(replace(e.config, input_gain_na=2.0))
    e = LifEngine(state=e.capture_state())
    pulse(e, e.time_us)
    e.advance_to(38_901)
    e.reconfigure(replace(e.config, stdp_tau_pre_s=0.03, current_tau_s=0.006))
    twin = LifEngine(state=e.capture_state())
    for item in (e, twin):
        item.advance_to(80_000)
    assert e.capture_state().digest == twin.capture_state().digest
    original = e.capture_state().digest
    with pytest.raises(ValueError, match="immutable"):
        e.reconfigure(replace(e.config, threshold_mv=-49.0))
    assert e.capture_state().digest == original


@pytest.mark.parametrize("field", ["definition_hash", "nodes", "active", "membranes"])
def test_corrupted_recovery_is_rejected(field):
    e = LifEngine()
    pulse(e)
    e.advance_to(1000)
    value = e.capture_state().to_dict()
    if field == "definition_hash":
        value[field] = "x"
    elif field == "membranes":
        value[field][0]["current_na"] = -1
    else:
        value[field] = []
    with pytest.raises(ValueError):
        LifEngine(state=StateImage.from_dict(value))


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"stp_enabled": False},
        {"stdp_enabled": False},
        {"plasticity": False},
        {"inhibition": False},
        {"leak_enabled": False},
        {"current_decay_enabled": False},
        {"delay_us": 1371, "step_us": 137, "refractory_us": 0},
        {"stp_utilization": 0.04, "stp_facilitation_tau_s": 1.0},
        {"max_nodes": 3, "max_edges": 4},
    ],
)
def test_native_reference_parity_including_cross_recovery_and_observation(changes):
    c = LifConfig(**({"input_gain_na": 5.0} | changes))
    a, b = LifEngine(c), NativeLifEngine(c)
    rng = random.Random(2917)
    for when in sorted(rng.randrange(80_000) for _ in range(25)):
        s = Stimulus(when, tuple((ch, rng.uniform(0.1, 0.9)) for ch in rng.sample(range(7), 3)))
        a.inject(s)
        b.inject(s)
    for when in (1003, 9317, 23101, 59997, 100009):
        left, right = [], []
        a.advance_to(when, left.append)
        b.advance_to(when, right.append)
        assert_state_close(right, left)
        a_state, b_state = a.capture_state(), b.capture_state()
        assert_state_close(b_state.to_dict(), a_state.to_dict())
        assert_state_close(b.graph(), a.graph())
        assert_state_close(b.metrics(), a.metrics())
        assert_state_close(b.physical_nodes(), a.physical_nodes())
        a, b = LifEngine(state=b_state), NativeLifEngine(state=a_state)
        assert a.capture_state().digest == b_state.digest
        assert b.capture_state().digest == a_state.digest
    changed = replace(c, stdp_tau_post_s=0.025, input_gain_na=3.0)
    for e in (a, b):
        e.reconfigure(changed)
        e.advance_to(150000)
    assert_state_close(b.capture_state().to_dict(), a.capture_state().to_dict())


@pytest.mark.parametrize("factory", [LifEngine, NativeLifEngine])
def test_grid_controls_spike_quantization_and_converges_to_rc_threshold(factory):
    lo, hi = 0.0, 0.001
    for _ in range(50):
        mid = (lo + hi) / 2
        if membrane_response(-65, 8, mid)[0] < -50:
            lo = mid
        else:
            hi = mid
    crossing = hi * 1e6
    for step in (250, 100, 25, 10):
        e = factory(LifConfig(step_us=step, input_gain_na=10, inhibition=False))
        e.inject(Stimulus(0, ((1, 0.8),)))
        events = []
        e.advance_to(1000, events.append)
        first = int(next(row for row in events if row["kind"] == "spikes")["time_us"])
        assert crossing <= first < crossing + step


def test_arrival_order_has_local_stdp_effect_without_external_target_labels():
    e = LifEngine(LifConfig(stp_enabled=False))
    pulse(e, amount=0.01)
    e.advance_to(0)
    edge = e.edges[1, 2]
    initial = edge.weight
    # A presynaptic arrival leaves a local trace; a later target spike potentiates it.
    e._arrival({"messages": [[1, 2, edge.id, 0.01]]})
    e._relax(1000)
    e.nodes[2].voltage_mv = e.config.threshold_mv
    e._spikes()
    assert edge.weight > initial
    before = edge.weight
    e._relax(2000)
    e._arrival({"messages": [[1, 2, edge.id, 0.01]]})
    assert edge.weight < before


@pytest.mark.parametrize("factory", [LifEngine, NativeLifEngine])
def test_silence_delete_and_deadline_arrival_preserve_identity_and_life(factory):
    e = factory(LifConfig(input_gain_na=5.0, quiescence_death_us=1000))
    pulse(e)
    e.advance_to(2000)
    e.intervene(nodes=[1, 2], action="silence")
    e.intervene(nodes=[1, 2], action="unsilence")
    e.inject(Stimulus(3000, ((1, 0.7),)))
    e.advance_to(3000)
    assert e.life == "alive"
    e.intervene(nodes=[1], action="delete_nodes")
    e.inject(Stimulus(3001, ((1, 0.8),)))
    e.advance_to(3001)
    identity = next(n["id"] for n in e.graph()["nodes"] if n["channel"] == 1)
    assert identity > 2
    clone = factory(state=e.capture_state())
    clone.advance_to(10000)
    assert clone.life == "alive"
