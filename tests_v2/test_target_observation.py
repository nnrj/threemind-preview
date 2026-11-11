import copy
import json

import pytest

from threemind_runtime.observation_tools import analyze_targets, run_tool
from threemind_runtime.target_observation import target_observation


def record(vectors, times=None):
    times = times or [i * 100000 for i in range(len(vectors))]
    return {
        "kind": "temporal_readout",
        "analysis_schema": "threemind.activity-analysis/2",
        "window_id": "test",
        "configuration": {"interval_us": 100000, "baseline_us": 0},
        "classification": "unresolved",
        "nodes": [{"node_id": i, "baseline_mean": 0} for i in (1, 2, 9)],
        "series": [
            {"time_us": str(t), "activation_vector": {str(k): v for k, v in ns.items()}}
            for t, ns in zip(times, vectors)
        ],
    }


def test_stable_target_in_changing_background_preserves_global_and_source():
    r = record([{1: 0.1, 2: 0.2, 9: 0.9 if i % 2 else 0.1} for i in range(6)])
    original = copy.deepcopy(r)
    result = analyze_targets(r, node_ids=[1, 2], settle_us=200000)
    assert result["original_classification"] == "unresolved"
    assert result["first_steady_convergence"]["time_us"] == "200000"
    assert result["first_steady_convergence"]["ranking"] == [
        {"node_id": 2, "activation": 0.2},
        {"node_id": 1, "activation": 0.1},
    ]
    assert result["terminal_local_state"]["status"] == "local_steady"
    assert result["nodes"][0]["sampled_activation_integral"] == pytest.approx(0.05)
    assert r == original


def test_transient_activity_is_preserved_without_manufacturing_convergence():
    result = analyze_targets(record([{1: 0.002}, {}, {}, {}]), node_ids=[1], settle_us=200000)
    assert result["process"]["raw_activity_seen"]
    assert result["nodes"][0]["sampled_activation_integral"] == pytest.approx(0.0002)
    assert result["nodes"][0]["terminal_activation"] == 0
    assert result["first_pattern_convergence"] is None
    assert result["terminal_local_state"]["status"] == "below_activity_floor"


def test_decay_is_stable_pattern_not_steady_amplitude():
    r = record([{1: 0.5 ** (i + 1), 2: 0.5 ** (i + 2)} for i in range(6)])
    result = analyze_targets(r, node_ids=[1, 2], settle_us=200000)
    assert result["first_pattern_convergence"] is not None
    assert result["first_steady_convergence"] is None
    assert result["terminal_local_state"]["status"] == "local_pattern"


def test_gap_and_short_record_cannot_establish_local_stability():
    r = record([{1: 0.2}] * 3, [0, 100000, 800000])
    result = analyze_targets(r, node_ids=[1], settle_us=200000)
    assert result["process"]["sampling_gap_detected"]
    assert result["first_steady_convergence"] is None
    assert result["terminal_local_state"]["status"] == "insufficient_span"
    empty = analyze_targets(record([]), node_ids=[1])
    assert empty["process"]["status"] == "not_observed"
    assert empty["terminal_local_state"]["status"] == "not_observed"


@pytest.mark.parametrize("ids", [[], [1, 1], [True], [1.5], [100], list(range(257))])
def test_invalid_or_unknown_target_is_not_a_zero_response(ids):
    with pytest.raises(ValueError):
        analyze_targets(record([{1: 0.2}]), node_ids=ids)


def test_baseline_decrease_and_reentry_and_no_topk_fallback():
    r = record([{1: 0.2}, {}, {1: 0.1}, {}, {}])
    r["nodes"][0]["baseline_mean"] = 0.3
    result = analyze_targets(r, node_ids=[1], settle_us=200000)
    assert result["process"]["decrease_seen"] and not result["process"]["increase_seen"]
    assert result["nodes"][0]["activity_episode_count"] == 2
    del r["series"][0]["activation_vector"]
    with pytest.raises(ValueError, match="complete activation"):
        analyze_targets(r, node_ids=[1])


def test_cli_and_registry_use_same_analysis_and_preserve_file(tmp_path):
    from threemind_runtime.observation_cli import main

    r = record([{1: 0.3}] * 6)
    src, out = tmp_path / "input.json", tmp_path / "result.jsonl"
    src.write_text(json.dumps(r), encoding="utf-8")
    before = src.read_bytes()
    main(["target", "--input", str(src), "--node-ids", "1", "--settle-us", "200000", "--output", str(out)])
    result = json.loads(out.read_text())["result"]
    assert result == run_tool("target", {"record": r}, {"node_ids": [1], "settle_us": 200000})
    assert src.read_bytes() == before
    with pytest.raises(SystemExit):
        main(["target", "--input", str(src), "--node-ids", "1", "--output", str(out)])


def test_cannot_fill_unknown_evidence_or_accept_nan():
    r = record([{1: 0.2}] * 6)
    with pytest.raises(ValueError):
        target_observation(r["series"], r["nodes"], [1], expected_interval_us=100000, response_floor=float("nan"))
    with pytest.raises(ValueError, match="unknown tool option"):
        run_tool("target", {"record": r}, {"node_ids": [1], "omit_background": True})


def test_saved_microsecond_strings_have_the_same_meaning():
    r = record([{1: 0.2}] * 10)
    expected = analyze_targets(r, node_ids=[1])
    r["configuration"]["interval_us"] = "100000"
    actual = analyze_targets(r, node_ids=[1])
    assert actual["process"] == expected["process"]
    assert actual["first_steady_convergence"] == expected["first_steady_convergence"]
