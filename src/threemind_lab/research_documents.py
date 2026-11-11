"""Versioned scientific authoring: measurements stay in referenced evidence."""

from uuid import UUID

from psycopg.types.json import Jsonb

from . import report_events
from .ai_providers import require_actor
from .database import Conflict, NotFound
from .notebooks import digest
from .report_schema import (
    AssessmentSummary,
    Chart,
    Commentary,
    DataTable,
    DocumentSpec,
    Fact,
    RecordBlock,
    SaveDocument,
)
from .report_sources import display_manifest, ready


def document(db, document_id, revision=None):
    row = db.execute(
        "SELECT d.*,v.spec,v.review,v.actor_id,v.ai_call_id,v.import_ai_generated,v.content_hash,v.revision AS content_revision,"
        "v.created_at AS version_created_at FROM research_documents d JOIN research_document_versions v "
        "ON v.document_id=d.id AND v.revision=coalesce(%s,d.revision) WHERE d.id=%s",
        (revision, document_id),
    ).fetchone()
    if not row:
        raise NotFound("research document revision is unavailable")
    return row


def validate_spec(db, value):
    spec = DocumentSpec.model_validate(value)
    sources = {source_id: ready(db, source_id) for source_id in spec.sources}
    references = {}
    for block in spec.blocks:
        if isinstance(block, Commentary):
            continue
        if isinstance(block, RecordBlock):
            record = document(db, block.record_id, block.revision)
            if record["kind"] != "record" or not any(b["id"] == block.block_id for b in record["spec"]["blocks"]):
                raise ValueError("select an existing block of a fixed experiment record revision")
            references[(block.record_id, block.revision, block.block_id)] = record
            continue
        source = sources[block.source]
        if isinstance(block, AssessmentSummary):
            if source["kind"] != "assessment":
                raise ValueError("规则判定摘要只能引用固定的独立评估来源。")
            continue
        selected = block.metrics if isinstance(block, DataTable) else [block.metric]
        if not set(selected) <= source["manifest"]["metrics"].keys():
            raise ValueError("a block selects a metric not captured in its source")
        if isinstance(block, Chart):
            if source["kind"] == "analysis":
                if block.analysis_metric not in {r["metric"] for r in source["manifest"]["analysis"]["metrics"]}:
                    raise ValueError("select one analysis endpoint; unrelated measurement units must not be merged")
            elif block.analysis_metric is not None:
                raise ValueError("only analysis charts select an analysis endpoint")
            allowed = {
                "trajectory": ("line", "scatter", "histogram"),
                "nodes": ("histogram",),
                "edges": ("histogram",),
                "analysis": ("bar",),
                "events": ("bar",),
                "evolution": ("histogram",),
                "ecology_trajectory": ("line", "scatter", "histogram"),
                "ecology_members": ("histogram",),
                "assessment": ("histogram",),
                "temporal_windows": ("histogram", "bar"),
                "temporal_nodes": ("histogram", "bar"),
                "temporal_series": ("line", "scatter"),
            }[source["kind"]]
            if block.chart not in allowed:
                raise ValueError("this chart type is not meaningful for the selected evidence kind")
        if isinstance(block, Fact) and source["kind"] == "analysis":
            raise ValueError(
                "use an analysis table or chart; averaging unrelated endpoints is not a valid factual summary"
            )
        if isinstance(block, Fact) and source["kind"] == "events" and block.statistic != "count":
            raise ValueError("event facts count log entries; event counters are not continuous measurements")
    return spec, sources, references


