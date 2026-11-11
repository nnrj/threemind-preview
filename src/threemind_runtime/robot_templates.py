"""Small editable bodies with direct motors, no hidden balancing/IK policies."""

import math

from .robot_protocol import RobotTask
from .world_schema import Body, Geometry, InertialSensor, Joint, JointSensor, Motor, Physics, TouchSensor, WorldSpec


def _sensors(joints, body, contact):
    sensors = []
    for joint in joints:
        for kind, scale in (("joint_position", 3.0), ("joint_velocity", 5.0)):
            sensors.append(
                JointSensor(id=kind + "_" + joint.id, port=len(sensors), kind=kind, joint_id=joint.id, scale=scale)
            )
    sensors.extend(
        [
            InertialSensor(id="acceleration", port=100, kind="accelerometer", body_id=body, scale=9.81),
            InertialSensor(id="angular_velocity", port=101, kind="gyroscope", body_id=body, scale=3.0),
            TouchSensor(id="contact", port=102, geometry_id=contact, scale=10.0),
        ]
    )
    return sensors


def custom_arm():
    q = (math.sqrt(0.5), 0.0, math.sqrt(0.5), 0.0)
    bodies = [Body(id="base", position=(0.0, 0.0, 0.12))]
    geometries = [
        Geometry(id="floor", shape="plane", size=(1.5, 1.5, 0.05)),
        Geometry(id="base", body_id="base", shape="cylinder", size=(0.07, 0.06)),
    ]
    joints, motors = [], []
    previous, previous_length = "base", 0.0
    for i, length in enumerate((0.24, 0.22, 0.12)):
        identity = f"link{i}"
        bodies.append(Body(id=identity, parent_id=previous, position=(previous_length, 0.0, 0.0)))
        geometries.append(
            Geometry(
                id=identity,
                body_id=identity,
                shape="capsule",
                size=(0.025, length / 2),
                position=(length / 2, 0.0, 0.0),
                quaternion=q,
                density=350.0,
                rgba=(0.18, 0.48 + i * 0.1, 0.42, 1.0),
            )
        )
        joints.append(
            Joint(id=identity, body_id=identity, kind="hinge", axis=(0.0, 0.0, 1.0), limits=(-2.8, 2.8), damping=0.2)
        )
        motors.append(Motor(id=identity, port=i, joint_id=identity, control_limit=1.5, projection_gain=0.02))
        previous, previous_length = identity, length
    bodies.extend(
        [
            Body(id="tool", parent_id=previous, position=(previous_length, 0.0, 0.0)),
            Body(id="finger", parent_id="tool", position=(0.03, 0.03, 0.0)),
        ]
    )
    geometries.extend(
        [
            Geometry(id="tool", body_id="tool", shape="box", size=(0.04, 0.01, 0.03), position=(0.02, -0.025, 0.0)),
            Geometry(id="finger", body_id="finger", shape="box", size=(0.04, 0.01, 0.03)),
        ]
    )
    joints.append(
        Joint(id="gripper", body_id="finger", axis=(0.0, 1.0, 0.0), limits=(0.0, 0.06), initial=0.03, damping=1.0)
    )
    motors.append(Motor(id="gripper", port=3, joint_id="gripper", control_limit=2.0, projection_gain=0.02))
    world = WorldSpec(
        schema_id="threemind.world/2",
        label="原始力矩机械臂",
        wiring_namespace="robot-arm-v1",
        physics=Physics(step_us=2000, sample_us=10000),
        bodies=bodies,
        geometries=geometries,
        joints=joints,
        motors=motors,
        sensors=_sensors(joints, "tool", "finger"),
    )
    return RobotTask(name="机械臂接近目标", world=world)


def custom_mobile():
    q = (math.sqrt(0.5), math.sqrt(0.5), 0.0, 0.0)
    bodies = [Body(id="base", free=True, position=(0.0, 0.0, 0.10))]
    geoms = [
        Geometry(id="floor", shape="plane", size=(3.0, 3.0, 0.05)),
        Geometry(id="base", body_id="base", shape="box", size=(0.14, 0.10, 0.04)),
        Geometry(
            id="caster",
            body_id="base",
            shape="sphere",
            size=(0.025,),
            position=(-0.11, 0.0, -0.075),
            friction=(0.01, 0.001, 0.0001),
        ),
    ]
    joints, motors = [], []
    for index, side in enumerate((-1.0, 1.0)):
        identity = f"wheel{index}"
        bodies.append(Body(id=identity, parent_id="base", position=(0.04, side * 0.125, -0.02)))
        geoms.append(Geometry(id=identity, body_id=identity, shape="cylinder", size=(0.08, 0.025), quaternion=q))
        joints.append(
            Joint(
                id=identity,
                body_id=identity,
                kind="hinge",
                axis=(0.0, 1.0, 0.0),
                limits=(-100000.0, 100000.0),
                damping=0.02,
            )
        )
        motors.append(Motor(id=identity, port=index, joint_id=identity, control_limit=1.0))
    world = WorldSpec(
        schema_id="threemind.world/2",
        label="原始力矩差速底盘",
        wiring_namespace="robot-mobile-v1",
        physics=Physics(step_us=2000, sample_us=10000),
        bodies=bodies,
        geometries=geoms,
        joints=joints,
        motors=motors,
        sensors=_sensors(joints, "base", "base"),
    )
    return RobotTask(
        name="移动底盘观测",
        body_id="custom-mobile/1",
        category="mobile",
        world=world,
        endpoint_body="base",
        objective="observe",
        target=(0.8, 0.3, 0.1),
    )


def robot_templates():
    reach = custom_arm()
    push = custom_arm().model_dump(mode="json")
    push.update(name="机械臂推动物体", objective="push", object_body="object", target=[0.35, 0.30, 0.04])
    push["world"]["bodies"].append(Body(id="object", free=True, position=(0.43, 0.12, 0.04)).model_dump(mode="json"))
    push["world"]["geometries"].append(
        Geometry(id="object", body_id="object", shape="box", size=(0.04, 0.04, 0.04), density=200.0).model_dump(
            mode="json"
        )
    )
    from .robot_protocol import parse_robot, playground_template

    return {"custom-arm-reach": reach, "custom-arm-push": parse_robot(push), "custom-mobile": custom_mobile(),
            "playground-panda": playground_template()}
