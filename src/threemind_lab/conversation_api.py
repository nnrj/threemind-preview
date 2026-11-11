"""Bounded observer feed. Visibility never controls admission, delivery, or readout."""

from __future__ import annotations

import csv
import io
import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

FILTER = """c.run_id=%(run)s AND c.id<=%(ceiling)s AND (%(before)s::bigint IS NULL OR c.id<%(before)s)
    AND (c.event_id IS NULL OR NOT EXISTS (SELECT 1 FROM events comparison
        WHERE comparison.id=c.event_id AND comparison.run_id=c.run_id AND comparison.payload->>'chat_primary'='false'))
    AND (%(after)s::bigint IS NULL OR c.id>%(after)s)
    AND (%(passive)s OR c.kind<>'structural_readout')
    AND (%(kind)s::text IS NULL OR c.kind=%(kind)s)
    AND (CASE WHEN c.kind='input' THEN
        c.source_class='manual' OR %(environment)s OR (%(triggering)s AND EXISTS (
            SELECT 1 FROM conversation_entries linked WHERE linked.run_id=c.run_id
                AND linked.kind='temporal_readout' AND linked.envelope_key=c.input_id::text
                AND linked.id<=%(ceiling)s AND (linked.source_class<>'environment' OR %(background)s)))
        ELSE c.source_class<>'environment' OR %(background)s END)"""


def page(database, project, run_id, *, ceiling=None, before=None, after=None, limit=20, **filters):
    if before is not None and after is not None:
        raise ValueError("use one conversation direction at a time")
    direction = "ASC" if after is not None else "DESC"
    with database.tx(project, repeatable=True) as db:
        # Both the membership ceiling and the observed current status belong to this query snapshot.
        revision = db.execute("SELECT revision FROM runs WHERE id=%s", (run_id,)).fetchone()["revision"]
        newest = db.execute(
            "SELECT COALESCE(max(id),0) AS id FROM conversation_entries WHERE run_id=%s", (run_id,)
        ).fetchone()["id"]
        ceiling = min(int(ceiling), newest) if ceiling is not None else newest
        args = dict(
            run=run_id, ceiling=ceiling, before=before, after=after, limit=limit + 1, **({"passive": True} | filters)
        )
        rows = db.execute(
            f"""WITH picked AS MATERIALIZED (
                SELECT c.* FROM conversation_entries c WHERE {FILTER} ORDER BY c.id {direction} LIMIT %(limit)s
            ) SELECT c.id::text,c.kind,c.input_id,c.event_id::text,c.source,c.source_class,c.reconstructed,
                c.indexed_at,c.envelope_key,
                linked.id AS linked_input_id,
                CASE WHEN i.id IS NULL THEN NULL ELSE jsonb_build_object(
                    'adapter_id',i.adapter_id,'status',i.status,'frame_count',i.frame_count,
                    'delivered_count',i.delivered_count,'filtered_count',i.filtered_count,
                    'created_at',i.created_at,'last_delivery_us',i.last_delivery_us::text,
                    'requested_time_us',i.requested_time_us::text,'payload_hash',i.payload_hash,
                    'text',left(i.payload->>'text',2000),'text_length',length(i.payload->>'text'),
                    'name',left(i.payload->>'name',240)) END AS stimulus,
                CASE WHEN e.id IS NULL THEN NULL ELSE jsonb_build_object(
                    'time_us',e.time_us::text,'commit_revision',e.commit_revision,
                    'display',e.payload->'chat','text',e.payload->>'text',
                    'start_us',e.payload->>'start_us','end_us',e.payload->>'end_us',
                    'classification',e.payload->>'classification','reason',e.payload->>'reason',
                    'analysis_id',e.payload->>'analysis_id','analysis_schema',e.payload->>'analysis_schema',
                    'ranking_time_us',e.payload->>'ranking_time_us',
                    'process',((e.payload->'process') - 'timeline'),
                    'analyses',(e.payload->'analyses' #- '{{pattern,nodes}}' #- '{{periodic,nodes}}'),
                    'censored',e.payload->'censored','overlapping_count',COALESCE(jsonb_array_length(e.payload->'overlapping_envelopes'),0),
                    'node_count',CASE WHEN e.kind='temporal_readout' THEN jsonb_array_length(e.payload->'nodes')
                        WHEN e.payload->'raw_observation'->>'complete'='true' THEN (e.payload->'raw_observation'->>'node_count')::integer
                        ELSE jsonb_array_length(e.payload->'activity_nodes') END,
                    'node_scope',CASE WHEN e.kind='temporal_readout' THEN 'sampled-node-aggregates'
                        WHEN e.payload->'raw_observation'->>'complete'='true' THEN 'all-source-nodes'
                        ELSE 'derived-nodes-only' END,
                    'candidate_count',e.payload->'candidate_count',
                    'structure_node_count',jsonb_array_length(e.payload->'structure'->'nodes'),
                    'structure_edge_count',jsonb_array_length(e.payload->'structure'->'edges'),
                    'recurrence_notice',e.payload->'structure'->'recurrence_notice') END AS readout
            FROM picked c LEFT JOIN input_envelopes i ON i.id=c.input_id AND i.run_id=c.run_id
                LEFT JOIN events e ON e.id=c.event_id AND e.run_id=c.run_id
                LEFT JOIN input_envelopes linked ON linked.run_id=c.run_id AND linked.id=CASE
                    WHEN c.envelope_key ~ '^[0-9a-fA-F]{{8}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{12}}$'
                    THEN c.envelope_key::uuid END
            ORDER BY c.id {direction}""",
            args,
        ).fetchall()
    return {
        "rows": rows[:limit],
        "more": len(rows) > limit,
        "next": rows[min(limit, len(rows)) - 1]["id"] if rows else None,
        "ceiling": str(ceiling),
        "query_revision": revision,
        "status_semantics": "current-at-query; membership-bounded-by-ceiling",
        "direction": "newer" if after is not None else "older",
    }


