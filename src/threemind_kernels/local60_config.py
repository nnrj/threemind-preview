"""Parameters owned by memory/6.0; defaults preserve the 2026-11-12 /6.0 baseline."""

from dataclasses import asdict, dataclass

from threemind_core import Config

from .decay60 import CURVES
from .mechanisms import FastTraceConfig, ShortTermConfig, number

CORE_KEYS = tuple(Config.__dataclass_fields__)


@dataclass(frozen=True, slots=True)
class _ContinuousParameters(Config):
    stp_enabled: bool = True
    stp_utilization: float = 0.5
    stp_recovery_tau_s: float = 0.8
    stp_active_tau_s: float = 0.003
    stp_facilitation_tau_s: float = 0.0
    fast_enabled: bool = True
    fast_tau_s: float = 2.0
    fast_learning_rate: float = 0.1
    fast_gain: float = 0.1
    context_enabled: bool = True
    context_tau_s: float = 1.0
    context_temperature: float = 1.0
    context_mix: float = 1.0

    def __post_init__(self):
        normalized = Config(**{key: getattr(self, key) for key in CORE_KEYS})
        for key in CORE_KEYS:
            object.__setattr__(self, key, getattr(normalized, key))
        for key in ("stp_enabled", "fast_enabled", "context_enabled"):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key} must be boolean")
        for key in self.__dataclass_fields__:
            if key not in CORE_KEYS and not key.endswith("_enabled"):
                object.__setattr__(self, key, number(getattr(self, key), key))
        self.short_term()
        self.fast_trace()
        number(self.context_tau_s, "context_tau_s", low=1e-6, high=1e9)
        number(self.context_temperature, "context_temperature", low=1e-6, high=1e6)
        number(self.context_mix, "context_mix", high=1.0)
        # Prevent unrepresentable traffic before entering partially mutated steps.
        number(self.propagation_rate, "candidate propagation_rate", high=1e9)
        number(self.propagation_rate * (self.propagation_interval_us / 1e6), "candidate emission gain", high=1e12)

    def base(self):
        return Config(**{key: getattr(self, key) for key in CORE_KEYS})

    def to_dict(self):
        return self.base().to_dict() | {key: value for key, value in asdict(self).items() if key not in CORE_KEYS}

    def short_term(self):
        return ShortTermConfig(
            self.stp_utilization, self.stp_recovery_tau_s, self.stp_active_tau_s, self.stp_facilitation_tau_s
        )

    def fast_trace(self):
        return FastTraceConfig(self.fast_tau_s, self.fast_learning_rate, self.fast_gain)


@dataclass(frozen=True, slots=True)
class _MemoryParameters(_ContinuousParameters):
    depletion_enabled: bool = True
    edge_consolidation_enabled: bool = True

    def __post_init__(self):
        _ContinuousParameters.__post_init__(self)
        for key in ("depletion_enabled", "edge_consolidation_enabled"):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key} must be boolean")


@dataclass(frozen=True, slots=True)
class _NoveltyParameters(_MemoryParameters):
    novelty_mode: str = "arrival-window"

    def __post_init__(self):
        normalized = _MemoryParameters(**{key: getattr(self, key) for key in _MemoryParameters.__dataclass_fields__})
        for key in _MemoryParameters.__dataclass_fields__:
            object.__setattr__(self, key, getattr(normalized, key))
        if self.novelty_mode not in ("immediate", "arrival-window"):
            raise ValueError("novelty_mode must be immediate or arrival-window")


