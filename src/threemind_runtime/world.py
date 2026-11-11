"""Headless MuJoCo transducer. Core only sees ordinary anonymous Stimulus objects."""

from __future__ import annotations

import copy
import hashlib
import math
import random
import xml.etree.ElementTree as ET

from threemind_core import Stimulus

from .world_ports import WorldPorts
from .world_schema import CameraSensor, InertialSensor, RangeSensor, WorldSpec, parse_world

WORLD_STATE = "threemind.world-state/1"


def numbers(values):
    return " ".join(format(float(v), ".17g") for v in values)


def compile_xml(spec: WorldSpec):
    """Only build elements from validated values; no includes, paths or plugins."""
    root = ET.Element("mujoco", model="threemind-world-v" + spec.schema_id.rsplit("/", 1)[1])
    ET.SubElement(root, "compiler", angle="radian", autolimits="true")
    cfg = spec.physics
    ET.SubElement(
        root,
        "option",
        timestep=numbers([cfg.step_us / 1e6]),
        gravity=numbers(cfg.gravity),
        integrator=cfg.integrator,
        iterations=str(cfg.iterations),
    )
    visual = ET.SubElement(root, "visual")
    cameras = [s for s in spec.sensors if isinstance(s, CameraSensor)]
    ET.SubElement(
        visual,
        "global",
        offwidth=str(max([64, *(s.width for s in cameras)])),
        offheight=str(max([64, *(s.height for s in cameras)])),
    )
    world = ET.SubElement(root, "worldbody")
    ET.SubElement(world, "light", pos="2 -2 4", dir="-1 1 -2", directional="true")
    elements = {None: world}

    def body_tree(parent):
        for body in sorted((v for v in spec.bodies if v.parent_id == parent), key=lambda v: v.id):
            elements[body.id] = ET.SubElement(
                elements[parent], "body", name="b_" + body.id, pos=numbers(body.position), quat=numbers(body.quaternion)
            )
            if body.free:
                ET.SubElement(elements[body.id], "freejoint", name="f_" + body.id)
            body_tree(body.id)

    body_tree(None)
    for geom in sorted(spec.geometries, key=lambda v: v.id):
        ET.SubElement(
            elements[geom.body_id],
            "geom",
            name="g_" + geom.id,
            type=geom.shape,
            size=numbers(geom.size),
            pos=numbers(geom.position),
            quat=numbers(geom.quaternion),
            density=str(geom.density),
            friction=numbers(geom.friction),
            rgba=numbers(geom.rgba),
            contype="1" if geom.collision else "0",
            conaffinity="1" if geom.collision else "0",
        )
    for joint in sorted(spec.joints, key=lambda v: v.id):
        ET.SubElement(
            elements[joint.body_id],
            "joint",
            name="j_" + joint.id,
            type=joint.kind,
            pos=numbers(joint.position),
            axis=numbers(joint.axis),
            range=numbers(joint.limits),
            damping=str(joint.damping),
            limited="true",
        )
    actuators = ET.SubElement(root, "actuator")
    for motor in sorted(spec.motors, key=lambda v: v.id):
        ET.SubElement(
            actuators,
            "motor",
            name="a_" + motor.id,
            joint="j_" + motor.joint_id,
            gear=str(motor.gear),
            ctrllimited="true",
            ctrlrange=numbers([-motor.control_limit, motor.control_limit]),
        )
    sensors = ET.SubElement(root, "sensor")
    for sensor in sorted(spec.sensors, key=lambda v: v.id):
        if isinstance(sensor, (RangeSensor, InertialSensor)):
            ET.SubElement(
                elements[sensor.body_id],
                "site",
                name="p_" + sensor.id,
                pos=numbers(sensor.position),
                quat=numbers(sensor.quaternion),
                size="0.001",
                rgba="0 0 0 0",
            )
            tag = "gyro" if sensor.kind == "gyroscope" else sensor.kind
            ET.SubElement(sensors, tag, name="s_" + sensor.id, site="p_" + sensor.id)
        elif isinstance(sensor, CameraSensor):
            ET.SubElement(
                elements[sensor.body_id],
                "camera",
                name="c_" + sensor.id,
                pos=numbers(sensor.position),
                quat=numbers(sensor.quaternion),
                fovy=str(sensor.fovy),
            )
    return ET.tostring(root, encoding="unicode")


