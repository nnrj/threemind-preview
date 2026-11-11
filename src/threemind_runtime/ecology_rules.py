"""External resource and reproduction rules; no Core, database or renderer dependency.

This policy layer is not yet a connected ecological trainer. Its measurements
must come from the physical adapter, and births still require the Runtime's
explicit inheritance transform and an atomic population checkpoint.
"""

from __future__ import annotations

import hashlib
import json
import math
from itertools import pairwise
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .world_schema import Id, Model, Nonnegative, Positive, Vec3, digest

Accumulated = Annotated[float, Field(ge=0)]
IndividualId = Annotated[str, Field(pattern=r"^n(0|[1-9][0-9]{0,5})$")]


class ResourcePatch(Model):
    id: Id
    label: str = Field(default="", max_length=120)
    position: Vec3 = (0.0, 0.0, 0.15)
    radius: Positive = 0.8
    capacity: Positive = 30.0
    initial: Nonnegative = 20.0
    regeneration_per_s: Nonnegative = 1.0
    minimum_gatherers: int = Field(default=1, ge=1, le=256)

    @model_validator(mode="after")
    def initial_capacity(self):
        if self.initial > self.capacity:
            raise ValueError("patch initial resources exceed its capacity")
        return self


class Hazard(Model):
    id: Id
    label: str = Field(default="", max_length=120)
    position: Vec3 = (0.0, 0.0, 0.0)
    radius: Positive = 0.5
    damage_per_s: Nonnegative = 1.0


class Reproduction(Model):
    enabled: bool = True
    parent_state: Literal["body_and_viable_core", "body_only"] = "body_and_viable_core"
    interval_us: int = Field(default=1000000, ge=1, le=1000000000)
    minimum_age_us: int = Field(default=2000000, ge=0, le=10**15)
    cooldown_us: int = Field(default=5000000, ge=1, le=10**15)
    threshold: Positive = 6.0
    offspring_reserve: Positive = 2.0
    expenditure: Nonnegative = 0.5
    parent_minimum_reserve: Nonnegative = 1.0
    population_limit: int = Field(default=16, ge=1, le=256)
    offspring_limit: int = Field(default=10000, ge=0, le=100000)

    @model_validator(mode="after")
    def budget(self):
        if self.threshold < self.offspring_reserve + self.expenditure + self.parent_minimum_reserve:
            raise ValueError("reproduction threshold must cover offspring, expenditure and retained parent resources")
        return self


class EcologyRules(Model):
    schema_id: Literal["threemind.ecology-rules/1"] = "threemind.ecology-rules/1"
    habitat: Literal["shared", "independent"] = "shared"
    allocation: Literal["equal", "demand", "nearest"] = "equal"
    patches: list[ResourcePatch] = Field(default_factory=lambda: [ResourcePatch(id="resource")], max_length=64)
    hazards: list[Hazard] = Field(default_factory=list, max_length=64)
    reserve_capacity: Positive = 10.0
    founder_reserve: Positive = 4.0
    uptake_per_s: Nonnegative = 1.0
    maintenance_per_s: Nonnegative = 0.1
    effort_per_s: Nonnegative = 0.02
    contact_force_threshold: Nonnegative = 10.0
    damage_per_force_s: Nonnegative = 0.0
    fatal_damage: Positive = 10.0
    reproduction: Reproduction = Field(default_factory=Reproduction)

    @model_validator(mode="after")
    def coherent(self):
        if (
            max(self.founder_reserve, self.reproduction.offspring_reserve, self.reproduction.threshold)
            > self.reserve_capacity
        ):
            raise ValueError("initial resources and reproduction threshold must fit the body reserve capacity")
        for group in (self.patches, self.hazards):
            if len({item.id for item in group}) != len(group):
                raise ValueError("duplicate ecological region ID")
        return self

    @property
    def physical_digest(self):
        value = self.model_dump(mode="json")
        for group in ("patches", "hazards"):
            value[group] = sorted(value[group], key=lambda item: item["id"])
            for item in value[group]:
                item.pop("label")
        return digest(value)