def save(database, project, actor, document_id, body, *, transaction=None):
    from contextlib import nullcontext

    body = SaveDocument.model_validate(body)
    fingerprint = digest(body.model_dump(mode="json"))
    with database.tx(project) if transaction is None else nullcontext(transaction) as db:
        require_actor(db, project, actor)
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("research-document:" + str(document_id),))
        previous = db.execute(
            "SELECT revision,request_hash,content_hash FROM research_document_versions WHERE document_id=%s AND operation_id=%s",
            (document_id, body.operation_id),
        ).fetchone()
        if previous:
            if previous["request_hash"] != fingerprint:
                raise Conflict("document operation ID reused with different content")
            return {"id": document_id, **previous, "replayed": True}
        head = db.execute("SELECT * FROM research_documents WHERE id=%s FOR UPDATE", (document_id,)).fetchone()
        if (head["revision"] if head else 0) != body.expected_revision:
            raise Conflict("document changed; keep this draft and reload or save a copy")
        if head and (head["archived_at"] or head["kind"] != body.spec.kind):
            raise Conflict("restore the document before editing; document type cannot change")
        import_ai_generated = bool(
            head
            and db.execute(
                "SELECT import_ai_generated FROM research_document_versions WHERE document_id=%s AND revision=%s",
                (document_id, head["revision"]),
            ).fetchone()["import_ai_generated"]
        )
        spec, sources, references = validate_spec(db, body.spec)
        if body.ai_call_id:
            call = db.execute("SELECT purpose,status,result FROM ai_calls WHERE id=%s", (body.ai_call_id,)).fetchone()
            if not call or call["status"] != "completed" or call["purpose"] != spec.kind:
                raise ValueError("AI provenance must reference a completed generation of this document type")
        revision = body.expected_revision + 1
        raw = spec.model_dump(mode="json")
        content_hash = digest(
            {
                "spec": raw,
                "review": body.review,
                "ai_call_id": str(body.ai_call_id) if body.ai_call_id else None,
                "sources": {str(k): v["content_hash"] for k, v in sources.items()},
                "records": {f"{k[0]}:{k[1]}:{k[2]}": v["content_hash"] for k, v in references.items()},
            }
            | ({"import_ai_generated": True} if import_ai_generated else {})
        )
        if head:
            db.execute(
                "UPDATE research_documents SET title=%s,revision=%s,updated_at=now() WHERE id=%s",
                (spec.title, revision, document_id),
            )
        else:
            db.execute(
                "INSERT INTO research_documents(id,project_id,kind,title,revision) VALUES(%s,%s,%s,%s,%s)",
                (document_id, project, spec.kind, spec.title, revision),
            )
        db.execute(
            "INSERT INTO research_document_versions(project_id,document_id,revision,actor_id,operation_id,request_hash,spec,review,ai_call_id,content_hash,import_ai_generated) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                project,
                document_id,
                revision,
                actor,
                body.operation_id,
                fingerprint,
                Jsonb(raw),
                body.review,
                body.ai_call_id,
                content_hash,
                import_ai_generated,
            ),
        )
        for source_id in sources:
            db.execute(
                "INSERT INTO research_document_sources VALUES(%s,%s,%s,%s)", (project, document_id, revision, source_id)
            )
        for record_id, record_revision, block_id in references:
            db.execute(
                "INSERT INTO research_document_refs VALUES(%s,%s,%s,%s,%s,%s)",
                (project, document_id, revision, record_id, record_revision, block_id),
            )
        return {"id": document_id, "revision": revision, "content_hash": content_hash, "replayed": False}


def get(database, project, document_id, revision=None):
    with database.tx(project) as db:
        return document(db, document_id, revision)


def listing(database, project, *, kind="record", query="", offset=0, archived=False):
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    with database.tx(project) as db:
        rows = db.execute(
            "SELECT d.*,v.review,v.ai_call_id,v.import_ai_generated,v.content_hash FROM research_documents d JOIN research_document_versions v "
            "ON v.document_id=d.id AND v.revision=d.revision WHERE d.kind=%s AND (d.archived_at IS NOT NULL)=%s "
            "AND d.title ILIKE %s ORDER BY d.updated_at DESC,d.id DESC LIMIT 51 OFFSET %s",
            (kind, archived, f"%{escaped}%", offset),
        ).fetchall()
        return {"rows": rows[:50], "more": len(rows) > 50}


