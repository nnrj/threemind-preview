"""External robot task, measurable sensors and explicitly selected controllers."""

from __future__ import annotations

import copy
import json
import math
import random

from threemind_core import Stimulus

from .robot_protocol import parse_robot
from .world import PhysicalWorld


class RobotWorld(PhysicalWorld):
    def name(self, kind, identity):
        return self._asset_names[kind + identity] if self.task.asset_id else kind + identity

    def _compile_model(self):
        if not self.task.asset_id:
            return super()._compile_model()
        from .robot_assets import describe_model, load, profile

        meta = profile(self.task.asset_id)
        if self.task.control.mode not in meta["modes"] and self.task.control.actuator_variant != "ideal-torque":
            raise ValueError(
                "torque is not supported by this hardware profile; explicitly select actuator_variant=ideal-torque for a simulated motor replacement"
            )
        model = load(self.task.asset_id, self.task.asset_sha256)
        expected, self._asset_names = describe_model(model)
        actual = self.spec.physical_document()
        expected.wiring_namespace = "menagerie-" + self.task.asset_id + "-v1"
        reference = expected.physical_document()
        reference["physics"] = actual["physics"]
        # Physical topology belongs to the pinned asset. Editable exposed fields
        # below really affect this adapter; silently ignored edits are rejected.
        for category, editable in (
            ("joints", ("initial", "initial_jitter")),
            ("motors", ("control_limit", "projection_gain")),
            ("sensors", ("scale", "enabled")),
        ):
            if len(actual[category]) != len(reference[category]):
                raise ValueError("asset port topology differs from pinned model")
            for provided, wanted in zip(actual[category], reference[category]):
                if category == "motors" and provided["control_limit"] > wanted["control_limit"]:
                    raise ValueError("requested force exceeds the asset motor limit")
                for key in editable:
                    if key in provided:
                        wanted[key] = provided[key]
        if actual != reference:
            raise ValueError("asset topology edit requires a separately versioned asset package")
        model.opt.timestep = self.spec.physics.step_us / 1e6
        model.opt.gravity[:] = self.spec.physics.gravity
        model.opt.iterations = self.spec.physics.iterations
        model.opt.integrator = getattr(self.mj.mjtIntegrator, "mjINT_" + self.spec.physics.integrator.upper())
        for motor in self.spec.motors:
            index = self.name("a_", motor.id)
            model.actuator_gaintype[index] = self.mj.mjtGain.mjGAIN_FIXED
            model.actuator_biastype[index] = self.mj.mjtBias.mjBIAS_NONE
            model.actuator_dyntype[index] = self.mj.mjtDyn.mjDYN_NONE
            model.actuator_gainprm[index] = 0
            model.actuator_gainprm[index, 0] = 1
            model.actuator_biasprm[index] = 0
            model.actuator_ctrlrange[index] = (-motor.control_limit, motor.control_limit)
            model.actuator_ctrllimited[index] = 1
        # Include every behavior-bearing choice in continuation identity. The
        # vendor model stays untouched on disk; our controller is a named variant.
        return json.dumps(
            {"asset": self.task.asset_sha256, "world": actual, "controller": self.task.control.model_dump()},
            sort_keys=True,
        ), model

    def __init__(self, protocol, seed, state=None, *, environment_seed=None):
        self.task = parse_robot(protocol)
        if state is not None and (
            state.get("schema") != "threemind.robot-state/1" or state.get("task_hash") != self.task.digest
        ):
            raise ValueError("robot task or control mode differs; continuation refused")
        rng = random.Random(f"robot-target-v1:{environment_seed if environment_seed is not None else seed}")
        self.target = [p + rng.uniform(-j, j) for p, j in zip(self.task.target, self.task.target_jitter)]
        self.total_work = 0.0
        self.contact_samples = 0
        self.success_time_us = None
        self.last_action = []
        self.last_action_source = "core_projection"
        self.external_force = None
        self.external_action = None
        super().__init__(self.task.world, seed, state["world"] if state else None, environment_seed=environment_seed)
        self.initial_distance = self._distance()
        self.best_distance = self.initial_distance
        if state is not None:
            for key in (
                "total_work",
                "contact_samples",
                "success_time_us",
                "initial_distance",
                "best_distance",
                "last_action",
                "last_action_source",
                "external_force",
                "external_action",
            ):
                if key not in state:
                    raise ValueError("incomplete robot state")
                setattr(self, key, copy.deepcopy(state[key]))
            if state.get("target") != self.target:
                raise ValueError("robot target does not match seed")

    def intervene(self, now, payload):
        from .robot_protocol import RobotIntervention

        value = RobotIntervention.model_validate_json(json.dumps(payload), strict=True)
        if value.action in ("force", "actuators") and value.duration_us % self.period_us:
            raise ValueError("intervention duration must contain whole robot control periods")
        start = max(now, self.last_delivery_us or now)
        if value.action == "force":
            if value.body_id not in {b.id for b in self.spec.bodies}:
                raise ValueError("unknown physical body")
            self.external_force = {
                "body_id": value.body_id,
                "wrench": [*value.force, *value.torque],
                "until_us": start + value.duration_us,
            }
        elif value.action == "actuators":
            if len(value.commands) != len(self.spec.motors):
                raise ValueError("one command per sorted actuator required")
            self.external_action = {"commands": value.commands, "until_us": start + value.duration_us}
        elif value.action == "release":
            self.external_force = self.external_action = None
        else:
            raise ValueError("world reset belongs to the owning runtime host")
        return {
            "effective_time_us": str(start),
            "until_us": str(start + value.duration_us),
            "clock": "simulation",
            "control_boundary_us": self.period_us,
        }

    def _point(self):
        identity = self.task.object_body if self.task.objective == "push" else self.task.endpoint_body
        return self.data.body(self.name("b_", identity)).xpos

    def _distance(self):
        return float(self.np.linalg.norm(self._point() - self.np.asarray(self.target)))

    def task_metrics(self):
        distance = self._distance()
        return {
            "task_distance": distance,
            "task_best_distance": self.best_distance,
            "task_distance_improvement": self.initial_distance - distance,
            "task_success": int(self.success_time_us is not None),
            "task_success_observed": self.task.objective != "observe",
            "task_elapsed_s": self.elapsed_us / 1e6,
            "task_contact_samples": self.contact_samples,
            "task_mechanical_work_j": self.total_work,
            "task_success_time_s": None if self.success_time_us is None else self.success_time_us / 1e6,
        }

    def _controller(self, commands):
        rows = []
        joints = {j.id: j for j in self.spec.joints}
        for motor, command in zip(sorted(self.spec.motors, key=lambda m: m.id), commands):
            joint = self.data.joint(self.name("j_", motor.joint_id))
            position, velocity = float(joint.qpos[0]), float(joint.qvel[0])
            cfg = self.task.control
            desired = command
            if cfg.mode == "torque":
                raw = command * motor.control_limit
            elif cfg.mode == "velocity":
                desired = command * cfg.maximum_velocity
                raw = cfg.kd * (desired - velocity)
            else:
                limits = joints[motor.joint_id].limits
                if limits == (-100000.0, 100000.0):
                    # Continuous-wheel position control refers to its fixed
                    # initial angle, never the large mechanical guard range.
                    center = joints[motor.joint_id].initial
                    limits = (center - cfg.continuous_position_span, center + cfg.continuous_position_span)
                if cfg.mode == "skill":
                    # Fixed external demonstration, not a learned ThreeMind policy.
                    command *= math.sin(2 * math.pi * float(self.data.time) / (cfg.skill_period_us / 1e6))
                desired = (limits[0] + limits[1]) / 2 + command * (limits[1] - limits[0]) / 2
                raw = cfg.kp * (desired - position) - cfg.kd * velocity
            control = max(-motor.control_limit, min(motor.control_limit, raw))
            self.data.actuator(self.name("a_", motor.id)).ctrl[0] = control
            self.total_work += abs(control * motor.gear * velocity) * self.spec.physics.step_us / 1e6
            rows.append(
                {
                    "id": motor.id,
                    "port": motor.port,
                    "command": command,
                    "desired": desired,
                    "control": control,
                    "joint_force": control * motor.gear,
                    "unit": "N" if joints[motor.joint_id].kind == "slide" else "Nm",
                    "mode": cfg.mode,
                    "source": self.last_action_source,
                    "external_controller": cfg.mode != "torque",
                    "actuator_variant": cfg.actuator_variant,
                }
            )
        self.last_controls = rows

    def sample(self, time_us, graph=None, *, action=None, action_source="explicit_action"):
        if (
            type(time_us) is not int
            or time_us < 0
            or (self.last_delivery_us is not None and time_us != self.last_delivery_us)
        ):
            raise ValueError("robot steps require consecutive sensory boundaries")
        if self.external_action is not None and time_us >= self.external_action["until_us"]:
            self.external_action = None
        if self.external_force is not None and time_us >= self.external_force["until_us"]:
            self.external_force = None
        if action is None and self.external_action is not None:
            action, action_source = self.external_action["commands"], "research_intervention"
        if action is None:
            activations = (
                ((n["id"], n["activation"]) for n in graph.get("nodes", [])) if isinstance(graph, dict) else graph
            )
            self._control(activations)
            commands = [
                float(self.data.actuator(self.name("a_", m.id)).ctrl[0]) / m.control_limit
                for m in sorted(self.spec.motors, key=lambda m: m.id)
            ]
            self.last_action_source = "core_projection"
        else:
            if len(action) != len(self.spec.motors) or any(
                type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1 for v in action
            ):
                raise ValueError("action must contain one finite normalized [-1,1] value per sorted motor")
            commands = list(action)
            self.last_action_source = action_source
        self.last_action = commands
        for _ in range(self.period_us // self.spec.physics.step_us):
            self._controller(commands)
            self.data.xfrc_applied[:] = 0
            for force in self.spec.forces:
                self.data.body(self.name("b_", force.body_id)).xfrc_applied[:] += [*force.force, *force.torque]
            if self.external_force:
                self.data.body(self.name("b_", self.external_force["body_id"])).xfrc_applied[:] += self.external_force[
                    "wrench"
                ]
            self.mj.mj_step(self.model, self.data)
        self.mj.mj_forward(self.model, self.data)
        self._check_physics()
        self.elapsed_us += self.period_us
        self.samples += 1
        self.last_delivery_us = time_us + self.period_us
        channels = list(self._senses())
        self.contact_samples += int(self.data.ncon > 0)
        self.best_distance = min(self.best_distance, self._distance())
        if (
            self.task.objective != "observe"
            and self.success_time_us is None
            and self._distance() <= self.task.success_distance
        ):
            self.success_time_us = self.elapsed_us
        if self.task.beacon_enabled:
            body = self.data.body(self.name("b_", self.task.endpoint_body))
            vector = body.xmat.reshape(3, 3).T @ (self.np.asarray(self.target) - body.xpos)
            visible = float(self.np.linalg.norm(vector)) <= self.task.beacon_range
            values = (
                [(2 * i + int(v < 0), abs(math.tanh(float(v) / self.task.beacon_scale))) for i, v in enumerate(vector)]
                if visible
                else []
            )
            values.append((6, float(visible)))
            encoded = [
                {"channel": ((self.task.beacon_port << 20) | i) ^ self.channel_mask, "value": v} for i, v in values if v
            ]
            channels.extend((e["channel"], e["value"]) for e in encoded)
            self.last_measurements.append(
                {
                    "id": "target_beacon",
                    "port": self.task.beacon_port,
                    "kind": "ideal-optical-beacon/1",
                    "values": vector.tolist() if visible else [],
                    "visible": visible,
                    "unit": "m",
                    "coordinate_frame": "endpoint-local",
                    "scale": self.task.beacon_scale,
                    "encoded": encoded,
                }
            )
        return Stimulus(self.last_delivery_us, tuple(sorted(channels)))

    def observation(self, *, include_measurements=True):
        # May be called during base construction, before metrics are initialized.
        result = super().observation(include_measurements=include_measurements)
        result.update(
            robot_task_hash=self.task.digest,
            target=list(self.target),
            control_mode=self.task.control.mode,
            task_metrics=self.task_metrics() if hasattr(self, "best_distance") else None,
        )
        result["geometries"].append(
            {"id": "task_target", "position": list(self.target), "rotation_matrix": [1, 0, 0, 0, 1, 0, 0, 0, 1]}
        )
        return result

    def scene_protocol(self):
        scene = self.spec.model_dump(mode="json")
        scene["observer_focus"] = "robot"
        if self.task.asset_id:
            shapes = {
                int(self.mj.mjtGeom.mjGEOM_PLANE): "plane",
                int(self.mj.mjtGeom.mjGEOM_BOX): "box",
                int(self.mj.mjtGeom.mjGEOM_CAPSULE): "capsule",
                int(self.mj.mjtGeom.mjGEOM_CYLINDER): "cylinder",
                int(self.mj.mjtGeom.mjGEOM_SPHERE): "sphere",
                int(self.mj.mjtGeom.mjGEOM_MESH): "mesh",
                int(self.mj.mjtGeom.mjGEOM_ELLIPSOID): "ellipsoid",
            }
            for geom in scene["geometries"]:
                index = self.name("g_", geom["id"])
                geom.update(
                    shape=shapes[int(self.model.geom_type[index])],
                    size=self.model.geom_size[index].tolist(),
                    rgba=self.model.geom_rgba[index].tolist(),
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
                geom["visible"] = int(self.model.geom_group[index]) != 3
        scene["geometries"].append(
            {
                "id": "task_target",
                "shape": "sphere",
                "size": [self.task.success_distance],
                "position": list(self.target),
                "rgba": [0.9, 0.5, 0.12, 0.4],
                "observer_overlay": True,
                "body_id": None,
            }
        )
        return scene

    def capture(self):
        return {
            "schema": "threemind.robot-state/1",
            "kind": "robot",
            "task_hash": self.task.digest,
            "world_hash": self.protocol_hash,
            "physical_hash": self.physical_hash,
            "mujoco_version": self.mj.__version__,
            "world": super().capture(),
            "target": list(self.target),
            **{
                key: copy.deepcopy(getattr(self, key))
                for key in (
                    "total_work",
                    "contact_samples",
                    "success_time_us",
                    "initial_distance",
                    "best_distance",
                    "last_action",
                    "last_action_source",
                    "external_force",
                    "external_action",
                )
            },
            "observation": self.observation(),
            "controls": copy.deepcopy(self.last_controls),
            "measurements": copy.deepcopy(self.last_measurements),
            "metrics": self.task_metrics(),
        }
