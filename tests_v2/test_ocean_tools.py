import copy
import json
import math

import pytest

from lab.tools.ocean import Ocean, OceanProtocol, zero_energy_birth
from lab.tools.ocean_controls import naive_same_receptors


def protocol(**kwargs):
    return OceanProtocol(**kwargs).model_dump(by_alias=True)


def test_food_contact_is_exclusive_and_population_energy_is_conserved():
    w = Ocean(protocol(founders=2, nutrient_initial=1, reproduction=False))
    w.bodies[0].position = w.food[0].tolist()
    w.bodies[1].position = w.food[0].tolist()
    w._ingest([0, 1])
    assert sum(b.grains for b in w.bodies.values()) == 1
    assert not len(w.food)
    w._ingest([0, 1])
    assert sum(b.grains for b in w.bodies.values()) == 1
    for _ in range(100):
        w.step()
    assert abs(w.metrics()["energy_balance_error"]) < 1e-8


def test_exact_checkpoint_continuation_with_physics_rng_and_core():
    w = Ocean(protocol(founders=2, reproduction=False))
    for _ in range(25):
        w.step()
    state = json.loads(json.dumps(w.capture()))
    images = {i: e.capture_state() for i, e in w.engines.items()}
    other = Ocean(state["protocol"], state=state, images=images)
    for _ in range(25):
        w.step()
        other.step()
    assert w.capture() == other.capture()
    assert w.metrics() == other.metrics()
    wrong = copy.deepcopy(state)
    wrong["core_hashes"]["0"] = "corrupt"
    with pytest.raises(ValueError, match="checksum"):
        Ocean(state["protocol"], state=wrong, images=images)


def test_reproduction_transfers_stored_food_and_not_free_core_reserves():
    w = Ocean(protocol(founders=1, reproduction_age_us=0, reproduction_cooldown_us=1000))
    w.step()
    b = w.bodies[0]
    # Controlled engineering receipt, explicitly accounted as external nutrient.
    b.storage += 500
    w.totals["food_consumed"] += 500
    w.totals["environment_food"] += 500
    w.time_us = 1000000
    w.engines[0].advance_to(w.time_us)
    before = w.engines[0].capture_state()
    w._reproduce()
    assert w.totals["births"] == 1
    assert w.engines[0].capture_state().digest == before.digest
    e = w.engines[1].metrics()["energy"]
    assert e["initial_total"] == 0 and e["supplied_total"] == w.p.child_energy
    assert e["reserve"] == w.p.child_energy
    assert abs(w.metrics()["energy_balance_error"]) < 1e-7
    assert zero_energy_birth(before).to_dict()["energy"]["reserve"] == 0


def test_engulfing_requires_whole_body_and_dwell_loses_energy_and_keeps_brain():
    w = Ocean(protocol(founders=2, predation=True, reproduction=False))
    w.step()
    w.bodies[0].radius = 0.016
    w.bodies[1].radius = 0.008
    w.bodies[0].position = [0.1, 0.1]
    w.bodies[1].position = [0.117, 0.1]  # Touch/overlap is not enclosure.
    w._predation([0, 1])
    assert not w.engulf
    w.bodies[1].position = [0.1, 0.1]
    w._predation([0, 1])
    assert w.bodies[1].physical
    w.bodies[1].storage += 10
    w.totals["food_consumed"] += 10
    w.totals["environment_food"] += 10
    before = w.bodies[0].storage
    prey = w.bodies[1].storage
    w.time_us += w.p.engulf_dwell_us
    w._predation([0, 1])
    assert not w.bodies[1].physical and w.bodies[1].consumed_by == 0
    assert w.bodies[0].storage == pytest.approx(before + prey * 0.6)
    assert w.totals["predation_heat"] == pytest.approx(prey * 0.4)
    assert w.engines[1].life == "active"  # No fabricated consciousness death.


def test_inertia_drag_no_force_neutral_buoyancy_and_passive_sensing():
    w = Ocean(protocol(founders=1, mode="passive", nutrient_initial=0, reproduction=False))
    b = w.bodies[0]
    b.velocity = [0.03, 0]
    before = b.velocity[0] - w.p.flow_m_s
    w._move(b, [0, 0, 0])
    ratio = math.exp(
        -(6 * math.pi * w.p.viscosity * b.radius) / (w.p.density * 4 * math.pi * b.radius**3 / 3) * w.p.physics_us / 1e6
    )
    assert b.velocity[0] - w.p.flow_m_s == pytest.approx(before * ratio)
    assert w.action(0) == [0, 0, 0]
    channels, raw = w.senses(0)
    assert raw[1:5] == [0, 0, 0, 0] and len(channels) == len({c for c, _ in channels})