class PhysicalWorld(WorldPorts):
    def _compile_model(self):
        xml = compile_xml(self.spec)
        return xml, self.mj.MjModel.from_xml_string(xml)

    def __init__(self, protocol, seed, state=None, *, environment_seed=None):
        import mujoco
        import numpy as np

        self.mj, self.np = mujoco, np
        self.prefix = ""
        self.spec = parse_world(protocol.model_dump(mode="json") if isinstance(protocol, WorldSpec) else protocol)
        self.protocol_hash, self.physical_hash = self.spec.digest, self.spec.physical_digest
        self.state_schema = "threemind.world-state/" + self.spec.schema_id.rsplit("/", 1)[1]
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise ValueError("invalid world sensory seed")
        if environment_seed is not None and (type(environment_seed) is not int or not 0 <= environment_seed < 2**32):
            raise ValueError("invalid world environment seed")
        self.seed, self.environment_seed = seed, environment_seed
        self.period_us = self.spec.physics.sample_us
        self.xml, self.model = self._compile_model()
        self.xml_sha256 = hashlib.sha256(self.xml.encode()).hexdigest()
        self.data = mujoco.MjData(self.model)
        self.state_mask = int(mujoco.mjtState.mjSTATE_INTEGRATION)
        self.state_size = mujoco.mj_stateSize(self.model, self.state_mask)
        self.renderers = {}
        self.elapsed_us = self.samples = 0
        self.last_delivery_us = None
        # Per-joint random streams avoid editor order and unrelated object names
        # changing the physical initial values of existing joints.
        for joint in self.spec.joints:
            rng = random.Random(f"world-initial-v1:{seed if environment_seed is None else environment_seed}:{joint.id}")
            self.data.joint(self.name("j_", joint.id)).qpos[0] = joint.initial + rng.uniform(
                -joint.initial_jitter, joint.initial_jitter
            )
        mujoco.mj_forward(self.model, self.data)
        try:
            super().__init__(self.model, self.data, self.spec, seed)
            if state is not None:
                self._restore(state)
            self._check_physics()
        except BaseException:
            self.close()
            raise

    def _integration(self):
        values = self.np.empty(self.state_size, dtype=self.np.float64)
        self.mj.mj_getState(self.model, self.data, values, self.state_mask)
        return values

    def _restore(self, state):
        expected = {
            "schema": self.state_schema,
            "physical_hash": self.physical_hash,
            "xml_sha256": self.xml_sha256,
            "mujoco_version": self.mj.__version__,
            "seed": self.seed,
            "environment_seed": self.environment_seed,
            "state_mask": self.state_mask,
            "render_calibration": self.render_calibration,
        }
        if not isinstance(state, dict) or any(state.get(k) != v for k, v in expected.items()):
            raise ValueError(
                "world protocol, wiring, physics version or RGB calibration differs; exact continuation refused"
            )
        values = self.np.asarray(state.get("integration"), dtype=self.np.float64)
        if values.shape != (self.state_size,) or not self.np.isfinite(values).all():
            raise ValueError("invalid physical integration state")
        elapsed, samples = state.get("elapsed_us"), state.get("samples")
        if type(elapsed) is not int or type(samples) is not int or elapsed < 0 or elapsed != samples * self.period_us:
            raise ValueError("invalid world clock state")
        if not math.isclose(float(values[0]), elapsed / 1e6, rel_tol=0, abs_tol=max(1e-9, elapsed / 1e6 * 1e-10)):
            raise ValueError("physical clock does not match recorded intervals")
        self.mj.mj_setState(self.model, self.data, values, self.state_mask)
        self.mj.mj_forward(self.model, self.data)
        # Recompute derived transforms without replacing the saved solver warm
        # start. Rendering and checkpoint reads cannot change integration state.
        self.mj.mj_setState(self.model, self.data, values, self.state_mask)
        self.elapsed_us, self.samples = elapsed, samples
        self.last_delivery_us = state.get("last_delivery_us")
        self.last_measurements = copy.deepcopy(state.get("measurements", []))
        self.last_controls = copy.deepcopy(state.get("controls", []))

    def _check_physics(self):
        warnings = [i for i, v in enumerate(self.data.warning) if v.number]
        if warnings or not self.np.isfinite(self._integration()).all():
            raise ValueError(f"physical simulation produced warnings or nonfinite state: {warnings}")

    def sample(self, time_us, graph=None):
        if (
            type(time_us) is not int
            or time_us < 0
            or (self.last_delivery_us is not None and time_us != self.last_delivery_us)
        ):
            raise ValueError("world steps must follow consecutive declared sensory boundaries")
        activations = ((n["id"], n["activation"]) for n in graph.get("nodes", [])) if isinstance(graph, dict) else graph
        self._control(activations)
        self.data.xfrc_applied[:] = 0
        for force in sorted(self.spec.forces, key=lambda v: v.id):
            self.data.body(self.name("b_", force.body_id)).xfrc_applied[:] += [*force.force, *force.torque]
        for _ in range(self.period_us // self.spec.physics.step_us):
            self.mj.mj_step(self.model, self.data)
        self.mj.mj_forward(self.model, self.data)
        self._check_physics()
        self.elapsed_us += self.period_us
        self.samples += 1
        self.last_delivery_us = time_us + self.period_us
        return Stimulus(self.last_delivery_us, self._senses())

    def observation(self, *, include_measurements=True):
        geometries = []
        for geom in self.spec.geometries:
            value = self.data.geom(self.name("g_", geom.id))
            geometries.append(
                {"id": geom.id, "position": value.xpos.tolist(), "rotation_matrix": value.xmat.reshape(-1).tolist()}
            )
        return {
            "schema": "threemind.world-observation/" + self.spec.schema_id.rsplit("/", 1)[1],
            "physical_time_us": str(self.elapsed_us),
            "delivery_time_us": str(self.last_delivery_us) if self.last_delivery_us is not None else None,
            "geometries": geometries,
            "bodies": [
                {
                    "id": body.id,
                    "position": self.data.body(self.name("b_", body.id)).xpos.tolist(),
                    "quaternion": self.data.body(self.name("b_", body.id)).xquat.tolist(),
                }
                for body in self.spec.bodies
            ],
            **(
                {
                    "stimulus_unit": self.stimulus_unit(
                        Stimulus(
                            self.last_delivery_us,
                            tuple(
                                sorted(
                                    (e["channel"], e["value"])
                                    for m in self.last_measurements
                                    for e in m.get("encoded", [])
                                )
                            ),
                        ),
                        capture_us=self.elapsed_us,
                    )
                }
                if self.spec.schema_id == "threemind.world/2"
                and self.last_delivery_us is not None
                and any(m.get("encoded") for m in self.last_measurements)
                else {}
            ),
            **(
                {"controls": copy.deepcopy(self.last_controls), "measurements": copy.deepcopy(self.last_measurements)}
                if include_measurements
                else {}
            ),
        }

    def capture(self):
        return {
            "schema": self.state_schema,
            "kind": "world",
            "world_hash": self.protocol_hash,
            "physical_hash": self.physical_hash,
            "xml_sha256": self.xml_sha256,
            "mujoco_version": self.mj.__version__,
            "seed": self.seed,
            "environment_seed": self.environment_seed,
            "state_mask": self.state_mask,
            "integration": self._integration().tolist(),
            "elapsed_us": self.elapsed_us,
            "samples": self.samples,
            "last_delivery_us": self.last_delivery_us,
            "render_calibration": dict(self.render_calibration),
            "controls": copy.deepcopy(self.last_controls),
            "measurements": copy.deepcopy(self.last_measurements),
            "observation": self.observation(include_measurements=False),
        }

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