def versions(database, project, document_id, before=None):
    with database.tx(project) as db:
        document(db, document_id)
        rows = db.execute(
            "SELECT revision,spec->>'title' AS title,review,actor_id,ai_call_id,import_ai_generated,content_hash,created_at FROM research_document_versions "
            "WHERE document_id=%s AND (%s::bigint IS NULL OR revision<%s) ORDER BY revision DESC LIMIT 51",
            (document_id, before, before),
        ).fetchall()
        return {"rows": rows[:50], "more": len(rows) > 50}


def archive(database, project, actor, document_id, revision, archived):
    with database.tx(project) as db:
        require_actor(db, project, actor)
        row = db.execute("SELECT * FROM research_documents WHERE id=%s FOR UPDATE", (document_id,)).fetchone()
        if not row:
            raise NotFound()
        if row["revision"] != revision:
            raise Conflict("document changed; reload before archiving")
        db.execute(
            "UPDATE research_documents SET archived_at=CASE WHEN %s THEN now() ELSE NULL END WHERE id=%s",
            (archived, document_id),
        )
        db.execute(
            "INSERT INTO audit(user_id,action,resource) VALUES(%s,%s,%s)",
            (actor, "research_document.archive" if archived else "research_document.restore", str(document_id)),
        )
        return {"id": document_id, "archived": archived}


def summary(db, source_id, metric, label=None):
    stats = db.execute(
        "SELECT count(*) AS total,count(values->>%s) AS count,min((values->>%s)::double precision) AS minimum,"
        "max((values->>%s)::double precision) AS maximum,avg((values->>%s)::numeric)::double precision AS mean "
        "FROM report_source_rows WHERE source_id=%s AND (%s::text IS NULL OR label=%s)",
        (metric, metric, metric, metric, source_id, label, label),
    ).fetchone()
    # First/last mean the boundary sample, including an explicitly missing value.
    first = db.execute(
        "SELECT values->%s AS value FROM report_source_rows WHERE source_id=%s AND (%s::text IS NULL OR label=%s) ORDER BY ordinal LIMIT 1",
        (metric, source_id, label, label),
    ).fetchone()
    last = db.execute(
        "SELECT values->%s AS value FROM report_source_rows WHERE source_id=%s AND (%s::text IS NULL OR label=%s) ORDER BY ordinal DESC LIMIT 1",
        (metric, source_id, label, label),
    ).fetchone()
    return stats | {
        "missing": stats["total"] - stats["count"],
        "first": first["value"] if first else None,
        "last": last["value"] if last else None,
    }


