//! Anonymous event-driven dynamics. No files, databases, Python or wall clock.
mod attention;
mod canonical;
mod energy;
mod resources;
mod restoration;
mod spatial;
use attention::{Attention, Modulation};
pub use canonical::{canonical_hash, parse_document};
use energy::{Cost, Energy, Supply};
use resources::{Candidate, Counter, Resources};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::cmp::Ordering;
use std::collections::{BTreeMap, BTreeSet, BinaryHeap, HashMap};

pub const LEGACY_SCHEMA: &str = "threemind.state/2";
pub const BUDGET_SCHEMA: &str = "threemind.state/3";
pub const ENERGY_SCHEMA: &str = "threemind.state/4";
pub const SCHEMA: &str = "threemind.state/6";
pub const LEGACY_DYNAMICS: &str = "threemind.causal/1";
pub const OPTIONAL_DYNAMICS: &str = "threemind.causal/2";
pub const BUDGET_DYNAMICS: &str = "threemind.causal/3";
pub const ENERGY_DYNAMICS: &str = "threemind.causal/4";
pub const ATTENTION_DYNAMICS: &str = "threemind.causal/5";
pub const SPATIAL_DYNAMICS: &str = "threemind.causal/6";
pub const DYNAMICS: &str = "threemind.causal/8";
const RESOURCE_VERSIONS: [&str; 5] = [
    BUDGET_DYNAMICS,
    ENERGY_DYNAMICS,
    ATTENTION_DYNAMICS,
    SPATIAL_DYNAMICS,
    DYNAMICS,
];
const ENERGY_VERSIONS: [&str; 4] = [
    ENERGY_DYNAMICS,
    ATTENTION_DYNAMICS,
    SPATIAL_DYNAMICS,
    DYNAMICS,
];
const ATTENTION_VERSIONS: [&str; 3] = [ATTENTION_DYNAMICS, SPATIAL_DYNAMICS, DYNAMICS];
const SPATIAL_VERSIONS: [&str; 2] = [SPATIAL_DYNAMICS, DYNAMICS];
fn state_schema(dynamics: &str) -> &str {
    match dynamics {
        DYNAMICS => SCHEMA,
        SPATIAL_DYNAMICS | ATTENTION_DYNAMICS => "threemind.state/5",
        ENERGY_DYNAMICS => ENERGY_SCHEMA,
        BUDGET_DYNAMICS => BUDGET_SCHEMA,
        LEGACY_DYNAMICS | OPTIONAL_DYNAMICS => LEGACY_SCHEMA,
        _ => "",
    }
}
fn restored_novelty(v: &f64) -> bool {
    *v == 0.018
}
fn restored_inhibition_min(v: &f64) -> bool {
    *v == 0.002
}
pub type Result<T> = std::result::Result<T, String>;

