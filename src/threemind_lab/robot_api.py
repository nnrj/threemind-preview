"""Robot protocols use the existing run/world/evolution services and receipts."""

from uuid import UUID

from fastapi import Request
from pydantic import Field

from threemind_runtime.robot import RobotWorld
from threemind_runtime.robot_assets import installed, profile, registry, task_for_asset
from threemind_runtime.robot_protocol import PlaygroundRobotTask, RobotTask, parse_robot
from threemind_runtime.robot_templates import robot_templates

from .protocols import StrictModel


class RobotPreview(StrictModel):
    protocol: dict
    seed: int = Field(default=0, ge=0, le=2**32 - 1, strict=True)


def validate_robot(value, seed=0):
    task = parse_robot(value)
    if isinstance(task, PlaygroundRobotTask):
        from threemind_runtime.playground_assets import manifest
        from threemind_runtime.world_schema import digest

        cfg = task.playground
        return {
            "valid": True,
            "validation_scope": "protocol-only; worker verifies pinned sources and executes physics",
            "protocol": task.model_dump(mode="json"),
            "protocol_hash": task.digest,
            "physical_hash": digest(
                {
                    "task": cfg.task,
                    "revision": cfg.revision,
                    "assets": manifest()["menagerie_revision"],
                    "implementation": cfg.implementation,
                    "device": cfg.device,
                }
            ),
            "physical_hash_scope": "pinned declaration; worker snapshots additionally bind dependency versions",
            "layout": None,
            "scene_protocol": None,
            "upstream_revision": manifest()["revision"],
            "required_capabilities": [f"worker.playground_{cfg.implementation}_{cfg.device}"],
            "control": task.control.model_dump(mode="json"),
            "external_controller": True,
            "simulated_motor_replacement": False,
            "model": {
                "bodies": len(task.world.bodies),
                "geometries": len(task.world.geometries),
                "motors": len(task.world.motors),
            },
        }
    with RobotWorld(task, seed) as world:
        return {
            "valid": True,
            "protocol": task.model_dump(mode="json"),
            "protocol_hash": task.digest,
            "physical_hash": world.physical_hash,
            "layout": world.observation(),
            "scene_protocol": world.scene_protocol(),
            "mujoco_version": world.mj.__version__,
            "model": {
                "bodies": world.model.nbody - 1,
                "geometries": world.model.ngeom,
                "dofs": world.model.nv,
                "motors": world.model.nu,
            },
            "required_capabilities": ["worker.robot_v1"]
            + (["worker.robot_asset_" + task.asset_id] if task.asset_id else []),
            "control": task.control.model_dump(mode="json"),
            "external_controller": task.control.mode != "torque",
            "simulated_motor_replacement": task.control.actuator_variant == "ideal-torque",
        }


def register(app, access):
    root = "/api/v2/projects/{project}/robots"

    @app.get(root + "/catalogue")
    def robot_catalogue(project: UUID, request: Request):
        access(request, project)
        assets = {
            key: {
                "available_here": installed(key),
                "asset_sha256": profile(key)["sha256"],
                "modes": profile(key)["modes"],
                "simulation_modes": ["torque", "position", "velocity", "skill"],
                "category": profile(key)["category"],
                "install_command": "threemind-robot assets install " + key,
            }
            for key in registry()["profiles"]
        }
        return {
            "schema": RobotTask.model_json_schema(),
            "playground_schema": PlaygroundRobotTask.model_json_schema(),
            "templates": {key: value.model_dump(mode="json") for key, value in robot_templates().items()},
            "assets": assets,
            "control_modes": ["torque", "position", "velocity", "skill"],
        }

    @app.get(root + "/assets/{identity}/template")
    def robot_asset_template(project: UUID, identity: str, request: Request):
        access(request, project)
        return task_for_asset(identity).model_dump(mode="json")

    @app.post(root + "/validate")
    def robot_validate(project: UUID, body: RobotPreview, request: Request):
        access(request, project)
        return validate_robot(body.protocol, body.seed)
