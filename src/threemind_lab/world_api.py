import json
from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from fastapi.responses import Response
from pydantic import Field

from threemind_runtime.world_schema import (
    Body,
    CameraSensor,
    Force,
    Geometry,
    InertialSensor,
    Joint,
    JointSensor,
    Motor,
    RangeSensor,
    TouchSensor,
    WorldSpec,
    default_world,
)

from . import worlds
from .database import Conflict, NotFound
from .protocols import StrictModel


class WorldEdit(StrictModel):
    operation_id: UUID
    document_id: UUID | None = None
    expected_revision: int = Field(default=0, ge=0, strict=True)
    protocol: dict
    ai_call_id: UUID | None = None


class Preview(StrictModel):
    protocol: dict
    seed: int = Field(default=0, ge=0, le=2**32 - 1, strict=True)


class Archive(StrictModel):
    archived: bool = Field(strict=True)
    expected_revision: int = Field(ge=1, strict=True)


def catalogue():
    from threemind_runtime.world_templates import physical_templates

    return {
        "defaults": default_world().model_dump(mode="json") | {"schema_id": "threemind.world/2"},
        "templates": {key: value.model_dump(mode="json") for key, value in physical_templates().items()},
        "schema": WorldSpec.model_json_schema(),
        "components": {
            key: obj.model_dump(mode="json")
            for key, obj in {
                "bodies": Body(id="body"),
                "geometries": Geometry(id="geometry"),
                "joints": Joint(id="joint", body_id="body"),
                "motors": Motor(id="motor", joint_id="joint", port=0),
                "forces": Force(id="force", body_id="body"),
                "joint_position": JointSensor(id="sensor", kind="joint_position", joint_id="joint", port=0),
                "joint_velocity": JointSensor(id="sensor", kind="joint_velocity", joint_id="joint", port=0),
                "touch": TouchSensor(id="sensor", geometry_id="geometry", port=0),
                "rangefinder": RangeSensor(id="sensor", body_id="body", port=0),
                "camera_rgb": CameraSensor(id="sensor", body_id="body", port=0),
                "accelerometer": InertialSensor(id="sensor", kind="accelerometer", body_id="body", port=0, scale=9.81),
                "gyroscope": InertialSensor(id="sensor", kind="gyroscope", body_id="body", port=0, scale=3.0),
            }.items()
        },
    }


