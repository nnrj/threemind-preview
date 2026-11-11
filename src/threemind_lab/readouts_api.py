"""Paged scientific readout views; bulk evidence is an explicit download."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import Query, Request
from fastapi.responses import Response, StreamingResponse

from threemind_runtime.observation_tools import analyze_record, analyze_responses, analyze_targets, compare_records

from .database import NotFound
from .readouts import export_stream, nodes_csv, response_figure

KINDS = ("structural_readout", "temporal_readout")
CLASSES = (
    "converged",
    "oscillatory",
    "residual_decay",
    "transient",
    "unresolved",
    "censored",
    "interrupted",
    "not_observed",
    "pattern_converged",
    "periodic_activity",
    "response_ended",
)
# Large arrays never cross the DB/application boundary for the history list.
SUMMARY = """((payload - 'nodes' - 'raw_nodes' - 'activity_nodes' - 'candidate_ids' - 'legacy_candidate_ids' - 'annotations' - 'structure' - 'series')
    #- '{primary_result,nodes}' #- '{analyses,pattern,nodes}' #- '{analyses,periodic,nodes}' #- '{process,timeline}')
    || jsonb_build_object('node_count', CASE WHEN kind='temporal_readout'
         THEN jsonb_array_length(payload->'nodes') ELSE jsonb_array_length(payload->'activity_nodes') END,
       'series_count',COALESCE(jsonb_array_length(payload->'series'),0),
       'structure', CASE WHEN payload->'structure' IS NULL OR payload->'structure'='null'::jsonb THEN NULL
          ELSE ((payload->'structure') - 'nodes' - 'edges') || jsonb_build_object(
              'node_count',jsonb_array_length(payload->'structure'->'nodes'),
              'edge_count',jsonb_array_length(payload->'structure'->'edges')) END)"""


def selection(kind, classification):
    if kind is not None and kind not in KINDS or classification is not None and classification not in CLASSES:
        raise ValueError("unknown readout filter")


def register_readout_routes(app, access):
    base = "/api/v2/projects/{project}/runs/{run_id}/readouts"

    def source_record(project, run_id, record_id):
        with app.state.db.tx(project) as db:
            row = db.execute(
                "SELECT payload,octet_length(payload::text) AS bytes FROM events "
                "WHERE run_id=%s AND id=%s AND kind='temporal_readout' "
                "AND octet_length(payload::text)<=67108864",
                (run_id, record_id),
            ).fetchone()
        if row is None:
            raise NotFound("找不到完整时序记录，或记录超过 64 MiB 单窗分析预算。")
        return row["payload"]

    @app.get(base + "/compare")
    def compare(
        project: UUID,
        run_id: UUID,
        request: Request,
        left_id: int = Query(..., ge=1),
        right_id: int = Query(..., ge=1),
        right_run: UUID | None = None,
        relative: bool = False,
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=2000),
    ):
        access(request, project)
        result = compare_records(
            source_record(project, run_id, left_id),
            source_record(project, right_run or run_id, right_id),
            relative=relative,
        )
        return result | {
            "nodes": result["nodes"][offset : offset + limit],
            "node_count": len(result["nodes"]),
            "series": result["series"][offset : offset + limit],
            "offset": offset,
        }

    @app.get(base + "/{record_id}/process")
    def process(
        project: UUID,
        run_id: UUID,
        record_id: int,
        request: Request,
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=2000),
    ):
        access(request, project)
        result = analyze_record(source_record(project, run_id, record_id))
        return result | {
            "nodes": result["nodes"][offset : offset + limit],
            "node_count": len(result["nodes"]),
            "process": result["process"] | {"timeline": result["process"].get("timeline", [])[offset : offset + limit]},
            "offset": offset,
        }

    @app.get(base + "/{record_id}/response")
    def response(
        project: UUID,
        run_id: UUID,
        record_id: int,
        request: Request,
        node_ids: str | None = Query(None, min_length=1, max_length=32768),
        epsilon: float = Query(1e-12, ge=0, le=1),
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=2000),
        event_index: int | None = Query(None, ge=0),
        rank_offset: int = Query(0, ge=0),
        download: bool = False,
    ):
        access(request, project)
        ids = None if node_ids is None else [int(n.strip()) for n in node_ids.split(",")]
        result = analyze_responses(source_record(project, run_id, record_id), node_ids=ids, epsilon=epsilon)
        if download:
            return Response(
                json.dumps(result, ensure_ascii=False, allow_nan=False),
                media_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="response-readout-{record_id}.json"'},
            )
        choice = result["strongest_event_index"] if event_index is None else event_index
        if choice is not None and choice >= len(result["events"]):
            raise ValueError("response event index is outside this record")
        selected = result["events"][choice] if choice is not None else None
        return result | {
            "events": [
                {k: v for k, v in e.items() if k != "ranking"} for e in result["events"][offset : offset + limit]
            ],
            "episodes": result["episodes"][offset : offset + limit],
            "timeline": result["timeline"][offset : offset + limit],
            "selected_event": None
            if selected is None
            else selected
            | {
                "ranking": selected["ranking"][rank_offset : rank_offset + limit],
                "ranking_count": len(selected["ranking"]),
            },
            "offset": offset,
            "rank_offset": rank_offset,
        }

    @app.get(base + "/{record_id}/target")
    def target(
        project: UUID,
        run_id: UUID,
        record_id: int,
        request: Request,
        node_ids: str = Query(..., min_length=1, max_length=8192),
        settle_us: int = Query(800000, ge=1, le=60000000),
        pattern_drift_max: float = Query(0.08, ge=0, le=1),
        amplitude_drift_max: float = Query(0.12, ge=0, le=1),
        response_floor: float = Query(1e-8, ge=0, le=1),
        epsilon: float = Query(1e-12, ge=0, le=1),
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=2000),
        download: bool = False,
    ):
        access(request, project)
        ids = [int(n.strip()) for n in node_ids.split(",")]
        result = analyze_targets(
            source_record(project, run_id, record_id),
            node_ids=ids,
            settle_us=settle_us,
            pattern_drift_max=pattern_drift_max,
            amplitude_drift_max=amplitude_drift_max,
            response_floor=response_floor,
            epsilon=epsilon,
        )
        if download:
            return Response(
                json.dumps(result, ensure_ascii=False, allow_nan=False),
                media_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="target-readout-{record_id}.json"'},
            )
        return result | {
            "process": result["process"] | {"timeline": result["process"].get("timeline", [])[offset : offset + limit]},
            "offset": offset,
        }

    @app.get(base)
    def history(
        project: UUID,
        run_id: UUID,
        request: Request,
        kind: str | None = None,
        classification: str | None = None,
        recurrent: bool = False,
        before_id: int | None = Query(None, ge=1),
        limit: int = Query(30, ge=1, le=100),
    ):
        access(request, project)
        run = app.state.db.get_run(project, run_id)
        selection(kind, classification)
        with app.state.db.tx(project, repeatable=True) as db:
            diagnostic = db.execute(
                "SELECT context->'readouts'->'activity'->'diagnostics' AS value "
                "FROM checkpoints WHERE run_id=%s AND revision=%s",
                (run_id, run["revision"]),
            ).fetchone()
            rows = db.execute(
                f"SELECT id,time_us,commit_revision,{SUMMARY} AS payload FROM events WHERE run_id=%s "
                "AND kind IN ('structural_readout','temporal_readout') AND (%s::text IS NULL OR kind=%s) "
                "AND (%s::text IS NULL OR payload->>'classification'=%s) "
                "AND (NOT %s OR payload->'structure'->>'recurrence_notice'='true') "
                "AND (%s::bigint IS NULL OR id<%s) ORDER BY id DESC LIMIT %s",
                (run_id, kind, kind, classification, classification, recurrent, before_id, before_id, limit + 1),
            ).fetchall()
            active = db.execute(
                "SELECT w.key AS envelope_id,w.value->>'window_id' AS window_id,w.value->>'source' AS source,"
                "w.value->>'start_us' AS start_us,w.value->>'last_us' AS last_sample_us,"
                "w.value->>'delivery_end_us' AS delivery_end_us,w.value->'sample_count' AS sample_count,"
                "(SELECT count(*) FROM jsonb_object_keys(w.value->'nodes')) AS node_count, reader.name AS analysis_id "
                "FROM checkpoints c CROSS JOIN LATERAL (VALUES ('temporal'),('activity')) reader(name) "
                "CROSS JOIN LATERAL jsonb_each(c.context->'readouts'->reader.name->'windows') w "
                "WHERE c.run_id=%s AND c.revision=%s ORDER BY (w.value->>'start_us')::numeric,w.key LIMIT 100",
                (run_id, run["revision"]),
            ).fetchall()
        return {
            "rows": rows[:limit],
            "more": len(rows) > limit,
            "next": rows[min(limit, len(rows)) - 1]["id"] if rows else None,
            "active": active,
            "active_limit": 100,
            "revision": run["revision"],
            "trigger_diagnostics": diagnostic["value"] if diagnostic else None,
            "configuration": {k: v for k, v in run["spec"].items() if k.endswith("_readout")},
        }

    # Static route must precede the record identifier route.
    @app.get(base + "/export")
    def export(
        project: UUID, run_id: UUID, request: Request, kind: str | None = None, classification: str | None = None
    ):
        access(request, project)
        app.state.db.get_run(project, run_id)
        selection(kind, classification)
        return StreamingResponse(
            export_stream(app.state.db, project, run_id, kind, classification),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": 'attachment; filename="readouts.jsonl"'},
        )

    @app.get(base + "/{record_id}")
    def detail(
        project: UUID,
        run_id: UUID,
        record_id: int,
        request: Request,
        section: str = "default",
        candidates_only: bool = False,
        order: str = "scientific",
        offset: int = Query(0, ge=0, le=10000000),
        limit: int = Query(20, ge=1, le=2000),
    ):
        access(request, project)
        app.state.db.get_run(project, run_id)
        if section not in (
            "default",
            "nodes",
            "raw_nodes",
            "structure_nodes",
            "edges",
            "series",
            "process_series",
        ) or order not in (
            "scientific",
            "id",
            "activation",
            "end-activation",
            "decision-activation",
            "duration",
            "excess",
            "increase",
            "decrease",
            "variation",
            "onset",
        ):
            raise ValueError("unknown readout section or order")
        with app.state.db.tx(project, repeatable=True) as db:
            record = db.execute(
                f"SELECT id,time_us,commit_revision,kind,{SUMMARY} AS payload FROM events WHERE run_id=%s AND id=%s "
                "AND kind IN ('structural_readout','temporal_readout')",
                (run_id, record_id),
            ).fetchone()
            if record is None:
                raise NotFound()
            temporal = record["kind"] == "temporal_readout"
            if section == "default":
                section = "nodes" if temporal else "raw_nodes"
            if (
                temporal
                and section not in ("nodes", "series", "process_series")
                or not temporal
                and section in ("series", "process_series")
            ):
                raise ValueError("section is not available for this readout kind")
            raw = record["payload"].get("raw_observation")
            section_available = section != "raw_nodes" or bool(raw and raw.get("complete"))
            array = {
                "nodes": "e.payload->'nodes'" if temporal else "e.payload->'activity_nodes'",
                "raw_nodes": "e.payload->'raw_nodes'",
                "structure_nodes": "e.payload->'structure'->'nodes'",
                "edges": "e.payload->'structure'->'edges'",
                "series": "e.payload->'series'",
                "process_series": "e.payload->'process'->'timeline'",
            }[section]
            node_filter = candidates_only and temporal and section == "nodes"
            if section in ("series", "edges", "process_series"):
                ordering = "ordinal"
            else:
                key = (
                    (
                        {
                            "id": "node_id",
                            "activation": "peak_activation",
                            "end-activation": "last_activation",
                            "decision-activation": "decision_activation",
                            "duration": "active_us",
                            "excess": "excess_integral",
                            "increase": "positive_change_peak",
                            "decrease": "negative_change_peak",
                            "variation": "total_activation_variation",
                            "onset": "first_positive_us",
                        }.get(order)
                        or ("decision_activation" if record["payload"].get("analysis_schema") else None)
                        or {"duration": "active_us", "activation-integral": "excess_integral"}.get(
                            record["payload"]["configuration"].get("ranking_mode"), "score"
                        )
                    )
                    if temporal
                    else (
                        "id"
                        if order == "id"
                        or order == "scientific"
                        and record["payload"]["configuration"]["display_order"] == "id"
                        else "activation"
                    )
                )
                ordering = (
                    f"(item->>'{key}')::numeric {'ASC' if key in ('id', 'node_id', 'first_positive_us') else 'DESC'} NULLS LAST,"
                    + ("(item->>'excess_integral')::numeric DESC NULLS LAST," if temporal else "")
                    + "ordinal"
                )
            rows = db.execute(
                f"SELECT item,ordinal,count(*) OVER() AS total,e.payload->'annotations'->COALESCE(item->>'node_id',item->>'id') AS annotations "
                f"FROM events e CROSS JOIN LATERAL jsonb_array_elements({array}) WITH ORDINALITY AS a(item,ordinal) "
                f"WHERE e.run_id=%s AND e.id=%s AND (NOT %s OR item->>'candidate'='true') ORDER BY {ordering} LIMIT %s OFFSET %s",
                (run_id, record_id, node_filter, limit + 1, offset),
            ).fetchall()
        return {
            "record": record,
            "section": section,
            "section_available": section_available,
            "rows": rows[:limit],
            "offset": offset,
            "limit": limit,
            "total": rows[0]["total"] if rows else None,
            "more": len(rows) > limit,
        }

    @app.get(base + "/{record_id}/export")
    def export_record(project: UUID, run_id: UUID, record_id: int, request: Request, format: str = "json"):
        access(request, project)
        app.state.db.get_run(project, run_id)
        if format not in ("json", "csv", "svg", "png", "pdf"):
            raise ValueError("unknown readout export format")
        with app.state.db.tx(project) as db:
            record = db.execute(
                "SELECT id,time_us,commit_revision,payload FROM events WHERE run_id=%s AND id=%s "
                "AND kind IN ('structural_readout','temporal_readout')",
                (run_id, record_id),
            ).fetchone()
        if record is None:
            raise NotFound()
        content = (
            response_figure(record["payload"], format)
            if format in ("svg", "png", "pdf")
            else (
                nodes_csv(record["payload"])
                if format == "csv"
                else json.dumps(record, ensure_ascii=False, default=str, allow_nan=False).encode()
            )
        )
        return Response(
            content,
            media_type={
                "csv": "text/csv",
                "json": "application/json",
                "svg": "image/svg+xml",
                "png": "image/png",
                "pdf": "application/pdf",
            }[format],
            headers={"Content-Disposition": f'attachment; filename="readout-{record_id}.{format}"'},
        )