#[derive(Clone, Serialize, Deserialize, Debug, PartialEq)]
#[serde(default, deny_unknown_fields)]
pub struct Config {
    pub step_us: u64,
    pub delay_us: u64,
    pub propagation_interval_us: u64,
    pub quiescence_death_us: u64,
    pub node_prune_after_us: u64,
    pub eligibility_tau: f64,
    pub activation_decay_enabled: bool,
    pub trace_decay_enabled: bool,
    pub inhibition_decay_enabled: bool,
    pub eligibility_decay_enabled: bool,
    pub stability_decay_enabled: bool,
    pub support_decay_enabled: bool,
    pub activation_tau: f64,
    pub trace_tau: f64,
    pub inhibition_tau: f64,
    pub stability_tau: f64,
    pub support_tau: f64,
    pub propagation_rate: f64,
    pub direct_gain: f64,
    pub learning_rate: f64,
    pub birth_weight: f64,
    pub first_gain: f64,
    pub repeat_gain: f64,
    pub intensity_gain: f64,
    pub associative_gain: f64,
    pub stability_gain: f64,
    pub support_gain: f64,
    pub forgetting_rate: f64,
    pub inhibition_gain: f64,
    pub inhibition_diffusion_rate: f64,
    pub inhibition_response_gain: f64,
    pub activation_floor: f64,
    pub prune_weight: f64,
    pub prune_support: f64,
    pub plasticity: bool,
    pub inhibition: bool,
    pub seed: u64,
    #[serde(skip_serializing_if = "zero")]
    pub propagation_activation_min: f64,
    #[serde(skip_serializing_if = "default_cap")]
    pub consolidation_cap: f64,
    #[serde(skip_serializing_if = "default_window")]
    pub association_window_us: u64,
    #[serde(skip_serializing_if = "default_birth")]
    pub edge_birth_policy: String,
    #[serde(skip_serializing_if = "zero")]
    pub edge_birth_activation_product_min: f64,
    #[serde(skip_serializing_if = "restored_novelty")]
    pub local_novelty_gain: f64,
    #[serde(skip_serializing_if = "default_novelty")]
    pub novelty_touch_reference: f64,
    #[serde(skip_serializing_if = "is_false")]
    pub homeostasis_enabled: bool,
    #[serde(skip_serializing_if = "default_target")]
    pub target_total_activation: f64,
    #[serde(skip_serializing_if = "one")]
    pub inhibition_saturation: f64,
    #[serde(skip_serializing_if = "restored_inhibition_min")]
    pub inhibition_propagation_min: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_nodes: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_edges: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub propagation_limit: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub edge_adaptation_limit: Option<u64>,
    #[serde(skip_serializing_if = "is_false")]
    pub energy_simulation_enabled: bool,
    #[serde(skip_serializing_if = "one")]
    pub energy_initial_reserve: f64,
    #[serde(skip_serializing_if = "one")]
    pub energy_capacity: f64,
    #[serde(skip_serializing_if = "energy_direct_default")]
    pub energy_direct_cost: f64,
    #[serde(skip_serializing_if = "energy_associative_default")]
    pub energy_associative_cost: f64,
    #[serde(skip_serializing_if = "energy_inhibition_default")]
    pub energy_inhibition_cost: f64,
    #[serde(skip_serializing_if = "is_false")]
    pub irreversible_energy_death_enabled: bool,
    #[serde(skip_serializing_if = "energy_node_default")]
    pub energy_maintenance_cost_per_node: f64,
    #[serde(skip_serializing_if = "energy_edge_default")]
    pub energy_maintenance_cost_per_edge: f64,
    #[serde(skip_serializing_if = "energy_decay_default")]
    pub energy_starvation_structural_decay: f64,
    #[serde(skip_serializing_if = "energy_death_default")]
    pub energy_starvation_death_us: u64,
    #[serde(skip_serializing_if = "is_false")]
    pub attention_competition_enabled: bool,
    #[serde(skip_serializing_if = "attention_budget_default")]
    pub attention_budget: u64,
    #[serde(skip_serializing_if = "is_false")]
    pub spatial_embedding: bool,
    #[serde(skip_serializing_if = "spatial_dimensions_default")]
    pub spatial_dimensions: u64,
    #[serde(skip_serializing_if = "is_true")]
    pub neighborhood_enabled: bool,
    #[serde(skip_serializing_if = "spatial_radius_default")]
    pub spatial_radius: f64,
    #[serde(skip_serializing_if = "zero")]
    pub spatial_competition_rate: f64,
}
fn is_true(v: &bool) -> bool {
    *v
}
fn spatial_dimensions_default(v: &u64) -> bool {
    *v == 3
}
fn spatial_radius_default(v: &f64) -> bool {
    *v == 2.5
}
fn attention_budget_default(v: &u64) -> bool {
    *v == 28
}
fn energy_direct_default(v: &f64) -> bool {
    *v == 0.035
}
fn energy_associative_default(v: &f64) -> bool {
    *v == 0.020
}
fn energy_inhibition_default(v: &f64) -> bool {
    *v == 0.010
}
fn energy_node_default(v: &f64) -> bool {
    *v == 0.0002
}
fn energy_edge_default(v: &f64) -> bool {
    *v == 0.00004
}
fn energy_decay_default(v: &f64) -> bool {
    *v == 0.06
}
fn energy_death_default(v: &u64) -> bool {
    *v == 90_000_000
}
fn zero(v: &f64) -> bool {
    *v == 0.0
}
fn one(v: &f64) -> bool {
    *v == 1.0
}
fn default_cap(v: &f64) -> bool {
    *v == 0.42
}
fn default_window(v: &u64) -> bool {
    *v == 500_000
}
fn default_birth(v: &str) -> bool {
    v == "co-stimulus"
}
fn default_novelty(v: &f64) -> bool {
    *v == 0.2
}
fn default_target(v: &f64) -> bool {
    *v == 4.0
}
fn is_false(v: &bool) -> bool {
    !v
}
impl Default for Config {
    fn default() -> Self {
        Self {
            step_us: 10000,
            delay_us: 10000,
            propagation_interval_us: 100_000,
            quiescence_death_us: 1_000_000,
            node_prune_after_us: 80_000_000,
            eligibility_tau: -0.1 / 0.78_f64.ln(),
            activation_decay_enabled: true,
            trace_decay_enabled: true,
            inhibition_decay_enabled: true,
            eligibility_decay_enabled: true,
            stability_decay_enabled: true,
            support_decay_enabled: true,
            activation_tau: -0.1 / 0.72_f64.ln(),
            trace_tau: -0.1 / 0.82_f64.ln(),
            inhibition_tau: -0.1 / 0.65_f64.ln(),
            stability_tau: 0.1 / 0.00015,
            support_tau: 0.1 / 0.00015,
            propagation_rate: 4.2,
            direct_gain: 0.9,
            learning_rate: 0.055,
            birth_weight: 0.065,
            first_gain: 0.045,
            repeat_gain: 0.018,
            intensity_gain: 0.075,
            associative_gain: 0.01,
            stability_gain: 0.022,
            support_gain: 0.035,
            forgetting_rate: 0.025,
            inhibition_gain: 0.24,
            inhibition_diffusion_rate: 3.5,
            inhibition_response_gain: 2.0,
            activation_floor: 0.004,
            prune_weight: 0.008,
            prune_support: 0.006,
            plasticity: true,
            inhibition: true,
            seed: 20260724,
            propagation_activation_min: 0.0,
            consolidation_cap: 0.42,
            association_window_us: 500_000,
            edge_birth_policy: "co-stimulus".into(),
            edge_birth_activation_product_min: 0.0,
            local_novelty_gain: 0.018,
            novelty_touch_reference: 0.2,
            homeostasis_enabled: false,
            target_total_activation: 4.0,
            inhibition_saturation: 1.0,
            inhibition_propagation_min: 0.002,
            max_nodes: None,
            max_edges: None,
            propagation_limit: None,
            edge_adaptation_limit: None,
            energy_simulation_enabled: false,
            energy_initial_reserve: 1.0,
            energy_capacity: 1.0,
            energy_direct_cost: 0.035,
            energy_associative_cost: 0.020,
            energy_inhibition_cost: 0.010,
            irreversible_energy_death_enabled: false,
            energy_maintenance_cost_per_node: 0.0002,
            energy_maintenance_cost_per_edge: 0.00004,
            energy_starvation_structural_decay: 0.06,
            energy_starvation_death_us: 90_000_000,
            attention_competition_enabled: false,
            attention_budget: 28,
            spatial_embedding: false,
            spatial_dimensions: 3,
            neighborhood_enabled: true,
            spatial_radius: 2.5,
            spatial_competition_rate: 0.0,
        }
    }
}
impl Config {
    pub fn has_spatial_changes(&self) -> bool {
        self.spatial_embedding
            || self.spatial_dimensions != 3
            || !self.neighborhood_enabled
            || self.spatial_radius != 2.5
            || self.spatial_competition_rate != 0.0
    }
    pub fn has_attention_changes(&self) -> bool {
        self.attention_competition_enabled || self.attention_budget != 28
    }
    pub fn energy_parameters(&self) -> Value {
        json!({"energy_simulation_enabled":self.energy_simulation_enabled,"energy_initial_reserve":self.energy_initial_reserve,
            "energy_capacity":self.energy_capacity,"energy_direct_cost":self.energy_direct_cost,"energy_associative_cost":self.energy_associative_cost,
            "energy_inhibition_cost":self.energy_inhibition_cost,"irreversible_energy_death_enabled":self.irreversible_energy_death_enabled,
            "energy_maintenance_cost_per_node":self.energy_maintenance_cost_per_node,"energy_maintenance_cost_per_edge":self.energy_maintenance_cost_per_edge,
            "energy_starvation_structural_decay":self.energy_starvation_structural_decay,"energy_starvation_death_us":self.energy_starvation_death_us})
    }
    pub fn has_energy_changes(&self) -> bool {
        self.energy_parameters() != Self::default().energy_parameters()
    }
    pub fn has_budget_limits(&self) -> bool {
        self.max_nodes.is_some()
            || self.max_edges.is_some()
            || self.propagation_limit.is_some()
            || self.edge_adaptation_limit.is_some()
    }
    pub fn has_optional_changes(&self) -> bool {
        !zero(&self.propagation_activation_min)
            || !default_cap(&self.consolidation_cap)
            || !default_window(&self.association_window_us)
            || !default_birth(&self.edge_birth_policy)
            || !zero(&self.edge_birth_activation_product_min)
            || !restored_novelty(&self.local_novelty_gain)
            || !default_novelty(&self.novelty_touch_reference)
            || self.homeostasis_enabled
            || !default_target(&self.target_total_activation)
            || !one(&self.inhibition_saturation)
            || !restored_inhibition_min(&self.inhibition_propagation_min)
    }
    pub fn validate(&self) -> Result<()> {
        if !(1..=64).contains(&self.spatial_dimensions)
            || !self.spatial_radius.is_finite()
            || self.spatial_radius <= 0.0
            || self.spatial_radius > 1e6
            || !self.spatial_competition_rate.is_finite()
            || !(0.0..=1e6).contains(&self.spatial_competition_rate)
        {
            return Err("invalid spatial dimensions, radius or competition rate".into());
        }
        if self.attention_budget > 100000 {
            return Err("attention_budget must lie in [0, 100000]".into());
        }
        if self.energy_capacity <= 0.0
            || self.energy_starvation_death_us == 0
            || self.energy_starvation_death_us > (1 << 53) - 1
            || self
                .energy_parameters()
                .as_object()
                .unwrap()
                .iter()
                .any(|(k, v)| {
                    k != "energy_starvation_death_us" && v.as_f64().is_some_and(|v| v > 1e12)
                })
        {
            return Err("invalid energy capacity, duration or cost".into());
        }
        if [
            self.max_nodes,
            self.max_edges,
            self.propagation_limit,
            self.edge_adaptation_limit,
        ]
        .iter()
        .flatten()
        .any(|v| *v > (1 << 53) - 1)
        {
            return Err("invalid resource budget".into());
        }
        if self.step_us == 0
            || self.delay_us == 0
            || self.propagation_interval_us == 0
            || self.propagation_interval_us > (1 << 53) - 1
            || self.quiescence_death_us > (1 << 53) - 1
            || self.node_prune_after_us > (1 << 53) - 1
            || self.step_us > (1 << 53) - 1
            || self.delay_us > (1 << 53) - 1
            || self.seed > (1 << 53) - 1
            || self.association_window_us == 0
            || self.association_window_us > (1 << 53) - 1
        {
            return Err("invalid integer configuration".into());
        }
        for (k, v) in serde_json::to_value(self).unwrap().as_object().unwrap() {
            if v.is_null() {
                return Err(format!("nonfinite {k}"));
            }
            if let Some(v) = v.as_f64() {
                if !v.is_finite() || v < 0.0 {
                    return Err(format!("invalid {k}"));
                }
            }
        }
        if [
            self.activation_tau,
            self.trace_tau,
            self.inhibition_tau,
            self.eligibility_tau,
            self.stability_tau,
            self.support_tau,
        ]
        .iter()
        .any(|x| *x <= 0.0)
            || self.activation_floor < 0.0
            || self.activation_floor >= 1.0
            || self.birth_weight > 1.0
            || self.prune_weight >= 1.0
        {
            return Err("invalid timescale or threshold".into());
        }
        if !["co-stimulus", "temporal-association"].contains(&self.edge_birth_policy.as_str())
            || [
                self.propagation_activation_min,
                self.consolidation_cap,
                self.edge_birth_activation_product_min,
                self.local_novelty_gain,
            ]
            .iter()
            .any(|v| *v > 1.0)
            || self.novelty_touch_reference <= 0.0
            || self.novelty_touch_reference > 1.0
            || self.target_total_activation <= 0.0
            || self.inhibition_saturation <= 0.0
            || self.inhibition_saturation > 1_000_000.0
            || self.inhibition_propagation_min > 1_000_000.0
        {
            return Err("invalid optional causal mechanism".into());
        }
        Ok(())
    }
}

