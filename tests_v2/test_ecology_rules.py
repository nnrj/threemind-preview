import copy
import math

import pytest

from threemind_runtime.ecology_rules import EcologyLedger, EcologyRules, distribute


def rules(**changes):
    value = EcologyRules().model_dump(mode="json")
    for key, item in changes.items():
        value[key] = value[key] | item if isinstance(item, dict) else item
    return value


def observed(ledger, **changes):
    return {key: {"position": [0, 0, 0.15]} | changes for key, body in ledger.accounts.items() if body.alive}


def test_allocations_obey_demands_and_explicit_rules():
    demand = {"a": 0.1, "b": 0.9}
    assert distribute(demand, 0.5, "equal") == pytest.approx({"a": 0.1, "b": 0.4})
    assert distribute(demand, 0.5, "demand") == pytest.approx({"a": 0.05, "b": 0.45})
    assert distribute(demand, 0.5, "nearest", {"a": 2, "b": 1}) == {"a": 0.0, "b": 0.5}
    for mode in ("equal", "demand", "nearest"):
        assert distribute(demand, 3, mode, {"a": 2, "b": 1}) == demand
        assert math.fsum(distribute(demand, 0, mode, {"a": 2, "b": 1}).values()) == 0
    for bad in (float("nan"), float("inf"), -1):
        with pytest.raises(ValueError, match="finite"):
            distribute({"a": bad}, 1, "equal")
    with pytest.raises(ValueError, match="unknown"):
        distribute({}, 0, "implicit fitness")
    with pytest.raises(ValueError, match="distances"):
        distribute(demand, 1, "nearest")


@pytest.mark.parametrize("habitat,per_body,total_supply", [("shared", 0.5, 9), ("independent", 1, 10)])
def test_shared_competition_and_independent_supply_are_distinct(habitat, per_body, total_supply):
    spec = rules(
        habitat=habitat,
        patches=[{"id": "food", "initial": 1, "regeneration_per_s": 0}],
        uptake_per_s=2,
        maintenance_per_s=0,
        reproduction={"enabled": False},
    )
    ledger = EcologyLedger(spec, 3, 1000000)
    events = ledger.step(observed(ledger))
    assert all(body.reserve == 4 + per_body for body in ledger.accounts.values())
    assert ledger.check_balance() == {
        "initial_external": total_supply,
        "regenerated": 0,
        "remaining": total_supply,
        "spent": 0,
    }
    assert sum(sum(e["amounts"].values()) for e in events) == 2 * per_body
    assert all(pool["food"] == 0 for pool in ledger.pools.values())


def test_coaccess_is_actual_local_population_not_a_cooperation_label():
    base = rules(
        patches=[{"id": "food", "minimum_gatherers": 2}],
        maintenance_per_s=0,
        reproduction={"enabled": False},
    )
    shared = EcologyLedger(base, 1, 1000000)
    independent = EcologyLedger(base | {"habitat": "independent"}, 1, 1000000)
    near = observed(shared)
    far = near | {"n1": {"position": [10, 0, 0]}}
    assert shared.step(far) == []
    assert independent.step(near) == []
    assert shared.step(near)[0]["amounts"] == {"n0": 1, "n1": 1}
    assert all(a.reserve == 4 for a in independent.accounts.values())


@pytest.mark.parametrize("habitat", ["shared", "independent"])
def test_births_transfer_parent_resources_and_caps_defer_without_killing(habitat):
    spec = rules(
        habitat=habitat,
        uptake_per_s=0,
        maintenance_per_s=0,
        reproduction={"minimum_age_us": 0, "threshold": 4, "offspring_reserve": 1, "population_limit": 3},
    )
    ledger = EcologyLedger(spec, 7, 1000000)
    events = ledger.step(observed(ledger))
    birth = next(e for e in events if e["kind"] == "birth_due")
    assert birth["model_born"] is False  # Policy cannot claim it instantiated a brain.
    assert birth["inheritance_rule"] == "threemind.birth/1"
    assert birth["new_habitat_external_supply"] == (20 if habitat == "independent" else 0)
    assert ledger.accounts[birth["parent"]].reserve == 2.5
    assert ledger.accounts["n2"].reserve == 1
    assert ledger.accounts["n2"].parent_id == birth["parent"]
    assert ledger.reproduction_spent == 0.5
    assert ledger.deferred_population == 1 and all(a.alive for a in ledger.accounts.values())
    resumed = EcologyLedger(spec, 7, 1000000, state=ledger.snapshot())
    assert ledger.step(observed(ledger)) == resumed.step(observed(resumed))
    assert ledger.snapshot() == resumed.snapshot()
    exhausted = EcologyLedger(spec | {"reproduction": spec["reproduction"] | {"offspring_limit": 0}}, 7, 1000000)
    assert {e["reason"] for e in exhausted.step(observed(exhausted))} == {"offspring_budget"}
    assert all(a.alive and a.reserve == 4 for a in exhausted.accounts.values())


