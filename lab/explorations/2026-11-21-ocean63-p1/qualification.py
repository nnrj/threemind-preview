"""Engineering fixtures. These worlds never enter the scientific results."""

import tempfile
from pathlib import Path


from paths import CONTROL, SECOND
from execution import checked_metrics, encoded, snapshot
from habitat import extent, make_world
from worldio import restore, world_fingerprint
from turns import EncounterTurns


def fixture(**kwargs):
    return make_world(0, 8, founders=2, nutrient_initial=0, **kwargs)


def test_habitat():
    reference = make_world(0, 1)
    sparse = make_world(0, 8)
    assert world_fingerprint(reference) == world_fingerprint(sparse)
    assert reference.next_food_us == SECOND and sparse.next_food_us == 8 * SECOND
    w = fixture()
    hunter, prey = sorted(w.bodies.values(), key=lambda b: -b.radius)
    hunter.position = [0.1, 0.1]
    hunter.angle = prey.angle = 0
    reach = extent(hunter.radius, hunter.elongation) + extent(prey.radius, prey.elongation)
    prey.position = [0.1 + reach + 0.00001, 0.1]
    w._predation(sorted(w.bodies))
    assert prey.physical
    # A juvenile relative and an empty hunter remain eligible on first actual contact.
    prey.parent = hunter.id
    w.totals["body_heat"] += hunter.storage
    hunter.storage = 0.0
    prey.position = [0.1 + reach - 0.000001, 0.1]
    w._predation(sorted(w.bodies))
    e = next(ev for ev in w.events if ev["kind"] == "body_engulfed")
    assert e["individual"] == prey.id and e["hunter_volume"] > e["prey_volume"] and not prey.physical
    w._predation([hunter.id])
    assert w.totals["predations"] == 1
    checked_metrics(w)
    equal = fixture()
    a, b = equal.bodies.values()
    b.radius = a.radius
    b.position = a.position[:]
    b.angle = a.angle
    equal._predation([a.id, b.id])
    assert a.physical and b.physical
    w = fixture(reproduction_age_us=20_000, reproduction_cooldown_us=20_000, reproduction_interval_us=20_000)
    parent = w.bodies[0]
    other = w.bodies[1]
    parent.position = [0.15, 0.15]
    other.position = [0.8, 0.8]
    w.totals["initial_body"] += 9000
    parent.storage += 9000
    for _ in range(5):
        events = w.step()
        twins = [e for e in events if e["kind"] == "birth" and e["parent"] == 0]
        if twins:
            break
    assert len(twins) == 2 and twins[0]["time_us"] == twins[1]["time_us"]
    assert all(e["generation"] == 1 and e["litter_size"] == 2 for e in twins)
    ids = [e["individual"] for e in twins]
    assert all(w.geometry(0, i)[0] > 0 for i in ids) and w.geometry(*ids)[0] > 0
    checked_metrics(w)
    CONTROL.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=CONTROL) as folder:
        path = Path(folder) / "twins.zip"
        snapshot(w, path)
        restored = restore(path)
        assert encoded(w.step()) == encoded(restored.step())
        assert encoded(w.capture()) == encoded(restored.capture())
    return {
        "initial_pair_identical": True,
        "strict_size_first_contact": True,
        "equal_size_survived": True,
        "unfunded_and_related_hunter": True,
        "funded_twins": True,
        "separated_at_birth": True,
        "same_next_tick_after_restore": True,
        "energy_error": checked_metrics(w)["energy_balance_error"],
    }


def test_escape():
    bodies = {
        0: dict(radius=0.005, elongation=0, sensor_range=0.025),
        1: dict(radius=0.009, elongation=0, sensor_range=0.025),
    }

    def run(turn):
        obs = EncounterTurns(1.2, bodies)
        for idx in range(31):
            t = idx * 0.2 - 1
            if t <= 0 or not turn:
                x, y = 0.25 + 0.008 * t, 0.4
                vx, vy = 0.008, 0
            else:
                x, y = 0.25, 0.4 + 0.012 * t
                vx, vy = 0, 0.012
            obs.frame((idx + 1) * 200000, [[0, x, y, vx, vy, 0, 1, 0.3, 0], [1, 0.284, 0.4, 0, 0, 0, 0, 0, 0]])
        return obs

    effective = run(True)
    assert len(effective.escape) == 1 and not run(False).escape
    return {"synthetic_turn_and_escape": True, "straight_control": True}


def test_pipeline():
    from unittest.mock import patch
    import worldio
    from outcomes import case_outcome, reproduction, verdict
    from p1_report import scientific_report
    from paths import exclusive_json

    counts = {0: dict(parent=None, birth_us=0, generation=0, radius=0.008)}
    for i in (1, 2):
        counts[i] = dict(parent=0, birth_us=0, generation=1, radius=0.008)
    counts[3] = dict(parent=1, birth_us=61 * SECOND, generation=2, radius=0.008)
    counts[4] = dict(parent=1, birth_us=61 * SECOND, generation=2, radius=0.008)
    r = reproduction(counts, {4: 80 * SECOND}, {1: [3 * SECOND]}, 250 * SECOND, False)
    assert r["adjusted_difference"] == 1 and r["groups"]["other"]["mean"] == 0
    assert verdict([1, None]) == "insufficient" and verdict([1, 0]) == "not_met"

    # The engineering path uses a temporary volume. Only its storage checks
    # and admission are substituted; the recorder, native world and analysis run normally.
    class TemporaryAdmission:
        def guard(self, *args, **kwargs):
            return base

    with tempfile.TemporaryDirectory(dir=CONTROL) as folder:
        base = Path(folder)
        run = base / "world"
        run.mkdir()
        w = fixture()
        snapshot(w, run / "initial.zip")
        with patch.object(worldio, "pool", return_value=TemporaryAdmission()), patch.object(worldio, "guard"):
            worldio.segment(w, run, base, 0, 3 * SECOND)
            worldio.segment(w, run, base, 1, 7 * SECOND)
        saved = worldio.restore_end(run / "seg-0001.zip")
        assert encoded(saved.capture()) == encoded(w.capture())
        m = checked_metrics(w)
        exclusive_json(
            run / "result.json", dict(time_us=w.time_us, extinct=False, members=m["members"], totals=m["totals"])
        )
        report = case_outcome(run)
        assert report["seconds"] == 7 and report["alive"] == 2 and report["change"] is None
        assert report["milestones"][-1]["alive"] == 2 and report["milestones"][-1]["time_us"] == 7 * SECOND
        data = {
            "cases": {"world-0-sparse": report},
            "outcomes": {
                **{
                    k: "insufficient"
                    for k in ("predation_over_generations", "extra_change_under_lower_supply", "surviving_offspring")
                },
                **{k: {"worlds_with_observations": 0} for k in ("escape", "pursuit", "food_turns")},
            },
        }
        assert "OCEAN63-P1" in scientific_report(data, "zh") and "OCEAN63-P1" in scientific_report(data, "en")
    return {
        "segmented_native_recording": True,
        "independent_event_and_state_readback": True,
        "lineage_denominators": True,
    }


if __name__ == "__main__":
    print(test_habitat(), test_escape(), test_pipeline())
