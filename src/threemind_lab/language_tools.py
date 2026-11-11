"""Language sessions own normal Core checkpoints; language models remain optional external tools."""

import hashlib
import importlib.util
import json
from uuid import UUID, uuid4

from fastapi import Request
from psycopg.types.json import Jsonb
from pydantic import Field

from threemind_kernels.registry import DEFAULT_KERNEL
from threemind_transformer.language_assets import available, registry
from threemind_transformer.language_bundle import validate_assets
from threemind_transformer.language_compute import compute
from threemind_transformer.language_protocol import LanguageCompute, LanguageProtocol, LanguageTraining, ScratchTraining
from threemind_transformer.language_session import LanguageSession
from threemind_transformer.protocol import digest

from .ai_providers import require_actor
from .database import Conflict, NotFound
from .protocols import RunSpec, StrictModel
from .transformer_tools import submit


class LanguageAssets(StrictModel):
    head: UUID | None = None
    input: UUID | None = None
    output: UUID | None = None


class CreateSession(StrictModel):
    request_id: UUID
    name: str = Field(default="语言实验意识", min_length=1, max_length=200)
    protocol: LanguageProtocol = Field(default_factory=LanguageProtocol)
    compute: LanguageCompute = Field(default_factory=LanguageCompute)
    assets: LanguageAssets = Field(default_factory=LanguageAssets)
    kernel_id: str = DEFAULT_KERNEL
    config: dict = Field(default_factory=dict)
    seed: int = Field(default=20260724, ge=0, le=2**32 - 1)
    text_sensor: dict = Field(default_factory=dict)
    source_run_id: UUID | None = None
    source_checkpoint_id: UUID | None = None


class TurnRequest(StrictModel):
    request_id: UUID
    expected_revision: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=2048)
    intensity: float = Field(default=1.0, ge=0, le=100)


class ObserveRequest(StrictModel):
    request_id: UUID
    expected_revision: int = Field(ge=1)


class HeadRequest(StrictModel):
    request_id: UUID
    training: LanguageTraining
    checkpoint: UUID | None = None


class ScratchRequest(StrictModel):
    request_id: UUID
    training: ScratchTraining
    checkpoint: UUID | None = None


def artifact(database, project, identity, kind):
    if identity is None:
        return None
    with database.tx(project) as db:
        row = db.execute("SELECT bytes,sha256,metadata FROM artifacts WHERE id=%s", (identity,)).fetchone()
        if row is None:
            raise NotFound("language model artifact")
        if row["metadata"].get("kind") != kind or not 0 < row["bytes"] <= 64 * 2**20:
            raise ValueError("language artifact has incompatible kind or size")
    from .binary_reads import object_bytes

    raw = object_bytes(database, project, "artifact", identity, maximum=64 * 2**20)
    if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise ValueError("language artifact checksum mismatch")
    return raw


def assets_bytes(database, project, assets, protocol):
    values = {
        key: artifact(database, project, assets.get(key), "language-head" if key == "head" else "language-scratch")
        for key in ("head", "input", "output")
    }
    validate_assets(protocol, values)
    return values


def features():
    installed = all(importlib.util.find_spec(module) is not None for module in ("torch", "safetensors"))
    return {
        "worker.language_v1": {"state": "available"},
        "worker.language_observation_v1": {"state": "available"},
        "worker.language_projection_v2": {"state": "available"},
        "worker.language_torch_v1": {"state": "available" if installed else "unavailable"},
        **{
            "worker.language_" + key: {
                "state": "available" if available(key) and importlib.util.find_spec("transformers") else "unavailable"
            }
            for key in ("embedding", "decoder")
        },
    }