def test_exhaustion_and_damage_are_body_failures_without_inventing_core_death():
    spec = rules(patches=[], founder_reserve=0.01, maintenance_per_s=0.1, reproduction={"enabled": False})
    ledger = EcologyLedger(spec, 11, 1000000)
    events = ledger.step(observed(ledger))
    assert len(events) == 2 and all(e["kind"] == "body_failed" for e in events)
    assert all(not e["core_death_observed"] and e["reason"] == "resource_exhaustion" for e in events)
    assert ledger.maintenance_spent == 0.02 and ledger.check_balance()["remaining"] == 0
    with pytest.raises(ValueError, match="actual physical"):
        ledger.step({"n0": {"position": [0, 0, 0]}})
    assert ledger.step({}) == []
    severe = rules(patches=[], maintenance_per_s=0, damage_per_force_s=1e6, reproduction={"enabled": False})
    ledger = EcologyLedger(severe, 1, 1000000, founders=1)
    events = ledger.step(observed(ledger, contact_force=1e6))
    assert events[-1]["reason"] == "damage" and ledger.accounts["n0"].reserve == 4
    assert ledger.accounts["n0"].damage > 1e6
    assert EcologyLedger(severe, 1, 1000000, founders=1, state=ledger.snapshot()).snapshot() == ledger.snapshot()


@pytest.mark.parametrize("habitat", ["shared", "independent"])
def test_resume_preserves_rules_physical_history_and_resource_balance(habitat):
    spec = rules(habitat=habitat, reproduction={"population_limit": 8, "cooldown_us": 2000000})
    ledger = EcologyLedger(spec, 19, 20000)
    for _ in range(150):
        ledger.step(observed(ledger, effort=0.25))
    saved = ledger.snapshot()
    saved["accounts"].reverse()  # Serialization order does not change mechanics.
    renamed = copy.deepcopy(spec)
    renamed["patches"][0]["label"] = "观察者认为有益，但这只是名称"
    resumed = EcologyLedger(renamed, 19, 20000, state=saved)
    assert ledger.snapshot() == resumed.snapshot()
    for _ in range(450):
        assert ledger.step(observed(ledger, effort=0.5)) == resumed.step(observed(resumed, effort=0.5))
    assert ledger.snapshot() == resumed.snapshot()
    assert len(ledger.accounts) > ledger.founder_count
    assert ledger.check_balance()["regenerated"] > 0
    changed = copy.deepcopy(spec)
    changed["allocation"] = "nearest"
    with pytest.raises(ValueError, match="continuation"):
        EcologyLedger(changed, 19, 20000, state=saved)


def test_rejected_measurements_do_not_advance_and_invalid_snapshots_fail_closed():
    spec = rules()
    ledger = EcologyLedger(spec, 2, 20000)
    saved = ledger.snapshot()
    for value in ({}, observed(ledger, effort=float("nan")), observed(ledger, position=[True, 0, 0])):
        with pytest.raises(ValueError):
            ledger.step(value)
        assert ledger.snapshot() == saved
    for patch in (
        {"time_us": 1},
        {"next_reproduction_us": 3000000},
        {"external_initial": 99},
        {"accounts": saved["accounts"][:1]},
        {"reproduction_spent": 1},
        {"accounts": [saved["accounts"][0] | {"last_reproduction_us": 0}, saved["accounts"][1]]},
    ):
        with pytest.raises(ValueError):
            EcologyLedger(spec, 2, 20000, state=saved | patch)
    large = EcologyLedger(rules(reserve_capacity=1e6, founder_reserve=1e6), 2, 20000, founders=4)
    assert large.snapshot()["external_initial"] > 1e6  # Cumulative totals are not per-body capacities.


def test_protocol_rejects_inconsistent_limits_and_non_numeric_switches():
    for changes in (
        {"reserve_capacity": 1},
        {"reproduction": {"threshold": 1}},
        {"patches": [{"id": "food", "initial": 10, "capacity": 1}]},
        {"patches": [{"id": "food"}, {"id": "food"}]},
        {"maintenance_per_s": True},
        {"habitat": "pretend shared"},
    ):
        with pytest.raises(ValueError):
            EcologyLedger(rules(**changes), 2, 20000)
    with pytest.raises(ValueError, match="interval"):
        EcologyLedger(rules(), 2, 21000)


def test_reproduction_waits_for_parent_state_at_the_actual_delivery_boundary():
    spec = rules(
        uptake_per_s=0, maintenance_per_s=0, reproduction={"threshold": 4, "minimum_age_us": 0, "population_limit": 3}
    )
    ledger = EcologyLedger(spec, 7, 1000000)
    assert ledger.step(observed(ledger), reproduce=False) == []
    assert len(ledger.accounts) == 2 and ledger.pending_reproduction_us == 1000000
    saved = ledger.snapshot()
    with pytest.raises(ValueError, match="pending"):
        ledger.step(observed(ledger))
    resumed = EcologyLedger(spec, 7, 1000000, state=saved)
    assert ledger.finish_boundary({"n0"}) == resumed.finish_boundary({"n0"})
    assert ledger.accounts["n2"].parent_id == "n0"
    assert ledger.snapshot() == resumed.snapshot()
    assert ledger.finish_boundary({"n0"}) == []  # Acknowledgment cannot charge a second birth.
    assert ledger.pending_reproduction_us is None
    control = spec | {"reproduction": spec["reproduction"] | {"parent_state": "body_only"}}
    body_only = EcologyLedger(control, 7, 1000000)
    body_only.step(observed(body_only), reproduce=False)
    assert any(e["kind"] == "birth_due" for e in body_only.finish_boundary(set()))
