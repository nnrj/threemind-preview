"""Paid growth, triplets, live-kin protection and direct parental care in a 6.3 habitat."""

import copy
import math
from collections import defaultdict

import numpy as np
from p2_paths import RULES, SECOND, SEEDS

# isort: split
from apparatus import E38_INPUT, create_engine, newborn_without_endowment, read
from carrion import Carrion63
from habitat import ContactLitter63, extent, volume

from lab.tools.ocean import difference
from lab.tools.ocean_contact import ContactBody, Stimulus, rotation

STATE = "threemind.ocean-juvenile-kin-care-state/1"
NEWBORN_RADIUS = 0.004
CARE_TIME = 30 * SECOND
CARE_RATE = 1.0
GROWTH_SECONDS = 120
BROOD = 3


class JuvenileWorld(Carrion63):
    geometry = ContactLitter63.geometry
    _separate_overlap = ContactLitter63._separate_overlap

    def __init__(self, protocol, *, state=None, images=None, **kwargs):
        self.adult_radii = {}
        self.birth_radii = {}
        self.ancestors = {}
        if state is not None:
            if state.get("schema") != STATE or state["rules"] != RULES:
                raise ValueError("P2 requires its own complete world")
            self.adult_radii = {int(i): r for i, r in state["adult_radii"].items()}
            self.birth_radii = {int(i): r for i, r in state["birth_radii"].items()}
        super().__init__(protocol, state=state["carrion"] if state else None, images=images, **kwargs)
        if self.p.recombination_probability or self.p.horizontal_transfer_probability:
            raise ValueError("P2 uses the registered single-parent population")
        if state is None:
            for i, b in self.bodies.items():
                self.adult_radii[i] = b.radius
                self.birth_radii[i] = b.radius = min(NEWBORN_RADIUS, b.radius)
            self.replace_founder_material(list(self.bodies))
            for b in self.bodies.values():
                reserve = self.neonatal_reserve(b.radius)
                self.totals["initial_body"] += reserve - b.storage
                b.storage = reserve
        if self.bodies.keys() != self.adult_radii.keys() or self.bodies.keys() != self.birth_radii.keys():
            raise ValueError("missing adult or neonatal body size")
        for b in self.bodies.values():
            self.remember_family(b)

    def capture(self):
        return {
            "schema": STATE,
            "rules": RULES,
            "adult_radii": dict(self.adult_radii),
            "birth_radii": dict(self.birth_radii),
            "carrion": super().capture(),
        }

    def neonatal_reserve(self, radius):
        return self.p.nutrient_energy * (radius / self.p.radius_m) ** 3

    def _advance_body_input(self, i, b, actions, initial_v):
        # Keep P1's adult reserve target. Increase the juvenile target only as
        # the body pays for growth, preserving the normal sensor/energy/tick order.
        p, engine = self.p, self.engines[i]
        when = self.time_us - b.birth_us
        item = None
        if b.physical:
            acceleration = rotation(b.angle).T @ ((np.asarray(b.velocity) - initial_v[i]) / (p.period_us / SECOND))
            b.acceleration_x, b.acceleration_y = map(float, acceleration)
            start, target = self.birth_radii[i] ** 3, self.adult_radii[i] ** 3
            fraction = min(1.0, max(0.0, (b.radius**3 - start) / (target - start))) if target > start else 1.0
            reserve_target = p.nutrient_energy * (1 + 3 * fraction)
            offer = min(b.storage, max(0.0, reserve_target - engine.metrics()["energy"]["reserve"]))
            if offer:
                engine.supply_energy(offer, time_us=when, source="nutrient-contact/3")
                b.storage -= offer
                b.supplied += offer
            channels, raw = self.senses(i)
            stimulus = Stimulus(when, channels)
            engine.inject(stimulus)
            item = {"individual": i, "stimulus": stimulus.to_dict(), "food": offer, "raw": raw, "action": actions[i]}
        engine.advance_to(when)
        if engine.life == "dead":
            b.physical, b.death_us = False, self.time_us
            self.events.append(
                {
                    "kind": "consciousness_dead",
                    "time_us": self.time_us,
                    "individual": i,
                    "energy": engine.metrics()["energy"],
                    "consumed_by": b.consumed_by,
                }
            )
        return item

    def remember_family(self, b):
        lineage = {b.id}
        parent = b.parent
        for _ in range(3):
            if parent is None:
                break
            lineage.add(parent)
            parent = self.bodies[parent].parent
        self.ancestors[b.id] = frozenset(lineage)

    def _protected_pair(self, predator, victim, now):
        return not self.ancestors[predator].isdisjoint(self.ancestors[victim])

    def _nurse(self, contacts):
        p = self.p
        dt = p.period_us / SECOND
        for parent_id, ids in contacts.items():
            parent = self.bodies[parent_id]
            if not parent.physical:
                continue
            young = [self.bodies[i] for i in ids if self.bodies[i].physical]
            requested = [min(CARE_RATE * dt, max(0.0, p.storage_capacity - b.storage)) for b in young]
            total = sum(requested)
            initial = parent.storage
            fraction = min(1.0, max(0.0, initial - p.parent_retained_food) / total) if total else 0.0
            for child, need in zip(young, requested):
                amount = fraction * need
                child.storage += amount
                self.events.append(
                    {
                        "kind": "nursing_contact",
                        "time_us": self.time_us,
                        "parent": parent_id,
                        "individual": child.id,
                        "age_us": self.time_us - child.birth_us,
                        "duration_s": dt,
                        "requested": need,
                        "received": amount,
                        "parent_before": initial,
                        "parent_after": initial - total * fraction,
                    }
                )
            parent.storage -= total * fraction

    def _predation(self, active):
        if not active:
            return super()._predation(active)
        p = self.p
        positions = np.asarray([self.bodies[i].position for i in active])
        radii = np.asarray([self.bodies[i].radius for i in active])
        predation = []
        care = defaultdict(list)
        for ix, i in enumerate(active[:-1]):
            a = self.bodies[i]
            delta = difference(positions[ix + 1 :], positions[ix], p.side_m)
            nearby = (delta * delta).sum(axis=1) <= (2 * (a.radius + radii[ix + 1 :])) ** 2
            for offset in np.flatnonzero(nearby):
                b = self.bodies[active[ix + 1 + int(offset)]]
                gap, _, separation = self.geometry(i, b.id)
                if gap > 0:
                    continue
                if self._protected_pair(i, b.id, self.time_us):
                    for child, parent in ((a, b), (b, a)):
                        if child.parent == parent.id and 0 <= self.time_us - child.birth_us < CARE_TIME:
                            care[parent.id].append(child.id)
                elif a.radius != b.radius:
                    hunter, prey = (a, b) if a.radius > b.radius else (b, a)
                    predation.append((-hunter.radius, float(separation @ separation), hunter.id, prey.id, gap))
        for _, _, hunter_id, prey_id, gap in sorted(predation):
            hunter, prey = self.bodies[hunter_id], self.bodies[prey_id]
            if not hunter.physical or not prey.physical:
                continue
            charge = p.shell_barrier_energy * prey.shell * (prey.radius / p.radius_m) ** 2
            paid = min(hunter.storage, charge)
            hunter.storage -= paid
            transfer = self._consume_body_energy(hunter, prey)
            remaining = min(hunter.storage, charge - paid)
            hunter.storage -= remaining
            paid += remaining
            self.totals["shell_heat"] += paid
            self.totals["predations"] += 1
            hunter.captured += 1
            hunter.contact = 1.0
            prey.physical, prey.consumed_by, prey.body_failure = False, hunter_id, "captured"
            self.engines[prey_id].close_inputs()
            self.events.append(
                dict(
                    kind="body_engulfed",
                    method="volume_contact",
                    time_us=self.time_us,
                    predator=hunter_id,
                    individual=prey_id,
                    hunter_volume=volume(hunter),
                    prey_volume=volume(prey),
                    surface_gap_m=gap,
                    shell_cost=paid,
                    shell_unpaid=charge - paid,
                    **transfer,
                )
            )
        self._nurse(care)
        super()._predation([i for i in active if self.bodies[i].physical])

    def grow(self, b):
        target = self.adult_radii[b.id]
        if b.radius >= target:
            return
        adult_cost = self.construction_cost({"radius": target, "shell": b.shell})
        paid = self.construction_paid[b.id]
        available = max(0.0, b.storage - self.neonatal_reserve(self.birth_radii[b.id]))
        cost = min(max(0.0, adult_cost - paid), adult_cost / GROWTH_SECONDS, available)
        if not cost:
            return
        before = b.radius
        b.storage -= cost
        self.construction_paid[b.id] = min(adult_cost, paid + cost)
        material = cost * self.p.body_material_fraction
        self.body_material[b.id] += material
        self.totals["body_heat"] += cost - material
        b.radius = target * (self.construction_paid[b.id] / adult_cost) ** (1 / 3)
        self.events.append(
            {
                "kind": "body_growth",
                "time_us": self.time_us,
                "individual": b.id,
                "old_radius": before,
                "radius": b.radius,
                "paid": cost,
                "material": material,
                "heat": cost - material,
            }
        )

    def _reproduce(self):
        p, now = self.p, self.time_us
        if now % SECOND == 0:
            for b in self.bodies.values():
                if b.physical:
                    self.grow(b)
        if not p.reproduction or now % p.reproduction_interval_us:
            return
        eligible = [
            b
            for b in self.bodies.values()
            if b.physical
            and self._reproduction_ready(b.id)
            and now - b.birth_us >= p.reproduction_age_us
            and now - b.last_birth_us >= p.reproduction_cooldown_us
            and b.radius >= 0.75 * self.adult_radii[b.id]
            and b.storage >= p.parent_retained_food + BROOD * (p.child_energy + p.reproduction_cost)
        ]
        eligible.sort(key=lambda b: (b.id - now // p.reproduction_interval_us) % len(self.bodies))
        alive = sum(b.physical for b in self.bodies.values())
        for parent in eligible:
            if alive + BROOD > p.population_limit or self.totals["births"] + BROOD > p.total_birth_limit:
                self.totals["deferred_births"] += 1
                continue
            if parent.pending_birth is None:
                genetic_parent = copy.copy(parent)
                genetic_parent.radius = self.adult_radii[parent.id]
                siblings = []
                for _ in range(BROOD):
                    traits, donor, recombined = self._child_traits(genetic_parent)
                    if donor is not None or recombined:
                        raise ValueError("unexpected second genetic parent")
                    shape, grip = self.pending_shape.pop(parent.id)
                    siblings.append({"traits": dict(traits, elongation=shape, grip=grip)})
                parent.pending_birth = {"siblings": siblings}
            plans = []
            for sibling in parent.pending_birth["siblings"]:
                traits = dict(sibling["traits"])
                adult = traits["radius"]
                traits["radius"] = min(NEWBORN_RADIUS, parent.radius / 2, adult)
                plans.append((traits, adult, self.neonatal_reserve(traits["radius"]), self.construction_cost(traits)))
            bill = sum(p.child_energy + p.reproduction_cost + reserve + cost for _, _, reserve, cost in plans)
            if parent.storage < p.parent_retained_food + bill:
                continue
            image = self.engines[parent.id].capture_state()
            newborn = newborn_without_endowment(image)
            angle = self.mutations.uniform(-math.pi, math.pi)
            max_child = max(extent(t["radius"], t["elongation"]) for t, *_ in plans)
            distance = max(
                extent(parent.radius, parent.elongation) + max_child + 0.001, (2 * max_child + 0.001) / math.sqrt(3)
            )
            before = parent.storage
            parent.storage -= bill
            parent.last_birth_us = now
            parent.children += BROOD
            parent.pending_birth = None
            for number, (traits, adult, reserve, cost) in enumerate(plans):
                direction = angle + number * math.tau / BROOD
                pos = (parent.position + distance * np.array([math.cos(direction), math.sin(direction)])) % p.side_m
                i = len(self.bodies)
                core = create_engine(state=newborn, backend=self.backend)
                core.supply_energy(p.child_energy, time_us=0, source="parent-stored-nutrient/2")
                core.advance_to(0)
                body = ContactBody(
                    id=i,
                    parent=parent.id,
                    generation=parent.generation + 1,
                    birth_us=now,
                    position=pos.tolist(),
                    velocity=list(parent.velocity),
                    angle=parent.angle,
                    storage=reserve,
                    last_birth_us=now,
                    **traits,
                )
                self.bodies[i] = body
                self.engines[i], self.seeds[i], self.cohorts[i] = core, self.seeds[parent.id], self.cohorts[parent.id]
                self.adult_radii[i], self.birth_radii[i] = adult, body.radius
                self.remember_family(body)
                material = cost * p.body_material_fraction
                self.body_material[i], self.construction_paid[i] = material, cost
                self.totals["reproduction_heat"] += p.reproduction_cost + cost - material
                self.totals["births"] += 1
                self.events.append(
                    {
                        "kind": "birth",
                        "time_us": now,
                        "parent": parent.id,
                        "individual": i,
                        "generation": body.generation,
                        "litter_size": BROOD,
                        "traits": traits,
                        "adult_target_radius": adult,
                        "parent_radius": parent.radius,
                        "litter_bill": bill,
                        "parent_before": before,
                        "parent_after": parent.storage,
                        "construction_cost": cost,
                        "construction_heat": cost - material,
                        "body_material_energy": material,
                        "core_grant": p.child_energy,
                        "body_grant": reserve,
                        "child_energy": p.child_energy + reserve,
                        "parent_state": image.digest,
                        "child_state": core.capture_state().digest,
                    }
                )
            alive += BROOD


def make_world(block, interval_s, **engineering):
    protocol = read(E38_INPUT)
    grain = protocol["nutrient_energy"]
    protocol.update(
        schema="threemind.ocean-enclosure/2",
        body_material_fraction=0.5,
        capture_enabled=False,
        seed=472100 + 100 * block,
        environment_seed=SEEDS[block],
        nutrient_initial=53,
        nutrient_interval_us=interval_s * SECOND,
        initial_energy=grain,
        child_energy=grain,
    )
    protocol.update(engineering)
    world = JuvenileWorld(protocol)
    world.configure({i: "native" for i in world.bodies}, {"native": "core"})
    world.research.update(
        environment_rules=RULES,
        brood_size=BROOD,
        supply_seconds=interval_s,
        parent_protection="three parental links per lineage",
        growth_seconds=GROWTH_SECONDS,
        nursing_seconds=CARE_TIME // SECOND,
        nursing_energy_per_second=CARE_RATE,
    )
    return world