def chart_data(db, source, block, *, points=500):
    metric, source_id = block.metric, source["id"]
    if source["kind"] == "events":
        counts = report_events.counts(db, source_id)
        return {
            "statistics": {"count": source["row_count"], "missing": 0},
            "unit": "log entries",
            "source_hash": source["content_hash"],
            "method": "all-events-by-kind-and-phase/1",
            "rows": [{"label": r["label"], "phase": r["phase"], "value": r["count"]} for r in counts],
        }
    stats = summary(db, source_id, metric, block.analysis_metric)
    base = {"statistics": stats, "unit": source["manifest"]["metrics"][metric], "source_hash": source["content_hash"]}
    if block.chart == "histogram":
        low, high = stats["minimum"], stats["maximum"]
        if low is None:
            return base | {"rows": [], "method": "complete-distribution/1"}
        if high == low:
            rows = [{"lower": low, "upper": high, "count": stats["count"]}]
        else:
            rows = db.execute(
                "SELECT least(%s-1,floor(((values->>%s)::numeric-%s)/(%s-%s)*%s)::int) AS bin,count(*) AS count "
                "FROM report_source_rows WHERE source_id=%s AND values->>%s IS NOT NULL GROUP BY bin ORDER BY bin",
                (block.bins, metric, low, high, low, block.bins, source_id, metric),
            ).fetchall()
            counts = {row["bin"]: row["count"] for row in rows}
            rows = [
                {
                    "lower": low + (high - low) * i / block.bins,
                    "upper": low + (high - low) * (i + 1) / block.bins,
                    "count": counts.get(i, 0),
                }
                for i in range(block.bins)
            ]
        return base | {"rows": rows, "method": "complete-distribution/1"}
    if source["row_count"] <= points or block.chart == "bar":
        rows = db.execute(
            "SELECT ordinal,time_us,label,quality,values->%s AS value,values,provenance FROM report_source_rows WHERE source_id=%s AND (%s::text IS NULL OR label=%s) ORDER BY ordinal",
            (metric, source_id, block.analysis_metric, block.analysis_metric),
        ).fetchall()
        return base | {"rows": rows, "method": "all-captured-rows/1"}
    rows = db.execute(
        "SELECT floor(ordinal::numeric*%s/%s)::int AS bin,min(time_us)::text AS from_us,max(time_us)::text AS through_us,"
        "avg((values->>%s)::numeric)::double precision AS value,min((values->>%s)::double precision) AS minimum,"
        "max((values->>%s)::double precision) AS maximum,count(*) AS total,count(values->>%s) AS count "
        "FROM report_source_rows WHERE source_id=%s GROUP BY bin ORDER BY bin",
        (points, source["row_count"], metric, metric, metric, metric, source_id),
    ).fetchall()
    return base | {
        "rows": rows,
        "method": "ordinal-bin-sample-mean-min-max/1",
        "notice": "display bins only; range is not a confidence interval; complete rows remain available",
    }


def render_in_transaction(db, spec, *, points=500):
    spec, sources, references = validate_spec(db, spec)
    blocks = []
    manifests = {
        str(k): {"manifest": display_manifest(v["manifest"]), "content_hash": v["content_hash"]}
        for k, v in sources.items()
    }
    for block in spec.blocks:
        raw = block.model_dump(mode="json")
        if isinstance(block, RecordBlock):
            record = references[(block.record_id, block.revision, block.block_id)]
            selected = next(b for b in record["spec"]["blocks"] if b["id"] == block.block_id)
            rendered = render_in_transaction(db, record["spec"] | {"blocks": [selected]}, points=points)
            manifests.update(rendered["sources"])
            blocks.append(
                raw
                | {
                    "content": rendered["blocks"][0],
                    "record_hash": record["content_hash"],
                    "record_ai_call_id": str(record["ai_call_id"]) if record["ai_call_id"] else None,
                    "record_import_ai_generated": bool(record.get("import_ai_generated")),
                }
            )
        elif isinstance(block, Commentary):
            blocks.append(raw | {"evidence_role": "author interpretation; not a verified measurement"})
        elif isinstance(block, AssessmentSummary):
            source = sources[block.source]
            blocks.append(raw | {"assessment": source["manifest"]["assessment"], "source_hash": source["content_hash"]})
        elif isinstance(block, Chart):
            blocks.append(raw | {"data": chart_data(db, sources[block.source], block, points=points)})
        elif isinstance(block, Fact):
            values = summary(db, block.source, block.metric)
            blocks.append(
                raw
                | {
                    "value": values[block.statistic],
                    "statistics": values,
                    "unit": sources[block.source]["manifest"]["metrics"][block.metric],
                }
            )
        else:
            fields = (
                report_events.PREVIEW_FIELDS if sources[block.source]["kind"] == "events" else report_events.FULL_FIELDS
            )
            rows = db.execute(
                f"SELECT {fields} FROM report_source_rows WHERE source_id=%s ORDER BY ordinal LIMIT 100",
                (block.source,),
            ).fetchall()
            blocks.append(
                raw
                | {
                    "rows": [{**r, "values": {m: r["values"].get(m) for m in block.metrics}} for r in rows],
                    "row_count": sources[block.source]["row_count"],
                    "preview_limit": 100,
                    "source_kind": sources[block.source]["kind"],
                }
            )
    return {
        "schema": "threemind.research-render/1",
        "spec": spec.model_dump(mode="json"),
        "blocks": blocks,
        "sources": manifests,
    }


