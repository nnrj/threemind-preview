from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from pydantic import Field

from . import report_events, report_exports, report_sources, research_ai, research_documents
from .protocols import StrictModel
from .report_schema import CaptureSource, DocumentSpec, SaveDocument


class Archive(StrictModel):
    expected_revision: int = Field(ge=1, strict=True)
    archived: bool = Field(strict=True)


def register_report_routes(app, access):
    prefix = "/api/v2/projects/{project}"

    @app.post(prefix + "/research-generation/preview")
    def generation_preview(project: UUID, request: Request, body: research_ai.GenerationScope):
        actor = access(request, project, write=True)
        return research_ai.preview(app.state.db, project, actor["id"], body)

    @app.post(prefix + "/research-generation", status_code=202)
    def generation(project: UUID, request: Request, body: research_ai.GenerationRequest):
        actor = access(request, project, write=True)
        return research_ai.request(app.state.db, app.state.settings, project, actor["id"], body)

    @app.post(prefix + "/research-documents/{document}/exports", status_code=202)
    def export(project: UUID, document: UUID, request: Request, body: report_exports.ExportRequest):
        actor = access(request, project, write=True)
        return report_exports.request(app.state.db, project, actor["id"], document, body)

    @app.get(prefix + "/research-documents/{document}/exports")
    def exports(project: UUID, document: UUID, request: Request, offset: int = Query(0, ge=0, le=100000)):
        access(request, project)
        return report_exports.listing(app.state.db, project, document, offset)

    @app.get(prefix + "/report-catalog")
    def catalog(project: UUID, request: Request):
        access(request, project)
        return {
            "metrics": report_sources.CATALOG,
            "event_groups": report_events.GROUPS,
            "document_schema": DocumentSpec.model_json_schema(),
            "limits": {"source_rows": report_sources.MAX_ROWS, "source_bytes": report_sources.MAX_BYTES},
        }

    @app.get(prefix + "/report-analyses")
    def analyses(project: UUID, request: Request, study: UUID | None = None, offset: int = Query(0, ge=0, le=100000)):
        access(request, project)
        with app.state.db.tx(project) as db:
            rows = db.execute(
                "SELECT a.id,a.created_at,a.sha256,j.params,s.name AS study_name FROM artifacts a JOIN jobs j ON j.id=a.job_id "
                "LEFT JOIN studies s ON s.id::text=j.params->>'study_id' WHERE j.kind='analysis' AND j.status='done' "
                "AND a.id::text=j.result->>'artifact_id' AND (%s::text IS NULL OR j.params->>'study_id'=%s) "
                "ORDER BY a.created_at DESC,a.id DESC LIMIT 51 OFFSET %s",
                (str(study) if study else None, str(study) if study else None, offset),
            ).fetchall()
        return {"rows": rows[:50], "more": len(rows) > 50}

    @app.post(prefix + "/report-sources", status_code=202)
    def capture(project: UUID, request: Request, body: CaptureSource):
        actor = access(request, project, write=True)
        return report_sources.request(app.state.db, project, actor["id"], body)

    @app.get(prefix + "/report-sources")
    def sources(project: UUID, request: Request, offset: int = Query(0, ge=0, le=100000)):
        access(request, project)
        return report_sources.list_sources(app.state.db, project, offset=offset)

    @app.get(prefix + "/report-sources/{source}")
    def source(project: UUID, source: UUID, request: Request, compact: bool = True):
        access(request, project)
        return report_sources.get_source(app.state.db, project, source, compact=compact)

    @app.get(prefix + "/report-sources/{source}/rows")
    def rows(
        project: UUID,
        source: UUID,
        request: Request,
        after: int = Query(-1, ge=-1),
        limit: int = Query(100, ge=1, le=1000),
    ):
        access(request, project)
        return report_sources.data_rows(app.state.db, project, source, after=after, limit=limit)

    @app.get(prefix + "/report-sources/{source}/rows/{ordinal}")
    def full_row(project: UUID, source: UUID, ordinal: int, request: Request):
        access(request, project)
        return report_sources.full_row(app.state.db, project, source, ordinal)

    @app.delete(prefix + "/report-sources/{source}")
    def release(project: UUID, source: UUID, request: Request):
        actor = access(request, project, write=True)
        return report_sources.release(app.state.db, project, actor["id"], source)

    @app.get(prefix + "/report-sources/{source}/template")
    def defaults(project: UUID, source: UUID, request: Request, kind: Literal["record", "report"] = "record"):
        access(request, project)
        return research_documents.defaults(app.state.db, project, source, kind=kind)

    @app.post(prefix + "/research-documents/preview")
    def preview(project: UUID, request: Request, body: DocumentSpec):
        access(request, project)
        return research_documents.render(app.state.db, project, spec=body)

    @app.get(prefix + "/research-documents")
    def documents(
        project: UUID,
        request: Request,
        kind: Literal["record", "report"] = "record",
        query: str = Query("", max_length=200),
        offset: int = Query(0, ge=0, le=100000),
        archived: bool = False,
    ):
        access(request, project)
        return research_documents.listing(
            app.state.db, project, kind=kind, query=query, offset=offset, archived=archived
        )

    @app.put(prefix + "/research-documents/{document}")
    def save(project: UUID, document: UUID, request: Request, body: SaveDocument):
        actor = access(request, project, write=True)
        return research_documents.save(app.state.db, project, actor["id"], document, body)

    @app.get(prefix + "/research-documents/{document}")
    def get(project: UUID, document: UUID, request: Request, revision: int | None = Query(None, ge=1)):
        access(request, project)
        return research_documents.get(app.state.db, project, document, revision)

    @app.get(prefix + "/research-documents/{document}/versions")
    def versions(project: UUID, document: UUID, request: Request, before: int | None = Query(None, ge=1)):
        access(request, project)
        return research_documents.versions(app.state.db, project, document, before)

    @app.get(prefix + "/research-documents/{document}/render")
    def render(
        project: UUID,
        document: UUID,
        request: Request,
        revision: int | None = Query(None, ge=1),
        points: int = Query(500, ge=10, le=1000),
    ):
        access(request, project)
        return research_documents.render(app.state.db, project, document, revision=revision, points=points)

    @app.post(prefix + "/research-documents/{document}/archive")
    def archive(project: UUID, document: UUID, request: Request, body: Archive):
        actor = access(request, project, write=True)
        return research_documents.archive(
            app.state.db, project, actor["id"], document, body.expected_revision, body.archived
        )
