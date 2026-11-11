"""Fixed temporal evidence views; numbers come only from recorded reader output."""

import hashlib
import json
from uuid import uuid4

from .database import NotFound

KINDS = ("temporal_windows", "temporal_nodes", "temporal_series")
CATALOG = {
    "temporal_windows": {
        "observed_seconds": "s",
        "tail_seconds": "s",
        "baseline_seconds": "s",
        "response_seconds": "s",
        "convergence_seconds": "s",
        "converged": "fraction",
        "node_count": "count",
        "candidate_count": "count",
        "sample_count": "count",
        "mean_jaccard": "fraction",
        "mean_distribution_drift": "fraction",
        "amplitude_drift": "fraction",
        "pattern_converged": "fraction",
        "pattern_seconds": "s",
        "period_seconds": "s",
        "response_ended": "fraction",
        "process_active_nodes": "count",
        "process_increased_nodes": "count",
        "process_decreased_nodes": "count",
        "process_ended_nodes": "count",
        "process_reactivated_nodes": "count",
        "process_total_variation": "a.u.",
    },
    "temporal_nodes": {
        "active_seconds": "s",
        "longest_run_seconds": "s",
        "tail_active_seconds": "s",
        "score": "a.u.",
        "rank": "rank",
        "peak_activation": "a.u.",
        "last_activation": "a.u.",
        "decision_activation": "a.u.",
        "activation_integral": "a.u. s",
        "excess_integral": "a.u. s",
        "reentry_count": "count",
        "positive_change_peak": "a.u.",
        "negative_change_peak": "a.u.",
        "positive_change_integral": "a.u. s",
        "negative_change_integral": "a.u. s",
        "total_activation_variation": "a.u.",
        "activity_episode_count": "count",
    },
    "temporal_series": {
        "total": "a.u.",
        "active_node_count": "count",
        "activation_total": "a.u.",
        "increase_over_baseline": "a.u.",
        "decrease_below_baseline": "a.u.",
        "step_increase": "a.u.",
        "step_decrease": "a.u.",
        "pattern_distance": "fraction",
    },
}


def seconds(value):
    return int(value) / 1e6 if value is not None else None


def calibration_snapshot(db, ident):
    row = db.execute(
        "SELECT c.*,j.result,j.status,a.sha256,a.bytes FROM probe_calibrations c JOIN jobs j ON j.id=c.job_id "
        "LEFT JOIN artifacts a ON a.id::text=j.result->>'artifact_id' WHERE c.id=%s AND j.status='done'",
        (ident,),
    ).fetchone()
    if not row or row["protocol"].get("mode") != "temporal":
        raise NotFound("select a completed temporal-window experiment")
    if row["bytes"] is None or row["bytes"] > 64 * 1024**2:
        raise ValueError("temporal experiment exceeds the evidence-source budget")
    return row


def windows(db, request, *, original_bytes=None):
    selection = request["selection"]
    if selection.get("calibration_id"):
        origin = request["provenance"]
        if original_bytes is None:
            chunks = db.execute(
                "SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal", (origin["artifact_id"],)
            ).fetchall()
            original_bytes = b"".join(bytes(r["body"]) for r in chunks)
        raw = original_bytes
        if hashlib.sha256(raw).hexdigest() != origin["artifact_hash"]:
            raise ValueError("temporal experiment artifact hash mismatch")
        for case in json.loads(raw)["rows"]:
            yield (
                case.get("temporal"),
                {
                    "calibration_id": selection["calibration_id"],
                    "case_id": case["id"],
                    "cue": case["cue"],
                    "classification": case["classification"],
                    "reason": case["reason"],
                    "source_hash": origin["source_hash"],
                },
            )
    else:
        cp = request["provenance"]["checkpoint"]
        with db.cursor(name="temporal_source_" + uuid4().hex) as cursor:
            cursor.itersize = 1
            cursor.execute(
                "SELECT id,payload,commit_revision FROM events WHERE run_id=%s AND kind='temporal_readout' "
                "AND time_us BETWEEN %s AND %s AND commit_revision<=%s ORDER BY time_us,id",
                (request["run_id"], selection["from_us"], selection["through_us"], cp["revision"]),
            )
            for record in cursor:
                yield record["payload"], {"event_id": str(record["id"]), "commit_revision": record["commit_revision"]}


