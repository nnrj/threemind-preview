"""Versioned local birth-window novelty; old memory/1 is never converted implicitly."""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from threemind_core import StateImage
from threemind_core.spec import timestamp

from .mechanisms import number
from .memory import MECHANISMS as MEMORY_MECHANISMS
from .memory import MemoryConfig, MemoryDynamics, MemoryEngine
from .memory import definition as memory_definition

KERNEL_ID = "threemind.continuous-memory/2"
STATE_SCHEMA = "threemind.continuous-memory-state/2"
MECHANISMS = MEMORY_MECHANISMS + (("threemind.local-birth-novelty/2", "after-arrivals-before-emission"),)
COUNTERS = ("births", "ineligible", "disabled", "no_reentry", "reference_reached", "awarded", "cancelled")
TOTALS = ("requested_bonus", "weight_bonus", "stability_bonus")


@dataclass(frozen=True, slots=True)
class NoveltyConfig(MemoryConfig):
    novelty_mode: str = "arrival-window"

    def __post_init__(self):
        normalized = MemoryConfig(**{key: getattr(self, key) for key in MemoryConfig.__dataclass_fields__})
        for key in MemoryConfig.__dataclass_fields__:
            object.__setattr__(self, key, getattr(normalized, key))
        if self.novelty_mode not in ("immediate", "arrival-window"):
            raise ValueError("novelty_mode must be immediate or arrival-window")


class NoveltyDynamics(MemoryDynamics):
    def __init__(self, config, state=None):
        self.pending_novelty = {}
        self.novelty_by_node = {}
        self.novelty_deadlines = []
        self.novelty_serial = 0
        self.novelty_audit = dict.fromkeys(COUNTERS, 0) | dict.fromkeys(TOTALS, 0.0)
        super().__init__(config, state)

    def _index_birth(self, key, row):
        self.pending_novelty[key] = row
        for node in key:
            self.novelty_by_node.setdefault(node, set()).add(key)
        heapq.heappush(self.novelty_deadlines, (int(row["deadline_us"]), row["serial"], key))

    def _drop_birth(self, key):
        row = self.pending_novelty.pop(key)
        for node in key:
            keys = self.novelty_by_node[node]
            keys.discard(key)
            if not keys:
                del self.novelty_by_node[node]
        return row

    def _birth_novelty(self, source, target, connected):
        c = self.config
        self.novelty_audit["births"] += 1
        eligible = source in connected or target in connected
        if self.parameters.novelty_mode == "immediate":
            bonus = super()._birth_novelty(source, target, connected)
            reentry = max(self.nodes[source].associative, self.nodes[target].associative)
            reason = self._reason(eligible, c.local_novelty_gain, reentry, c.novelty_touch_reference)
            self.novelty_audit[reason] += 1
            self.novelty_audit["requested_bonus"] += bonus
            # Applied totals are only recorded for delayed settlements, whose pre-update rows are available.
            return bonus
        if not eligible or c.local_novelty_gain == 0:
            self.novelty_audit["ineligible" if not eligible else "disabled"] += 1
            return 0.0
        self.novelty_serial += 1
        self._index_birth(
            (source, target),
            {
                "source": source,
                "target": target,
                "serial": self.novelty_serial,
                "birth_us": str(self.time_us),
                "deadline_us": str(self.next_propagation_us + c.delay_us),
                "gain": c.local_novelty_gain,
                "reference": c.novelty_touch_reference,
                "source_touch": self.nodes[source].associative,
                "target_touch": self.nodes[target].associative,
            },
        )
        return 0.0

    @staticmethod
    def _reason(eligible, gain, reentry, reference):
        if not eligible:
            return "ineligible"
        if gain == 0:
            return "disabled"
        if reentry <= 0:
            return "no_reentry"
        return "reference_reached" if reentry >= reference else "awarded"

    def _touch(self, node_id, value, *, direct):
        amount = super()._touch(node_id, value, direct=direct)
        if not direct and amount > 0:
            for key in self.novelty_by_node.get(node_id, ()):
                row = self.pending_novelty[key]
                field = "source_touch" if key[0] == node_id else "target_touch"
                row[field] += amount
        return amount

    def _next_local_deadline(self):
        while self.novelty_deadlines:
            deadline, serial, key = self.novelty_deadlines[0]
            if key in self.pending_novelty and self.pending_novelty[key]["serial"] == serial:
                return deadline
            heapq.heappop(self.novelty_deadlines)
        return None

    def _settle_local_arrivals(self):
        while NoveltyDynamics._next_local_deadline(self) is not None and self.novelty_deadlines[0][0] <= self.time_us:
            _, _, key = heapq.heappop(self.novelty_deadlines)
            row = self._drop_birth(key)
            if (
                key not in self.edges
                or not self.config.plasticity
                or key in self.silenced_edges
                or any(n in self.silenced_nodes for n in key)
            ):
                self.novelty_audit["cancelled"] += 1
                continue
            reentry = max(row["source_touch"], row["target_touch"])
            reason = self._reason(True, row["gain"], reentry, row["reference"])
            self.novelty_audit[reason] += 1
            if reason == "awarded":
                bonus = row["gain"] * max(0.0, 1.0 - min(1.0, reentry / row["reference"]))
                self._prepare_edge(key)
                edge = self.edges[key]
                self.novelty_audit["requested_bonus"] += bonus
                self.novelty_audit["weight_bonus"] += min(1.0, edge.weight + bonus) - edge.weight
                self.novelty_audit["stability_bonus"] += min(1.0, edge.stability + bonus) - edge.stability
                edge.weight = min(1.0, edge.weight + bonus)
                edge.stability = min(1.0, edge.stability + bonus)
                self._edge_changed(key)

    def _remove_edge(self, key):
        if key in self.pending_novelty:
            self._drop_birth(key)
            self.novelty_audit["cancelled"] += 1
        super()._remove_edge(key)

    def settle_parameters(self, config):
        if config.novelty_mode != self.parameters.novelty_mode:
            raise ValueError("novelty_mode is immutable after creation; use a new birth")
        super().settle_parameters(config)


