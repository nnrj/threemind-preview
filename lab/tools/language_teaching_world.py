"""Small MuJoCo visual teaching apparatus, not an ecological/behavioural simulation.

Four rigid objects remain present. A camera is aimed by the external teacher;
ray distances and rendered material RGB are sensory measurements. Names stay
with the external teacher and never appear in the Core payload.
"""

import math

import mujoco
import numpy as np

from threemind_core import Stimulus
from threemind_runtime.receptors import ReceptorWiring

WORDS = ("红球", "蓝盒", "绿柱", "黄块")


class TeachingWorld:
    def __init__(self, seed=17):
        self.wiring = ReceptorWiring(seed)
        self.model = mujoco.MjModel.from_xml_string('''
        <mujoco><option timestep="0.005" gravity="0 0 -9.81"/>
        <worldbody><geom type="plane" size="4 4 0.1" rgba="0.4 0.4 0.4 1"/>
        <body name="a" pos="-0.6 -0.6 0.15"><freejoint/><geom type="sphere" size="0.12" mass="0.1" rgba="1 0.1 0.1 1"/></body>
        <body name="b" pos="0.6 -0.6 0.15"><freejoint/><geom type="box" size="0.1 0.12 0.12" mass="0.1" rgba="0.1 0.1 1 1"/></body>
        <body name="c" pos="-0.6 0.6 0.18"><freejoint/><geom type="cylinder" size="0.1 0.15" mass="0.1" rgba="0.1 1 0.1 1"/></body>
        <body name="d" pos="0.6 0.6 0.15"><freejoint/><geom type="box" size="0.14 0.08 0.1" mass="0.1" rgba="1 1 0.1 1"/></body>
        </worldbody></mujoco>''')
        self.data = mujoco.MjData(self.model)
        for _ in range(200):
            mujoco.mj_step(self.model, self.data)

    def sample(self, item, variant=0):
        if not 0 <= item < 4:
            raise ValueError("four physical teaching objects")
        target = self.data.xpos[item + 1].copy()
        angle = variant * 0.73
        distance = 0.45 + 0.025 * (variant % 5)
        origin = target + np.array([math.cos(angle) * distance, math.sin(angle) * distance, 0.18])
        forward = target - origin
        forward /= np.linalg.norm(forward)
        right = np.cross(forward, np.array([0., 0., 1.]))
        right /= np.linalg.norm(right)
        up = np.cross(right, forward)
        values, rays = [], []
        for x, y in ((0, 0), (-0.13, 0), (0.13, 0), (0, -0.13), (0, 0.13)):
            direction = forward + x * right + y * up
            direction /= np.linalg.norm(direction)
            geometry = np.array([-1], dtype=np.int32)
            length = float(mujoco.mj_ray(self.model, self.data, origin, direction, None, 1, -1, geometry))
            color = self.model.geom_rgba[int(geometry[0]), :3].astype(float) if geometry[0] >= 0 else np.zeros(3)
            value = [0.0 if length < 0 else 1 / (1 + length), *color.tolist()]
            values.extend(value)
            rays.append({"distance_m": length, "rgb": color.tolist(), "direction": direction.tolist()})
        return {"schema": "threemind.visual-teaching-world/1", "time_s": float(self.data.time),
                "camera_origin_m": origin.tolist(), "rays": rays, "values": values,
                "object_positions_m": self.data.xpos[1:].tolist(), "gravity_m_s2": [0, 0, -9.81],
                "teacher_selected_view": True, "active_body_control": False}

    def frame(self, observation, amount=2.0):
        values = observation["values"]
        total = sum(values)
        return Stimulus(0, tuple((self.wiring.identity(0xD00000 + i), v / total * amount)
                                 for i, v in enumerate(values) if v), intensity=1.0)


def co_observed(frames, visual):
    """One declared language/vision acquisition. Independent telemetry stays separate."""
    from dataclasses import replace

    result = []
    for row in frames:
        stimulus = row["stimulus"]
        channels = dict(stimulus.channels)
        if set(channels) & dict(visual.channels).keys():
            raise ValueError("visual and language wiring collision")
        channels.update(visual.channels)
        result.append({"stimulus": replace(stimulus, channels=tuple(sorted(channels.items()))), "labels": {}})
    return result
