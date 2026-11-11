import copy
import math

import pytest
from pydantic import ValidationError

from threemind_lab.evolution_protocol import (
    EvolutionProtocol,
    SelectionCriterion,
    endpoints,
    rank_candidates,
    seed_plan,
)
from threemind_lab.protocols import RunSpec


def protocol(**changes):
    spec = RunSpec(
        environment="ambient",
        clock="unbounded",
        duration_s=0.03,
        sample_us=10000,
        checkpoint_us=10000,
        ambient_field={"sample_us": 10000},
    )
    return {
        "generations": 2,
        "population_size": 2,
        "survivor_count": 1,
        "development": spec.model_dump(mode="json"),
        "evaluation": spec.model_dump(mode="json"),
        "criteria": [{"metric": "nodes", "direction": "maximize"}],
        **seed_plan(2, 2, 2, 2, 42),
        **changes,
    }


def test_seed_plan_and_protocol_separate_formation_selection_and_final_verification():
    value = EvolutionProtocol(**protocol())
    assert value.inheritance_rule == "threemind.birth/1" and value.selection_mode == "directed"
    assert value.development_seeds == seed_plan(2, 2, 2, 2, 42)["development_seeds"]
    seeds = (
        [seed for generation in value.development_seeds for seed in generation]
        + value.evaluation_seeds
        + value.verification_seeds
    )
    assert len(set(seeds)) == 8
    assert EvolutionProtocol.model_validate_json(value.model_dump_json()) == value


@pytest.mark.parametrize(
    "change",
    [
        {"generations": True},
        {"population_size": 1},
        {"survivor_count": 3},
        {"selection_mode": "ecological"},
        {"inheritance_rule": "random-rewire"},
        {"criteria": []},
        {"criteria": [{"metric": "consciousness", "direction": "maximize"}]},
        {"development_seeds": [[1, 2]]},
        {"development_seeds": [[1, 1], [2, 3]]},
        {"evaluation_seeds": [1, 1]},
        {"verification_seeds": []},
        {"evaluation_seeds": [True]},
    ],
)
def test_invalid_or_unimplemented_rules_are_rejected(change):
    with pytest.raises(ValidationError):
        EvolutionProtocol(**protocol(**change))


def test_identity_and_seed_leakage_are_checked_before_any_run_is_created():
    base = protocol()
    for group, replacement in (
        ("evaluation_seeds", [base["development_seeds"][0][0]]),
        ("verification_seeds", [base["development_seeds"][0][1]]),
        ("verification_seeds", base["evaluation_seeds"]),
    ):
        with pytest.raises(ValidationError):
            EvolutionProtocol(**(base | {group: replacement}))
    for path, value in (
        ("seed", 19),
        ("clock", "realtime"),
        ("environment_seed", 93),
        ("duration_s", "0.1"),
        ("host_telemetry", {"enabled": True}),
        ("config", {"activation_decay": 0.01}),
    ):
        changed = copy.deepcopy(base)
        changed["evaluation"][path] = value
        with pytest.raises((ValidationError, ValueError)):
            EvolutionProtocol(**changed)


def test_declared_objective_priority_direction_and_ties_are_reproducible():
    criteria = [
        SelectionCriterion(metric="nodes", direction="maximize", aggregate="worst"),
        SelectionCriterion(metric="energy_consumed", direction="minimize"),
    ]
    rows = [
        {"slot": slot, "blocks": [{"values": {"nodes": nodes, "energy_consumed": cost}} for nodes, cost in blocks]}
        for slot, blocks in [
            (3, [(5, 4), (6, 6)]),
            (0, [(5, 4), (6, 6)]),
            (1, [(5, 9), (10, 9)]),
            (2, [(4, 0), (100, 0)]),
        ]
    ]
    ranked = rank_candidates(rows, criteria)
    assert [r["slot"] for r in ranked] == [0, 3, 1, 2]
    assert ranked[0]["scores"] == {"nodes": 5, "energy_consumed": 5}
    assert [r["rank"] for r in ranked] == [1, 2, 3, 4]
    assert rank_candidates(list(reversed(rows)), criteria) == ranked
    minimizing = [SelectionCriterion(metric="energy_consumed", direction="minimize", aggregate="worst")]
    assert rank_candidates(rows, minimizing)[0]["slot"] == 2


def test_censoring_and_missing_metrics_are_not_disguised_as_fitness():
    criteria = [SelectionCriterion(metric=k, direction="maximize") for k in ("observed_lifetime_s", "not_dead_at_end")]
    result = endpoints({"life": "alive", "time_us": "1000000", "metrics": {}}, criteria)
    assert result["values"] == {"observed_lifetime_s": 1.0, "not_dead_at_end": 1}
    assert result["lifetime_right_censored"]
    dead = endpoints({"life": "dead", "time_us": "500000", "metrics": {}}, criteria)
    assert dead["values"]["not_dead_at_end"] == 0 and not dead["lifetime_right_censored"]
    criterion = [SelectionCriterion(metric="mean_weight", direction="maximize")]
    for value in (None, math.nan, math.inf, True):
        with pytest.raises(ValueError):
            endpoints({"life": "alive", "time_us": "0", "metrics": {"mean_weight": value}}, criterion)
    with pytest.raises(ValueError):
        rank_candidates([{"slot": 0, "blocks": []}], criterion)
