"""Portable, bounded ocean apparatus. All biological choices are external to Core.

A neutral-buoyant, planar slice with periodic boundaries, inertia and linear
viscous drag. It is not a Navier-Stokes solver or a model of Earth's early ocean.
Sensors are local measurements; no target direction or food command enters Core.
"""

from __future__ import annotations

import copy
import hashlib
import math
from dataclasses import asdict, dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from threemind_core import StateImage, Stimulus
from threemind_core.energy import Energy
from threemind_runtime import create_engine
from threemind_runtime.inheritance import birth


class OceanProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_id: str = Field(default="threemind.ocean/1", alias="schema")
    seed: int = Field(default=280001, ge=0, le=2**32 - 1)
    environment_seed: int = Field(default=281001, ge=0, le=2**32 - 1)
    founders: int = Field(default=8, ge=1, le=32)
    population_limit: int = Field(default=24, ge=1, le=64)
    total_birth_limit: int = Field(default=96, ge=0, le=512)
    period_us: int = Field(default=20000, ge=1000, le=100000)
    physics_us: int = Field(default=5000, ge=100, le=20000)
    side_m: float = Field(default=0.3, gt=0, allow_inf_nan=False)
    radius_m: float = Field(default=0.008, gt=0, allow_inf_nan=False)
    viscosity: float = Field(default=0.01, gt=0, allow_inf_nan=False)
    density: float = Field(default=1000.0, gt=0, allow_inf_nan=False)
    flow_m_s: float = Field(default=0.002, ge=0, allow_inf_nan=False)
    mixing_m2_s: float = Field(default=0.000001, ge=0, allow_inf_nan=False)
    thrust_n: float = Field(default=0.00006, ge=0, allow_inf_nan=False)
    torque_nm: float = Field(default=0.000000004, ge=0, allow_inf_nan=False)
    projection_gain: float = Field(default=0.12, ge=0, allow_inf_nan=False)
    nutrient_initial: int = Field(default=160, ge=0, le=512)
    nutrient_capacity: int = Field(default=160, ge=0, le=512)
    nutrient_interval_us: int = Field(default=5000000, ge=1000)
    nutrient_radius_m: float = Field(default=0.001, gt=0, allow_inf_nan=False)
    nutrient_energy: float = Field(default=30.0, gt=0, le=1e9, allow_inf_nan=False)
    initial_energy: float = Field(default=240.0, gt=0, le=1e9, allow_inf_nan=False)
    core_capacity: float = Field(default=960.0, gt=0, le=1e9, allow_inf_nan=False)
    storage_capacity: float = Field(default=960.0, gt=0, le=1e9, allow_inf_nan=False)
    child_energy: float = Field(default=180.0, gt=0, le=1e9, allow_inf_nan=False)
    reproduction_cost: float = Field(default=30.0, ge=0, allow_inf_nan=False)
    parent_retained_food: float = Field(default=180.0, ge=0, allow_inf_nan=False)
    reproduction_age_us: int = Field(default=60000000, ge=0)
    reproduction_interval_us: int = Field(default=1000000, ge=1000)
    reproduction_cooldown_us: int = Field(default=60000000, ge=1000)
    reproduction: bool = True
    mode: str = "core"
    mutation_sigma: float = Field(default=0.0, ge=0, le=0.3, allow_inf_nan=False)
    predation: bool = False
    predation_efficiency: float = Field(default=0.6, gt=0, lt=1, allow_inf_nan=False)
    engulf_dwell_us: int = Field(default=200000, ge=1000)
    core_overrides: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def boundaries(self):
        if self.schema_id != "threemind.ocean/1" or self.mode not in {"core", "passive", "random"}:
            raise ValueError("unsupported ocean or control protocol")
        if self.period_us % self.physics_us or any(
            x % self.period_us for x in (self.nutrient_interval_us, self.reproduction_interval_us, self.engulf_dwell_us)
        ):
            raise ValueError("external intervals must contain complete sampling periods")
        if self.founders > self.population_limit or self.nutrient_initial > self.nutrient_capacity:
            raise ValueError("initial population or food exceeds capacity")
        if max(self.initial_energy, self.child_energy) > self.core_capacity:
            raise ValueError("initial/child energy exceeds Core capacity")
        if self.radius_m * 6 >= self.side_m:
            raise ValueError("body must be small relative to ocean patch")
        if set(self.core_overrides) & {
            "seed",
            "energy_initial_reserve",
            "energy_capacity",
            "energy_simulation_enabled",
            "energy_starvation_damage_enabled",
        }:
            raise ValueError("energy and identity belong to the declared ocean protocol")
        return self


