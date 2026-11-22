"""Artificial fixtures run before scientific world time zero."""

import math
import uuid

from p2_paths import CONTROL, SECOND

# isort: split
from execution import checked_metrics, encoded, snapshot
from p2_habitat import CARE_TIME, NEWBORN_RADIUS, make_world
from p2_io import restore, state_bytes, world_fingerprint


def set_store(world, b, value):
    world.totals["initial_body"] += value - b.storage
    b.storage = value


def funded_parent():
    w = make_world(
        0,
        8,
        founders=1,
        nutrient_initial=0,
        reproduction_age_us=20000,
        reproduction_cooldown_us=20000,
        reproduction_interval_us=20000,
    )
    b = w.bodies[0]
    assert b.radius == NEWBORN_RADIUS
    w.grow(b)
    assert b.radius == NEWBORN_RADIUS
    set_store(w, b, 3000)
    radius, paid = b.radius, w.construction_paid[0]
    w.grow(b)
    assert b.radius > radius and w.construction_paid[0] > paid
    for _ in range(130):
        w.grow(b)
    assert math.isclose(b.radius, w.adult_radii[0])
    set_store(w, b, w.p.parent_retained_food + 500)
    w.step()
    assert not w.totals["births"]
    set_store(w, b, 5000)
    for _ in range(5):
        events = w.step()
        births = [e for e in events if e["kind"] == "birth"]
        if births:
            break
    assert len(births) == 3 and len({e["time_us"] for e in births}) == 1
    bill = births[0]["litter_bill"]
    assert bill < 4549.42 and math.isclose(births[0]["parent_before"] - births[0]["parent_after"], bill)
    for i in range(1, 4):
        assert w.bodies[i].radius <= min(NEWBORN_RADIUS, b.radius / 2)
        assert w._protected_pair(i, 0, w.time_us)
        for j in range(i):
            assert w.geometry(i, j)[0] > 0 and w._protected_pair(i, j, w.time_us)
    checked_metrics(w)
    return w, bill


