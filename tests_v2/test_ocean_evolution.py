import copy
import json

import numpy as np
import pytest

from lab.tools.ocean_evolution import TRAITS, EvolutionOcean, EvolutionProtocol
from lab.tools.ocean_evolution_cli import RecordWriter, iter_records, load_population, run, verify


def world(**values):
    return EvolutionOcean(EvolutionProtocol(founders=2, **values).model_dump(by_alias=True))


def credit(w, i, amount):
    w.bodies[i].storage += amount
    w.totals["environment_food"] += amount
    w.totals["food_consumed"] += amount


def test_motor_cost_is_paid_and_zero_fuel_produces_no_free_thrust():
    a = world(nutrient_initial=0, reproduction=False)
    b = world(nutrient_initial=0, reproduction=False)
    before = a.bodies[0].storage
    a._move(a.bodies[0], [1, 1, 1])
    b._move(b.bodies[0], [0, 0, 0])
    assert a.bodies[0].storage < before and a.bodies[0].motor_energy > 0
    assert a.bodies[0].mechanical_work_j <= a.bodies[0].motor_energy * a.p.joules_per_energy
    a.bodies[0].storage = 0
    b.bodies[0] = copy.deepcopy(a.bodies[0])
    a._move(a.bodies[0], [1, 1, 1])
    b._move(b.bodies[0], [0, 0, 0])
    assert a.bodies[0].position == b.bodies[0].position
    assert a.bodies[0].storage == 0


def test_size_and_shell_have_maintenance_costs_and_energy_ledger_closes():
    w = world(reproduction=False)
    w.bodies[1].radius *= 1.3
    w.bodies[1].shell = 0.9
    for _ in range(100):
        w.step()
    assert w.bodies[1].body_maintenance > w.bodies[0].body_maintenance
    assert abs(w.metrics()["energy_balance_error"]) < 1e-7


def test_source_protocol_and_state_are_versioned_without_changing_core():
    w = world(reproduction=False)
    for _ in range(10):
        w.step()
    state = json.loads(json.dumps(w.capture()))
    images = {i: e.capture_state() for i, e in w.engines.items()}
    resumed = EvolutionOcean(state["protocol"], state=state, images=images)
    for _ in range(10):
        w.step()
        resumed.step()
    assert w.capture() == resumed.capture()
    assert all(
        e.capture_state().to_dict()["definition"]["kernel_id"] == "threemind.continuous-memory/2"
        for e in w.engines.values()
    )
    assert w.p.maximum_age_us is None
    with pytest.raises(ValueError):
        EvolutionProtocol(schema="threemind.ocean/1")


def test_reflectance_changes_local_measurement_not_hidden_core_values():
    w = world(reproduction=False)
    w.bodies[0].position = [0.1, 0.1]
    w.bodies[1].position = [0.115, 0.1]
    before = w.engines[0].capture_state().digest
    high = w.senses(0)[1][13:17]
    w.bodies[1].reflectance = 0
    low = w.senses(0)[1][13:17]
    assert sum(high) > sum(low) == 0
    assert w.engines[0].capture_state().digest == before


def test_newborn_parent_protection_and_shell_cost():
    w = world(predation=True, reproduction=False)
    w.step()
    a, b = w.bodies[0], w.bodies[1]
    a.radius = 0.016
    b.radius = 0.008
    a.position = b.position = [0.1, 0.1]
    b.parent = 0
    b.birth_us = w.time_us
    w._predation([0, 1])
    w.time_us += 1000000
    w._predation([0, 1])
    assert b.physical and w.totals["protected_contacts"] > 0
    w.time_us = b.birth_us + w.p.maturity_us
    w._predation([0, 1])
    w.time_us += w.p.engulf_dwell_us * 5
    before = a.storage
    w._predation([0, 1])
    assert not b.physical and b.consumed_by == 0
    assert w.totals["shell_heat"] > 0
    assert a.storage != before
    assert abs(w.metrics()["energy_balance_error"]) < 1e-7


def test_sharing_is_local_compatible_lossy_and_conservative():
    w = world(sharing_rate_per_s=1, reproduction=False)
    a, b = w.bodies[0], w.bodies[1]
    a.position = b.position = [0.1, 0.1]
    credit(w, 0, 100)
    before = a.storage + b.storage
    w._share([0, 1])
    assert a.share_sent > 0 and b.share_received == pytest.approx(a.share_sent * 0.9)
    assert a.storage + b.storage < before
    assert abs(w.metrics()["energy_balance_error"]) < 1e-7
    b.ligand = 1
    prior = (a.storage, b.storage)
    w._share([0, 1])
    assert (a.storage, b.storage) == prior


def test_birth_funds_body_core_and_material_preserves_parent_brain():
    w = world(reproduction_age_us=0, reproduction_cooldown_us=1000, recombination_probability=1)
    w.step()
    w.time_us = 1000000
    for e in w.engines.values():
        e.advance_to(w.time_us)
    a, b = w.bodies[0], w.bodies[1]
    a.position = b.position = [0.1, 0.1]
    a.birth_us = b.birth_us = -w.p.maturity_us
    b.shell = 0.9
    credit(w, 0, 9000)
    before = w.engines[0].capture_state().digest
    w._reproduce()
    assert w.totals["births"] == 1 and w.totals["recombinations"] == 1
    child = w.bodies[2]
    assert child.storage == w.p.child_body_energy
    assert w.engines[2].metrics()["energy"]["reserve"] == w.p.child_energy
    assert w.engines[0].capture_state().digest == before
    assert child.parent == 0
    assert abs(w.metrics()["energy_balance_error"]) < 1e-6