#[derive(Clone, Serialize, Deserialize, Debug)]
#[serde(deny_unknown_fields)]
pub struct Stimulus {
    pub time_us: String,
    pub channels: Vec<(u32, f64)>,
    pub intensity: f64,
    #[serde(default, skip_serializing_if = "is_false")]
    pub bypass_attention: bool,
}
impl Stimulus {
    pub fn time(&self) -> Result<u128> {
        parse_time(&self.time_us)
    }
    pub fn validate(&self) -> Result<()> {
        self.time()?;
        let mut seen = BTreeSet::new();
        if !self.intensity.is_finite() || self.intensity < 0.0 {
            return Err("invalid intensity".into());
        }
        for (n, v) in &self.channels {
            if !seen.insert(n) || !v.is_finite() || !(0.0..=1.0).contains(v) {
                return Err("invalid channels".into());
            }
        }
        Ok(())
    }
}
pub fn parse_time(s: &str) -> Result<u128> {
    if s.is_empty() || !s.bytes().all(|c| c.is_ascii_digit()) {
        return Err("time must be unsigned decimal microseconds".into());
    }
    s.parse()
        .map_err(|_| "time exceeds unsigned 128-bit range".into())
}

#[derive(Clone, Serialize, Deserialize, Debug)]
#[serde(deny_unknown_fields)]
pub struct Node {
    pub id: u64,
    pub channel: u32,
    pub activation: f64,
    pub inhibition: f64,
    pub trace: f64,
    pub support: f64,
    pub stability: f64,
    pub direct: f64,
    pub associative: f64,
    pub touches: u64,
    pub last_touch_us: String,
    pub birth_us: String,
    pub local_plasticity: f64,
    pub pending_inhibition: f64,
    pub generated_inhibition: f64,
}
#[derive(Clone, Serialize, Deserialize, Debug)]
#[serde(deny_unknown_fields)]
pub struct Edge {
    pub source: u64,
    pub target: u64,
    pub weight: f64,
    pub stability: f64,
    pub eligibility: f64,
    pub touches: u64,
    pub birth_us: String,
    pub last_touch_us: String,
}
#[derive(Clone, Serialize, Deserialize, Debug)]
pub struct SavedEvent {
    pub time_us: String,
    pub id: u64,
    pub kind: String,
    pub payload: Value,
}
#[derive(Clone, Debug)]
struct Event {
    time: u128,
    id: u64,
    kind: String,
    payload: Value,
}
impl PartialEq for Event {
    fn eq(&self, o: &Self) -> bool {
        (self.time, self.id) == (o.time, o.id)
    }
}
impl Eq for Event {}
impl PartialOrd for Event {
    fn partial_cmp(&self, o: &Self) -> Option<Ordering> {
        Some(self.cmp(o))
    }
}
impl Ord for Event {
    fn cmp(&self, o: &Self) -> Ordering {
        (o.time, o.id).cmp(&(self.time, self.id))
    }
}

#[derive(Clone, Serialize, Deserialize, Debug)]
#[serde(deny_unknown_fields)]
pub struct State {
    pub schema: String,
    pub dynamics: String,
    pub config: Config,
    pub time_us: String,
    pub state_time_us: String,
    pub next_step_us: String,
    pub next_propagation_us: String,
    pub quiet_since_us: Option<String>,
    pub transport: BTreeMap<String, f64>,
    pub traversed: Vec<(u64, u64)>,
    pub sequence: u64,
    pub next_event: u64,
    pub next_node: u64,
    pub sources_open: bool,
    pub life: String,
    pub nodes: Vec<Node>,
    pub edges: Vec<Edge>,
    pub queue: Vec<SavedEvent>,
    pub silenced_nodes: Vec<u64>,
    pub silenced_edges: Vec<(u64, u64)>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub resources: Option<Resources>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub energy: Option<Energy>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub attention: Option<Attention>,
}

