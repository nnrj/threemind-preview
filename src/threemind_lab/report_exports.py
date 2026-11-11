"""On-demand fixed-revision publication, with complete optional evidence streams."""

import zipfile
from datetime import UTC, datetime
from tempfile import SpooledTemporaryFile
from typing import Literal
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb
from pydantic import Field

from . import report_ecology, report_events, report_evolution, research_documents
from .ai_evidence import wire
from .database import Conflict
from .database_stream import closing_iterator, stream_rows
from .evidence import SPOOL_BYTES, EvidenceArchive
from .notebooks import digest
from .permissions import connection_access
from .protocols import StrictModel
from .report_sources import encode, ready

MAX_TABLE_CELLS = 100_000
MAX_PACKAGE_BYTES = 2 * 1024**3


def require_actor(db, project, actor):
    return connection_access(db, actor, project, action="reports.export", write=True)


class ExportRequest(StrictModel):
    operation_id: UUID
    revision: int = Field(ge=1, strict=True)
    format: Literal["markdown", "html", "docx", "pdf"] = "pdf"
    language: Literal["zh-CN", "en"] = "zh-CN"
    include_data: bool = Field(default=False, strict=True)
    table_rows: int = Field(default=100, ge=1, le=5000, strict=True)
    chart_points: int = Field(default=500, ge=10, le=1000, strict=True)


def request(database, project, actor, document_id, body):
    body = ExportRequest.model_validate(body)
    options = body.model_dump(mode="json", exclude={"operation_id"})
    fingerprint = digest({"document_id": str(document_id), "options": options})
    with database.tx(project) as db:
        require_actor(db, project, actor)
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("report-export:" + str(body.operation_id),))
        previous = db.execute(
            "SELECT id,job_id,request_hash FROM research_document_exports WHERE operation_id=%s", (body.operation_id,)
        ).fetchone()
        if previous:
            if previous["request_hash"] != fingerprint:
                raise Conflict("export operation ID reused with different options")
            return previous | {"replayed": True}
        document = research_documents.document(db, document_id, body.revision)
        export_id, job_id = uuid4(), uuid4()
        params = {"export_id": str(export_id), "storage_policy": database.blobs.freeze("export")}
        if report_evolution.used_by_document(db, document["spec"]):
            params["evolution_evidence"] = True
        if report_evolution.used_by_document(db, document["spec"], kinds=report_ecology.KINDS):
            params["ecology_evidence"] = True
        if report_evolution.used_by_document(db, document["spec"], kinds=("assessment",)):
            params["assessment_evidence"] = True
        db.execute(
            "INSERT INTO jobs(id,project_id,kind,params) VALUES(%s,%s,'report_export',%s)",
            (job_id, project, Jsonb(params)),
        )
        db.execute(
            "INSERT INTO research_document_exports(id,project_id,document_id,revision,actor_id,operation_id,request_hash,job_id,options) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                export_id,
                project,
                document_id,
                body.revision,
                actor,
                body.operation_id,
                fingerprint,
                job_id,
                Jsonb(options),
            ),
        )
        return {"id": export_id, "job_id": job_id, "replayed": False}


def listing(database, project, document_id, offset=0):
    with database.tx(project) as db:
        research_documents.document(db, document_id)
        rows = db.execute(
            "SELECT e.id,e.revision,e.options,e.created_at,e.job_id,j.status,j.error,j.result FROM research_document_exports e "
            "JOIN jobs j ON j.id=e.job_id WHERE e.document_id=%s ORDER BY e.created_at DESC,e.id DESC LIMIT 21 OFFSET %s",
            (document_id, offset),
        ).fetchall()
        return {"rows": rows[:20], "more": len(rows) > 20}


def prepare(database, project, export):
    options = export["options"]
    with database.tx(project) as db:
        require_actor(db, project, export["actor_id"])
        document = research_documents.document(db, export["document_id"], export["revision"])
        rendered = research_documents.render_in_transaction(db, document["spec"], points=options["chart_points"])
        sources = {key: ready(db, key) for key in rendered["sources"]}
        references, cells = {}, 0

        def complete(block):
            nonlocal cells
            if block["type"] == "record_block":
                key = f"{block['record_id']}-r{block['revision']}"
                references[key] = fixed_document(research_documents.document(db, block["record_id"], block["revision"]))
                complete(block["content"])
            elif block["type"] == "table":
                count = min(block["row_count"], options["table_rows"])
                events = sources[block["source"]]["kind"] == "events"
                cells += count * (8 if events else len(block["metrics"]) + 3)
                if cells > MAX_TABLE_CELLS:
                    raise ValueError("正文表格超过 100000 单元格；请减少正文行数，并在证据包中附带完整数据。")
                fields = report_events.PREVIEW_FIELDS if events else report_events.FULL_FIELDS
                block["rows"] = db.execute(
                    f"SELECT {fields} FROM report_source_rows WHERE source_id=%s ORDER BY ordinal LIMIT %s",
                    (block["source"], options["table_rows"]),
                ).fetchall()
                block["preview_limit"] = options["table_rows"]

        for block in rendered["blocks"]:
            complete(block)
        return fixed_document(document), wire(rendered), wire(sources), references