def definition(config):
    value = memory_definition(config)
    value.update(
        kernel_id=KERNEL_ID,
        state_schema=STATE_SCHEMA,
        hypothesis_id="threemind.hypotheses/continuous-memory2",
        operators=[{"id": name, "phase": phase} for name, phase in MECHANISMS],
    )
    return value


class NoveltyEngine(MemoryEngine):
    dynamics = KERNEL_ID
    state_schema = STATE_SCHEMA
    config_type = NoveltyConfig
    engine_type = NoveltyDynamics
    definition = staticmethod(definition)

    def __init__(self, config=None, state=None):
        saved = None
        if state is not None:
            value = state.to_dict()
            saved = value.get("operator_state", {}).pop("novelty", None)
            if saved is None:
                raise ValueError("missing novelty state")
            state = StateImage.from_dict(value)
        super().__init__(config, state)
        if saved is not None:
            self._restore_novelty(saved)

    def _restore_novelty(self, saved):
        if not isinstance(saved, dict) or set(saved) != {"serial", "pending", "audit"}:
            raise ValueError("invalid novelty state fields")
        serial, rows, audit = saved["serial"], saved["pending"], saved["audit"]
        if type(serial) is not int or serial < 0 or not isinstance(rows, list):
            raise ValueError("invalid novelty serial or pending list")
        if not isinstance(audit, dict) or set(audit) != set(COUNTERS + TOTALS):
            raise ValueError("invalid novelty audit")
        for key in COUNTERS:
            if type(audit[key]) is not int or audit[key] < 0:
                raise ValueError("invalid novelty counter")
        for key in TOTALS:
            number(audit[key], key)
        serials = set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != {
                "source",
                "target",
                "serial",
                "birth_us",
                "deadline_us",
                "gain",
                "reference",
                "source_touch",
                "target_touch",
            }:
                raise ValueError("invalid pending novelty fields")
            key = row["source"], row["target"]
            birth, end = timestamp(row["birth_us"]), timestamp(row["deadline_us"])
            if (
                any(type(n) is not int for n in key)
                or key not in self.edges
                or key in self.pending_novelty
                or row["birth_us"] != self.edges[key].birth_us
                or not birth <= self.time_us < end
                or type(row["serial"]) is not int
                or not 0 < row["serial"] <= serial
                or row["serial"] in serials
                or self.config.novelty_mode != "arrival-window"
            ):
                raise ValueError("invalid pending novelty identity or lifetime")
            for field in ("gain", "source_touch", "target_touch"):
                number(row[field], field)
            number(row["reference"], "novelty reference", low=1e-300)
            serials.add(row["serial"])
            self._engine._index_birth(key, dict(row))
        self._engine.novelty_serial = serial
        self._engine.novelty_audit = dict(audit)

    def capture_state(self):
        value = super().capture_state().to_dict()
        value["operator_state"]["novelty"] = {
            "serial": self.novelty_serial,
            "pending": [dict(row) for _, row in sorted(self.pending_novelty.items())],
            "audit": dict(self.novelty_audit),
        }
        return StateImage.from_dict(value)

    def metrics(self):
        return super().metrics() | {"novelty": dict(self.novelty_audit) | {"pending": len(self.pending_novelty)}}
