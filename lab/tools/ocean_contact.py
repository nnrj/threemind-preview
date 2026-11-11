"""Ocean /3: local capsule contact, capture, and environmental measurements.

External experimental apparatus; no changes to Core or frozen Ocean /1 and /2.
Capsules conserve planar area. This is a shallow-water mechanical approximation,
not CFD, soft tissue mechanics, or an evolved organ simulator.
"""
from __future__ import annotations

import copy
import math
from dataclasses import asdict, dataclass

import numpy as np
from pydantic import Field, model_validator

from lab.tools.ocean import Ocean, Stimulus, channel, difference, rotation
from lab.tools.ocean_evolution import EvolutionOcean, EvolutionProtocol, EvolvingBody
from threemind_runtime import create_engine


class ContactProtocol(EvolutionProtocol):
    schema_id: str = Field(default="threemind.ocean/3", alias="schema")
    side_m: float = Field(default=0.8, gt=0)
    predation: bool = True
    founder_variation: float = Field(default=0.15, ge=0, le=0.3)
    elongation: float = Field(default=0.7, ge=0, le=2)
    capture_enabled: bool = True
    capture_dwell_us: int = Field(default=400000, ge=20000)
    shell_time_factor: float = Field(default=4.0, ge=0)
    contact_skin_m: float = Field(default=0.0008, ge=0, le=0.003)
    grip_initial: float = Field(default=0.5, ge=0, le=1)
    grip_break_m: float = Field(default=0.003, gt=0, le=0.01)
    grip_cost_per_s: float = Field(default=0.1, ge=0)
    random_interval_us: int = Field(default=1000000, ge=20000)
    random_amplitude: float = Field(default=1.0, ge=0, le=1)
    flow_variation_m_s: float = Field(default=0.002, ge=0)
    temperature_amplitude_c: float = Field(default=2.0, ge=0, le=5)
    environment_sense_gain: float = Field(default=0.2, ge=0, le=1)

    @model_validator(mode="after")
    def boundaries(self):
        # Delegate all common checks to /2 without changing that frozen validator.
        if self.schema_id != "threemind.ocean/3":
            raise ValueError("ocean /3 required")
        values = {k: v for k, v in self.model_dump(by_alias=True).items()
                  if k == "schema" or k in EvolutionProtocol.model_fields}
        values["schema"] = "threemind.ocean/2"
        EvolutionProtocol.model_validate(values)
        if self.random_interval_us % self.period_us or self.capture_dwell_us % self.period_us:
            raise ValueError("capture and control intervals must contain full samples")
        if self.recombination_probability or self.horizontal_transfer_probability or self.sharing_rate_per_s:
            raise ValueError("fusion and sharing are excluded from this apparatus")
        return self


@dataclass
class ContactBody(EvolvingBody):
    elongation: float = 0.7
    grip: float = 0.5
    collision: float = 0.0
    acceleration_x: float = 0.0
    acceleration_y: float = 0.0
    captured: int = 0


def capsule(b, origin=None):
    """Spine endpoints and cap radius, with area equal to pi*body.radius**2."""
    radius = b.radius / math.sqrt(1 + 4 * b.elongation / math.pi)
    v = np.array([math.cos(b.angle), math.sin(b.angle)]) * b.elongation * radius
    center = np.asarray(b.position if origin is None else origin)
    return center - v, center + v, radius


def point_segment(points, a, b):
    v = b - a
    denominator = float(v @ v)
    t = np.zeros(np.asarray(points).shape[:-1]) if denominator == 0 else np.clip((points - a) @ v / denominator, 0, 1)
    closest = a + np.asarray(t)[..., None] * v
    return np.linalg.norm(points - closest, axis=-1)


def segment_distance(a, b, c, d):
    # In 2D, nonintersecting segment distance occurs at an endpoint.
    u, v, w = b - a, d - c, c - a
    cross = lambda x, y: float(x[0] * y[1] - x[1] * y[0])
    den = cross(u, v)
    if abs(den) > 1e-20 and 0 <= cross(w, v) / den <= 1 and 0 <= cross(w, u) / den <= 1:
        return 0.0
    return min(float(point_segment(p, x, y)) for p, x, y in ((a, c, d), (b, c, d), (c, a, b), (d, a, b)))


