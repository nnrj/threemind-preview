"""6.1 engineering witnesses; all subjects are isolated test instances."""

import copy
import json
from dataclasses import replace

import pytest
from test_local60 import OPTIONS as OLD_OPTIONS
from test_local60 import inject_course, same

from threemind_core import StateImage, Stimulus
from threemind_kernels.decay61 import crossing_seconds, decay_value
from threemind_kernels.local60 import Local60Config
from threemind_kernels.local61 import KERNEL_ID, Local61Config
from threemind_kernels.registry import resolve_kernel
from threemind_runtime import ArtifactCodec
from threemind_runtime.inheritance import birth

OPTIONS = OLD_OPTIONS + [
    {"stp_facilitation_tau_s": 0.1},
    {"inflight_delivery": "same-birth"},
    {"dormant_traces_enabled": True, "revival_enabled": True, "node_wake_threshold": 0.01, "edge_wake_threshold": 0.01},
]


def make(config=None, backend="reference", state=None):
    return resolve_kernel(KERNEL_ID).create(config, state, backend=backend)


def state(doc):
    return StateImage(json.dumps(doc).encode())


@pytest.mark.parametrize("curve", ("exponential", "power-law", "inverse-logarithmic", "power-exponential"))
@pytest.mark.parametrize("relax", (False, True))
@pytest.mark.parametrize("age", (0.0, 5.0, 25.0))
def test_analytic_crossing(curve, relax, age):
    c = Local61Config(decay_curve=curve, retention_relaxation_enabled=relax)
    t = crossing_seconds(0.05, age, 90, 0.008, c)
    actual, _, _ = decay_value(0.05, age, 90, t, c)
    if t == 1e12:
        assert actual > 0.008  # Deliberately bounded local recheck of a distant tail.
        return
    assert actual == pytest.approx(0.008, rel=1e-12)
    assert decay_value(0.05, age, 90, t + 0.01, c)[0] < 0.008


@pytest.mark.parametrize("strategy", ("local", "global-scan"))
@pytest.mark.parametrize("curve", ("exponential", "power-law", "inverse-logarithmic", "power-exponential"))
@pytest.mark.parametrize("options", OPTIONS)
def test_python_rust_and_restore(strategy, curve, options):
    c = Local61Config(deletion_strategy=strategy, decay_curve=curve, quiescence_death_us=10**12, **options)
    p, r = make(c), make(c, "native")
    inject_course(p)
    inject_course(r)
    for t in (0, 100000, 110000, 700000, 1800000, 10000000, 600000000):
        p.advance_to(t)
        r.advance_to(t)
        same(p.capture_state().to_dict(), r.capture_state().to_dict())
        before = p.capture_state()
        # Full state round trip and observation do not consume simulated time.
        p.activations()
        p.observation_nodes()
        assert before.payload == p.capture_state().payload
        p = make(state=before)
        r = make(backend="native", state=r.capture_state())


def compatible(doc):
    doc = copy.deepcopy(doc)
    for k in ("schema", "dynamics", "definition", "definition_hash"):
        doc.pop(k, None)
    for k in ("deletion_strategy", "activation_send_threshold", "inhibition_send_threshold"):
        doc["config"].pop(k, None)
    return doc


@pytest.mark.parametrize("backend", ("reference", "native"))
@pytest.mark.parametrize("options", OPTIONS)
def test_zero_gates_global_preserves_60(backend, options):
    c = Local60Config(quiescence_death_us=10**12, **options)
    old = resolve_kernel("threemind.continuous-memory/6.0").create(c, backend=backend)
    new = make(
        Local61Config(
            **c.to_dict(), deletion_strategy="global-scan", activation_send_threshold=0, inhibition_send_threshold=0
        ),
        backend,
    )
    inject_course(old)
    inject_course(new)
    for t in (0, 110000, 900000, 2100000, 10000000):
        old.advance_to(t)
        new.advance_to(t)
        assert compatible(old.capture_state().to_dict()) == compatible(new.capture_state().to_dict())


def quiet_pair(backend="reference", **kw):
    e = make(
        Local61Config(quiescence_death_us=10**12, propagation_rate=0, inhibition=False, local_novelty_gain=0, **kw),
        backend,
    )
    e.inject(Stimulus(0, ((1, 0.1), (2, 0.1))))
    e.advance_to(10_000_000)
    return e


