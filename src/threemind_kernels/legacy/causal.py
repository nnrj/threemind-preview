"""Identity-preserving bridge to the frozen causal families.

causal/1..7 share the historical compatible executor, verified against original
continuation witnesses. causal/8 has its own restored-V3 executor. No modern
engine is executed, relabelled or used as a fallback.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import asdict
from functools import lru_cache

from threemind_core import StateImage


def version(identity):
    if identity not in tuple(f"threemind.causal/{n}" for n in range(1, 9)):
        raise ValueError("unknown historical causal identity")
    return int(identity.rsplit("/", 1)[1])


@lru_cache(maxsize=8)
def configuration_type(identity):
    cls = importlib.import_module(f".configs.causal{version(identity)}", __package__).Config
    if not hasattr(cls, "to_dict"):
        # The initial config used asdict directly; expose the same bytes contract.
        cls.to_dict = asdict
    return cls


def configuration(identity, value=None):
    cls = configuration_type(identity)
    if value is None:
        return cls()
    if type(value) is cls:
        return value
    if not isinstance(value, dict):
        raise ValueError("historical configuration must be an object belonging to the selected kernel")  # noqa: TRY004 -- public configuration validation contract
    try:
        result = cls(**value)
    except TypeError as exc:
        raise ValueError(str(exc)) from exc
    validate_capabilities(identity, result)
    return result


def fields(identity):
    return asdict(configuration(identity))


def validate_capabilities(identity, config):
    n = version(identity)
    for minimum, method, description in (
        (2, "has_optional_changes", "optional mechanisms"),
        (3, "has_budget_limits", "resource budgets"),
        (4, "has_energy_changes", "energy accounting"),
        (5, "has_attention_changes", "attention selection"),
        (6, "has_spatial_changes", "spatial mechanisms"),
    ):
        if n < minimum and hasattr(config, method) and getattr(config, method)():
            raise ValueError(f"{identity} does not implement {description}; kernel identity is fixed at birth")


class LegacyCausalEngine:
    def __init__(self, identity, config=None, state=None, *, backend="reference"):
        self.dynamics = identity
        self._version = version(identity)
        if state is not None:
            if config is not None:
                raise ValueError("restoration uses the saved configuration")
            saved = state.to_dict()
            if saved.get("dynamics") != identity:
                raise ValueError("historical kernel identity mismatch")
            config = configuration(identity, saved["config"])
        else:
            config = configuration(identity, config)
        validate_capabilities(identity, config)
        self._backend = backend
        if backend == "reference":
            self._module = importlib.import_module(
                ".causal8.engine" if self._version == 8 else ".causal_compat.engine", __package__
            )
            common = self._module.Config(**config.to_dict())
            if self._version == 8:
                self._engine = self._module.Engine(common, state)
            else:
                self._engine = self._module.Engine(common, state, dynamics=identity)
        elif backend == "native":
            from _threemind_native import NativeLegacy

            self._engine = NativeLegacy(
                identity, json.dumps(config.to_dict()), state.payload.decode() if state else None
            )
        else:
            raise ValueError("unsupported historical backend; no automatic fallback")

    @property
    def config(self):
        value = (
            self._engine.config.to_dict() if self._backend == "reference" else json.loads(self._engine.config_json())
        )
        known = configuration_type(self.dynamics).__dataclass_fields__
        return configuration(self.dynamics, {k: v for k, v in value.items() if k in known})

    @property
    def time_us(self):
        return self._engine.time_us if self._backend == "reference" else int(self._engine.time_us())

    @property
    def sequence(self):
        return self._engine.sequence if self._backend == "reference" else self._engine.sequence()

    @property
    def life(self):
        return self._engine.life if self._backend == "reference" else self._engine.life()

    def capture_state(self):
        if self._backend == "reference":
            return StateImage(self._engine.capture_state().payload)
        return StateImage(self._engine.state_json().encode())

    def inject(self, stimulus):
        if stimulus.bypass_attention and self._version < 7:
            raise ValueError("per-frame attention bypass requires causal/7; kernel identity is fixed at birth")
        if self._backend == "reference":
            return self._engine.inject(self._module.Stimulus.from_dict(stimulus.to_dict()))
        return self._engine.inject(json.dumps(stimulus.to_dict()))

    def advance_to(self, target_us, observer=None, *, inputs_only=False):
        if self._backend == "reference":
            return self._engine.advance_to(target_us, observer, inputs_only=inputs_only)
        rows = json.loads(self._engine.advance(str(target_us), observer is not None, inputs_only))
        if observer is not None:
            for row in rows:
                observer(row)

    def reconfigure(self, config):
        config = configuration(self.dynamics, config)
        validate_capabilities(self.dynamics, config)
        if self._backend == "reference":
            self._engine.reconfigure(self._module.Config(**config.to_dict()))
        else:
            self._engine.reconfigure(json.dumps(config.to_dict()))

    def close_inputs(self):
        self._engine.close_inputs()

    def supply_energy(self, amount, *, time_us=None, source="external-energy"):
        if self._version < 4:
            raise ValueError("this historical kernel has no energy port")
        if self._backend == "reference":
            return self._engine.supply_energy(amount, time_us=time_us, source=source)
        return self._engine.supply_energy(str(self.time_us if time_us is None else time_us), amount, source)

    def modulate_input(self, *, time_us=None, **adjustment):
        if self._version < 5:
            raise ValueError("this historical kernel has no attention modulation port")
        if self._backend == "reference":
            return self._engine.modulate_input(time_us=time_us, **adjustment)
        return self._engine.modulate_input(str(self.time_us if time_us is None else time_us), json.dumps(adjustment))

    def _json_query(self, method, *args):
        return json.loads(getattr(self._engine, method)(*args))

    def metrics(self):
        return self._engine.metrics() if self._backend == "reference" else self._json_query("metrics_json")

    def graph(self, limit=None):
        return self._engine.graph(limit) if self._backend == "reference" else self._json_query("graph_json", limit)

    def activations(self):
        return self._engine.activations()

    def observation_nodes(self):
        return (
            self._engine.observation_nodes()
            if self._backend == "reference"
            else self._json_query("observation_nodes_json")
        )

    def induced_edges(self, node_ids):
        return (
            self._engine.induced_edges(node_ids)
            if self._backend == "reference"
            else self._json_query("induced_edges_json", list(node_ids))
        )

    def spatial_geometry(self):
        if self._version < 6:
            raise ValueError("this historical kernel has no causal spatial contract")
        return (
            self._engine.spatial_geometry()
            if self._backend == "reference"
            else self._json_query("spatial_geometry_json")
        )

    def intervene(self, *, nodes=(), edges=(), lesion=False, action=None):
        if action not in (None, "silence", "delete_nodes", "disconnect_edges"):
            raise ValueError("historical kernel does not implement this intervention")
        if action == "delete_nodes":
            lesion = True
        if action == "disconnect_edges":
            # The historical lesion primitive deletes only selected edges when nodes is empty.
            lesion = True
        if self._backend == "reference":
            return self._engine.intervene(nodes=list(nodes), edges=list(edges), lesion=lesion)
        return self._engine.intervene(list(nodes), list(edges), lesion)


def create(identity, config=None, state=None, *, backend="reference"):
    return LegacyCausalEngine(identity, config, state, backend=backend)