def uniform_counter(ids, tick, seed, lane=0):
    """Counter-based environment noise: deletion cannot shift other food paths."""
    with np.errstate(over="ignore"):
        x = np.asarray(ids, dtype=np.uint64) ^ np.uint64(seed) ^ (np.uint64(tick) * np.uint64(0x9E3779B97F4A7C15)) ^ np.uint64(lane * 7919)
        x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        x ^= x >> np.uint64(31)
    return ((x >> np.uint64(11)).astype(float) + 0.5) / 2**53


class ContactOcean(EvolutionOcean):
    protocol_model = ContactProtocol

    def __init__(self, protocol, *, state=None, images=None, founder_images=None, backend="native"):
        self.p = self.protocol_model.model_validate(protocol)
        self.backend, self.time_us = backend, 0
        self.rng = np.random.default_rng(self.p.environment_seed)
        self.mutations = np.random.default_rng(self.p.environment_seed ^ 0xAB003)
        self.bodies, self.engines, self.seeds, self.projections, self.engulf = {}, {}, {}, {}, {}
        self.food = np.empty((0, 2))
        self.food_ids, self.next_food_id = [], 0
        self.next_food_us = self.p.nutrient_interval_us
        self.totals = dict.fromkeys(("initial_core", "initial_body", "environment_food", "food_consumed",
            "reproduction_heat", "storage_overflow", "predation_heat", "body_heat", "sharing_heat", "shell_heat",
            "deferred_births", "births", "predations", "recombinations", "horizontal_transfers", "sharing_contacts",
            "protected_contacts", "nutrient_capacity_blocks", "contact_frames", "capture_starts", "capture_breaks"), 0.0)
        self.events, self.pending_shape, self.contacts = [], {}, {}
        self.last_actions = {}
        if state is not None:
            self.restore(state, images)
        else:
            self._add_food(self.p.nutrient_initial)
            for i in range(self.p.founders):
                self._founder(i, founder_images[i] if founder_images else None)
                b = self.bodies[i]
                v = self.p.founder_variation
                b.radius *= math.exp(float(self.mutations.normal(0, v)))
                b.shell = float(np.clip(b.shell + self.mutations.normal(0, v), 0, 1))
                self.bodies[i] = ContactBody(**asdict(b), elongation=float(np.clip(self.p.elongation + self.mutations.normal(0, v), 0, 2)),
                                           grip=float(np.clip(self.p.grip_initial + self.mutations.normal(0, v), 0, 1)))

    def _add_food(self, count):
        count = min(count, self.p.nutrient_capacity - len(self.food))
        if count <= 0:
            self.totals["nutrient_capacity_blocks"] += 1
            return
        ids = np.arange(self.next_food_id, self.next_food_id + count)
        positions = np.stack([uniform_counter(ids, 0, self.p.environment_seed, k) for k in (1, 2)], axis=1) * self.p.side_m
        self.food = np.concatenate([self.food, positions])
        self.food_ids += ids.tolist()
        self.next_food_id += count
        self.totals["environment_food"] += count * self.p.nutrient_energy

    def environment(self, position):
        pos = np.asarray(position)
        phase = 2 * math.pi * pos / self.p.side_m
        t = self.time_us / 1e6
        flow = np.stack((self.p.flow_m_s + self.p.flow_variation_m_s * np.sin(phase[..., 1] + t / 17),
                         self.p.flow_variation_m_s * np.sin(phase[..., 0] - t / 23)), axis=-1)
        temperature = 20 + self.p.temperature_amplitude_c * np.sin(phase[..., 0] + phase[..., 1] + t / 61)
        return flow, temperature

    def _motion(self, b, action):
        # Retain /2 finite-work motor law; local water flow and viscosity replace constants.
        p, dt = self.p, self.p.physics_us / 1e6
        flow, temperature = self.environment(b.position)
        viscosity = p.viscosity * math.exp(-0.02 * (float(temperature) - 20))
        mass = p.density * 4 * math.pi * b.radius**3 / 3 * (1 + b.shell)
        drag = 6 * math.pi * viscosity * b.radius * (1 + b.shell * .2) * (1 + .1 * b.elongation)
        inertia = .4 * mass * b.radius**2 * (1 + b.elongation)
        rd = 8 * math.pi * viscosity * b.radius**3 * (1 + b.shell * .2) * (1 + b.elongation)
        torque = action[2] * p.torque_nm * b.thrust / p.thrust_n
        w0, wt = b.angular_velocity, torque / rd
        er = math.exp(-rd / inertia * dt)
        turn = wt * dt + (w0 - wt) * (1 - er) * inertia / rd
        force = rotation(b.angle + turn / 2) @ (np.asarray(action[:2]) * b.thrust)
        v0 = np.asarray(b.velocity)
        vt = flow + force / drag
        er = math.exp(-drag / mass * dt)
        delta = vt * dt + (v0 - vt) * (1 - er) * mass / drag
        velocity = vt + (v0 - vt) * er
        work = max(0.0, float(force @ delta) + torque * turn)
        loss = (float(force @ force) / drag + torque**2 / rd) * dt * (1 / p.motor_efficiency - 1)
        return delta, velocity, turn, wt + (w0 - wt) * math.exp(-rd / inertia * dt), work, (work + loss) / p.joules_per_energy

    def action(self, i):
        if self.p.mode == "random":
            r = np.random.default_rng(np.random.SeedSequence([self.p.environment_seed, i, self.time_us // self.p.random_interval_us]))
            return (r.uniform(-1, 1, 3) * self.p.random_amplitude).tolist()
        return super().action(i)

    def _ingest(self, active):
        if not active or not len(self.food):
            return
        distances = []
        for i in active:
            b = self.bodies[i]
            a, c, radius = capsule(b)
            local = np.asarray(b.position) + difference(self.food, b.position, self.p.side_m)
            values = point_segment(local, a, c)
            distances.append(np.where(values <= radius + self.p.nutrient_radius_m, values / radius, np.inf))
        matrix = np.stack(distances, axis=1)
        removed = []
        for k in np.flatnonzero(np.isfinite(matrix.min(axis=1))):
            row = matrix[k]
            ties = [active[j] for j in np.flatnonzero(row == row.min())]
            i = min(ties, key=lambda item: (item - self.food_ids[k]) % (max(active) + 1))
            b = self.bodies[i]
            amount = min(self.p.nutrient_energy, max(0.0, self.p.storage_capacity - b.storage))
            b.storage += amount
            b.grains += 1
            b.contact = 1.0
            self.totals["food_consumed"] += self.p.nutrient_energy
            self.totals["storage_overflow"] += self.p.nutrient_energy - amount
            self.events.append({"kind": "nutrient_contact", "time_us": self.time_us, "individual": i,
                                "particle": self.food_ids[k], "energy": amount})
            removed.append(k)
        if removed:
            keep = np.ones(len(self.food), dtype=bool)
            keep[removed] = False
            self.food = self.food[keep]
            self.food_ids = [v for k, v in enumerate(self.food_ids) if keep[k]]

    def geometry(self, i, j):
        a, b = self.bodies[i], self.bodies[j]
        delta = difference(b.position, a.position, self.p.side_m)
        aa, ab, ar = capsule(a)
        ba, bb, br = capsule(b, np.asarray(a.position) + delta)
        gap = segment_distance(aa, ab, ba, bb) - ar - br
        contained = ar >= br and max(float(point_segment(ba, aa, ab)), float(point_segment(bb, aa, ab))) + br <= ar
        return gap, contained, delta

    def _protected_pair(self, predator, victim, now):
        """Ocean/3's original one-way juvenile protection, preserved by default."""
        prey = self.bodies[victim]
        return prey.parent == predator and now - prey.birth_us < self.p.maturity_us

    def _separate_overlap(self, a, b, gap, normal):
        """Original Ocean/3 collision correction; specialized bodies may override."""
        correction = -gap * .45 * normal
        a.position = ((np.asarray(a.position) - correction) % self.p.side_m).tolist()
        b.position = ((np.asarray(b.position) + correction) % self.p.side_m).tolist()

    def _predation(self, active):
        p, now = self.p, self.time_us
        present = {}
        for i in active:
            self.bodies[i].strain = self.bodies[i].collision = 0.0
        for n, i in enumerate(active):
            a = self.bodies[i]
            if not a.physical:
                continue
            for j in active[n + 1:]:
                b = self.bodies[j]
                if not b.physical:
                    continue
                # Broad phase; bound includes the longest allowed capsule and grip gap.
                delta = difference(b.position, a.position, p.side_m)
                if float(delta @ delta) > (2 * (a.radius + b.radius) + p.grip_break_m)**2:
                    continue
                gap, enclosed_ab, delta = self.geometry(i, j)
                old = self.contacts.get((i, j))
                if gap > (p.grip_break_m if old else p.contact_skin_m):
                    continue
                self.totals["contact_frames"] += 1
                a.collision = b.collision = max(0.0, -gap) / max(1e-8, a.radius + b.radius)
                # Local passive adhesion; movement can pull apart beyond break distance.
                normal = delta / max(float(np.linalg.norm(delta)), 1e-12)
                if float(np.linalg.norm(delta)) < 1e-12:
                    normal = np.array([1.0, 0.0])
                enclosed_ba = self.geometry(j, i)[1]
                if gap < 0 and not (enclosed_ab or enclosed_ba):
                    self._separate_overlap(a, b, gap, normal)
                elif gap > 0 and old:
                    # Adhesive traction is limited, and costs stored energy in both bodies.
                    grip = min(a.grip, b.grip)
                    shift = min(gap / 2, grip * .02 * p.period_us / 1e6)
                    cost = p.grip_cost_per_s * p.period_us / 1e6 + shift * min(a.thrust, b.thrust) / p.joules_per_energy
                    fraction = min(1.0, a.storage / max(cost, 1e-12), b.storage / max(cost, 1e-12))
                    a.storage -= cost * fraction
                    b.storage -= cost * fraction
                    self.totals["body_heat"] += 2 * cost * fraction
                    a.position = ((np.asarray(a.position) + normal * shift * fraction) % p.side_m).tolist()
                    b.position = ((np.asarray(b.position) - normal * shift * fraction) % p.side_m).tolist()
                if not p.predation:
                    continue
                # Holding ability is a body property; no neural node is assigned a hunting role.
                strength_a = a.thrust * (.25 + a.grip) * a.radius**2
                strength_b = b.thrust * (.25 + b.grip) * b.radius**2
                predator, victim = (i, j) if strength_a >= strength_b else (j, i)
                if enclosed_ab:
                    predator, victim = i, j
                elif enclosed_ba:
                    predator, victim = j, i
                elif not p.capture_enabled:
                    continue
                hunter, prey = self.bodies[predator], self.bodies[victim]
                if self._protected_pair(predator, victim, now):
                    self.totals["protected_contacts"] += 1
                    continue
                is_enclosed = enclosed_ab or enclosed_ba
                start = old[2] if old and old[0] == predator and old[1] == victim else now
                present[i, j] = [predator, victim, start]
                hunter.strain = prey.strain = 1 / (1 + prey.shell)
                if old is None:
                    self.totals["capture_starts"] += 1
                    self.events.append({"kind": "capture_started", "time_us": now, "predator": predator, "individual": victim,
                                        "method": "enclosure" if is_enclosed else "contact"})
                dwell = (p.engulf_dwell_us if is_enclosed else p.capture_dwell_us) * (1 + p.shell_time_factor * prey.shell)
                barrier = p.shell_barrier_energy * prey.shell * (prey.radius / p.radius_m)**2
                if now - start < dwell or hunter.storage < barrier or not (hunter.physical and prey.physical):
                    continue
                hunter.storage -= barrier
                self.totals["shell_heat"] += barrier
                transfer = self._consume_body_energy(hunter, prey)
                prey.physical, prey.consumed_by, prey.body_failure = False, predator, "captured"
                self.engines[victim].close_inputs()
                hunter.captured += 1
                self.totals["predations"] += 1
                self.events.append({"kind": "body_engulfed", "method": "enclosure" if is_enclosed else "contact", "time_us": now,
                                    "individual": victim, "predator": predator, **transfer, "shell_cost": barrier,
                                    "shell": prey.shell, "contact_us": now - start, "required_us": dwell})
        for pair, old in self.contacts.items():
            if pair not in present:
                self.totals["capture_breaks"] += 1
                self.events.append({"kind": "capture_released", "time_us": now, "predator": old[0], "individual": old[1], "contact_us": now-old[2]})
        self.contacts = {k: v for k, v in present.items() if all(self.bodies[i].physical for i in k)}

    def _consume_body_energy(self, hunter, prey):
        """Original reserve-only transfer; newer apparatus may retain paid material."""
        p = self.p
        received = min(prey.storage * p.predation_efficiency, max(0.0, p.storage_capacity - hunter.storage))
        hunter.storage += received
        self.totals["predation_heat"] += prey.storage - received
        prey.storage = 0.0
        return {"transferred": received}

    def senses(self, i):
        _, raw = super().senses(i)
        b, p = self.bodies[i], self.p
        flow, temperature = self.environment(b.position)
        relative = rotation(b.angle).T @ (np.asarray(b.velocity) - flow)
        raw[5:7] = list(relative / .03)
        # Horizontal constrained layer: its constraint bears excess shell weight.
        # These are separate forces, not an invented vertical acceleration.
        displaced_mass = p.density * 4 * math.pi * b.radius**3 / 3
        mass = displaced_mass * (1 + b.shell)
        extra = [*list(rotation(b.angle).T @ flow / .01), (float(temperature) - 20) / 5,
                 b.acceleration_x / .1, b.acceleration_y / .1, b.collision,
                 mass * 9.81 / .05, displaced_mass * 9.81 / .05]
        encoded = [(channel(self.seeds[i], f"v2:{j}:{int(v < 0)}"), abs(math.tanh(v))) for j, v in enumerate(raw) if v]
        encoded += [(channel(self.seeds[i], f"v3:physical:{j}:{int(v < 0)}"), p.environment_sense_gain * abs(math.tanh(v)))
                    for j, v in enumerate(extra) if v and p.environment_sense_gain]
        return tuple(sorted(encoded)), raw + extra

    def _child_traits(self, b):
        traits, donor, recombined = super()._child_traits(b)
        def mutate(value, maximum):
            if self.p.mutation_sigma and self.mutations.random() < self.p.mutation_probability:
                value = (value + self.mutations.normal(0, self.p.mutation_sigma)) % (2 * maximum)
                value = value if value <= maximum else 2 * maximum - value
            return float(value)
        self.pending_shape[b.id] = [mutate(b.elongation, 2), mutate(b.grip, 1)]
        return traits, donor, recombined

    def _reproduce(self):
        old = set(self.bodies)
        super()._reproduce()
        for i in self.bodies.keys() - old:
            body = self.bodies[i]
            shape, grip = self.pending_shape.pop(body.parent)
            self.bodies[i] = ContactBody(**asdict(body), elongation=shape, grip=grip)
            for event in reversed(self.events):
                if event["kind"] == "birth" and event["individual"] == i:
                    event["traits"].update(elongation=shape, grip=grip)
                    break

    def _advance_body_input(self, i, b, actions, initial_v):
        """External apparatus hook; the default retains the original input/energy order."""
        p, e = self.p, self.engines[i]
        when, offer, item = self.time_us - b.birth_us, 0.0, None
        if b.physical:
            acceleration = rotation(b.angle).T @ ((np.asarray(b.velocity) - initial_v[i]) / (p.period_us / 1e6))
            b.acceleration_x, b.acceleration_y = map(float, acceleration)
            offer = min(b.storage, max(0.0, p.initial_energy - e.metrics()["energy"]["reserve"]))
            if offer > 0:
                e.supply_energy(offer, time_us=when, source="nutrient-contact/3")
                b.storage -= offer
                b.supplied += offer
            channels, physical = self.senses(i)
            stimulus = Stimulus(when, channels)
            e.inject(stimulus)
            item = {"individual": i, "stimulus": stimulus.to_dict(), "food": offer, "raw": physical, "action": actions[i]}
        e.advance_to(when)
        if e.life == "dead":
            b.physical, b.death_us = False, self.time_us
            self.events.append({"kind": "consciousness_dead", "time_us": self.time_us, "individual": i,
                                "energy": e.metrics()["energy"], "consumed_by": b.consumed_by})
        return item

    def step(self, record=None):
        p = self.p
        # Preserve the explicitly requested age-control option; formal E30 uses None.
        if p.maximum_age_us is not None:
            for i, b in self.bodies.items():
                if b.physical and self.time_us - b.birth_us >= p.maximum_age_us:
                    b.physical, b.body_failure = False, 'configured_age_limit'
                    self.engines[i].close_inputs()
                    self.events.append({'kind':'body_age_limit','time_us':self.time_us,'individual':i})
        active = [i for i, b in self.bodies.items() if b.physical and self.engines[i].life != "dead"]
        actions = {i: self.action(i) for i in active}
        self.last_actions = actions
        initial_v = {i: np.asarray(self.bodies[i].velocity) for i in active}
        for i in active:
            self.bodies[i].contact = 0.0
        for _ in range(p.period_us // p.physics_us):
            for i in active:
                self._move(self.bodies[i], actions[i])
            if len(self.food):
                dt = p.physics_us / 1e6
                flow, _ = self.environment(self.food)
                tick = self.time_us // p.physics_us + 1
                u = uniform_counter(self.food_ids, tick, p.environment_seed, 3)
                v = uniform_counter(self.food_ids, tick, p.environment_seed, 4)
                z = np.sqrt(-2 * np.log(u))[:, None] * np.stack((np.cos(2 * math.pi * v), np.sin(2 * math.pi * v)), axis=1)
                self.food = (self.food + flow * dt + z * math.sqrt(2 * p.mixing_m2_s * dt)) % p.side_m
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
            item = self._advance_body_input(i, b, actions, initial_v)
            if item is not None:
                inputs.append(item)
        self._reproduce()
        events, self.events = self.events, []
        if record:
            record({"time_us": self.time_us, "inputs": inputs, "events": events})
        return events

    def capture(self):
        state = super().capture()
        state.update(schema="threemind.ocean-state/3", contacts=[list(k) + v for k, v in self.contacts.items()], pending_shape=self.pending_shape)
        return copy.deepcopy(state)

    def restore(self, state, images):
        if state.get("schema") != "threemind.ocean-state/3" or state["protocol"] != self.p.model_dump(by_alias=True):
            raise ValueError("ocean /3 state and protocol must match")
        self.time_us = state["time_us"]
        self.rng.bit_generator.state = state["rng"]
        self.mutations.bit_generator.state = state["mutations"]
        self.bodies = {v["id"]: ContactBody(**v) for v in state["bodies"]}
        self.seeds = {int(k): v for k, v in state["seeds"].items()}
        self.food = np.asarray(state["food"], dtype=float).reshape(-1, 2)
        for k in ("food_ids", "next_food_id", "next_food_us", "totals"):
            setattr(self, k, copy.deepcopy(state[k]))
        self.pending_shape = {int(k): v for k, v in state["pending_shape"].items()}
        self.contacts = {(v[0], v[1]): v[2:] for v in state["contacts"]}
        self.engines = {int(k): create_engine(state=v, backend=self.backend) for k, v in images.items()}
        if set(self.engines) != set(self.bodies):
            raise ValueError("missing population states")
