from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from pydantic import Field

from threemind_runtime.ecology import EcologySettings
from threemind_runtime.ecology_rules import Hazard, ResourcePatch
from threemind_runtime.world_schema import default_world

from . import ecology_store
from .configuration import default_spec
from .database import NotFound
from .development import IDENTITY_PATHS
from .ecology_protocol import EcologyProtocol, EcologyRequest
from .protocols import StrictModel


class Control(StrictModel):
    action: Literal["pause", "resume", "retry", "cancel"]
    expected_revision: int = Field(ge=1, strict=True)


class Export(StrictModel):
    operation_id: UUID
    checkpoint_id: UUID | None = None
    include_models: bool = Field(default=False, strict=True)


def register_ecology_routes(app, access):
    root = "/api/v2/projects/{project}/ecologies"

    @app.get(root + "/catalogue")
    def catalogue(project: UUID, request: Request):
        access(request, project)
        return {
            "defaults": {
                "base": default_spec()
                | {
                    "environment": "world",
                    "world_protocol": default_world().model_dump(mode="json"),
                    "clock": "unbounded",
                    "duration_s": min(30, app.state.settings.max_run_seconds),
                },
                "ecology": EcologySettings().model_dump(mode="json"),
                "external_inputs": False,
                "initial_version_id": None,
            },
            "ecology_schema": EcologySettings.model_json_schema(),
            "inheritance_locked_paths": ["config", *IDENTITY_PATHS],
            "templates": {
                "patches": ResourcePatch(id="resource").model_dump(mode="json"),
                "hazards": Hazard(id="hazard").model_dump(mode="json"),
            },
        }

    @app.post(root + "/validate")
    def validate(project: UUID, request: Request, body: EcologyProtocol):
        access(request, project)
        with app.state.db.tx(project) as db:
            value = ecology_store.validate(db, body, app.state.settings.max_run_seconds)
        return {"valid": True, "protocol": value}

    @app.get(root)
    def listing(
        project: UUID, request: Request, q: str = Query("", max_length=120), offset: int = Query(0, ge=0, le=100000)
    ):
        access(request, project)
        with app.state.db.tx(project) as db:
            rows = db.execute(
                "SELECT id,name,objective,status,requested_action,revision,checkpoint_revision,time_us,summary,error,created_at FROM ecology_campaigns WHERE name ILIKE %s ORDER BY created_at DESC,id DESC LIMIT 31 OFFSET %s",
                (f"%{q}%", offset),
            ).fetchall()
        return {"rows": rows[:30], "more": len(rows) > 30}

    @app.post(root, status_code=201)
    def create(project: UUID, request: Request, body: EcologyRequest):
        actor = access(request, project, write=True)
        return ecology_store.create(app.state.db, project, actor["id"], body, app.state.settings.max_run_seconds)

    @app.get(root + "/{identity}")
    def detail(
        project: UUID,
        identity: UUID,
        request: Request,
        checkpoint_id: UUID | None = None,
        offset: int = Query(0, ge=0, le=100256),
        life: Literal["all", "body_alive", "body_failed", "core_dead"] = "all",
    ):
        access(request, project)
        with app.state.db.tx(project, repeatable=True) as db:
            row = ecology_store.campaign(db, identity)
            selected = checkpoint_id or row["checkpoint_id"]
            cp, members = None, []
            if selected:
                cp = db.execute(
                    "SELECT id,revision,time_us,state_hash,status,created_at,observation,(context->'ledger')-ARRAY['accounts','pools'] AS ledger,context->'pending_end_us' AS pending_end_us FROM ecology_checkpoints WHERE id=%s AND campaign_id=%s",
                    (selected, identity),
                ).fetchone()
                if cp is None:
                    raise NotFound()
                members = db.execute(
                    "SELECT m.*,c.checkpoint_id,c.state_hash,c.outcome,r.name FROM ecology_checkpoint_members c "
                    "JOIN ecology_members m USING(campaign_id,individual) JOIN runs r ON r.id=m.run_id "
                    "WHERE c.population_checkpoint_id=%s AND (%s='all' OR %s='body_alive' AND c.outcome->>'alive'='true' "
                    "OR %s='body_failed' AND c.outcome->>'alive'='false' OR %s='core_dead' AND c.outcome->>'core_life'='dead') "
                    "ORDER BY length(m.individual),m.individual LIMIT 31 OFFSET %s",
                    (selected, life, life, life, life, offset),
                ).fetchall()
                # The ledger schema has exactly one pool per historical individual
                # in independent mode, or one shared pool. Do not decode either
                # unbounded JSON collection merely to construct a page summary.
                cp["ledger"]["pool_count"] = (
                    1
                    if row["protocol"]["ecology"]["rules"]["habitat"] == "shared"
                    else cp["observation"]["population"]["individuals"]
                )
            return {
                "campaign": {k: v for k, v in row.items() if k not in ("protocol", "request_hash")},
                "checkpoint": cp,
                "members": members[:30],
                "more": len(members) > 30,
            }

    @app.get(root + "/{identity}/resource-pools")
    def resource_pools(
        project: UUID,
        identity: UUID,
        request: Request,
        checkpoint_id: UUID,
        after: str | None = Query(None, pattern=r"^(shared|n[0-9]+)$", max_length=20),
    ):
        access(request, project)
        with app.state.db.tx(project) as db:
            if (
                db.execute(
                    "SELECT id FROM ecology_checkpoints WHERE id=%s AND campaign_id=%s", (checkpoint_id, identity)
                ).fetchone()
                is None
            ):
                raise NotFound()
            rows = db.execute(
                "SELECT p.key AS habitat,p.value AS resources FROM ecology_checkpoints c "
                "CROSS JOIN LATERAL jsonb_each(c.context#>'{ledger,pools}') p "
                "WHERE c.id=%s AND c.campaign_id=%s AND (%s::text IS NULL OR (length(p.key),p.key)>(length(%s::text),%s::text)) "
                "ORDER BY length(p.key),p.key LIMIT 31",
                (checkpoint_id, identity, after, after, after),
            ).fetchall()
            return {"checkpoint_id": str(checkpoint_id), "rows": rows[:30], "more": len(rows) > 30}

    @app.get(root + "/{identity}/protocol")
    def protocol(project: UUID, identity: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            row = ecology_store.campaign(db, identity)
            return {"protocol": row["protocol"], "protocol_hash": row["protocol_hash"]}

    @app.get(root + "/{identity}/checkpoints")
    def checkpoints(project: UUID, identity: UUID, request: Request, before: int | None = Query(None, ge=1)):
        access(request, project)
        with app.state.db.tx(project) as db:
            ecology_store.campaign(db, identity)
            rows = db.execute(
                "SELECT id,revision,time_us,state_hash,status,created_at FROM ecology_checkpoints WHERE campaign_id=%s AND (%s::bigint IS NULL OR revision<%s) ORDER BY revision DESC LIMIT 31",
                (identity, before, before),
            ).fetchall()
        return {"rows": rows[:30], "more": len(rows) > 30}

    @app.get(root + "/{identity}/events")
    def events(
        project: UUID,
        identity: UUID,
        request: Request,
        after: int = Query(0, ge=0),
        kind: str | None = Query(None, max_length=80),
        individual: str | None = Query(None, pattern=r"^n[0-9]+$"),
        checkpoint_id: UUID | None = None,
    ):
        access(request, project)
        with app.state.db.tx(project, repeatable=True) as db:
            row = ecology_store.campaign(db, identity)
            selected = checkpoint_id or row["checkpoint_id"]
            cp = (
                db.execute(
                    "SELECT revision FROM ecology_checkpoints WHERE id=%s AND campaign_id=%s", (selected, identity)
                ).fetchone()
                if selected
                else None
            )
            if selected and cp is None:
                raise NotFound()
            rows = db.execute(
                "SELECT e.* FROM ecology_events e JOIN ecology_checkpoints c ON c.id=e.population_checkpoint_id WHERE e.campaign_id=%s AND e.id>%s AND c.revision<=%s AND (%s::text IS NULL OR e.kind=%s) "
                "AND (%s::text IS NULL OR e.individual=%s OR e.payload->>'parent'=%s OR (e.kind='resource_transfer' AND (e.payload->'amounts') ? %s)) ORDER BY e.id LIMIT 101",
                (
                    identity,
                    after,
                    cp["revision"] if cp else 0,
                    kind,
                    kind,
                    individual,
                    individual,
                    individual,
                    individual,
                ),
            ).fetchall()
        return {
            "rows": rows[:100],
            "more": len(rows) > 100,
            "next": rows[99]["id"] if len(rows) > 100 else None,
            "checkpoint_id": selected,
        }

    @app.get(root + "/{identity}/trajectory")
    def trajectory(
        project: UUID, identity: UUID, request: Request, after: int = Query(0, ge=0), checkpoint_id: UUID | None = None
    ):
        access(request, project)
        with app.state.db.tx(project, repeatable=True) as db:
            row = ecology_store.campaign(db, identity)
            selected = checkpoint_id or row["checkpoint_id"]
            cp = (
                db.execute(
                    "SELECT revision FROM ecology_checkpoints WHERE id=%s AND campaign_id=%s", (selected, identity)
                ).fetchone()
                if selected
                else None
            )
            if selected and cp is None:
                raise NotFound()
            rows = db.execute(
                "SELECT revision,time_us,observation->'population' AS metrics FROM ecology_checkpoints WHERE campaign_id=%s AND revision>%s AND revision<=%s ORDER BY revision LIMIT 1001",
                (identity, after, cp["revision"] if cp else 0),
            ).fetchall()
        return {
            "rows": rows[:1000],
            "more": len(rows) > 1000,
            "next": rows[999]["revision"] if len(rows) > 1000 else None,
            "checkpoint_id": selected,
        }

    @app.post(root + "/{identity}/controls")
    def control(project: UUID, identity: UUID, request: Request, body: Control):
        actor = access(request, project, write=True)
        return ecology_store.control(app.state.db, project, identity, actor["id"], body.action, body.expected_revision)

    @app.post(root + "/{identity}/exports", status_code=202)
    def export(project: UUID, identity: UUID, request: Request, body: Export):
        from .ecology_export import enqueue

        actor = access(request, project, write=True)
        return enqueue(app.state.db, project, identity, actor["id"], body)

    @app.get(root + "/{identity}/exports")
    def exports(project: UUID, identity: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            ecology_store.campaign(db, identity)
            return db.execute(
                "SELECT id,status,result,error,created_at,params->>'checkpoint_id' AS checkpoint_id FROM jobs WHERE kind='ecology_export' AND params->>'campaign_id'=%s ORDER BY created_at DESC LIMIT 30",
                (str(identity),),
            ).fetchall()
