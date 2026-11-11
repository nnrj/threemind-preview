"""A body's sensory and actuator ports attached to an externally owned physics state.

Port identities use the local declaration and sensory seed. Physical instance
prefixes only address MuJoCo objects and never enter the anonymous wiring.
"""

from __future__ import annotations

import hashlib
import math

from .adapters import channel_id
from .world_schema import CameraSensor, InertialSensor, JointSensor, RangeSensor, TouchSensor


class WorldPorts:
    def __init__(self, model, data, spec, seed, *, prefix=""):
        import mujoco
        import numpy as np

        self.mj, self.np = mujoco, np
        self.model, self.data, self.spec, self.seed = model, data, spec, seed
        self.prefix = prefix
        self.renderers, self.render_calibration = {}, {}
        self.last_measurements, self.last_controls = [], []
        self._projection = {}
        self.channel_mask = channel_id(seed, "world-port-v1:" + spec.wiring_namespace, 0)
        try:
            for sensor in spec.sensors:
                if isinstance(sensor, CameraSensor):
                    renderer = mujoco.Renderer(model, height=sensor.height, width=sensor.width)
                    self.renderers[sensor.id] = renderer
                    renderer.update_scene(data, camera=self.name("c_", sensor.id))
                    self.render_calibration[sensor.id] = hashlib.sha256(renderer.render().tobytes()).hexdigest()
        except BaseException:
            self.close()
            raise

    def name(self, kind, identity):
        return self.prefix + kind + identity

    def close(self):
        for renderer in self.renderers.values():
            renderer.close()
        self.renderers.clear()

    def _control(self, activations):
        values = sorted((int(i), float(v)) for i, v in (activations or ()))
        if any(not math.isfinite(v) or v < 0 for _, v in values):
            raise ValueError("motor readout requires finite nonnegative activations")
        cache, result = {}, []
        motors = sorted(self.spec.motors, key=lambda v: v.id)
        for node, _ in values:
            cache[node] = self._projection.get(node) or tuple(
                1 if channel_id(self.seed, f"world-motor-v1:{self.spec.wiring_namespace}:{m.port}", node) & 1 else -1
                for m in motors
            )
        for index, motor in enumerate(motors):
            raw = math.fsum(cache[node][index] * value for node, value in values)
            control = motor.control_limit * math.tanh(raw * motor.projection_gain)
            self.data.actuator(self.name("a_", motor.id)).ctrl[0] = control
            result.append({"id": motor.id, "port": motor.port, "activation_projection": raw, "control": control})
        self._projection = cache  # Pruned Core nodes cannot accumulate here.
        self.last_controls = result

    def _senses(self):
        channels, measurements = [], []
        touch = {}
        if any(isinstance(s, TouchSensor) for s in self.spec.sensors):
            force = self.np.empty(6, dtype=self.np.float64)
            for index in range(self.data.ncon):
                self.mj.mj_contactForce(self.model, self.data, index, force)
                magnitude = float(self.np.linalg.norm(force[:3]))
                for geom in self.data.contact[index].geom:
                    touch[int(geom)] = touch.get(int(geom), 0.0) + magnitude
        for sensor in sorted(self.spec.sensors, key=lambda v: v.port):
            if isinstance(sensor, InertialSensor):
                if not sensor.enabled:
                    continue
                observed = [float(v) for v in self.data.sensor(self.name("s_", sensor.id)).data]
                values = [(2 * axis + int(v < 0), abs(math.tanh(v / sensor.scale))) for axis, v in enumerate(observed)]
            elif isinstance(sensor, JointSensor):
                joint = self.data.joint(self.name("j_", sensor.joint_id))
                raw = float(joint.qpos[0] if sensor.kind == "joint_position" else joint.qvel[0])
                value = math.tanh(raw / sensor.scale)
                values = [(int(value < 0), abs(value))]
                observed = [raw]
            elif isinstance(sensor, TouchSensor):
                raw = touch.get(int(self.model.geom(self.name("g_", sensor.geometry_id)).id), 0.0)
                values, observed = [(0, math.tanh(raw / sensor.scale))], [raw]
            elif isinstance(sensor, RangeSensor):
                raw = float(self.data.sensor(self.name("s_", sensor.id)).data[0])
                hit = 0 <= raw <= sensor.maximum_distance
                values = [(0, raw / sensor.maximum_distance if hit else 1.0), (1, float(hit))]
                observed = [raw, float(hit)]
            else:
                renderer = self.renderers[sensor.id]
                renderer.update_scene(self.data, camera=self.name("c_", sensor.id))
                pixels = renderer.render().reshape(-1)
                observed = pixels.tolist()
                values = ((i, float(v) / 255) for i, v in enumerate(pixels))
            encoded = []
            for index, value in values:
                if value:
                    # Explicit port blocks plus XOR are bijective, unlike
                    # independently hashing hundreds of thousands of pixels.
                    channels.append((((sensor.port << 20) | index) ^ self.channel_mask, value))
                    encoded.append({"channel": channels[-1][0], "value": value})
            measurement = {"id": sensor.id, "port": sensor.port, "kind": sensor.kind, "values": observed}
            if self.spec.schema_id == "threemind.world/2":
                measurement.update(
                    encoded=encoded,
                    scale=getattr(sensor, "scale", None),
                    unit={"accelerometer": "m/s²", "gyroscope": "rad/s"}.get(sensor.kind, "sensor-specific"),
                    coordinate_frame="sensor-local" if isinstance(sensor, InertialSensor) else "declared-port",
                )
            measurements.append(measurement)
        self.last_measurements = measurements
        return tuple(sorted(channels))

    def stimulus_unit(self, stimulus, *, capture_us):
        """Observer carrier of the already measured frame; never resample physics."""
        from copy import deepcopy

        from .stimulus_units import VERSION

        return {
            "schema_id": VERSION,
            "kind": "group",
            "source": "physical-world",
            "time_us": str(stimulus.time_us),
            "capture_time_us": str(capture_us),
            "intensity": stimulus.intensity,
            "mapping_version": "world-port/" + self.spec.schema_id.rsplit("/", 1)[1],
            "grouping_basis": "same body/world sensory sampling boundary",
            "coordinate_frame": "declared-sensor-local",
            "elements": [{"channel": c, "value": v} for c, v in stimulus.channels],
            "measurements": deepcopy(self.last_measurements),
        }