def check():
    CONTROL.mkdir(parents=True, exist_ok=True)
    folder = CONTROL / ("qualification-" + uuid.uuid4().hex)
    folder.mkdir()
    w, bill = funded_parent()
    children = [1, 2, 3]
    before = w.bodies[0].storage
    w._predation([0, *children])
    assert not any(e["kind"] == "nursing_contact" for e in w.events) and w.bodies[0].storage == before
    parent = w.bodies[0]
    set_store(w, parent, w.p.parent_retained_food + 0.03)
    for child in children:
        w.bodies[child].position = parent.position.copy()
    w._predation([0, *children])
    nursed = [e for e in w.events if e["kind"] == "nursing_contact"]
    assert len(nursed) == 3 and all(math.isclose(e["received"], 0.01, abs_tol=1e-10) for e in nursed)
    limited_amounts = [e["received"] for e in nursed]
    assert math.isclose(parent.storage, w.p.parent_retained_food, abs_tol=1e-10)
    w.events = []
    set_store(w, parent, w.p.parent_retained_food + 100)
    for child in children:
        w.bodies[child].position = parent.position.copy()
    w._predation([0, *children])
    nursed = [e for e in w.events if e["kind"] == "nursing_contact"]
    assert len(nursed) == 3 and all(e["received"] == 0.02 for e in nursed)
    checked_metrics(w)
    w.events = []
    for child in children:
        w.bodies[child].birth_us = w.time_us - CARE_TIME
        w.bodies[child].position = parent.position.copy()
    w._predation([0, *children])
    assert not any(e["kind"] == "nursing_contact" for e in w.events) and not w.totals["predations"]
    # Resume a real paid litter (including the inherited native Core) on the same next tick.
    w, _ = funded_parent()
    snapshot(w, folder / "litter.zip")
    loaded = restore(folder / "litter.zip")
    assert encoded(w.step()) == encoded(loaded.step()) and state_bytes(w.capture()) == state_bytes(loaded.capture())
    for i in w.engines:
        assert w.engines[i].capture_state().payload == loaded.engines[i].capture_state().payload

    kin = make_world(0, 8, founders=8, nutrient_initial=0)
    for b, parent_id in zip(kin.bodies.values(), (None, 0, 1, 2, 3, 0, 5, None)):
        b.parent = parent_id
        kin.remember_family(b)
    assert kin._protected_pair(0, 3, 0) and kin._protected_pair(3, 6, 0)
    assert not kin._protected_pair(0, 4, 0) and not kin._protected_pair(3, 7, 0)
    for i in (0, 4):
        kin.bodies[i].position = [0.2, 0.2]
    kin._predation([0, 4])
    assert kin.bodies[4].physical  # equal size
    set_store(kin, kin.bodies[0], 200)
    kin.grow(kin.bodies[0])
    kin.bodies[4].position = kin.bodies[0].position.copy()
    kin._predation([0, 4])
    assert kin.bodies[4].consumed_by == 0 and kin.totals["predations"] == 1
    checked_metrics(kin)

    matched = []
    for block in range(2):
        a, b = make_world(block, 1), make_world(block, 8)
        assert (
            world_fingerprint(a) == world_fingerprint(b) and a.next_food_us == SECOND and b.next_food_us == 8 * SECOND
        )
        for i in a.engines:
            assert a.engines[i].capture_state().payload == b.engines[i].capture_state().payload
        matched.append(world_fingerprint(a))
        if block == 0:
            snapshot(a, folder / "founders.zip")
            loaded = restore(folder / "founders.zip")
            assert encoded(a.step()) == encoded(loaded.step()) and state_bytes(a.capture()) == state_bytes(
                loaded.capture()
            )
        checked_metrics(a)
    assert matched[0] != matched[1]

    # A single blank juvenile with no food, parent or experimental energy input.
    juvenile = make_world(0, 2400, founders=1, nutrient_initial=0)
    for _ in range(1500):
        juvenile.step()
    assert juvenile.time_us == CARE_TIME and juvenile.bodies[0].physical
    error = checked_metrics(juvenile)["energy_balance_error"]
    from unittest.mock import patch

    import p2_io
    from p2_analysis import analyze
    from p2_report import report

    data = folder / "short-run"
    data.mkdir()
    (data / "analysis").mkdir()

    class TemporaryVolume:
        def guard(self, *args, **kwargs):
            return data

    def short_world(block, interval):
        return make_world(block, interval, founders=3, nutrient_initial=4)

    with (
        patch.object(p2_io, "pool", return_value=TemporaryVolume()),
        patch.object(p2_io, "guard"),
        patch.object(p2_io, "make_world", short_world),
        patch.object(p2_io, "HORIZON", 7),
    ):
        for block in (0, 1):
            for arm, interval in (("reference", 1), ("sparse", 8)):
                p2_io.run_case(data, block, arm, interval)
    analysis = analyze(data)
    assert all(c["seconds"] == 7 for c in analysis["cases"].values())
    assert "OCEAN63-P2" in report(analysis, "zh") and "OCEAN63-P2" in report(analysis, "en")
    return {
        "paired_world_fingerprints": matched,
        "native_core_and_next_tick_verified": True,
        "sealed_and_analyzed_four_short_worlds": True,
        "litter_size": 3,
        "example_litter_bill": bill,
        "positive_growth_paid": True,
        "separated_births": True,
        "kin_boundary_verified": True,
        "equal_size_survived": True,
        "shared_care_under_floor_pressure": limited_amounts,
        "contact_full_rate_per_tick": [e["received"] for e in nursed],
        "full_30s_without_food_alive": True,
        "juvenile_core_life": juvenile.engines[0].life,
        "balance_at_30s": error,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(check(), indent=2))