def channel(seed, key):
    return int.from_bytes(hashlib.blake2b(f"ocean-senses/1:{seed}:{key}".encode(), digest_size=4).digest(), "little")


def rotation(angle):
    c, s = math.cos(angle), math.sin(angle)
    return np.array([[c, -s], [s, c]])


def difference(a, b, side):
    return (np.asarray(a) - np.asarray(b) + side / 2) % side - side / 2


def zero_energy_birth(parent):
    """New individual: birth/1 structure, explicitly ZERO free starting energy.

    Parent image is never changed. The external account must pay the first
    supply. This is a declared initial condition, not a new Core update rule.
    """
    value = birth(parent).to_dict()
    value["config"]["energy_initial_reserve"] = 0.0
    initial = (
        create_engine(value["config"], kernel_id="threemind.continuous-memory/2", backend="reference")
        .capture_state()
        .to_dict()
    )
    value["definition"], value["definition_hash"] = initial["definition"], initial["definition_hash"]
    value["energy"] = Energy(initial_total=0.0, reserve=0.0).to_dict()
    image = StateImage.from_dict(value)
    create_engine(state=image, backend="reference")
    return image


@dataclass
class Body:
    id: int
    parent: int | None
    generation: int
    birth_us: int
    radius: float
    thrust: float
    sensor_range: float
    position: list
    velocity: list
    angle: float
    angular_velocity: float = 0.0
    storage: float = 0.0
    last_birth_us: int = 0
    contact: float = 0.0
    path_m: float = 0.0
    mechanical_work_j: float = 0.0
    grains: int = 0
    supplied: float = 0.0
    children: int = 0
    physical: bool = True
    consumed_by: int | None = None
    death_us: int | None = None