@pytest.mark.parametrize("backend", ("reference", "native"))
@pytest.mark.parametrize("curve", ("exponential", "power-law", "inverse-logarithmic", "power-exponential"))
def test_idle_edges_expire_and_do_not_scan(backend, curve):
    e = quiet_pair(backend, decay_curve=curve)
    d = e.capture_state().to_dict()
    due = min(int(row[3]) for row in d["timers"] if row[0] == 2)
    e.advance_to(due - 1)
    assert e.capture_state().to_dict()["edges"]
    e.advance_to(due)
    assert not e.capture_state().to_dict()["edges"]
    e.advance_to(10**10)
    assert not e.capture_state().to_dict()["nodes"]
    assert e.capture_state().to_dict()["audit"]["scan_visits"] == 0


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_same_time_reinforcement_replaces_deadline(backend):
    e = quiet_pair(backend)
    d = e.capture_state().to_dict()
    due = min(int(row[3]) for row in d["timers"] if row[0] == 2)
    e.inject(Stimulus(due, ((1, 0.8), (2, 0.8))))
    e.advance_to(due)
    d = e.capture_state().to_dict()
    assert len(d["edges"]) == 2
    new = [int(row[3]) for row in d["timers"] if row[0] == 2]
    assert len(new) == 2 and min(new) > due
    make(backend=backend, state=e.capture_state())


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_missing_expiry_rejected(backend):
    e = quiet_pair()
    d = e.capture_state().to_dict()
    d["timers"] = [t for t in d["timers"] if t[0] != 2]
    with pytest.raises(ValueError, match="deletion deadline"):
        make(backend=backend, state=state(d))


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_gates_stop_and_new_input_wakes(backend):
    e = make(Local61Config(quiescence_death_us=10**12), backend)
    inject_course(e)
    e.advance_to(10_000_000)
    d = e.capture_state().to_dict()
    assert not any(t[0] == 0 for t in d["timers"])
    e.inject(Stimulus(10_000_001, ((0, 0.8),)))
    e.advance_to(10_000_001)
    assert any(t[0] == 0 for t in e.capture_state().to_dict()["timers"])


def test_source_gates_are_independent_and_zero_disables():
    e = make()
    n = e.nodes[e._birth(1)]
    n.activation, n.inhibition = 0.003, 0.001
    assert not e._can_emit(n)
    n.activation = 0.004
    assert e._can_emit(n)
    n.activation, n.inhibition = 0, 0.002
    assert e._can_emit(n)
    e.config = replace(e.config, inhibition_send_threshold=0)
    n.inhibition = 1e-50
    assert e._can_emit(n)
    n.inhibition = 0
    assert not e._can_emit(n)


@pytest.mark.parametrize("backend", ("reference", "native"))
@pytest.mark.parametrize("strategy", ("local", "global-scan"))
def test_birth_codec_and_partition(backend, strategy):
    e = make(Local61Config(deletion_strategy=strategy, quiescence_death_us=10**12), backend)
    inject_course(e)
    e.advance_to(1500000)
    start = e.capture_state()
    assert ArtifactCodec.decode(ArtifactCodec.encode(start)).digest == start.digest
    a, b = make(backend=backend, state=start), make(backend=backend, state=start)
    a.advance_to(20_000_000)
    for t in (1500001, 3333333, 17_777_777, 20_000_000):
        b.advance_to(t)
        b = make(backend=backend, state=b.capture_state())
    assert a.capture_state().payload == b.capture_state().payload
    for age in ("preserve", "reset"):
        child = birth(start, decay_age=age)
        same(make(state=child).capture_state().to_dict(), make(backend="native", state=child).capture_state().to_dict())
        assert child.to_dict()["dynamics"] == KERNEL_ID


@pytest.mark.parametrize(
    "kw",
    ({"deletion_strategy": "typo"}, {"activation_send_threshold": -1}, {"inhibition_send_threshold": float("nan")}),
)
@pytest.mark.parametrize("backend", ("reference", "native"))
def test_invalid_options(backend, kw):
    with pytest.raises(ValueError):
        resolve_kernel(KERNEL_ID).create(kw, backend=backend)


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_configuration_switch_and_zero_delete_threshold(backend):
    e = quiet_pair(backend)
    e.reconfigure(replace(e.config, deletion_strategy="global-scan", activation_send_threshold=0.2))
    d = e.capture_state().to_dict()
    assert any(t[0] == 6 for t in d["timers"])
    assert not any(t[0] in (2, 3) for t in d["timers"])
    e.reconfigure(replace(e.config, deletion_strategy="local", prune_weight=0.0))
    d = e.capture_state().to_dict()
    assert not any(t[0] in (2, 6) for t in d["timers"])
    make(backend=backend, state=e.capture_state())
    e.reconfigure(replace(e.config, prune_weight=0.008))
    assert any(t[0] == 2 for t in e.capture_state().to_dict()["timers"])


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_leading_zero_short_term_clocks_round_trip(backend):
    e = make()
    inject_course(e)
    e.advance_to(1000000)
    d = e.capture_state().to_dict()
    for row in d["edges"]:
        for name in ("short_term", "fast"):
            if row[name]:
                row[name]["time_us"] = "000" + row[name]["time_us"]
    restored = make(backend=backend, state=state(d))
    same(d, restored.capture_state().to_dict())
    p = make(state=state(d))
    p.advance_to(2000000)
    restored.advance_to(2000000)
    same(p.capture_state().to_dict(), restored.capture_state().to_dict())


@pytest.mark.parametrize("curve", ("exponential", "power-law", "inverse-logarithmic", "power-exponential"))
def test_local_and_global_have_same_idle_deletion_grid(curve):
    local = quiet_pair(decay_curve=curve)
    scan = quiet_pair(decay_curve=curve, deletion_strategy="global-scan")
    due = min(int(t[3]) for t in local.capture_state().to_dict()["timers"] if t[0] == 2)
    for t in (due - 1, due, due + 100000):
        local.advance_to(t)
        scan.advance_to(t)
        assert set(local.edges) == set(scan.edges)
        assert set(local.nodes) == set(scan.nodes)