def test_reference_native_ocean_matches_and_mutations_do_not_modify_core_parameters():
    p = protocol(founders=1, nutrient_initial=2, reproduction=False)
    a, b = Ocean(p), Ocean(p, backend="reference")
    for _ in range(30):
        a.step()
        b.step()
    x, y = a.capture(), b.capture()
    x.pop("core_hashes")
    y.pop("core_hashes")
    assert x == y

    def compare(u, v):
        if isinstance(u, dict):
            assert u.keys() == v.keys()
            for k in u:
                compare(u[k], v[k])
        elif isinstance(u, list):
            assert len(u) == len(v)
            for m, n in zip(u, v):
                compare(m, n)
        elif isinstance(u, float):
            assert u == pytest.approx(v, rel=1e-12, abs=1e-14)
        else:
            assert u == v

    compare(a.engines[0].capture_state().to_dict(), b.engines[0].capture_state().to_dict())
    assert a.engines[0].config.to_dict() == b.engines[0].config.to_dict()
    for change in (
        {"period_us": 21000},
        {"initial_energy": -1},
        {"mode": "seek_food"},
        {"core_overrides": {"energy_simulation_enabled": False}},
    ):
        with pytest.raises(ValueError):
            OceanProtocol(**change)


def test_blank_comparison_preserves_receptor_and_motor_identities():
    w = Ocean(protocol(founders=1, reproduction=False))
    for _ in range(30):
        w.step()
    original = w.engines[0].capture_state()
    clean = naive_same_receptors(original)
    assert clean.digest != original.digest
    before, after = original.to_dict(), clean.to_dict()
    assert [(n["id"], n["channel"]) for n in before["nodes"]] == [(n["id"], n["channel"]) for n in after["nodes"]]
    assert not after["edges"]
    assert all(n["touches"] == n["support"] == n["stability"] == n["activation"] == 0 for n in after["nodes"])
    assert all(n["local_plasticity"] == 1 for n in after["nodes"])
    assert w.engines[0].capture_state().digest == original.digest


def test_full_cli_record_replay_and_paused_snapshot(tmp_path):
    from lab.tools.ocean_cli import load_population, run, verify

    world = Ocean(protocol(founders=1, reproduction=False))
    result = run(world, tmp_path / "case", 400000, wall_seconds=30)
    assert result["status"] == "horizon_paused" and result["members"][0]["life"] == "active"
    verified = verify(tmp_path / "case")
    assert verified["complete"] and verified["matched"] and verified["steps"] == 20
    resumed = load_population(tmp_path / "case/final")
    resumed.step()
    world.step()
    assert resumed.capture() == world.capture()


def test_mutation_changes_body_only_and_population_cap_is_not_a_death():
    w = Ocean(
        protocol(
            founders=1, population_limit=2, mutation_sigma=0.15, reproduction_age_us=0, reproduction_cooldown_us=1000
        )
    )
    w.step()
    w.bodies[0].storage = 900
    w.time_us = 1000000
    w.engines[0].advance_to(w.time_us)
    w._reproduce()
    parent, child = w.bodies[0], w.bodies[1]
    assert (parent.radius, parent.thrust, parent.sensor_range) != (child.radius, child.thrust, child.sensor_range)
    a, b = w.engines[0].config.to_dict(), w.engines[1].config.to_dict()
    a.pop("energy_initial_reserve")
    b.pop("energy_initial_reserve")
    assert a == b
    before = w.engines[0].capture_state().digest
    w.time_us += w.p.reproduction_interval_us
    w._reproduce()
    assert w.totals["deferred_births"] > 0
    assert w.engines[0].capture_state().digest == before


def test_viewer_follows_saved_continuation_and_rejects_escape(tmp_path):
    import json

    from lab.tools.ocean_cli import load_population, run, write_json
    from lab.tools.ocean_view import create, recorded_segments

    world = Ocean(protocol(founders=1, reproduction=False))
    folder = tmp_path / "case"
    run(world, folder, 100000, wall_seconds=30)
    resumed = load_population(folder / "final")
    run(resumed, folder / "continuations/01", 100000, wall_seconds=30)
    write_json(folder / "completion.json", {"segment": "continuations/01"})
    create(folder, tmp_path / "view.html")
    html = (tmp_path / "view.html").read_text(encoding="utf-8")
    payload = json.loads(html.split("const data=", 1)[1].split("; const slider=", 1)[0])
    assert [r["t"] for r in payload["frames"]] == [0.0, 0.1, 0.2]
    assert payload["frames"][-1]["b"][0]["life"] == "active"
    (folder / "completion.json").write_text(json.dumps({"segment": "../outside"}), encoding="utf-8")
    with pytest.raises(ValueError, match="continuation"):
        recorded_segments(folder)
