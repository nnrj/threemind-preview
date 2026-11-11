from __future__ import annotations

import hashlib
import math
import random

from threemind_core import Stimulus


def channel_id(seed: int, namespace: str, index: int) -> int:
    return int.from_bytes(hashlib.blake2s(f"{seed}:{namespace}:{index}".encode(), digest_size=4).digest(), "big")


def sensory_vector(time_us: int, values, *, seed: int, namespace: str) -> Stimulus:
    channels = []
    for index, value in enumerate(values):
        # Signed physical signals are split into nonnegative receptor amplitudes.
        value = math.tanh(float(value))
        if value:
            channels.append((channel_id(seed, namespace, index * 2 + (value < 0)), abs(value)))
    return Stimulus(time_us, tuple(channels))


class HostTelemetry:
    period_us = 1_000_000

    def __init__(self, seed):
        import psutil

        self.psutil, self.seed = psutil, seed
        psutil.cpu_percent(None)

    def sample(self, time_us, graph=None):
        memory = self.psutil.virtual_memory()
        return sensory_vector(
            time_us,
            [self.psutil.cpu_percent(None) / 100, memory.percent / 100],
            seed=self.seed,
            namespace="host-physical-v1",
        )

    def capture(self):
        return {"kind": "host", "exact_external_resume": False}


class PlanarBody:
    """Versioned two-axis physical body. No semantic goal or trained controller."""

    period_us = 20_000
    XML = """<mujoco model="threemind-planar-v1"><option timestep="0.005" gravity="0 0 0" integrator="RK4"/>
      <worldbody><geom type="plane" size="2 2 .1"/><body pos="0 0 .12">
        <joint name="x" type="slide" axis="1 0 0" damping=".5" limited="true" range="-1 1"/>
        <joint name="y" type="slide" axis="0 1 0" damping=".5" limited="true" range="-1 1"/>
        <geom type="sphere" size=".1" mass="1"/></body></worldbody>
      <actuator><motor joint="x" ctrllimited="true" ctrlrange="-1 1"/><motor joint="y" ctrllimited="true" ctrlrange="-1 1"/></actuator>
    </mujoco>"""

    def __init__(self, seed, state=None, *, environment_seed=None):
        import mujoco

        self.mj, self.seed = mujoco, seed
        self.environment_seed = environment_seed
        self._wiring = {}
        self.model = mujoco.MjModel.from_xml_string(self.XML)
        self.data = mujoco.MjData(self.model)
        rng = random.Random(seed if environment_seed is None else environment_seed)
        self.phase = rng.random() * math.tau
        if state:
            if (
                state.get("version") != "planar-v1"
                or state.get("xml_sha256") != hashlib.sha256(self.XML.encode()).hexdigest()
                or state.get("mujoco_version") != mujoco.__version__
                or state.get("environment_seed") != environment_seed
            ):
                raise ValueError(
                    "environment version differs; exact continuation requires the recorded MuJoCo and XML versions"
                )
            self.phase = state["phase"]
            self.data.time = state["time"]
            self.data.qpos[:] = state["qpos"]
            self.data.qvel[:] = state["qvel"]
            self.data.act[:] = state["act"]
            self.data.ctrl[:] = state["ctrl"]
            self.data.qacc_warmstart[:] = state["qacc_warmstart"]
        else:
            self.data.qpos[:] = [rng.uniform(-0.7, 0.7), rng.uniform(-0.7, 0.7)]
        mujoco.mj_forward(self.model, self.data)

    def sample(self, time_us, graph=None):
        actions = [0.0, 0.0]
        # Versioned actuator wiring is outside the core and does not label any node.
        values = (
            ((n["id"], n["activation"]) for n in graph.get("nodes", [])) if isinstance(graph, dict) else (graph or ())
        )
        wiring = {}
        for node_id, activation in values:
            signs = self._wiring.get(node_id)
            if signs is None:
                signs = tuple(
                    1 if channel_id(self.seed, "actuator", node_id * 2 + axis) & 1 else -1 for axis in range(2)
                )
            wiring[node_id] = signs
            for axis in range(2):
                actions[axis] += signs[axis] * activation * 0.02
        self._wiring = wiring  # Pruned nodes cannot accumulate in the adapter cache.
        self.data.ctrl[:] = [math.tanh(a) for a in actions]
        for _ in range(4):
            # An explicitly modeled physical force, common across paired branches.
            self.data.qfrc_applied[:] = [
                0.15 * math.sin(self.data.time + self.phase),
                0.15 * math.cos(self.data.time * 0.7 + self.phase),
            ]
            self.mj.mj_step(self.model, self.data)
        values = [*self.data.qpos, *self.data.qvel, *self.data.qacc, *self.data.qfrc_constraint]
        # Actions computed at t affect the physical interval [t,t+period]. The
        # resulting sensory event is delivered at its END, never backdated to t.
        return sensory_vector(time_us + self.period_us, values, seed=self.seed, namespace="planar-physical-v1")

    def capture(self):
        return {
            "kind": "mujoco",
            "version": "planar-v1",
            "phase": self.phase,
            "time": float(self.data.time),
            "qpos": self.data.qpos.tolist(),
            "qvel": self.data.qvel.tolist(),
            "act": self.data.act.tolist(),
            "ctrl": self.data.ctrl.tolist(),
            "qacc_warmstart": self.data.qacc_warmstart.tolist(),
            "xml_sha256": hashlib.sha256(self.XML.encode()).hexdigest(),
            "mujoco_version": self.mj.__version__,
            **({"environment_seed": self.environment_seed} if self.environment_seed is not None else {}),
        }
