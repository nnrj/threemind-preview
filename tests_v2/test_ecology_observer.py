from copy import deepcopy

import pytest

from threemind_runtime.ecology_observer import (
    ObserverConfig,
    WarningRule,
    describe_checkpoint,
    describe_event,
    evaluate_rules,
)


def configured(**rule):
    return ObserverConfig(enabled=True, rules=[WarningRule(id="body-test", **rule)])


def sample(at, failed=1):
    return {"individuals": 2, "body_failures": failed, "model_time_us": str(at), "physical_time_us": str(at)}


def codes(entries):
    return [entry["code"] for entry in entries]


def test_sampled_duration_cooldown_clearance_and_missing_intervals():
    config = configured(hold_us=100, cooldown_us=100, maximum_gap_us=200)
    events, state = evaluate_rules(config, sample(0), {}, {})
    assert not events and state["body-test"]["status"] == "pending"
    events, state = evaluate_rules(config, sample(99), state, {})
    assert not events
    events, state = evaluate_rules(config, sample(100), state, {})
    assert codes(events) == ["triggered"]
    assert events[0]["facts"]["sampled_only"]
    events, state = evaluate_rules(config, sample(100), state, {})
    assert not events  # Polling the same time cannot accumulate duration or repeats.
    events, state = evaluate_rules(config, sample(200), state, {})
    assert codes(events) == ["reminder"]
    events, state = evaluate_rules(config, sample(250, 0), state, {})
    assert codes(events) == ["cleared"]
    events, state = evaluate_rules(config, sample(251), state, {})
    assert not events
    events, state = evaluate_rules(config, sample(451), state, {})
    assert codes(events) == ["triggered"]
    events, state = evaluate_rules(config, sample(652), state, {})
    assert codes(events) == ["coverage_gap"] and state["body-test"]["status"] == "pending"
    events, state = evaluate_rules(config, sample(752), state, {})
    assert codes(events) == ["triggered"]
    events, state = evaluate_rules(config, sample(753, None), state, {})
    assert codes(events) == ["missing_evidence"] and state["body-test"]["status"] == "missing"
    events, state = evaluate_rules(config, sample(754, 0), state, {})
    assert codes(events) == ["coverage_resumed"]  # Not a false clearance across a gap.


def test_observer_inputs_are_immutable_and_clocks_are_not_interchangeable():
    config = ObserverConfig(
        enabled=True,
        rules=[
            WarningRule(id="body", metric="living_bodies", hold_us=100),
            WarningRule(id="core", metric="viable_cores", hold_us=100),
        ],
    )
    population = {"living_bodies": 1, "viable_cores": 1, "model_time_us": "0", "physical_time_us": "0"}
    source = {"checkpoint_id": "example", "checkpoint_hash": "hash"}
    original = deepcopy((population, source))
    events, state = evaluate_rules(config, population, {}, source)
    assert not events
    previous = deepcopy(state)
    population2 = population | {"model_time_us": "50", "physical_time_us": "100"}
    events, _ = evaluate_rules(config, population2, state, source)
    assert [entry["rule_id"] for entry in events] == ["body"]
    assert state == previous and (population, source) == original
    events[0]["source"].clear()
    assert source == original[1]
    with pytest.raises(ValueError, match="backwards"):
        evaluate_rules(
            config, population | {"model_time_us": "-1", "physical_time_us": "0"}, {"body": {"last_us": "10"}}, source
        )
    _, missing = evaluate_rules(config, population | {"physical_time_us": None}, {"body": {"last_us": "10"}}, source)
    assert missing["body"]["last_us"] == "10"
    with pytest.raises(ValueError, match="backwards"):
        evaluate_rules(config, population, missing, source)


def test_unknown_events_and_task_end_are_not_fabricated_interpretations():
    event = {"kind": "unrecognized_future_kind", "time_us": "123", "measurement": 0.7}
    result = describe_event(event, {"event_id": "7"})
    assert "没有" not in result["text"]["zh"] and result["facts"] == event
    result["facts"]["measurement"] = 99
    assert event["measurement"] == 0.7
    summary = describe_checkpoint({}, "completed", {})
    assert "?" in summary["text"]["zh"] and "死亡" in summary["text"]["zh"]
    assert summary["facts"]["living_bodies"] is None
    assert evaluate_rules(ObserverConfig(), sample(0), {}, {}) == ([], {})
    for invalid in (
        {"enabled": "false"},
        {"rules": [{"id": "a"}, {"id": "a"}]},
        {"rules": [{"id": "a", "metric": "hostility"}]},
    ):
        with pytest.raises(ValueError):
            ObserverConfig(**invalid)