class BodyMeasurement(Model):
    position: Vec3
    # This is a declared command-effort cost, not mechanical work in joules.
    effort: Accumulated = 0.0
    contact_force: Accumulated = 0.0


class BodyAccount(Model):
    id: IndividualId
    parent_id: IndividualId | None = None
    generation: int = Field(default=0, ge=0)
    birth_us: int = Field(ge=0)
    reserve: Nonnegative
    damage: Accumulated = 0.0
    alive: bool = True
    last_reproduction_us: int | None = Field(default=None, ge=0)


class LedgerState(Model):
    schema_id: Literal["threemind.ecology-ledger/1"] = "threemind.ecology-ledger/1"
    rules_hash: str
    seed: int = Field(ge=0, le=2**32 - 1)
    period_us: int = Field(ge=1, le=1000000)
    time_us: int = Field(ge=0)
    next_reproduction_us: int = Field(ge=0)
    pending_reproduction_us: int | None = Field(default=None, ge=0)
    founder_count: int = Field(ge=1, le=256)
    accounts: list[BodyAccount] = Field(max_length=100256)
    pools: dict[str, dict[str, Nonnegative]]
    external_initial: Accumulated
    regenerated: Accumulated
    maintenance_spent: Accumulated
    effort_spent: Accumulated
    reproduction_spent: Accumulated
    deferred_population: int = Field(ge=0)
    deferred_budget: int = Field(ge=0)


def typed(model, value):
    return model.model_validate_json(json.dumps(value, allow_nan=False), strict=True)


def distribute(demand, amount, mode, distances=None):
    """No recipient can receive more than its declared demand or available stock."""
    if any(not math.isfinite(v) or v < 0 for v in [amount, *demand.values()]):
        raise ValueError("resource stock and demands must be finite and nonnegative")
    if mode not in {"equal", "demand", "nearest"}:
        raise ValueError("unknown resource allocation policy")
    if mode == "nearest" and (
        distances is None
        or any(key not in distances or not math.isfinite(distances[key]) or distances[key] < 0 for key in demand)
    ):
        raise ValueError("nearest allocation requires actual finite distances")
    keys = sorted(demand)
    total = math.fsum(demand.values())
    if amount >= total:
        return {key: demand[key] for key in keys}
    amount = min(amount, total)
    if not total:
        return {key: 0.0 for key in keys}
    if mode == "demand":
        return {key: min(demand[key], amount * demand[key] / total) for key in keys}
    if mode == "nearest":
        result = {key: 0.0 for key in keys}
        for key in sorted(keys, key=lambda key: (distances[key], key)):
            result[key] = min(demand[key], amount)
            amount = max(0.0, amount - result[key])
        return result
    result = {key: 0.0 for key in keys}
    pending = sorted(keys, key=lambda key: (demand[key], key))
    for index, key in enumerate(pending):
        share = min(demand[key], amount / (len(pending) - index))
        result[key] = share
        amount = max(0.0, amount - share)
    return result


