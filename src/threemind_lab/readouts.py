"""Lab host for recoverable, read-only output analysis."""

from __future__ import annotations

import csv
import io
import json

from threemind_runtime.readout_host import ReadoutHost


def reconfigure(state, spec, run_id, time_us):
    events = []
    host = ReadoutHost(spec, run_id, time_us, state=state, record=events.append)
    return host.capture(), events


def export_stream(database, project, run_id, kind=None, classification=None):
    with database.tx(project, repeatable=True) as db, db.cursor(name="readout_export") as cursor:
        cursor.itersize = 5
        cursor.execute(
            "SELECT id,time_us,payload,commit_revision FROM events WHERE run_id=%s AND kind IN ('structural_readout','temporal_readout') "
            "AND (%s::text IS NULL OR kind=%s) AND (%s::text IS NULL OR payload->>'classification'=%s) ORDER BY id",
            (run_id, kind, kind, classification, classification),
        )
        for row in cursor:
            yield (json.dumps(row, ensure_ascii=False, default=str, allow_nan=False) + "\n").encode()


def nodes_csv(value):
    temporal = value["kind"] == "temporal_readout"
    raw = value.get("raw_observation", {})
    rows = (
        value["nodes"]
        if temporal
        else value["raw_nodes"]
        if raw.get("complete")
        else value["activity_nodes"] or (value.get("structure") or {}).get("nodes", [])
    )
    scope = (
        "sampled-node-aggregates" if temporal else "all-source-nodes" if raw.get("complete") else "derived-nodes-only"
    )
    rows = [dict(row, observation_scope=scope) for row in rows]
    buffer = io.StringIO(newline="")
    fields = list(rows[0]) if rows else ["node_id", "observation_scope"]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return ("\ufeff" + buffer.getvalue()).encode()


def response_figure(value, format):
    """Export all recorded aggregate points, including explicit censoring."""
    from matplotlib.figure import Figure

    if value["kind"] != "temporal_readout":
        raise ValueError("trajectory figures require a temporal readout")
    process = value.get("process", {}).get("timeline", [])
    fig = Figure(figsize=(9, 9 if process else 6), layout="constrained")
    axes = fig.subplots(3 if process else 2, 1, sharex=True)
    times = [int(row["time_us"]) / 1e6 for row in value["series"]]
    for ax, key, label in zip(axes, ("total", "active_node_count"), ("Excess activation (a.u.)", "Active nodes")):
        ax.step(times, [r[key] for r in value["series"]], where="post", color="#237e74")
        ax.set_ylabel(label)
        ax.grid(alpha=0.2)
        if value["delivery_end_us"] is not None:
            ax.axvline(
                int(value["delivery_end_us"]) / 1e6, color="#a77530", linestyle="--", label="Input delivery ended"
            )
            ax.legend()
    if process:
        pt = [int(r["time_us"]) / 1e6 for r in process]
        for key, label in (
            ("activation_total", "Raw activity"),
            ("increase_over_baseline", "Increase vs baseline"),
            ("decrease_below_baseline", "Decrease vs baseline"),
        ):
            axes[2].step(pt, [r[key] for r in process], where="post", label=label)
        axes[2].legend()
        axes[2].set_ylabel("Process (a.u.)")
        axes[2].grid(alpha=0.2)
    axes[-1].set_xlabel("Simulation time (s); left-hold sampled estimate")
    fig.suptitle(
        f"{value['classification']} / {value['reason']}\nWindow {value['window_id']}; baseline coverage {value['coverage']['baseline_coverage_us']} us"
    )
    output = io.BytesIO()
    fig.savefig(output, format=format, dpi=180)
    return output.getvalue()