def create(database, project, actor, body):
    fingerprint = digest(body.model_dump(mode="json") | {"actor": str(actor)})
    assets = body.assets.model_dump(mode="json")
    assets_bytes(database, project, assets, body.protocol)
    spec = RunSpec(
        kernel_id=body.kernel_id,
        environment="manual",
        clock="unbounded",
        config=body.config,
        seed=body.seed,
        text_sensor=body.text_sensor,
        activity_readout={"enabled": True, "analysis_version": 2},
    )
    source = None
    if body.source_checkpoint_id and not body.source_run_id:
        raise ValueError("source checkpoint requires a source consciousness")
    if body.source_run_id:
        source, image = database.load_checkpoint(project, body.source_run_id, body.source_checkpoint_id)
        from threemind_kernels.registry import state_kernel

        if state_kernel(image).kernel_id != body.kernel_id:
            raise ValueError("source Core identity differs; select its actual kernel")
        if body.config and body.config != image.to_dict()["config"]:
            raise ValueError(
                "source checkpoint retains its Core parameters; omit config or supply its exact parameters"
            )
        spec = spec.model_copy(update={"config": image.to_dict()["config"]})
    run_id = body.request_id
    with database.tx(project) as db:
        require_actor(db, project, actor)
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("language:" + str(run_id),))
        old = db.execute("SELECT fingerprint FROM language_sessions WHERE run_id=%s", (run_id,)).fetchone()
        if old:
            if old["fingerprint"] != fingerprint:
                raise Conflict("request identifier already used for another session")
            return {"run_id": str(run_id), "replayed": True}
        if db.execute("SELECT id FROM runs WHERE id=%s", (run_id,)).fetchone():
            raise Conflict("request identifier already belongs to another consciousness")
        db.execute(
            "INSERT INTO runs(id,project_id,name,spec,parent_id,origin_hash,origin_checkpoint_id,origin_kind) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                run_id,
                project,
                body.name,
                Jsonb(spec.model_dump()),
                body.source_run_id,
                source["state_hash"] if source else None,
                source["id"] if source else None,
                "fork" if source else "created",
            ),
        )
        db.execute(
            "INSERT INTO language_sessions(run_id,project_id,actor_id,fingerprint,protocol,compute,assets,source_run_id,source_checkpoint_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                run_id,
                project,
                actor,
                fingerprint,
                Jsonb(body.protocol.model_dump()),
                Jsonb(body.compute.model_dump()),
                Jsonb(assets),
                body.source_run_id,
                source["id"] if source else None,
            ),
        )
        db.execute(
            "INSERT INTO jobs(id,project_id,run_id,kind,params) VALUES(%s,%s,%s,'transformer',%s)",
            (
                uuid4(),
                project,
                run_id,
                Jsonb({"operation": "language_init", "actor_id": str(actor), "protocol": body.protocol.model_dump()}),
            ),
        )
    return {"run_id": str(run_id), "replayed": False}


def turn(database, project, run_id, actor, body):
    observing = isinstance(body, ObserveRequest)
    with database.tx(project) as db:
        require_actor(db, project, actor)
        session = db.execute(
            "SELECT s.*,r.revision,r.life,r.status FROM language_sessions s JOIN runs r ON r.id=s.run_id WHERE s.run_id=%s FOR UPDATE OF r",
            (run_id,),
        ).fetchone()
        if session is None:
            raise NotFound("language consciousness")
        params = {
            "operation": "language_observe" if observing else "language_turn",
            "actor_id": str(actor),
            "protocol": session["protocol"],
            **body.model_dump(mode="json", exclude={"request_id"}),
        }
        existing = db.execute("SELECT params,run_id FROM jobs WHERE id=%s", (body.request_id,)).fetchone()
        if existing:
            if existing["params"] != params or str(existing["run_id"]) != str(run_id):
                raise Conflict("request identifier conflict")
            return {"id": str(body.request_id), "replayed": True}
        if session["status"] != "paused" or session["life"] == "dead" or session["revision"] != body.expected_revision:
            raise Conflict("wait for the current turn, then reload the live paused consciousness revision")
        if db.execute("SELECT 1 FROM jobs WHERE run_id=%s AND status IN ('pending','leased')", (run_id,)).fetchone():
            raise Conflict("this consciousness already has a pending operation")
        db.execute(
            "INSERT INTO jobs(id,project_id,run_id,kind,params) VALUES(%s,%s,%s,'transformer',%s)",
            (body.request_id, project, run_id, Jsonb(params)),
        )
        db.execute(
            "INSERT INTO language_turns(job_id,project_id,run_id,expected_revision,text,intensity) VALUES(%s,%s,%s,%s,%s,%s)",
            (
                body.request_id,
                project,
                run_id,
                body.expected_revision,
                "" if observing else body.text,
                0.0 if observing else body.intensity,
            ),
        )
    return {"id": str(body.request_id), "replayed": False}