class EcologyLedger:
    def __init__(self, rules, seed, period_us, founders=2, *, state=None):
        self.rules = typed(EcologyRules, rules.model_dump(mode="json") if isinstance(rules, EcologyRules) else rules)
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise ValueError("invalid ecology seed")
        if (
            type(period_us) is not int
            or not 1 <= period_us <= 1000000
            or self.rules.reproduction.interval_us % period_us
        ):
            raise ValueError("ecology settlement interval must divide the reproduction interval")
        if type(founders) is not int or not 1 <= founders <= self.rules.reproduction.population_limit:
            raise ValueError("invalid initial population")
        self.seed, self.period_us = seed, period_us
        self.time_us = 0
        self.next_reproduction_us = self.rules.reproduction.interval_us
        self.pending_reproduction_us = None
        self.founder_count = founders
        self.accounts = {
            f"n{i}": BodyAccount(id=f"n{i}", birth_us=0, reserve=self.rules.founder_reserve) for i in range(founders)
        }
        self.pools = {}
        self.external_initial = founders * self.rules.founder_reserve
        self.regenerated = self.maintenance_spent = self.effort_spent = self.reproduction_spent = 0.0
        self.deferred_population = self.deferred_budget = 0
        for account in self.accounts.values():
            self._habitat(account.id)
        if state is not None:
            self._restore(state)

    def _habitat(self, identity):
        key = "shared" if self.rules.habitat == "shared" else identity
        if key not in self.pools:
            self.pools[key] = {patch.id: patch.initial for patch in self.rules.patches}
            self.external_initial += math.fsum(self.pools[key].values())
        return key

    def _restore(self, value):
        saved = typed(LedgerState, value)
        if (saved.rules_hash, saved.seed, saved.period_us, saved.founder_count) != (
            self.rules.physical_digest,
            self.seed,
            self.period_us,
            self.founder_count,
        ):
            raise ValueError("ecology rules or identity changed; exact continuation refused")
        rule = self.rules.reproduction
        if (
            saved.time_us % self.period_us
            or saved.next_reproduction_us != (saved.time_us // rule.interval_us + 1) * rule.interval_us
        ):
            raise ValueError("inconsistent ecology clock")
        if saved.pending_reproduction_us is not None and (
            saved.pending_reproduction_us != saved.time_us
            or saved.time_us % rule.interval_us
            or saved.time_us == 0
            or not rule.enabled
        ):
            raise ValueError("inconsistent pending reproduction boundary")
        accounts = {item.id: item for item in saved.accounts}
        if (
            not self.founder_count <= len(accounts) <= self.founder_count + rule.offspring_limit
            or set(accounts) != {f"n{i}" for i in range(len(accounts))}
            or len(accounts) != len(saved.accounts)
            or sum(a.alive for a in accounts.values()) > rule.population_limit
        ):
            raise ValueError("inconsistent ecological lineage identifiers")
        accounts = {f"n{i}": accounts[f"n{i}"] for i in range(len(accounts))}
        patches = {patch.id: patch for patch in self.rules.patches}
        expected_pools = {"shared"} if self.rules.habitat == "shared" else set(accounts)
        if set(saved.pools) != expected_pools:
            raise ValueError("ecology resource habitats are incomplete")
        for pool in saved.pools.values():
            if set(pool) != set(patches) or any(value > patches[key].capacity for key, value in pool.items()):
                raise ValueError("resource pool capacity mismatch")
        child_times = {key: [] for key in accounts}
        previous_birth = 0
        for i, account in enumerate(accounts.values()):
            if (
                account.reserve > self.rules.reserve_capacity
                or not previous_birth <= account.birth_us <= saved.time_us
                or account.birth_us % rule.interval_us
                or account.alive != (account.reserve > 0 and account.damage < self.rules.fatal_damage)
            ):
                raise ValueError("invalid body resource state")
            previous_birth = account.birth_us
            if i < self.founder_count:
                if account.parent_id is not None or account.generation or account.birth_us:
                    raise ValueError("inconsistent founder lineage")
            elif account.parent_id is not None:
                parent = accounts.get(account.parent_id)
                if (
                    parent is None
                    or int(parent.id[1:]) >= int(account.id[1:])
                    or account.generation != parent.generation + 1
                    or account.birth_us <= parent.birth_us
                    or account.birth_us - parent.birth_us < rule.minimum_age_us
                ):
                    raise ValueError("inconsistent parent lineage")
                child_times[parent.id].append(account.birth_us)
            else:
                raise ValueError("offspring is missing a parent")
        for key, account in accounts.items():
            times = child_times[key]
            if account.last_reproduction_us != max(times, default=None) or any(
                b - a < rule.cooldown_us for a, b in pairwise(times)
            ):
                raise ValueError("inconsistent reproduction history")
        expected_supply = self.founder_count * self.rules.founder_reserve + len(expected_pools) * math.fsum(
            patch.initial for patch in self.rules.patches
        )
        expected_spending = (len(accounts) - self.founder_count) * rule.expenditure
        if not math.isclose(saved.external_initial, expected_supply, rel_tol=1e-10, abs_tol=1e-8) or not math.isclose(
            saved.reproduction_spent, expected_spending, rel_tol=1e-10, abs_tol=1e-8
        ):
            raise ValueError("external supply or reproduction expenditure differs from the declared rules")
        for key, val in saved.model_dump(exclude={"schema_id", "rules_hash", "accounts"}).items():
            setattr(self, key, val)
        self.accounts = accounts
        self.check_balance()

    def snapshot(self):
        value = {
            key: getattr(self, key) for key in LedgerState.model_fields if hasattr(self, key) and key != "accounts"
        }
        value.update(
            rules_hash=self.rules.physical_digest,
            accounts=[account.model_dump(mode="json") for account in self.accounts.values()],
        )
        return typed(LedgerState, value).model_dump(mode="json")

    def check_balance(self):
        remaining = math.fsum(account.reserve for account in self.accounts.values()) + math.fsum(
            value for pool in self.pools.values() for value in pool.values()
        )
        spent = math.fsum((self.maintenance_spent, self.effort_spent, self.reproduction_spent))
        if not math.isclose(self.external_initial + self.regenerated, remaining + spent, rel_tol=1e-10, abs_tol=1e-8):
            raise ValueError("ecological resource balance is inconsistent")
        return {
            "initial_external": self.external_initial,
            "regenerated": self.regenerated,
            "remaining": remaining,
            "spent": spent,
        }

    def step(self, measurements, *, reproduce=True):
        if self.pending_reproduction_us is not None:
            raise ValueError("finish the pending reproduction boundary before advancing the world")
        alive = {key: account for key, account in self.accounts.items() if account.alive}
        if set(measurements) != set(alive):
            raise ValueError("every living body requires an actual physical measurement; missing is not zero")
        observed = {key: typed(BodyMeasurement, value) for key, value in measurements.items()}
        now = self.time_us + self.period_us
        seconds = self.period_us / 1e6
        events, uptake = [], dict.fromkeys(alive, 0.0)
        habitats = {}
        for key in sorted(alive):
            habitats.setdefault(self._habitat(key), []).append(key)
        for habitat, members in sorted(habitats.items()):
            for patch in sorted(self.rules.patches, key=lambda item: item.id):
                pool = self.pools[habitat]
                addition = min(patch.capacity - pool[patch.id], patch.regeneration_per_s * seconds)
                pool[patch.id] += addition
                self.regenerated += addition
                distances = {key: math.dist(observed[key].position, patch.position) for key in members}
                nearby = [key for key in members if distances[key] <= patch.radius]
                if len(nearby) < patch.minimum_gatherers:
                    continue
                demand = {
                    key: max(
                        0.0,
                        min(
                            self.rules.uptake_per_s * seconds - uptake[key],
                            self.rules.reserve_capacity - alive[key].reserve - uptake[key],
                        ),
                    )
                    for key in nearby
                }
                allocation = distribute(demand, pool[patch.id], self.rules.allocation, distances)
                removed = math.fsum(allocation.values())
                pool[patch.id] = max(0.0, pool[patch.id] - removed)
                for key, amount in allocation.items():
                    uptake[key] += amount
                if removed:
                    events.append(
                        {
                            "kind": "resource_transfer",
                            "time_us": now,
                            "habitat": habitat,
                            "patch_id": patch.id,
                            "amounts": allocation,
                        }
                    )
        for key, account in alive.items():
            account.reserve += uptake[key]
            maintenance = self.rules.maintenance_per_s * seconds
            effort = self.rules.effort_per_s * observed[key].effort * seconds
            cost = maintenance + effort
            fraction = min(1.0, account.reserve / cost) if cost else 0.0
            self.maintenance_spent += maintenance * fraction
            self.effort_spent += effort * fraction
            account.reserve = max(0.0, account.reserve - cost)
            damage = (
                max(0.0, observed[key].contact_force - self.rules.contact_force_threshold)
                * self.rules.damage_per_force_s
                * seconds
            )
            damage += math.fsum(
                h.damage_per_s * seconds
                for h in self.rules.hazards
                if math.dist(observed[key].position, h.position) <= h.radius
            )
            account.damage += damage
            if damage:
                events.append({"kind": "body_damage", "time_us": now, "individual": key, "amount": damage})
            if not account.reserve or account.damage >= self.rules.fatal_damage:
                account.alive = False
                events.append(
                    {
                        "kind": "body_failed",
                        "time_us": now,
                        "individual": key,
                        "reason": "resource_exhaustion" if not account.reserve else "damage",
                        "core_death_observed": False,
                    }
                )
        self.time_us = now
        if now >= self.next_reproduction_us:
            self.next_reproduction_us = now + self.rules.reproduction.interval_us
            if self.rules.reproduction.enabled:
                self.pending_reproduction_us = now
                if reproduce:
                    events.extend(self.finish_boundary())
        self.check_balance()
        return events

    def finish_boundary(self, viable_parents=None):
        if viable_parents is not None and not set(viable_parents) <= set(self.accounts):
            raise ValueError("unknown parent viability observation")
        if self.pending_reproduction_us is None:
            return []
        events = self._reproduce(viable_parents)
        self.pending_reproduction_us = None
        self.check_balance()
        return events

    def _reproduce(self, viable_parents):
        rule, now = self.rules.reproduction, self.time_us
        available = rule.population_limit - sum(account.alive for account in self.accounts.values())
        remaining = rule.offspring_limit - (len(self.accounts) - self.founder_count)
        eligible = [
            account
            for account in self.accounts.values()
            if account.alive
            and account.reserve >= rule.threshold
            and now - account.birth_us >= rule.minimum_age_us
            and (account.last_reproduction_us is None or now - account.last_reproduction_us >= rule.cooldown_us)
        ]
        # The lottery is an explicit ecological boundary, independent of worker scheduling.
        eligible.sort(
            key=lambda account: (
                hashlib.sha256(f"ecology-birth-v1:{self.seed}:{now}:{account.id}".encode()).digest(),
                account.id,
            )
        )
        events = []
        for parent in eligible:
            if (
                rule.parent_state == "body_and_viable_core"
                and viable_parents is not None
                and parent.id not in viable_parents
            ):
                events.append(
                    {"kind": "birth_deferred", "time_us": now, "parent": parent.id, "reason": "core_not_viable"}
                )
                continue
            if available <= 0:
                self.deferred_population += 1
                events.append(
                    {"kind": "birth_deferred", "time_us": now, "parent": parent.id, "reason": "population_limit"}
                )
                continue
            if remaining <= 0:
                self.deferred_budget += 1
                events.append(
                    {"kind": "birth_deferred", "time_us": now, "parent": parent.id, "reason": "offspring_budget"}
                )
                continue
            identity = f"n{len(self.accounts)}"
            parent.reserve -= rule.offspring_reserve + rule.expenditure
            parent.last_reproduction_us = now
            self.reproduction_spent += rule.expenditure
            self.accounts[identity] = BodyAccount(
                id=identity,
                parent_id=parent.id,
                generation=parent.generation + 1,
                birth_us=now,
                reserve=rule.offspring_reserve,
            )
            before = self.external_initial
            habitat = self._habitat(identity)
            events.append(
                {
                    "kind": "birth_due",
                    "time_us": now,
                    "parent": parent.id,
                    "individual": identity,
                    "generation": parent.generation + 1,
                    "offspring_reserve": rule.offspring_reserve,
                    "reproduction_expenditure": rule.expenditure,
                    "habitat": habitat,
                    "new_habitat_external_supply": self.external_initial - before,
                    "inheritance_rule": "threemind.birth/1",
                    "model_born": False,
                    "core_viability_checked": viable_parents is not None,
                }
            )
            available -= 1
            remaining -= 1
        return events