def export_index(database, project, run_id, selection, first, format):
    metadata = {
        "schema": "threemind-conversation-index/1",
        "run_id": str(run_id),
        "ceiling": first["ceiling"],
        "filters": selection,
        "status_semantics": first["status_semantics"],
        "evidence": "observer summaries; original inputs/readouts are exported at their own endpoints",
    }
    keys = [
        "id",
        "kind",
        "source",
        "input_id",
        "event_id",
        "linked_input_id",
        "reconstructed",
        "query_revision",
        "membership_ceiling",
        "filters",
        "status_semantics",
        "summary",
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    def csv_row(values):
        buffer.seek(0)
        buffer.truncate()
        # JSONL keeps exact text. CSV protects spreadsheet consumers of carrier names/text.
        writer.writerow(["'" + str(v) if str(v).lstrip().startswith(("=", "+", "-", "@")) else v for v in values])
        return buffer.getvalue()

    if format == "jsonl":
        yield json.dumps({"metadata": metadata}, ensure_ascii=False) + "\n"
    else:
        yield "\ufeff" + csv_row(keys)
    result = first
    while True:
        for row in result["rows"]:
            row["query_revision"] = result["query_revision"]
            if format == "jsonl":
                yield json.dumps(jsonable_encoder(row), ensure_ascii=False) + "\n"
            else:
                row["membership_ceiling"] = first["ceiling"]
                row["filters"] = json.dumps(selection, ensure_ascii=False)
                row["status_semantics"] = first["status_semantics"]
                row["summary"] = json.dumps(jsonable_encoder(row["stimulus"] or row["readout"]), ensure_ascii=False)
                yield csv_row([row.get(k, "") for k in keys])
        if not result["more"]:
            break
        result = page(
            database, project, run_id, ceiling=first["ceiling"], before=result["next"], limit=100, **selection
        )


def register_conversation_routes(app, access):
    base = "/api/v2/projects/{project}/runs/{run_id}/conversation"

    @app.get(base)
    def history(
        project: UUID,
        run_id: UUID,
        request: Request,
        environment: bool = False,
        triggering: bool = True,
        background: bool = False,
        passive: bool = True,
        kind: Literal["input", "temporal_readout", "structural_readout", "external_interpretation"] | None = None,
        before: int | None = Query(None, ge=1, le=9223372036854775807),
        after: int | None = Query(None, ge=0, le=9223372036854775807),
        ceiling: int | None = Query(None, ge=0, le=9223372036854775807),
        limit: int = Query(20, ge=1, le=100),
    ):
        access(request, project)
        app.state.db.get_run(project, run_id)
        return page(
            app.state.db,
            project,
            run_id,
            environment=environment,
            triggering=triggering,
            background=background,
            passive=passive,
            kind=kind,
            before=before,
            after=after,
            ceiling=ceiling,
            limit=limit,
        )

    @app.get(base + "/statuses")
    def statuses(project: UUID, run_id: UUID, request: Request, entry: Annotated[list[int], Query(max_length=320)]):
        access(request, project)
        app.state.db.get_run(project, run_id)
        if any(v < 1 or v > 9223372036854775807 for v in entry):
            raise ValueError("invalid conversation entry identity")
        with app.state.db.tx(project, read_only=True) as db:
            rows = db.execute(
                "SELECT c.id::text,i.status,i.frame_count,i.delivered_count,i.filtered_count,"
                "i.last_delivery_us::text FROM conversation_entries c JOIN input_envelopes i "
                "ON i.id=c.input_id AND i.run_id=c.run_id WHERE c.run_id=%s AND c.id=ANY(%s)",
                (run_id, entry),
            ).fetchall()
        return {"rows": rows}

    @app.get(base + "/{entry_id}/presentation")
    def presentation(
        project: UUID,
        run_id: UUID,
        entry_id: int,
        request: Request,
        order: Literal["activation", "id"] = "activation",
        scope: Literal["candidates", "active", "all"] | None = None,
        offset: int = Query(0, ge=0, le=10000000),
        limit: int = Query(128, ge=1, le=2000),
    ):
        from threemind_runtime.chat_readout import CHAT_VERSION, display_readout

        from .database import NotFound

        access(request, project)
        app.state.db.get_run(project, run_id)
        with app.state.db.tx(project, read_only=True) as db:
            row = db.execute(
                "SELECT e.payload FROM conversation_entries c JOIN events e ON e.id=c.event_id AND e.run_id=c.run_id "
                "WHERE c.run_id=%s AND c.id=%s AND c.kind IN ('structural_readout','temporal_readout')",
                (run_id, entry_id),
            ).fetchone()
        if row is None:
            raise NotFound()
        value = row["payload"]
        if value.get("chat", {}).get("schema") != CHAT_VERSION:
            return {"legacy": True, "display": value.get("chat"), "reason": "historical presentation is unchanged"}
        return {"legacy": False, "display": display_readout(value, limit, order=order, scope=scope, offset=offset)}

    @app.get(base + "/export")
    def export(
        project: UUID,
        run_id: UUID,
        request: Request,
        environment: bool = False,
        triggering: bool = True,
        background: bool = False,
        kind: Literal["input", "temporal_readout", "structural_readout", "external_interpretation"] | None = None,
        ceiling: int | None = Query(None, ge=0, le=9223372036854775807),
        format: Literal["jsonl", "csv"] = "jsonl",
        passive: bool = True,
    ):
        access(request, project)
        app.state.db.get_run(project, run_id)
        selection = {
            "environment": environment,
            "triggering": triggering,
            "background": background,
            "kind": kind,
            "passive": passive,
        }
        first = page(app.state.db, project, run_id, ceiling=ceiling, limit=100, **selection)
        return StreamingResponse(
            export_index(app.state.db, project, run_id, selection, first, format),
            media_type="application/x-ndjson" if format == "jsonl" else "text/csv",
            headers={"Content-Disposition": f'attachment; filename="conversation-index.{format}"'},
        )
