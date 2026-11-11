from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from fastapi.responses import StreamingResponse
from pydantic import Field, StrictStr, field_validator

from . import model_library as library
from .database import NotFound
from .protocols import StrictModel
from .state_captures import CaptureRequest


class Annotation(StrictModel):
    tags: list[StrictStr] = Field(default_factory=list, max_length=20)
    expected_metadata_revision: int = Field(ge=0, strict=True)

    @field_validator("tags")
    @classmethod
    def tags_valid(cls, values):
        tags = [value.strip() for value in values]
        if any(not value or len(value) > 48 for value in tags) or len(set(tags)) != len(tags):
            raise ValueError("标签应为 1～48 字符且不重复，最多 20 项。")
        return tags


class ModelAnnotation(Annotation):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=20000)
    archived: bool = Field(default=False, strict=True)

    @field_validator("name")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("名称不能全部为空白。")
        return value.strip()


class VersionAnnotation(Annotation):
    label: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=20000)
    pinned: bool = Field(default=False, strict=True)


class Cleanup(StrictModel):
    token: str = Field(min_length=64, max_length=64)
    confirm_name: str = Field(min_length=1, max_length=120)


def register_library_routes(app, access):
    base = "/api/v2/projects/{project}"
    run_base = base + "/runs/{run_id}"

    @app.post(run_base + "/state-captures", status_code=202)
    def capture(project: UUID, run_id: UUID, body: CaptureRequest, request: Request):
        from .state_captures import submit

        actor = access(request, project, write=True)
        return submit(app.state.db, project, run_id, actor["id"], body)

    @app.get(run_base + "/state-captures")
    def captures(
        project: UUID,
        run_id: UUID,
        request: Request,
        before: int | None = Query(None, ge=1),
        limit: int = Query(10, ge=1, le=100),
    ):
        from .state_captures import history

        access(request, project)
        return history(app.state.db, project, run_id, before=before, limit=limit)

    @app.get(base + "/model-library")
    def models(
        project: UUID,
        request: Request,
        q: str = Query("", max_length=160),
        tag: str = Query("", max_length=48),
        status: str = Query("", max_length=20),
        archived: Literal["active", "archived", "all"] = "active",
        offset: int = Query(0, ge=0, le=1000000),
        limit: int = Query(30, ge=1, le=100),
    ):
        access(request, project)
        return library.library(
            app.state.db, project, q=q, tag=tag, status=status, archived=archived, offset=offset, limit=limit
        )

    @app.patch(run_base + "/metadata")
    def edit(project: UUID, run_id: UUID, body: ModelAnnotation, request: Request):
        actor = access(request, project, write=True)
        return library.edit_run(app.state.db, project, run_id, actor, body)

    @app.get(run_base + "/metadata")
    def metadata(project: UUID, run_id: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            row = db.execute(f"SELECT {library.SUMMARY},description FROM runs WHERE id=%s", (run_id,)).fetchone()
        if row is None:
            raise NotFound()
        return row

    @app.get(run_base + "/metadata-export")
    def export_metadata(project: UUID, run_id: UUID, request: Request):
        access(request, project)
        app.state.db.get_run(project, run_id)
        return StreamingResponse(
            library.export_annotations(app.state.db, project, run_id),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="model-annotations-{run_id}.jsonl"'},
        )

    @app.get(run_base + "/versions")
    def versions(
        project: UUID,
        run_id: UUID,
        request: Request,
        q: str = Query("", max_length=160),
        tag: str = Query("", max_length=48),
        pinned: bool = False,
        before: int | None = Query(None, ge=0, le=9223372036854775807),
        limit: int = Query(30, ge=1, le=100),
    ):
        access(request, project)
        return library.versions(app.state.db, project, run_id, q=q, tag=tag, pinned=pinned, before=before, limit=limit)

    @app.get(run_base + "/versions/{checkpoint_id}")
    def version(project: UUID, run_id: UUID, checkpoint_id: UUID, request: Request):
        access(request, project)
        app.state.db.get_run(project, run_id)
        with app.state.db.tx(project) as db:
            row = db.execute(
                f"SELECT {library.VERSIONS} FROM checkpoints WHERE run_id=%s AND id=%s", (run_id, checkpoint_id)
            ).fetchone()
        if row is None:
            raise NotFound()
        return row

    @app.patch(run_base + "/versions/{checkpoint_id}/metadata")
    def annotate_version(project: UUID, run_id: UUID, checkpoint_id: UUID, body: VersionAnnotation, request: Request):
        actor = access(request, project, write=True)
        return library.edit_version(app.state.db, project, run_id, checkpoint_id, actor, body)

    @app.get(run_base + "/metadata-history")
    def history(
        project: UUID,
        run_id: UUID,
        request: Request,
        before: int | None = Query(None, ge=1, le=9223372036854775807),
        limit: int = Query(30, ge=1, le=100),
    ):
        access(request, project)
        app.state.db.get_run(project, run_id)
        with app.state.db.tx(project) as db:
            rows = db.execute(
                "SELECT * FROM model_metadata_history WHERE run_id=%s AND (%s::bigint IS NULL OR id<%s) ORDER BY id DESC LIMIT %s",
                (run_id, before, before, limit + 1),
            ).fetchall()
        return {
            "rows": rows[:limit],
            "more": len(rows) > limit,
            "next": rows[limit - 1]["id"] if len(rows) >= limit else None,
        }

    @app.get(run_base + "/lineage")
    def lineage(
        project: UUID,
        run_id: UUID,
        request: Request,
        offset: int = Query(0, ge=0, le=1000000),
        limit: int = Query(30, ge=1, le=100),
    ):
        access(request, project)
        return library.lineage(app.state.db, project, run_id, offset=offset, limit=limit)

    @app.get(run_base + "/cleanup-preview")
    def preview(project: UUID, run_id: UUID, request: Request):
        access(request, project)
        return library.preview_cleanup(app.state.db, project, run_id)

    @app.post(run_base + "/cleanup")
    def remove(project: UUID, run_id: UUID, body: Cleanup, request: Request):
        actor = access(request, project, write=True, owner=True)
        return library.cleanup(app.state.db, project, run_id, actor, body.token, body.confirm_name)

    @app.get(base + "/cleanup-history")
    def cleanup_history(
        project: UUID, request: Request, offset: int = Query(0, ge=0, le=1000000), limit: int = Query(30, ge=1, le=100)
    ):
        access(request, project, owner=True)
        with app.state.db.tx(project) as db:
            rows = db.execute(
                "SELECT * FROM model_cleanup_log ORDER BY created_at DESC,id LIMIT %s OFFSET %s", (limit + 1, offset)
            ).fetchall()
        return {"rows": rows[:limit], "more": len(rows) > limit, "offset": offset}