def render(database, project, document_id=None, *, revision=None, spec=None, points=500):
    with database.tx(project) as db:
        row = document(db, document_id, revision) if document_id else None
        return render_in_transaction(db, row["spec"] if row else spec, points=points) | {
            "document_id": str(document_id) if document_id else None,
            "revision": row["content_revision"] if row else None,
            "content_hash": row["content_hash"] if row else None,
            "review": row["review"] if row else "draft",
            "ai_call_id": str(row["ai_call_id"]) if row and row["ai_call_id"] else None,
            "import_ai_generated": bool(row and row.get("import_ai_generated")),
        }


def defaults(database, project, source_id, *, kind="record"):
    with database.tx(project) as db:
        row = ready(db, source_id)
        source = str(UUID(str(source_id)))
        metrics = row["selection"]["metrics"]
        blocks = [{"id": "purpose", "type": "commentary", "section": "purpose", "markdown": ""}]
        preferred = (
            [
                m
                for m in ("mean_activation", "edges", "mean_weight", "energy_reserve")
                if m in metrics and row["manifest"]["coverage"]["missing"][m] < row["row_count"]
            ]
            if row["kind"] == "trajectory"
            else metrics[:2]
        )
        if row["kind"] == "ecology_trajectory":
            preferred = [
                metric for metric in ("living_bodies", "births", "resource_remaining") if metric in metrics
            ] or metrics[:2]
        elif row["kind"] == "ecology_members":
            preferred = [metric for metric in ("body_reserve", "offspring_count") if metric in metrics] or metrics[:2]
        elif row["kind"] == "assessment":
            preferred = list(
                dict.fromkeys(
                    r["criterion"]["metric"]
                    for r in row["manifest"]["assessment"]["criteria"]
                    if r["criterion"]["metric"] in metrics
                )
            )[:3]
            blocks.append({"id": "assessment", "type": "assessment_summary", "source": source})
        elif row["kind"] == "temporal_windows":
            preferred = [m for m in ("convergence_seconds", "observed_seconds") if m in metrics] or metrics[:2]
        elif row["kind"] == "temporal_nodes":
            preferred = [m for m in ("score", "active_seconds") if m in metrics] or metrics[:2]
        if row["kind"] == "analysis":
            blocks.append({"id": "analysis", "type": "table", "source": source, "metrics": metrics, "title": ""})
        elif row["kind"] == "events":
            blocks.extend(
                [
                    {
                        "id": "event_count",
                        "type": "fact",
                        "source": source,
                        "metric": "event_count",
                        "statistic": "count",
                    },
                    {"id": "event_types", "type": "chart", "source": source, "metric": "event_count", "chart": "bar"},
                    {"id": "event_log", "type": "table", "source": source, "metrics": ["event_count"]},
                ]
            )
        else:
            for i, metric in enumerate(preferred):
                blocks.append(
                    {
                        "id": f"chart_{i}",
                        "type": "chart",
                        "source": source,
                        "metric": metric,
                        "chart": "line"
                        if row["kind"] in ("trajectory", "ecology_trajectory", "temporal_series")
                        else "bar"
                        if row["kind"] == "temporal_nodes"
                        else "histogram",
                    }
                )
            blocks.append({"id": "data", "type": "table", "source": source, "metrics": metrics[:8]})
        blocks.append({"id": "limitations", "type": "commentary", "section": "limitations", "markdown": ""})
        return DocumentSpec.model_validate(
            {
                "kind": kind,
                "title": row["provenance"].get("run_name") or row["provenance"].get("batch_name") or "Research record",
                "sources": [source],
                "blocks": blocks,
            }
        ).model_dump(mode="json")
