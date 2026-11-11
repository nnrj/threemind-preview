"""Declarative physical worlds and sensory wiring, independent of Core and Lab."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Id = Annotated[str, Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")]
Number = Annotated[float, Field(ge=-1e6, le=1e6)]
Positive = Annotated[float, Field(gt=0, le=1e6)]
Nonnegative = Annotated[float, Field(ge=0, le=1e6)]
Unit = Annotated[float, Field(ge=0, le=1)]
Vec3 = tuple[Number, Number, Number]
Quat = tuple[Number, Number, Number, Number]  # MuJoCo order: w, x, y, z.


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class Named(Model):
    id: Id
    label: str = Field(default="", max_length=120)


class Pose(Model):
    position: Vec3 = (0.0, 0.0, 0.0)
    quaternion: Quat = (1.0, 0.0, 0.0, 0.0)

    @model_validator(mode="after")
    def orientation(self):
        if not math.isclose(math.fsum(v * v for v in self.quaternion), 1, rel_tol=0, abs_tol=1e-8):
            raise ValueError("quaternion must be a unit vector in w,x,y,z order")
        return self


class Physics(Model):
    step_us: int = Field(default=5000, ge=10, le=100000)
    sample_us: int = Field(default=20000, ge=10, le=1000000)
    gravity: Vec3 = (0.0, 0.0, -9.81)
    integrator: Literal["Euler", "RK4", "implicitfast"] = "implicitfast"
    iterations: int = Field(default=50, ge=1, le=1000)

    @model_validator(mode="after")
    def interval(self):
        if self.sample_us % self.step_us or self.sample_us // self.step_us > 1000:
            raise ValueError("sensory interval must contain 1 to 1000 complete physics steps")
        return self


class Body(Named, Pose):
    parent_id: Id | None = None
    free: bool = False


class Geometry(Named, Pose):
    body_id: Id | None = None
    shape: Literal["sphere", "box", "capsule", "cylinder", "plane"] = "sphere"
    size: tuple[Positive, ...] = Field(default=(0.15,), min_length=1, max_length=3)
    density: Positive = 100.0
    friction: tuple[Nonnegative, Nonnegative, Nonnegative] = (0.8, 0.005, 0.0001)
    rgba: tuple[Unit, Unit, Unit, Unit] = (0.22, 0.52, 0.45, 1.0)
    collision: bool = True

    @model_validator(mode="after")
    def dimensions(self):
        count = {"sphere": 1, "box": 3, "capsule": 2, "cylinder": 2, "plane": 3}[self.shape]
        if len(self.size) != count:
            raise ValueError(f"{self.shape} requires {count} size components (radii or half lengths)")
        if self.shape == "plane" and self.body_id is not None:
            raise ValueError("planes belong to the fixed world, not articulated bodies")
        return self


class Joint(Named):
    body_id: Id
    kind: Literal["slide", "hinge"] = "slide"
    axis: Vec3 = (1.0, 0.0, 0.0)
    position: Vec3 = (0.0, 0.0, 0.0)
    limits: tuple[Number, Number] = (-1.0, 1.0)
    damping: Nonnegative = 0.5
    initial: Number = 0.0
    initial_jitter: Nonnegative = 0.0

    @model_validator(mode="after")
    def joint(self):
        if not math.isclose(math.fsum(v * v for v in self.axis), 1, rel_tol=0, abs_tol=1e-8):
            raise ValueError("joint axis must be a unit vector")
        low, high = self.limits
        if low >= high or self.initial - self.initial_jitter < low or self.initial + self.initial_jitter > high:
            raise ValueError("joint limits must contain its full initial randomization interval")
        return self


class Motor(Named):
    port: int = Field(ge=0, le=4095)
    joint_id: Id
    gear: Positive = 1.0
    control_limit: Positive = 1.0
    projection_gain: Nonnegative = 0.02


class SensorPort(Named):
    port: int = Field(ge=0, le=4095)


class JointSensor(SensorPort):
    kind: Literal["joint_position", "joint_velocity"]
    joint_id: Id
    scale: Positive = 1.0


class TouchSensor(SensorPort):
    kind: Literal["touch"] = "touch"
    geometry_id: Id
    scale: Positive = 1.0


class RangeSensor(SensorPort, Pose):
    kind: Literal["rangefinder"] = "rangefinder"
    body_id: Id
    maximum_distance: Positive = 10.0


class CameraSensor(SensorPort, Pose):
    kind: Literal["camera_rgb"] = "camera_rgb"
    body_id: Id
    width: int = Field(default=8, ge=1, le=512)
    height: int = Field(default=8, ge=1, le=512)
    fovy: float = Field(default=60.0, gt=1, lt=179)


class InertialSensor(SensorPort, Pose):
    kind: Literal["accelerometer", "gyroscope"]
    body_id: Id
    scale: Positive = 10.0
    enabled: bool = True


Sensor = Annotated[JointSensor | TouchSensor | RangeSensor | CameraSensor | InertialSensor, Field(discriminator="kind")]


class Force(Named):
    body_id: Id
    force: Vec3 = (0.0, 0.0, 0.0)
    torque: Vec3 = (0.0, 0.0, 0.0)


class WorldSpec(Model):
    schema_id: Literal["threemind.world/1", "threemind.world/2"] = "threemind.world/1"
    label: str = Field(default="", max_length=120)
    wiring_namespace: Id = "physical-world-v1"
    physics: Physics = Field(default_factory=Physics)
    bodies: list[Body] = Field(default_factory=list, max_length=256)
    geometries: list[Geometry] = Field(default_factory=list, max_length=1024)
    joints: list[Joint] = Field(default_factory=list, max_length=512)
    motors: list[Motor] = Field(default_factory=list, max_length=512)
    sensors: list[Sensor] = Field(default_factory=list, max_length=256)
    forces: list[Force] = Field(default_factory=list, max_length=256)

    @model_validator(mode="after")
    def references(self):
        if self.schema_id == "threemind.world/1" and any(isinstance(s, InertialSensor) for s in self.sensors):
            raise ValueError("inertial sensors require explicit world/2; world/1 is preserved")
        for name in ("bodies", "geometries", "joints", "motors", "sensors", "forces"):
            ids = [v.id for v in getattr(self, name)]
            if len(set(ids)) != len(ids):
                raise ValueError(f"duplicate {name} id")
        for name in ("motors", "sensors"):
            ports = [v.port for v in getattr(self, name)]
            if len(set(ports)) != len(ports):
                raise ValueError(f"duplicate {name} port number")
        bodies = {v.id: v for v in self.bodies}
        joints = {v.id: v for v in self.joints}
        geoms = {v.id: v for v in self.geometries}
        for body in self.bodies:
            if body.free and body.parent_id is not None:
                raise ValueError("a free body must be a root body")
            visited = {body.id}
            parent = body.parent_id
            while parent is not None:
                if parent not in bodies or parent in visited:
                    raise ValueError("body hierarchy contains a cycle or missing parent")
                visited.add(parent)
                if len(visited) > 32:
                    raise ValueError("body hierarchy exceeds 32 levels")
                parent = bodies[parent].parent_id
        for obj in [*self.geometries, *self.joints, *self.sensors, *self.forces]:
            body_id = getattr(obj, "body_id", None)
            if body_id is not None and body_id not in bodies:
                raise ValueError(f"{obj.id}: missing body {body_id}")
        for joint in self.joints:
            if bodies[joint.body_id].free:
                raise ValueError("a free body cannot also have scalar joints")
        for obj in [*self.motors, *self.sensors]:
            if getattr(obj, "joint_id", None) is not None and obj.joint_id not in joints:
                raise ValueError(f"{obj.id}: missing joint")
        for obj in self.sensors:
            if isinstance(obj, TouchSensor) and obj.geometry_id not in geoms:
                raise ValueError(f"{obj.id}: missing touch geometry")
        # Explicit protocol budget, never adjusted by a frontend display tier.
        if sum(v.width * v.height * 3 for v in self.sensors if isinstance(v, CameraSensor)) > 786432:
            raise ValueError("RGB sensors exceed the declared 786432 scalar values per sample budget")
        return self

    @property
    def digest(self):
        return digest(self.model_dump(mode="json"))

    def physical_document(self):
        value = self.model_dump(mode="json")
        value.pop("label")
        for name in ("bodies", "geometries", "joints", "motors", "sensors", "forces"):
            value[name] = sorted(value[name], key=lambda v: v["id"])
            for obj in value[name]:
                obj.pop("label")
        return value

    @property
    def physical_digest(self):
        return digest(self.physical_document())


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


MAX_WORLD_BYTES = 4 * 1024 * 1024


def parse_world(value):
    # JSON validation accepts arrays for typed tuples, while preserving strict
    # numbers, booleans and duplicate/unknown-field checks at the public boundary.
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate world field: {key}")
            result[key] = value
        return result

    if isinstance(value, (str, bytes)):
        if len(value.encode("utf-8") if isinstance(value, str) else value) > MAX_WORLD_BYTES:
            raise ValueError("world protocol exceeds 4 MiB")
        value = json.loads(value, object_pairs_hook=unique)
    encoded = json.dumps(value, allow_nan=False, ensure_ascii=False).encode("utf-8")
    if len(encoded) > MAX_WORLD_BYTES:
        raise ValueError("world protocol exceeds 4 MiB")
    return WorldSpec.model_validate_json(encoded, strict=True)


def default_world():
    return WorldSpec(
        label="平面探索世界",
        bodies=[Body(id="body", label="虚拟躯体", position=(0.0, 0.0, 0.15))],
        geometries=[
            Geometry(id="floor", label="地面", shape="plane", size=(3.0, 3.0, 0.1), rgba=(0.7, 0.73, 0.7, 1.0)),
            Geometry(id="shell", label="躯体外壳", body_id="body"),
            Geometry(id="wall", label="障碍物", shape="box", size=(0.12, 0.8, 0.3), position=(1.3, 0.0, 0.3)),
        ],
        joints=[
            Joint(id="x", body_id="body", limits=(-2.0, 2.0), initial_jitter=0.7),
            Joint(id="y", body_id="body", axis=(0.0, 1.0, 0.0), limits=(-2.0, 2.0), initial_jitter=0.7),
        ],
        motors=[Motor(id="move_x", port=0, joint_id="x"), Motor(id="move_y", port=1, joint_id="y")],
        sensors=[
            JointSensor(id="position_x", port=0, kind="joint_position", joint_id="x"),
            JointSensor(id="position_y", port=1, kind="joint_position", joint_id="y"),
            JointSensor(id="velocity_x", port=2, kind="joint_velocity", joint_id="x"),
            JointSensor(id="velocity_y", port=3, kind="joint_velocity", joint_id="y"),
            TouchSensor(id="contact", port=4, geometry_id="shell"),
            RangeSensor(
                id="distance", port=5, body_id="body", quaternion=(0.7071067811865476, 0.0, 0.7071067811865476, 0.0)
            ),
        ],
    )
