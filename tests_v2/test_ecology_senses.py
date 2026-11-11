import copy

import pytest

from threemind_core import Stimulus
from threemind_runtime import create_engine
from threemind_runtime.ecology_rules import EcologyLedger, EcologyRules
from threemind_runtime.ecology_senses import BodyStateSenses, transduce
from threemind_runtime.world_schema import default_world


def test_default_body_senses_use_actual_resources_and_keep_zero_values_in_evidence():
    world = default_world()
    ledger = EcologyLedger(EcologyRules(), 11, 20000)
    config = BodyStateSenses()
    raw = Stimulus(0, ((1, 0.5),))
    frame, evidence = transduce(config, world, raw, ledger, "n0", (0, 0, 0.15), 11)
    assert evidence["reserve"] == 4 and evidence["damage"] == 0
    assert evidence["normalized"]["reserve"] == 0.4
    assert evidence["normalized"]["resource"] == pytest.approx(20 / 30)
    assert evidence["encoded"]["damage"]["amplitude"] == 0
    assert evidence["encoded"]["damage"]["channel"] not in dict(frame.channels)
    assert dict(frame.channels)[1] == 0.5
    assert frame.time_us == raw.time_us
    assert not evidence["core_energy_coupling"]
    distant, facts = transduce(config, world, raw, ledger, "n0", (100, 0, 0), 11)
    assert facts["normalized"]["resource"] == 0 and len(distant.channels) == 2
    ledger.pools["shared"]["resource"] = 0  # Deliberately controlled external measurement fixture.
    _, depleted = transduce(config, world, raw, ledger, "n0", (0, 0, 0.15), 11)
    assert depleted["normalized"]["resource"] == 0


def test_sense_switches_scales_and_ports_are_explicit_and_do_not_mutate_inputs():
    world, ledger = default_world(), EcologyLedger(EcologyRules(), 11, 20000)
    raw = Stimulus(0, ((1, 0.5),))
    config = BodyStateSenses(enabled=False)
    frame, evidence = transduce(config, world, raw, ledger, "n0", (0, 0, 0.15), 11)
    assert frame is raw and not evidence["encoded"] and evidence["reserve"] == 4
    config = BodyStateSenses(reserve_enabled=False, damage_enabled=False)
    frame, evidence = transduce(config, world, raw, ledger, "n0", (0, 0, 0.15), 11)
    assert set(evidence["encoded"]) == {"resource"} and len(frame.channels) == 2
    config = BodyStateSenses(reserve_scale=20.0, gain=2.0, intensity=0.5)
    _, evidence = transduce(config, world, raw, ledger, "n0", (0, 0, 0.15), 11)
    assert evidence["encoded"]["reserve"]["amplitude"] == pytest.approx(0.2)
    assert raw.channels == ((1, 0.5),)
    for config in (BodyStateSenses(reserve_port=0), BodyStateSenses(damage_port=4092)):
        with pytest.raises(ValueError, match="collide"):
            config.validate_ports(world)


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_observer_identity_and_explanations_do_not_enter_core_dynamics(backend):
    world, rules = default_world(), EcologyRules()
    changed = copy.deepcopy(rules)
    changed.patches[0].label = "研究者解释它为有益，不进入匿名刺激"
    left, right = EcologyLedger(rules, 17, 20000), EcologyLedger(changed, 17, 20000)
    a, b = create_engine(backend=backend), create_engine(backend=backend)
    config = BodyStateSenses()
    for now in range(20000, 120001, 20000):
        for ledger in (left, right):
            ledger.step({"n0": {"position": [0, 0, 0.15]}, "n1": {"position": [0, 0, 0.15]}})
        original = Stimulus(now, ((7, 0.3), (9, 0.7)))
        first, metadata_a = transduce(config, world, original, left, "n0", (0, 0, 0.15), 17)
        second, metadata_b = transduce(config, world, original, right, "n1", (0, 0, 0.15), 17)
        assert metadata_a["individual"] != metadata_b["individual"]
        assert first == second
        a.inject(first)
        b.inject(second)
        a.advance_to(now)
        b.advance_to(now)
        assert a.capture_state().digest == b.capture_state().digest
    assert a.metrics()["nodes"] > 0