pub struct Engine {
    pub config: Config,
    dynamics: String,
    resources: Resources,
    energy: Energy,
    attention: Attention,
    spatial_points: HashMap<u64, Vec<f64>>,
    pub time: u128,
    state_time: u128,
    next_step: u128,
    next_propagation: u128,
    quiet_since: Option<u128>,
    transport: BTreeMap<String, f64>,
    traversed: BTreeSet<(u64, u64)>,
    pub sequence: u64,
    next_event: u64,
    next_node: u64,
    pub sources_open: bool,
    pub life: String,
    // Dense numeric rows; indices are rebuilt only after actual topology deletion.
    nodes: Vec<Node>,
    edges: Vec<Edge>,
    node_index: HashMap<u64, usize>,
    edge_index: HashMap<(u64, u64), usize>,
    receptors: HashMap<u32, u64>,
    outgoing: BTreeMap<u64, BTreeSet<u64>>,
    incident: BTreeMap<u64, BTreeSet<u64>>,
    queue: BinaryHeap<Event>,
    silenced_nodes: BTreeSet<u64>,
    silenced_edges: BTreeSet<(u64, u64)>,
}
impl Engine {
    pub fn new(config: Config) -> Result<Self> {
        config.validate()?;
        Ok(Self {
            next_step: config.step_us as u128,
            next_propagation: config.propagation_interval_us as u128,
            quiet_since: None,
            transport: ["sent", "received", "activated", "discarded"]
                .into_iter()
                .map(|s| (s.into(), 0.0))
                .collect(),
            traversed: BTreeSet::new(),
            energy: Energy::initial(&config, 0),
            attention: Attention::new(0),
            spatial_points: HashMap::new(),
            config,
            dynamics: DYNAMICS.into(),
            resources: Resources::default(),
            time: 0,
            state_time: 0,
            sequence: 0,
            next_event: 0,
            next_node: 1,
            sources_open: true,
            life: "waiting".into(),
            nodes: vec![],
            edges: vec![],
            node_index: HashMap::new(),
            edge_index: HashMap::new(),
            receptors: HashMap::new(),
            outgoing: BTreeMap::new(),
            incident: BTreeMap::new(),
            queue: BinaryHeap::new(),
            silenced_nodes: BTreeSet::new(),
            silenced_edges: BTreeSet::new(),
        })
    }
    fn event(&mut self, time: u128, kind: &str, payload: Value) {
        self.next_event += 1;
        self.queue.push(Event {
            time,
            id: self.next_event,
            kind: kind.into(),
            payload,
        });
    }
    pub fn inject(&mut self, stimulus: Stimulus) -> Result<u64> {
        stimulus.validate()?;
        let time = stimulus.time()?;
        if self.life == "dead" || !self.sources_open || time < self.time {
            return Err("dead, closed or late input".into());
        }
        if stimulus.bypass_attention && self.dynamics != DYNAMICS {
            self.relax(self.time);
            self.upgrade_attention(&self.config.clone());
            self.dynamics = DYNAMICS.into();
        }
        self.event(time, "stimulus", serde_json::to_value(stimulus).unwrap());
        Ok(self.next_event)
    }
    pub fn reconfigure(&mut self, config: Config) -> Result<()> {
        config.validate()?;
        if config.step_us != self.config.step_us
            || config.seed != self.config.seed
            || config.energy_initial_reserve != self.config.energy_initial_reserve
        {
            return Err(
                "step_us, seed and energy_initial_reserve are immutable after creation".into(),
            );
        }
        if config == self.config {
            return Ok(());
        }
        if self.life == "dead" {
            return Err("a dead instance requires an explicit new birth".into());
        }
        // The old parameters govern all elapsed time. In-flight events and the
        // fixed lattice retain their phase; new settings govern future work.
        self.relax(self.time);
        if config.has_spatial_changes() && !SPATIAL_VERSIONS.contains(&self.dynamics.as_str()) {
            self.upgrade_attention(&config);
            self.dynamics = DYNAMICS.into();
        } else if config.has_attention_changes()
            && !ATTENTION_VERSIONS.contains(&self.dynamics.as_str())
        {
            self.upgrade_attention(&config);
        } else if config.has_energy_changes() && !ENERGY_VERSIONS.contains(&self.dynamics.as_str())
        {
            if self.dynamics != BUDGET_DYNAMICS {
                self.resources = Resources {
                    since_us: self.time.to_string(),
                    ..Resources::default()
                };
            }
            self.dynamics = ENERGY_DYNAMICS.into();
            self.energy = Energy::initial(&config, self.time);
        } else if config.has_budget_limits() && !RESOURCE_VERSIONS.contains(&self.dynamics.as_str())
        {
            self.dynamics = BUDGET_DYNAMICS.into();
            self.resources = Resources {
                since_us: self.time.to_string(),
                ..Resources::default()
            };
        } else if config.has_optional_changes() && self.dynamics == LEGACY_DYNAMICS {
            self.dynamics = OPTIONAL_DYNAMICS.into();
        }
        if ENERGY_VERSIONS.contains(&self.dynamics.as_str()) {
            self.energy.resize(config.energy_capacity);
            if (
                self.config.energy_simulation_enabled,
                self.config.irreversible_energy_death_enabled,
            ) != (
                config.energy_simulation_enabled,
                config.irreversible_energy_death_enabled,
            ) {
                self.energy.starved_since_us = None;
                self.energy.last_settlement_us = self.time.to_string();
                self.energy.last_maintenance_deficit = 0.0;
            }
        }
        if (
            self.config.spatial_embedding,
            self.config.spatial_dimensions,
        ) != (config.spatial_embedding, config.spatial_dimensions)
        {
            self.spatial_points.clear();
        }
        if self.config.propagation_interval_us != config.propagation_interval_us {
            self.next_propagation = self.time + config.propagation_interval_us as u128;
            self.resources.adaptation_period_us = (self.time
                / config.propagation_interval_us as u128
                * config.propagation_interval_us as u128)
                .to_string();
            self.resources.adaptations_used = 0;
        }
        if self.config.inhibition && !config.inhibition {
            for n in &mut self.nodes {
                n.inhibition = 0.0;
                n.pending_inhibition = 0.0;
                n.generated_inhibition = 0.0;
            }
            self.queue.retain(|e| e.kind != "inhibition");
        }
        self.config = config;
        self.sync_spatial();
        for n in &mut self.nodes {
            n.inhibition = n.inhibition.min(self.config.inhibition_saturation);
        }
        self.homeostasis();
        self.lifecycle();
        self.sequence += 1;
        Ok(())
    }
    fn upgrade_attention(&mut self, config: &Config) {
        if ATTENTION_VERSIONS.contains(&self.dynamics.as_str()) {
            return;
        }
        if !RESOURCE_VERSIONS.contains(&self.dynamics.as_str()) {
            self.resources = Resources {
                since_us: self.time.to_string(),
                ..Resources::default()
            };
        }
        if !ENERGY_VERSIONS.contains(&self.dynamics.as_str()) {
            self.energy = Energy::initial(config, self.time);
        }
        self.attention = Attention::new(self.time);
        self.dynamics = ATTENTION_DYNAMICS.into();
    }
    pub fn modulate_input(&mut self, time: u128, adjustment: Value) -> Result<u64> {
        let payload: Modulation = serde_json::from_value(adjustment).map_err(|e| e.to_string())?;
        payload.validate()?;
        if self.life == "dead"
            || !self.sources_open
            || time < self.time
            || time.checked_add(payload.ttl_us as u128).is_none()
        {
            return Err("dead instance or invalid modulation timestamp".into());
        }
        if !ATTENTION_VERSIONS.contains(&self.dynamics.as_str()) {
            self.relax(self.time);
            self.upgrade_attention(&self.config.clone());
        }
        self.event(time, "modulation", serde_json::to_value(payload).unwrap());
        Ok(self.next_event)
    }
    pub fn supply_energy(&mut self, time: u128, amount: f64, source: String) -> Result<u64> {
        if self.life == "dead"
            || !self.sources_open
            || !self.config.energy_simulation_enabled
            || time < self.time
        {
            return Err("dead, energy-disabled or late supply".into());
        }
        let supply = Supply { amount, source };
        supply.validate()?;
        self.event(time, "energy", serde_json::to_value(supply).unwrap());
        Ok(self.next_event)
    }
    fn maintain_energy(&mut self, when: u128, duration_us: u128) {
        let c = &self.config;
        if !(c.energy_simulation_enabled && c.irreversible_energy_death_enabled) {
            return;
        }
        let duration =
            self.energy
                .maintain(when, duration_us, self.nodes.len(), self.edges.len(), c);
        if duration > 0.0 && c.energy_starvation_structural_decay > 0.0 {
            let factor = (-c.energy_starvation_structural_decay * duration).exp();
            for n in &mut self.nodes {
                n.support *= factor;
            }
            for e in &mut self.edges {
                e.weight *= factor;
                e.stability *= factor;
            }
        }
    }
    fn energy_deadline(&self) -> Option<u128> {
        self.energy.starved_since_us.as_ref().map(|since| {
            self.time.max(
                parse_time(since)
                    .unwrap()
                    .saturating_add(self.config.energy_starvation_death_us as u128),
            )
        })
    }
    fn energy_lifecycle(&mut self) {
        let c = &self.config;
        if self.life == "dead" {
            return;
        }
        if c.energy_simulation_enabled
            && c.irreversible_energy_death_enabled
            && self.energy.reserve == 0.0
            && !(self.nodes.is_empty() && self.edges.is_empty())
        {
            if self.energy.starved_since_us.is_none() {
                self.energy.starved_since_us = Some(self.time.to_string());
            }
            if self.time - parse_time(self.energy.starved_since_us.as_ref().unwrap()).unwrap()
                >= c.energy_starvation_death_us as u128
            {
                for n in &mut self.nodes {
                    n.activation = 0.0;
                    n.direct = 0.0;
                    n.associative = 0.0;
                    n.inhibition = 0.0;
                    n.trace = 0.0;
                }
                self.queue.clear();
                self.sources_open = false;
                self.life = "dead".into();
                self.energy.death_us = Some(self.time.to_string());
            }
        } else {
            self.energy.starved_since_us = None;
        }
    }
    pub fn close_inputs(&mut self) {
        self.sources_open = false;
        self.sequence += 1;
        self.lifecycle();
    }
    fn sync_spatial(&mut self) {
        if !self.config.spatial_embedding {
            self.spatial_points.clear();
            return;
        }
        self.spatial_points
            .retain(|id, _| self.node_index.contains_key(id));
        for node in &self.nodes {
            self.spatial_points
                .entry(node.id)
                .or_insert_with(|| spatial::position(&self.config, node.id));
        }
    }
    fn reindex(&mut self) {
        self.node_index.clear();
        self.edge_index.clear();
        self.receptors.clear();
        self.outgoing.clear();
        self.incident.clear();
        for (i, n) in self.nodes.iter().enumerate() {
            self.node_index.insert(n.id, i);
            self.receptors.insert(n.channel, n.id);
        }
        for (i, e) in self.edges.iter().enumerate() {
            self.edge_index.insert((e.source, e.target), i);
            self.outgoing.entry(e.source).or_default().insert(e.target);
            self.incident.entry(e.source).or_default().insert(e.target);
            self.incident.entry(e.target).or_default().insert(e.source);
        }
        self.sync_spatial();
    }
    pub fn restore(state: State) -> Result<Self> {
        if !SPATIAL_VERSIONS.contains(&state.dynamics.as_str())
            && state.config.has_spatial_changes()
        {
            return Err("legacy dynamics cannot contain causal spatial rules".into());
        }
        if state.dynamics != DYNAMICS {
            return Err("Older dynamics are read-only; create a new causal/8 consciousness".into());
        }
        let expected_schema = state_schema(&state.dynamics);
        if expected_schema.is_empty() || state.schema != expected_schema {
            return Err("unsupported state version".into());
        }
        if state.dynamics == LEGACY_DYNAMICS && state.config.has_optional_changes() {
            return Err("causal/1 cannot contain causal/2 mechanisms".into());
        }
        if !RESOURCE_VERSIONS.contains(&state.dynamics.as_str())
            && (state.config.has_budget_limits() || state.resources.is_some())
        {
            return Err("resource budgets require causal/3".into());
        }
        if !ENERGY_VERSIONS.contains(&state.dynamics.as_str())
            && (state.config.has_energy_changes() || state.energy.is_some())
        {
            return Err("energy accounting requires causal/4".into());
        }
        if !ATTENTION_VERSIONS.contains(&state.dynamics.as_str())
            && (state.config.has_attention_changes() || state.attention.is_some())
        {
            return Err("input selection requires causal/5".into());
        }
        let mut e = Self::new(state.config)?;
        e.dynamics = state.dynamics;
        e.time = parse_time(&state.time_us)?;
        e.state_time = parse_time(&state.state_time_us)?;
        e.next_step = parse_time(&state.next_step_us)?;
        if e.state_time > e.time || e.next_step <= e.state_time {
            return Err("invalid numerical phase".into());
        }
        if RESOURCE_VERSIONS.contains(&e.dynamics.as_str()) {
            e.resources = state.resources.ok_or("missing resource accounting")?;
            e.resources
                .validate(e.time, e.config.propagation_interval_us)?;
        }
        if ENERGY_VERSIONS.contains(&e.dynamics.as_str()) {
            e.energy = state.energy.ok_or("missing energy accounting")?;
            e.energy.validate(e.time, &e.config)?;
        }
        if ATTENTION_VERSIONS.contains(&e.dynamics.as_str()) {
            e.attention = state.attention.ok_or("missing input selection state")?;
            e.attention.validate(e.time)?;
        }
        if !["waiting", "active", "dead"].contains(&state.life.as_str()) {
            return Err("invalid lifecycle".into());
        }
        e.sequence = state.sequence;
        e.next_event = state.next_event;
        e.next_node = state.next_node;
        e.sources_open = state.sources_open;
        e.life = state.life;
        e.next_propagation = parse_time(&state.next_propagation_us)?;
        e.quiet_since = state
            .quiet_since_us
            .as_deref()
            .map(parse_time)
            .transpose()?;
        if e.next_propagation <= e.state_time || e.quiet_since.is_some_and(|t| t > e.state_time) {
            return Err("invalid propagation or quiescence clock".into());
        }
        e.transport = state.transport;
        if e.transport.len() != 4
            || ["sent", "received", "activated", "discarded"]
                .iter()
                .any(|k| {
                    !e.transport
                        .get(*k)
                        .is_some_and(|v| v.is_finite() && *v >= 0.0)
                })
        {
            return Err("invalid transport accounting".into());
        }
        e.traversed = state.traversed.into_iter().collect();
        if e.next_node == 0
            || [e.sequence, e.next_event, e.next_node]
                .iter()
                .any(|v| *v >= 1 << 63)
        {
            return Err("invalid state counter".into());
        }
        let mut ids = BTreeSet::new();
        let mut channels = BTreeSet::new();
        for n in &state.nodes {
            if n.id == 0
                || n.id >= e.next_node
                || !ids.insert(n.id)
                || !channels.insert(n.channel)
                || [
                    n.activation,
                    n.trace,
                    n.support,
                    n.stability,
                    n.local_plasticity,
                ]
                .iter()
                .any(|v| !v.is_finite() || !(0.0..=1.00000000000001).contains(v))
                || [
                    n.direct,
                    n.associative,
                    n.pending_inhibition,
                    n.generated_inhibition,
                ]
                .iter()
                .any(|v| !v.is_finite() || *v < 0.0)
                || !n.inhibition.is_finite()
                || n.inhibition < 0.0
                || n.inhibition > e.config.inhibition_saturation + 1e-14
            {
                return Err("invalid node state".into());
            }
            if parse_time(&n.birth_us)? > parse_time(&n.last_touch_us)?
                || parse_time(&n.last_touch_us)? > e.state_time
                || n.touches >= 1 << 63
            {
                return Err("invalid node history".into());
            }
        }
        let mut keys = BTreeSet::new();
        for edge in &state.edges {
            if edge.source == edge.target
                || !ids.contains(&edge.source)
                || !ids.contains(&edge.target)
                || !keys.insert((edge.source, edge.target))
                || [edge.weight, edge.stability, edge.eligibility]
                    .iter()
                    .any(|v| !v.is_finite() || !(0.0..=1.0).contains(v))
            {
                return Err("invalid edge state".into());
            }
            if parse_time(&edge.birth_us)? > parse_time(&edge.last_touch_us)?
                || parse_time(&edge.last_touch_us)? > e.state_time
                || edge.touches >= 1 << 63
            {
                return Err("invalid edge history".into());
            }
        }
        let mut events = BTreeSet::new();
        for event in state.queue {
            let t = parse_time(&event.time_us)?;
            if t < e.time || event.id == 0 || event.id > e.next_event || !events.insert(event.id) {
                return Err("invalid event order".into());
            }
            if event.kind == "stimulus" {
                if event.payload.get("bypass_attention").is_some() && e.dynamics != DYNAMICS {
                    return Err("per-frame attention bypass requires causal/7".into());
                }
                let s = serde_json::from_value::<Stimulus>(event.payload.clone())
                    .map_err(|x| x.to_string())?;
                s.validate()?;
                if s.time()? != t {
                    return Err("stimulus timestamp differs from envelope".into());
                }
            } else if event.kind == "energy" {
                if !ENERGY_VERSIONS.contains(&e.dynamics.as_str()) {
                    return Err("energy supply requires causal/4".into());
                }
                serde_json::from_value::<Supply>(event.payload.clone())
                    .map_err(|e| e.to_string())?
                    .validate()?;
            } else if event.kind == "modulation" {
                if !ATTENTION_VERSIONS.contains(&e.dynamics.as_str())
                    || event.payload.as_object().is_none_or(|v| v.len() != 5)
                {
                    return Err("invalid pending input modulation".into());
                }
                let payload: Modulation =
                    serde_json::from_value(event.payload.clone()).map_err(|x| x.to_string())?;
                payload.validate()?;
            } else if event.kind == "signal" || event.kind == "inhibition" {
                let values: Vec<(u64, f64)> =
                    serde_json::from_value(event.payload["values"].clone())
                        .map_err(|x| x.to_string())?;
                if values.iter().any(|(_, v)| !v.is_finite() || *v < 0.0) {
                    return Err("invalid pending signal".into());
                }
            } else {
                return Err("unknown event kind".into());
            }
            e.queue.push(Event {
                time: t,
                id: event.id,
                kind: event.kind,
                payload: event.payload,
            });
        }
        e.nodes = state.nodes;
        e.nodes.sort_by_key(|n| n.id);
        e.edges = state.edges;
        e.silenced_nodes = state.silenced_nodes.into_iter().collect();
        e.silenced_edges = state.silenced_edges.into_iter().collect();
        if e.energy
            .death_us
            .as_ref()
            .is_some_and(|when| e.life != "dead" || *when != e.time.to_string())
        {
            return Err("invalid energy death boundary".into());
        }
        e.reindex();
        if e.traversed
            .iter()
            .any(|key| !e.edge_index.contains_key(key))
        {
            return Err("invalid traversed edge".into());
        }
        Ok(e)
    }
    pub fn capture(&self) -> State {
        let mut nodes = self.nodes.clone();
        nodes.sort_by_key(|n| n.id);
        let mut edges = self.edges.clone();
        edges.sort_by_key(|e| (e.source, e.target));
        let mut queue: Vec<_> = self
            .queue
            .iter()
            .map(|q| SavedEvent {
                time_us: q.time.to_string(),
                id: q.id,
                kind: q.kind.clone(),
                payload: q.payload.clone(),
            })
            .collect();
        queue.sort_by_key(|q| (parse_time(&q.time_us).unwrap(), q.id));
        State {
            schema: state_schema(&self.dynamics).into(),
            dynamics: self.dynamics.clone(),
            config: self.config.clone(),
            time_us: self.time.to_string(),
            state_time_us: self.state_time.to_string(),
            next_step_us: self.next_step.to_string(),
            next_propagation_us: self.next_propagation.to_string(),
            quiet_since_us: self.quiet_since.map(|t| t.to_string()),
            transport: self.transport.clone(),
            traversed: self.traversed.iter().copied().collect(),
            sequence: self.sequence,
            next_event: self.next_event,
            next_node: self.next_node,
            sources_open: self.sources_open,
            life: self.life.clone(),
            nodes,
            edges,
            queue,
            silenced_nodes: self.silenced_nodes.iter().copied().collect(),
            silenced_edges: self.silenced_edges.iter().copied().collect(),
            resources: if RESOURCE_VERSIONS.contains(&self.dynamics.as_str()) {
                Some(self.resources.clone())
            } else {
                None
            },
            energy: if ENERGY_VERSIONS.contains(&self.dynamics.as_str()) {
                Some(self.energy.clone())
            } else {
                None
            },
            attention: if ATTENTION_VERSIONS.contains(&self.dynamics.as_str()) {
                Some(self.attention.clone())
            } else {
                None
            },
        }
    }
    pub fn advance(&mut self, target: u128, record: bool) -> Result<Vec<Value>> {
        self.advance_impl(target, record, false)
    }
    pub fn advance_inputs(&mut self, target: u128) -> Result<Vec<Value>> {
        self.advance_impl(target, true, true)
    }
    pub fn is_empty(&self) -> bool {
        self.nodes.is_empty() && self.queue.is_empty()
    }
    fn advance_impl(
        &mut self,
        target: u128,
        record: bool,
        inputs_only: bool,
    ) -> Result<Vec<Value>> {
        if target < self.time {
            return Err("time cannot go backwards".into());
        }
        if target > u128::MAX - self.config.step_us as u128 - self.config.delay_us as u128 {
            return Err("time too close to representational limit".into());
        }
        let mut records = vec![];
        while self.life != "dead" {
            let mut event_time;
            if self.nodes.is_empty() && self.life == "waiting" {
                if self.queue.peek().is_none_or(|q| q.time > target) {
                    self.time = target;
                    self.state_time = target;
                    self.next_step =
                        (target / self.config.step_us as u128 + 1) * self.config.step_us as u128;
                    let period = self.config.propagation_interval_us as u128;
                    if self.next_propagation <= target {
                        self.next_propagation +=
                            ((target - self.next_propagation) / period + 1) * period;
                    }
                    break;
                }
                event_time = self.queue.peek().unwrap().time;
                self.next_step = self.next_step.max(
                    event_time.div_ceil(self.config.step_us as u128) * self.config.step_us as u128,
                );
                if self.next_propagation < event_time {
                    let period = self.config.propagation_interval_us as u128;
                    self.next_propagation +=
                        (event_time - self.next_propagation).div_ceil(period) * period;
                }
            } else {
                event_time = self.next_step.min(self.next_propagation);
            }
            if let Some(since) = self.quiet_since {
                event_time =
                    event_time.min(since.saturating_add(self.config.quiescence_death_us as u128));
            }
            if let Some(q) = self.queue.peek() {
                event_time = event_time.min(q.time);
            }
            if let Some(deadline) = self.energy_deadline() {
                event_time = event_time.min(deadline);
            }
            if event_time > target {
                break;
            }
            self.relax(event_time);
            self.time = event_time;
            let baseline: HashMap<_, _> = self.nodes.iter().map(|n| (n.id, n.activation)).collect();
            while self.queue.peek().is_some_and(|q| q.time == event_time) {
                let mut q = self.queue.pop().unwrap();
                let mut selection = None;
                if q.kind == "stimulus" {
                    let mut stimulus: Stimulus =
                        serde_json::from_value(q.payload.clone()).map_err(|e| e.to_string())?;
                    if ATTENTION_VERSIONS.contains(&self.dynamics.as_str()) {
                        (stimulus, selection) =
                            self.attention.select(stimulus, self.time, &self.config);
                    }
                    self.stimulate(stimulus);
                } else if q.kind == "energy" {
                    let result = self.energy.supply(
                        q.payload["amount"].as_f64().unwrap(),
                        self.config.energy_capacity,
                        self.config.energy_simulation_enabled,
                    );
                    q.payload
                        .as_object_mut()
                        .unwrap()
                        .extend(result.as_object().unwrap().clone());
                } else if q.kind == "modulation" {
                    let payload =
                        serde_json::from_value(q.payload.clone()).map_err(|e| e.to_string())?;
                    let result = self.attention.update(payload, self.time);
                    q.payload
                        .as_object_mut()
                        .unwrap()
                        .extend(result.as_object().unwrap().clone());
                } else {
                    let values: Vec<(u64, f64)> =
                        serde_json::from_value(q.payload["values"].clone())
                            .map_err(|e| e.to_string())?;
                    let mut touched = vec![];
                    let mut contacts = vec![];
                    for (id, value) in values {
                        if q.kind == "signal" {
                            let amount = self.touch(id, value, false);
                            if amount > 0.0 {
                                touched.push((id, 0.0));
                                contacts.push((id, amount));
                            }
                        } else if self.config.inhibition {
                            if let Some(i) = self.node_index.get(&id) {
                                let n = &mut self.nodes[*i];
                                n.pending_inhibition += value;
                            }
                        }
                    }
                    if q.kind == "signal" && self.config.edge_birth_policy == "temporal-association"
                    {
                        self.associate(touched);
                    }
                    self.update_touched(&contacts);
                }
                self.sequence += 1;
                if record
                    && (!inputs_only
                        || q.kind == "stimulus"
                        || q.kind == "energy"
                        || q.kind == "modulation")
                {
                    let mut event = json!({"sequence":self.sequence,"time_us":self.time.to_string(),"kind":q.kind,"event_id":q.id,"payload":q.payload});
                    if let Some(decision) = selection {
                        event["input_gate"] = decision;
                    }
                    records.push(event);
                }
            }
            self.homeostasis();
            self.generate_inhibition(&baseline);
            if event_time == self.next_step {
                self.spatial_competition();
            }
            if event_time == self.next_propagation {
                self.emit();
                self.prune();
                self.next_propagation += self.config.propagation_interval_us as u128;
            }
            if event_time == self.next_step {
                self.next_step += self.config.step_us as u128;
                self.sequence += 1;
                if record && !inputs_only {
                    records.push(json!({"sequence":self.sequence,"time_us":self.time.to_string(),"kind":"observation","payload":self.metrics()}));
                }
            }
            self.lifecycle();
        }
        if self.life != "dead" {
            self.time = target;
        }
        Ok(records)
    }
    fn associate(&mut self, touched: Vec<(u64, f64)>) {
        let c = &self.config;
        if !c.plasticity || touched.is_empty() {
            return;
        }
        let mut sources = touched.clone();
        if c.edge_birth_policy == "temporal-association" {
            let impulses: BTreeMap<u64, f64> = touched.iter().copied().collect();
            sources = self
                .nodes
                .iter()
                .filter(|n| {
                    (n.touches > 0 || impulses.contains_key(&n.id))
                        && n.activation > 0.0
                        && !self.silenced_nodes.contains(&n.id)
                        && self.time - parse_time(&n.last_touch_us).unwrap()
                            <= c.association_window_us as u128
                })
                .map(|n| (n.id, impulses.get(&n.id).copied().unwrap_or(0.0)))
                .collect();
            sources.sort_by_key(|(id, _)| *id);
        }
        let connected: BTreeSet<u64> = if c.local_novelty_gain > 0.0 {
            self.incident
                .iter()
                .filter(|(_, v)| !v.is_empty())
                .map(|(id, _)| *id)
                .collect()
        } else {
            BTreeSet::new()
        };
        let limit = c.edge_adaptation_limit;
        let available = limit.map(|value| {
            self.resources
                .available_adaptations(self.time, c.propagation_interval_us, value)
        });
        let threshold = c.edge_birth_activation_product_min;
        let spatial_radius =
            (c.spatial_embedding && c.neighborhood_enabled).then_some(c.spatial_radius);
        let mut selected = BTreeSet::new();
        let mut count: u128 = 0;
        for (source, si) in sources {
            for &(target, ti) in &touched {
                if source == target || self.silenced_edges.contains(&(source, target)) {
                    continue;
                }
                if spatial_radius.is_some_and(|radius| {
                    spatial::distance(&self.spatial_points, source, target) > radius
                }) {
                    continue;
                }
                let score = self.nodes[self.node_index[&source]].activation
                    * self.nodes[self.node_index[&target]].activation;
                if score <= 0.0
                    || (score < threshold && !self.edge_index.contains_key(&(source, target)))
                {
                    continue;
                }
                let candidate = Candidate {
                    score,
                    source,
                    target,
                    si,
                    ti,
                };
                if let Some(available) = available {
                    count += 1;
                    if available > 0 {
                        selected.insert(candidate);
                        if selected.len() as u64 > available {
                            selected.pop_last();
                        }
                    }
                } else {
                    self.adapt_candidate(candidate, &connected);
                }
            }
        }
        if limit.is_some() {
            self.resources
                .increment(Counter::Adaptation, count - selected.len() as u128);
            for candidate in selected {
                self.adapt_candidate(candidate, &connected);
            }
        }
    }
    fn homeostasis(&mut self) {
        if !self.config.homeostasis_enabled {
            return;
        }
        let total: f64 = self.nodes.iter().map(|n| n.activation).sum();
        if total > self.config.target_total_activation {
            let scale = self.config.target_total_activation / total;
            for n in &mut self.nodes {
                n.activation *= scale;
                n.direct *= scale;
                n.associative *= scale;
            }
        }
    }
    pub fn activations(&self) -> Vec<(u64, f64)> {
        let decay = if self.config.activation_decay_enabled {
            (-((self.time - self.state_time) as f64 / 1e6) / self.config.activation_tau).exp()
        } else {
            1.0
        };
        let mut values: Vec<_> = self
            .nodes
            .iter()
            .map(|n| (n.id, n.activation * decay))
            .collect();
        values.sort_by_key(|n| n.0);
        values
    }
    pub fn observation_nodes(&self) -> Vec<Node> {
        let dt = (self.time - self.state_time) as f64 / 1e6;
        let c = &self.config;
        let mut rows = self.nodes.clone();
        rows.sort_by_key(|n| n.id);
        for n in &mut rows {
            if c.activation_decay_enabled {
                n.activation *= (-dt / c.activation_tau).exp();
            }
            if c.inhibition_decay_enabled {
                n.inhibition *= (-dt / c.inhibition_tau).exp();
            }
            if c.trace_decay_enabled {
                n.trace *= (-dt / c.trace_tau).exp();
            }
            if c.plasticity && c.support_decay_enabled {
                n.support = (n.support - dt / c.support_tau * (1.0 - n.stability)).max(0.0);
            }
        }
        rows
    }
    pub fn induced_edges(&self, node_ids: Vec<u64>) -> Vec<Edge> {
        let ids: BTreeSet<_> = node_ids.into_iter().collect();
        let mut rows = Vec::new();
        for source in &ids {
            if let Some(targets) = self.outgoing.get(source) {
                for target in targets.intersection(&ids) {
                    rows.push(self.edges[self.edge_index[&(*source, *target)]].clone());
                }
            }
        }
        rows
    }
    pub fn graph(&self, limit: Option<usize>) -> Value {
        let decay = if self.config.activation_decay_enabled {
            (-((self.time - self.state_time) as f64 / 1e6) / self.config.activation_tau).exp()
        } else {
            1.0
        };
        let mut nodes = self.nodes.clone();
        nodes.sort_by_key(|n| n.id);
        nodes.truncate(limit.unwrap_or(nodes.len()));
        for n in &mut nodes {
            n.activation *= decay;
        }
        let ids: BTreeSet<_> = nodes.iter().map(|n| n.id).collect();
        let edges: Vec<_> = self
            .edges
            .iter()
            .filter(|e| ids.contains(&e.source) && ids.contains(&e.target))
            .collect();
        json!({"nodes":nodes,"edges":edges,"sequence":self.sequence,"time_us":self.time.to_string(),"total_nodes":self.nodes.len(),"total_edges":self.edges.len(),"complete":nodes.len()==self.nodes.len()})
    }
    pub fn metrics(&self) -> Value {
        let dt = (self.time - self.state_time) as f64 / 1e6;
        let decay = if self.config.activation_decay_enabled {
            (-dt / self.config.activation_tau).exp()
        } else {
            1.0
        };
        let count = self.nodes.len();
        let activation = self.nodes.iter().map(|n| n.activation).sum::<f64>() * decay;
        let average = |total: f64| {
            if count > 0 {
                Some(total / count as f64)
            } else {
                None
            }
        };
        let active = self
            .nodes
            .iter()
            .filter(|n| n.activation * decay > self.config.activation_floor)
            .count();
        let saturated = self
            .nodes
            .iter()
            .filter(|n| n.activation * decay >= 0.95)
            .count();
        let mean = if self.edges.is_empty() {
            None
        } else {
            Some(self.edges.iter().map(|e| e.weight).sum::<f64>() / self.edges.len() as f64)
        };
        let resources = if RESOURCE_VERSIONS.contains(&self.dynamics.as_str()) {
            let mut value = serde_json::to_value(&self.resources).unwrap();
            value["limits"] = json!({"max_nodes":self.config.max_nodes,"max_edges":self.config.max_edges,
                "propagation_limit":self.config.propagation_limit,"edge_adaptation_limit":self.config.edge_adaptation_limit});
            value["step_us"] = json!(self.config.propagation_interval_us);
            value
        } else {
            Value::Null
        };
        let energy = if ENERGY_VERSIONS.contains(&self.dynamics.as_str()) {
            let mut value = serde_json::to_value(&self.energy).unwrap();
            value["parameters"] = self.config.energy_parameters();
            value["settled_state_time_us"] = json!(self.state_time.to_string());
            value
        } else {
            Value::Null
        };
        let attention = if ATTENTION_VERSIONS.contains(&self.dynamics.as_str()) {
            let mut value = serde_json::to_value(&self.attention).unwrap();
            value["parameters"] = json!({"attention_competition_enabled":self.config.attention_competition_enabled,"attention_budget":self.config.attention_budget});
            value["effective"] =
                serde_json::to_value(self.attention.effective(self.time, &self.config)).unwrap();
            value
        } else {
            Value::Null
        };
        json!({"time_us":self.time.to_string(),"state_time_us":self.state_time.to_string(),"sequence":self.sequence,"life":self.life,"quiet_since_us":self.quiet_since.map(|t|t.to_string()),"transport":self.transport,"nodes":self.nodes.len(),"edges":self.edges.len(),
            "activation":activation,"mean_activation":average(activation),"active_fraction":average(active as f64),"saturated_fraction":average(saturated as f64),
            "edge_density":if count > 1 { Some(self.edges.len() as f64 / (count as f64 * (count - 1) as f64)) } else { None },
            "inhibition":self.nodes.iter().map(|n|n.inhibition).sum::<f64>()*if self.config.inhibition_decay_enabled {(-dt/self.config.inhibition_tau).exp()} else {1.0},"pending_events":self.queue.len(),"mean_weight":mean,
            "resources":resources,"energy":energy,"attention":attention,
            "spatial":if SPATIAL_VERSIONS.contains(&self.dynamics.as_str()) { spatial::observation(&self.config,&self.spatial_points,&self.nodes,&self.edges,false) } else { Value::Null }})
    }
    pub fn spatial_geometry(&self) -> Result<Value> {
        if !SPATIAL_VERSIONS.contains(&self.dynamics.as_str()) {
            return Err("this dynamics version has no causal spatial contract".into());
        }
        Ok(spatial::observation(
            &self.config,
            &self.spatial_points,
            &self.nodes,
            &self.edges,
            true,
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn event_boundary() {
        let mut e = Engine::new(Config::default()).unwrap();
        for n in [1, 2] {
            e.inject(Stimulus {
                time_us: "0".into(),
                channels: vec![(n, 0.8)],
                intensity: 1.0,
                bypass_attention: false,
            })
            .unwrap();
        }
        e.advance(0, false).unwrap();
        assert_eq!(e.capture().edges.len(), 0);
    }
    #[test]
    fn resume_is_exact() {
        let mut e = Engine::new(Config::default()).unwrap();
        e.inject(Stimulus {
            time_us: "0".into(),
            channels: vec![(1, 0.8), (2, 0.6)],
            intensity: 1.0,
            bypass_attention: false,
        })
        .unwrap();
        e.advance(12345, false).unwrap();
        let mut b = Engine::restore(e.capture()).unwrap();
        e.advance(100000, false).unwrap();
        b.advance(100000, false).unwrap();
        assert_eq!(
            serde_json::to_string(&e.capture()).unwrap(),
            serde_json::to_string(&b.capture()).unwrap()
        );
    }
}