def execute(database, job, *, backend="native"):
    project, params = job["project_id"], job["params"]
    with database.tx(project) as db:
        require_actor(db, project, params["actor_id"])
        database.fence(db, job)
    operation = params["operation"]
    if operation in ("language_train", "language_scratch_train"):
        cls = LanguageTraining if operation == "language_train" else ScratchTraining
        spec = cls.model_validate(params["training"])
        result, weights = compute(
            "train" if operation == "language_train" else "scratch_train",
            spec.model_dump(),
            spec.compute,
            checkpoint=artifact(database, project, params.get("checkpoint"), "language-scratch"),
        )
        kind = "language-head" if operation == "language_train" else "language-scratch"
        with database.tx(project) as db:
            require_actor(db, project, params["actor_id"])
            database.fence(db, job)
        item = database.put_artifact(
            job,
            kind + ".safetensors",
            "application/octet-stream",
            weights,
            {"kind": kind, "protocol": spec.protocol.model_dump(), "training": result},
        )
        result["model_artifact_id"] = str(item["id"])
        return {"summary": result}
    run_id = job["run_id"]
    run = database.get_run(project, run_id)
    with database.tx(project) as db:
        row = db.execute("SELECT * FROM language_sessions WHERE run_id=%s", (run_id,)).fetchone()
        old = db.execute("SELECT result FROM language_turns WHERE job_id=%s", (job["id"],)).fetchone()
        if old and old["result"]:
            return old["result"]
    if row is None:
        raise NotFound("language consciousness")
    if operation == "language_init" and run["revision"]:
        return {"run_id": str(run_id), "revision": run["revision"]}
    image, context = None, None
    if run["revision"]:
        cp, image = database.load_checkpoint(project, run_id)
        context = cp["context"].get("language")
        if run["revision"] != params["expected_revision"]:
            raise Conflict("language revision changed")
    elif row["source_run_id"]:
        _, image = database.load_checkpoint(project, row["source_run_id"], row["source_checkpoint_id"])
    spec = RunSpec(**run["spec"])
    session = LanguageSession(
        row["protocol"],
        image=image,
        context=context,
        kernel_id=spec.kernel_id,
        config=spec.config,
        seed=spec.seed,
        text_sensor=spec.model_dump()["text_sensor"],
        backend=backend,
    )
    result = {"run_id": str(run_id)}
    if operation in ("language_turn", "language_observe"):
        assets = assets_bytes(database, project, row["assets"], session.protocol)
        kwargs = {
            "policy": LanguageCompute(**row["compute"]),
            "head": assets["head"],
            "output_checkpoint": assets["output"],
        }
        full = (
            session.observe(**kwargs)
            if operation == "language_observe"
            else session.turn(
                params["text"],
                intensity=params["intensity"],
                input_checkpoint=assets["input"],
                **kwargs,
            )
        )
        evidence = database.put_artifact(
            job,
            "language-turn.json",
            "application/json",
            json.dumps(full, ensure_ascii=False, allow_nan=False).encode(),
            {"kind": "language-turn", "run_id": str(run_id)},
        )
        result.update(
            result_artifact_id=str(evidence["id"]),
            text=full["text"],
            intensity=full["intensity"],
            interpretation=full["interpretation"],
            readouts=[
                {
                    **r,
                    "payload": {
                        k: v
                        for k, v in r["payload"].items()
                        if k in ("chat", "kind", "analysis_id", "window_id", "status", "classification")
                    },
                }
                for r in full["readouts"]
            ],
            process={k: v for k, v in full["process"].items() if k != "trajectory"},
            final_activities=sorted(
                full["process"]["trajectory"][-1]["nodes"], key=lambda n: (-n["activation"], int(n["id"]))
            )[:200],
            final_activity_count=len(full["process"]["trajectory"][-1]["nodes"]),
            before_hash=full["before_hash"],
            after_hash=full["after_hash"],
            new_input=operation == "language_turn",
            wall_seconds=full["wall_seconds"],
            pending_external_before=full.get("pending_external_before"),
            pending_external_after=full.get("pending_external_after"),
        )
    with database.tx(project) as db:
        require_actor(db, project, params["actor_id"])
        database.fence(db, job)
        cp = database.save_checkpoint(
            project,
            run_id,
            session.engine.capture_state(),
            context={"language": session.context()},
            expected_revision=run["revision"],
            status="dead" if session.engine.life == "dead" else "paused",
            job=job,
            observations=[session.engine.metrics()],
            transaction=db,
        )
        result.update(checkpoint_id=str(cp["id"]), revision=cp["revision"])
        if operation in ("language_turn", "language_observe"):
            db.execute(
                "UPDATE language_turns SET result=%s,result_checkpoint_id=%s WHERE job_id=%s",
                (Jsonb(result), cp["id"], job["id"]),
            )
    return result


