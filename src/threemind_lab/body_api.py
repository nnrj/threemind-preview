"""Checkpoint-pinned evidence for external environments and body transduction."""

import csv
import io
import json
from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from fastapi.responses import StreamingResponse

from threemind_core.spec import timestamp

from .database import NotFound

SOURCES = ("mujoco", "ambient-fixture", "ambient-disturbance", "simulated-interoception")


def selection(database, project, run_id, checkpoint_id):
    database.get_run(project, run_id)
    with database.tx(project) as db:
        cp = db.execute(
            "SELECT id,revision,time_us,state_hash,context FROM checkpoints WHERE run_id=%s AND (%s::uuid IS NULL OR id=%s) ORDER BY revision DESC LIMIT 1",
            (run_id, checkpoint_id, checkpoint_id),
        ).fetchone()
    if cp is None:
        raise NotFound("No matching checkpoint")
    tools = cp["context"].get("body_tools")
    # Random generator and per-channel baselines remain available in checkpoints,
    # but the status view need not transfer these large recovery internals.
    status = None if tools is None else {k: v for k, v in tools.items() if k not in ("ambient", "body_filter")}
    if status is not None:
        status["body_filter"] = {k: v for k, v in tools["body_filter"].items() if k not in ("rng", "baseline")}
        status["body_filter"]["baseline_channels"] = len(tools["body_filter"]["baseline"])
        status["ambient"] = (
            None
            if tools["ambient"] is None
            else {k: v for k, v in tools["ambient"].items() if k not in ("rng", "transients")}
        )
        if status["ambient"] is not None:
            status["ambient"]["active_transients"] = len(tools["ambient"]["transients"])
    return {
        "checkpoint_id": str(cp["id"]),
        "revision": cp["revision"],
        "time_us": str(cp["time_us"]),
        "state_hash": cp["state_hash"],
        "has_world": (cp["context"].get("environment") or {}).get("kind") in ("world", "robot"),
        "status": status,
        "configuration": {
            k: v
            for k, v in cp["context"].get("protocol", {}).items()
            if k in ("environment", "seed", "ambient_field", "body_filter", "interoception")
        },
    }


def evidence(database, project, run_id, selected, source, start, until, before, limit=None):
    revision = selected["revision"]
    with database.tx(project) as db, db.cursor(name="body_evidence") as cursor:
        cursor.execute(
            """SELECT e.ordinal AS frame_id,e.id AS envelope_id,e.source,e.payload,e.configuration,e.configuration_hash,
                f.stimulus,f.status,f.reason,f.scheduled_time_us,f.delivered_time_us,f.delivered_revision,f.input_gate
                FROM input_frames f JOIN input_envelopes e ON e.id=f.envelope_id
                WHERE f.run_id=%s AND f.frame_index=0 AND f.scheduled_revision<=%s AND e.adapter_id=ANY(%s)
                AND (%s='' OR e.source=%s) AND f.scheduled_time_us>=%s
                AND (%s::numeric IS NULL OR f.scheduled_time_us<=%s)
                AND (%s::bigint IS NULL OR e.ordinal<%s) ORDER BY e.ordinal DESC LIMIT %s""",
            (run_id, revision, list(SOURCES), source, source, start, until, until, before, before, limit),
        )
        for row in cursor:
            if row["delivered_revision"] is None or row["delivered_revision"] > revision:
                row["delivered_time_us"] = None
                row["input_gate"] = None
                if row["status"] == "delivered":
                    row["status"] = "scheduled"
            yield {
                "frame_id": row["frame_id"],
                "envelope_id": str(row["envelope_id"]),
                "source": row["source"],
                "scheduled_time_us": str(row["scheduled_time_us"]),
                "delivered_time_us": str(row["delivered_time_us"]) if row["delivered_time_us"] is not None else None,
                "status": row["status"],
                "reason": row["reason"],
                "configuration": row["configuration"],
                "configuration_hash": row["configuration_hash"],
                "raw": row["payload"]["frames"][0],
                "transduction": row["payload"].get("transduction"),
                "stimulus": row["stimulus"],
                "input_gate": row["input_gate"],
            }


def register_body_routes(app, access):
    def query(request, project, run_id, checkpoint_id, source, after_us, until_us):
        access(request, project)
        if source and source not in SOURCES:
            raise ValueError("Unknown environmental source")
        start, until = timestamp(after_us), timestamp(until_us) if until_us is not None else None
        if until is not None and until < start:
            raise ValueError("End precedes start")
        selected = selection(app.state.db, project, run_id, checkpoint_id)
        selected["filter"] = {
            "source": source,
            "after_us": str(start),
            "until_us": str(until) if until is not None else None,
        }
        return selected, start, until

    @app.get("/api/v2/projects/{project}/runs/{run_id}/body-tools")
    def get(
        project: UUID,
        run_id: UUID,
        request: Request,
        checkpoint_id: UUID | None = None,
        source: str = "",
        after_us: str = "0",
        until_us: str | None = None,
        before: int | None = Query(None, ge=1, le=2**63 - 1),
        limit: int = Query(30, ge=1, le=500),
    ):
        selected, start, until = query(request, project, run_id, checkpoint_id, source, after_us, until_us)
        rows = list(evidence(app.state.db, project, run_id, selected, source, start, until, before, limit + 1))
        return selected | {
            "rows": rows[:limit],
            "more": len(rows) > limit,
            "next": rows[limit - 1]["frame_id"] if len(rows) > limit else None,
        }

    @app.get("/api/v2/projects/{project}/runs/{run_id}/body-tools/export")
    def export(
        project: UUID,
        run_id: UUID,
        request: Request,
        checkpoint_id: UUID | None = None,
        source: str = "",
        after_us: str = "0",
        until_us: str | None = None,
        format: Literal["csv", "jsonl"] = "jsonl",
    ):
        selected, start, until = query(request, project, run_id, checkpoint_id, source, after_us, until_us)

        def stream():
            rows = evidence(app.state.db, project, run_id, selected, source, start, until, None)
            if format == "jsonl":
                yield json.dumps({"kind": "selection", **selected}, ensure_ascii=False) + "\n"
                for row in rows:
                    yield json.dumps({"kind": "body_evidence", **row}, ensure_ascii=False) + "\n"
            else:
                buffer = io.StringIO(newline="")
                columns = [
                    "checkpoint_id",
                    "revision",
                    "state_hash",
                    "frame_id",
                    "envelope_id",
                    "source",
                    "scheduled_time_us",
                    "delivered_time_us",
                    "status",
                    "reason",
                    "configuration_hash",
                    "configuration",
                    "raw",
                    "transduction",
                    "stimulus",
                    "input_gate",
                ]
                writer = csv.DictWriter(buffer, fieldnames=columns)
                writer.writeheader()
                yield "\ufeff" + buffer.getvalue()
                for row in rows:
                    buffer.seek(0)
                    buffer.truncate()
                    values = {**row, **{k: selected[k] for k in ("checkpoint_id", "revision", "state_hash")}}
                    writer.writerow(
                        {
                            k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                            for k, v in values.items()
                        }
                    )
                    yield buffer.getvalue()

        return StreamingResponse(
            stream(),
            media_type="text/csv; charset=utf-8" if format == "csv" else "application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="body-{run_id}-r{selected["revision"]}.{format}"'},
        )
