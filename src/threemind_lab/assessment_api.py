from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from pydantic import Field

from . import assessments
from .assessment_protocol import AssessmentProtocol, AssessmentRequest
from .evolution_protocol import SELECTION_METRICS
from .protocols import StrictModel


class Control(StrictModel):
    operation_id: UUID
    expected_revision: int = Field(ge=1, strict=True)
    action: Literal["pause", "resume", "retry", "cancel"]


def register_assessment_routes(app, access):
    root = "/api/v2/projects/{project}/assessments"

    @app.get(root + "/catalogue")
    def catalogue(project: UUID, request: Request):
        access(request, project)
        return {
            "schema": AssessmentProtocol.model_json_schema(),
            "metrics": [{"id": key, "label": v[0], "unit": v[1], "hint": v[2]} for key, v in SELECTION_METRICS.items()],
        }

    @app.post(root + "/validate")
    def validate(project: UUID, request: Request, body: AssessmentProtocol):
        access(request, project)
        with app.state.db.tx(project) as db:
            return {"valid": True, "protocol": assessments.validate(db, body, app.state.settings.max_run_seconds)}

    @app.get(root)
    def listing(
        project: UUID, request: Request, q: str = Query("", max_length=120), offset: int = Query(0, ge=0, le=100000)
    ):
        access(request, project)
        return assessments.listing(app.state.db, project, q, offset)

    @app.post(root, status_code=201)
    def create(project: UUID, request: Request, body: AssessmentRequest):
        actor = access(request, project, write=True)
        return assessments.create(app.state.db, project, actor["id"], body, app.state.settings.max_run_seconds)

    @app.get(root + "/{identity}")
    def detail(project: UUID, identity: UUID, request: Request):
        access(request, project)
        return assessments.detail(app.state.db, project, identity)

    @app.post(root + "/{identity}/controls")
    def control(project: UUID, identity: UUID, request: Request, body: Control):
        actor = access(request, project, write=True)
        return assessments.control(app.state.db, project, actor["id"], identity, body)