def test_mutations_are_not_always_beneficial_and_have_neutral_carrier():
    w = world(mutation_probability=1, mutation_sigma=0.2)
    parent = w.bodies[0]
    samples = [w._child_traits(parent)[0] for _ in range(100)]
    for key in ("radius", "thrust", "sensor_range", "shell", "reflectance"):
        assert min(v[key] for v in samples) < getattr(parent, key) < max(v[key] for v in samples)
    assert len({v["neutral_allele"] for v in samples}) > 90
    assert set(samples[0]) == set(TRAITS)


def test_engulfing_retains_future_alleles_without_changing_live_body_or_brain():
    w = world(predation=True, reproduction=False, horizontal_transfer_probability=1, mutation_sigma=0.0)
    w.step()
    a, b = w.bodies[0], w.bodies[1]
    a.radius, b.radius = 0.016, 0.008
    a.position = b.position = [0.1, 0.1]
    b.reflectance = 0.05
    before = {k: getattr(a, k) for k in TRAITS}
    brain = w.engines[0].capture_state().digest
    w._predation([0, 1])
    w.time_us += 1000000
    w._predation([0, 1])
    assert a.genome_donor == 1 and w.totals["horizontal_transfers"] == 1
    assert {k: getattr(a, k) for k in TRAITS} == before
    assert w.engines[0].capture_state().digest == brain
    assert any(w._child_traits(a)[0]["reflectance"] == 0.05 for _ in range(20))


def test_pending_offspring_does_not_reroll_and_age_is_an_explicit_body_option():
    w = world(reproduction_age_us=0, reproduction_cooldown_us=1000, construction_energy=10000.0)
    w.step()
    w.time_us = 1000000
    for e in w.engines.values():
        e.advance_to(w.time_us)
    credit(w, 0, 5000)
    w._reproduce()
    pending = copy.deepcopy(w.bodies[0].pending_birth)
    assert pending and w.totals["births"] == 0
    rng = copy.deepcopy(w.mutations.bit_generator.state)
    w.time_us += w.p.reproduction_interval_us
    w._reproduce()
    assert w.bodies[0].pending_birth == pending and w.mutations.bit_generator.state == rng
    aged = world(reproduction=False, maximum_age_us=20000)
    aged.step()
    aged.step()
    assert all(not b.physical and b.body_failure == "configured_age_limit" for b in aged.bodies.values())
    assert any(e.life != "dead" for e in aged.engines.values())


def test_lossless_arrow_full_replay_and_restore(tmp_path):
    w = world(reproduction=False)
    result = run(w, tmp_path / "case", 400000)
    assert result["horizon_reached"]
    assert verify(tmp_path / "case")["matched"]
    other = load_population(tmp_path / "case/final")
    w.step()
    other.step()
    assert w.capture() == other.capture()
    writer = RecordWriter(tmp_path / "standalone", chunk_steps=1)
    row = {
        "time_us": 1,
        "inputs": [
            {
                "individual": 2,
                "stimulus": {"time_us": "1", "channels": [[2**32 - 1, np.nextafter(0.0, 1.0)]], "intensity": 1.0},
                "food": 0.0,
                "raw": [-0.0, 1e-200],
                "action": [0.0, 0.0, 0.0],
            }
        ],
        "events": [],
    }
    writer.record(row)
    got = next(iter_records(tmp_path / "standalone"))
    assert got == row and np.signbit(got["inputs"][0]["raw"][0])


def test_native_reference_agree_on_external_body_and_kernel_identity():
    p = EvolutionProtocol(founders=1, reproduction=False).model_dump(by_alias=True)
    a, b = EvolutionOcean(p), EvolutionOcean(p, backend="reference")
    for _ in range(20):
        a.step()
        b.step()
    assert a.bodies[0].position == pytest.approx(b.bodies[0].position, abs=1e-14)
    assert a.bodies[0].storage == pytest.approx(b.bodies[0].storage, rel=1e-12)

    def compare(x, y):
        if isinstance(x, dict):
            assert x.keys() == y.keys()
            for k in x:
                compare(x[k], y[k])
        elif isinstance(x, list):
            assert len(x) == len(y)
            for m, n in zip(x, y, strict=True):
                compare(m, n)
        elif isinstance(x, float):
            assert x == pytest.approx(y, rel=1e-12, abs=1e-14)
        else:
            assert x == y

    compare(a.engines[0].capture_state().to_dict(), b.engines[0].capture_state().to_dict())


def test_birth_budget_can_preserve_motor_fuel_without_changing_legacy_digestive_rule():
    remaining = []
    for child_energy in (1800.0, 2400.0):
        w = world(reproduction_age_us=0, reproduction_cooldown_us=1000, child_energy=child_energy)
        w.step()
        w.time_us = 1000000
        for e in w.engines.values():
            e.advance_to(w.time_us)
        credit(w, 0, 9000)
        w._reproduce()
        assert w.totals["births"] == 1
        child = w.bodies[2]
        assert child.storage == w.p.child_body_energy
        w.step()
        remaining.append(child.storage)
        assert abs(w.metrics()["energy_balance_error"]) < 1e-6
    # Old parameters remain reproducible; equal initial Core endowment removes
    # the initial reserve gap, without inventing free body energy or changing Core.
    assert remaining[0] == 0.0
    assert remaining[1] > 0.99 * 600.0
