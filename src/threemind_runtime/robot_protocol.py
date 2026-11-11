"""Robot experiments describe external physics and wiring, never Core rules."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import Field, model_validator

from .world_schema import Model, Vec3, WorldSpec, digest


class RobotControl(Model):
    mode: Literal["torque", "position", "velocity", "skill"] = "torque"
    # An explicit simulator intervention, not a claim about vendor hardware.
    actuator_variant: Literal["profile", "ideal-torque"] = "profile"
    kp: float = Field(default=20.0, ge=0, le=10000)
    kd: float = Field(default=2.0, ge=0, le=10000)
    maximum_velocity: float = Field(default=2.0, gt=0, le=100)
    continuous_position_span: float = Field(default=3.141592653589793, gt=0, le=100)
    # The example skill is an explicit external trajectory, not an inferred ability.
    skill: Literal["joint-sweep/1"] = "joint-sweep/1"
    skill_period_us: int = Field(default=2000000, ge=10000, le=60000000)


class RobotIntervention(Model):
    action: Literal["force", "actuators", "release", "reset_world"]
    duration_us: int = Field(default=100000, ge=1000, le=60000000)
    body_id: str | None = None
    force: Vec3 = (0.0, 0.0, 0.0)
    torque: Vec3 = (0.0, 0.0, 0.0)
    commands: list[float] = Field(default_factory=list, max_length=512)

    @model_validator(mode="after")
    def action_shape(self):
        if any(abs(v) > 1 for v in self.commands):
            raise ValueError("actuator commands must be normalized to [-1,1]")
        if self.action == "force" and (not self.body_id or self.commands):
            raise ValueError("force intervention requires one body and no actuator commands")
        if self.action == "actuators" and (not self.commands or self.body_id or any(self.force) or any(self.torque)):
            raise ValueError("actuator intervention only accepts actuator commands")
        if self.action in ("release", "reset_world") and (
            self.commands or self.body_id or any(self.force) or any(self.torque)
        ):
            raise ValueError("release/reset do not accept forces or actuator commands")
        return self


class RobotTask(Model):
    schema_id: Literal["threemind.robot-task/1"] = "threemind.robot-task/1"
    name: str = Field(default="Robot experiment", min_length=1, max_length=120)
    body_id: str = Field(default="custom-arm/1", min_length=1, max_length=120)
    category: Literal["arm", "mobile", "humanoid"] = "arm"
    world: WorldSpec
    control: RobotControl = Field(default_factory=RobotControl)
    objective: Literal["observe", "reach", "push"] = "reach"
    endpoint_body: str = "tool"
    object_body: str | None = None
    target: Vec3 = (0.4, 0.18, 0.12)
    target_jitter: Vec3 = (0.08, 0.08, 0.0)
    success_distance: float = Field(default=0.05, gt=0, le=10)
    # Explicit ideal optical beacon: body-local bearing/range; not task reward.
    beacon_enabled: bool = True
    beacon_scale: float = Field(default=1.0, gt=0, le=1000)
    beacon_range: float = Field(default=3.0, gt=0, le=10000)
    beacon_port: int = Field(default=4094, ge=0, le=4095)
    asset_id: str | None = Field(default=None, max_length=100)
    asset_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def references(self):
        if self.control.actuator_variant == "ideal-torque" and self.control.mode != "torque":
            raise ValueError("ideal-torque actuator variant requires torque control")
        if self.world.schema_id != "threemind.world/2":
            raise ValueError("robot tasks require explicit world/2 wiring")
        if any(v < 0 for v in self.target_jitter):
            raise ValueError("target jitter must be nonnegative")
        if bool(self.asset_id) != bool(self.asset_sha256):
            raise ValueError("robot assets require both identity and content hash")
        if not self.asset_id:
            bodies = {b.id for b in self.world.bodies}
            if self.endpoint_body not in bodies:
                raise ValueError("missing physical endpoint body")
            if self.objective == "push" and self.object_body not in bodies:
                raise ValueError("pushing requires a physical object body")
            if not self.world.motors:
                raise ValueError("a robot requires declared actuators")
        if self.beacon_port in {s.port for s in self.world.sensors}:
            raise ValueError("beacon port collides with another sensor")
        return self

    @property
    def digest(self):
        return digest(self.model_dump(mode="json"))


class PlaygroundOptions(Model):
    task: Literal["PandaPickCube"] = "PandaPickCube"
    revision: Literal["ef4fefc13033c0468af4ef651847f5348af0c7d7"] = "ef4fefc13033c0468af4ef651847f5348af0c7d7"
    implementation: Literal["jax", "warp"] = "jax"
    device: Literal["cpu", "cuda"] = "cpu"
    observation: Literal["physical-senses", "official-state"] = "physical-senses"
    input_intensity: float = Field(default=1.0, ge=0, le=100)
    projection_gain: float = Field(default=1.0, ge=0, le=100)

    @model_validator(mode="after")
    def compute(self):
        if self.implementation == "warp" and self.device != "cuda":
            raise ValueError("the official Warp task requires a CUDA worker; choose jax for CPU")
        return self


class PlaygroundRobotTask(RobotTask):
    """An explicit /2 task; historical /1 serialization and hashes stay intact."""

    schema_id: Literal["threemind.robot-task/2"] = "threemind.robot-task/2"
    objective: Literal["reference"] = "reference"
    playground: PlaygroundOptions = Field(default_factory=PlaygroundOptions)

    @model_validator(mode="after")
    def reference_task(self):
        from .playground_assets import manifest

        meta = manifest()
        # These fields are shared port/observer descriptors, not configurable
        # replacements for the upstream physical task or its servo controller.
        if self.world.model_dump(mode="json") != meta["world"]:
            raise ValueError(
                "official Playground timing and port declarations are fixed; create a separate custom robot task to change them"
            )
        if self.control != RobotControl(mode="position") or self.asset_id:
            raise ValueError(
                "PandaPickCube retains its official incremental position servo; raw torque belongs to a separately identified task"
            )
        if self.body_id != "playground-PandaPickCube/1" or self.category != "arm":
            raise ValueError("official task identity differs")
        if self.endpoint_body != meta["endpoint"] or self.object_body != meta["object_body"]:
            raise ValueError("official task body declaration differs")
        if self.target != (0.4, 0.18, 0.12) or self.target_jitter != (0.08, 0.08, 0.0) or self.success_distance != 0.05:
            raise ValueError(
                "generic target fields are not used by Playground; upstream reset and metrics define its task"
            )
        if (self.beacon_scale, self.beacon_range, self.beacon_port) != (1.0, 3.0, 4094):
            raise ValueError("official-task physical beacon calibration is versioned")
        return self


def playground_template():
    from .playground_assets import manifest

    value = manifest()
    return PlaygroundRobotTask(
        name="Playground PandaPickCube",
        body_id="playground-PandaPickCube/1",
        world=WorldSpec.model_validate_json(json.dumps(value["world"])),
        control=RobotControl(mode="position"),
        endpoint_body=value["endpoint"],
        object_body=value["object_body"],
    )


def parse_robot(value):
    if isinstance(value, RobotTask):
        return value

    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError(f"duplicate robot field: {key}")
            result[key] = item
        return result

    if isinstance(value, (str, bytes)):
        if len(value.encode("utf-8") if isinstance(value, str) else value) > 4 * 1024 * 1024:
            raise ValueError("robot protocol exceeds 4 MiB")
        value = json.loads(value, object_pairs_hook=unique)
    encoded = json.dumps(value, allow_nan=False, ensure_ascii=False).encode("utf-8")
    if len(encoded) > 4 * 1024 * 1024:
        raise ValueError("robot protocol exceeds 4 MiB")
    if not isinstance(value, dict):
        raise ValueError("robot protocol must be an object")  # noqa: TRY004 -- public API validation
    kind = PlaygroundRobotTask if value.get("schema_id") == "threemind.robot-task/2" else RobotTask
    return kind.model_validate_json(encoded, strict=True)
