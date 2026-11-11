from datetime import datetime
from uuid import UUID

from fastapi import Query, Request
from pydantic import Field

from . import auth, execution_limits, permissions, scheduling
from .protocols import StrictModel


class LimitEdit(StrictModel):
    limits: dict
    expected_revision: int = Field(strict=True, ge=0)


class LimitValidation(StrictModel):
    limits: dict
    project: bool = Field(default=False, strict=True)


def register_execution_routes(app, access):
    def admin(request, mutate=False):
        user = auth.identity(request, mutate=mutate)
        return permissions.require(app.state.db, user, 'system.write' if mutate else 'execution.read')

    @app.get("/api/v2/admin/execution")
    def management(request: Request):
        admin(request)
        return execution_limits.snapshot(app.state.db)

    @app.get("/api/v2/admin/execution/projects")
    def projects(request: Request, query: str = Query("", max_length=80), offset: int = Query(0, ge=0)):
        admin(request)
        return execution_limits.project_choices(app.state.db, query, offset)

    @app.get("/api/v2/admin/execution/projects/{project}")
    def project_management(project: UUID, request: Request):
        admin(request)
        return execution_limits.snapshot(app.state.db, project)

    @app.get("/api/v2/projects/{project}/execution")
    def usage(project: UUID, request: Request):
        access(request, project)
        return execution_limits.snapshot(app.state.db, project)

    @app.get("/api/v2/admin/execution/projects/{project}/jobs")
    @app.get("/api/v2/projects/{project}/execution/jobs")
    def jobs(
        project: UUID,
        request: Request,
        history: bool = False,
        run_id: UUID | None = None,
        before_time: datetime | None = None,
        before_id: UUID | None = None,
    ):
        if request.url.path.startswith("/api/v2/admin/"):
            admin(request)
        else:
            access(request, project)
        return scheduling.jobs(
            app.state.db, project, history=history, run_id=run_id, before_time=before_time, before_id=before_id
        )

    @app.get("/api/v2/admin/execution/projects/{project}/jobs/{job}/assignments")
    @app.get("/api/v2/projects/{project}/execution/jobs/{job}/assignments")
    def assignments(project: UUID, job: UUID, request: Request):
        if request.url.path.startswith("/api/v2/admin/"):
            admin(request)
        else:
            access(request, project)
        return scheduling.assignments(app.state.db, project, job)

    @app.post("/api/v2/admin/execution/validate")
    def validate(body: LimitValidation, request: Request):
        admin(request)
        model = execution_limits.ProjectLimits if body.project else execution_limits.GlobalLimits
        return {"limits": model.model_validate(body.limits).model_dump()}

    @app.post("/api/v2/admin/execution/limits")
    def global_edit(body: LimitEdit, request: Request):
        actor = admin(request, True)
        return execution_limits.save(app.state.db, actor["id"], body.limits, body.expected_revision)

    @app.post("/api/v2/admin/execution/projects/{project}/limits")
    def project_edit(project: UUID, body: LimitEdit, request: Request):
        actor = admin(request, True)
        return execution_limits.save(app.state.db, actor["id"], body.limits, body.expected_revision, project)