def register(app, access):
    import asyncio

    from fastapi import Query, Response

    from threemind_transformer.language_bundle import MAX_BYTES, pack

    root = "/api/v2/projects/{project}/language"

    @app.get(root + "/sessions/{run_id}/bundle", response_class=Response)
    def export_bundle(project: UUID, run_id: UUID, request: Request, revision: int = Query(ge=1)):
        access(request, project)
        with app.state.db.tx(project) as db:
            row = db.execute("SELECT * FROM language_sessions WHERE run_id=%s", (run_id,)).fetchone()
            cp = db.execute("SELECT id FROM checkpoints WHERE run_id=%s AND revision=%s", (run_id, revision)).fetchone()
            if row is None or cp is None:
                raise NotFound("language checkpoint")
        checkpoint, image = app.state.db.load_checkpoint(project, run_id, cp["id"])
        assets = assets_bytes(app.state.db, project, row["assets"], LanguageProtocol.model_validate(row["protocol"]))
        raw = pack(image, checkpoint["context"]["language"], assets)
        return Response(
            raw,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{run_id}-{revision}.tmlanguage"'},
        )

    @app.post(
        root + "/imports",
        status_code=201,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
            }
        },
    )
    async def import_language(
        project: UUID,
        request: Request,
        request_id: UUID,
        name: str = Query("导入的语言意识", min_length=1, max_length=200),
    ):
        actor = access(request, project, write=True)
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > MAX_BYTES:
                raise ValueError("language bundle exceeds 256 MiB")
            raw.extend(chunk)
        from .language_archive import import_bundle

        return await asyncio.to_thread(
            import_bundle,
            app.state.db,
            project,
            actor["id"],
            request_id,
            name,
            bytes(raw),
            backend=app.state.settings.backend,
        )

    @app.get(root)
    def overview(project: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            sessions = db.execute(
                "SELECT r.id,r.name,r.status,r.life,r.revision,r.time_us,r.spec->>'kernel_id' kernel_id,r.spec->'text_sensor' text_sensor,r.spec->'seed' seed,s.protocol,s.assets,s.compute FROM language_sessions s JOIN runs r ON r.id=s.run_id ORDER BY s.created_at DESC LIMIT 100"
            ).fetchall()
            models = db.execute(
                "SELECT id,name,sha256,bytes,metadata FROM artifacts WHERE metadata->>'kind' IN ('language-head','language-scratch') ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
            jobs = db.execute(
                "SELECT id,status,error,result,params->>'operation' operation FROM jobs WHERE kind='transformer' AND params->>'operation' LIKE 'language_%' ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
        return {
            "sessions": sessions,
            "models": models,
            "jobs": jobs,
            "default_protocol": LanguageProtocol().model_dump(),
            "default_compute": LanguageCompute().model_dump(),
            "schema": LanguageProtocol.model_json_schema(),
            "assets": {key: info | {"available_here": available(key)} for key, info in registry().items()},
        }

    @app.post(root + "/sessions", status_code=202)
    def create_session(project: UUID, body: CreateSession, request: Request):
        actor = access(request, project, write=True)
        return create(app.state.db, project, actor["id"], body)

    @app.get(root + "/sessions/{run_id}/turns")
    def turns(project: UUID, run_id: UUID, request: Request, offset: int = 0):
        access(request, project)
        if offset < 0:
            raise ValueError("offset must be nonnegative")
        with app.state.db.tx(project) as db:
            if not db.execute("SELECT 1 FROM language_sessions WHERE run_id=%s", (run_id,)).fetchone():
                raise NotFound()
            rows = db.execute(
                "SELECT t.*,j.status,j.error FROM language_turns t JOIN jobs j ON j.id=t.job_id WHERE t.run_id=%s ORDER BY t.created_at DESC,t.job_id DESC LIMIT 21 OFFSET %s",
                (run_id, offset),
            ).fetchall()
        return {"rows": rows[:20], "more": len(rows) > 20}

    @app.post(root + "/sessions/{run_id}/turns", status_code=202)
    def send(project: UUID, run_id: UUID, body: TurnRequest, request: Request):
        actor = access(request, project, write=True)
        return turn(app.state.db, project, run_id, actor["id"], body)

    @app.post(root + "/sessions/{run_id}/observations", status_code=202)
    def observe(project: UUID, run_id: UUID, body: ObserveRequest, request: Request):
        actor = access(request, project, write=True)
        return turn(app.state.db, project, run_id, actor["id"], body)

    @app.post(root + "/head-training", status_code=202)
    def train_head(project: UUID, body: HeadRequest, request: Request):
        actor = access(request, project, write=True)
        artifact(app.state.db, project, body.checkpoint, "language-scratch")
        return submit(
            app.state.db,
            project,
            actor["id"],
            body.request_id,
            {
                "operation": "language_train",
                "training": body.training.model_dump(),
                "checkpoint": str(body.checkpoint) if body.checkpoint else None,
            },
        )

    @app.post(root + "/scratch-training", status_code=202)
    def train_scratch(project: UUID, body: ScratchRequest, request: Request):
        actor = access(request, project, write=True)
        artifact(app.state.db, project, body.checkpoint, "language-scratch")
        return submit(
            app.state.db,
            project,
            actor["id"],
            body.request_id,
            {
                "operation": "language_scratch_train",
                "training": body.training.model_dump(),
                "checkpoint": str(body.checkpoint) if body.checkpoint else None,
            },
        )
