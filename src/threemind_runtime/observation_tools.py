"""Reusable offline observation tools. No simulation, database writes or plugins executed."""

from __future__ import annotations

import hashlib
import json

from .process_observation import compare_observations, process_observation
from .response_readout import VERSION as RESPONSE_VERSION
from .response_readout import response_readout
from .target_observation import VERSION as TARGET_VERSION
from .target_observation import target_observation

TOOLS = {
    "response": {
        "version": RESPONSE_VERSION,
        "inputs": ["record"],
        "purpose": "Brief responses and simultaneous activation rankings, without a minimum duration",
    },
    "target": {
        "version": TARGET_VERSION,
        "inputs": ["record"],
        "purpose": "Explicit target response and local convergence, separate from the global classification",
    },
    "process": {
        "version": "threemind.process-observation/1",
        "inputs": ["record"],
        "purpose": "Full sampled process, including brief, weak and decreasing activity",
    },
    "compare": {
        "version": "threemind.observation-comparison/1",
        "inputs": ["left", "right"],
        "purpose": "Corresponding node trajectories at matched times; not only endpoint or top-k",
    },
}


def payload(record):
    value = record.get("payload", record)
    if value.get("kind") != "temporal_readout" or not value.get("analysis_schema"):
        raise ValueError("requires an activity readout with complete vectors; top-k cannot reconstruct a process")
    return value


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    ).hexdigest()


def analyze_record(record, *, epsilon=1e-12):
    value = payload(record)
    process, nodes = process_observation(
        value["series"],
        value["nodes"],
        epsilon=epsilon,
        delivery_end_us=value.get("delivery_end_us"),
        expected_interval_us=value["configuration"]["interval_us"],
    )
    process["baseline_status"] = baseline_status(value)
    return {
        "schema": "threemind.observation-analysis/1",
        "tool": TOOLS["process"],
        "source_sha256": fingerprint(record),
        "original_classification": value["classification"],
        "original_coverage": value.get("coverage"),
        "original_censored": value.get("censored"),
        "process": process,
        "nodes": [
            {"node_id": int(key), "annotations": value.get("annotations", {}).get(key, []), **row}
            for key, row in sorted(nodes.items(), key=lambda kv: int(kv[0]))
        ],
        "scope": "derived from existing complete samples; missing intervals cannot be reconstructed",
    }


def baseline_status(value):
    coverage = value.get("coverage", {})
    requested = int(coverage.get("baseline_requested_us", value["configuration"].get("baseline_us", 0)))
    measured = int(coverage.get("baseline_coverage_us", 0))
    return (
        "zero-reference-configured"
        if not requested
        else "unavailable-zero-reference"
        if not measured
        else "measured"
        if measured >= requested
        else "partial"
    )


def analyze_targets(record, *, node_ids, **options):
    value = payload(record)
    result = target_observation(
        value["series"],
        value["nodes"],
        node_ids,
        expected_interval_us=int(value["configuration"]["interval_us"]),
        **options,
    )
    result["process"]["baseline_status"] = baseline_status(value)
    for row in result["nodes"]:
        row["annotations"] = value.get("annotations", {}).get(str(row["node_id"]), [])
    return result | {
        "tool": TOOLS["target"],
        "source_sha256": fingerprint(record),
        "source_window": value["window_id"],
        "original_classification": value["classification"],
        "original_coverage": value.get("coverage"),
        "original_censored": value.get("censored"),
    }


def analyze_responses(record, *, node_ids=None, epsilon=1e-12):
    value = payload(record)
    result = response_readout(
        value["series"],
        value["nodes"],
        node_ids=node_ids,
        expected_interval_us=value["configuration"]["interval_us"],
        epsilon=epsilon,
    )
    selected = set(result["selection"]["node_ids"])
    return result | {
        "tool": TOOLS["response"],
        "source_sha256": fingerprint(record),
        "source_window": value["window_id"],
        "original_classification": value["classification"],
        "original_coverage": value.get("coverage"),
        "original_censored": value.get("censored"),
        "annotations": {k: v for k, v in value.get("annotations", {}).items() if int(k) in selected},
    }


def compare_records(left, right, *, relative=False, epsilon=1e-12):
    a, b = payload(left), payload(right)
    return compare_observations(a["series"], b["series"], relative=relative, epsilon=epsilon) | {
        "source_sha256": [fingerprint(left), fingerprint(right)],
        "source_windows": [a["window_id"], b["window_id"]],
        "source_coverage": [a.get("coverage"), b.get("coverage")],
    }


def run_tool(name, records, options=None):
    """Static registry: inspectable and composable, never load code from a plan."""
    if name not in TOOLS:
        raise ValueError("unknown observation tool")
    expected = TOOLS[name]["inputs"]
    if set(records) != set(expected):
        raise ValueError("tool inputs do not match the registered contract")
    options = options or {}
    allowed = {"epsilon"} | (
        {"relative"}
        if name == "compare"
        else {"node_ids", "settle_us", "pattern_drift_max", "amplitude_drift_max", "response_floor"}
        if name == "target"
        else {"node_ids"}
        if name == "response"
        else set()
    )
    if set(options) - allowed:
        raise ValueError("unknown tool option")
    if "relative" in options and type(options["relative"]) is not bool:
        raise ValueError("relative must be boolean")
    return {
        "process": analyze_record,
        "compare": compare_records,
        "target": analyze_targets,
        "response": analyze_responses,
    }[name](**records, **options)