def register_world_routes(app, access):
    from . import world_ai

    root = "/api/v2/projects/{project}/worlds"

    @app.post(root + "/ai/preview")
    def ai_preview(project: UUID, request: Request, body: world_ai.WorldScope):
        access(request, project, write=True)
        return world_ai.prepare(body)

    @app.post(root + "/ai/requests", status_code=202)
    def ai_request(project: UUID, request: Request, body: world_ai.WorldGeneration):
        actor = access(request, project, write=True)
        return world_ai.request(app.state.db, app.state.settings, project, actor["id"], body)

    @app.get(root + "/catalogue")
    def schema(project: UUID, request: Request):
        access(request, project)
        return catalogue()

    @app.post(root + "/validate")
    def validate(project: UUID, request: Request, body: Preview):
        access(request, project)
        return worlds.validate(body.protocol, body.seed)

    @app.get(root)
    def listing(
        project: UUID,
        request: Request,
        q: str = Query("", max_length=120),
        archived: bool = False,
        kind: Literal["world", "robot"] = "world",
        offset: int = Query(0, ge=0, le=100000),
    ):
        access(request, project)
        with app.state.db.tx(project) as db:
            rows = db.execute(
                "SELECT d.*,v.protocol_hash,v.physical_hash FROM world_documents d "
                "JOIN world_versions v ON v.document_id=d.id AND v.revision=d.revision "
                "WHERE d.archived=%s AND (%s='' OR d.title ILIKE %s) "
                "AND (v.protocol->>'schema_id' IN ('threemind.robot-task/1','threemind.robot-task/2'))=%s "
                "ORDER BY d.updated_at DESC,d.id DESC LIMIT 31 OFFSET %s",
                (archived, q, "%" + q + "%", kind == "robot", offset),
            ).fetchall()
        return {"rows": rows[:30], "more": len(rows) > 30}

    @app.post(root, status_code=201)
    def save(project: UUID, request: Request, body: WorldEdit):
        actor = access(request, project, write=True)
        return worlds.save(app.state.db, project, actor["id"], body)

    @app.get(root + "/{identity}")
    def get(project: UUID, identity: UUID, request: Request, revision: int | None = Query(None, ge=1)):
        access(request, project)
        with app.state.db.tx(project) as db:
            return worlds.get(db, identity, revision)

    @app.get(root + "/{identity}/revisions")
    def history(project: UUID, identity: UUID, request: Request, before: int | None = Query(None, ge=1)):
        access(request, project)
        with app.state.db.tx(project) as db:
            worlds.get(db, identity)
            rows = db.execute(
                "SELECT revision,protocol_hash,physical_hash,actor_id,created_at FROM world_versions "
                "WHERE document_id=%s AND (%s::bigint IS NULL OR revision<%s) ORDER BY revision DESC LIMIT 31",
                (identity, before, before),
            ).fetchall()
        return {"rows": rows[:30], "more": len(rows) > 30}

    @app.put(root + "/{identity}/archive")
    def archive(project: UUID, identity: UUID, request: Request, body: Archive):
        access(request, project, write=True)
        with app.state.db.tx(project) as db:
            row = db.execute(
                "UPDATE world_documents SET archived=%s,updated_at=clock_timestamp() "
                "WHERE id=%s AND revision=%s RETURNING id,revision,archived",
                (body.archived, identity, body.expected_revision),
            ).fetchone()
            if row is None:
                raise Conflict("世界已更新或不可访问，请刷新后重试。")
        return row

    @app.get(root + "/{identity}/export")
    def export(project: UUID, identity: UUID, request: Request, revision: int | None = Query(None, ge=1)):
        access(request, project)
        with app.state.db.tx(project) as db:
            row = worlds.get(db, identity, revision)
        return Response(
            json.dumps(row["protocol"], ensure_ascii=False, indent=2) + "\n",
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="world-{identity}-r{row["revision"]}.world.json"'},
        )

    def checkpoint(project, run_id, checkpoint_id):
        app.state.db.get_run(project, run_id)
        with app.state.db.tx(project) as db:
            row = db.execute(
                "SELECT id,revision,time_us::text,state_hash,context FROM checkpoints "
                "WHERE run_id=%s AND (%s::uuid IS NULL OR id=%s) ORDER BY revision DESC LIMIT 1",
                (run_id, checkpoint_id, checkpoint_id),
            ).fetchone()
        if row is None or (row["context"].get("environment") or {}).get("kind") not in ("world", "robot"):
            raise NotFound("所选检查点没有可配置物理世界的观测。")
        return row

    @app.get("/api/v2/projects/{project}/runs/{run_id}/world/observation")
    def observation(project: UUID, run_id: UUID, request: Request, checkpoint_id: UUID | None = None):
        access(request, project)
        row = checkpoint(project, run_id, checkpoint_id)
        state = row.pop("context")["environment"]
        return row | {
            "world_hash": state["world_hash"],
            "physical_hash": state["physical_hash"],
            "mujoco_version": state["mujoco_version"],
            "observation": state["observation"],
            "controls": state["controls"],
            "measurements": state["measurements"],
        }

    @app.get("/api/v2/projects/{project}/runs/{run_id}/world/protocol")
    def protocol(project: UUID, run_id: UUID, request: Request, checkpoint_id: UUID | None = None):
        access(request, project)
        row = checkpoint(project, run_id, checkpoint_id)
        frozen = row["context"].get("protocol") or app.state.db.get_run(project, run_id)["spec"]
        if frozen["environment"] == "robot":
            saved = row["context"]["environment"]
            if saved.get("schema") == "threemind.playground-state/1":
                from threemind_runtime.playground_scene import unpack_scene

                return {"checkpoint_id": row["id"], "protocol": unpack_scene(saved["scene_archive"]),
                        "robot_protocol": frozen["robot_protocol"], "world_hash": saved["world_hash"]}
            from threemind_runtime.robot import RobotWorld

            with RobotWorld(frozen["robot_protocol"], frozen["seed"], row["context"]["environment"],
                            environment_seed=frozen.get("environment_seed")) as world:
                return {"checkpoint_id": row["id"], "protocol": world.scene_protocol(),
                        "robot_protocol": frozen["robot_protocol"], "world_hash": world.protocol_hash}
        return {
            "checkpoint_id": row["id"],
            "protocol": frozen["world_protocol"],
            "world_hash": row["context"]["environment"]["world_hash"],
        }
