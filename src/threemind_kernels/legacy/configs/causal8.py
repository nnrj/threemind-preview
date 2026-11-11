from __future__ import annotations

import math
from dataclasses import asdict, dataclass

LEGACY_SCHEMA = "threemind.state/2"
BUDGET_SCHEMA = "threemind.state/3"
ENERGY_SCHEMA = "threemind.state/4"
SCHEMA = "threemind.state/6"
LEGACY_DYNAMICS = "threemind.causal/1"
OPTIONAL_DYNAMICS = "threemind.causal/2"
BUDGET_DYNAMICS = "threemind.causal/3"
ENERGY_DYNAMICS = "threemind.causal/4"
ATTENTION_DYNAMICS = "threemind.causal/5"
SPATIAL_DYNAMICS = "threemind.causal/6"
DYNAMICS = "threemind.causal/8"
STATE_SCHEMAS = {
    LEGACY_DYNAMICS: LEGACY_SCHEMA,
    OPTIONAL_DYNAMICS: LEGACY_SCHEMA,
    BUDGET_DYNAMICS: BUDGET_SCHEMA,
    ENERGY_DYNAMICS: ENERGY_SCHEMA,
    ATTENTION_DYNAMICS: "threemind.state/5",
    SPATIAL_DYNAMICS: "threemind.state/5",
    DYNAMICS: SCHEMA,
}
MAX_TIME = 2**128 - 1
RESOURCE_VERSIONS = (BUDGET_DYNAMICS, ENERGY_DYNAMICS, ATTENTION_DYNAMICS, SPATIAL_DYNAMICS, DYNAMICS)
ENERGY_VERSIONS = (ENERGY_DYNAMICS, ATTENTION_DYNAMICS, SPATIAL_DYNAMICS, DYNAMICS)
ATTENTION_VERSIONS = (ATTENTION_DYNAMICS, SPATIAL_DYNAMICS, DYNAMICS)
SPATIAL_VERSIONS = (SPATIAL_DYNAMICS, DYNAMICS)
SPATIAL_DEFAULTS = {
    "spatial_embedding": False,
    "spatial_dimensions": 3,
    "neighborhood_enabled": True,
    "spatial_radius": 2.5,
    "spatial_competition_rate": 0.0,
}

# Omitted defaults keep the original causal/1 model representation unchanged.
# These are scientific mechanisms, never display/performance preferences.
OPTIONAL_DEFAULTS = {
    "propagation_activation_min": 0.0,
    "consolidation_cap": 0.42,
    "association_window_us": 500_000,
    "edge_birth_policy": "co-stimulus",
    "edge_birth_activation_product_min": 0.0,
    "local_novelty_gain": 0.018,
    "novelty_touch_reference": 0.2,
    "homeostasis_enabled": False,
    "target_total_activation": 4.0,
    "inhibition_saturation": 1.0,
    "inhibition_propagation_min": 0.002,
}
BUDGET_DEFAULTS = dict.fromkeys(("max_nodes", "max_edges", "propagation_limit", "edge_adaptation_limit"))
ATTENTION_DEFAULTS = {"attention_competition_enabled": False, "attention_budget": 28}
ENERGY_DEFAULTS = {
    "energy_simulation_enabled": False,
    "energy_initial_reserve": 1.0,
    "energy_capacity": 1.0,
    "energy_direct_cost": 0.035,
    "energy_associative_cost": 0.020,
    "energy_inhibition_cost": 0.010,
    "irreversible_energy_death_enabled": False,
    "energy_maintenance_cost_per_node": 0.0002,
    "energy_maintenance_cost_per_edge": 0.00004,
    "energy_starvation_structural_decay": 0.06,
    "energy_starvation_death_us": 90_000_000,
}


