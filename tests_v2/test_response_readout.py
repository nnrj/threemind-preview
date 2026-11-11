import copy
import json

import pytest
from test_target_observation import record

from threemind_runtime.observation_cli import main
from threemind_runtime.observation_tools import analyze_responses, analyze_targets, run_tool


def read(vectors, times=None, **options):
    return analyze_responses(record(vectors, times), **options)


def test_one_sample_is_a_response_without_inventing_duration_or_competition():
    r = read([{}, {1: 0.2, 2: 0.1}, {}], node_ids=[1, 2])
    assert r["status"] == "response_observed"
    e = r["events"][r["strongest_event_index"]]
    assert e["time_us"] == "100000"
    assert e["ranking"] == [{"node_id": 1, "activation": 0.2}, {"node_id": 2, "activation": 0.1}]
    assert e["episode_sample_count"] == 1
    assert "observed_peak" in e["reasons"]
    assert r["episodes"][0]["observed_span_us"] == "0"
    assert not r["episodes"][0]["duration_resolved"]
    assert r["episodes"][0]["end_observed_us"] == "200000"
    old = analyze_targets(record([{}, {1: 0.2, 2: 0.1}, {}]), node_ids=[1, 2])
    assert old["first_pattern_convergence"] is None


def test_multiple_peaks_and_equal_total_leader_changes_are_retained():
    r = read([{}, {1: 0.3, 2: 0.1}, {1: 0.1, 2: 0.3}, {2: 0.1}, {1: 0.4}, {}])
    assert len(r["episodes"]) == 1
    assert [e["time_us"] for e in r["events"] if "observed_peak" in e["reasons"]] == ["100000", "400000"]
    switch = next(e for e in r["events"] if e["time_us"] == "200000")
    assert switch["leader_ids"] == [2]
    assert "leader_change" in switch["reasons"]
    assert switch["ranking"][1] == {"node_id": 1, "activation": 0.1}  # Not node 1's .4 peak.


def test_ties_flat_plateau_and_window_boundary_have_no_manufactured_winner():
    r = read([{1: 0.2, 2: 0.2}] * 5)
    assert r["events"][0]["leader_ids"] == [1, 2]
    assert r["events"][0]["lead_margin"] == 0
    assert "observed_peak" not in r["events"][0]["reasons"]
    assert r["episodes"][0]["left_censored"] and r["episodes"][0]["right_censored"]


def test_missing_interval_does_not_become_continuous_activity_or_a_peak():
    r = read([{}, {1: 0.3}, {1: 0.2}, {}], [0, 100000, 900000, 1000000])
    assert r["sampling_gap_count"] == 1
    assert r["episode_count"] == 2
    assert r["episodes"][0]["end_reason"] == "sampling_gap"
    assert r["episodes"][1]["left_censored"]
    assert not any("observed_peak" in e["reasons"] for e in r["events"])


def test_entry_and_exit_can_be_missing_without_losing_observed_response():
    r = read([{1: 0.01}])
    assert r["status"] == "response_observed"
    assert r["events"][0]["reasons"] == ["already_active", "episode_maximum"]
    assert r["episodes"][0]["end_observed_us"] is None
    assert read([{}, {}])["status"] == "no_active_sample"
    assert read([])["status"] == "not_observed"


def test_tolerance_never_erases_raw_measurements():
    r = read([{1: 1e-15}])
    assert r["raw_activity_seen"] and r["timeline"][0]["activation_total"] == 1e-15
    assert r["status"] == "no_active_sample"
    assert read([{1: 1e-15}], epsilon=0)["status"] == "response_observed"


def test_explicit_selection_ignores_background_without_changing_source():
    source = record([{}, {1: 0.001, 2: 0.002, 9: 0.9}, {}, {9: 0.8}])
    source["annotations"] = {"1": ["A"], "2": ["B"], "9": ["background"]}
    original = copy.deepcopy(source)
    r = analyze_responses(source, node_ids=[1, 2])
    assert r["events"][0]["ranking"][0]["node_id"] == 2
    assert source == original
    source["annotations"] = {"1": ["renamed"], "2": ["irrelevant"]}
    assert analyze_responses(source, node_ids=[1, 2])["events"] == r["events"]
    assert r["original_classification"] == "unresolved"
    assert run_tool("response", {"record": original}, {"node_ids": [1, 2]}) == r


@pytest.mark.parametrize("ids", [[], [1, 1], [True], [1.1], [999999]])
def test_invalid_selection_is_not_silent_zero(ids):
    with pytest.raises(ValueError):
        read([{1: 0.1}], node_ids=ids)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True])
def test_invalid_tolerance(value):
    with pytest.raises(ValueError):
        read([{1: 0.1}], epsilon=value)


def test_cli_outputs_new_artifact_without_touching_source(tmp_path):
    source, out = tmp_path / "record.json", tmp_path / "response.jsonl"
    source.write_text(json.dumps(record([{1: 0.1}, {}])), encoding="utf-8")
    before = source.read_bytes()
    main(["response", "--input", str(source), "--output", str(out), "--node-ids", "1"])
    assert json.loads(out.read_text())["result"]["events"][0]["ranking"][0]["activation"] == 0.1
    assert source.read_bytes() == before
    with pytest.raises(SystemExit):
        main(["response", "--input", str(source), "--output", str(out)])