BASE_KEYS = (
    "step_us",
    "delay_us",
    "propagation_interval_us",
    "quiescence_death_us",
    "node_prune_after_us",
    "activation_tau",
    "trace_tau",
    "inhibition_tau",
    "eligibility_tau",
    "stability_tau",
    "support_tau",
    "activation_decay_enabled",
    "trace_decay_enabled",
    "inhibition_decay_enabled",
    "eligibility_decay_enabled",
    "stability_decay_enabled",
    "support_decay_enabled",
    "propagation_rate",
    "direct_gain",
    "learning_rate",
    "birth_weight",
    "first_gain",
    "repeat_gain",
    "intensity_gain",
    "associative_gain",
    "stability_gain",
    "support_gain",
    "forgetting_rate",
    "inhibition_gain",
    "inhibition_diffusion_rate",
    "inhibition_response_gain",
    "activation_floor",
    "prune_weight",
    "prune_support",
    "plasticity",
    "inhibition",
    "seed",
    "propagation_activation_min",
    "consolidation_cap",
    "association_window_us",
    "edge_birth_policy",
    "edge_birth_activation_product_min",
    "local_novelty_gain",
    "novelty_touch_reference",
    "homeostasis_enabled",
    "target_total_activation",
    "inhibition_saturation",
    "inhibition_propagation_min",
    "max_nodes",
    "max_edges",
    "propagation_limit",
    "edge_adaptation_limit",
    "energy_simulation_enabled",
    "energy_initial_reserve",
    "energy_capacity",
    "energy_direct_cost",
    "energy_associative_cost",
    "energy_inhibition_cost",
    "energy_starvation_damage_enabled",
    "energy_maintenance_cost_per_node",
    "energy_maintenance_cost_per_edge",
    "energy_starvation_structural_decay",
    "attention_competition_enabled",
    "attention_budget",
    "spatial_embedding",
    "spatial_dimensions",
    "neighborhood_enabled",
    "spatial_radius",
    "spatial_competition_rate",
    "stp_enabled",
    "stp_utilization",
    "stp_recovery_tau_s",
    "stp_active_tau_s",
    "stp_facilitation_tau_s",
    "fast_enabled",
    "fast_tau_s",
    "fast_learning_rate",
    "fast_gain",
    "context_enabled",
    "context_tau_s",
    "context_temperature",
    "context_mix",
    "depletion_enabled",
    "edge_consolidation_enabled",
    "novelty_mode",
)
EXTRA_KEYS = (
    "consolidation_mode",
    "memory_growth_formula",
    "node_retention_mode",
    "retain_nodes",
    "dead_node_retention_us",
    "dormant_traces_enabled",
    "revival_enabled",
    "node_wake_threshold",
    "edge_wake_threshold",
    "memory_half_life_min_s",
    "memory_half_life_max_s",
    "memory_half_life_decay_rate",
    "memory_learning_gain",
    "memory_weight_learning_rate",
    "strong_fatigue_enabled",
    "strong_fatigue_tau_s",
    "strong_fatigue_gain",
    "dormant_prune_weight",
)
BOOL_KEYS = ("retain_nodes", "dormant_traces_enabled", "revival_enabled", "strong_fatigue_enabled")


@dataclass(frozen=True, slots=True)
class _RetentionParameters(_NoveltyParameters):
    consolidation_mode: str = "adaptive-half-life"
    memory_growth_formula: str = "log-saturating"
    node_retention_mode: str = "automatic"
    retain_nodes: bool = False
    dead_node_retention_us: int = 80_000_000
    dormant_traces_enabled: bool = False
    revival_enabled: bool = False
    node_wake_threshold: float | None = None
    edge_wake_threshold: float | None = None
    memory_half_life_min_s: float = 30.0
    memory_half_life_max_s: float = 2_592_000.0
    memory_half_life_decay_rate: float = 0.125
    memory_learning_gain: float = 0.2
    memory_weight_learning_rate: float = 0.55
    strong_fatigue_enabled: bool = True
    strong_fatigue_tau_s: float = 5.0
    strong_fatigue_gain: float = 1.0
    dormant_prune_weight: float = 1e-8

    def __post_init__(self):
        base = _NoveltyParameters(**{k: getattr(self, k) for k in BASE_KEYS})
        for k in BASE_KEYS:
            object.__setattr__(self, k, getattr(base, k))
        if self.propagation_limit is not None or self.edge_adaptation_limit is not None:
            raise ValueError("memory/6.0 does not support propagation/adaptation quotas; pace the host instead")
        for key, choices in (
            ("consolidation_mode", ("adaptive-half-life", "legacy-stability")),
            ("memory_growth_formula", ("log-saturating", "linear-saturating")),
            ("node_retention_mode", ("automatic", "manual")),
        ):
            if getattr(self, key) not in choices:
                raise ValueError(f"unknown {key}")
        for key in EXTRA_KEYS:
            value = getattr(self, key)
            if key in BOOL_KEYS:
                if type(value) is not bool:
                    raise ValueError(f"{key} must be boolean")
            elif key == "dead_node_retention_us":
                if type(value) is not int or not 1 <= value <= 2**53 - 1:
                    raise ValueError("dead_node_retention_us must be a positive safe integer")
            elif key.endswith("wake_threshold"):
                if value is not None:
                    object.__setattr__(self, key, number(value, key, low=1e-12, high=1e12))
            elif key not in ("consolidation_mode", "node_retention_mode", "memory_growth_formula"):
                object.__setattr__(self, key, number(value, key, high=1e12))
        if not 1e-6 <= self.memory_half_life_min_s < self.memory_half_life_max_s:
            raise ValueError("half-life bounds must satisfy 1e-6 <= min < max")
        if self.strong_fatigue_tau_s < 1e-6 or not 0 < self.dormant_prune_weight <= 1 or self.prune_support > 1:
            raise ValueError("invalid retention bounds")
        if self.dormant_traces_enabled and self.dormant_prune_weight >= self.prune_weight:
            raise ValueError("enabled dormancy requires dormant floor < prune_weight")
        if not self.dormant_traces_enabled:
            object.__setattr__(self, "revival_enabled", False)
        if self.revival_enabled and (self.node_wake_threshold is None or self.edge_wake_threshold is None):
            raise ValueError("awakening requires explicit positive node_wake_threshold and edge_wake_threshold")


