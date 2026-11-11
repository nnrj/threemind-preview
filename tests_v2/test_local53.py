"""Engineering specimens only: no research subjects or training conclusions."""

import math
from dataclasses import asdict

import pytest

from threemind_core import StateImage, Stimulus
from threemind_kernels.decay53 import CURVES, decay_value, log_remaining
from threemind_kernels.local53 import KERNEL_ID, Local53Config
from threemind_kernels.registry import resolve_kernel, DEFAULT_KERNEL


def same(a, b, path=""):
    """No tolerance for event identity, ordering, topology or discrete outcomes."""
    if isinstance(a, dict):
        assert a.keys() == b.keys(), path
        for k in a:
            same(a[k], b[k], path + "/" + k)
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            same(x, y, f"{path}/{i}")
    elif isinstance(a, float):
        assert math.isclose(a, b, rel_tol=3e-12, abs_tol=3e-14), (path, a, b)
    else:
        assert a == b, (path, a, b)


def make(config=None, backend="reference"):
    return resolve_kernel(KERNEL_ID).create(config or Local53Config(), backend=backend)


def inputs():
    return [
        Stimulus(t, ((1, 0.7), (2 + i % 3, 0.4)), intensity=3.0 if i == 4 else 1.0)
        for i, t in enumerate((0, 0, 50_000, 100_000, 110_000, 200_000, 411_337, 900_000))
    ]


@pytest.mark.parametrize("curve", CURVES)
@pytest.mark.parametrize("relax", (False, True))
def test_decay_closed_form_and_split(curve, relax):
    c = Local53Config(decay_curve=curve, retention_relaxation_enabled=relax)
    value, age, h = decay_value(0.8, 0.25, 100.0, 10000.0, c)
    v, a, scale = 0.8, 0.25, 100.0
    for dt in (1.0, 29.0, 70.0, 900.0, 9000.0):
        v, a, scale = decay_value(v, a, scale, dt, c)
    assert math.isclose(v, value, rel_tol=3e-13, abs_tol=1e-100)
    assert math.isclose(a, age, rel_tol=3e-14)
    assert scale == h
    assert math.isclose(value, 0.8 * math.exp(log_remaining(curve, age) - log_remaining(curve, 0.25)), rel_tol=3e-13)


def test_piecewise_value_and_slope_are_continuous():
    h = 1e-5
    mid = log_remaining("power-exponential", 10)
    left = (mid - log_remaining("power-exponential", 10 - h)) / h
    right = (log_remaining("power-exponential", 10 + h) - mid) / h
    assert left == pytest.approx(-1 / 11, rel=1e-5)
    assert right == pytest.approx(left, rel=1e-5)


@pytest.mark.parametrize("curve", CURVES)
@pytest.mark.parametrize("policy", ("keep", "reset"))
@pytest.mark.parametrize("growth,relax", ((False, False), (True, True)))
def test_reference_native_state_events_and_cross_restore(curve, policy, growth, relax):
    c = Local53Config(
        decay_curve=curve,
        reinforcement_age_policy=policy,
        retention_growth_enabled=growth,
        retention_relaxation_enabled=relax,
    )
    ref, native = make(c), make(c, "native")
    for s in inputs():
        ref.inject(s)
        native.inject(s)
    for t in (0, 50_000, 100_000, 110_000, 200_000, 411_337, 500_000, 900_000, 1_000_000, 5_000_000):
        a, b = [], []
        ref.advance_to(t, a.append)
        native.advance_to(t, b.append)
        same(a, b, "events")
        same(ref.capture_state().to_dict(), native.capture_state().to_dict(), "state")
        same(ref.graph(), native.graph(), "graph")
        old = ref.capture_state()
        for _ in range(2):
            ref.metrics()
            ref.activations()
            ref.graph()
            ref.capture_state()
        assert old.payload == ref.capture_state().payload
        ref = resolve_kernel(KERNEL_ID).create(state=native.capture_state(), backend="reference")
        native = resolve_kernel(KERNEL_ID).create(state=old, backend="native")