def timestamp(value: int | str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("time must be an integer number of microseconds")  # noqa: TRY004 -- public protocol validation contract
    if isinstance(value, str) and (not value.isascii() or not value.isdecimal()):
        raise ValueError("time must be an unsigned decimal integer")
    result = int(value)
    if not 0 <= result <= MAX_TIME:
        raise ValueError("time exceeds the unsigned 128-bit microsecond range")
    return result


@dataclass(frozen=True, slots=True)
class Config:
    step_us: int = 10_000
    delay_us: int = 10_000
    propagation_interval_us: int = 100_000
    quiescence_death_us: int = 1_000_000
    node_prune_after_us: int = 80_000_000
    activation_tau: float = -0.1 / math.log(0.72)
    trace_tau: float = -0.1 / math.log(0.82)
    inhibition_tau: float = -0.1 / math.log(0.65)
    eligibility_tau: float = -0.1 / math.log(0.78)
    stability_tau: float = 0.1 / 0.00015  # Linear loss time scale, modulated by eligibility.
    support_tau: float = 0.1 / 0.00015  # Linear loss time scale, modulated by node stability.
    activation_decay_enabled: bool = True
    trace_decay_enabled: bool = True
    inhibition_decay_enabled: bool = True
    eligibility_decay_enabled: bool = True
    stability_decay_enabled: bool = True
    support_decay_enabled: bool = True
    propagation_rate: float = 4.2
    direct_gain: float = 0.9
    learning_rate: float = 0.055  # Weight impulse per delivered external event, not per solver step.
    birth_weight: float = 0.065
    first_gain: float = 0.045
    repeat_gain: float = 0.018
    intensity_gain: float = 0.075
    associative_gain: float = 0.01
    stability_gain: float = 0.022
    support_gain: float = 0.035
    forgetting_rate: float = 0.025
    inhibition_gain: float = 0.24
    inhibition_diffusion_rate: float = 3.5
    inhibition_response_gain: float = 2.0
    activation_floor: float = 0.004
    prune_weight: float = 0.008
    prune_support: float = 0.006
    plasticity: bool = True
    inhibition: bool = True
    seed: int = 20260724
    propagation_activation_min: float = 0.0
    consolidation_cap: float = 0.42
    association_window_us: int = 500_000
    edge_birth_policy: str = "co-stimulus"
    edge_birth_activation_product_min: float = 0.0
    local_novelty_gain: float = 0.018
    novelty_touch_reference: float = 0.2
    homeostasis_enabled: bool = False
    target_total_activation: float = 4.0
    inhibition_saturation: float = 1.0
    inhibition_propagation_min: float = 0.002  # Potential per propagation pulse, never multiplied by step size.
    max_nodes: int | None = None
    max_edges: int | None = None
    propagation_limit: int | None = None
    edge_adaptation_limit: int | None = None
    energy_simulation_enabled: bool = False
    energy_initial_reserve: float = 1.0
    energy_capacity: float = 1.0
    energy_direct_cost: float = 0.035
    energy_associative_cost: float = 0.020
    energy_inhibition_cost: float = 0.010
    irreversible_energy_death_enabled: bool = False
    energy_maintenance_cost_per_node: float = 0.0002  # units / node / simulated second
    energy_maintenance_cost_per_edge: float = 0.00004
    energy_starvation_structural_decay: float = 0.06  # s^-1, explicit damage experiment
    energy_starvation_death_us: int = 90_000_000
    attention_competition_enabled: bool = False
    attention_budget: int = 28
    spatial_embedding: bool = False
    spatial_dimensions: int = 3
    neighborhood_enabled: bool = True
    spatial_radius: float = 2.5
    spatial_competition_rate: float = 0.0

    def to_dict(self) -> dict:
        defaults = OPTIONAL_DEFAULTS | BUDGET_DEFAULTS | ENERGY_DEFAULTS | ATTENTION_DEFAULTS | SPATIAL_DEFAULTS
        return {k: v for k, v in asdict(self).items() if k not in defaults or v != defaults[k]}

    def has_optional_changes(self) -> bool:
        return any(getattr(self, k) != value for k, value in OPTIONAL_DEFAULTS.items())

    def has_budget_limits(self) -> bool:
        return any(getattr(self, k) is not None for k in BUDGET_DEFAULTS)

    def has_energy_changes(self) -> bool:
        return any(getattr(self, k) != v for k, v in ENERGY_DEFAULTS.items())

    def has_attention_changes(self) -> bool:
        return any(getattr(self, k) != v for k, v in ATTENTION_DEFAULTS.items())

    def has_spatial_changes(self) -> bool:
        return any(getattr(self, k) != v for k, v in SPATIAL_DEFAULTS.items())

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if name in BUDGET_DEFAULTS:
                if value is not None and (type(value) is not int or not 0 <= value <= 2**53 - 1):
                    raise ValueError(f"{name} must be a safe nonnegative integer or null")
            elif name == "edge_birth_policy":
                if value not in ("co-stimulus", "temporal-association"):
                    raise ValueError("unknown edge_birth_policy")
            elif name in (
                "plasticity",
                "inhibition",
                "homeostasis_enabled",
                "energy_simulation_enabled",
                "irreversible_energy_death_enabled",
                "attention_competition_enabled",
                "spatial_embedding",
                "neighborhood_enabled",
                "activation_decay_enabled",
                "trace_decay_enabled",
                "inhibition_decay_enabled",
                "eligibility_decay_enabled",
                "stability_decay_enabled",
                "support_decay_enabled",
            ):
                if type(value) is not bool:
                    raise ValueError(f"{name} must be boolean")
            elif name in (
                "step_us",
                "delay_us",
                "propagation_interval_us",
                "quiescence_death_us",
                "node_prune_after_us",
                "seed",
                "association_window_us",
                "energy_starvation_death_us",
                "attention_budget",
                "spatial_dimensions",
            ):
                if type(value) is not int or not 0 <= value <= 2**53 - 1:
                    raise ValueError(f"{name} must be a safe unsigned integer")
            elif (
                isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0
            ):
                raise ValueError(f"{name} must be finite and nonnegative")
            else:
                object.__setattr__(self, name, float(value))
        if self.step_us < 1 or self.delay_us < 1 or self.propagation_interval_us < 1:
            raise ValueError("numerical step and causal delay must be positive")
        if any(
            getattr(self, n) <= 0
            for n in (
                "activation_tau",
                "trace_tau",
                "inhibition_tau",
                "eligibility_tau",
                "stability_tau",
                "support_tau",
            )
        ):
            raise ValueError("time constants must be positive")
        if not 0 <= self.activation_floor < 1 or self.birth_weight > 1 or self.prune_weight >= 1:
            raise ValueError("invalid activation/weight threshold")
        if self.association_window_us < 1:
            raise ValueError("association_window_us must be positive")
        if any(
            getattr(self, k) > 1
            for k in (
                "propagation_activation_min",
                "consolidation_cap",
                "edge_birth_activation_product_min",
                "local_novelty_gain",
            )
        ):
            raise ValueError("optional activation and consolidation thresholds must lie in [0, 1]")
        if not 0 < self.novelty_touch_reference <= 1 or self.target_total_activation <= 0:
            raise ValueError("novelty reference and activation target must be positive")
        if not 0 < self.inhibition_saturation <= 1_000_000 or self.inhibition_propagation_min > 1_000_000:
            raise ValueError("invalid inhibition saturation or flux threshold")
        if not 0 < self.energy_capacity <= 1e12 or self.energy_starvation_death_us < 1:
            raise ValueError("energy capacity and starvation duration must be positive")
        if any(getattr(self, k) > 1e12 for k in ENERGY_DEFAULTS if k != "energy_starvation_death_us"):
            raise ValueError("experimental energy parameters exceed supported range")
        if self.attention_budget > 100000:
            raise ValueError("attention_budget must lie in [0, 100000]")
        if (
            not 1 <= self.spatial_dimensions <= 64
            or not 0 < self.spatial_radius <= 1e6
            or self.spatial_competition_rate > 1e6
        ):
            raise ValueError("invalid spatial dimensions, radius or competition rate")


@dataclass(frozen=True, slots=True)
class Stimulus:
    time_us: int
    channels: tuple[tuple[int, float], ...]
    intensity: float = 1.0
    bypass_attention: bool = False

    def __post_init__(self) -> None:
        if type(self.bypass_attention) is not bool:
            raise ValueError("attention bypass must be a boolean")
        object.__setattr__(self, "time_us", timestamp(self.time_us))
        object.__setattr__(self, "intensity", float(self.intensity))
        if not math.isfinite(self.intensity) or self.intensity < 0:
            raise ValueError("intensity must be finite and nonnegative")
        seen: set[int] = set()
        for channel, value in self.channels:
            if type(channel) is not int or not 0 <= channel < 2**32 or channel in seen:
                raise ValueError("channels must be unique unsigned 32-bit integers")
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("channel amplitude must lie in [0, 1]")
            seen.add(channel)
        object.__setattr__(self, "channels", tuple((channel, float(value)) for channel, value in self.channels))

    def to_dict(self) -> dict:
        return {
            "time_us": str(self.time_us),
            "channels": [list(c) for c in self.channels],
            "intensity": self.intensity,
        } | ({"bypass_attention": True} if self.bypass_attention else {})

    @classmethod
    def from_dict(cls, data: dict) -> Stimulus:
        if set(data) - {"time_us", "channels", "intensity", "bypass_attention"}:
            raise ValueError("unknown stimulus fields")
        return cls(
            timestamp(data["time_us"]),
            tuple((c, float(v)) for c, v in data["channels"]),
            float(data.get("intensity", 1.0)),
            data.get("bypass_attention", False),
        )
