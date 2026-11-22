"""A simulated water world with immediate contact predation and paid twin births."""

import math
import numpy as np

from paths import SECOND, SEEDS
from apparatus import E38_INPUT, create_engine, newborn_without_endowment, read
from carrion import Carrion63
from lab.tools.ocean import difference
from lab.tools.ocean_contact import ContactBody, ContactOcean

STATE = "threemind.ocean-volume-contact-litter-state/1"
RULES = "threemind.ocean-volume-contact-litter/1"


def volume(body):
    return 4 * math.pi * body.radius**3 / 3


def extent(radius, elongation):
    return radius * (1 + elongation) / math.sqrt(1 + 4 * elongation / math.pi)


class ContactLitter63(Carrion63):
    def __init__(self, protocol, *, state=None, images=None, **kwargs):
        if state is not None:
            if state.get("schema") != STATE or state["rules"] != RULES:
                raise ValueError("a P1 world requires its own complete state")
            state = state["carrion"]
        super().__init__(protocol, state=state, images=images, **kwargs)

    def capture(self):
        return dict(schema=STATE, rules=RULES, carrion=super().capture())

    def geometry(self, i, j):
        # Keep the actual capsule surface distance. The inherited collision and
        # carcass code needs this distance; live meals are handled here in P1.
        gap, _, delta = ContactOcean.geometry(self, i, j)
        return gap, False, delta

    _separate_overlap = ContactOcean._separate_overlap

    def _protected_pair(self, predator, victim, now):
        return False

    def _predation(self, active):
        p = self.p
        positions = np.asarray([self.bodies[i].position for i in active])
        radii = np.asarray([self.bodies[i].radius for i in active])
        pairs = []
        for ix, i in enumerate(active[:-1]):
            delta = difference(positions[ix + 1 :], positions[ix], p.side_m)
            close = (delta * delta).sum(axis=1) <= (2 * (radii[ix] + radii[ix + 1 :])) ** 2
            for offset in np.flatnonzero(close):
                j = active[ix + 1 + int(offset)]
                a, b = self.bodies[i], self.bodies[j]
                if a.radius == b.radius:
                    continue
                gap, _, displacement = self.geometry(i, j)
                if gap > 0:
                    continue
                hunter, prey = (a, b) if a.radius > b.radius else (b, a)
                pairs.append((-hunter.radius, float(displacement @ displacement), hunter.id, prey.id, gap))
        for _, _, hunter_id, prey_id, gap in sorted(pairs):
            hunter, prey = self.bodies[hunter_id], self.bodies[prey_id]
            if not hunter.physical or not prey.physical:
                continue
            charge = p.shell_barrier_energy * prey.shell * (prey.radius / p.radius_m) ** 2
            paid = min(hunter.storage, charge)
            hunter.storage -= paid
            transfer = self._consume_body_energy(hunter, prey)
            remainder = min(hunter.storage, charge - paid)
            hunter.storage -= remainder
            paid += remainder
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
        super()._predation([i for i in active if self.bodies[i].physical])

    def _reproduce(self):
        p, now = self.p, self.time_us
        if not p.reproduction or now % p.reproduction_interval_us:
            return
        base_cost = p.child_energy + p.child_body_energy + p.reproduction_cost
        eligible = [
            b
            for b in self.bodies.values()
            if b.physical
            and self._reproduction_ready(b.id)
            and now - b.birth_us >= p.reproduction_age_us
            and now - b.last_birth_us >= p.reproduction_cooldown_us
            and b.storage >= p.parent_retained_food + 2 * (base_cost + 0.125 * p.construction_energy)
        ]
        eligible.sort(key=lambda b: (b.id - now // p.reproduction_interval_us) % len(self.bodies))
        alive = sum(b.physical for b in self.bodies.values())
        for parent in eligible:
            if alive + 2 > p.population_limit or self.totals["births"] + 2 > p.total_birth_limit:
                self.totals["deferred_births"] += 1
                continue
            if parent.pending_birth is None:
                siblings = []
                for _ in range(2):
                    traits, donor, recombined = self._child_traits(parent)
                    shape, grip = self.pending_shape.pop(parent.id)
                    siblings.append(
                        dict(traits=dict(traits, elongation=shape, grip=grip), donor=donor, recombined=recombined)
                    )
                parent.pending_birth = {"siblings": siblings}
            siblings = parent.pending_birth["siblings"]
            material = [self.construction_cost(s["traits"]) for s in siblings]
            bill = 2 * base_cost + sum(material)
            if parent.storage < p.parent_retained_food + bill:
                continue
            image = self.engines[parent.id].capture_state()
            newborn = newborn_without_endowment(image)
            angle = self.mutations.uniform(-math.pi, math.pi)
            direction = np.array([math.cos(angle), math.sin(angle)])
            parent.storage -= bill
            parent.last_birth_us = now
            parent.children += 2
            parent.pending_birth = None
            for side, sibling, cost in zip((1, -1), siblings, material):
                traits = sibling["traits"]
                offset = (
                    extent(parent.radius, parent.elongation) + extent(traits["radius"], traits["elongation"]) + 0.001
                )
                pos = (parent.position + side * offset * direction) % p.side_m
                i = len(self.bodies)
                core = create_engine(state=newborn, backend=self.backend)
                core.supply_energy(p.child_energy, time_us=0, source="parent-stored-nutrient/2")
                core.advance_to(0)
                self.bodies[i] = ContactBody(
                    id=i,
                    parent=parent.id,
                    generation=parent.generation + 1,
                    birth_us=now,
                    position=pos.tolist(),
                    velocity=list(parent.velocity),
                    angle=parent.angle,
                    storage=p.child_body_energy,
                    last_birth_us=now,
                    **traits,
                )
                self.engines[i], self.seeds[i] = core, self.seeds[parent.id]
                self.cohorts[i] = self.cohorts[parent.id]
                retained = cost * p.body_material_fraction
                self.body_material[i], self.construction_paid[i] = retained, cost
                self.totals["reproduction_heat"] += p.reproduction_cost + cost - retained
                self.totals["births"] += 1
                self.totals["recombinations"] += int(sibling["recombined"])
                self.events.append(
                    dict(
                        kind="birth",
                        time_us=now,
                        parent=parent.id,
                        individual=i,
                        litter_size=2,
                        generation=parent.generation + 1,
                        traits=traits,
                        body_donor=sibling["donor"],
                        recombined=sibling["recombined"],
                        construction_cost=cost,
                        construction_heat=cost - retained,
                        body_material_energy=retained,
                        child_energy=p.child_energy + p.child_body_energy,
                        parent_state=image.digest,
                        child_state=core.capture_state().digest,
                    )
                )
            alive += 2


def make_world(block, interval_s, **engineering):
    p = read(E38_INPUT)
    p.update(
        schema="threemind.ocean-enclosure/2",
        body_material_fraction=0.5,
        capture_enabled=False,
        seed=472100 + 100 * block,
        environment_seed=SEEDS[block],
        nutrient_initial=53,
        nutrient_interval_us=interval_s * SECOND,
    )
    p.update(engineering)
    w = ContactLitter63(p)
    w.configure({i: "native" for i in w.bodies}, {"native": "core"})
    w.research.update(
        environment_rules=RULES, parent_protection="none under volume contact", brood_size=2, supply_seconds=interval_s
    )
    return w
