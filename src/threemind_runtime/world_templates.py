"""Small physical references, with no semantic targets or Core access."""

from .world_schema import Body, Force, Geometry, InertialSensor, Joint, JointSensor, Physics, WorldSpec


def physical_templates():
    sensors = [
        InertialSensor(id="acceleration", kind="accelerometer", body_id="body", port=0, scale=9.81),
        InertialSensor(id="angular_velocity", kind="gyroscope", body_id="body", port=1, scale=3.0),
    ]
    return {
        "inertial-cart": WorldSpec(
            schema_id="threemind.world/2",
            label="惯性滑车",
            physics=Physics(gravity=(0.0, 0.0, 0.0)),
            bodies=[Body(id="body")],
            geometries=[Geometry(id="cart", body_id="body", shape="box", size=(0.1, 0.1, 0.1))],
            joints=[Joint(id="slide", body_id="body", damping=0.0, limits=(-100.0, 100.0))],
            sensors=sensors
            + [
                JointSensor(id="position", port=2, kind="joint_position", joint_id="slide", scale=5.0),
                JointSensor(id="velocity", port=3, kind="joint_velocity", joint_id="slide", scale=2.0),
            ],
            forces=[Force(id="push", body_id="body", force=(0.01, 0.0, 0.0))],
        ),
        "gravity-pendulum": WorldSpec(
            schema_id="threemind.world/2",
            label="重力摆体",
            bodies=[Body(id="body", position=(0.0, 0.0, 1.5))],
            geometries=[Geometry(id="bob", body_id="body", position=(0.0, 0.0, -0.6), size=(0.1,))],
            joints=[
                Joint(
                    id="hinge",
                    body_id="body",
                    kind="hinge",
                    axis=(0.0, 1.0, 0.0),
                    limits=(-3.0, 3.0),
                    initial=0.7,
                    damping=0.002,
                )
            ],
            sensors=[s.model_copy(update={"position": (0.0, 0.0, -0.6)}) for s in sensors]
            + [
                JointSensor(id="angle", port=2, kind="joint_position", joint_id="hinge", scale=1.0),
                JointSensor(id="speed", port=3, kind="joint_velocity", joint_id="hinge", scale=3.0),
            ],
        ),
    }