@pytest.mark.parametrize("backend", ("reference", "native"))
@pytest.mark.parametrize("curve", CURVES)
def test_advance_partition_and_observation_do_not_change_trajectory(backend, curve):
    c = Local53Config(decay_curve=curve)
    full, parts = make(c, backend), make(c, backend)
    for s in inputs():
        full.inject(s)
        parts.inject(s)
    full.advance_to(2_000_000)
    for t in range(0, 2_000_000, 17321):
        parts.advance_to(t)
        parts.metrics()
        parts.capture_state()
        parts.graph()
    parts.advance_to(2_000_000)
    same(full.capture_state().to_dict(), parts.capture_state().to_dict())


@pytest.mark.parametrize("policy", ("keep", "reset"))
def test_age_policy_damage_cap_and_constant_state(policy):
    e = make(Local53Config(reinforcement_age_policy=policy))
    row = e.edge_type(0, 1, 0.3, decay_age=10)
    row.weight += 0.2
    assert row.decay_age == (10 if policy == "keep" else 0)
    row.decay_age = 10
    row.weight -= 0.1
    assert row.decay_age == 10
    row.weight = 1.0
    row.decay_age = 10
    row.weight = 1.0
    assert row.decay_age == 10
    fields = set(asdict(row))
    for _ in range(1000):
        row.weight = 0.9
        row.weight = 1.0
    assert set(asdict(row)) == fields
    assert "decay_contributions" not in fields


def simple_state(**config):
    e = make(Local53Config(stp_enabled=False, fast_enabled=False, context_enabled=False, inhibition=False, **config))
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.7))))
    e.advance_to(0)
    return e


def test_two_directions_delete_independently_at_clock_check():
    e = simple_state(propagation_rate=0.0)
    assert set(e.edges) == {(0, 1), (1, 0)}
    e.edges[0, 1].weight = 0.007
    e.advance_to(99_999)
    assert (0, 1) in e.edges
    e.advance_to(100_000)
    assert (0, 1) not in e.edges and (1, 0) in e.edges
    assert not any(k[0] == 2 for k in e.timers.positions)


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_same_time_reinforcement_precedes_deletion(backend):
    e = simple_state(propagation_rate=0.0)
    e.edges[0, 1].weight = 0.007
    e = resolve_kernel(KERNEL_ID).create(state=e.capture_state(), backend=backend)
    e.inject(Stimulus(100_000, ((1, 0.9), (2, 0.9))))
    e.advance_to(100_000)
    assert {(x["source"], x["target"]) for x in e.graph()["edges"]} == {(0, 1), (1, 0)}


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_saved_identity_and_missing_clock_are_rejected(backend):
    e = simple_state()
    for mutation in ("identity", "age", "clock"):
        doc = e.capture_state().to_dict()
        if mutation == "identity":
            doc["dynamics"] = "threemind.continuous-memory/5.1"
        elif mutation == "age":
            del doc["edges"][0]["decay_age"]
        else:
            doc["timers"] = [t for t in doc["timers"] if t[0] != 6]
        with pytest.raises(ValueError):
            resolve_kernel(KERNEL_ID).create(state=StateImage.from_dict(doc), backend=backend)


@pytest.mark.parametrize("backend", ("reference", "native"))
@pytest.mark.parametrize(
    "extra",
    (
        {"energy_simulation_enabled": True, "energy_model": "local-field"},
        {"energy_simulation_enabled": True, "energy_model": "global-ledger"},
        {"spatial_embedding": True, "neighborhood_enabled": True},
        {"arrival_mode": "coincident", "reception_mode": "unified", "propagation_phase": "asynchronous"},
        {"inhibitory_learning_enabled": False},
        {"signal_threshold_enabled": False},
        {"weight_gate_enabled": True, "weight_gate": 0.1},
        {"plasticity": False},
    ),
)
def test_configuration_variants_and_restore(backend, extra):
    c = Local53Config(**extra)
    a, b = make(c), make(c, backend)
    for s in inputs():
        a.inject(s)
        b.inject(s)
    for t in (100_000, 200_000, 500_000, 1_000_000):
        a.advance_to(t)
        b.advance_to(t)
        same(a.capture_state().to_dict(), b.capture_state().to_dict())
        b = resolve_kernel(KERNEL_ID).create(state=b.capture_state(), backend=backend)


