"""One physics clock for a population; local ports retain their inherited wiring.

This adapter owns bodies and physical measurements, not reproduction or brains.
Inactive slots have no collisions or visible geometry. Slot allocation and body
removal are explicit simulator rules, not claims about biological corpses.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import re
import xml.etree.ElementTree as ET

from threemind_core import Stimulus

from .world import compile_xml, numbers
from .world_ports import WorldPorts
from .world_schema import CameraSensor, Model, Positive, Vec3, digest, parse_world


class SpawnLayout(Model):
    origin: Vec3 = (0.0, 0.0, 0.0)
    spacing: Positive = 0.45


def body_scope(world, root_id):
    roots = {b.id for b in world.bodies if b.parent_id is None}
    if root_id not in roots:
        raise ValueError("population body must select an existing root and all of its descendants")
    selected = {root_id}
    while True:
        expanded = selected | {b.id for b in world.bodies if b.parent_id in selected}
        if expanded == selected:
            break
        selected = expanded
    joints = {j.id for j in world.joints if j.body_id in selected}
    geoms = {g.id for g in world.geometries if g.body_id in selected}
    if any(m.joint_id not in joints for m in world.motors) or any(
        getattr(s, "body_id", root_id) not in selected
        or (getattr(s, "joint_id", None) is not None and s.joint_id not in joints)
        or (getattr(s, "geometry_id", None) is not None and s.geometry_id not in geoms)
        for s in world.sensors
    ):
        raise ValueError("every configured sensory/actuator port must belong to the selected population body")
    local = world.model_dump(mode="json")
    for group in ("bodies", "geometries", "joints", "forces"):
        local[group] = [row for row in local[group] if (row["id"] if group == "bodies" else row["body_id"]) in selected]
    return selected, parse_world(local)


def placement(slot, capacity, layout):
    columns = math.ceil(math.sqrt(capacity))
    center = (columns - 1) / 2
    points = sorted(
        ((x - center, y - center) for y in range(columns) for x in range(columns)),
        key=lambda point: (point[0] ** 2 + point[1] ** 2, point[1], point[0]),
    )
    x, y = points[slot]
    return (layout.origin[0] + x * layout.spacing, layout.origin[1] + y * layout.spacing, layout.origin[2])


def population_xml(world, root_id, capacity, layout):
    selected, local = body_scope(world, root_id)
    totals = {
        group: len(getattr(world, group)) + (capacity - 1) * len(getattr(local, group))
        for group in ("bodies", "geometries", "joints")
    }
    if totals["bodies"] > 8192 or totals["geometries"] > 32768 or totals["joints"] > 16384:
        raise ValueError("population exceeds the declared aggregate physical object budget")
    if capacity * sum(s.width * s.height * 3 for s in local.sensors if isinstance(s, CameraSensor)) > 16777216:
        raise ValueError("population RGB exceeds the declared 16777216 scalar values per sample budget")
    tree = ET.fromstring(compile_xml(world))
    worldbody = tree.find("worldbody")
    body = next(b for b in worldbody.findall("body") if b.attrib["name"] == "b_" + root_id)
    worldbody.remove(body)
    actuators, sensors = tree.find("actuator"), tree.find("sensor")
    templates = list(actuators), list(sensors)
    actuators.clear()
    sensors.clear()

    def clone(element, prefix):
        result = copy.deepcopy(element)
        for node in result.iter():
            for attr in ("name", "joint", "site", "body", "geom", "camera"):
                if attr in node.attrib:
                    node.attrib[attr] = prefix + node.attrib[attr]
        return result

    for slot in range(capacity):
        prefix = f"p{slot}_"
        replica = clone(body, prefix)
        origin = [float(v) for v in body.attrib["pos"].split()]
        replica.attrib["pos"] = numbers(a + b for a, b in zip(origin, placement(slot, capacity, layout), strict=True))
        worldbody.append(replica)
        actuators.extend(clone(m, prefix) for m in templates[0])
        sensors.extend(clone(s, prefix) for s in templates[1])
    return ET.tostring(tree, encoding="unicode"), selected, local


class SharedHabitat:
    def __init__(self, world, root_id, capacity, seed, environment_seed, layout, *, start_us=0, state=None):
        import mujoco
        import numpy as np

        self.world = parse_world(world.model_dump(mode="json") if hasattr(world, "model_dump") else world)
        if type(capacity) is not int or not 1 <= capacity <= 256:
            raise ValueError("invalid physical population capacity")
        if any(type(v) is not int or not 0 <= v < 2**32 for v in (seed, environment_seed)):
            raise ValueError("invalid physical population seed")
        if type(start_us) is not int or start_us < 0:
            raise ValueError("invalid habitat birth clock")
        self.layout = SpawnLayout.model_validate_json(
            layout.model_dump_json() if isinstance(layout, SpawnLayout) else json.dumps(layout)
        )
        self.seed, self.environment_seed, self.capacity, self.root_id = seed, environment_seed, capacity, root_id
        self.period_us = self.world.physics.sample_us
        self.start_us = self.time_us = start_us
        self.mj, self.np = mujoco, np
        self.xml, self.selected, self.local = population_xml(self.world, root_id, capacity, self.layout)
        self.model = mujoco.MjModel.from_xml_string(self.xml)
        self.data = mujoco.MjData(self.model)
        self.state_mask = int(mujoco.mjtState.mjSTATE_INTEGRATION)
        self.state_size = mujoco.mj_stateSize(self.model, self.state_mask)
        self.slots, self.ports = {}, {}
        self.contact_impulses, self.contact_peaks = {}, {}
        self.joint_names = ["j_" + j.id for j in self.local.joints] + ["f_" + b.id for b in self.local.bodies if b.free]
        self.geom_ids = {
            slot: [int(self.model.geom(f"p{slot}_g_" + g.id).id) for g in self.local.geometries]
            for slot in range(capacity)
        }
        self.original_geom = {
            slot: [
                (
                    g,
                    self.model.geom_contype[g].copy(),
                    self.model.geom_conaffinity[g].copy(),
                    self.model.geom_rgba[g].copy(),
                )
                for g in ids
            ]
            for slot, ids in self.geom_ids.items()
        }
        for joint in self.world.joints:
            if joint.body_id not in self.selected:
                rng = random.Random(f"world-initial-v1:{environment_seed}:{joint.id}")
                self.data.joint("j_" + joint.id).qpos[0] = joint.initial + rng.uniform(
                    -joint.initial_jitter, joint.initial_jitter
                )
        self.initial_joint = {
            slot: {name: self.data.joint(f"p{slot}_" + name).qpos.copy() for name in self.joint_names}
            for slot in range(capacity)
        }
        for slot in range(capacity):
            self._visible(slot, False)
        mujoco.mj_forward(self.model, self.data)
        # A fixed initial scene probes the renderer independently of live births
        # and checkpoint poses. It is not a guarantee across GPUs or drivers.
        probe = WorldPorts(self.model, self.data, self.local, seed, prefix="p0_")
        self.render_calibration = probe.render_calibration
        probe.close()
        try:
            if state is not None:
                self._restore(state)
        except BaseException:
            self.close()
            raise

    def _visible(self, slot, enabled):
        for geom, contype, affinity, rgba in self.original_geom[slot]:
            self.model.geom_contype[geom] = contype if enabled else 0
            self.model.geom_conaffinity[geom] = affinity if enabled else 0
            self.model.geom_rgba[geom] = rgba if enabled else [*rgba[:3], 0]

    def _reset_body(self, slot, identity=None):
        prefix = f"p{slot}_"
        for name, initial in self.initial_joint[slot].items():
            joint = self.data.joint(prefix + name)
            joint.qpos[:] = initial
            joint.qvel[:] = 0
            dof = int(self.model.joint(prefix + name).dofadr[0])
            self.data.qacc_warmstart[dof : dof + len(joint.qvel)] = 0
        if identity is not None:
            for joint in self.local.joints:
                rng = random.Random(f"population-initial-v1:{self.environment_seed}:{identity}:{joint.id}")
                self.data.joint(prefix + "j_" + joint.id).qpos[0] = joint.initial + rng.uniform(
                    -joint.initial_jitter, joint.initial_jitter
                )
        for motor in self.local.motors:
            self.data.actuator(prefix + "a_" + motor.id).ctrl[:] = 0

    def activate(self, identity, *, slot=None):
        if not isinstance(identity, str) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}", identity):
            raise ValueError("invalid physical individual identity")
        if identity in self.ports:
            raise ValueError("individual already has a physical body")
        if slot is None:
            slot = next((s for s in range(self.capacity) if s not in self.slots), None)
        if type(slot) is not int or not 0 <= slot < self.capacity or slot in self.slots:
            raise ValueError("no free physical body slot")
        self._reset_body(slot, identity)
        self._visible(slot, True)
        self.mj.mj_forward(self.model, self.data)
        try:
            self.ports[identity] = WorldPorts(self.model, self.data, self.local, self.seed, prefix=f"p{slot}_")
        except BaseException:
            self._visible(slot, False)
            raise
        self.slots[slot] = identity
        self.contact_impulses[identity] = self.contact_peaks[identity] = 0.0

    def remove(self, identity):
        if identity not in self.ports:
            raise ValueError("individual has no physical body")
        slot = next(s for s, value in self.slots.items() if value == identity)
        self.ports.pop(identity).close()
        self.contact_impulses.pop(identity)
        self.contact_peaks.pop(identity)
        del self.slots[slot]
        self._visible(slot, False)
        self._reset_body(slot)
        self.mj.mj_forward(self.model, self.data)

    def integration(self):
        values = self.np.empty(self.state_size, dtype=self.np.float64)
        self.mj.mj_getState(self.model, self.data, values, self.state_mask)
        return values

    def _contract(self):
        return {
            "schema": "threemind.shared-habitat/1",
            "physical_hash": self.world.physical_digest,
            "xml_sha256": hashlib.sha256(self.xml.encode()).hexdigest(),
            "root_id": self.root_id,
            "capacity": self.capacity,
            "seed": self.seed,
            "environment_seed": self.environment_seed,
            "layout": self.layout.model_dump(mode="json"),
            "mujoco_version": self.mj.__version__,
            "render_calibration": dict(self.render_calibration),
            "state_mask": self.state_mask,
            "start_us": self.start_us,
        }

    def _restore(self, state):
        if not isinstance(state, dict) or any(state.get(key) != value for key, value in self._contract().items()):
            raise ValueError("population physics contract changed; exact continuation refused")
        time_us = state.get("time_us")
        if type(time_us) is not int or time_us < self.start_us or (time_us - self.start_us) % self.period_us:
            raise ValueError("invalid population physical clock")
        values = self.np.asarray(state.get("integration"), dtype=self.np.float64)
        if (
            values.shape != (self.state_size,)
            or not self.np.isfinite(values).all()
            or not math.isclose(float(values[0]), (time_us - self.start_us) / 1e6, rel_tol=1e-10, abs_tol=1e-9)
        ):
            raise ValueError("invalid shared physical integration state")
        members = state.get("members")
        if not isinstance(members, list) or len(members) > self.capacity:
            raise ValueError("invalid physical membership")
        for member in members:
            self.activate(member["id"], slot=member["slot"])
            port = self.ports[member["id"]]
            port.last_measurements = copy.deepcopy(member["measurements"])
            port.last_controls = copy.deepcopy(member["controls"])
        for field in ("contact_impulses", "contact_peaks"):
            recorded = state.get(field)
            if (
                not isinstance(recorded, dict)
                or set(recorded) != set(self.ports)
                or any(
                    type(value) not in (int, float) or not math.isfinite(value) or value < 0
                    for value in recorded.values()
                )
            ):
                raise ValueError("incomplete physical contact interval")
            setattr(self, field, copy.deepcopy(recorded))
        self.time_us = time_us
        self.mj.mj_setState(self.model, self.data, values, self.state_mask)
        self.mj.mj_forward(self.model, self.data)
        self.mj.mj_setState(self.model, self.data, values, self.state_mask)

    def step(self, actions):
        if set(actions) != set(self.ports):
            raise ValueError("all active bodies must submit their current actions at the shared boundary")
        normalized = {}
        for identity, graph in actions.items():
            values = graph.get("nodes", []) if isinstance(graph, dict) else graph or ()
            values = [
                (int(v["id"]), float(v["activation"])) if isinstance(v, dict) else (int(v[0]), float(v[1]))
                for v in values
            ]
            if any(not math.isfinite(v) or v < 0 for _, v in values):
                raise ValueError("motor readout requires finite nonnegative activations")
            normalized[identity] = values
        for identity in sorted(self.ports):
            self.ports[identity]._control(normalized[identity])
        self.contact_impulses = dict.fromkeys(self.ports, 0.0)
        self.contact_peaks = dict.fromkeys(self.ports, 0.0)
        owners = {g: identity for slot, identity in self.slots.items() for g in self.geom_ids[slot]}
        contact_force = self.np.empty(6, dtype=self.np.float64)
        self.data.xfrc_applied[:] = 0
        for force in sorted(self.world.forces, key=lambda v: v.id):
            prefixes = [f"p{s}_" for s in sorted(self.slots)] if force.body_id in self.selected else [""]
            for prefix in prefixes:
                self.data.body(prefix + "b_" + force.body_id).xfrc_applied[:] += [*force.force, *force.torque]
        for _ in range(self.period_us // self.world.physics.step_us):
            for slot in range(self.capacity):
                if slot not in self.slots:
                    self._reset_body(slot)
            self.mj.mj_step(self.model, self.data)
            forces = dict.fromkeys(self.ports, 0.0)
            for index in range(self.data.ncon):
                self.mj.mj_contactForce(self.model, self.data, index, contact_force)
                magnitude = float(self.np.linalg.norm(contact_force[:3]))
                for identity in {owners[int(g)] for g in self.data.contact[index].geom if int(g) in owners}:
                    forces[identity] += magnitude
            for identity, magnitude in forces.items():
                self.contact_impulses[identity] += magnitude * self.world.physics.step_us / 1e6
                self.contact_peaks[identity] = max(self.contact_peaks[identity], magnitude)
        for slot in range(self.capacity):
            if slot not in self.slots:
                self._reset_body(slot)
        self.mj.mj_forward(self.model, self.data)
        warnings = [i for i, value in enumerate(self.data.warning) if value.number]
        if warnings or not self.np.isfinite(self.integration()).all():
            raise ValueError(f"population physics warning or nonfinite state: {warnings}")
        self.time_us += self.period_us
        return {identity: Stimulus(self.time_us, port._senses()) for identity, port in sorted(self.ports.items())}

    def measurements(self):
        result = {}
        for identity, port in self.ports.items():
            result[identity] = {
                "position": self.data.body(port.name("b_", self.root_id)).xpos.tolist(),
                "effort": math.fsum(abs(c["control"]) for c in port.last_controls),
                # Interval mean, not a final sample that may miss an earlier impact.
                "contact_force": self.contact_impulses[identity] / (self.period_us / 1e6),
            }
        return result

    def capture(self):
        return self._contract() | {
            "time_us": self.time_us,
            "integration": self.integration().tolist(),
            "contact_impulses": dict(self.contact_impulses),
            "contact_peaks": dict(self.contact_peaks),
            "members": [
                {
                    "id": identity,
                    "slot": slot,
                    "measurements": copy.deepcopy(self.ports[identity].last_measurements),
                    "controls": copy.deepcopy(self.ports[identity].last_controls),
                }
                for slot, identity in sorted(self.slots.items())
            ],
        }

    def observation(self):
        return {
            "schema": "threemind.population-observation/1",
            "time_us": str(self.time_us),
            "physical_elapsed_us": str(self.time_us - self.start_us),
            "members": [
                {"id": identity, "slot": slot, "prefix": f"p{slot}_"} for slot, identity in sorted(self.slots.items())
            ],
            "geometries": [
                {
                    "name": self.model.geom(i).name,
                    "position": self.data.geom(i).xpos.tolist(),
                    "rotation_matrix": self.data.geom(i).xmat.tolist(),
                    "rgba": self.model.geom_rgba[i].tolist(),
                }
                for i in range(self.model.ngeom)
                if self.model.geom_rgba[i][3] > 0
            ],
            "body_measurements": self.measurements(),
        }

    def close(self):
        for port in self.ports.values():
            port.close()
        self.ports.clear()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class PopulationWorld:
    def __init__(self, world, root_id, capacity, seed, environment_seed, *, habitat="shared", layout=None, state=None):
        if habitat not in {"shared", "independent"}:
            raise ValueError("unknown habitat policy")
        world = parse_world(world.model_dump(mode="json") if hasattr(world, "model_dump") else world)
        body_scope(world, root_id)
        if type(capacity) is not int or not 1 <= capacity <= 256:
            raise ValueError("invalid physical population capacity")
        if any(type(v) is not int or not 0 <= v < 2**32 for v in (seed, environment_seed)):
            raise ValueError("invalid physical population seed")
        layout = layout or SpawnLayout()
        layout = SpawnLayout.model_validate_json(
            layout.model_dump_json() if isinstance(layout, SpawnLayout) else json.dumps(layout)
        )
        self.args = (world, root_id, capacity, seed, environment_seed, layout)
        self._period_us = world.physics.sample_us
        self.contract = {
            "schema": "threemind.population-world/1",
            "habitat": habitat,
            "physical_hash": world.physical_digest,
            "root_id": root_id,
            "capacity": capacity,
            "seed": seed,
            "environment_seed": environment_seed,
            "layout": layout.model_dump(mode="json"),
        }
        self.kind, self.time_us, self.habitats = habitat, 0, {}
        try:
            if state is not None:
                if any(state.get(key) != value for key, value in self.contract.items()):
                    raise ValueError("incompatible physical population state")
                if type(state.get("time_us")) is not int or state["time_us"] < 0 or state["time_us"] % self.period_us:
                    raise ValueError("invalid population time")
                self.time_us = state["time_us"]
            if habitat == "shared":
                self.habitats["shared"] = SharedHabitat(*self.args, state=state["worlds"]["shared"] if state else None)
                if state and set(state["worlds"]) != {"shared"}:
                    raise ValueError("unexpected shared worlds")
            elif state:
                if len(state["worlds"]) > capacity:
                    raise ValueError("independent habitat capacity exceeded")
                for identity, saved in state["worlds"].items():
                    self.habitats[identity] = self._independent(identity, saved["start_us"], state=saved)
                    if set(self.habitats[identity].ports) != {identity}:
                        raise ValueError("independent habitat membership mismatch")
            if any(h.time_us != self.time_us for h in self.habitats.values()):
                raise ValueError("population checkpoint combines different physical times")
        except BaseException:
            self.close()
            raise

    def _independent(self, identity, start_us, *, state=None):
        world, root, _, seed, environment_seed, layout = self.args
        local_seed = int(digest({"environment_seed": environment_seed, "individual": identity})[:8], 16)
        return SharedHabitat(world, root, 1, seed, local_seed, layout, start_us=start_us, state=state)

    @property
    def members(self):
        return {identity for h in self.habitats.values() for identity in h.ports}

    @property
    def period_us(self):
        return self._period_us

    def activate(self, identity):
        if identity in self.members or len(self.members) >= self.args[2]:
            raise ValueError("duplicate individual or physical population capacity exceeded")
        if self.kind == "shared":
            self.habitats["shared"].activate(identity)
        else:
            instance = self._independent(identity, self.time_us)
            try:
                instance.activate(identity)
            except BaseException:
                instance.close()
                raise
            self.habitats[identity] = instance

    def remove(self, identity):
        if self.kind == "shared":
            self.habitats["shared"].remove(identity)
        else:
            if identity not in self.habitats:
                raise ValueError("individual has no physical body")
            self.habitats.pop(identity).close()

    def step(self, actions):
        if set(actions) != self.members:
            raise ValueError("physical population action set mismatch")
        result = {}
        for key, habitat in sorted(self.habitats.items()):
            result.update(habitat.step(actions if self.kind == "shared" else {key: actions[key]}))
        self.time_us += self.period_us
        return result

    def measurements(self):
        return {key: row for h in self.habitats.values() for key, row in h.measurements().items()}

    def port(self, identity):
        return self.habitats["shared" if self.kind == "shared" else identity].ports[identity]

    def capture(self):
        return copy.deepcopy(self.contract) | {
            "time_us": self.time_us,
            "worlds": {key: value.capture() for key, value in sorted(self.habitats.items())},
        }

    def observation(self):
        return {
            "habitat": self.kind,
            "time_us": str(self.time_us),
            "worlds": {key: value.observation() for key, value in sorted(self.habitats.items())},
        }

    def close(self):
        for habitat in self.habitats.values():
            habitat.close()
        self.habitats.clear()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
