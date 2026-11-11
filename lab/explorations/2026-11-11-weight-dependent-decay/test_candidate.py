"""Engineering verification only; seeds excluded from scientific origins."""

import copy
import math
from dataclasses import replace

import pytest
from threemind_core import Stimulus
from threemind_kernels.local53 import Local53Config, Local53Engine
from candidate import CandidateConfig, RULES, create, exact_weight


@pytest.mark.parametrize("w", [0.0, 0.008, 0.035, 0.2, 0.9, 0.999, 1.0])
def test_exact_flow_and_differential_equation(w):
    a, b = math.log(2) / 86400, 0.06
    x = exact_weight(w, 9, a, b)
    assert 0 <= x <= w
    assert exact_weight(exact_weight(w, 3, a, b), 6, a, b) == pytest.approx(x, rel=2e-14, abs=1e-15)
    dt = 1e-5
    derivative = (exact_weight(w, dt, a, b) - w) / dt
    assert derivative == pytest.approx(-w * (a + b * (1 - w)), rel=1e-5, abs=1e-10)
    assert exact_weight(w, 30, a, 0) == pytest.approx(w * math.exp(-a * 30), rel=2e-14)
    assert exact_weight(w, 30 * 86400, a, b) < 0.008


def test_stronger_weight_has_slower_relative_loss():
    values = [0.008, 0.035, 0.2, 0.5, 0.9, 1.0]
    fractions = [exact_weight(w, 10, 0.00001, 0.06) / w for w in values]
    assert all(x < y for x, y in zip(fractions, fractions[1:]))


@pytest.mark.parametrize(
    "args",
    [
        (-0.1, 1, 0.1, 0.1),
        (1.1, 1, 0.1, 0.1),
        (0.5, -1, 0.1, 0.1),
        (0.5, 1, 0, 0.1),
        (0.5, 1, 0.1, -0.1),
        (0.5, float("nan"), 0.1, 0.1),
    ],
)
def test_invalid_quantities_rejected(args):
    with pytest.raises(ValueError):
        exact_weight(*args)


@pytest.mark.parametrize("rule", RULES)
def test_state_restore_next_input_and_observation(rule):
    x = create(98765411, rule)
    x.inject(Stimulus(0, ((1, 0.4), (2, 0.4)), 1.0))
    x.advance_to(1_000_000)
    before = x.capture_state().to_dict()
    for _ in range(5):
        x.graph()
        x.observation_nodes()
    assert before == x.capture_state().to_dict()
    y = create(state=copy.deepcopy(before))
    for obj in (x, y):
        obj.inject(Stimulus(1_100_000, ((1, 0.8),), 1.0))
        obj.advance_to(2_000_000)
    assert x.capture_state().to_dict() == y.capture_state().to_dict()
    assert x.dynamics == "threemind.experimental-weight-decay/1"
    with pytest.raises(ValueError):
        Local53Engine(state=x.capture_state())
    with pytest.raises(ValueError):
        x.reconfigure(replace(x.config, extra_rate=0.03))


def test_inverse_reference_matches_production_dynamics():
    a = create(98765412, "inverse-logarithmic", energy_seed=43)
    b = Local53Engine(Local53Config(seed=98765412, energy_seed=43, decay_curve="inverse-logarithmic"))
    for t in range(0, 20_000_000, 500_000):
        event = Stimulus(t, ((1, 0.4), (2, 0.4)) if t < 2_000_000 else ((3, 0.2),), 1.0)
        for x in (a, b):
            x.inject(event)
            x.advance_to(t)
    aa = a.capture_state().to_dict()
    bb = b.capture_state().to_dict()
    for key in ("schema", "dynamics", "definition", "definition_hash", "config"):
        aa.pop(key)
        bb.pop(key)
    assert aa == bb


@pytest.mark.parametrize("rule", RULES)
def test_elapsed_partition_preserves_next_response(rule):
    a = create(98765414, rule)
    b = create(98765414, rule)
    for x in (a, b):
        for t in range(0, 3_000_000, 500_000):
            x.inject(Stimulus(t, ((1, 0.2), (2, 0.2)), 1.0))
    a.advance_to(3_000_000)
    for t in range(50_000, 3_000_001, 50_000):
        b.advance_to(t)
    assert a.capture_state().to_dict() == b.capture_state().to_dict()


def test_configuration_preserves_local_mechanisms():
    c = CandidateConfig()
    assert c.decay_curve == "inverse-logarithmic"
    assert not c.retention_growth_enabled and not c.retention_relaxation_enabled
    assert c.reinforcement_age_policy == "keep"
    assert c.signal_threshold_enabled and c.inhibitory_learning_enabled