def evidence_rows(db, request, coverage, *, original_bytes=None):
    selected = set(request["selection"].get("window_ids", []))
    seen, counts = set(), {}
    coverage.update(
        row_unit={
            "temporal_windows": "one completed or explicitly unobserved window",
            "temporal_nodes": "one node within one window",
            "temporal_series": "one window sample",
        }[request["kind"]],
        classifications=counts,
        missing_values_are_zero=False,
        rows_are_independent_replicates=False,
        interpretation="window/peak/final measurements are distinct; same-source probes share inherited state",
    )
    for value, origin in windows(db, request, original_bytes=original_bytes):
        if value is None:
            if selected or request["kind"] != "temporal_windows":
                continue
            counts[origin["classification"]] = counts.get(origin["classification"], 0) + 1
            yield {
                "time_us": None,
                "label": origin["case_id"],
                "quality": origin["classification"],
                "values": {},
                "provenance": origin,
            }
            continue
        window_id = value["window_id"]
        if selected and window_id not in selected:
            continue
        seen.add(window_id)
        classification = value["classification"]
        counts[classification] = counts.get(classification, 0) + 1
        meta = origin | {
            "window_id": window_id,
            "envelope_id": value.get("envelope_id"),
            "classification": classification,
            "reason": value["reason"],
            "configuration": value["configuration"],
            "coverage": value["coverage"],
            "overlapping_envelopes": value.get("overlapping_envelopes", []),
            "measurement_scope": value.get("measurement_scope"),
            "analysis_schema": value.get("analysis_schema"),
            "analysis_id": value.get("analysis_id", "activity-steady-state"),
            "ranking_time_us": value.get("ranking_time_us"),
            "window_hash": hashlib.sha256(
                json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
            ).hexdigest(),
        }
        label = window_id
        if request["kind"] == "temporal_windows":
            c, convergence = value["coverage"], value["convergence"]
            response = (
                (int(value["end_us"]) - int(value["delivery_end_us"])) / 1e6
                if value["delivery_end_us"] is not None
                else None
            )
            valid = classification not in ("not_observed", "interrupted", "censored")
            values = {
                "observed_seconds": seconds(c.get("observed_us")),
                "tail_seconds": seconds(c.get("tail_observed_us")),
                "baseline_seconds": seconds(c.get("baseline_coverage_us")),
                "response_seconds": response,
                "convergence_seconds": response if classification == "converged" else None,
                "converged": int(classification == "converged") if valid else None,
                "node_count": len(value["nodes"]),
                "candidate_count": len(value["candidate_ids"]),
                "sample_count": c.get("sample_count"),
                **{k: convergence.get(k) for k in ("mean_jaccard", "mean_distribution_drift", "amplitude_drift")},
            }
            if value.get("analysis_schema"):
                analyses = value["analyses"]
                pattern, periodic, ended = (analyses[k] for k in ("pattern", "periodic", "response_end"))
                values.update(
                    pattern_converged=int(pattern["status"] == "converged")
                    if pattern["status"] != "disabled"
                    else None,
                    pattern_seconds=(
                        int(pattern["end_us"]) - int(value.get("observation_anchor_us") or value["delivery_end_us"])
                    )
                    / 1e6
                    if pattern["status"] == "converged"
                    else None,
                    period_seconds=seconds(periodic.get("period_us")),
                    response_ended=int(ended["status"] == "ended") if ended["status"] != "disabled" else None,
                    # Preserve the old measure's meaning; pattern convergence is a separate column.
                    converged=None,
                    convergence_seconds=None,
                )
            process = value.get("process", {})
            if process.get("status") == "recorded":
                values.update(
                    {
                        "process_" + key: process.get(field)
                        for key, field in (
                            ("active_nodes", "active_node_count"),
                            ("increased_nodes", "increased_node_count"),
                            ("decreased_nodes", "decreased_node_count"),
                            ("ended_nodes", "ended_node_count"),
                            ("reactivated_nodes", "reactivated_node_count"),
                            ("total_variation", "total_activation_variation"),
                        )
                    }
                )
            yield {
                "time_us": value["end_us"],
                "label": label,
                "quality": classification,
                "values": values,
                "provenance": meta | {"readout": value},
            }
        elif request["kind"] == "temporal_nodes":
            ranks = {int(node): i + 1 for i, node in enumerate(value["candidate_ids"])}
            for node in value["nodes"]:
                values = node | {
                    "rank": ranks.get(node["node_id"]),
                    "active_seconds": seconds(node["active_us"]),
                    "longest_run_seconds": seconds(node["longest_run_us"]),
                    "tail_active_seconds": seconds(node["tail_active_us"]),
                }
                yield {
                    "time_us": value["end_us"],
                    "label": f"{label} / #{node['node_id']}",
                    "quality": classification,
                    "values": values,
                    "provenance": meta
                    | {"raw_node": node, "labels": value.get("annotations", {}).get(str(node["node_id"]), [])},
                }
        else:
            process_points = {point["time_us"]: point for point in value.get("process", {}).get("timeline", [])}
            for point in value["series"]:
                yield {
                    "time_us": point["time_us"],
                    "label": label,
                    "quality": classification,
                    "values": point | process_points.get(point["time_us"], {}),
                    "provenance": meta | {"raw_sample": point},
                }
    if selected - seen:
        raise NotFound("selected windows are outside the fixed source boundary")