class Ocean:
    def __init__(self, protocol, *, state=None, images=None, founder_images=None, backend="native"):
        self.p = OceanProtocol.model_validate(protocol)
        self.backend = backend
        self.time_us = 0
        self.rng = np.random.default_rng(self.p.environment_seed)
        self.mutations = np.random.default_rng(self.p.environment_seed ^ 0xAB001)
        self.bodies, self.engines, self.seeds = {}, {}, {}
        self.food = np.empty((0, 2))
        self.food_ids = []
        self.next_food_id = 0
        self.engulf = {}
        self.projections = {}
        self.totals = {
            "initial_core": 0.0,
            "environment_food": 0.0,
            "food_consumed": 0.0,
            "reproduction_heat": 0.0,
            "storage_overflow": 0.0,
            "predation_heat": 0.0,
            "deferred_births": 0,
            "births": 0,
            "predations": 0,
        }
        self.events = []
        self.next_food_us = self.p.nutrient_interval_us
        if state is not None:
            self.restore(state, images)
        else:
            self._add_food(self.p.nutrient_initial)
            for i in range(self.p.founders):
                self._founder(i, founder_images[i] if founder_images else None)

    def _config(self, seed):
        return self.p.core_overrides | {
            "seed": seed,
            "energy_simulation_enabled": True,
            "energy_starvation_damage_enabled": True,
            "energy_initial_reserve": self.p.initial_energy,
            "energy_capacity": self.p.core_capacity,
        }

    def _founder(self, i, image):
        seed = self.p.seed + i
        if image is None:
            engine = create_engine(self._config(seed), kernel_id="threemind.continuous-memory/2", backend=self.backend)
        else:
            engine = create_engine(state=zero_energy_birth(image), backend=self.backend)
            seed = engine.config.seed
            engine.supply_energy(self.p.initial_energy, time_us=0, source="ocean-founder-endowment/1")
            engine.advance_to(0)
        self.seeds[i] = seed
        self.engines[i] = engine
        self.totals["initial_core"] += self.p.initial_energy
        self.bodies[i] = Body(
            i,
            None,
            0,
            0,
            self.p.radius_m,
            self.p.thrust_n,
            0.025,
            self.rng.uniform(0, self.p.side_m, 2).tolist(),
            [self.p.flow_m_s, 0.0],
            float(self.rng.uniform(-math.pi, math.pi)),
        )

    def _add_food(self, count):
        count = min(count, self.p.nutrient_capacity - len(self.food))
        if count <= 0:
            return
        self.food = np.concatenate([self.food, self.rng.uniform(0, self.p.side_m, (count, 2))])
        self.food_ids += list(range(self.next_food_id, self.next_food_id + count))
        self.next_food_id += count
        self.totals["environment_food"] += count * self.p.nutrient_energy

    def action(self, i):
        if self.p.mode == "passive":
            return [0.0, 0.0, 0.0]
        if self.p.mode == "random":
            # Independent, repeatable sample-and-hold, not a food-seeking controller.
            r = np.random.default_rng(np.random.SeedSequence([self.p.environment_seed, i, self.time_us // 1000000]))
            return r.uniform(-1, 1, 3).tolist()
        values = sorted((int(n), float(a)) for n, a in self.engines[i].activations())
        seed = self.seeds[i]
        for n, _ in values:
            self.projections.setdefault(
                (seed, n), tuple(1 if channel(seed, f"motor:{j}:{n}") & 1 else -1 for j in range(3))
            )
        return [
            math.tanh(self.p.projection_gain * math.fsum(self.projections[seed, n][j] * a for n, a in values))
            for j in range(3)
        ]

    def _move(self, b, action):
        p = self.p
        dt = p.physics_us / 1e6
        mass = p.density * 4 * math.pi * b.radius**3 / 3
        drag = 6 * math.pi * p.viscosity * b.radius
        inertia = 0.4 * mass * b.radius**2
        rotational_drag = 8 * math.pi * p.viscosity * b.radius**3
        torque = action[2] * p.torque_nm
        w0 = b.angular_velocity
        w_target = torque / rotational_drag
        er = math.exp(-rotational_drag / inertia * dt)
        turn = w_target * dt + (w0 - w_target) * (1 - er) * inertia / rotational_drag
        b.angular_velocity = w_target + (w0 - w_target) * er
        force = rotation(b.angle + turn / 2) @ (np.asarray(action[:2]) * b.thrust)
        v0 = np.asarray(b.velocity)
        terminal = np.array([p.flow_m_s, 0.0]) + force / drag
        er = math.exp(-drag / mass * dt)
        delta = terminal * dt + (v0 - terminal) * (1 - er) * mass / drag
        b.velocity = (terminal + (v0 - terminal) * er).tolist()
        b.position = ((np.asarray(b.position) + delta) % p.side_m).tolist()
        b.angle = (b.angle + turn + math.pi) % (2 * math.pi) - math.pi
        b.path_m += float(np.linalg.norm(delta))
        b.mechanical_work_j += max(0.0, float(force @ delta) + torque * turn)

    def senses(self, i):
        b, p = self.bodies[i], self.p
        r = rotation(b.angle)
        values = [1.0]  # Constant local water medium, never a timer or semantic answer.
        for point in ([1, 0], [0, 1], [-1, 0], [0, -1]):
            sensor = np.asarray(b.position) + r @ (np.asarray(point) * b.radius)
            d = np.linalg.norm(difference(self.food, sensor, p.side_m), axis=1)
            # Local concentration only: finite diffusion-length measurement.
            concentration = float(np.exp(-d[d < 3 * b.sensor_range] / b.sensor_range).sum())
            values.append(concentration / 4.0)
        relative = r.T @ (np.asarray(b.velocity) - [p.flow_m_s, 0.0])
        values += [
            *list(relative / 0.03),
            b.angular_velocity / 2,
            math.sin(b.angle),
            math.cos(b.angle),
            b.contact,
            self.engines[i].metrics()["energy"]["reserve"] / p.core_capacity,
            b.storage / p.storage_capacity,
        ]
        channels = []
        for j, value in enumerate(values):
            if value:
                channels.append((channel(self.seeds[i], f"{j}:{int(value < 0)}"), abs(math.tanh(value))))
        return tuple(sorted(channels)), values

    def _ingest(self, active):
        if not active or not len(self.food):
            return
        positions = np.asarray([self.bodies[i].position for i in active])
        distances = np.linalg.norm(difference(self.food[:, None, :], positions[None, :, :], self.p.side_m), axis=2)
        radii = np.asarray([self.bodies[i].radius + self.p.nutrient_radius_m for i in active])
        distances[distances > radii] = np.inf
        removed = []
        for k, row in enumerate(distances):
            best = float(row.min())
            if not math.isfinite(best):
                continue
            # One particle, one recipient. Exact distance ties alternate by particle identity.
            ties = [active[j] for j in np.flatnonzero(row == best)]
            i = min(ties, key=lambda item: (item - self.food_ids[k]) % (max(active) + 1))
            b = self.bodies[i]
            amount = min(self.p.nutrient_energy, max(0.0, self.p.storage_capacity - b.storage))
            b.storage += amount
            b.grains += 1
            b.contact = 1.0
            self.totals["food_consumed"] += self.p.nutrient_energy
            self.totals["storage_overflow"] += self.p.nutrient_energy - amount
            self.events.append(
                {
                    "kind": "nutrient_contact",
                    "time_us": self.time_us,
                    "individual": i,
                    "particle": self.food_ids[k],
                    "energy": amount,
                }
            )
            removed.append(k)
        if removed:
            keep = np.ones(len(self.food), dtype=bool)
            keep[removed] = False
            self.food = self.food[keep]
            self.food_ids = [v for k, v in enumerate(self.food_ids) if keep[k]]

    def _predation(self, active):
        if not self.p.predation:
            return
        enclosed = {}
        for victim in active:
            v = self.bodies[victim]
            candidates = [
                i
                for i in active
                if i != victim
                and self.bodies[i].radius > v.radius
                and np.linalg.norm(difference(self.bodies[i].position, v.position, self.p.side_m)) + v.radius
                <= self.bodies[i].radius
            ]
            if candidates:
                predator = max(candidates, key=lambda i: (self.bodies[i].radius, -i))
                enclosed[victim] = (
                    predator,
                    self.engulf.get(victim, [predator, self.time_us])[1]
                    if self.engulf.get(victim, [predator])[0] == predator
                    else self.time_us,
                )
        self.engulf = enclosed
        for victim, (predator, start) in sorted(enclosed.items()):
            v, b = self.bodies[victim], self.bodies[predator]
            if not v.physical or not b.physical or self.time_us - start < self.p.engulf_dwell_us:
                continue
            eligible = v.storage * self.p.predation_efficiency
            received = min(eligible, max(0.0, self.p.storage_capacity - b.storage))
            b.storage += received
            self.totals["predation_heat"] += v.storage - received
            v.storage = 0.0
            v.physical, v.consumed_by = False, predator
            self.engines[victim].close_inputs()
            self.totals["predations"] += 1
            self.events.append(
                {
                    "kind": "body_engulfed",
                    "time_us": self.time_us,
                    "individual": victim,
                    "predator": predator,
                    "transferred": received,
                    "consciousness_dead": self.engines[victim].life == "dead",
                }
            )

    def _reproduce(self):
        p = self.p
        if not p.reproduction or self.time_us % p.reproduction_interval_us:
            return
        eligible = [
            i
            for i, b in self.bodies.items()
            if b.physical
            and self.engines[i].life == "active"
            and self.time_us - b.birth_us >= p.reproduction_age_us
            and self.time_us - b.last_birth_us >= p.reproduction_cooldown_us
            and b.storage >= p.child_energy + p.reproduction_cost + p.parent_retained_food
        ]
        # Rotating stable priority avoids permanently privileging the smallest ID.
        eligible.sort(key=lambda i: (i - self.time_us // p.reproduction_interval_us) % max(1, len(self.bodies)))
        for parent in eligible:
            if (
                sum(b.physical for b in self.bodies.values()) >= p.population_limit
                or self.totals["births"] >= p.total_birth_limit
            ):
                self.totals["deferred_births"] += 1
                continue
            b = self.bodies[parent]
            image = zero_energy_birth(self.engines[parent].capture_state())
            child = create_engine(state=image, backend=self.backend)
            child.supply_energy(p.child_energy, time_us=0, source="parent-stored-nutrient/1")
            child.advance_to(0)
            identity = len(self.bodies)
            factors = np.exp(self.mutations.normal(0, p.mutation_sigma, 3))
            radius = float(np.clip(b.radius * factors[0], p.radius_m * 0.5, p.radius_m * 2))
            thrust = float(np.clip(b.thrust * factors[1], p.thrust_n * 0.5, p.thrust_n * 2))
            reach = float(np.clip(b.sensor_range * factors[2], 0.0125, 0.05))
            angle = float(self.mutations.uniform(-math.pi, math.pi))
            pos = (
                np.asarray(b.position) + (b.radius + radius) * np.array([math.cos(angle), math.sin(angle)])
            ) % p.side_m
            new_body = Body(
                identity,
                parent,
                b.generation + 1,
                self.time_us,
                radius,
                thrust,
                reach,
                pos.tolist(),
                list(b.velocity),
                b.angle,
                last_birth_us=self.time_us,
            )
            b.storage -= p.child_energy + p.reproduction_cost
            b.last_birth_us = self.time_us
            b.children += 1
            self.totals["reproduction_heat"] += p.reproduction_cost
            self.totals["births"] += 1
            self.engines[identity], self.bodies[identity], self.seeds[identity] = child, new_body, self.seeds[parent]
            self.events.append(
                {
                    "kind": "birth",
                    "time_us": self.time_us,
                    "individual": identity,
                    "parent": parent,
                    "generation": new_body.generation,
                    "child_energy": p.child_energy,
                    "parent_state": self.engines[parent].capture_state().digest,
                    "child_state": child.capture_state().digest,
                    "traits": [radius, thrust, reach],
                }
            )

    def step(self, record=None):
        p = self.p
        active = [i for i, b in self.bodies.items() if b.physical and self.engines[i].life != "dead"]
        actions = {i: self.action(i) for i in active}
        for i in active:
            self.bodies[i].contact = 0.0
        for _ in range(p.period_us // p.physics_us):
            for i in active:
                self._move(self.bodies[i], actions[i])
            if len(self.food):
                dt = p.physics_us / 1e6
                self.food = (
                    self.food
                    + [p.flow_m_s * dt, 0]
                    + self.rng.normal(0, math.sqrt(2 * p.mixing_m2_s * dt), self.food.shape)
                ) % p.side_m
            self.time_us += p.physics_us
            self._ingest(active)
        if self.time_us >= self.next_food_us:
            self._add_food(1)
            self.next_food_us += p.nutrient_interval_us
        self._predation(active)
        inputs = []
        for i, b in list(self.bodies.items()):
            e = self.engines[i]
            if e.life == "dead":
                continue
            when = self.time_us - b.birth_us
            offer = 0.0
            if b.physical:
                reserve = e.metrics()["energy"]["reserve"]
                # Digestion replenishes only spent reserve; excess food remains available to offspring.
                offer = min(b.storage, max(0.0, p.initial_energy - reserve))
                if offer > 0:
                    e.supply_energy(offer, time_us=when, source="nutrient-contact/1")
                    b.storage -= offer
                    b.supplied += offer
                channels, physical = self.senses(i)
                stimulus = Stimulus(when, channels)
                e.inject(stimulus)
                inputs.append(
                    {
                        "individual": i,
                        "stimulus": stimulus.to_dict(),
                        "food": offer,
                        "raw": physical,
                        "action": actions[i],
                    }
                )
            e.advance_to(when)
            if e.life == "dead":
                b.physical = False
                b.death_us = self.time_us
                self.events.append(
                    {
                        "kind": "consciousness_dead",
                        "time_us": self.time_us,
                        "individual": i,
                        "energy": e.metrics()["energy"],
                        "consumed_by": b.consumed_by,
                    }
                )
        self._reproduce()
        events, self.events = self.events, []
        if record:
            record({"time_us": self.time_us, "inputs": inputs, "events": events})
        return events

    def metrics(self):
        members = []
        for i, b in self.bodies.items():
            e = self.engines[i]
            m = e.metrics()
            members.append(
                asdict(b)
                | {"life": e.life, "core_energy": m["energy"], "nodes": m.get("nodes"), "edges": m.get("edges")}
            )
        # Includes archives of dead/engulfed individuals. Energy is never silently recycled.
        remaining = sum(m["core_energy"]["reserve"] + m["storage"] for m in members)
        spent = sum(
            sum(
                m["core_energy"][k]
                for k in (
                    "consumed_direct",
                    "consumed_associative",
                    "consumed_inhibition",
                    "consumed_maintenance",
                    "discarded_total",
                )
            )
            for m in members
        )
        heat = sum(self.totals[k] for k in ("reproduction_heat", "storage_overflow", "predation_heat"))
        balance = (
            self.totals["initial_core"]
            + self.totals["environment_food"]
            - (remaining + spent + heat + len(self.food) * self.p.nutrient_energy)
        )
        return {
            "time_us": self.time_us,
            "members": members,
            "totals": copy.deepcopy(self.totals),
            "nutrient_count": len(self.food),
            "energy_balance_error": balance,
        }

    def capture(self):
        return {
            "schema": "threemind.ocean-state/1",
            "protocol": self.p.model_dump(by_alias=True),
            "time_us": self.time_us,
            "rng": copy.deepcopy(self.rng.bit_generator.state),
            "mutations": copy.deepcopy(self.mutations.bit_generator.state),
            "bodies": [asdict(b) for b in self.bodies.values()],
            "seeds": self.seeds.copy(),
            "food": self.food.tolist(),
            "food_ids": self.food_ids.copy(),
            "next_food_id": self.next_food_id,
            "next_food_us": self.next_food_us,
            "totals": copy.deepcopy(self.totals),
            "engulf": copy.deepcopy(self.engulf),
            "core_hashes": {i: e.capture_state().digest for i, e in self.engines.items()},
        }

    def restore(self, state, images):
        if state.get("schema") != "threemind.ocean-state/1" or state["protocol"] != self.p.model_dump(by_alias=True):
            raise ValueError("ocean protocol changed across continuation")
        if set(map(int, state["core_hashes"])) != set(map(int, images)):
            raise ValueError("missing population image")
        self.time_us = state["time_us"]
        self.rng.bit_generator.state = state["rng"]
        self.mutations.bit_generator.state = state["mutations"]
        self.bodies = {v["id"]: Body(**v) for v in state["bodies"]}
        self.seeds = {int(k): v for k, v in state["seeds"].items()}
        self.food = np.asarray(state["food"], dtype=float).reshape(-1, 2)
        for field in ("food_ids", "next_food_id", "next_food_us", "totals"):
            setattr(self, field, copy.deepcopy(state[field]))
        self.engulf = {int(k): v for k, v in state["engulf"].items()}
        hashes = {int(k): v for k, v in state["core_hashes"].items()}
        for key, image in images.items():
            i = int(key)
            if image.digest != hashes[i]:
                raise ValueError("Core image checksum mismatch")
            self.engines[i] = create_engine(state=image, backend=self.backend)
            if self.engines[i].life != "dead" and self.engines[i].time_us != self.time_us - self.bodies[i].birth_us:
                raise ValueError("ocean and consciousness clocks differ")
        if abs(self.metrics()["energy_balance_error"]) > 1e-5:
            raise ValueError("population energy ledger does not close")
