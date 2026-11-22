"""Isolated backend-parity specimens, never restored scientific subjects."""

import json
from dataclasses import replace
import pytest
from threemind_core import StateImage, Stimulus
from threemind_kernels.local52 import Local52Config, Local52Engine
from threemind_kernels.local52_native import NativeLocal52Engine
from test_local53 import same, inputs


def test_registered_native_route_preserves_52_and_global_default():
    from threemind_kernels.registry import DEFAULT_KERNEL, resolve_kernel
    from threemind_lab.execution import select_execution
    from threemind_runtime.inheritance import birth

    key = "threemind.continuous-memory/5.2"
    descriptor = resolve_kernel(key)
    assert descriptor.backends == ("reference", "native")
    assert DEFAULT_KERNEL == "threemind.continuous-memory/6.1"
    assert select_execution(key, default="native") == {"backend": "native"}
    e = descriptor.create(backend="native")
    assert type(e) is NativeLocal52Engine
    image = e.capture_state()
    assert image.to_dict()["dynamics"] == key
    with pytest.raises(ValueError, match="contribution ages"):
        birth(image)
    for other in ("5.1", "5.3"):
        with pytest.raises(ValueError, match="identity"):
            resolve_kernel("threemind.continuous-memory/" + other).create(state=image, backend="native")


@pytest.mark.parametrize("curve", ("exponential", "power-law", "inverse-logarithmic"))
@pytest.mark.parametrize("relax", (False, True))
@pytest.mark.parametrize(
    "opts",
    (
        {},
        dict(reception_mode="unified", arrival_mode="coincident", propagation_phase="asynchronous"),
        dict(energy_simulation_enabled=True, energy_starvation_damage_enabled=True, energy_initial_reserve=0.1),
        dict(stp_enabled=False, fast_enabled=False, plasticity=False),
    ),
)
def test_all_state_events_cross_restore(curve, relax, opts):
    c = Local52Config(decay_curve=curve, retention_relaxation_enabled=relax, **opts)
    a, b = Local52Engine(c), NativeLocal52Engine(c)
    for s in inputs():
        a.inject(s)
        b.inject(s)
    for t in (0, 50_000, 100_000, 110_000, 411_337, 900_000, 1_000_000, 5_000_000):
        x, y = [], []
        a.advance_to(t, x.append)
        b.advance_to(t, y.append)
        same(x, y, "events")
        same(a.capture_state().to_dict(), b.capture_state().to_dict(), "state")
        same(json.loads(json.dumps(a.graph())), b.graph(), "graph")
        old = a.capture_state()
        a = Local52Engine(state=b.capture_state())
        b = NativeLocal52Engine(state=old)
    for e in (a, b):
        e.reconfigure(replace(c, retention_relaxation_enabled=not relax))
    a.advance_to(5_100_000)
    b.advance_to(5_100_000)
    same(a.capture_state().to_dict(), b.capture_state().to_dict())


@pytest.mark.parametrize("curve", ("power-law", "inverse-logarithmic"))
def test_history_validation_and_quiet_projection(curve):
    c = Local52Config(decay_curve=curve, retention_relaxation_enabled=False)
    a = Local52Engine(c)
    for t in (0, 100_000, 1_000_000):
        a.inject(Stimulus(t, ((1, 0.4), (2, 0.3))))
    a.advance_to(2_000_000)
    state = a.capture_state()
    b = NativeLocal52Engine(state=state)
    for _ in range(3):
        b.metrics()
        b.graph()
        b.capture_state()
    same(state.to_dict(), b.capture_state().to_dict())
    for e in (a, b):
        e.advance_to(300_000_000)
    same(a.capture_state().to_dict(), b.capture_state().to_dict())
    invalid = state.to_dict()
    invalid["edges"][0]["decay_contributions"][0][0] *= 0.1
    with pytest.raises(ValueError, match="history"):
        NativeLocal52Engine(state=StateImage.from_dict(invalid))
    invalid = state.to_dict()
    del invalid["edges"][0]["decay_contributions"]
    with pytest.raises(ValueError):
        NativeLocal52Engine(state=StateImage.from_dict(invalid))


def test_scalar_exponential_manual_legacy_mode():
    c = Local52Config(consolidation_mode="legacy-stability", node_retention_mode="manual")
    a, b = Local52Engine(c), NativeLocal52Engine(c)
    for e in (a, b):
        e.inject(Stimulus(0, ((1, 0.8), (2, 0.3))))
        e.advance_to(2_000_000)
    same(a.capture_state().to_dict(), b.capture_state().to_dict())


def test_curve_is_immutable_and_birth_identity_stays_52():
    e = NativeLocal52Engine()
    assert e.capture_state().to_dict()["dynamics"] == "threemind.continuous-memory/5.2"
    with pytest.raises(ValueError):
        e.reconfigure(replace(e.config, decay_curve="power-law"))


@pytest.mark.parametrize("curve", ("exponential", "power-law", "inverse-logarithmic"))
@pytest.mark.parametrize("mode", ("delete", "dormant", "damage"))
def test_expiry_dormancy_and_starvation(curve, mode):
    opts = dict(
        memory_half_life_min_s=0.03,
        memory_learning_gain=0.0,
        retention_relaxation_enabled=False,
        quiescence_death_us=10**12,
    )
    if mode == "dormant":
        opts.update(
            dormant_traces_enabled=True, revival_enabled=True, node_wake_threshold=0.001, edge_wake_threshold=0.001
        )
    if mode == "damage":
        opts.update(energy_simulation_enabled=True, energy_starvation_damage_enabled=True, energy_initial_reserve=0.001)
    c = Local52Config(decay_curve=curve, **opts)
    a, b = Local52Engine(c), NativeLocal52Engine(c)
    for e in (a, b):
        e.inject(Stimulus(0, ((10, 0.5), (20, 0.4))))
        e.inject(Stimulus(1_011_337, ((10, 0.6), (20, 0.5))))
    for t in (0, 100_000, 1_000_000, 1_011_337, 2_000_000, 30_000_000):
        left, right = [], []
        a.advance_to(t, left.append)
        b.advance_to(t, right.append)
        same(left, right)
        same(a.capture_state().to_dict(), b.capture_state().to_dict())
        state = a.capture_state()
        a = Local52Engine(state=b.capture_state())
        b = NativeLocal52Engine(state=state)


@pytest.mark.parametrize("curve", ("power-law", "inverse-logarithmic"))
def test_observation_partition_and_deadline_tampering(curve):
    c = Local52Config(decay_curve=curve, quiescence_death_us=10**12)
    a, b = NativeLocal52Engine(c), NativeLocal52Engine(c)
    for e in (a, b):
        for s in inputs():
            e.inject(s)
    a.advance_to(2_000_000)
    for t in (0, 11_111, 100_000, 101_010, 411_337, 500_000, 711_111, 1_000_000, 2_000_000):
        b.advance_to(t)
        old = b.capture_state().payload
        b.graph()
        b.metrics()
        b.activations()
        assert b.capture_state().payload == old
    same(a.capture_state().to_dict(), b.capture_state().to_dict())
    invalid = a.capture_state().to_dict()
    timer = next(x for x in invalid["timers"] if x[0] == 2)
    timer[3] = str(int(timer[3]) + 1_000_000)
    with pytest.raises(ValueError, match="expiry time"):
        NativeLocal52Engine(state=StateImage.from_dict(invalid))