@dataclass(frozen=True, slots=True)
class _LocalParameters(_RetentionParameters):
    propagation_mode: str = "local-events"
    propagation_phase: str = "aligned"
    arrival_mode: str = "sequential"
    reception_mode: str = "legacy-source"
    energy_model: str = "local-field"
    energy_distribution: str = "counter-random"
    energy_seed: int = 20261009
    energy_region_count: int = 16
    energy_node_capacity: float = 1.0

    def __post_init__(self):
        _RetentionParameters.__post_init__(self)
        for key, choices in (
            ("propagation_mode", ("local-events", "scan-control")),
            ("propagation_phase", ("aligned", "asynchronous")),
            ("arrival_mode", ("coincident", "sequential")),
            ("reception_mode", ("unified", "legacy-source")),
            ("energy_model", ("local-field", "global-ledger")),
            ("energy_distribution", ("counter-random", "stream-random")),
        ):
            if getattr(self, key) not in choices:
                raise ValueError(f"unknown {key}")
        for key, high in (("energy_seed", 2**53 - 1), ("energy_region_count", 4096)):
            if type(getattr(self, key)) is not int or not 0 <= getattr(self, key) <= high:
                raise ValueError(f"invalid {key}")
        if self.energy_region_count == 0:
            raise ValueError("energy_region_count must be positive")
        object.__setattr__(
            self,
            "energy_node_capacity",
            number(self.energy_node_capacity, "energy_node_capacity", low=1e-12, high=1e12),
        )
        if self.homeostasis_enabled or self.spatial_competition_rate > 0:
            raise ValueError("memory/6.0 does not implement global homeostasis/spatial competition")
        if self.edge_birth_policy != "co-stimulus":
            raise ValueError(
                "memory/6.0 requires delivered-contact co-stimulus birth; global temporal search is unsupported"
            )
        if self.attention_competition_enabled:
            raise ValueError("memory/6.0 does not rank external inputs globally; use an explicit peripheral")
        for key in ("step_us", "association_window_us", "attention_budget", "target_total_activation"):
            if getattr(self, key) != _RetentionParameters.__dataclass_fields__[key].default:
                raise ValueError(f"{key} is inactive metadata in memory/6.0 and cannot be changed")

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Local60Config(_LocalParameters):
    inflight_delivery: str = "address"
    decay_curve: str = "inverse-logarithmic"
    decay_transition_age: float = 10.0
    reinforcement_age_policy: str = "keep"
    retention_growth_enabled: bool = False
    retention_relaxation_enabled: bool = False
    structure_check_interval_us: int = 100_000
    signal_threshold_enabled: bool = True
    signal_threshold: float = 0.0004
    weight_gate_enabled: bool = False
    weight_gate: float = 0.008
    inhibitory_learning_enabled: bool = True
    # Historical field retained only as an explicitly enabled sender control.
    inhibition_sender_gate_enabled: bool = False

    def __post_init__(self):
        _LocalParameters.__post_init__(self)
        if self.inflight_delivery not in ("address", "same-birth"):
            raise ValueError("inflight_delivery must be address or same-birth")
        if self.decay_curve not in CURVES or self.reinforcement_age_policy not in ("keep", "reset"):
            raise ValueError("unknown decay curve or reinforcement age policy")
        if self.consolidation_mode != "adaptive-half-life" or self.node_retention_mode != "automatic":
            raise ValueError("/6.0 uses single-age persistent decay for both connections and nodes")
        for name in (
            "retention_growth_enabled",
            "retention_relaxation_enabled",
            "signal_threshold_enabled",
            "weight_gate_enabled",
            "inhibitory_learning_enabled",
            "inhibition_sender_gate_enabled",
        ):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be boolean")
        for name in ("signal_threshold", "weight_gate", "decay_transition_age"):
            object.__setattr__(self, name, number(getattr(self, name), name, high=1e12))
        if self.decay_transition_age <= 0 or self.weight_gate > 1:
            raise ValueError("invalid transition age or weight gate")
        if self.weight_gate_enabled and self.weight_gate < self.prune_weight:
            raise ValueError("weight gate must be at least the deletion threshold")
        if type(self.structure_check_interval_us) is not int or not 1 <= self.structure_check_interval_us < 2**53:
            raise ValueError("structure check interval must be a positive safe integer")
