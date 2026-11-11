"""Ocean /2: external bodies, finite work, inherited traits and contact exchange.

The frozen E28 Ocean /1 stays intact. This is an explicitly simplified material
environment, not a fluid/organ-development simulator. No fitness enters Core.
"""

from __future__ import annotations

import copy
import math
from dataclasses import asdict, dataclass

import numpy as np
from pydantic import Field, model_validator

from lab.tools.ocean import Body, Ocean, OceanProtocol, channel, difference, rotation, zero_energy_birth
from threemind_runtime import create_engine


class EvolutionProtocol(OceanProtocol):
    schema_id: str = Field(default="threemind.ocean/2", alias="schema")
    founders: int = Field(default=31, ge=1, le=127)
    population_limit: int = Field(default=37, ge=1, le=127)
    total_birth_limit: int = Field(default=148, ge=0, le=1024)
    side_m: float = Field(default=1.2, gt=0, allow_inf_nan=False)
    nutrient_initial: int = Field(default=180, ge=0, le=4096)
    nutrient_capacity: int = Field(default=1024, ge=0, le=4096)
    nutrient_interval_us: int = Field(default=2000000, ge=1000)
    nutrient_energy: float = Field(default=600.0, gt=0, allow_inf_nan=False)
    initial_energy: float = Field(default=2400.0, gt=0, allow_inf_nan=False)
    core_capacity: float = Field(default=20000.0, gt=0, allow_inf_nan=False)
    storage_capacity: float = Field(default=20000.0, gt=0, allow_inf_nan=False)
    child_energy: float = Field(default=1800.0, gt=0, allow_inf_nan=False)
    parent_retained_food: float = Field(default=1200.0, ge=0, allow_inf_nan=False)
    reproduction_cost: float = Field(default=300.0, ge=0, allow_inf_nan=False)
    initial_body_energy: float = Field(default=1200.0, ge=0, allow_inf_nan=False)
    child_body_energy: float = Field(default=600.0, ge=0, allow_inf_nan=False)
    body_maintenance_per_s: float = Field(default=0.5, ge=0, allow_inf_nan=False)
    construction_energy: float = Field(default=200.0, ge=0, allow_inf_nan=False)
    joules_per_energy: float = Field(default=0.000002, gt=0, allow_inf_nan=False)
    motor_efficiency: float = Field(default=0.4, gt=0, le=1, allow_inf_nan=False)
    shell_initial: float = Field(default=0.2, ge=0, le=1, allow_inf_nan=False)
    reflectance_initial: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
    shell_barrier_energy: float = Field(default=100.0, ge=0, allow_inf_nan=False)
    maturity_us: int = Field(default=60000000, ge=0)
    mutation_probability: float = Field(default=0.35, ge=0, le=1, allow_inf_nan=False)
    mutation_sigma: float = Field(default=0.12, ge=0, le=0.3, allow_inf_nan=False)
    recombination_probability: float = Field(default=0.0, ge=0, le=1, allow_inf_nan=False)
    horizontal_transfer_probability: float = Field(default=0.0, ge=0, le=1, allow_inf_nan=False)
    sharing_rate_per_s: float = Field(default=0.0, ge=0, le=10, allow_inf_nan=False)
    sharing_efficiency: float = Field(default=0.9, gt=0, le=1, allow_inf_nan=False)
    maximum_age_us: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def boundaries(self):
        # Override the /1 identity check, while retaining its physical boundaries.
        if self.schema_id != "threemind.ocean/2" or self.mode not in {"core", "passive", "random"}:
            raise ValueError("unsupported evolution protocol")
        if self.period_us % self.physics_us or any(
            x % self.period_us for x in (self.nutrient_interval_us, self.reproduction_interval_us, self.engulf_dwell_us)
        ):
            raise ValueError("external intervals must contain complete sampling periods")
        if self.founders > self.population_limit or self.nutrient_initial > self.nutrient_capacity:
            raise ValueError("initial population or food exceeds capacity")
        if max(self.initial_energy, self.child_energy) > self.core_capacity:
            raise ValueError("initial/child energy exceeds Core capacity")
        if max(self.initial_body_energy, self.child_body_energy) > self.storage_capacity:
            raise ValueError("body endowment exceeds storage")
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


@dataclass
class EvolvingBody(Body):
    shell: float = 0.2
    reflectance: float = 0.5
    ligand: int = 0
    neutral_allele: int = 0
    genome_donor: int | None = None
    body_maintenance: float = 0.0
    body_unserved: float = 0.0
    motor_energy: float = 0.0
    share_sent: float = 0.0
    share_received: float = 0.0
    strain: float = 0.0
    exhausted_motor_steps: int = 0
    body_failure: str | None = None
    pending_birth: dict | None = None