def test_global_default_unchanged_and_version_definition():
    assert DEFAULT_KERNEL == "threemind.continuous-memory/3"
    assert (
        make().definition(Local53Config())
        == resolve_kernel(KERNEL_ID).create(backend="native").capture_state().to_dict()["definition"]
    )


def transport_specimen(**changes):
    config = dict(
        stp_enabled=False,
        fast_enabled=False,
        context_enabled=False,
        activation_decay_enabled=False,
        inhibition_decay_enabled=False,
        plasticity=True,
        propagation_rate=10.0,
        inhibition_diffusion_rate=10.0,
        activation_floor=0.0,
        signal_threshold=0.01,
        inhibition=False,
    )
    config.update(changes)
    e = make(Local53Config(**config))
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.7))))
    e.advance_to(0)
    for n in e.nodes.values():
        n.activation = 0.2
        n.inhibition = 0
        n.pending_inhibition = 0
        n.generated_inhibition = 0
    e.intervene(edges=[(1, 0)], action="disconnect_edges")
    return e


@pytest.mark.parametrize("backend", ("reference", "native"))
@pytest.mark.parametrize(
    "weight,signal,passes", ((0.8, 0.02, True), (0.02, 0.8, True), (0.02, 0.02, False), (0.8, 0.8, True))
)
def test_joint_weight_signal_criterion(backend, weight, signal, passes):
    e = transport_specimen()
    e.edges[0, 1].weight = weight
    e.nodes[0].activation = signal
    e = resolve_kernel(KERNEL_ID).create(state=e.capture_state(), backend=backend)
    e.advance_to(100_000)
    queue = e.capture_state().to_dict()["queue"]
    messages = [m for event in queue if event["kind"] == "signal" for m in event["payload"]["messages"]]
    assert bool(messages) == passes
    if messages:
        assert messages[0][0:2] == [0, 1]


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_inhibition_cannot_use_reverse_of_incoming_edge(backend):
    e = transport_specimen(inhibition=True)
    for n in e.nodes.values():
        n.activation = 0
    e.nodes[1].inhibition = 0.5
    e = resolve_kernel(KERNEL_ID).create(state=e.capture_state(), backend=backend)
    e.advance_to(110_000)
    assert e.graph()["nodes"][0]["pending_inhibition"] == 0
    assert e.graph()["nodes"][0]["inhibition"] == 0


@pytest.mark.parametrize("backend", ("reference", "native"))
@pytest.mark.parametrize("inhibitory_learning", (False, True))
def test_inhibition_learning_has_explicit_control(backend, inhibitory_learning):
    e = transport_specimen(inhibition=True, inhibitory_learning_enabled=inhibitory_learning)
    for n in e.nodes.values():
        n.activation = 0
    e.nodes[0].inhibition = 0.5
    e.edges[0, 1].weight = 0.8
    expected = e._project_edge(e.edges[0, 1], 100_000).weight
    e = resolve_kernel(KERNEL_ID).create(state=e.capture_state(), backend=backend)
    e.advance_to(100_000)
    result = e.graph()["edges"][0]["weight"]
    assert (result > expected) == inhibitory_learning
    assert any(q["kind"] == "inhibition" for q in e.capture_state().to_dict()["queue"])


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_failed_attempt_still_costs_energy_and_shared_resource(backend):
    from threemind_kernels.mechanisms import ShortTermState

    e = transport_specimen(
        inhibition=True,
        stp_enabled=True,
        signal_threshold=1.0,
        energy_simulation_enabled=True,
        energy_model="global-ledger",
        energy_direct_cost=0.0,
    )
    e.nodes[0].inhibition = 0.5
    expected_state, fraction = ShortTermState().release(100_000, e.config.short_term())
    saturation = e.config.inhibition_saturation
    inhibition = saturation * math.tanh(math.tanh(0.5 / saturation))
    excitation = 0.2 / (1 + e.config.inhibition_response_gain * inhibition)
    expected_cost = excitation * e.config.energy_associative_cost + inhibition * e.config.energy_inhibition_cost
    e = resolve_kernel(KERNEL_ID).create(state=e.capture_state(), backend=backend)
    e.advance_to(100_000)
    doc = e.capture_state().to_dict()
    assert doc["energy"]["consumed_associative"] + doc["energy"]["consumed_inhibition"] == pytest.approx(expected_cost)
    assert doc["edges"][0]["short_term"]["available"] == pytest.approx(expected_state.available)
    assert not any(q["kind"] in ("signal", "inhibition") for q in doc["queue"])


