from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from pydantic import Field

from . import development, evolution
from .configuration import default_spec
from .evolution_protocol import SELECTION_METRICS, EvolutionProtocol, EvolutionRequest, seed_plan
from .protocols import StrictModel


class Seeds(StrictModel):
    generations: int = Field(ge=1, le=1000, strict=True)
    population_size: int = Field(ge=2, le=64, strict=True)
    evaluation_blocks: int = Field(ge=1, le=32, strict=True)
    verification_blocks: int = Field(ge=1, le=32, strict=True)
    seed: int = Field(ge=0, le=2**32 - 1, strict=True)


class Control(StrictModel):
    action: Literal["pause", "resume", "retry", "cancel"]
    expected_revision: int = Field(ge=1, strict=True)


class Export(StrictModel):
    operation_id: UUID


def validate(database, project, value, maximum):
    with database.tx(project) as db:
        source = development._version(db, value.initial_version_id) if value.initial_version_id else None
        return value.model_dump(mode="json") | {
            "development": development.validate_spec(value.development, source, maximum),
            "evaluation": development.validate_spec(value.evaluation, source, maximum),
        }


def register_evolution_routes(app, access):
    root = "/api/v2/projects/{project}/evolutions"

    @app.get(root + "/catalogue")
    def catalogue(project: UUID, request: Request):
        access(request, project)
        shared = default_spec() | {"clock": "unbounded", "duration_s": min(30, app.state.settings.max_run_seconds)}
        return {
            "defaults": {
                "schema_id": "threemind.evolution/1",
                "inheritance_rule": "threemind.birth/1",
                "selection_mode": "directed",
                "initial_version_id": None,
                "generations": 2,
                "population_size": 4,
                "survivor_count": 2,
                "development": shared,
                "evaluation": shared,
                "criteria": [],
                **seed_plan(2, 4, 3, 3, 20260907),
            },
            "metrics": [
                {"id": key, "label": value[0], "unit": value[1], "hint": value[2]}
                for key, value in SELECTION_METRICS.items()
            ],
            "shared_paths": ["config", *development.IDENTITY_PATHS],
            "schema": EvolutionProtocol.model_json_schema(),
        }

    @app.post(root + "/seeds")
    def seeds(project: UUID, request: Request, body: Seeds):
        access(request, project)
        return seed_plan(
            body.generations, body.population_size, body.evaluation_blocks, body.verification_blocks, body.seed
        )

    @app.post(root + "/validate")
    def check(project: UUID, request: Request, body: EvolutionProtocol):
        access(request, project)
        return {"valid": True, "protocol": validate(app.state.db, project, body, app.state.settings.max_run_seconds)}

    @app.get(root)
    def listing(
        project: UUID, request: Request, q: str = Query("", max_length=120), offset: int = Query(0, ge=0, le=100000)
    ):
        access(request, project)
        return evolution.listing(app.state.db, project, q, offset)

    @app.post(root, status_code=201)
    def create(project: UUID, request: Request, body: EvolutionRequest):
        actor = access(request, project, write=True)
        return evolution.create(app.state.db, project, actor["id"], body, app.state.settings.max_run_seconds)

    @app.get(root + "/{identity}")
    def detail(
        project: UUID,
        identity: UUID,
        request: Request,
        generation: int | None = Query(None, ge=0, le=999),
        offset: int = Query(0, ge=0, le=100000),
        stage: Literal["development", "evaluation", "verification"] | None = None,
    ):
        access(request, project)
        return evolution.detail(app.state.db, project, identity, generation, offset, stage)

    @app.get(root + "/{identity}/protocol")
    def declared(project: UUID, identity: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            row = evolution._campaign(db, identity)
            return {"id": row["id"], "protocol": row["protocol"], "protocol_hash": row["protocol_hash"]}

    @app.post(root + "/{identity}/controls")
    def control(project: UUID, identity: UUID, request: Request, body: Control):
        actor = access(request, project, write=True)
        evolution.control(app.state.db, project, identity, actor["id"], body.action, body.expected_revision)
        return evolution.detail(app.state.db, project, identity)

    @app.post(root + "/{identity}/exports", status_code=202)
    def export(project: UUID, identity: UUID, request: Request, body: Export):
        from .evolution_export import enqueue

        actor = access(request, project, write=True)
        return enqueue(app.state.db, project, identity, actor["id"], body.operation_id)

    @app.get(root + "/{identity}/exports")
    def exports(project: UUID, identity: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            evolution._campaign(db, identity, summary=True)
            return db.execute(
                "SELECT id,status,result,error,created_at FROM jobs WHERE kind='evolution_export' AND params->>'campaign_id'=%s ORDER BY created_at DESC,id DESC LIMIT 30",
                (str(identity),),
            ).fetchall()
