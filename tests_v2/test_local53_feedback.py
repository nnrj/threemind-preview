"""Bounded recurrent and weak-signal engineering fixtures for /5.3."""

import math

import pytest
from threemind_core import Stimulus
from threemind_kernels.decay53 import decay_value
from threemind_kernels.local53 import KERNEL_ID, Local53Config
from threemind_kernels.registry import resolve_kernel
from test_local53 import make, same, transport_specimen


@pytest.mark.parametrize("energy", (False, True))
def test_recurrent_excitation_and_inhibition_remain_bounded_and_match(energy):
    c = Local53Config(
        energy_simulation_enabled=energy,
        energy_model="global-ledger",
        energy_initial_reserve=1.0,
        signal_threshold=0.0,
        quiescence_death_us=10**12,
    )
    a, b = make(c), make(c, "native")
    for e in (a, b):
        # Six jointly stimulated nodes form 30 actual directed connections.
        for t in (0, 100_000, 200_000):
            e.inject(Stimulus(t, tuple((i, 0.9) for i in range(6))))
    for t in (0, 100_000, 500_000, 1_000_000, 2_000_000):
        x, y = [], []
        a.advance_to(t, x.append)
        b.advance_to(t, y.append)
        same(x, y)
        doc = a.capture_state().to_dict()
        same(doc, b.capture_state().to_dict())
        for n in doc["nodes"]:
            assert 0 <= n["activation"] <= 1 and math.isfinite(n["inhibition"])
        assert len(doc["queue"]) < 1000
        assert all(0 <= edge["weight"] <= 1 for edge in doc["edges"])
    assert doc["transport"]["offered_inhibition"] > 0
    assert doc["transport"]["transmitted_excitation"] > 0


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_disabling_joint_cutoff_transmits_positive_weak_signals(backend):
    a = transport_specimen(signal_threshold=0.0, activation_floor=0.0)
    a.nodes[0].activation = 1e-8
    a.edges[0, 1].weight = 0.8
    a = resolve_kernel(KERNEL_ID).create(state=a.capture_state(), backend=backend)
    a.advance_to(100_000)
    rows = [m for q in a.capture_state().to_dict()["queue"] if q["kind"] == "signal" for m in q["payload"]["messages"]]
    assert rows and 0 < rows[0][2] < 0.0004


@pytest.mark.parametrize("curve", ("power-law", "inverse-logarithmic"))
def test_old_connection_keeps_age_after_weak_reinforcement(curve):
    c = Local53Config(decay_curve=curve)
    a = make(c)
    fresh = a.edge_type(0, 1, 0.019, decay_age=0)
    old = a.edge_type(0, 1, 0.019, decay_age=100)
    for e in (fresh, old):
        e.weight += 0.001
    assert fresh.decay_age == 0 and old.decay_age == 100
    vf, af, _ = decay_value(fresh.weight, fresh.decay_age, 30.0, 30.0, c)
    vo, ao, _ = decay_value(old.weight, old.decay_age, 30.0, 30.0, c)
    assert af == 1 and ao == 101
    assert vo > vf