@pytest.mark.parametrize("backend", ("reference", "native"))
def test_underfunded_attempts_have_equal_scale(backend):
    e = transport_specimen(
        inhibition=True,
        signal_threshold=0.0,
        energy_direct_cost=0.0,
        energy_simulation_enabled=True,
        energy_model="global-ledger",
    )
    e.nodes[0].inhibition = 0.5
    e.edges[0, 1].weight = 0.8
    e.energy.reserve = 0.0001
    # Explicit engineering budget specimen, not a naturally trained subject.
    e.energy.discarded_total = e.energy.initial_total - 0.0001
    e = resolve_kernel(KERNEL_ID).create(state=e.capture_state(), backend=backend)
    e.advance_to(100_000)
    energy = e.metrics()["energy"]
    saturation = e.config.inhibition_saturation
    inhibition = saturation * math.tanh(math.tanh(0.5 / saturation))
    excitation = 0.2 / (1 + e.config.inhibition_response_gain * inhibition)
    ratio = (excitation * 0.02) / (inhibition * 0.01)
    assert energy["consumed_associative"] / energy["consumed_inhibition"] == pytest.approx(ratio)
    assert energy["consumed_associative"] + energy["consumed_inhibition"] == pytest.approx(0.0001)


def test_public_configuration_has_every_supported_field_and_locks():
    from dataclasses import fields
    from threemind_lab.configuration import catalogue
    from threemind_runtime.codec import ArtifactCodec
    from threemind_runtime.inheritance import birth

    cat = catalogue(KERNEL_ID)
    actual = [x["path"] for x in cat["fields"] if x["path"].startswith("config.")]
    inactive = {
        "propagation_limit",
        "edge_adaptation_limit",
        "homeostasis_enabled",
        "target_total_activation",
        "spatial_competition_rate",
        "attention_competition_enabled",
        "attention_budget",
        "edge_birth_policy",
        "association_window_us",
        "step_us",
    }
    expected = {"config." + f.name for f in fields(Local53Config) if f.name not in inactive}
    assert set(actual) == expected
    assert len(actual) == len(set(actual))
    for field in ("decay_curve", "decay_transition_age", "reinforcement_age_policy", "structure_check_interval_us"):
        assert "config." + field in cat["kernel_immutable"][KERNEL_ID]
    image = simple_state().capture_state()
    for fmt in ("json", "tmind"):
        restored = ArtifactCodec.decode(ArtifactCodec.encode(image, fmt))
        assert restored.payload == image.payload
        assert make().dynamics == resolve_kernel(KERNEL_ID).create(state=restored, backend="native").dynamics
    with pytest.raises(ValueError, match="age"):
        birth(image)


@pytest.mark.parametrize("model", ("local-field", "global-ledger"))
@pytest.mark.parametrize("distribution", ("counter-random", "stream-random"))
def test_explicit_energy_delivery_matches_and_survives_restore(model, distribution):
    cfg = Local53Config(
        energy_simulation_enabled=True,
        energy_model=model,
        energy_distribution=distribution,
        energy_initial_reserve=0.04,
    )
    ref, native = make(cfg), make(cfg, "native")
    for core in (ref, native):
        core.inject(Stimulus(0, ((1, 0.7), (2, 0.6))))
        core.supply_energy(0.4, time_us=50_000)
        core.supply_energy(0.6, time_us=150_000)
    for when in (0, 50_000, 110_000, 150_000, 200_000):
        traces = []
        for core in (ref, native):
            trace = []
            core.advance_to(when, trace.append)
            traces.append(trace)
        same(*traces)
        same(ref.capture_state().to_dict(), native.capture_state().to_dict())
        state = ref.capture_state()
        ref = resolve_kernel(KERNEL_ID).create(state=native.capture_state(), backend="reference")
        native = resolve_kernel(KERNEL_ID).create(state=state, backend="native")
