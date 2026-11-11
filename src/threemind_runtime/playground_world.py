"""Pinned official task outside Core. Scores are evidence, never input channels."""

import base64
import copy
import hashlib
import importlib.metadata
import io
import json
import math
import zipfile
from functools import cached_property, lru_cache

from threemind_core import Stimulus

from .adapters import channel_id
from .playground_assets import manifest, root, verify_source
from .robot_protocol import PlaygroundRobotTask, RobotIntervention, parse_robot
from .world import PhysicalWorld
from .world_ports import WorldPorts
from .world_schema import digest


@lru_cache(maxsize=2)
def environment(implementation, device):
    verify_source()
    import jax
    from mujoco_playground import registry
    from mujoco_playground._src import mjx_env

    # The upstream resolver permits a fixed local Menagerie path. Nothing is
    # patched in its reset, step, dynamics, observation or reward functions.
    mjx_env.MENAGERIE_PATH = root()
    selected = jax.devices("gpu" if device == "cuda" else "cpu")[0]
    config = registry.get_default_config("PandaPickCube")
    config.impl = implementation
    with jax.default_device(selected):
        env = registry.load("PandaPickCube", config=config)
    return env, selected, jax.jit(env.reset, device=selected), jax.jit(env.step, device=selected)


def pack_tree(value, jax, np):
    leaves, _ = jax.tree_util.tree_flatten(value)
    arrays = [np.asarray(v) for v in leaves]
    if sum(v.nbytes for v in arrays) > 64 * 2**20:
        raise ValueError("Playground state exceeds 64 MiB")
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **{f"a{i}": v for i, v in enumerate(arrays)})
    raw = buffer.getvalue()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "npz": base64.b64encode(raw).decode(), "leaves": len(arrays)}


def unpack_tree(value, template, jax, np):
    if len(value["npz"]) > 96 * 2**20:
        raise ValueError("Playground state exceeds encoded budget")
    raw = base64.b64decode(value["npz"], validate=True)
    if hashlib.sha256(raw).hexdigest() != value["sha256"]:
        raise ValueError("Playground state checksum differs")
    originals, structure = jax.tree_util.tree_flatten(template)
    if value["leaves"] != len(originals):
        raise ValueError("Playground state tree differs")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if sum(info.file_size for info in archive.infolist()) > 64 * 2**20:
            raise ValueError("Playground state expands beyond budget")
        if len(archive.namelist()) != len(originals) or set(archive.namelist()) != {
            f"a{i}.npy" for i in range(len(originals))
        }:
            raise ValueError("unexpected Playground state members")
    with np.load(io.BytesIO(raw), allow_pickle=False) as values:
        restored = []
        for i, original in enumerate(originals):
            value = values[f"a{i}"]
            expected = np.asarray(original)
            if value.shape != expected.shape or value.dtype != expected.dtype or value.dtype.hasobject:
                raise ValueError("Playground state array differs from template")
            if getattr(original, "weak_type", False) and value.shape == ():
                restored.append(jax.numpy.asarray(value.item()))
            else:
                restored.append(jax.device_put(value))
    return jax.tree_util.tree_unflatten(structure, restored)


