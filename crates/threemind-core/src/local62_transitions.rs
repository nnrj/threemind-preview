// /6.2 transition fork. Reception, novelty and peripheral contracts retain /5.1 rules.
// Persistent decay, structure checks, transmission and attempt energy are new dynamics.
use crate::continuous::{self, Parameters as Operators};
use crate::energy::{Cost, Energy, Supply};
use crate::mechanisms::local_attention;
use super::local61_synapse::{FastTrace, ShortTermState};
use crate::retention::{self, grow, Parameters as Retention};
use crate::{canonical_hash, Config, Result, Stimulus};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

pub const LEGACY_KERNEL_ID: &str = "threemind.continuous-memory/4";
pub const LEGACY_STATE_SCHEMA: &str = "threemind.continuous-memory-state/4.1";
pub const KERNEL5_ID: &str = "threemind.continuous-memory/5";
pub const STATE5_SCHEMA: &str = "threemind.continuous-memory-state/5";
const MECHANISMS: &[(&str, &str)] = &[
    ("threemind.object-local-clock/1", "arrivals-emission-expiry"),
    (
        "threemind.source-independent-reception/1",
        "receiver-local-arrivals",
    ),
    ("threemind.tm-synapse/1", "before-emission"),
    ("threemind.leaky-fast-trace/1", "efficacy-and-emission"),
    (
        "threemind.local-context-attention/1",
        "receiver-local-arrivals",
    ),
    (
        "threemind.local-contact-learning/1",
        "delivered-contact-packet",
    ),
    ("threemind.local-arrival-novelty/3", "local-birth-window"),
    (
        "threemind.single-age-decay/1",
        "local-settlement",
    ),
    (
        "threemind.local-resource-field/1",
        "supply-local-uptake-expense",
    ),
    ("threemind.local-awakening/2", "residual-contact-arrivals"),
];
const MECHANISMS5: &[(&str, &str)] = &[
    ("threemind.object-local-clock/2", "arrivals-novelty-emission-expiry"),
    ("threemind.source-independent-reception/2", "receiver-local-arrivals"),
    ("threemind.tm-synapse/1", "before-emission"),
    ("threemind.leaky-fast-trace/1", "efficacy-and-emission"),
    ("threemind.local-context-attention/1", "receiver-local-arrivals"),
    ("threemind.local-contact-learning/2", "external-contact-packet"),
    ("threemind.local-arrival-novelty/4", "pre-emission-aligned-window"),
    ("threemind.local-resource-field/1", "supply-local-uptake-expense"),
    ("threemind.local-awakening/2", "residual-contact-arrivals"),
    ("threemind.inhibition-packet-saturation/1", "after-same-time-emissions"),
    ("threemind.single-age-decay/1", "local-settlement"),
    ("threemind.local-deletion/1", "after-same-time-emissions"),
    ("threemind.source-send-thresholds/1", "node-emission-scheduling"),
    ("threemind.directed-shared-transport/1", "node-offer-edge-transmission"),
    ("threemind.fixed-function-addressing/1", "external-stimulus-reception"),
    ("threemind.inflight-delivery/1", "internal-event-reception"),
    ("threemind.stability-retention/1", "connection-local-period"),
    ("threemind.signal-type-thresholds/1", "connection-transmission"),
];
const NEW_KEYS: &[&str] = &[
    "activation_signal_threshold", "inhibition_signal_threshold",
    "stability_growth_enabled", "stability_relaxation_enabled",
    "activation_weight_reinforcement_enabled", "inhibition_weight_reinforcement_enabled",
    "resource_precheck_enabled", "subthreshold_expiry_enabled",
    "separate_inhibition", "separate_inhibition_weights", "separate_inhibition_resources", "separate_inhibition_learning",
    "deletion_strategy", "activation_send_threshold", "inhibition_send_threshold",
    "inflight_delivery",
    "decay_curve",
    "decay_transition_age",
    "reinforcement_age_policy",
    "retention_growth_enabled",
    "retention_relaxation_enabled",
    "structure_check_interval_us",
    "signal_threshold_enabled",
    "signal_threshold",
    "weight_gate_enabled",
    "weight_gate",
    "inhibitory_learning_enabled",
    "inhibition_updates_usage",
    "inhibition_sender_gate_enabled",

    "propagation_mode",
    "propagation_phase",
    "arrival_mode",
    "reception_mode",
    "energy_model",
    "energy_distribution",
    "energy_seed",
    "energy_region_count",
    "energy_node_capacity",
];
const IMMUTABLE: &[&str] = &[
    "separate_inhibition", "separate_inhibition_weights", "separate_inhibition_resources", "separate_inhibition_learning",
    "inflight_delivery",
    "decay_curve", "decay_transition_age", "reinforcement_age_policy", "structure_check_interval_us",
    "seed",
    "step_us",
    "propagation_interval_us",
    "energy_initial_reserve",
    "consolidation_mode",
    "memory_growth_formula",
    "novelty_mode",
    "propagation_mode",
    "propagation_phase",
    "arrival_mode",
    "reception_mode",
    "energy_model",
    "energy_distribution",
    "energy_seed",
    "energy_region_count",
];
type Key = (u64, u64);
type Timer = (u8, u64, u64);
type Message = (i64, u64, f64, Vec<f64>);
type Packet = (i128, Vec<Message>, bool, f64);
type Contact = (u64, f64, f64);
fn at<T: RuntimeTimestamp + ?Sized>(s: &T) -> u128 {
    read_time(s).expect("validated local timestamp")
}
fn word(seed: u64, domain: u64, serial: u64) -> u64 {
    let mut v = seed ^ domain.wrapping_mul(0x9e3779b97f4a7c15) ^ serial;
    v = (v ^ (v >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
    v = (v ^ (v >> 27)).wrapping_mul(0x94d049bb133111eb);
    v ^ (v >> 31)
}

#[derive(Clone, Deserialize)]
struct RuntimeOptions {
    inflight_delivery: String,
    propagation_mode: String,
    propagation_phase: String,
    arrival_mode: String,
    reception_mode: String,
    energy_model: String,
    energy_distribution: String,
    reinforcement_age_policy: String,
    deletion_strategy: String,
    decay_curve: String,
    energy_node_capacity: f64,
    weight_gate: f64,
    signal_threshold: f64,
    activation_signal_threshold: Option<f64>,
    inhibition_signal_threshold: Option<f64>,
    stability_growth_enabled: bool,
    stability_relaxation_enabled: bool,
    activation_weight_reinforcement_enabled: bool,
    inhibition_weight_reinforcement_enabled: bool,
    separate_inhibition: bool,
    separate_inhibition_weights: Option<bool>,
    separate_inhibition_resources: Option<bool>,
    separate_inhibition_learning: Option<bool>,
    resource_precheck_enabled: bool,
    subthreshold_expiry_enabled: bool,
    decay_transition_age: f64,
    activation_send_threshold: f64,
    inhibition_send_threshold: f64,
    energy_seed: u64,
    energy_region_count: u64,
    structure_check_interval_us: u64,
    weight_gate_enabled: bool,
    signal_threshold_enabled: bool,
    retention_growth_enabled: bool,
    retention_relaxation_enabled: bool,
    inhibitory_learning_enabled: bool,
    inhibition_updates_usage: bool,
    inhibition_sender_gate_enabled: bool,
}

#[derive(Clone)]
struct Settings {
    f: RuntimeOptions,
    value: Value,
    c: Config,
    o: Operators,
    r: Retention,
    depletion: bool,
    consolidate: bool,
    novelty: String,
    eligibility_period_retention: f64,
}
impl Settings {
    fn parse(v: Value) -> Result<Self> {
        let defaults: Value = serde_json::from_str(include_str!("local62-defaults.json")).unwrap();
        let mut value = defaults.clone();
        for (k, v) in v
            .as_object()
            .ok_or("local configuration must be an object")?
        {
            if defaults.get(k).is_none() {
                return Err(format!("unknown local configuration field {k}"));
            }
            value[k] = v.clone();
        }
        for (key, choices) in [
            ("deletion_strategy", vec!["local", "global-scan"]),
            ("inflight_delivery", vec!["address", "same-birth"]),
            ("propagation_mode", vec!["local-events", "scan-control"]),
            ("propagation_phase", vec!["aligned", "asynchronous"]),
            ("arrival_mode", vec!["coincident", "sequential"]),
            ("reception_mode", vec!["unified", "legacy-source"]),
            ("energy_model", vec!["local-field", "global-ledger"]),
            (
                "energy_distribution",
                vec!["counter-random", "stream-random"],
            ),
        ] {
            if !choices.contains(&value[key].as_str().unwrap_or("")) {
                return Err(format!("unknown {key}"));
            }
        }
        if value["energy_seed"]
            .as_u64()
            .is_none_or(|v| v > 9_007_199_254_740_991)
            || value["energy_region_count"]
                .as_u64()
                .is_none_or(|v| !(1..=4096).contains(&v))
            || value["energy_node_capacity"]
                .as_f64()
                .is_none_or(|v| !v.is_finite() || !(1e-12..=1e12).contains(&v))
        {
            return Err("invalid local energy parameters".into());
        }
        for k in ["stability_growth_enabled", "stability_relaxation_enabled", "activation_weight_reinforcement_enabled", "inhibition_weight_reinforcement_enabled", "retention_growth_enabled", "retention_relaxation_enabled", "signal_threshold_enabled",
            "weight_gate_enabled", "inhibitory_learning_enabled", "inhibition_updates_usage", "inhibition_sender_gate_enabled",
            "resource_precheck_enabled", "subthreshold_expiry_enabled",
            "separate_inhibition"] {
            if !value[k].is_boolean() { return Err(format!("{k} must be boolean")); }
        }
        for k in ["separate_inhibition_weights", "separate_inhibition_resources", "separate_inhibition_learning"] {
            if !value[k].is_null() && !value[k].is_boolean() { return Err(format!("{k} must be boolean or null")); }
        }
        let master = value["separate_inhibition"].as_bool().unwrap();
        if value["separate_inhibition_learning"].as_bool().unwrap_or(master)
            && !value["separate_inhibition_weights"].as_bool().unwrap_or(master) {
            return Err("separate inhibitory learning requires separate weights".into());
        }
        if !["exponential", "power-law", "inverse-logarithmic", "power-exponential"].contains(&value["decay_curve"].as_str().unwrap_or(""))
            || !["keep", "reset"].contains(&value["reinforcement_age_policy"].as_str().unwrap_or("")) {
            return Err("unknown decay curve or age policy".into());
        }
        for k in ["decay_transition_age", "signal_threshold", "weight_gate", "activation_send_threshold", "inhibition_send_threshold"] {
            if value[k].as_f64().is_none_or(|x| !x.is_finite() || !(0.0..=1e12).contains(&x)) {
                return Err(format!("invalid {k}"));
            }
        }
        for k in ["activation_signal_threshold", "inhibition_signal_threshold"] {
            if !value[k].is_null() {
                let x = value[k].as_f64().ok_or_else(|| format!("invalid {k}"))?;
                if !x.is_finite() || !(0.0..=1e12).contains(&x) { return Err(format!("invalid {k}")); }
                value[k] = json!(x);
            }
        }
        if value["consolidation_mode"] == "stability"
            && (value["retention_growth_enabled"] == true || value["retention_relaxation_enabled"] == true) {
            return Err("H growth/relaxation belongs to single-age decay; stability retention has separate controls".into());
        }
        if value["decay_transition_age"].as_f64().unwrap() <= 0.0 || value["weight_gate"].as_f64().unwrap() > 1.0
            || value["structure_check_interval_us"].as_u64().is_none_or(|x| x == 0 || x >= 1 << 53)
            || !["adaptive-half-life", "stability"].contains(&value["consolidation_mode"].as_str().unwrap_or("")) || value["node_retention_mode"] != "automatic"
            || (value["weight_gate_enabled"] == true && value["weight_gate"].as_f64().unwrap() < value["prune_weight"].as_f64().ok_or("invalid prune weight")?) {
            return Err("invalid /6.2 decay or threshold configuration".into());
        }
        let mut old = value.clone();
        for k in NEW_KEYS {
            old.as_object_mut().unwrap().remove(*k);
        }
        // Reuse the unchanged numeric parameter parser, not a historical engine.
        // The public 6.2 configuration retains its formal "stability" name.
        if old["consolidation_mode"] == "stability" { old["consolidation_mode"] = json!("legacy-stability"); }
        let r = retention::take(&mut old)?;
        let novelty = old
            .as_object_mut()
            .unwrap()
            .remove("novelty_mode")
            .unwrap()
            .as_str()
            .ok_or("invalid novelty_mode")?
            .to_string();
        if !["arrival-window", "immediate"].contains(&novelty.as_str()) {
            return Err("invalid novelty_mode".into());
        }
        let depletion = old
            .as_object_mut()
            .unwrap()
            .remove("depletion_enabled")
            .unwrap()
            .as_bool()
            .ok_or("invalid depletion_enabled")?;
        let consolidate = old
            .as_object_mut()
            .unwrap()
            .remove("edge_consolidation_enabled")
            .unwrap()
            .as_bool()
            .ok_or("invalid edge_consolidation_enabled")?;
        let (c, o) = continuous::parse_config(old)?;
        r.validate(&c)?;
        if c.homeostasis_enabled
            || c.spatial_competition_rate > 0.0
            || c.attention_competition_enabled
            || c.edge_birth_policy != "co-stimulus"
        {
            return Err("memory/4 does not implement global homeostasis, spatial competition, input ranking or temporal search".into());
        }
        for key in [
            "step_us",
            "association_window_us",
            "attention_budget",
            "target_total_activation",
        ] {
            if value[key] != defaults[key] {
                return Err(format!(
                    "{key} is inactive metadata in memory/4 and cannot be changed"
                ));
            }
        }
        value["revival_enabled"] = json!(r.revival_enabled);
        for (k, d) in defaults.as_object().unwrap() {
            if d.is_f64() || (k.ends_with("wake_threshold") && !value[k].is_null()) {
                value[k] = json!(value[k].as_f64().ok_or("invalid numeric configuration")?);
            }
        }
        let eligibility_period_retention = if OPTIMIZED && c.eligibility_decay_enabled {
            let dt = c.propagation_interval_us as f64 / 1e6;
            (-dt / c.eligibility_tau).exp()
        } else {
            1.0
        };
        Ok(Self {
            eligibility_period_retention,
            f: serde_json::from_value(value.clone()).map_err(|e| e.to_string())?,
            value,
            c,
            o,
            r,
            depletion,
            consolidate,
            novelty,
        })
    }
    fn separates_weights(&self) -> bool { self.f.separate_inhibition_weights.unwrap_or(self.f.separate_inhibition) }
    fn separates_resources(&self) -> bool { self.f.separate_inhibition_resources.unwrap_or(self.f.separate_inhibition) }
    fn separates_learning(&self) -> bool { self.f.separate_inhibition_learning.unwrap_or(self.f.separate_inhibition) }
    fn stability_grows(&self) -> bool { self.r.adaptive() || self.f.stability_growth_enabled }
    fn signal_threshold_for(&self, inhibitory: bool) -> f64 {
        (if inhibitory { self.f.inhibition_signal_threshold } else { self.f.activation_signal_threshold })
            .unwrap_or(self.f.signal_threshold)
    }
    fn choice(&self, k: &str, v: &str) -> bool {
        match k {
            "inflight_delivery" => self.f.inflight_delivery == v,
            "propagation_mode" => self.f.propagation_mode == v,
            "propagation_phase" => self.f.propagation_phase == v,
            "arrival_mode" => self.f.arrival_mode == v,
            "reception_mode" => self.f.reception_mode == v,
            "energy_model" => self.f.energy_model == v,
            "energy_distribution" => self.f.energy_distribution == v,
            "reinforcement_age_policy" => self.f.reinforcement_age_policy == v,
            "deletion_strategy" => self.f.deletion_strategy == v,
            "decay_curve" => self.f.decay_curve == v,
            _ => self.value[k].as_str() == Some(v),
        }
    }
    fn uint(&self, k: &str) -> u64 {
        match k {
            "energy_seed" => self.f.energy_seed,
            "energy_region_count" => self.f.energy_region_count,
            "structure_check_interval_us" => self.f.structure_check_interval_us,
            _ => self.value[k].as_u64().unwrap(),
        }
    }
    fn num(&self, k: &str) -> f64 {
        match k {
            "energy_node_capacity" => self.f.energy_node_capacity,
            "weight_gate" => self.f.weight_gate,
            "signal_threshold" => self.f.signal_threshold,
            "decay_transition_age" => self.f.decay_transition_age,
            "activation_send_threshold" => self.f.activation_send_threshold,
            "inhibition_send_threshold" => self.f.inhibition_send_threshold,
            _ => self.value[k].as_f64().unwrap(),
        }
    }
}

#[derive(Clone, Copy, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Node {
    id: u64,
    channel: u32,
    birth_serial: u64,
    activation: f64,
    inhibition: f64,
    trace: f64,
    support: f64,
    stability: f64,
    direct: f64,
    associative: f64,
    touches: u64,
    last_touch_us: Timestamp,
    birth_us: Timestamp,
    local_plasticity: f64,
    pending_inhibition: f64,
    generated_inhibition: f64,
    state_us: Timestamp,
    half_life: f64,
    decay_age: f64,
    fatigue: f64,
    salience: f64,
    isolated_us: Timestamp,
    region: u64,
    reserve: f64,
    energy_us: Timestamp,
    sleeping: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    last_emit_us: Option<Timestamp>,
}
#[derive(Clone, Copy, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct InhibitionLearning {
    fast: Option<FastTrace>,
    eligibility: f64,
    stability: f64,
    half_life: f64,
    decay_age: f64,
    last_pass_us: Timestamp,
    touches: u64,
    last_touch_us: Timestamp,
}
#[derive(Clone, Copy, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Edge {
    source: u64,
    target: u64,
    weight: f64,
    stability: f64,
    eligibility: f64,
    touches: u64,
    birth_us: Timestamp,
    last_touch_us: Timestamp,
    state_us: Timestamp,
    half_life: f64,
    decay_age: f64,
    last_pass_us: Timestamp,
    sleeping: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    inhibition_weight: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    inhibition_short_term: Option<ShortTermState>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    inhibition_learning: Option<InhibitionLearning>,
    short_term: Option<ShortTermState>,
    fast: Option<FastTrace>,
    novelty_deadline_us: Option<Timestamp>,
    novelty_source: f64,
    novelty_target: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    completed_period_us: Option<Timestamp>,
}
impl Edge {
    fn learning(&self) -> InhibitionLearning {
        InhibitionLearning { fast:self.fast, eligibility:self.eligibility, stability:self.stability,
            half_life:self.half_life, decay_age:self.decay_age, last_pass_us:self.last_pass_us,
            touches:self.touches, last_touch_us:self.last_touch_us }
    }
    fn inhibition_lane(&self) -> Self {
        let mut lane = *self;
        let state = self.inhibition_learning.unwrap();
        lane.weight = self.inhibition_weight.unwrap();
        lane.fast=state.fast; lane.eligibility=state.eligibility; lane.stability=state.stability;
        lane.half_life=state.half_life; lane.decay_age=state.decay_age; lane.last_pass_us=state.last_pass_us;
        lane.touches=state.touches; lane.last_touch_us=state.last_touch_us;
        lane.inhibition_weight=None; lane.inhibition_learning=None; lane.inhibition_short_term=None;
        lane
    }
    fn merge_inhibition_lane(&mut self, lane: &Self) {
        self.inhibition_weight=Some(lane.weight); self.inhibition_learning=Some(lane.learning());
    }
    fn structural_weight(&self) -> f64 {
        self.inhibition_weight.map_or(self.weight, |w| self.weight.max(w))
    }
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Event {
    time_us: Timestamp,
    id: u64,
    kind: String,
    payload: Payload,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    birth_limit: Option<u64>,
}

/// Version selection is fixed at construction and monomorphized, never hot-switched.
pub struct LocalEngineImpl<const V5: bool> {
    s: Settings,
    nodes: ObjectMap<u64, Node>,
    edges: ObjectMap<Key, Edge>,
    outgoing: BTreeMap<u64, BTreeSet<Key>>,
    incident: BTreeMap<u64, BTreeSet<Key>>,
    regions: BTreeMap<u64, BTreeSet<u64>>,
    active: BTreeSet<u64>,
    silenced_nodes: BTreeSet<u64>,
    silenced_edges: BTreeSet<Key>,
    queue: BTreeMap<(u128, u64), Event>,
    timers: BTreeSet<(u128, Timer)>,
    deadlines: BTreeMap<Timer, u128>,
    pub time: u128,
    pub sequence: u64,
    next_event: u64,
    birth_count: u64,
    sources_open: bool,
    pub life: String,
    quiet: Option<u128>,
    transport: BTreeMap<String, f64>,
    audit: BTreeMap<String, u64>,
    energy: Energy,
    pools: BTreeMap<u64, f64>,
    energy_serial: u64,
    energy_rng: u64,
    // Derived/transient indexes; checkpoints serialize their source state only.
    pending_novelty: BTreeMap<u64, BTreeSet<Key>>,
    inhibition_batch: BTreeMap<u64, f64>,
    before_emission: bool,
    deletion_phase: bool,
    // Executor phase watermark, not a global node/edge update.
    completed_emission_us: u128,
}
impl<const V5: bool> LocalEngineImpl<V5> {
    const KERNEL: &'static str = if OPTIMIZED {
        KERNEL_ID
    } else if V5 {
        KERNEL5_ID
    } else {
        LEGACY_KERNEL_ID
    };
    const SCHEMA: &'static str = if OPTIMIZED {
        STATE_SCHEMA
    } else if V5 {
        STATE5_SCHEMA
    } else {
        LEGACY_STATE_SCHEMA
    };
    pub fn new(value: Value) -> Result<Self> {
        if OPTIMIZED && !V5 {
            return Err("memory/5.1 only implements the version-five scientific rules".into());
        }
        let mut value = value;
        if V5 {
            let fields = value
                .as_object_mut()
                .ok_or("local configuration must be an object")?;
            fields
                .entry("reception_mode")
                .or_insert(json!("legacy-source"));
            fields.entry("arrival_mode").or_insert(json!("sequential"));
        }
        let s = Settings::parse(value)?;
        let mut energy = Energy::initial(&s.c, 0);
        let reserve = if s.choice("energy_model", "local-field") {
            let v = energy.reserve;
            energy.reserve = 0.0;
            v
        } else {
            0.0
        };
        let pools = (0..s.uint("energy_region_count"))
            .map(|r| (r, reserve / s.uint("energy_region_count") as f64))
            .collect();
        let energy_rng = word(s.uint("energy_seed"), 3, 0);
        Ok(Self {
            s,
            nodes: ObjectMap::new(),
            edges: ObjectMap::new(),
            outgoing: BTreeMap::new(),
            incident: BTreeMap::new(),
            regions: BTreeMap::new(),
            active: BTreeSet::new(),
            silenced_nodes: BTreeSet::new(),
            silenced_edges: BTreeSet::new(),
            queue: BTreeMap::new(),
            timers: BTreeSet::new(),
            deadlines: BTreeMap::new(),
            time: 0,
            sequence: 0,
            next_event: 0,
            birth_count: 0,
            sources_open: true,
            life: "waiting".into(),
            quiet: None,
            transport: ["sent", "received", "activated", "discarded", "offered_excitation", "offered_inhibition", "transmitted_excitation", "transmitted_inhibition", "received_inhibition", "blocked_weight", "blocked_signal", "blocked_dormancy", "blocked_energy"]
                .into_iter()
                .map(|k| (k.into(), 0.0))
                .collect(),
            audit: [
                "node_visits",
                "edge_visits",
                "scan_visits",
                "expiry_checks",
                "nodes_deleted",
                "edges_deleted",
                "nodes_awakened",
                "edges_awakened",
            ]
            .into_iter()
            .map(|k| (k.into(), 0))
            .collect(),
            energy,
            pools,
            energy_serial: 0,
            energy_rng,
            pending_novelty: BTreeMap::new(),
            inhibition_batch: BTreeMap::new(),
            before_emission: false,
            deletion_phase: false,
            completed_emission_us: 0,
        })
    }
    pub fn config(&self) -> Value {
        self.s.value.clone()
    }
    pub fn definition(&self) -> Value {
        let mechanisms = if V5 { MECHANISMS5 } else { MECHANISMS };
        let hypothesis = if OPTIMIZED {
            "threemind.hypotheses/continuous-memory62"
        } else if V5 {
            "threemind.hypotheses/continuous-memory5"
        } else {
            "threemind.hypotheses/continuous-memory4"
        };
        json!({"schema":"threemind.kernel-definition/1","kernel_id":Self::KERNEL,"state_schema":Self::SCHEMA,"hypothesis_id":hypothesis,"operators":mechanisms.iter().map(|(id,phase)|json!({"id":id,"phase":phase})).collect::<Vec<_>>(),"config":self.config()})
    }
    pub fn is_empty(&self) -> bool {
        self.nodes.is_empty()
    }
    fn timer(&mut self, key: Timer, time: Option<u128>) {
        if V5 && self.deadlines.get(&key).copied() == time {
            return;
        }
        if let Some(old) = self.deadlines.remove(&key) {
            self.timers.remove(&(old, key));
        }
        if let Some(t) = time {
            self.deadlines.insert(key, t);
            self.timers.insert((t, key));
        }
    }
    fn delay(&self, seconds: f64) -> u128 {
        self.time + ((seconds * 1e6).ceil() as u128 + 1).max(1)
    }
    fn event(&mut self, t: u128, kind: &str, payload: Value) -> u64 {
        self.event_payload(t, kind, payload.into())
    }
    fn event_payload(&mut self, t: u128, kind: &str, payload: Payload) -> u64 {
        let id = self.next_event;
        self.next_event += 1;
        self.queue.insert(
            (t, id),
            Event {
                time_us: stamp(t),
                id,
                kind: kind.into(),
                payload,
                birth_limit: if self.s.choice("inflight_delivery", "same-birth")
                    && matches!(kind, "signal" | "inhibition" | "wake") {
                    Some(self.birth_count)
                } else { None },
            },
        );
        id
    }
    // The birth counter records lifetime only; addressing remains F(code) = code.
    fn accept_birth(&self, id: u64, limit: Option<u64>) -> bool {
        limit.is_none_or(|limit| self.nodes.get(&id).is_some_and(|n| n.birth_serial <= limit))
    }
    pub fn inject(&mut self, s: Stimulus) -> Result<u64> {
        s.validate()?;
        let t = s.time()?;
        if t < self.time || self.life == "dead" || !self.sources_open {
            return Err("input violates causal/lifecycle boundary".into());
        }
        Ok(self.event(t, "stimulus", serde_json::to_value(s).unwrap()))
    }
    pub fn close_inputs(&mut self) {
        self.sources_open = false;
    }
    pub fn supply_energy(&mut self, t: u128, amount: f64, source: String) -> Result<u64> {
        let p = Supply { amount, source };
        p.validate()?;
        if !self.s.c.energy_simulation_enabled || t < self.time || self.life == "dead" {
            return Err("energy input violates configuration or causal boundary".into());
        }
        Ok(self.event(t, "energy", serde_json::to_value(p).unwrap()))
    }
    pub fn modulate_input(&mut self, _t: u128, _v: Value) -> Result<u64> {
        Err(if V5 {
            "memory/5 input modulation belongs to an explicit peripheral"
        } else {
            "memory/4 input modulation belongs to an explicit peripheral"
        }
        .into())
    }
    fn soft(&self, v: f64) -> f64 {
        self.s.c.inhibition_saturation * (v.max(0.0) / self.s.c.inhibition_saturation).tanh()
    }
    fn response(&self, n: &Node) -> f64 {
        (if self.s.c.inhibition {
            1.0 / (1.0 + self.s.c.inhibition_response_gain * self.soft(n.inhibition))
        } else {
            1.0
        }) / (1.0
            + if self.s.r.strong_fatigue_enabled {
                n.fatigue
            } else {
                0.0
            })
    }
    fn node_value(&self, node: &Node, t: u128) -> Node {
        let mut n = node.clone();
        let c = &self.s.c;
        let r = &self.s.r;
        let dt = (t - at(&n.state_us)) as f64 / 1e6;
        if V5 && dt == 0.0 {
            return n;
        }
        if c.activation_decay_enabled {
            n.activation *= (-dt / c.activation_tau).exp();
        }
        if c.trace_decay_enabled {
            n.trace *= (-dt / c.trace_tau).exp();
        }
        if c.inhibition_decay_enabled {
            n.inhibition *= (-dt / c.inhibition_tau).exp();
        }
        if n.activation < c.activation_floor {
            n.activation = 0.0;
        }
        if c.plasticity && c.support_decay_enabled {
            if r.node_retention_mode == "automatic" {
                (n.support, n.decay_age, n.half_life) = self.s.decay_value(n.support, n.decay_age, n.half_life, dt);
            } else {
                n.support = (n.support - dt / c.support_tau * (1.0 - n.stability)).max(0.0);
            }
        }
        if V5 {
            if n.fatigue != 0.0 || n.salience != 0.0 {
                let factor = (-dt / r.strong_fatigue_tau_s).exp();
                n.fatigue *= factor;
                n.salience *= factor;
            }
        } else {
            n.fatigue *= (-dt / r.strong_fatigue_tau_s).exp();
            n.salience *= (-dt / r.strong_fatigue_tau_s).exp();
        }
        n.state_us = stamp(t);
        n
    }
    fn settle_node(&mut self, id: u64) -> Node {
        *self.audit.get_mut("node_visits").unwrap() += 1;
        let unchanged = V5 && at(&self.nodes[&id].state_us) == self.time;
        let n = if unchanged {
            self.nodes[&id].clone()
        } else {
            self.node_value(&self.nodes[&id], self.time)
        };
        if n.activation == 0.0 {
            self.active.remove(&id);
            if self.life != "waiting" && self.active.is_empty() && self.quiet.is_none() {
                self.quiet = Some(self.time);
            }
        }
        if !unchanged {
            self.nodes.insert(id, n.clone());
        }
        n
    }
    fn edge_value(&self, edge: &Edge, t: u128) -> Edge {
        let mut e = self.primary_edge_value(edge, t);
        if edge.inhibition_learning.is_some() {
            let lane = self.primary_edge_value(&edge.inhibition_lane(), t);
            e.merge_inhibition_lane(&lane);
        }
        e
    }
    fn primary_edge_value(&self, edge: &Edge, t: u128) -> Edge {
        let mut e = edge.clone();
        let c = &self.s.c;
        let dt = (t - at(&e.state_us)) as f64 / 1e6;
        if V5 && !c.plasticity {
            e.completed_period_us = Some(stamp(self.completed_period(t)));
        }
        if c.plasticity && self.s.r.adaptive() {
            if !V5 || dt > 0.0 {
                if let Some(w) = e.inhibition_weight {
                    e.inhibition_weight = Some(self.s.decay_value(w, e.decay_age, e.half_life, dt).0);
                }
                (e.weight, e.decay_age, e.half_life) = self.s.decay_value(e.weight, e.decay_age, e.half_life, dt);
            }
            if V5 {
                self.discrete_edge_state(&mut e, t);
                e.state_us = stamp(t);
                return e;
            }
            let old = e.eligibility;
            if c.eligibility_decay_enabled {
                e.eligibility *= (-dt / c.eligibility_tau).exp();
            }
            if c.stability_decay_enabled {
                let integrated = if c.eligibility_decay_enabled {
                    old * c.eligibility_tau * -(-dt / c.eligibility_tau).exp_m1()
                } else {
                    old * dt
                };
                e.stability = (e.stability - (dt - integrated) / c.stability_tau).max(0.0);
            }
        }
        e.state_us = stamp(t);
        e
    }
    fn completed_period(&self, t: u128) -> u128 {
        let p = self.s.c.propagation_interval_us as u128;
        let time = if self.before_emission && t == self.time {
            t.saturating_sub(1)
        } else {
            t
        };
        time / p * p
    }
    fn discrete_edge_state(&self, e: &mut Edge, t: u128) {
        let c = &self.s.c;
        let p = c.propagation_interval_us as u128;
        let completed = self.completed_period(t);
        let previous = at(e
            .completed_period_us
            .as_ref()
            .expect("version 5 edge clock"));
        let steps = completed.saturating_sub(previous) / p;
        if steps == 0 {
            return;
        }
        let dt = p as f64 / 1e6;
        let old = e.eligibility;
        let n = steps as f64;
        let retention = if OPTIMIZED {
            self.s.eligibility_period_retention
        } else if c.eligibility_decay_enabled {
            (-dt / c.eligibility_tau).exp()
        } else {
            1.0
        };
        let factor = retention.powf(n);
        let integrated = if retention == 1.0 {
            old * n
        } else {
            old * retention * (1.0 - factor) / (1.0 - retention)
        };
        if c.eligibility_decay_enabled {
            e.eligibility *= factor;
        }
        if c.stability_decay_enabled {
            e.stability = (e.stability - dt / c.stability_tau * (n - integrated)).max(0.0);
        }
        e.completed_period_us = Some(stamp(completed));
    }
    fn settle_edge(&mut self, key: Key) -> Edge {
        *self.audit.get_mut("edge_visits").unwrap() += 1;
        let current = &self.edges[&key];
        let unchanged = V5
            && at(&current.state_us) == self.time
            && at(current.completed_period_us.as_ref().unwrap())
                == self.completed_period(self.time);
        if unchanged {
            return *current;
        }
        let e = self.edge_value(current, self.time);
        *self.edges.get_mut(&key).unwrap() = e;
        e
    }
    fn connected(&self, id: u64) -> bool {
        self.incident
            .get(&id)
            .is_some_and(|keys| keys.iter().any(|k| !self.edges[k].sleeping))
    }
    fn structure_timer(&mut self) {
        let key = (6, 0, 0);
        if self.s.f.deletion_strategy == "global-scan" && !self.nodes.is_empty() && self.s.c.plasticity {
            if !self.deadlines.contains_key(&key) {
                let interval = self.s.uint("structure_check_interval_us") as u128;
                self.timer(key, Some((self.time / interval + 1) * interval));
            }
        } else { self.timer(key, None); }
    }
    fn node_timers(&mut self, n: &Node) {
        let c = &self.s.c;
        let due = if n.activation > c.activation_floor && c.activation_decay_enabled && c.activation_floor > 0.0 {
            Some(self.delay(c.activation_tau * (n.activation / c.activation_floor).ln()))
        } else if self.s.f.subthreshold_expiry_enabled && n.activation > 0.0 && n.activation <= c.activation_floor
            && (n.activation < c.activation_floor || c.activation_decay_enabled) {
            Some(self.time + 1)
        } else { None };
        self.timer((1, n.id, 0), due);
        self.structure_timer();
        let seconds = if self.s.f.deletion_strategy == "local" && self.s.c.plasticity && !self.s.r.retain_nodes && n.activation == 0.0 && !self.connected(n.id) {
            if self.s.c.support_decay_enabled { self.s.crossing_seconds(n.support, n.decay_age, n.half_life, 0.006) }
            else if n.support < 0.006 { Some(0.0) } else { None }
        } else { None };
        let due = if seconds.is_some() && self.deletion_phase && n.support < 0.006 && self.time % self.s.f.structure_check_interval_us as u128 == 0 {
            Some(self.time)
        } else { self.deletion_time(at(&n.state_us), seconds) };
        self.timer((3,n.id,0), due);
    }
    fn deletion_time(&self, anchor: u128, seconds: Option<f64>) -> Option<u128> {
        seconds.map(|s| {
            let interval = self.s.f.structure_check_interval_us as u128;
            let due = (self.time + 1).max(anchor.saturating_add((s * 1e6).ceil() as u128).saturating_add(1));
            due.div_ceil(interval) * interval
        })
    }
    fn edge_timer(&mut self, e: &Edge) {
        self.structure_timer();
        let stable = !self.s.r.adaptive() && self.s.c.plasticity;
        let period = self.s.c.propagation_interval_us as u128;
        let current_due = stable && self.before_emission && self.time > 0 && self.time % period == 0
            && at(e.completed_period_us.as_ref().unwrap()) < self.time;
        self.timer((7,e.source,e.target), if stable {
            Some(if current_due { self.time } else { (self.time / period + 1) * period })
        } else { None });
        let floor = if e.sleeping { self.s.r.dormant_prune_weight } else { self.s.c.prune_weight };
        let seconds = if self.s.f.deletion_strategy == "local" && self.s.c.plasticity {
            if stable { if e.structural_weight() < floor { Some(0.0) } else { None } }
            else { self.s.crossing_seconds(e.structural_weight(),e.decay_age,e.half_life,floor) }
        } else { None };
        let seconds = if self.s.separates_learning() && self.s.f.deletion_strategy == "local" && self.s.c.plasticity && !stable {
            let lane = e.inhibition_lane();
            self.s.crossing_seconds(e.weight,e.decay_age,e.half_life,floor)
                .zip(self.s.crossing_seconds(lane.weight,lane.decay_age,lane.half_life,floor)).map(|(a,b)|a.max(b))
        } else { seconds };
        let due = if seconds.is_some() && self.deletion_phase && e.structural_weight() < floor
            && self.time % self.s.f.structure_check_interval_us as u128 == 0 { Some(self.time) }
            else { self.deletion_time(at(&e.state_us), seconds) };
        self.timer((2,e.source,e.target), due);
        if let Some(t) = &e.novelty_deadline_us { self.timer((4,e.source,e.target),Some(at(t))); }
    }
    fn can_emit(&self, n: &Node) -> bool {
        (n.activation > 0.0 && n.activation >= self.s.f.activation_send_threshold)
            || (self.s.c.inhibition && n.inhibition > 0.0 && n.inhibition >= self.s.f.inhibition_send_threshold)
            || n.pending_inhibition > 0.0
    }
    fn pulse(&mut self, n: &Node, after: bool) {
        let c = &self.s.c;
        let key = (0, n.id, 0);
        if n.sleeping
            || self.silenced_nodes.contains(&n.id)
            || !self.can_emit(n)
        {
            self.timer(key, None);
            return;
        }
        if self.deadlines.contains_key(&key) && !after {
            return;
        }
        let p = c.propagation_interval_us as u128;
        let t = if after || self.s.choice("propagation_phase", "asynchronous") {
            self.time + p
        } else {
            let t = p.max(self.time.div_ceil(p) * p);
            if V5 {
                t.max(self.completed_emission_us + p)
            } else {
                t
            }
        };
        self.timer(key, Some(t));
    }
    fn birth(&mut self, channel: u32) -> Option<u64> {
        if self
            .s
            .c
            .max_nodes
            .is_some_and(|max| self.nodes.len() as u64 >= max)
        {
            return None;
        }
        let id = node_address(channel);
        self.birth_count += 1;
        let t = stamp(self.time);
        let region = word(self.s.uint("energy_seed"), 1, id) % self.s.uint("energy_region_count");
        let n = Node {
            id,
            channel,
            birth_serial: self.birth_count,
            activation: 0.0,
            inhibition: 0.0,
            trace: 0.0,
            support: 0.0,
            stability: 0.0,
            direct: 0.0,
            associative: 0.0,
            touches: 0,
            last_touch_us: t.clone(),
            birth_us: t.clone(),
            local_plasticity: 1.0,
            pending_inhibition: 0.0,
            generated_inhibition: 0.0,
            state_us: t.clone(),
            half_life: self.s.r.memory_half_life_min_s,
                        decay_age: 0.0,
            fatigue: 0.0,
            salience: 0.0,
            isolated_us: t.clone(),
            region,
            reserve: 0.0,
            energy_us: t,
            sleeping: false,
            last_emit_us: if V5 { Some("0".into()) } else { None },
        };
        self.nodes.insert(id, n);
        self.regions.entry(region).or_default().insert(id);
        if self.s.c.energy_simulation_enabled && self.s.c.energy_starvation_damage_enabled {
            self.timer(
                (5, id, 0),
                Some(self.time + self.s.c.propagation_interval_us as u128),
            );
        }
        Some(id)
    }
    fn expense(&mut self, n: &mut Node, value: f64, cost: f64, kind: Cost) -> f64 {
        if !self.s.c.energy_simulation_enabled || cost <= 0.0 {
            return value;
        }
        if self.s.choice("energy_model", "global-ledger") {
            return self.energy.afford(value, cost, kind);
        }
        let accepted = value.min(n.reserve / cost);
        let used = n.reserve.min(accepted * cost);
        n.reserve = (n.reserve - used).max(0.0);
        match kind {
            Cost::Direct => self.energy.consumed_direct += used,
            Cost::Associative => self.energy.consumed_associative += used,
            Cost::Inhibition => self.energy.consumed_inhibition += used,
            Cost::Maintenance => self.energy.consumed_maintenance += used,
        };
        self.energy.unserved_total += (value * cost - used).max(0.0);
        accepted
    }
    fn outgoing_keys(&self, id: u64) -> Vec<Key> {
        self.outgoing
            .get(&id)
            .map(|s| s.iter().copied().collect())
            .unwrap_or_default()
    }
    fn incident_keys(&self, id: u64) -> Vec<Key> {
        self.incident
            .get(&id)
            .map(|s| s.iter().copied().collect())
            .unwrap_or_default()
    }
    fn maintenance(&mut self, n: &mut Node) {
        let dt = (self.time - at(&n.energy_us)) as f64 / 1e6;
        n.energy_us = stamp(self.time);
        if !self.s.c.energy_simulation_enabled
            || !self.s.c.energy_starvation_damage_enabled
            || dt <= 0.0
        {
            return;
        }
        let required = dt
            * (self.s.c.energy_maintenance_cost_per_node
                + self.outgoing_keys(n.id).len() as f64
                    * self.s.c.energy_maintenance_cost_per_edge);
        let paid = self.expense(n, required, 1.0, Cost::Maintenance);
        let deficit = if required > 0.0 {
            dt * (1.0 - paid / required)
        } else {
            0.0
        };
        let factor = (-self.s.c.energy_starvation_structural_decay * deficit).exp();
        n.support *= factor;
        for key in self.outgoing_keys(n.id) {
            let mut e = self.settle_edge(key);
            e.weight *= factor;
            if let Some(w) = e.inhibition_weight.as_mut() { *w *= factor; }
            e.stability *= factor;
            self.edges.insert(key, e.clone());
            self.edge_timer(&e);
        }
    }
    fn uptake(&mut self, region: u64) {
        let ids: Vec<_> = self
            .regions
            .get(&region)
            .map(|s| s.iter().copied().collect())
            .unwrap_or_default();
        for &id in &ids {
            let mut n = self.settle_node(id);
            self.maintenance(&mut n);
            self.nodes.insert(id, n);
        }
        let requests: Vec<_> = ids
            .iter()
            .map(|id| {
                (
                    *id,
                    (self.s.num("energy_node_capacity") - self.nodes[id].reserve).max(0.0),
                )
            })
            .collect();
        let total: f64 = requests.iter().map(|(_, v)| v).sum();
        let amount = self.pools[&region].min(total);
        if total > 0.0 {
            for (id, v) in requests {
                self.nodes.get_mut(&id).unwrap().reserve += amount * (v / total);
            }
            self.pools
                .insert(region, (self.pools[&region] - amount).max(0.0));
        }
    }
    fn touch(&mut self, id: u64, raw: f64, direct: bool, intensity: f64, drive: f64) -> (f64, f64) {
        if !self.nodes.contains_key(&id) || self.silenced_nodes.contains(&id) || raw <= 0.0 {
            return (0.0, 0.0);
        }
        let mut n = self.settle_node(id);
        if n.sleeping {
            if !self.s.r.revival_enabled || raw < self.s.r.node_wake_threshold.unwrap() {
                return (0.0, 0.0);
            }
            n.sleeping = false;
            *self.audit.get_mut("nodes_awakened").unwrap() += 1;
        }
        self.maintenance(&mut n);
        let unified = self.s.choice("reception_mode", "unified");
        let arrived = if direct || unified {
            self.expense(&mut n, raw, self.s.c.energy_direct_cost, Cost::Direct)
        } else {
            raw
        };
        let response = self.response(&n);
        let amount = arrived * response;
        *self.transport.get_mut("received").unwrap() += arrived;
        if V5 && amount <= 0.0 {
            self.nodes.insert(id, n.clone());
            self.node_timers(&n);
            self.pulse(&n, false);
            return (0.0, 0.0);
        }
        let initial = n.touches == 0;
        let delta = (1.0 - n.activation).min(amount);
        n.activation += delta;
        *self.transport.get_mut("activated").unwrap() += delta;
        n.trace = (n.trace + amount).min(1.0);
        if direct {
            n.direct = n.direct.max(amount);
        } else {
            n.associative += amount;
        }
        n.last_touch_us = stamp(self.time);
        n.isolated_us = stamp(self.time);
        n.touches += 1;
        let c = &self.s.c;
        let r = &self.s.r;
        if c.inhibition {
            n.generated_inhibition += delta * c.inhibition_gain;
        }
        let strength = ((if unified && !V5 { raw } else { intensity }) - 1.0).max(0.0);
        n.salience += amount * strength;
        if r.strong_fatigue_enabled {
            n.fatigue += amount * strength * r.strong_fatigue_gain;
        }
        let mut impulse = 0.0;
        if c.plasticity {
            let dose = amount * 0.1 * (1.0 + n.salience);
            if r.node_retention_mode == "automatic" {
                if self.s.f.retention_growth_enabled { n.half_life = grow(n.half_life, dose, r); }
                let before = n.support;
                n.support = 1.0 - (1.0 - n.support) * (-r.memory_weight_learning_rate * dose).exp();
                if n.support > before && self.s.choice("reinforcement_age_policy", "reset") { n.decay_age = 0.0; }
            } else {
                n.support = (n.support + c.support_gain * amount).min(1.0);
            }
            if direct || unified {
                let actual_drive = if V5 {
                    let expected = raw * response;
                    drive
                        * if expected > 0.0 {
                            amount / expected
                        } else {
                            0.0
                        }
                } else {
                    raw
                };
                impulse = c.consolidation_cap.min(
                    actual_drive
                        * n.local_plasticity
                        * (c.first_gain * if initial { 1.0 } else { 0.0 }
                            + c.repeat_gain
                            + c.intensity_gain * strength),
                );
            }
            n.stability = (n.stability + 0.5 * c.stability_gain * n.activation).min(1.0);
            n.local_plasticity = 0.12_f64.max(1.0 - 0.72 * n.stability);
        }
        let novelty_keys = if V5 {
            self.pending_novelty
                .get(&id)
                .map(|keys| keys.iter().copied().collect())
                .unwrap_or_default()
        } else {
            self.incident_keys(id)
        };
        for key in novelty_keys {
            let e = self.edges.get_mut(&key).unwrap();
            if c.plasticity && e.novelty_deadline_us.is_some() && (!direct || (unified && !V5)) {
                if key.0 == id {
                    e.novelty_source += amount;
                } else {
                    e.novelty_target += amount;
                }
            }
        }
        if n.activation > 0.0 {
            self.active.insert(id);
            self.life = "active".into();
            self.quiet = None;
        }
        self.nodes.insert(id, n.clone());
        self.node_timers(&n);
        self.pulse(&n, false);
        (amount, impulse)
    }
    fn distance(&self, a: u64, b: u64) -> f64 {
        crate::spatial::position(&self.s.c, a)
            .iter()
            .zip(crate::spatial::position(&self.s.c, b))
            .map(|(a, b)| (a - b).powi(2))
            .sum::<f64>()
            .sqrt()
    }
    fn associate(&mut self, contacts: Vec<Contact>) {
        if !self.s.c.plasticity {
            return;
        }
        let connected: BTreeSet<_> = if V5 {
            contacts
                .iter()
                .filter_map(|(id, _, _)| {
                    self.incident
                        .get(id)
                        .is_some_and(|keys| !keys.is_empty())
                        .then_some(*id)
                })
                .collect()
        } else {
            BTreeSet::new()
        };
        for &(a, av, ai) in &contacts {
            for &(b, bv, bi) in &contacts {
                let key = (a, b);
                if a == b
                    || self.silenced_edges.contains(&key)
                    || !self.nodes.contains_key(&a)
                    || !self.nodes.contains_key(&b)
                {
                    continue;
                }
                let c = &self.s.c;
                let score = if V5 {
                    self.nodes[&a].activation * self.nodes[&b].activation
                } else {
                    av * bv
                };
                if score <= 0.0
                    || (!self.edges.contains_key(&key)
                        && score < c.edge_birth_activation_product_min)
                {
                    continue;
                }
                if c.spatial_embedding
                    && c.neighborhood_enabled
                    && self.distance(a, b) > c.spatial_radius
                {
                    continue;
                }
                let impulse = (ai + bi).min(c.consolidation_cap);
                let e = if !self.edges.contains_key(&key) {
                    if c.max_edges
                        .is_some_and(|max| self.edges.len() as u64 >= max)
                    {
                        continue;
                    }
                    let t = stamp(self.time);
                    let mut e = Edge {
                        source: a,
                        target: b,
                        weight: 1.0_f64.min(c.birth_weight * (0.5 + score) + 0.18 * impulse),
                        stability: if self.s.stability_grows() { impulse.min(1.0) } else { 0.0 },
                        eligibility: impulse,
                        touches: 0,
                        birth_us: t.clone(),
                        last_touch_us: t.clone(),
                        state_us: t,
                        half_life: self.s.r.memory_half_life_min_s,
                        decay_age: 0.0,
                        last_pass_us: "0".into(),
                        sleeping: false,
                        inhibition_weight: None,
                        inhibition_short_term: None,
                        inhibition_learning: None,
                        short_term: None,
                        fast: None,
                        novelty_deadline_us: None,
                        novelty_source: 0.0,
                        novelty_target: 0.0,
                        completed_period_us: if V5 {
                            Some(stamp(self.completed_period(self.time)))
                        } else {
                            None
                        },
                    };
                    let novelty_eligible = if V5 {
                        connected.contains(&a) || connected.contains(&b)
                    } else {
                        self.incident.get(&a).is_some_and(|s| !s.is_empty())
                            || self.incident.get(&b).is_some_and(|s| !s.is_empty())
                    };
                    if novelty_eligible {
                        if self.s.novelty == "arrival-window" && (!V5 || c.local_novelty_gain > 0.0)
                        {
                            let boundary = if V5 {
                                let period = c.propagation_interval_us as u128;
                                period
                                    .max(self.time.div_ceil(period) * period)
                                    .max(self.completed_emission_us + period)
                            } else {
                                self.time + c.propagation_interval_us as u128
                            };
                            e.novelty_deadline_us = Some(stamp(boundary + c.delay_us as u128));
                            if V5 {
                                e.novelty_source = self.nodes[&a].associative;
                                e.novelty_target = self.nodes[&b].associative;
                            }
                        } else {
                            let reentry = if self.s.choice("reception_mode", "unified") && !V5 {
                                av.max(bv)
                            } else {
                                self.nodes[&a].associative.max(self.nodes[&b].associative)
                            };
                            let bonus = if reentry > 0.0 {
                                c.local_novelty_gain
                                    * (1.0 - reentry / c.novelty_touch_reference).max(0.0)
                            } else {
                                0.0
                            };
                            let before = e.weight;
                            e.weight = (e.weight + bonus).min(1.0);
                            if let Some(w) = e.inhibition_weight.as_mut() {
                                let prior = *w;
                                *w = (*w + bonus).min(1.0);
                                if *w > prior && self.s.f.reinforcement_age_policy == "reset" {
                                    if let Some(l)=e.inhibition_learning.as_mut() { l.decay_age=0.0; } else { e.decay_age=0.0; }
                                }
                            }
                            if e.weight > before && self.s.choice("reinforcement_age_policy", "reset") { e.decay_age = 0.0; }
                            if self.s.stability_grows() {
                                e.stability = (e.stability + bonus).min(1.0);
                                if let Some(l)=e.inhibition_learning.as_mut() { l.stability=(l.stability+bonus).min(1.0); }
                            }
                        }
                    }
                    if self.s.separates_weights() { e.inhibition_weight = Some(e.weight); }
                    if self.s.separates_learning() { e.inhibition_learning = Some(e.learning()); }
                    self.outgoing.entry(a).or_default().insert(key);
                    self.incident.entry(a).or_default().insert(key);
                    self.incident.entry(b).or_default().insert(key);
                    e
                } else {
                    let mut e = self.settle_edge(key);
                    if e.sleeping {
                        continue;
                    }
                    let mut lane = e.inhibition_learning.map(|_| e.inhibition_lane());
                    let c = &self.s.c;
                    let previous = if self.s.choice("propagation_phase", "aligned") { self.completed_period(self.time) }
                        else { at(self.nodes[&a].last_emit_us.as_ref().unwrap()) };
                    if self.s.consolidate {
                        let passed = at(&e.last_pass_us);
                        let previous = if V5 {
                            if self.s.choice("propagation_phase", "aligned") {
                                self.completed_period(self.time)
                            } else {
                                at(self.nodes[&a].last_emit_us.as_ref().unwrap())
                            }
                        } else {
                            self.time
                        };
                        let internal = if passed == previous && (!V5 || passed > 0) {
                            1.0
                        } else {
                            0.45
                        };
                        if let Some(w) = e.inhibition_weight.as_mut().filter(|_| lane.is_none()) {
                            let before = *w;
                            *w = (*w + c.learning_rate * score * internal * (1.0 - *w) + 0.08 * impulse).min(1.0);
                            if *w > before && self.s.f.reinforcement_age_policy == "reset" { e.decay_age = 0.0; }
                        }
                        let before = e.weight;
                        e.weight = (e.weight
                            + c.learning_rate * score * internal * (1.0 - e.weight)
                            + 0.08 * impulse)
                            .min(1.0);
                        if e.weight > before && self.s.choice("reinforcement_age_policy", "reset") { e.decay_age = 0.0; }
                        if self.s.stability_grows() {
                            e.stability = (e.stability + c.stability_gain * score * (1.0 + (e.touches as f64).ln_1p()) + impulse).min(1.0);
                        }
                    }
                    e.eligibility = (e.eligibility + 0.3 * score + 0.25 * impulse).min(1.0);
                    e.touches += 1;
                    e.last_touch_us = stamp(self.time);
                    if let Some(i) = lane.as_mut() {
                        if self.s.consolidate {
                            let internal = if at(&i.last_pass_us) > 0 && at(&i.last_pass_us) == previous { 1.0 } else { 0.45 };
                            let before = i.weight;
                            i.weight = (i.weight + c.learning_rate * score * internal * (1.0 - i.weight) + 0.08 * impulse).min(1.0);
                            if i.weight > before && self.s.f.reinforcement_age_policy == "reset" { i.decay_age = 0.0; }
                            if self.s.stability_grows() { i.stability = (i.stability + c.stability_gain * score * (1.0 + (i.touches as f64).ln_1p()) + impulse).min(1.0); }
                        }
                        i.eligibility = (i.eligibility + 0.3 * score + 0.25 * impulse).min(1.0);
                        i.touches += 1; i.last_touch_us = stamp(self.time);
                        e.merge_inhibition_lane(i);
                    }
                    e
                };
                if V5 && e.novelty_deadline_us.is_some() {
                    self.pending_novelty.entry(a).or_default().insert(key);
                    self.pending_novelty.entry(b).or_default().insert(key);
                }
                self.edges.insert(key, e.clone());
                self.edge_timer(&e);
                self.timer((3, a, 0), None);
                self.timer((3, b, 0), None);
            }
        }
    }
    fn features(&self, n: &Node) -> Vec<f64> {
        self.feature_values(n).to_vec()
    }
    fn feature_values(&self, n: &Node) -> [f64; 4] {
        [
            n.activation,
            n.trace,
            n.inhibition / (1.0 + n.inhibition),
            (-((self.time - at(&n.last_touch_us)) as f64 / 1e6) / self.s.o.context_tau_s).exp(),
        ]
    }
    fn receive(&mut self, packets: Vec<Packet>, drives: &BTreeMap<(i128, u64), f64>) -> Result<()> {
        if V5 && self.s.choice("arrival_mode", "sequential") {
            let mut ordered: Vec<Packet> = Vec::new();
            let mut internal: Option<usize> = None;
            for (serial, messages, direct, intensity) in packets {
                if direct {
                    ordered.push((serial, messages, direct, intensity));
                } else if let Some(index) = internal {
                    ordered[index].1.extend(messages);
                } else {
                    internal = Some(ordered.len());
                    ordered.push((serial, messages, direct, intensity));
                }
            }
            for packet in ordered {
                self.receive_batch(vec![packet], drives)?;
            }
            Ok(())
        } else {
            self.receive_batch(packets, drives)
        }
    }
    fn receive_batch(
        &mut self,
        packets: Vec<Packet>,
        drives: &BTreeMap<(i128, u64), f64>,
    ) -> Result<()> {
        type Arrival = (i128, i64, f64, Vec<f64>, bool, f64);
        let mut inboxes: BTreeMap<u64, Vec<Arrival>> = BTreeMap::new();
        let mut cohorts: BTreeMap<i128, Vec<Contact>> = BTreeMap::new();
        for (serial, messages, direct, intensity) in packets {
            for (source, target, value, features) in messages {
                inboxes
                    .entry(target)
                    .or_default()
                    .push((serial, source, value, features, direct, intensity));
            }
        }
        for (id, batch) in inboxes {
            if !self.nodes.contains_key(&id) {
                continue;
            }
            let groups = if V5 || self.s.choice("arrival_mode", "coincident") {
                vec![batch]
            } else {
                batch.into_iter().map(|m| vec![m]).collect()
            };
            for group in groups {
                let values: Vec<_> = group.iter().map(|m| m.2).collect();
                let unified = self.s.choice("reception_mode", "unified");
                let use_context = self.s.o.context_enabled
                    && self.s.o.context_mix > 0.0
                    && (unified || !group.iter().any(|m| m.4));
                let (value, coeff) = if use_context {
                    let n = self.settle_node(id);
                    if V5
                        && group.len() == 1
                        && group[0].3.len() == 4
                        && group[0]
                            .3
                            .iter()
                            .all(|v| v.is_finite() && (-1.0..=1.0).contains(v))
                        && values[0].is_finite()
                        && (0.0..=1e12).contains(&values[0])
                    {
                        // A singleton has exp(score-score)=1, hence weight=1.
                        // Keep the original coefficient arithmetic and settle.
                        let factor = (1.0 - self.s.o.context_mix) + self.s.o.context_mix;
                        (values[0] * factor, vec![factor])
                    } else {
                        local_attention(
                            &self.features(&n),
                            &group.iter().map(|m| m.3.clone()).collect::<Vec<_>>(),
                            &values,
                            self.s.o.context_temperature,
                            self.s.o.context_mix,
                        )?
                    }
                } else {
                    (values.iter().sum(), vec![1.0; values.len()])
                };
                let direct = group.iter().all(|m| m.4);
                let intensity = group.iter().map(|m| m.5).fold(0.0, f64::max);
                let drive: f64 = if V5 {
                    group
                        .iter()
                        .zip(&coeff)
                        .filter(|(m, _)| m.4)
                        .map(|(m, factor)| drives.get(&(m.0, id)).copied().unwrap_or(m.2) * factor)
                        .sum()
                } else {
                    value
                };
                let (amount, impulse) = self.touch(id, value, direct, intensity, drive);
                if V5 && use_context && !unified && !direct {
                    *self.transport.get_mut("received").unwrap() +=
                        values.iter().sum::<f64>() - value;
                }
                if amount <= 0.0 {
                    continue;
                }
                let total: f64 = values.iter().zip(&coeff).map(|(v, k)| v * k).sum();
                for (m, k) in group.iter().zip(coeff) {
                    if (unified && !V5) || m.4 {
                        let f = if total > 0.0 { m.2 * k / total } else { 0.0 };
                        cohorts
                            .entry(m.0)
                            .or_default()
                            .push((id, amount * f, impulse * f));
                    }
                }
            }
        }
        for (_, contacts) in cohorts {
            let mut merged: BTreeMap<u64, (f64, f64)> = BTreeMap::new();
            for (id, a, i) in contacts {
                let v = merged.entry(id).or_default();
                v.0 += a;
                v.1 += i;
            }
            self.associate(merged.into_iter().map(|(id, (a, i))| (id, a, i)).collect());
        }
        Ok(())
    }
    fn emit(&mut self, id: u64) -> Result<()> {
        if !self.nodes.contains_key(&id) || self.silenced_nodes.contains(&id) { return Ok(()); }
        let mut n = self.settle_node(id);
        self.maintenance(&mut n);
        if self.s.c.inhibition { n.inhibition = self.soft(n.inhibition + n.pending_inhibition); }
        n.pending_inhibition = 0.0;
        let features = self.feature_values(&n);
        let mut positive = n.activation * self.response(&n) * self.s.c.propagation_rate * self.s.c.propagation_interval_us as f64 / 1e6;
        if n.activation < self.s.c.propagation_activation_min.max(self.s.f.activation_send_threshold) { positive = 0.0; }
        if self.s.c.inhibition { n.inhibition = self.soft(n.inhibition + n.generated_inhibition); }
        n.generated_inhibition = 0.0;
        let mut negative = if self.s.c.inhibition { n.inhibition * (self.s.c.inhibition_diffusion_rate * self.s.c.propagation_interval_us as f64 / 1e6).min(1.0) } else { 0.0 };
        if self.s.f.inhibition_sender_gate_enabled && negative < self.s.c.inhibition_propagation_min { negative = 0.0; }
        if n.inhibition < self.s.f.inhibition_send_threshold { negative = 0.0; }
        let keys: Vec<_> = self.outgoing_keys(id).into_iter().filter(|k| !self.silenced_edges.contains(k)).collect();
        let count = keys.len() as f64;
        *self.transport.get_mut("offered_excitation").unwrap() += count * positive;
        *self.transport.get_mut("offered_inhibition").unwrap() += count * negative;
        let requested = count * positive * self.s.c.energy_associative_cost + count * negative * self.s.c.energy_inhibition_cost;
        let mut scale = 1.0_f64;
        if self.s.c.energy_simulation_enabled && requested > 0.0 {
            let available = if self.s.choice("energy_model", "global-ledger") { self.energy.reserve } else { n.reserve };
            scale = (available / requested).min(1.0);
            self.expense(&mut n, count * positive * scale, self.s.c.energy_associative_cost, Cost::Associative);
            self.expense(&mut n, count * negative * scale, self.s.c.energy_inhibition_cost, Cost::Inhibition);
            self.energy.unserved_total += requested * (1.0 - scale);
        }
        *self.transport.get_mut("blocked_energy").unwrap() += count * (positive + negative) * (1.0 - scale);
        positive *= scale;
        negative *= scale;
        let mut messages: Vec<Message> = Vec::new();
        for key in &keys {
            let mut e = self.settle_edge(*key);
            if positive <= 0.0 && negative <= 0.0 { continue; }
            if e.sleeping { *self.transport.get_mut("blocked_dormancy").unwrap() += positive + negative; continue; }
            let o = &self.s.o;
            let fast = e.fast.unwrap_or_else(|| FastTrace { time_us: e.birth_us, ..Default::default() });
            let fast_value = if o.fast_enabled { fast.projected(self.time, &o.fast_trace())? } else { 0.0 };
            let weight = if o.fast_enabled { (e.weight + o.fast_gain * fast_value).min(1.0) } else { e.weight };
            let mut lane = e.inhibition_learning.map(|_| e.inhibition_lane());
            let i_fast_value = if let Some(i) = &lane {
                let fast = i.fast.unwrap_or_else(|| FastTrace { time_us:e.birth_us, ..Default::default() });
                if o.fast_enabled { fast.projected(self.time,&o.fast_trace())? } else { 0.0 }
            } else { fast_value };
            let i_base = e.inhibition_weight.unwrap_or(e.weight);
            let i_weight = if o.fast_enabled { (i_base + o.fast_gain * i_fast_value).min(1.0) } else { i_base };
            let distance = if self.s.c.spatial_embedding && self.s.c.neighborhood_enabled {
                (-self.distance(e.source,e.target) / self.s.c.spatial_radius).exp()
            } else { 1.0 };
            let (mut p_offer, mut n_offer) = (positive, negative);
            if self.s.f.resource_precheck_enabled && self.s.f.signal_threshold_enabled {
                if weight * p_offer * distance < self.s.signal_threshold_for(false) { p_offer = 0.0; }
                if i_weight * n_offer * distance < self.s.signal_threshold_for(true) { n_offer = 0.0; }
                if p_offer <= 0.0 && n_offer <= 0.0 { continue; }
            }
            let (fraction, i_fraction) = if self.s.separates_resources() {
                (if p_offer > 0.0 { self.release_resource(&mut e.short_term, e.birth_us)? } else { 1.0 },
                 if n_offer > 0.0 { self.release_resource(&mut e.inhibition_short_term, e.birth_us)? } else { 1.0 })
            } else {
                let fraction = self.release_resource(&mut e.short_term, e.birth_us)?;
                (fraction, fraction)
            };
            let mut transmitted = [0.0; 2];
            for (i, signal) in [p_offer, n_offer].into_iter().enumerate() {
                let (signal_weight, signal_fraction, base_weight) = if i == 1 { (i_weight, i_fraction, i_base) } else { (weight, fraction, e.weight) };
                let mut amount = signal_weight * signal * signal_fraction * distance;
                *self.transport.get_mut("sent").unwrap() += amount;
                if (self.s.f.weight_gate_enabled && base_weight < self.s.num("weight_gate"))
                    || (self.s.f.signal_threshold_enabled && amount < self.s.signal_threshold_for(i == 1)) {
                    let reason = if self.s.f.weight_gate_enabled && base_weight < self.s.num("weight_gate") { "blocked_weight" } else { "blocked_signal" };
                    *self.transport.get_mut(reason).unwrap() += amount;
                    *self.transport.get_mut("discarded").unwrap() += amount;
                    amount = 0.0;
                }
                transmitted[i] = amount;
            }
            let [pos, neg] = transmitted;
            *self.transport.get_mut("transmitted_excitation").unwrap() += pos;
            *self.transport.get_mut("transmitted_inhibition").unwrap() += neg;
            if pos > 0.0 { messages.push((id as i64, e.target, pos, features.to_vec())); }
            if neg > 0.0 { *self.inhibition_batch.entry(e.target).or_default() += neg; }
            if let Some(i) = lane.as_mut() {
                if pos > 0.0 { e.last_pass_us = stamp(self.time); }
                if neg > 0.0 && self.s.f.inhibition_updates_usage { i.last_pass_us = stamp(self.time); }
                self.learn_lane(&mut e,pos,self.s.f.activation_weight_reinforcement_enabled,fast_value)?;
                self.learn_lane(i,if self.s.f.inhibitory_learning_enabled { neg } else { 0.0 },
                                self.s.f.inhibition_weight_reinforcement_enabled,i_fast_value)?;
                e.merge_inhibition_lane(i);
                if self.s.c.plasticity && (pos > 0.0 || (neg > 0.0 && self.s.f.inhibitory_learning_enabled)) { self.edge_timer(&e); }
            } else {
                if pos > 0.0 || (neg > 0.0 && self.s.f.inhibition_updates_usage) { e.last_pass_us = stamp(self.time); }
                let learned = pos + if self.s.f.inhibitory_learning_enabled { neg } else { 0.0 };
                if self.s.c.plasticity && learned > 0.0 {
                    if o.fast_enabled { e.fast = Some(FastTrace::transmit_projected(fast_value, learned, self.time, &o.fast_trace())?); }
                    e.eligibility = (0.7 * e.eligibility + learned).min(1.0);
                    if self.s.consolidate {
                        let before = e.weight;
                        let mut weight_signal = if self.s.f.activation_weight_reinforcement_enabled { pos } else { 0.0 }
                            + if self.s.f.inhibitory_learning_enabled && self.s.f.inhibition_weight_reinforcement_enabled { neg } else { 0.0 };
                        if let Some(w) = e.inhibition_weight.as_mut() {
                            let prior = *w;
                            let i_signal = if self.s.f.inhibitory_learning_enabled && self.s.f.inhibition_weight_reinforcement_enabled { neg } else { 0.0 };
                            *w = (*w + self.s.c.associative_gain * i_signal).min(1.0);
                            if *w > prior && self.s.f.reinforcement_age_policy == "reset" {
                                    if let Some(l)=e.inhibition_learning.as_mut() { l.decay_age=0.0; } else { e.decay_age=0.0; }
                                }
                            weight_signal = if self.s.f.activation_weight_reinforcement_enabled { pos } else { 0.0 };
                        }
                        e.weight = (e.weight + self.s.c.associative_gain * weight_signal).min(1.0);
                        if e.weight > before && self.s.choice("reinforcement_age_policy", "reset") { e.decay_age = 0.0; }
                        if self.s.stability_grows() { e.stability = (e.stability + self.s.c.stability_gain * learned).min(1.0); }
                        if self.s.f.retention_growth_enabled { e.half_life = grow(e.half_life, learned * 0.1, &self.s.r); }
                    }
                    e.touches += 1;
                    e.last_touch_us = stamp(self.time);
                    self.edge_timer(&e);
                }
            }
            self.edges.insert(*key,e);
        }
        if !messages.is_empty() { self.event_payload(self.time + self.s.c.delay_us as u128, "signal", signal_payload(messages)); }
        if !keys.is_empty() { n.inhibition = (n.inhibition - negative).max(0.0); }
        if self.s.r.revival_enabled && positive > 0.0 {
            for key in self.incident_keys(id) {
                if self.edges[&key].sleeping && !self.silenced_edges.contains(&key) {
                    self.event(self.time + self.s.c.delay_us as u128, "wake", json!({"edge":key,"sender":id,"value":positive}));
                }
            }
        }
        n.last_emit_us = Some(stamp(self.time));
        n.direct = 0.0; n.associative = 0.0;
        self.nodes.insert(id,n.clone());
        self.node_timers(&n);
        self.pulse(&n,true);
        Ok(())
    }
    fn learn_lane(&self, e: &mut Edge, signal: f64, reinforce: bool, fast_value: f64) -> Result<()> {
        if !self.s.c.plasticity || signal <= 0.0 { return Ok(()); }
        if self.s.o.fast_enabled { e.fast=Some(FastTrace::transmit_projected(fast_value,signal,self.time,&self.s.o.fast_trace())?); }
        e.eligibility=(0.7*e.eligibility+signal).min(1.0);
        if self.s.consolidate {
            if reinforce {
                let before=e.weight;
                e.weight=(e.weight+self.s.c.associative_gain*signal).min(1.0);
                if e.weight>before && self.s.f.reinforcement_age_policy=="reset" { e.decay_age=0.0; }
            }
            if self.s.stability_grows() { e.stability=(e.stability+self.s.c.stability_gain*signal).min(1.0); }
            if self.s.f.retention_growth_enabled { e.half_life=grow(e.half_life,signal*0.1,&self.s.r); }
        }
        e.touches+=1; e.last_touch_us=stamp(self.time);
        Ok(())
    }
    fn release_resource(&self, state: &mut Option<ShortTermState>, birth: Timestamp) -> Result<f64> {
        let o = &self.s.o;
        if !o.stp_enabled { return Ok(1.0); }
        let mut st = state.unwrap_or_else(|| ShortTermState { time_us: birth, ..Default::default() });
        if !self.s.depletion {
            st = st.recovered_validated(self.time, &o.short_term())?;
            st.available = 1.0; st.active = 0.0;
        }
        let (mut st, fraction) = st.release_validated(self.time, &o.short_term())?;
        if !self.s.depletion { st.available = 1.0; st.active = 0.0; }
        *state = Some(st);
        Ok(fraction)
    }
    fn remove_edge(&mut self, key: Key, explicit: bool) {
        if !self.edges.contains_key(&key) {
            return;
        }
        let mut e = self.settle_edge(key);
        if !explicit
            && !e.sleeping
            && self.s.r.dormant_traces_enabled
            && e.structural_weight() >= self.s.r.dormant_prune_weight
        {
            e.sleeping = true;
            self.edges.insert(key, e.clone());
            self.edge_timer(&e);
        } else {
            self.edges.remove(&key);
            if V5 {
                self.drop_novelty_index(key);
            }
            if let Some(s) = self.outgoing.get_mut(&e.source) {
                s.remove(&key);
            }
            for id in [key.0, key.1] {
                if let Some(s) = self.incident.get_mut(&id) {
                    s.remove(&key);
                }
            }
            self.timer((2, key.0, key.1), None);
            self.timer((4, key.0, key.1), None);
            self.timer((7, key.0, key.1), None);
            *self.audit.get_mut("edges_deleted").unwrap() += 1;
        }
        for id in [key.0, key.1] {
            if self.nodes.contains_key(&id) {
                let mut n = self.settle_node(id);
                if !self.connected(id) {
                    n.isolated_us = stamp(self.time);
                    n.sleeping = n.activation == 0.0
                        && self.incident.get(&id).is_some_and(|s| !s.is_empty());
                }
                self.nodes.insert(id, n.clone());
                self.node_timers(&n);
            }
        }
    }
    fn drop_novelty_index(&mut self, key: Key) {
        for id in [key.0, key.1] {
            if let Some(keys) = self.pending_novelty.get_mut(&id) {
                keys.remove(&key);
                if keys.is_empty() {
                    self.pending_novelty.remove(&id);
                }
            }
        }
    }
    fn delete_node(&mut self, id: u64) {
        if !self.nodes.contains_key(&id) {
            return;
        }
        for key in self.incident_keys(id) {
            self.remove_edge(key, true);
        }
        let n = self.nodes.remove(&id).unwrap();
        self.regions.get_mut(&n.region).unwrap().remove(&id);
        self.outgoing.remove(&id);
        self.incident.remove(&id);
        self.active.remove(&id);
        if self.life != "waiting" && self.active.is_empty() && self.quiet.is_none() {
            self.quiet = Some(self.time);
        }
        for kind in [0, 1, 3, 5] {
            self.timer((kind, id, 0), None);
        }
        self.energy.discarded_total += n.reserve;
        *self.audit.get_mut("nodes_deleted").unwrap() += 1;
    }
    fn expiry(&mut self, kind: u8, a: u64, b: u64) {
        if kind == 7 {
            let key = (a,b);
            if !self.edges.contains_key(&key) || !self.s.c.plasticity || self.s.r.adaptive() { return; }
            *self.audit.get_mut("expiry_checks").unwrap() += 1;
            let mut e = self.settle_edge(key);
            let c = &self.s.c;
            let mut lane = e.inhibition_learning.map(|_| e.inhibition_lane());
            let dt = c.propagation_interval_us as f64 / 1e6;
            if c.eligibility_decay_enabled { e.eligibility *= (-dt / c.eligibility_tau).exp(); }
            if c.stability_decay_enabled && self.s.f.stability_relaxation_enabled {
                e.stability = (e.stability - dt / c.stability_tau * (1.0 - e.eligibility)).max(0.0);
            }
            if at(&e.last_pass_us) != self.time {
                let factor = (1.0 - 0.1 * c.forgetting_rate * (1.0 - (0.08 + 0.92 * e.stability))).max(0.0).powf(dt / 0.1);
                e.weight *= factor;
                if let Some(w) = e.inhibition_weight.as_mut() { *w *= factor; }
            }
            if let Some(i)=lane.as_mut() {
                if c.eligibility_decay_enabled { i.eligibility*=(-dt/c.eligibility_tau).exp(); }
                if c.stability_decay_enabled && self.s.f.stability_relaxation_enabled {
                    i.stability=(i.stability-dt/c.stability_tau*(1.0-i.eligibility)).max(0.0);
                }
                if at(&i.last_pass_us)!=self.time {
                    i.weight*=(1.0-0.1*c.forgetting_rate*(1.0-(0.08+0.92*i.stability))).max(0.0).powf(dt/0.1);
                }
                e.merge_inhibition_lane(i);
            }
            e.completed_period_us = Some(stamp(self.time));
            self.edges.insert(key,e);
            self.edge_timer(&e);
            return;
        }
        if kind == 6 {
            *self.audit.get_mut("scan_visits").unwrap() += (self.edges.len() + self.nodes.len()) as u64;
            let keys: Vec<_> = self.edges.keys().copied().collect();
            for key in keys {
                let e = self.settle_edge(key);
                let floor = if e.sleeping { self.s.r.dormant_prune_weight } else { self.s.c.prune_weight };
                if e.structural_weight() < floor { self.remove_edge(key, false); }
            }
            let ids: Vec<_> = self.nodes.keys().copied().collect();
            for id in ids { self.expiry(3, id, 0); }
            self.structure_timer();
            return;
        }
        *self.audit.get_mut("expiry_checks").unwrap() += 1;
        let key = (a, b);
        if kind == 5 && self.nodes.contains_key(&a) {
            let mut n = self.settle_node(a);
            self.maintenance(&mut n);
            self.nodes.insert(a, n.clone());
            self.node_timers(&n);
            if self.s.c.energy_simulation_enabled && self.s.c.energy_starvation_damage_enabled {
                self.timer(
                    (5, a, 0),
                    Some(self.time + self.s.c.propagation_interval_us as u128),
                );
            }
        } else if [1, 3].contains(&kind) && self.nodes.contains_key(&a) {
            let n = self.settle_node(a);
            if kind == 3 {
                let floor = if self.s.r.node_retention_mode == "automatic" {
                    0.006
                } else {
                    self.s.c.prune_support
                };
                let mut eligible = if floor > 0.0 {
                    n.support < floor
                } else {
                    self.time - at(&n.isolated_us).max(at(&n.last_touch_us))
                        >= self.s.r.dead_node_retention_us as u128
                };
                if self.s.r.node_retention_mode == "manual" && floor > 0.0 {
                    eligible = eligible
                        && self.time - at(&n.last_touch_us) > self.s.c.node_prune_after_us as u128;
                }
                if !self.s.r.retain_nodes && n.activation == 0.0 && !self.connected(a) && eligible {
                    self.delete_node(a);
                    return;
                }
            }
            self.node_timers(&n);
            self.pulse(&n, false);
        } else if [2, 4].contains(&kind) && self.edges.contains_key(&key) {
            let mut e = self.settle_edge(key);
            let c = &self.s.c;
            if kind == 4 {
                let reentry = e.novelty_source.max(e.novelty_target);
                if c.plasticity
                    && reentry > 0.0
                    && !e.sleeping
                    && !self.silenced_edges.contains(&key)
                    && !self.silenced_nodes.contains(&a)
                    && !self.silenced_nodes.contains(&b)
                {
                    let bonus =
                        c.local_novelty_gain * (1.0 - reentry / c.novelty_touch_reference).max(0.0);
                    let before = e.weight;
                            e.weight = (e.weight + bonus).min(1.0);
                            if let Some(w) = e.inhibition_weight.as_mut() {
                                let prior = *w;
                                *w = (*w + bonus).min(1.0);
                                if *w > prior && self.s.f.reinforcement_age_policy == "reset" {
                                    if let Some(l)=e.inhibition_learning.as_mut() { l.decay_age=0.0; } else { e.decay_age=0.0; }
                                }
                            }
                            if e.weight > before && self.s.choice("reinforcement_age_policy", "reset") { e.decay_age = 0.0; }
                    if self.s.stability_grows() {
                                e.stability = (e.stability + bonus).min(1.0);
                                if let Some(l)=e.inhibition_learning.as_mut() { l.stability=(l.stability+bonus).min(1.0); }
                            }
                }
                e.novelty_deadline_us = None;
            }
            let remove = e.structural_weight()
                < if e.sleeping {
                    self.s.r.dormant_prune_weight
                } else {
                    c.prune_weight
                };
            if V5 && kind == 4 {
                self.drop_novelty_index(key);
            }
            self.edges.insert(key, e.clone());
            if remove && kind != 4 {
                self.remove_edge(key, false);
            } else {
                self.edge_timer(&e);
            }
        }
    }
    pub fn advance(&mut self, target: u128, record: bool) -> Result<Vec<Value>> {
        self.advance_impl(target, record, false)
    }
    pub fn advance_inputs(&mut self, target: u128) -> Result<Vec<Value>> {
        self.advance_impl(target, true, true)
    }
    fn advance_impl(
        &mut self,
        target: u128,
        record: bool,
        inputs_only: bool,
    ) -> Result<Vec<Value>> {
        if target < self.time {
            return Err("simulation time cannot go backwards".into());
        }
        let mut rows = Vec::new();
        while self.life != "dead" {
            let next = self
                .queue
                .first_key_value()
                .map(|(k, _)| k.0)
                .into_iter()
                .chain(self.timers.first().map(|(t, _)| *t))
                .chain(self.quiet.map(|t| t + self.s.c.quiescence_death_us as u128))
                .min();
            let Some(t) = next.filter(|t| *t <= target) else {
                break;
            };
            self.time = t;
            if V5 {
                self.before_emission = t % self.s.c.propagation_interval_us as u128 == 0
                    && t > self.completed_emission_us;
            }
            let mut packets = Vec::new();
            let mut direct_drives = BTreeMap::new();
            let mut wake: BTreeMap<Key, BTreeMap<u64, f64>> = BTreeMap::new();
            let mut energy_regions = BTreeSet::new();
            while self
                .queue
                .first_key_value()
                .is_some_and(|(k, _)| k.0 == self.time)
            {
                let (_, ev) = self.queue.pop_first().unwrap();
                let wire_payload = if OPTIMIZED && ev.kind == "signal" {
                    std::borrow::Cow::Borrowed(&Value::Null)
                } else {
                    payload_view(&ev.payload)
                };
                let payload = wire_payload.as_ref();
                let mut observed_payload = None;
                match ev.kind.as_str() {
                    "stimulus" => {
                        let mut s: Stimulus =
                            serde_json::from_value(payload.clone()).map_err(|e| e.to_string())?;
                        s.channels.sort_by_key(|(ch, _)| *ch);
                        let mut messages = Vec::new();
                        for (channel, value) in s.channels {
                            let mut raw = value * s.intensity * self.s.c.direct_gain;
                            if V5 || self.s.choice("reception_mode", "legacy-source") {
                                raw = raw.min(1.0);
                            }
                            if raw <= 0.0 {
                                continue;
                            }
                            let id = if self.nodes.contains_key(&node_address(channel)) {
                                Some(node_address(channel))
                            } else {
                                self.birth(channel)
                            };
                            if let Some(id) = id {
                                messages.push((-1, id, raw, vec![0.0; 4]));
                                if V5 {
                                    direct_drives.insert((ev.id as i128, id), value * s.intensity);
                                }
                                if !V5 || self.s.c.energy_simulation_enabled {
                                    energy_regions.insert(self.nodes[&id].region);
                                }
                            }
                        }
                        packets.push((ev.id as i128, messages, true, s.intensity));
                    }
                    "signal" => {
                        let mut messages = payload_messages(&ev.payload)?;
                        if ev.birth_limit.is_some() {
                            messages.retain(|m| self.accept_birth(m.1, ev.birth_limit));
                        }
                        if !V5 || self.s.c.energy_simulation_enabled {
                            for m in &messages {
                                if let Some(n) = self.nodes.get(&m.1) {
                                    energy_regions.insert(n.region);
                                }
                            }
                        }
                        packets.push((ev.id as i128, messages, false, 1.0));
                    }
                    "inhibition" => {
                        let values: Vec<(u64, f64)> =
                            serde_json::from_value(payload["values"].clone())
                                .map_err(|e| e.to_string())?;
                        for (id, value) in values {
                            if self.nodes.contains_key(&id)
                                && !self.silenced_nodes.contains(&id)
                                && self.s.c.inhibition
                                && self.accept_birth(id, ev.birth_limit)
                            {
                                let mut n = self.settle_node(id);
                                *self.transport.get_mut("received_inhibition").unwrap() += value;
                                n.pending_inhibition += value;
                                self.nodes.insert(id, n.clone());
                                self.pulse(&n, false);
                            }
                        }
                    }
                    "wake" => {
                        let key: Key = serde_json::from_value(payload["edge"].clone())
                            .map_err(|e| e.to_string())?;
                        let sender = payload["sender"].as_u64().ok_or("missing wake sender")?;
                        if self.s.r.revival_enabled
                            && !self.silenced_edges.contains(&key)
                            && !self.silenced_nodes.contains(&key.0)
                            && !self.silenced_nodes.contains(&key.1)
                            && self.accept_birth(key.0, ev.birth_limit)
                            && self.accept_birth(key.1, ev.birth_limit)
                        {
                            let target = if sender == key.0 { key.1 } else { key.0 };
                            *wake.entry(key).or_default().entry(target).or_default() +=
                                payload["value"].as_f64().ok_or("invalid wake signal")?;
                        }
                    }
                    "energy" => {
                        let p: Supply =
                            serde_json::from_value(payload.clone()).map_err(|e| e.to_string())?;
                        let accepted;
                        if self.s.choice("energy_model", "global-ledger") {
                            let before = self.energy.supplied_total;
                            accepted = self.energy.supply(p.amount, self.s.c.energy_capacity, true)
                                ["accepted"]
                                .as_f64()
                                .unwrap();
                            self.energy.discarded_total +=
                                p.amount - (self.energy.supplied_total - before);
                        } else {
                            self.energy.offered_total += p.amount;
                            let random = if self.s.choice("energy_distribution", "counter-random") {
                                word(self.s.uint("energy_seed"), 2, self.energy_serial)
                            } else {
                                self.energy_rng = self
                                    .energy_rng
                                    .wrapping_mul(6364136223846793005)
                                    .wrapping_add(1442695040888963407);
                                self.energy_rng >> 32
                            };
                            let region = random % self.s.uint("energy_region_count");
                            self.energy_serial += 1;
                            let amount = p
                                .amount
                                .min((self.s.c.energy_capacity - self.pools[&region]).max(0.0));
                            *self.pools.get_mut(&region).unwrap() += amount;
                            self.energy.supplied_total += amount;
                            self.energy.discarded_total += p.amount - amount;
                            energy_regions.insert(region);
                            accepted = amount;
                        }
                        // Receipt metadata only; allocation and the input stay unchanged.
                        let mut receipt = payload.clone();
                        receipt["offered"] = json!(p.amount);
                        receipt["accepted"] = json!(accepted);
                        receipt["status"] = json!("accepted");
                        observed_payload = Some(receipt);
                    }
                    _ => return Err("unknown local event".into()),
                }
                self.sequence += 1;
                if record && (!inputs_only || ["stimulus", "energy"].contains(&ev.kind.as_str())) {
                    rows.push(json!({"sequence":self.sequence,"time_us":self.time.to_string(),"kind":ev.kind,"event_id":ev.id,"payload":observed_payload.unwrap_or_else(|| payload_view(&ev.payload).into_owned())}));
                }
            }
            if self.s.c.energy_simulation_enabled && self.s.choice("energy_model", "local-field") {
                for region in energy_regions {
                    self.uptake(region);
                }
            }
            for (key, arrivals) in wake {
                if self.edges.get(&key).is_some_and(|e| e.sleeping) {
                    let mut e = self.settle_edge(key);
                    let value: f64 = arrivals.values().sum();
                    if value >= self.s.r.edge_wake_threshold.unwrap() {
                        e.sleeping = false;
                        *self.audit.get_mut("edges_awakened").unwrap() += 1;
                        self.edge_timer(&e);
                    }
                    self.edges.insert(key, e);
                    for (target, amount) in arrivals {
                        packets.push((
                            -(key.0 as i128 + 1),
                            vec![(-1, target, amount, vec![0.0; 4])],
                            false,
                            1.0,
                        ));
                    }
                }
            }
            self.receive(packets, &direct_drives)?;
            let mut due = Vec::new();
            while self.timers.first().is_some_and(|(t, _)| *t <= self.time) {
                let (_, key) = self.timers.pop_first().unwrap();
                self.deadlines.remove(&key);
                due.push(key);
            }
            let mut pulses: Vec<_> = due.iter().filter(|k| k.0 == 0).map(|k| k.1).collect();
            if V5 {
                for &(kind, a, b) in &due {
                    if kind == 4 {
                        self.expiry(kind, a, b);
                    }
                }
            }
            if self.s.choice("propagation_mode", "scan-control") && !pulses.is_empty() {
                let requested: BTreeSet<_> = pulses.into_iter().collect();
                pulses = self
                    .nodes
                    .keys()
                    .filter(|id| requested.contains(id))
                    .copied()
                    .collect();
                *self.audit.get_mut("scan_visits").unwrap() += self.nodes.len() as u64;
            }
            for id in pulses {
                self.emit(id)?;
            }
            if V5 {
                self.before_emission = false;
                let period = self.s.c.propagation_interval_us as u128;
                self.completed_emission_us = self.time / period * period;
                if !self.inhibition_batch.is_empty() {
                    let values: Vec<_> = std::mem::take(&mut self.inhibition_batch)
                        .into_iter()
                        .map(|(id, value)| (id, self.soft(value)))
                        .collect();
                    self.event(
                        self.time + self.s.c.delay_us as u128,
                        "inhibition",
                        json!({"values":values}),
                    );
                }
            }
            self.deletion_phase = true;
            due.sort_by_key(|row| (row.0 != 7,*row));
            for (kind, a, b) in due {
                if kind != 0 && (!V5 || kind != 4) {
                    self.expiry(kind, a, b);
                }
            }
            while self.timers.first().is_some_and(|(t,_)| *t <= self.time) {
                let (_,key) = self.timers.pop_first().unwrap();
                self.deadlines.remove(&key);
                assert!([2,3].contains(&key.0), "only local deletion may schedule same-phase work");
                self.expiry(key.0,key.1,key.2);
            }
            self.deletion_phase = false;
            if self.quiet.is_some_and(|t| {
                self.active.is_empty() && self.time - t >= self.s.c.quiescence_death_us as u128
            }) {
                self.life = "dead".into();
                self.energy.death_us = Some(self.time.to_string());
            }
        }
        if self.life != "dead" {
            self.time = target;
        }
        if V5 {
            let period = self.s.c.propagation_interval_us as u128;
            self.completed_emission_us = self.time / period * period;
        }
        Ok(rows)
    }
    pub fn intervene(&mut self, nodes: Vec<u64>, edges: Vec<Key>, lesion: bool) -> Result<()> {
        let action = if lesion {
            if nodes.is_empty() {
                "disconnect_edges"
            } else {
                "delete_nodes"
            }
        } else {
            "silence"
        };
        self.intervene_action(nodes, edges, action)
    }
    pub fn intervene_action(
        &mut self,
        nodes: Vec<u64>,
        edges: Vec<Key>,
        action: &str,
    ) -> Result<()> {
        if !["silence", "restore", "delete_nodes", "disconnect_edges"].contains(&action) {
            return Err("unsupported intervention".into());
        }
        for id in nodes {
            match action {
                "delete_nodes" => self.delete_node(id),
                "restore" => {
                    self.silenced_nodes.remove(&id);
                    if self.nodes.contains_key(&id) {
                        let n = self.settle_node(id);
                        self.pulse(&n, false);
                    }
                }
                _ => {
                    self.silenced_nodes.insert(id);
                    self.timer((0, id, 0), None);
                }
            }
        }
        for key in edges {
            match action {
                "disconnect_edges" => {
                    self.remove_edge(key, true);
                    self.silenced_edges.insert(key);
                }
                "restore" => {
                    self.silenced_edges.remove(&key);
                }
                _ => {
                    self.silenced_edges.insert(key);
                }
            }
        }
        Ok(())
    }
    pub fn reconfigure(&mut self, value: Value) -> Result<()> {
        let next = Settings::parse(value)?;
        if IMMUTABLE.iter().any(|k| self.s.value[*k] != next.value[*k]) {
            return Err(if V5 {
                "memory/5 identity, clocks and model choices are fixed at birth"
            } else {
                "memory/4 identity, clocks and model choices are fixed at birth"
            }
            .into());
        }
        for id in self.nodes.keys().copied().collect::<Vec<_>>() {
            let mut n = self.settle_node(id);
            self.maintenance(&mut n);
            self.nodes.insert(id, n);
        }
        for key in self.edges.keys().copied().collect::<Vec<_>>() {
            let mut e = self.settle_edge(key);
            if let Some(st) = &e.short_term {
                e.short_term = Some(st.recovered(self.time, &self.s.o.short_term())?);
            }
            if let Some(l) = e.inhibition_learning.as_mut() {
                if let Some(f)=l.fast { l.fast=Some(FastTrace { value:f.projected(self.time,&self.s.o.fast_trace())?, time_us:stamp(self.time) }); }
            }
            if let Some(st) = &e.inhibition_short_term {
                e.inhibition_short_term = Some(st.recovered(self.time, &self.s.o.short_term())?);
            }
            if let Some(f) = &e.fast {
                e.fast = Some(FastTrace {
                    value: f.projected(self.time, &self.s.o.fast_trace())?,
                    time_us: stamp(self.time),
                });
            }
            self.edges.insert(key, e);
        }
        self.s = next;
        if self.s.choice("energy_model", "global-ledger") {
            self.energy.resize(self.s.c.energy_capacity);
        } else {
            for v in self.pools.values_mut() {
                let excess = (*v - self.s.c.energy_capacity).max(0.0);
                *v -= excess;
                self.energy.discarded_total += excess;
            }
        }
        if !self.s.r.dormant_traces_enabled {
            for key in self
                .edges
                .iter()
                .filter(|(_, e)| e.sleeping)
                .map(|(k, _)| *k)
                .collect::<Vec<_>>()
            {
                self.remove_edge(key, true);
            }
            for n in self.nodes.values_mut() {
                n.sleeping = false;
            }
        }
        for id in self.nodes.keys().copied().collect::<Vec<_>>() {
            let mut n = self.settle_node(id);
            n.half_life = n.half_life.clamp(
                self.s.r.memory_half_life_min_s,
                self.s.r.memory_half_life_max_s,
            );
            if n.reserve > self.s.num("energy_node_capacity") {
                self.energy.discarded_total += n.reserve - self.s.num("energy_node_capacity");
                n.reserve = self.s.num("energy_node_capacity");
            }
            n.energy_us = stamp(self.time);
            self.nodes.insert(id, n.clone());
            self.node_timers(&n);
            self.pulse(&n, false);
            let t = if self.s.c.energy_simulation_enabled
                && self.s.c.energy_starvation_damage_enabled
            {
                Some(self.time + self.s.c.propagation_interval_us as u128)
            } else {
                None
            };
            self.timer((5, id, 0), t);
        }
        for key in self.edges.keys().copied().collect::<Vec<_>>() {
            let mut e = self.edges[&key].clone();
            e.half_life = e.half_life.clamp(
                self.s.r.memory_half_life_min_s,
                self.s.r.memory_half_life_max_s,
            );
            if let Some(l)=e.inhibition_learning.as_mut() { l.half_life=l.half_life.clamp(self.s.r.memory_half_life_min_s,self.s.r.memory_half_life_max_s); }
            self.edges.insert(key, e.clone());
            self.edge_timer(&e);
        }
        Ok(())
    }
    pub fn activations(&self) -> Vec<(u64, f64)> {
        self.nodes
            .iter()
            .map(|(id, n)| (*id, self.node_value(n, self.time).activation))
            .collect()
    }
    pub fn observation_nodes(&self) -> Vec<Value> {
        self.nodes
            .values()
            .map(|n| serde_json::to_value(self.node_value(n, self.time)).unwrap())
            .collect()
    }
    pub fn induced_edges(&self, ids: Vec<u64>) -> Vec<Value> {
        let ids: BTreeSet<_> = ids.into_iter().collect();
        self.edges
            .values()
            .filter(|e| ids.contains(&e.source) && ids.contains(&e.target) && !e.sleeping)
            .map(|e| serde_json::to_value(self.edge_value(e, self.time)).unwrap())
            .collect()
    }
    pub fn graph(&self, limit: Option<usize>) -> Value {
        let mut nodes = self.observation_nodes();
        nodes.truncate(limit.unwrap_or(nodes.len()));
        let edges = self.induced_edges(nodes.iter().map(|n| n["id"].as_u64().unwrap()).collect());
        json!({"nodes":nodes,"edges":edges,"kernel_id":Self::KERNEL,"observation_quantity":"activation"})
    }
    pub fn spatial_geometry(&self) -> Result<Value> {
        let nodes = if self.s.c.spatial_embedding {
            self.nodes
                .keys()
                .map(|id| json!({"id":id,"position":crate::spatial::position(&self.s.c,*id)}))
                .collect::<Vec<_>>()
        } else {
            Vec::new()
        };
        Ok(
            json!({"schema":"threemind.spatial-observation/1","nodes":nodes,"edges":[],"parameters":{"spatial_embedding":self.s.c.spatial_embedding},"seed":self.s.c.seed}),
        )
    }
    pub fn metrics(&self) -> Value {
        let nodes: Vec<_> = self
            .nodes
            .values()
            .map(|n| self.node_value(n, self.time))
            .collect();
        let edges: Vec<_> = self
            .edges
            .values()
            .filter(|e| !e.sleeping)
            .map(|e| self.edge_value(e, self.time))
            .collect();
        let mut energy = serde_json::to_value(&self.energy).unwrap();
        if self.s.choice("energy_model", "local-field") {
            energy["reserve"] = json!(
                self.pools.values().sum::<f64>()
                    + self.nodes.values().map(|n| n.reserve).sum::<f64>()
            );
        }
        let mut parameters = self.s.c.energy_parameters();
        for key in [
            "energy_model",
            "energy_distribution",
            "energy_seed",
            "energy_region_count",
            "energy_node_capacity",
        ] {
            parameters[key] = self.s.value[key].clone();
        }
        energy["parameters"] = parameters;
        energy["settled_state_time_us"] = json!(self.time.to_string());
        let count = nodes.len();
        let activation: f64 = nodes.iter().map(|n| n.activation).sum();
        json!({"time_us":self.time.to_string(),"state_time_us":self.time.to_string(),"quiet_since_us":self.quiet.map(|t|t.to_string()),"sequence":self.sequence,"life":self.life,"nodes":count,"edges":edges.len(),"activation":activation,"mean_activation":if count>0{Some(activation/count as f64)}else{None},"mean_weight":if edges.is_empty(){None}else{Some(edges.iter().map(|e|e.weight).sum::<f64>()/edges.len() as f64)},"active_fraction":if count>0{Some(nodes.iter().filter(|n|n.activation>self.s.c.activation_floor).count() as f64/count as f64)}else{None},"saturated_fraction":if count>0{Some(nodes.iter().filter(|n|n.activation>=0.95).count() as f64/count as f64)}else{None},"edge_density":if count>1{Some(edges.len() as f64/(count*(count-1)) as f64)}else{None},"inhibition":nodes.iter().map(|n|n.inhibition).sum::<f64>(),"pending_events":self.queue.len()+self.timers.len(),"resources":null,"attention":null,"transport":self.transport,"energy":energy,"local_audit":self.audit,"dynamics":Self::KERNEL,"kernel_id":Self::KERNEL,"state_schema":Self::SCHEMA})
    }
    pub fn capture(&self) -> Result<Value> {
        let definition = self.definition();
        let hash = canonical_hash(&serde_json::to_vec(&definition).unwrap())?;
        let mut state = json!({"schema":Self::SCHEMA,"dynamics":Self::KERNEL,"config":self.config(),"definition":definition,"definition_hash":hash,"time_us":self.time.to_string(),"sequence":self.sequence,"next_event":self.next_event,"birth_count":self.birth_count,"sources_open":self.sources_open,"life":self.life,"quiet_since_us":self.quiet.map(|t|t.to_string()),"nodes":self.nodes.values().collect::<Vec<_>>(),"edges":self.edges.values().collect::<Vec<_>>(),"queue":self.queue.values().collect::<Vec<_>>(),"timers":self.timers.iter().map(|(t,(k,a,b))|json!([k,a,b,t.to_string()])).collect::<Vec<_>>(),"active":self.active,"silenced_nodes":self.silenced_nodes,"silenced_edges":self.silenced_edges,"transport":self.transport,"audit":self.audit,"energy":self.energy,"pools":self.pools.iter().map(|(r,v)|json!([r,v])).collect::<Vec<_>>(),"energy_serial":self.energy_serial,"energy_rng":self.energy_rng.to_string()});
        if V5 {
            state["completed_emission_us"] = json!(self.completed_emission_us.to_string());
        }
        Ok(state)
    }
    pub fn restore(value: Value) -> Result<Self> {
        if value["schema"] != Self::SCHEMA || value["dynamics"] != Self::KERNEL {
            return Err("memory/4 identity mismatch; conversion is not restoration".into());
        }
        let mut saved_config = value["config"].clone();
        saved_config.as_object_mut().ok_or("invalid config")?.entry("inhibition_updates_usage").or_insert(json!(true));
        for name in ["resource_precheck_enabled", "subthreshold_expiry_enabled"] {
            saved_config.as_object_mut().ok_or("invalid config")?.entry(name).or_insert(json!(false));
        }
        let mut e = Self::new(saved_config)?;
        if value
            .as_object()
            .map(|m| m.keys().cloned().collect::<BTreeSet<_>>())
            != e.capture()?
                .as_object()
                .map(|m| m.keys().cloned().collect::<BTreeSet<_>>())
        {
            return Err("invalid memory/4 state fields".into());
        }
        let mut expected_definition = e.definition();
        for name in ["activation_weight_reinforcement_enabled", "inhibition_weight_reinforcement_enabled",
                     "resource_precheck_enabled", "subthreshold_expiry_enabled",
            "separate_inhibition", "separate_inhibition_weights", "separate_inhibition_resources", "separate_inhibition_learning", "inhibition_updates_usage"] {
            if value["config"].get(name).is_none() {
                expected_definition["config"].as_object_mut().unwrap().remove(name);
            }
        }
        if value["definition"] != expected_definition
            || value["definition_hash"]
                != canonical_hash(&serde_json::to_vec(&expected_definition).unwrap())?
        {
            return Err("memory/4 definition/hash mismatch".into());
        }
        e.time = read_time(value["time_us"].as_str().ok_or("invalid time")?)?;
        if V5 {
            e.completed_emission_us = read_time(
                value["completed_emission_us"]
                    .as_str()
                    .ok_or("missing memory/5 completed emission clock")?,
            )?;
            let period = e.s.c.propagation_interval_us as u128;
            if e.completed_emission_us != e.time / period * period {
                return Err("invalid memory/5 completed emission clock".into());
            }
        }
        e.sequence = value["sequence"].as_u64().ok_or("invalid sequence")?;
        e.next_event = value["next_event"].as_u64().ok_or("invalid event id")?;
        e.birth_count = value["birth_count"].as_u64().ok_or("invalid node id")?;
        e.sources_open = value["sources_open"]
            .as_bool()
            .ok_or("invalid sources flag")?;
        e.life = value["life"].as_str().ok_or("invalid life")?.into();
        e.quiet = if value["quiet_since_us"].is_null() {
            None
        } else {
            Some(read_time(
                value["quiet_since_us"]
                    .as_str()
                    .ok_or("invalid quiet time")?,
            )?)
        };
        e.energy = serde_json::from_value(value["energy"].clone()).map_err(|e| e.to_string())?;
        e.energy.validate(e.time, &e.s.c)?;
        e.energy_serial = value["energy_serial"]
            .as_u64()
            .ok_or("invalid energy serial")?;
        e.energy_rng = value["energy_rng"]
            .as_str()
            .ok_or("invalid energy RNG")?
            .parse()
            .map_err(|_| "invalid energy RNG")?;
        e.transport =
            serde_json::from_value(value["transport"].clone()).map_err(|e| e.to_string())?;
        e.audit = serde_json::from_value(value["audit"].clone()).map_err(|e| e.to_string())?;
        e.pools = serde_json::from_value::<Vec<(u64, f64)>>(value["pools"].clone())
            .map_err(|e| e.to_string())?
            .into_iter()
            .collect();
        for n in serde_json::from_value::<Vec<Node>>(value["nodes"].clone())
            .map_err(|e| e.to_string())?
        {
            if e.nodes.contains_key(&n.id)
                || n.id != node_address(n.channel)
                || read_time(&n.state_us)? > e.time
                || n.region >= e.s.uint("energy_region_count")
            {
                return Err("invalid local node history".into());
            }
            e.regions.entry(n.region).or_default().insert(n.id);
            e.nodes.insert(n.id, n);
        }
        for edge in serde_json::from_value::<Vec<Edge>>(value["edges"].clone())
            .map_err(|e| e.to_string())?
        {
            let key = (edge.source, edge.target);
            if e.edges.contains_key(&key)
                || !e.nodes.contains_key(&key.0)
                || !e.nodes.contains_key(&key.1)
                || read_time(&edge.state_us)? > e.time
            {
                return Err("invalid local edge history".into());
            }
            e.outgoing.entry(key.0).or_default().insert(key);
            e.incident.entry(key.0).or_default().insert(key);
            e.incident.entry(key.1).or_default().insert(key);
            if V5 && edge.novelty_deadline_us.is_some() {
                e.pending_novelty.entry(key.0).or_default().insert(key);
                e.pending_novelty.entry(key.1).or_default().insert(key);
            }
            e.edges.insert(key, edge);
        }
        let mut queued_ids = BTreeSet::new();
        for ev in serde_json::from_value::<Vec<Event>>(value["queue"].clone())
            .map_err(|e| e.to_string())?
        {
            let t = read_time(&ev.time_us)?;
            if t < e.time
                || ev.id >= e.next_event
                || !queued_ids.insert(ev.id)
                || !["stimulus", "signal", "inhibition", "wake", "energy"]
                    .contains(&ev.kind.as_str())
            {
                return Err("invalid local queued event".into());
            }
            if e.queue.insert((t, ev.id), ev).is_some() {
                return Err("duplicate queued event".into());
            }
        }
        for (kind, a, b, t) in
            serde_json::from_value::<Vec<(u8, u64, u64, String)>>(value["timers"].clone())
                .map_err(|e| e.to_string())?
        {
            let key = (kind, a, b);
            let t = read_time(&t)?;
            if ![0, 1, 2, 3, 4, 5, 6, 7].contains(&kind) || (kind == 6 && (a, b) != (0, 0))
                || t < e.time
                || e.deadlines.contains_key(&key)
                || ([0, 1, 3, 5].contains(&kind) && !e.nodes.contains_key(&a))
                || ([2, 4, 7].contains(&kind) && !e.edges.contains_key(&(a, b)))
            {
                return Err("invalid local deadline".into());
            }
            e.timer(key, Some(t));
        }
        e.active = serde_json::from_value(value["active"].clone()).map_err(|e| e.to_string())?;
        e.silenced_nodes =
            serde_json::from_value(value["silenced_nodes"].clone()).map_err(|e| e.to_string())?;
        e.silenced_edges =
            serde_json::from_value(value["silenced_edges"].clone()).map_err(|e| e.to_string())?;
        if !e.active.iter().all(|id| e.nodes.contains_key(id))
            || e.birth_count < e.nodes.len() as u64
        {
            return Err("invalid local identities".into());
        }
        e.validate()?;
        Ok(e)
    }
    fn validate(&self) -> Result<()> {
        let c = &self.s.c;
        if self
            .audit
            .keys()
            .map(String::as_str)
            .collect::<BTreeSet<_>>()
            != [
                "node_visits",
                "edge_visits",
                "scan_visits",
                "expiry_checks",
                "nodes_deleted",
                "edges_deleted",
                "nodes_awakened",
                "edges_awakened",
            ]
            .into_iter()
            .collect()
            || self
                .transport
                .keys()
                .map(String::as_str)
                .collect::<BTreeSet<_>>()
                != ["sent", "received", "activated", "discarded", "offered_excitation", "offered_inhibition", "transmitted_excitation", "transmitted_inhibition", "received_inhibition", "blocked_weight", "blocked_signal", "blocked_dormancy", "blocked_energy"]
                    .into_iter()
                    .collect()
        {
            return Err("invalid local audit or transport fields".into());
        }
        if self.transport.values().any(|v| !v.is_finite() || *v < 0.0) {
            return Err("invalid transport counter".into());
        }
        if !["waiting", "active", "dead"].contains(&self.life.as_str())
            || self.quiet.is_some_and(|t| t > self.time)
        {
            return Err("invalid lifecycle".into());
        }
        if self.pools.len() != self.s.uint("energy_region_count") as usize
            || self.pools.iter().any(|(r, v)| {
                *r >= self.s.uint("energy_region_count")
                    || !v.is_finite()
                    || *v < 0.0
                    || *v > c.energy_capacity
            })
        {
            return Err("invalid local energy pool".into());
        }
        let mut births = BTreeSet::new();
        for n in self.nodes.values() {
            if n.birth_serial == 0 || n.birth_serial > self.birth_count || !births.insert(n.birth_serial) {
                return Err("invalid node birth serial".into());
            }
            if V5 != n.last_emit_us.is_some()
                || n.last_emit_us
                    .as_ref()
                    .is_some_and(|t| read_time(t).map_or(true, |t| t > self.time))
            {
                return Err("invalid version-specific node emission clock".into());
            }
            for t in [
                &n.state_us,
                &n.birth_us,
                &n.last_touch_us,
                &n.isolated_us,
                &n.energy_us,
            ] {
                if read_time(t)? > self.time {
                    return Err("invalid node clock".into());
                }
            }
            let v = serde_json::to_value(n).unwrap();
            for (k, x) in v.as_object().unwrap() {
                if x.is_number()
                    && !["id", "channel", "touches", "region"].contains(&k.as_str())
                    && x.as_f64().is_none_or(|v| !v.is_finite() || v < 0.0)
                {
                    return Err("invalid node value".into());
                }
            }
            if [
                n.activation,
                n.trace,
                n.support,
                n.stability,
                n.local_plasticity,
            ]
            .iter()
            .any(|v| *v > 1.0)
                || n.reserve > self.s.num("energy_node_capacity")
                || n.half_life < self.s.r.memory_half_life_min_s
                || n.half_life > self.s.r.memory_half_life_max_s
            {
                return Err("invalid local node bounds".into());
            }
            if ((n.activation > c.activation_floor && c.activation_decay_enabled && c.activation_floor > 0.0)
                || (self.s.f.subthreshold_expiry_enabled && n.activation > 0.0 && n.activation <= c.activation_floor
                    && (n.activation < c.activation_floor || c.activation_decay_enabled)))
                && !self.deadlines.contains_key(&(1, n.id, 0))
            {
                return Err("missing node activation deadline".into());
            }
            if c.energy_simulation_enabled
                && c.energy_starvation_damage_enabled
                && !self.deadlines.contains_key(&(5, n.id, 0))
            {
                return Err("missing node energy deadline".into());
            }
            if !n.sleeping
                && !self.silenced_nodes.contains(&n.id)
                && self.can_emit(n)
                && !self.deadlines.contains_key(&(0, n.id, 0))
            {
                return Err("missing node emission deadline".into());
            }
        }
        for (key, e) in &self.edges {
            if V5 != e.completed_period_us.is_some()
                || e.completed_period_us.as_ref().is_some_and(|t| {
                    read_time(t).map_or(true, |t| {
                        t > self.time || t % c.propagation_interval_us as u128 != 0
                    })
                })
            {
                return Err("invalid version-specific edge period clock".into());
            }
            if self.s.separates_learning() != e.inhibition_learning.is_some() { return Err("inhibitory learning records do not match birth configuration".into()); }
            if let Some(l)=e.inhibition_learning {
                if [l.stability,l.eligibility].iter().any(|x| !x.is_finite() || !(0.0..=1.0).contains(x))
                    || !l.decay_age.is_finite() || l.decay_age<0.0 || !l.half_life.is_finite()
                    || l.half_life<self.s.r.memory_half_life_min_s || l.half_life>self.s.r.memory_half_life_max_s
                    || read_time(&l.last_pass_us)?>self.time || read_time(&l.last_touch_us)?>self.time {
                    return Err("invalid inhibitory learning records".into());
                }
                if let Some(f)=l.fast { f.projected(self.time,&self.s.o.fast_trace())?; }
            }
            if self.s.separates_weights() != e.inhibition_weight.is_some() {
                return Err("inhibition weight does not match birth configuration".into());
            }
            if e.inhibition_weight.is_some_and(|w| !w.is_finite() || !(0.0..=1.0).contains(&w)) {
                return Err("invalid inhibition weight".into());
            }
            if let Some(st) = &e.inhibition_short_term {
                if !self.s.separates_resources() { return Err("unexpected separate inhibitory resource".into()); }
                st.validate()?;
                if at(&st.time_us) > self.time { return Err("future inhibitory resource".into()); }
            }
            for t in [&e.state_us, &e.birth_us, &e.last_touch_us, &e.last_pass_us] {
                if read_time(t)? > self.time {
                    return Err("invalid edge clock".into());
                }
            }
            if [
                e.weight,
                e.stability,
                e.eligibility,
                e.novelty_source,
                e.novelty_target,
            ]
            .iter()
            .any(|v| !v.is_finite() || *v < 0.0)
                || e.weight > 1.0
                || e.stability > 1.0
                || e.eligibility > 1.0
                || e.half_life < self.s.r.memory_half_life_min_s
                || e.half_life > self.s.r.memory_half_life_max_s
            {
                return Err("invalid local edge bounds".into());
            }
            if let Some(st) = &e.short_term {
                st.validate()?;
                if at(&st.time_us) > self.time {
                    return Err("future short-term state".into());
                }
            }
            if let Some(f) = &e.fast {
                f.projected(self.time, &self.s.o.fast_trace())?;
            }
            if let Some(t) = &e.novelty_deadline_us {
                if self.deadlines.get(&(4, key.0, key.1)) != Some(&read_time(t)?) {
                    return Err("missing novelty deadline".into());
                }
            }
        }
        for (age, state, birth) in self.nodes.values().map(|n| (n.decay_age, at(&n.state_us), at(&n.birth_us)))
            .chain(self.edges.values().map(|e| (e.decay_age, at(&e.state_us), at(&e.birth_us)))) {
            // A newborn can inherit decay age while its own clock starts at zero.
            if birth > state || !age.is_finite() || age < 0.0 {
                return Err("invalid decay age".into());
            }
        }
        let key = (6, 0, 0);
        if self.s.f.deletion_strategy == "global-scan" && !self.nodes.is_empty() && c.plasticity && !self.deadlines.contains_key(&key) { return Err("missing structure clock".into()); }
        if let Some(t) = self.deadlines.get(&key) {
            if self.s.f.deletion_strategy != "global-scan" { return Err("unexpected global structure clock".into()); }
            let interval = self.s.uint("structure_check_interval_us") as u128;
            if *t != (self.time / interval + 1) * interval { return Err("invalid structure clock phase".into()); }
        }
        if self.s.f.deletion_strategy == "local" && c.plasticity {
            for (key,e) in &self.edges {
                let floor = if e.sleeping { self.s.r.dormant_prune_weight } else { c.prune_weight };
                if floor > 0.0 && (self.s.r.adaptive() || e.structural_weight() < floor) && !self.deadlines.contains_key(&(2,key.0,key.1)) { return Err("missing edge deletion deadline".into()); }
            }
            for n in self.nodes.values() {
                if !self.s.r.retain_nodes && n.activation == 0.0 && !self.connected(n.id) && (c.support_decay_enabled || n.support < 0.006)
                    && !self.deadlines.contains_key(&(3,n.id,0)) { return Err("missing node deletion deadline".into()); }
            }
        }
        for key in self.edges.keys() {
            let stable = !self.s.r.adaptive() && c.plasticity;
            let due = self.deadlines.get(&(7,key.0,key.1));
            if stable != due.is_some() { return Err("missing or unexpected stability deadline".into()); }
            if due.is_some_and(|t| *t != (self.time / c.propagation_interval_us as u128 + 1) * c.propagation_interval_us as u128) {
                return Err("invalid stability clock phase".into());
            }
        }
        for ((kind,_,_), t) in &self.deadlines {
            if [2,3].contains(kind) && (self.s.f.deletion_strategy != "local" || !c.plasticity || t % self.s.f.structure_check_interval_us as u128 != 0) {
                return Err("invalid local deletion clock".into());
            }
        }
        for ((t, _), ev) in &self.queue {
            let guarded = self.s.choice("inflight_delivery", "same-birth")
                && matches!(ev.kind.as_str(), "signal" | "inhibition" | "wake");
            if guarded {
                if ev.birth_limit.is_none_or(|limit| limit == 0 || limit > self.birth_count) {
                    return Err("missing or invalid event birth limit".into());
                }
            } else if ev.birth_limit.is_some() {
                return Err("unexpected event birth limit".into());
            }
            let wire_payload = payload_view(&ev.payload);
            let payload = wire_payload.as_ref();
            match ev.kind.as_str() {
                "stimulus" => {
                    let s: Stimulus =
                        serde_json::from_value(payload.clone()).map_err(|e| e.to_string())?;
                    s.validate()?;
                    if s.time()? != *t {
                        return Err("queued stimulus clock mismatch".into());
                    }
                }
                "energy" => {
                    let s: Supply =
                        serde_json::from_value(payload.clone()).map_err(|e| e.to_string())?;
                    s.validate()?;
                }
                "signal" => {
                    let messages: Vec<Message> =
                        serde_json::from_value(payload["messages"].clone())
                            .map_err(|e| e.to_string())?;
                    if messages.iter().any(|(source, _, value, features)| {
                        *source < -1
                            || !value.is_finite()
                            || *value < 0.0
                            || *value > 1e12
                            || features.len() != 4
                            || features
                                .iter()
                                .any(|v| !v.is_finite() || !(-1.0..=1.0).contains(v))
                    }) {
                        return Err("invalid queued signal".into());
                    }
                }
                "inhibition" => {
                    let values: Vec<(u64, f64)> = serde_json::from_value(payload["values"].clone())
                        .map_err(|e| e.to_string())?;
                    if values
                        .iter()
                        .any(|(_, v)| !v.is_finite() || *v < 0.0 || *v > 1e12)
                    {
                        return Err("invalid queued inhibition".into());
                    }
                }
                "wake" => {
                    let key: Key = serde_json::from_value(payload["edge"].clone())
                        .map_err(|e| e.to_string())?;
                    let sender = payload["sender"].as_u64().ok_or("invalid wake sender")?;
                    let value = payload["value"].as_f64().ok_or("invalid wake signal")?;
                    if (sender != key.0 && sender != key.1)
                        || !value.is_finite()
                        || value < 0.0
                        || value > 1e12
                    {
                        return Err("invalid queued wake".into());
                    }
                }
                _ => return Err("invalid queued event kind".into()),
            }
        }
        Ok(())
    }
}