TRAITS = ("radius", "thrust", "sensor_range", "shell", "reflectance", "ligand", "neutral_allele")


class EvolutionOcean(Ocean):
    def __init__(self, protocol, *, state=None, images=None, founder_images=None, backend="native"):
        self.p = EvolutionProtocol.model_validate(protocol)
        self.backend, self.time_us = backend, 0
        self.rng = np.random.default_rng(self.p.environment_seed)
        self.mutations = np.random.default_rng(self.p.environment_seed ^ 0xAB002)
        self.bodies, self.engines, self.seeds, self.projections, self.engulf = {}, {}, {}, {}, {}
        self.food = np.empty((0, 2))
        self.food_ids, self.next_food_id = [], 0
        self.next_food_us = self.p.nutrient_interval_us
        self.totals = dict.fromkeys(
            (
                "initial_core",
                "initial_body",
                "environment_food",
                "food_consumed",
                "reproduction_heat",
                "storage_overflow",
                "predation_heat",
                "body_heat",
                "sharing_heat",
                "shell_heat",
                "deferred_births",
                "births",
                "predations",
                "recombinations",
                "horizontal_transfers",
                "sharing_contacts",
                "protected_contacts",
                "nutrient_capacity_blocks",
            ),
            0.0,
        )
        self.events = []
        if state is not None:
            self.restore(state, images)
        else:
            self._add_food(self.p.nutrient_initial)
            for i in range(self.p.founders):
                self._founder(i, founder_images[i] if founder_images else None)

    def _founder(self, i, image):
        super()._founder(i, image)
        self.bodies[i] = EvolvingBody(
            **(asdict(self.bodies[i]) | {"storage": self.p.initial_body_energy}),
            shell=self.p.shell_initial,
            reflectance=self.p.reflectance_initial,
        )
        self.totals["initial_body"] += self.p.initial_body_energy

    def _add_food(self, count):
        self.totals["nutrient_capacity_blocks"] += max(0, len(self.food) + count - self.p.nutrient_capacity)
        super()._add_food(count)

    def _motion(self, b, action):
        """Predict one step so unavailable motor energy cannot become free force."""
        p, dt = self.p, self.p.physics_us / 1e6
        mass = p.density * 4 * math.pi * b.radius**3 / 3 * (1 + b.shell)
        drag = 6 * math.pi * p.viscosity * b.radius * (1 + b.shell * 0.2)
        inertia = 0.4 * mass * b.radius**2
        rd = 8 * math.pi * p.viscosity * b.radius**3 * (1 + b.shell * 0.2)
        torque = action[2] * p.torque_nm * (b.thrust / p.thrust_n if p.thrust_n else 0)
        w0, wt = b.angular_velocity, torque / rd
        er = math.exp(-rd / inertia * dt)
        turn = wt * dt + (w0 - wt) * (1 - er) * inertia / rd
        omega = wt + (w0 - wt) * er
        force = rotation(b.angle + turn / 2) @ (np.asarray(action[:2]) * b.thrust)
        v0 = np.asarray(b.velocity)
        vt = np.array([p.flow_m_s, 0.0]) + force / drag
        er = math.exp(-drag / mass * dt)
        delta = vt * dt + (v0 - vt) * (1 - er) * mass / drag
        velocity = vt + (v0 - vt) * er
        work = max(0.0, float(force @ delta) + torque * turn)
        # Positive mechanical work plus resistive actuator loss; no regenerative feeding.
        loss = (float(force @ force) / drag + torque**2 / rd) * dt * (1 / p.motor_efficiency - 1)
        cost = (work + loss) / p.joules_per_energy
        return delta, velocity, turn, omega, work, cost

    def _move(self, b, action):
        p, dt = self.p, self.p.physics_us / 1e6
        volume = (b.radius / p.radius_m) ** 3
        demand = p.body_maintenance_per_s * volume * (1 + b.shell + 0.2 * (1 - b.reflectance)) * dt
        paid = min(b.storage, demand)
        b.storage -= paid
        b.body_maintenance += paid
        b.body_unserved += demand - paid
        self.totals["body_heat"] += paid
        action = np.asarray(action, dtype=float)
        motion = self._motion(b, action)
        if motion[-1] > b.storage:
            b.exhausted_motor_steps += 1
            lo, hi = 0.0, 1.0
            motion = self._motion(b, action * 0)
            if b.storage > 0:
                for _ in range(8):
                    mid = (lo + hi) / 2
                    candidate = self._motion(b, action * mid)
                    if candidate[-1] <= b.storage:
                        lo, motion = mid, candidate
                    else:
                        hi = mid
        delta, velocity, turn, omega, work, cost = motion
        b.storage -= cost
        b.motor_energy += cost
        self.totals["body_heat"] += cost
        b.position = ((np.asarray(b.position) + delta) % p.side_m).tolist()
        b.velocity = velocity.tolist()
        b.angle = (b.angle + turn + math.pi) % (2 * math.pi) - math.pi
        b.angular_velocity = omega
        b.path_m += float(np.linalg.norm(delta))
        b.mechanical_work_j += work

    def senses(self, i):
        _, raw = super().senses(i)
        b, p = self.bodies[i], self.p
        others = [o for j, o in self.bodies.items() if j != i and o.physical]
        positions = np.asarray([o.position for o in others]).reshape(-1, 2)
        reflected = np.asarray([o.reflectance * (o.radius / p.radius_m) ** 2 for o in others])
        # Local reflectance field, not identity, ancestry, food value or a predator label.
        for point in ([1, 0], [0, 1], [-1, 0], [0, -1]):
            sensor = np.asarray(b.position) + rotation(b.angle) @ (np.asarray(point) * b.radius)
            distances = np.linalg.norm(difference(positions, sensor, p.side_m), axis=1)
            inside = distances < 3 * b.sensor_range
            raw.append(float((reflected[inside] * np.exp(-distances[inside] / b.sensor_range)).sum()) / 4)
        raw.append(b.strain)
        encoded = tuple(
            sorted((channel(self.seeds[i], f"v2:{j}:{int(v < 0)}"), abs(math.tanh(v))) for j, v in enumerate(raw) if v)
        )
        return encoded, raw

    def _share(self, active):
        p = self.p
        if not p.sharing_rate_per_s:
            return
        delta = dict.fromkeys(active, 0.0)
        pairs = []
        for k, i in enumerate(active):
            a = self.bodies[i]
            for j in active[k + 1 :]:
                b = self.bodies[j]
                if (
                    a.ligand != b.ligand
                    or np.linalg.norm(difference(a.position, b.position, p.side_m)) > a.radius + b.radius
                ):
                    continue
                donor, receiver = (a, b) if a.storage > b.storage else (b, a)
                request = min(
                    (donor.storage - receiver.storage) / 2,
                    p.sharing_rate_per_s * p.period_us / 1e6 * (donor.storage - receiver.storage),
                )
                if request > 0:
                    pairs.append((donor.id, receiver.id, request))
        outgoing = {i: math.fsum(a for d, _, a in pairs if d == i) for i in active}
        incoming = {i: math.fsum(a * p.sharing_efficiency for _, r, a in pairs if r == i) for i in active}
        for donor, receiver, request in pairs:
            a, b = self.bodies[donor], self.bodies[receiver]
            fraction = min(
                1.0, a.storage / outgoing[donor], max(0.0, p.storage_capacity - b.storage) / incoming[receiver]
            )
            sent = request * fraction
            got = sent * p.sharing_efficiency
            delta[donor] -= sent
            delta[receiver] += got
            a.share_sent += sent
            b.share_received += got
            self.totals["sharing_heat"] += sent - got
            self.totals["sharing_contacts"] += 1
            self.events.append(
                {
                    "kind": "resource_exchange",
                    "time_us": self.time_us,
                    "donor": donor,
                    "receiver": receiver,
                    "sent": sent,
                    "received": got,
                }
            )
        for i, amount in delta.items():
            self.bodies[i].storage += amount

    def _predation(self, active):
        p = self.p
        self._share(active)
        for i in active:
            self.bodies[i].strain = 0.0
        if not p.predation:
            return
        enclosed = {}
        for victim in active:
            v = self.bodies[victim]
            candidates = []
            for i in active:
                b = self.bodies[i]
                if i == victim or b.radius <= v.radius:
                    continue
                if np.linalg.norm(difference(b.position, v.position, p.side_m)) + v.radius > b.radius:
                    continue
                if v.parent == i and self.time_us - v.birth_us < p.maturity_us:
                    self.totals["protected_contacts"] += 1
                    continue
                candidates.append(i)
            if candidates:
                predator = max(candidates, key=lambda i: (self.bodies[i].radius, -i))
                prev = self.engulf.get(victim)
                start = prev[1] if prev and prev[0] == predator else self.time_us
                enclosed[victim] = (predator, start)
                v.strain = (self.bodies[predator].radius / v.radius - 1) / (1 + v.shell)
        self.engulf = enclosed
        for victim, (predator, start) in sorted(enclosed.items()):
            v, b = self.bodies[victim], self.bodies[predator]
            if not v.physical or not b.physical or self.time_us - start < p.engulf_dwell_us * (1 + 4 * v.shell):
                continue
            barrier = p.shell_barrier_energy * v.shell * (v.radius / p.radius_m) ** 2
            if b.storage < barrier:
                continue
            b.storage -= barrier
            self.totals["shell_heat"] += barrier
            received = min(v.storage * p.predation_efficiency, max(0, p.storage_capacity - b.storage))
            b.storage += received
            self.totals["predation_heat"] += v.storage - received
            v.storage = 0.0
            v.physical, v.consumed_by, v.body_failure = False, predator, "engulfed"
            self.engines[victim].close_inputs()
            self.totals["predations"] += 1
            self.events.append(
                {
                    "kind": "body_engulfed",
                    "time_us": self.time_us,
                    "individual": victim,
                    "predator": predator,
                    "transferred": received,
                    "shell_cost": barrier,
                }
            )
            if p.horizontal_transfer_probability and self.mutations.random() < p.horizontal_transfer_probability:
                # Transfer a stored allele for future offspring; never resize a live body for free.
                b.genome_donor = victim
                self.totals["horizontal_transfers"] += 1
                self.events.append(
                    {"kind": "allele_source_retained", "time_us": self.time_us, "individual": predator, "donor": victim}
                )

    def _child_traits(self, b):
        p = self.p
        traits = {k: getattr(b, k) for k in TRAITS}
        donor = b.genome_donor
        recombined = False
        if p.recombination_probability:
            partners = [
                o.id
                for o in self.bodies.values()
                if o.id != b.id
                and o.physical
                and self.time_us - o.birth_us >= p.maturity_us
                and np.linalg.norm(difference(o.position, b.position, p.side_m)) <= o.radius + b.radius
            ]
            if partners and self.mutations.random() < p.recombination_probability:
                donor = int(self.mutations.choice(partners))
                recombined = True
        if donor is not None:
            other = self.bodies[donor]
            for key in TRAITS:
                if self.mutations.random() < 0.5:
                    traits[key] = getattr(other, key)
        if p.mutation_sigma:
            bounds = {
                "radius": (p.radius_m * 0.5, p.radius_m * 2),
                "thrust": (p.thrust_n * 0.5, p.thrust_n * 2),
                "sensor_range": (0.0125, 0.075),
            }
            for key, (lo, hi) in bounds.items():
                if self.mutations.random() < p.mutation_probability:
                    traits[key] = float(
                        np.clip(traits[key] * math.exp(self.mutations.normal(0, p.mutation_sigma)), lo, hi)
                    )
            for key in ("shell", "reflectance"):
                if self.mutations.random() < p.mutation_probability:
                    value = (traits[key] + self.mutations.normal(0, p.mutation_sigma)) % 2
                    traits[key] = float(value if value <= 1 else 2 - value)
            if self.mutations.random() < p.mutation_probability:
                traits["ligand"] = int(self.mutations.integers(0, 4))
            if self.mutations.random() < p.mutation_probability:
                traits["neutral_allele"] = int(self.mutations.integers(0, 2**31))
        return traits, donor, recombined

    def _reproduction_ready(self, i):
        return self.engines[i].life == "active"

    def _reproduce(self):
        p = self.p
        if not p.reproduction or self.time_us % p.reproduction_interval_us:
            return
        # Draw a prospective offspring once, retaining it until it can be funded.
        # Do not demand the maximum possible body cost or reroll unaffordable traits.
        reserve_cost = p.construction_energy * 0.5**3
        eligible = [
            i
            for i, b in self.bodies.items()
            if b.physical
            and self._reproduction_ready(i)
            and self.time_us - b.birth_us >= p.reproduction_age_us
            and self.time_us - b.last_birth_us >= p.reproduction_cooldown_us
            and b.storage
            >= p.child_energy + p.child_body_energy + p.reproduction_cost + reserve_cost + p.parent_retained_food
        ]
        eligible.sort(key=lambda i: (i - self.time_us // p.reproduction_interval_us) % max(1, len(self.bodies)))
        for parent in eligible:
            if (
                sum(b.physical for b in self.bodies.values()) >= p.population_limit
                or self.totals["births"] >= p.total_birth_limit
            ):
                self.totals["deferred_births"] += 1
                continue
            b = self.bodies[parent]
            if b.pending_birth is None:
                traits, donor, recombined = self._child_traits(b)
                b.pending_birth = {"traits": traits, "donor": donor, "recombined": recombined}
            traits = dict(b.pending_birth["traits"])
            donor, recombined = b.pending_birth["donor"], b.pending_birth["recombined"]
            material = p.construction_energy * (traits["radius"] / p.radius_m) ** 3 * (1 + traits["shell"])
            cost = p.reproduction_cost + material
            if b.storage < p.child_energy + p.child_body_energy + cost + p.parent_retained_food:
                continue
            image = zero_energy_birth(self.engines[parent].capture_state())
            child = create_engine(state=image, backend=self.backend)
            child.supply_energy(p.child_energy, time_us=0, source="parent-stored-nutrient/2")
            child.advance_to(0)
            identity = len(self.bodies)
            angle = float(self.mutations.uniform(-math.pi, math.pi))
            position = (
                np.asarray(b.position) + (b.radius + traits["radius"]) * np.array([math.cos(angle), math.sin(angle)])
            ) % p.side_m
            body = EvolvingBody(
                identity,
                parent,
                b.generation + 1,
                self.time_us,
                traits.pop("radius"),
                traits.pop("thrust"),
                traits.pop("sensor_range"),
                position.tolist(),
                list(b.velocity),
                b.angle,
                storage=p.child_body_energy,
                last_birth_us=self.time_us,
                **traits,
            )
            b.storage -= p.child_energy + p.child_body_energy + cost
            b.last_birth_us = self.time_us
            b.children += 1
            b.pending_birth = None
            self.totals["reproduction_heat"] += cost
            self.totals["births"] += 1
            self.totals["recombinations"] += int(recombined)
            self.engines[identity], self.bodies[identity], self.seeds[identity] = child, body, self.seeds[parent]
            self.events.append(
                {
                    "kind": "birth",
                    "time_us": self.time_us,
                    "individual": identity,
                    "parent": parent,
                    "body_donor": donor,
                    "recombined": recombined,
                    "generation": body.generation,
                    "construction_cost": material,
                    "child_energy": p.child_energy + p.child_body_energy,
                    "traits": {k: getattr(body, k) for k in TRAITS},
                    "parent_state": self.engines[parent].capture_state().digest,
                    "child_state": child.capture_state().digest,
                }
            )

    def step(self, record=None):
        if self.p.maximum_age_us is not None:
            for i, b in self.bodies.items():
                if b.physical and self.time_us - b.birth_us >= self.p.maximum_age_us:
                    b.physical, b.body_failure = False, "configured_age_limit"
                    self.engines[i].close_inputs()
                    self.events.append({"kind": "body_age_limit", "time_us": self.time_us, "individual": i})
        return super().step(record)

    def metrics(self):
        m = super().metrics()
        m["energy_balance_error"] += self.totals["initial_body"] - math.fsum(
            self.totals[k] for k in ("body_heat", "sharing_heat", "shell_heat")
        )
        return m

    def capture(self):
        state = super().capture()
        state["schema"] = "threemind.ocean-state/2"
        return state

    def restore(self, state, images):
        if state.get("schema") != "threemind.ocean-state/2" or state["protocol"] != self.p.model_dump(by_alias=True):
            raise ValueError("ocean /2 protocol changed across continuation")
        if set(map(int, state["core_hashes"])) != set(map(int, images)):
            raise ValueError("missing population image")
        self.time_us = state["time_us"]
        self.rng.bit_generator.state = state["rng"]
        self.mutations.bit_generator.state = state["mutations"]
        self.bodies = {v["id"]: EvolvingBody(**v) for v in state["bodies"]}
        self.seeds = {int(k): v for k, v in state["seeds"].items()}
        self.food = np.asarray(state["food"], dtype=float).reshape(-1, 2)
        for k in ("food_ids", "next_food_id", "next_food_us", "totals"):
            setattr(self, k, copy.deepcopy(state[k]))
        self.engulf = {int(k): v for k, v in state["engulf"].items()}
        hashes = {int(k): v for k, v in state["core_hashes"].items()}
        for key, image in images.items():
            i = int(key)
            if image.digest != hashes[i]:
                raise ValueError("Core image checksum mismatch")
            self.engines[i] = create_engine(state=image, backend=self.backend)
            if self.engines[i].life != "dead" and self.engines[i].time_us != self.time_us - self.bodies[i].birth_us:
                raise ValueError("ocean and consciousness clocks differ")
        if abs(self.metrics()["energy_balance_error"]) > 1e-4:
            raise ValueError("population energy ledger does not close")