class PlaygroundWorld(WorldPorts):
    def __init__(self, protocol, seed, state=None, *, environment_seed=None):
        import jax
        import jax.numpy as jp
        import mujoco
        import numpy as np
        from mujoco import mjx

        self.task = parse_robot(protocol)
        if not isinstance(self.task, PlaygroundRobotTask):
            raise TypeError("Playground requires an explicit robot-task/2 protocol")
        self.jax, self.jp, self.mjx = jax, jp, mjx
        self.environment_seed = environment_seed if environment_seed is not None else seed
        cfg = self.task.playground
        self.env, self.device, self._reset, self._step = environment(cfg.implementation, cfg.device)
        self.versions = {
            name: importlib.metadata.version(name) for name in ("jax", "jaxlib", "mujoco", "mujoco-mjx", "playground")
        }
        self.protocol_hash = self.task.digest
        self.physical_hash = digest(
            {
                "upstream": manifest()["revision"],
                "assets": manifest()["menagerie_revision"],
                "config": self.env._config.to_dict(),
                "versions": self.versions,
                "device": cfg.device,
            }
        )
        with jax.default_device(self.device):
            self.state = self._reset(jax.random.PRNGKey(self.environment_seed))
            jax.block_until_ready(self.state)
            if state:
                if (
                    state.get("schema") != "threemind.playground-state/1"
                    or state.get("task_hash") != self.protocol_hash
                    or state.get("physical_hash") != self.physical_hash
                ):
                    raise ValueError("Playground task, backend or dependency version differs; no silent continuation")
                if state.get("seed") != seed or state.get("environment_seed") != self.environment_seed:
                    raise ValueError("Playground mapping or environment seed differs")
                self.state = unpack_tree(state["tree"], self.state, jax, np)
        self._names = manifest()["object_names"]
        self.period_us = round(self.env.dt * 1e6)
        if self.period_us != 20000 or round(self.env.sim_dt * 1e6) != 5000:
            raise ValueError("upstream task timing differs from pinned declaration")
        if not state or int(state["steps"]) == 0:
            # Upstream reset does not forward derived poses/mass matrices.
            # Compute only the observer's initial pose on a separate native
            # copy. Never write these derived values into the official state.
            data = mujoco.MjData(self.env.mj_model)
            for field in ("qpos", "qvel", "act", "ctrl", "mocap_pos", "mocap_quat"):
                getattr(data, field)[:] = np.asarray(getattr(self.state.data, field))
            mujoco.mj_forward(self.env.mj_model, data)
        else:
            data = mjx.get_data(self.env.mj_model, self.state.data)
        super().__init__(self.env.mj_model, data, self.task.world, seed)
        self.elapsed_us = int(state["elapsed_us"]) if state else 0
        self.last_delivery_us = state["last_delivery_us"] if state else None
        self.steps = int(state["steps"]) if state else 0
        self.terminated = bool(state["terminated"]) if state else False
        self.external_action = copy.deepcopy(state.get("external_action")) if state else None
        self.external_force = copy.deepcopy(state.get("external_force")) if state else None
        self.initial_distance = float(state["initial_distance"]) if state else self._distance()
        self.best_distance = float(state["best_distance"]) if state else self.initial_distance
        self.last_measurements = copy.deepcopy(state["measurements"]) if state else []
        self.last_controls = copy.deepcopy(state["controls"]) if state else []
        self.total_reward = float(state["total_reward"]) if state else 0.0

    def name(self, kind, identity):
        return self._names[kind + identity]

    def _distance(self):
        # The upstream reset leaves derived xpos unforwarded. qpos contains
        # the actual initial free-joint position without changing task state.
        position = (
            self.data.qpos[self.env._obj_qposadr : self.env._obj_qposadr + 3]
            if self.steps == 0
            else self.data.xpos[self.env._obj_body]
        )
        return float(self.np.linalg.norm(position - self.np.asarray(self.state.info["target_pos"])))

    def _action(self, graph):
        active = sorted((int(i), float(a)) for i, a in (graph or ()))
        if any(not math.isfinite(a) or a < 0 for _, a in active):
            raise ValueError("actuator input requires finite nonnegative activation")
        gain = self.task.playground.projection_gain
        return [
            math.tanh(
                gain
                * math.fsum(
                    a * (1 if channel_id(self.seed, f"playground-output/1:{i}", n) & 1 else -1) for n, a in active
                )
            )
            for i in range(self.model.nu)
        ]

    def intervene(self, now, payload):
        command = RobotIntervention.model_validate_json(json.dumps(payload))
        effective = max(now, self.last_delivery_us or now)
        if command.action in ("force", "actuators") and command.duration_us % self.period_us:
            raise ValueError("intervention duration must contain whole official action periods")
        if command.action == "actuators":
            if len(command.commands) != self.model.nu:
                raise ValueError("official task requires one normalized command per action dimension")
            self.external_action = {"commands": command.commands, "end_us": self.elapsed_us + command.duration_us}
        elif command.action == "force":
            self.name("b_", command.body_id)
            self.external_force = {
                "body_id": command.body_id,
                "values": [*command.force, *command.torque],
                "end_us": self.elapsed_us + command.duration_us,
            }
        elif command.action == "release":
            self.external_force = self.external_action = None
        else:
            raise ValueError("reset_world is handled by the runtime, preserving Core")
        return {
            "effective_time_us": str(effective),
            "intervention": command.model_dump(mode="json"),
            "upstream_task_intervened": command.action != "release",
        }

    def _physical_senses(self):
        channels = list(super()._senses())
        measurements = self.last_measurements
        for index, raw in enumerate(self.data.sensordata):
            value = abs(math.tanh(float(raw)))
            channel = ((4092 << 20) | index) ^ self.channel_mask
            if value:
                channels.append((channel, value))
            measurements.append(
                {
                    "id": f"contact{index}",
                    "port": 4092,
                    "kind": "contact",
                    "values": [float(raw)],
                    "unit": "found",
                    "encoded": [{"channel": channel, "value": value}],
                }
            )
        if self.task.beacon_enabled:
            location = self.data.site_xpos[self.env._gripper_site]
            rotation = self.data.site_xmat[self.env._gripper_site].reshape(3, 3)
            for port, target in (
                (4093, self.data.xpos[self.env._obj_body]),
                (4094, self.np.asarray(self.state.info["target_pos"])),
            ):
                vector = rotation.T @ (target - location)
                visible = float(self.np.linalg.norm(vector)) <= self.task.beacon_range
                pairs = (
                    [(2 * i + int(v < 0), abs(math.tanh(float(v)))) for i, v in enumerate(vector)] if visible else []
                )
                pairs.append((6, float(visible)))
                encoded = [
                    {"channel": ((port << 20) | i) ^ self.channel_mask, "value": value} for i, value in pairs if value
                ]
                channels.extend((r["channel"], r["value"]) for r in encoded)
                measurements.append(
                    {
                        "id": f"beacon{port}",
                        "port": port,
                        "kind": "ideal_optical_beacon",
                        "unit": "m",
                        "coordinate_frame": "gripper-local",
                        "values": vector.tolist(),
                        "scale": 1.0,
                        "visible": visible,
                        "occlusion_model": False,
                        "encoded": encoded,
                    }
                )
        self.last_measurements = measurements
        return tuple(sorted(channels))

    def sample(self, time_us, graph=None, *, action=None, action_source="explicit_action"):
        if self.terminated:
            raise ValueError("official episode ended; reset the world explicitly before further sampling")
        if self.last_delivery_us is not None and time_us != self.last_delivery_us:
            raise ValueError("robot samples must be consecutive")
        for field in ("external_action", "external_force"):
            if getattr(self, field) and getattr(self, field)["end_us"] <= self.elapsed_us:
                setattr(self, field, None)
        if self.external_action:
            action, action_source = self.external_action["commands"], "explicit_intervention"
        if action is None:
            action, action_source = self._action(graph), "core_projection"
        if len(action) != self.model.nu or any(not math.isfinite(v) or abs(v) > 1 for v in action):
            raise ValueError("official actions must be finite, normalized and match task dimensions")
        with self.jax.default_device(self.device):
            forces = self.jp.zeros_like(self.state.data.xfrc_applied)
            if self.external_force:
                forces = forces.at[self.name("b_", self.external_force["body_id"])].set(
                    self.jp.asarray(self.external_force["values"])
                )
            self.state = self.state.replace(data=self.state.data.replace(xfrc_applied=forces))
            self.state = self._step(self.state, self.jp.asarray(action, dtype=self.jp.float32))
            self.jax.block_until_ready(self.state)
        self.data = self.mjx.get_data(self.model, self.state.data)
        self.elapsed_us += self.period_us
        self.last_delivery_us = time_us + self.period_us
        self.steps += 1
        self.total_reward += float(self.state.reward)
        self.terminated = bool(self.state.done) or self.steps >= self.env._config.episode_length
        self.best_distance = min(self.best_distance, self._distance())
        self.last_controls = [
            {
                "id": f"motor{i}",
                "port": i,
                "command": float(v),
                "control": float(self.data.ctrl[i]),
                "joint_force": float(self.data.actuator_force[i]),
                "mode": "official_incremental_position",
                "source": action_source,
                "external_controller": True,
                "unit": "upstream normalized action",
            }
            for i, v in enumerate(action)
        ]
        if self.task.playground.observation == "official-state":
            # Explicit privileged-state research option. Reward/info/done are
            # still excluded; the exact upstream observation vector is retained.
            values = self.np.asarray(self.state.obs).reshape(-1)
            channels = tuple(
                sorted(
                    (((4091 << 20) | (2 * i + int(v < 0))) ^ self.channel_mask, abs(math.tanh(float(v))))
                    for i, v in enumerate(values)
                    if v
                )
            )
            self.last_measurements = [
                {
                    "id": "official-state",
                    "port": 4091,
                    "kind": "privileged_upstream_observation",
                    "values": values.tolist(),
                    "scale": 1.0,
                    "unit": "mixed upstream units",
                    "encoded": [{"channel": c, "value": v} for c, v in channels],
                }
            ]
        else:
            channels = self._physical_senses()
        return Stimulus(time_us + self.period_us, channels, self.task.playground.input_intensity)

    def task_metrics(self):
        return {
            "task_distance": self._distance(),
            "task_best_distance": self.best_distance,
            "task_distance_improvement": self.initial_distance - self._distance(),
            "task_success_observed": False,
            "task_success": 0,
            "task_reward": float(self.state.reward),
            "task_reward_total": self.total_reward,
            "task_elapsed_s": self.elapsed_us / 1e6,
            "task_done": self.terminated,
            **{"playground_" + k: float(v) for k, v in self.state.metrics.items()},
        }

    def observation(self, *, include_measurements=True):
        value = PhysicalWorld.observation(self, include_measurements=include_measurements)
        if "stimulus_unit" in value:
            value["stimulus_unit"]["intensity"] = self.task.playground.input_intensity
        value.update(
            robot_task_hash=self.task.digest,
            target=self.np.asarray(self.state.info["target_pos"]).tolist(),
            control_mode="official_incremental_position",
            task_metrics=self.task_metrics(),
            upstream={
                "task": "PandaPickCube",
                "revision": manifest()["revision"],
                "implementation": self.task.playground.implementation,
                "device": self.task.playground.device,
                "observation": self.task.playground.observation,
            },
        )
        return value

    def scene_protocol(self):
        scene = self.spec.model_dump(mode="json")
        scene["observer_focus"] = "robot"
        shapes = {0: "plane", 2: "sphere", 3: "capsule", 4: "ellipsoid", 5: "cylinder", 6: "box", 7: "mesh"}
        for geom in scene["geometries"]:
            index = self.name("g_", geom["id"])
            geom.update(
                shape=shapes[int(self.model.geom_type[index])],
                size=self.model.geom_size[index].tolist(),
                rgba=self.model.geom_rgba[index].tolist(),
                visible=int(self.model.geom_group[index]) != 3,
            )
            if geom["shape"] == "plane":
                geom["size"][:2] = [3.0 if v == 0 else v for v in geom["size"][:2]]
            if geom["shape"] == "mesh":
                mesh = int(self.model.geom_dataid[index])
                va, vn = self.model.mesh_vertadr[mesh], self.model.mesh_vertnum[mesh]
                fa, fn = self.model.mesh_faceadr[mesh], self.model.mesh_facenum[mesh]
                geom["mesh_id"] = str(mesh)
                scene.setdefault("meshes", {})[str(mesh)] = {
                    "vertices": self.model.mesh_vert[va : va + vn].reshape(-1).tolist(),
                    "indices": self.model.mesh_face[fa : fa + fn].reshape(-1).tolist(),
                }
        return scene

    def capture(self):
        return {
            "schema": "threemind.playground-state/1",
            "kind": "robot",
            "task_hash": self.protocol_hash,
            "world_hash": self.protocol_hash,
            "physical_hash": self.physical_hash,
            "mujoco_version": self.mj.__version__,
            "versions": self.versions,
            "seed": self.seed,
            "environment_seed": self.environment_seed,
            "tree": pack_tree(self.state, self.jax, self.np),
            "elapsed_us": str(self.elapsed_us),
            "last_delivery_us": self.last_delivery_us,
            "steps": self.steps,
            "terminated": self.terminated,
            "total_reward": self.total_reward,
            "initial_distance": self.initial_distance,
            "best_distance": self.best_distance,
            "external_action": copy.deepcopy(self.external_action),
            "external_force": copy.deepcopy(self.external_force),
            "observation": self.observation(),
            "controls": copy.deepcopy(self.last_controls),
            "measurements": copy.deepcopy(self.last_measurements),
            "metrics": self.task_metrics(),
            # A Windows API can serve an already recorded scene without JAX.
            "scene_archive": dict(self.scene_archive),
        }

    @cached_property
    def scene_archive(self):
        from .playground_scene import pack_scene

        return pack_scene(self.scene_protocol())

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