def fixed_document(row):
    # A fixed revision must not pick up later title, archive or head-revision metadata.
    result = {
        key: row[key]
        for key in (
            "id",
            "project_id",
            "kind",
            "actor_id",
            "ai_call_id",
            "import_ai_generated",
            "spec",
            "review",
            "content_hash",
            "version_created_at",
            "content_revision",
        )
    }
    return wire(result | {"revision": row["content_revision"], "title": row["spec"]["title"]})


def execute(database, job):
    from .report_publication import publication

    project = job["project_id"]
    with database.tx(project) as db:
        export = db.execute(
            "SELECT * FROM research_document_exports WHERE id=%s AND job_id=%s", (job["params"]["export_id"], job["id"])
        ).fetchone()
        if not export:
            raise ValueError("fixed document export request is unavailable")
    document, rendered, sources, references = prepare(database, project, export)
    options = export["options"]
    # CPU-heavy layout is outside the database transaction. No live model advances.
    with (
        publication(document, rendered, options) as result,
        SpooledTemporaryFile(max_size=SPOOL_BYTES, mode="w+b") as package,
    ):
        name, media_type, content, assets, warnings = result
        metadata = {
            "schema": "threemind.research-export/1",
            "export_id": str(export["id"]),
            "requested_at": export["created_at"].isoformat(),
            "generated_at": datetime.now(UTC).isoformat(),
            "document_id": str(export["document_id"]),
            "revision": export["revision"],
            "document_hash": document["content_hash"],
            "options": options,
            "sources": {key: value["content_hash"] for key, value in sources.items()},
            "warnings": warnings,
            "table_scope": "first selected rows in ordinal order; omitted rows are not zero or absent observations",
            "chart_scope": "all captured samples or explicitly labelled display bins; ranges are not confidence intervals",
        }
        with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            evidence = EvidenceArchive(archive)
            evidence.write(name, iter(lambda: content.read(1024 * 1024), b""))
            evidence.json("document.json", document)
            evidence.json("render.json", rendered)
            for key, value in references.items():
                evidence.json(f"records/{key}.json", value)
            for path, raw in assets.items():
                evidence.bytes(path, raw)
            budget = sum(evidence.sizes.values())
            with database.tx(project) as db:
                for key in sources:
                    # One full manifest at a time; never decode every analysis pair tree in memory.
                    full = db.execute(
                        "SELECT manifest::text AS content FROM report_sources WHERE id=%s", (key,)
                    ).fetchone()["content"]
                    evidence.bytes(f"sources/{key}/manifest.json", full.encode())
                    del full
                    budget += evidence.sizes[f"sources/{key}/manifest.json"]
                    if budget > MAX_PACKAGE_BYTES:
                        raise ValueError("证据包超过 2 GiB 导出预算；请拆分来源。")
                    if not options["include_data"]:
                        continue

                    # The canonical source hash can be recomputed from these rows + manifest.
                    def rows(source_id=key):
                        nonlocal budget
                        records = stream_rows(
                            db,
                            "SELECT ordinal,time_us::text,label,quality,values,provenance "
                            "FROM report_source_rows WHERE source_id=%s ORDER BY ordinal",
                            (source_id,),
                            batch=1000,
                        )
                        with closing_iterator(records) as items:
                            for item in items:
                                raw = encode(item) + b"\n"
                                budget += len(raw)
                                if budget > MAX_PACKAGE_BYTES:
                                    raise ValueError("证据包超过 2 GiB 导出预算；请拆分来源或关闭完整数据附件。")
                                yield raw

                    evidence.write(f"sources/{key}/rows.jsonl", rows())
                require_actor(db, project, export["actor_id"])
            evidence.json("manifest.json", metadata | {"files": evidence.files, "file_bytes": evidence.sizes})
        with database.tx(project) as db:
            require_actor(db, project, export["actor_id"])
            database.fence(db, job)
        content.seek(0)
        main = database.put_artifact_stream(job, name, media_type, content, metadata)
        package.seek(0)
        bundle = database.put_artifact_stream(job, "research-evidence.zip", "application/zip", package, metadata)
        return {
            "artifact_id": str(main["id"]),
            "bundle_artifact_id": str(bundle["id"]),
            "revision": export["revision"],
            "document_hash": document["content_hash"],
            "sha256": main["sha256"],
            "bundle_sha256": bundle["sha256"],
            "warnings": warnings,
        }
