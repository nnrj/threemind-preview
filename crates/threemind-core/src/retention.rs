//! Versioned finite retention. Historical kernels never own this operator.
use super::*;

pub const KERNEL_ID: &str = "threemind.continuous-memory/3";
pub const NODE_SUPPORT_FLOOR: f64 = 0.006;
pub const STATE_SCHEMA: &str = "threemind.continuous-memory-state/3.1";
pub const KERNEL31_ID: &str = "threemind.continuous-memory/3.1";
pub const STATE31_SCHEMA: &str = "threemind.continuous-memory-state/3.2";

#[derive(Clone, Copy)]
pub enum Version {
    Original,
    LocalBirthExpiry,
}
impl Version {
    pub fn identity(self) -> (&'static str, &'static str) {
        match self {
            Self::Original => (KERNEL_ID, STATE_SCHEMA),
            Self::LocalBirthExpiry => (KERNEL31_ID, STATE31_SCHEMA),
        }
    }
}

#[derive(Clone, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Parameters {
    pub consolidation_mode: String,
    pub node_retention_mode: String,
    pub memory_growth_formula: String,
    pub node_wake_threshold: Option<f64>,
    pub edge_wake_threshold: Option<f64>,
    pub retain_nodes: bool,
    pub dead_node_retention_us: u64,
    pub dormant_traces_enabled: bool,
    pub revival_enabled: bool,
    pub memory_half_life_min_s: f64,
    pub memory_half_life_max_s: f64,
    pub memory_half_life_decay_rate: f64,
    pub memory_learning_gain: f64,
    pub memory_weight_learning_rate: f64,
    pub strong_fatigue_enabled: bool,
    pub strong_fatigue_tau_s: f64,
    pub strong_fatigue_gain: f64,
    pub dormant_prune_weight: f64,
}
impl Default for Parameters {
    fn default() -> Self {
        Self {
            consolidation_mode: "adaptive-half-life".into(),
            node_retention_mode: "automatic".into(),
            memory_growth_formula: "log-saturating".into(),
            node_wake_threshold: None,
            edge_wake_threshold: None,
            retain_nodes: false,
            dead_node_retention_us: 80_000_000,
            dormant_traces_enabled: false,
            revival_enabled: false,
            memory_half_life_min_s: 30.0,
            memory_half_life_max_s: 2_592_000.0,
            memory_half_life_decay_rate: 0.125,
            memory_learning_gain: 0.2,
            memory_weight_learning_rate: 0.55,
            strong_fatigue_enabled: true,
            strong_fatigue_tau_s: 5.0,
            strong_fatigue_gain: 1.0,
            dormant_prune_weight: 1e-8,
        }
    }
}
impl Parameters {
    pub fn adaptive(&self) -> bool {
        self.consolidation_mode == "adaptive-half-life"
    }
    pub fn validate(&self, c: &Config) -> Result<()> {
        if !["adaptive-half-life", "legacy-stability"].contains(&self.consolidation_mode.as_str()) {
            return Err("unknown consolidation_mode".into());
        }
        if !["automatic", "manual"].contains(&self.node_retention_mode.as_str()) {
            return Err("unknown node_retention_mode".into());
        }
        for value in [
            self.memory_half_life_min_s,
            self.memory_half_life_max_s,
            self.memory_half_life_decay_rate,
            self.memory_learning_gain,
            self.memory_weight_learning_rate,
            self.strong_fatigue_tau_s,
            self.strong_fatigue_gain,
            self.dormant_prune_weight,
        ] {
            if !value.is_finite() || !(0.0..=1e12).contains(&value) {
                return Err("invalid retention parameter".into());
            }
        }
        if c.propagation_limit.is_some() || c.edge_adaptation_limit.is_some() {
            return Err(
                "memory/3 does not support propagation/adaptation quotas; pace the host instead"
                    .into(),
            );
        }
        if !["log-saturating", "linear-saturating"].contains(&self.memory_growth_formula.as_str()) {
            return Err("unknown memory_growth_formula".into());
        }
        for v in [self.node_wake_threshold, self.edge_wake_threshold] {
            if v.is_some_and(|v| !v.is_finite() || !(1e-12..=1e12).contains(&v)) {
                return Err("invalid awakening threshold".into());
            }
        }
        if self.revival_enabled
            && (self.node_wake_threshold.is_none() || self.edge_wake_threshold.is_none())
        {
            return Err(
                "awakening requires explicit positive node_wake_threshold and edge_wake_threshold"
                    .into(),
            );
        }
        if self.memory_half_life_min_s < 1e-6
            || self.memory_half_life_min_s >= self.memory_half_life_max_s
            || self.strong_fatigue_tau_s < 1e-6
            || !(0.0 < self.dormant_prune_weight && self.dormant_prune_weight <= 1.0)
            || (self.dormant_traces_enabled && self.dormant_prune_weight >= c.prune_weight)
            || c.prune_support > 1.0
            || !(1..=9_007_199_254_740_991).contains(&self.dead_node_retention_us)
        {
            return Err("invalid retention bounds or timing".into());
        }
        Ok(())
    }
}
pub fn take(value: &mut Value) -> Result<Parameters> {
    let config = value
        .as_object_mut()
        .ok_or("retention config must be an object")?;
    let mut fields = serde_json::Map::new();
    for key in serde_json::to_value(Parameters::default())
        .unwrap()
        .as_object()
        .unwrap()
        .keys()
    {
        if let Some(value) = config.remove(key) {
            fields.insert(key.clone(), value);
        }
    }
    let mut p: Parameters =
        serde_json::from_value(Value::Object(fields)).map_err(|e| e.to_string())?;
    if !p.dormant_traces_enabled {
        p.revival_enabled = false;
    }
    Ok(p)
}
pub fn definition(mut value: Value, p: &Parameters, version: Version) -> Value {
    let (kernel, schema) = version.identity();
    value["kernel_id"] = json!(kernel);
    value["state_schema"] = json!(schema);
    value["hypothesis_id"] = json!(match version {
        Version::Original => "threemind.hypotheses/continuous-memory3",
        Version::LocalBirthExpiry => "threemind.hypotheses/continuous-memory3.1",
    });
    value["config"].as_object_mut().unwrap().extend(
        serde_json::to_value(p)
            .unwrap()
            .as_object()
            .unwrap()
            .clone(),
    );
    value["operators"].as_array_mut().unwrap().extend([
        json!({"id":"threemind.adaptive-half-life/2","phase":"local-touch-emission-expiry"}),
        json!({"id":"threemind.strong-input-fatigue/2","phase":"accepted-input"}),
        json!({"id":"threemind.optional-dormancy/2","phase":"local-expiry"}),
        json!({"id":"threemind.local-awakening/1","phase":"same-time-local-arrivals"}),
    ]);
    if matches!(version, Version::LocalBirthExpiry) {
        value["operators"].as_array_mut().unwrap().push(json!({
            "id": "threemind.zero-response-local-expiry/1",
            "phase": "after-local-reception"
        }));
    }
    value
}
pub(crate) fn decay(weight: f64, h: f64, dt: f64, p: &Parameters) -> (f64, f64) {
    let end = p
        .memory_half_life_min_s
        .max(h - p.memory_half_life_decay_rate * dt);
    let falling = if p.memory_half_life_decay_rate > 0.0 {
        dt.min((h - p.memory_half_life_min_s) / p.memory_half_life_decay_rate)
    } else {
        0.0
    };
    let integral = if falling > 0.0 {
        (h / end).ln() / p.memory_half_life_decay_rate
    } else {
        0.0
    } + (dt - falling) / end;
    (weight * (-2.0_f64.ln() * integral).exp(), end)
}

type Key = (u64, u64);
type TimerKey = (u8, u64, u64);
const DOSE_SECONDS: f64 = 0.1;
const AUDIT: [&str; 8] = [
    "dormant_created",
    "dormant_expired",
    "revived",
    "nodes_awakened",
    "nodes_deleted",
    "node_settlements",
    "edge_settlements",
    "expiry_checks",
];

pub(crate) fn grow(h: f64, dose: f64, p: &Parameters) -> f64 {
    if dose <= 0.0 {
        return h;
    }
    if p.memory_growth_formula == "linear-saturating" {
        return p
            .memory_half_life_max_s
            .min(h + p.memory_half_life_min_s * p.memory_learning_gain * dose);
    }
    let xmax = (p.memory_half_life_max_s / p.memory_half_life_min_s).ln();
    let x = (h / p.memory_half_life_min_s).ln();
    p.memory_half_life_max_s.min(
        p.memory_half_life_min_s
            * (xmax - (xmax - x) * (-p.memory_learning_gain * dose / xmax).exp()).exp(),
    )
}
pub(crate) fn crossing(q: f64, h: f64, floor: f64, p: &Parameters) -> Option<f64> {
    if floor <= 0.0 {
        return None;
    }
    if q <= floor {
        return Some(0.0);
    }
    let need = (q / floor).ln() / 2.0_f64.ln();
    let r = p.memory_half_life_decay_rate;
    if r == 0.0 {
        return Some(need * h);
    }
    let fall = (h / p.memory_half_life_min_s).ln() / r;
    Some(if need <= fall {
        h * -(-r * need).exp_m1() / r
    } else {
        (h - p.memory_half_life_min_s) / r + (need - fall) * p.memory_half_life_min_s
    })
}

pub(super) struct Operator {
    pub p: Parameters,
    pub version: Version,
    pub edges: BTreeMap<Key, (f64, u128)>,
    nodes: BTreeMap<u64, (f64, u128)>,
    pub dormant: BTreeMap<Key, (Edge, f64, u128)>,
    isolated: BTreeMap<u64, u128>,
    fatigue: BTreeMap<u64, (f64, u128)>,
    salience: BTreeMap<u64, (f64, u128)>,
    contacts: BTreeMap<u64, BTreeSet<Key>>,
    sleeping: BTreeSet<u64>,
    wake_edges: BTreeMap<Key, f64>,
    wake_nodes: BTreeMap<u64, f64>,
    deadlines: BTreeSet<(u128, TimerKey)>,
    timers: BTreeMap<TimerKey, u128>,
    pub strong_intensity: f64,
    audit: BTreeMap<String, u64>,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Saved {
    edges: Vec<(u64, u64, f64, String)>,
    nodes: Vec<(u64, f64, String)>,
    dormant: Vec<(Edge, f64, String)>,
    isolated: Vec<(u64, String)>,
    fatigue: Vec<(u64, f64, String)>,
    salience: Vec<(u64, f64, String)>,
    sleeping: Vec<u64>,
    deadlines: Vec<(u8, u64, u64, String)>,
    audit: BTreeMap<String, u64>,
}
impl Operator {
    pub fn new(p: Parameters, version: Version) -> Self {
        Self {
            p,
            version,
            edges: BTreeMap::new(),
            nodes: BTreeMap::new(),
            dormant: BTreeMap::new(),
            isolated: BTreeMap::new(),
            fatigue: BTreeMap::new(),
            salience: BTreeMap::new(),
            contacts: BTreeMap::new(),
            sleeping: BTreeSet::new(),
            wake_edges: BTreeMap::new(),
            wake_nodes: BTreeMap::new(),
            deadlines: BTreeSet::new(),
            timers: BTreeMap::new(),
            strong_intensity: 1.0,
            audit: AUDIT.into_iter().map(|s| (s.into(), 0)).collect(),
        }
    }
    fn count(&mut self, key: &str) {
        *self.audit.get_mut(key).unwrap() += 1;
    }
    fn timer(&mut self, k: TimerKey, time: Option<u128>) {
        if let Some(old) = self.timers.remove(&k) {
            self.deadlines.remove(&(old, k));
        }
        if let Some(t) = time {
            self.timers.insert(k, t);
            self.deadlines.insert((t, k));
        }
    }
    fn round(e: &Engine, seconds: Option<f64>) -> Option<u128> {
        let s = seconds?;
        if !s.is_finite() {
            return None;
        }
        let earliest = e.time + ((s * 1e6).ceil() as u128).max(1);
        let period = e.config.propagation_interval_us as u128;
        Some(
            e.next_propagation
                + earliest.saturating_sub(e.next_propagation).div_ceil(period) * period,
        )
    }
    pub fn node_value(&self, e: &Engine, id: u64, when: u128) -> (f64, f64) {
        let n = &e.nodes[e.node_index[&id]];
        let (h, t) = self.nodes[&id];
        if e.config.plasticity
            && e.config.support_decay_enabled
            && self.p.node_retention_mode == "automatic"
        {
            decay(n.support, h, (when - t) as f64 / 1e6, &self.p)
        } else {
            (n.support, h)
        }
    }
    pub fn edge_value(&self, e: &Engine, key: Key, when: u128) -> (f64, f64) {
        let (weight, h, t) = if let Some(&i) = e.edge_index.get(&key) {
            let (h, t) = self.edges[&key];
            (e.edges[i].weight, h, t)
        } else {
            let (edge, h, t) = &self.dormant[&key];
            (edge.weight, *h, *t)
        };
        if e.config.plasticity {
            let dt = (when - t) as f64 / 1e6;
            if self.p.adaptive() {
                return decay(weight, h, dt, &self.p);
            }
            if self.dormant.contains_key(&key) {
                return (weight * (-e.config.forgetting_rate * dt).exp(), h);
            }
        }
        (weight, h)
    }
    fn settle_node(&mut self, e: &mut Engine, id: u64) {
        if !self.nodes.contains_key(&id) {
            self.nodes
                .insert(id, (self.p.memory_half_life_min_s, e.time));
            self.isolated.insert(id, e.time);
        }
        let (q, h) = self.node_value(e, id, e.time);
        e.nodes[e.node_index[&id]].support = q;
        self.nodes.insert(id, (h, e.time));
        self.count("node_settlements");
    }
    pub fn prepare_edge(&mut self, e: &mut Engine, key: Key) {
        if self.edges.get(&key).is_none_or(|row| row.1 == e.time) {
            return;
        }
        let (q, h) = self.edge_value(e, key, e.time);
        e.edges[e.edge_index[&key]].weight = q;
        self.edges.insert(key, (h, e.time));
        self.count("edge_settlements");
    }
    fn schedule_node(&mut self, e: &Engine, id: u64) {
        let k = (0, id, 0);
        let c = &e.config;
        if self.p.retain_nodes
            || !c.plasticity
            || e.incident.get(&id).is_some_and(|v| !v.is_empty())
        {
            self.timer(k, None);
            return;
        }
        let n = &e.nodes[e.node_index[&id]];
        if n.activation > 0.0 && (!c.activation_decay_enabled || c.activation_floor <= 0.0) {
            self.timer(k, None);
            return;
        }
        let inactive = if n.activation > c.activation_floor {
            (c.activation_tau * (n.activation / c.activation_floor).ln()
                - (e.time - e.state_time) as f64 / 1e6)
                .max(0.0)
        } else {
            0.0
        };
        let delay = if self.p.node_retention_mode == "automatic" {
            let (q, h) = self.node_value(e, id, e.time);
            if c.support_decay_enabled {
                crossing(q, h, NODE_SUPPORT_FLOOR, &self.p)
            } else if q < NODE_SUPPORT_FLOOR {
                Some(0.0)
            } else {
                None
            }
        } else if c.prune_support == 0.0 {
            Some(
                (self.isolated[&id].max(parse_time(&n.last_touch_us).unwrap())
                    + self.p.dead_node_retention_us as u128)
                    .saturating_sub(e.time) as f64
                    / 1e6,
            )
        } else {
            let rate = if c.support_decay_enabled {
                (1.0 - n.stability) / c.support_tau
            } else {
                0.0
            };
            let delay = if rate > 0.0 {
                Some(((n.support - c.prune_support) / rate).max(0.0))
            } else if n.support < c.prune_support {
                Some(0.0)
            } else {
                None
            };
            delay.map(|d| {
                d.max(
                    (parse_time(&n.last_touch_us).unwrap() + c.node_prune_after_us as u128 + 1)
                        .saturating_sub(e.time) as f64
                        / 1e6,
                )
            })
        };
        self.timer(k, Self::round(e, delay.map(|d| d.max(inactive))));
    }
    pub fn edge_changed(&mut self, e: &Engine, key: Key) {
        if !self.edges.contains_key(&key) {
            self.drop_dormant(key);
            self.edges
                .insert(key, (self.p.memory_half_life_min_s, e.time));
        }
        for n in [key.0, key.1] {
            self.isolated.remove(&n);
            self.timer((0, n, 0), None);
        }
        self.schedule_edge(e, key);
    }
    fn schedule_edge(&mut self, e: &Engine, key: Key) {
        let t = if !e.config.plasticity {
            None
        } else if self.p.adaptive() {
            let (q, h) = self.edge_value(e, key, e.time);
            Self::round(e, crossing(q, h, e.config.prune_weight, &self.p))
        } else if e.edges[e.edge_index[&key]].weight < e.config.prune_weight {
            Self::round(e, Some(0.0))
        } else {
            None
        };
        self.timer((1, key.0, key.1), t);
    }
    fn schedule_dormant(&mut self, e: &Engine, key: Key) {
        let (q, h) = self.edge_value(e, key, e.time);
        let delay = if self.p.adaptive() {
            crossing(q, h, self.p.dormant_prune_weight, &self.p)
        } else if q > 0.0 && e.config.forgetting_rate > 0.0 {
            Some(((q / self.p.dormant_prune_weight).ln() / e.config.forgetting_rate).max(0.0))
        } else if q < self.p.dormant_prune_weight {
            Some(0.0)
        } else {
            None
        };
        self.timer(
            (2, key.0, key.1),
            if e.config.plasticity {
                Self::round(e, delay)
            } else {
                None
            },
        );
    }
    fn factor(&self, values: &BTreeMap<u64, (f64, u128)>, id: u64, when: u128) -> f64 {
        values.get(&id).map_or(0.0, |&(v, t)| {
            v * (-((when - t) as f64 / 1e6) / self.p.strong_fatigue_tau_s).exp()
        })
    }
    pub fn fatigue_response(&self, id: u64, when: u128) -> f64 {
        1.0 / (1.0 + self.factor(&self.fatigue, id, when))
    }
    pub fn gate(&mut self, id: u64, value: f64) -> bool {
        if self.p.revival_enabled && self.sleeping.contains(&id) {
            *self.wake_nodes.entry(id).or_default() += value;
            true
        } else {
            false
        }
    }
    pub fn node_quiet(&mut self, id: u64, isolated: bool) {
        if isolated && self.contacts.contains_key(&id) {
            self.sleeping.insert(id);
        }
    }
    pub fn touch(&mut self, id: u64, amount: f64, direct: bool, e: &mut Engine) {
        self.settle_node(e, id);
        if amount <= 0.0 {
            if matches!(self.version, Version::LocalBirthExpiry) {
                self.schedule_node(e, id);
            }
            return;
        }
        if e.incident.get(&id).is_none_or(|v| v.is_empty()) {
            self.isolated.insert(id, e.time);
        }
        let mut salience = self.factor(&self.salience, id, e.time);
        if direct && self.strong_intensity > 1.0 {
            let mut extra = amount * (self.strong_intensity - 1.0);
            if e.config.energy_simulation_enabled {
                extra = e
                    .energy
                    .afford(extra, e.config.energy_direct_cost, Cost::Direct);
            }
            salience = (salience + extra).min(1e12);
            self.salience.insert(id, (salience, e.time));
            if self.p.strong_fatigue_enabled {
                self.fatigue.insert(
                    id,
                    (
                        (self.factor(&self.fatigue, id, e.time)
                            + extra * self.p.strong_fatigue_gain)
                            .min(1e12),
                        e.time,
                    ),
                );
            }
        }
        if e.config.plasticity && self.p.node_retention_mode == "automatic" {
            let dose = amount * DOSE_SECONDS * (1.0 + salience);
            self.nodes.get_mut(&id).unwrap().0 = grow(self.nodes[&id].0, dose, &self.p);
            let n = &mut e.nodes[e.node_index[&id]];
            n.support =
                1.0 - (1.0 - n.support) * (-self.p.memory_weight_learning_rate * dose).exp();
        }
        self.schedule_node(e, id);
    }
    pub fn legacy_expired(&mut self, k: Key, time: u128) {
        self.timer((1, k.0, k.1), Some(time));
    }
    pub fn emitted(&mut self, e: &Engine, key: Key, amount: f64) {
        if e.config.plasticity && self.p.adaptive() && e.edge_consolidation_enabled {
            self.edges.get_mut(&key).unwrap().0 =
                grow(self.edges[&key].0, amount * DOSE_SECONDS, &self.p);
        }
        self.schedule_edge(e, key);
    }
    fn drop_dormant(&mut self, key: Key) {
        self.timer((2, key.0, key.1), None);
        if self.dormant.remove(&key).is_some() {
            for n in [key.0, key.1] {
                if let Some(s) = self.contacts.get_mut(&n) {
                    s.remove(&key);
                    if s.is_empty() {
                        self.contacts.remove(&n);
                    }
                }
            }
        }
        self.wake_edges.remove(&key);
    }
    fn removed_edge(&mut self, e: &Engine, key: Key) {
        self.edges.remove(&key);
        self.timer((1, key.0, key.1), None);
        for n in [key.0, key.1] {
            if e.node_index.contains_key(&n) && e.incident.get(&n).is_none_or(|v| v.is_empty()) {
                self.isolated.entry(n).or_insert(e.time);
                self.schedule_node(e, n);
            }
        }
    }
    pub fn node_output(&mut self, e: &Engine, n: &Node) {
        if !self.p.revival_enabled || e.silenced_nodes.contains(&n.id) {
            return;
        }
        let amount = n.activation
            * crate::restoration::response(&e.config, n)
            * self.fatigue_response(n.id, e.time)
            * e.config.propagation_rate
            * e.config.propagation_interval_us as f64
            / 1e6;
        if amount <= 0.0 || amount < e.config.activation_floor {
            return;
        }
        if let Some(keys) = self.contacts.get(&n.id) {
            for key in keys {
                if !e.silenced_edges.contains(key) {
                    *self.wake_edges.entry(*key).or_default() += amount;
                }
            }
        }
    }
    fn wake_arrivals(&mut self, e: &Engine) -> Vec<(u64, f64)> {
        let mut awake = vec![];
        for (n, v) in std::mem::take(&mut self.wake_nodes) {
            if self.sleeping.contains(&n)
                && v >= self.p.node_wake_threshold.unwrap()
                && !e.silenced_nodes.contains(&n)
            {
                self.sleeping.remove(&n);
                self.count("nodes_awakened");
                awake.push((n, v));
            }
        }
        awake
    }
    pub fn prune(&mut self, e: &mut Engine) {
        if !e.config.plasticity {
            self.wake_edges.clear();
            return;
        }
        while let Some(&(t, (kind, a, b))) = self.deadlines.first() {
            if t > e.time {
                break;
            }
            self.timer((kind, a, b), None);
            self.count("expiry_checks");
            let key = (a, b);
            if kind == 1 && e.edge_index.contains_key(&key) {
                self.prepare_edge(e, key);
                if e.edges[e.edge_index[&key]].weight < e.config.prune_weight {
                    let h = self.edges[&key].0;
                    let edge = e.remove_local_edge(key).unwrap();
                    self.removed_edge(e, key);
                    if self.p.dormant_traces_enabled && edge.weight >= self.p.dormant_prune_weight {
                        self.dormant.insert(key, (edge, h, e.time));
                        for n in [a, b] {
                            self.contacts.entry(n).or_default().insert(key);
                            if e.incident.get(&n).is_none_or(|v| v.is_empty())
                                && e.nodes[e.node_index[&n]].activation == 0.0
                            {
                                self.sleeping.insert(n);
                            }
                        }
                        self.schedule_dormant(e, key);
                        self.count("dormant_created");
                    }
                } else {
                    self.schedule_edge(e, key);
                }
            } else if kind == 2 && self.dormant.contains_key(&key) {
                let (q, _) = self.edge_value(e, key, e.time);
                if q < self.p.dormant_prune_weight {
                    self.drop_dormant(key);
                    self.count("dormant_expired");
                } else {
                    self.schedule_dormant(e, key);
                }
            } else if kind == 0 && e.node_index.contains_key(&a) {
                self.settle_node(e, a);
                let n = &e.nodes[e.node_index[&a]];
                let eligible = if self.p.node_retention_mode == "automatic" {
                    n.support < NODE_SUPPORT_FLOOR
                } else if e.config.prune_support > 0.0 {
                    n.support < e.config.prune_support
                        && e.time - parse_time(&n.last_touch_us).unwrap()
                            > e.config.node_prune_after_us as u128
                } else {
                    e.time
                        - self
                            .isolated
                            .get(&a)
                            .copied()
                            .unwrap_or(e.time)
                            .max(parse_time(&n.last_touch_us).unwrap())
                        >= self.p.dead_node_retention_us as u128
                };
                if !self.p.retain_nodes
                    && n.activation == 0.0
                    && e.incident.get(&a).is_none_or(|v| v.is_empty())
                    && eligible
                {
                    self.delete_node(e, a);
                } else {
                    if n.activation == 0.0
                        && e.incident.get(&a).is_none_or(|v| v.is_empty())
                        && self.contacts.contains_key(&a)
                    {
                        self.sleeping.insert(a);
                    }
                    self.schedule_node(e, a);
                }
            }
        }
        for (key, amount) in std::mem::take(&mut self.wake_edges) {
            if !self.dormant.contains_key(&key)
                || amount < self.p.edge_wake_threshold.unwrap()
                || e.silenced_edges.contains(&key)
                || e.silenced_nodes.contains(&key.0)
                || e.silenced_nodes.contains(&key.1)
            {
                continue;
            }
            let (q, h) = self.edge_value(e, key, e.time);
            let mut edge = self.dormant[&key].0.clone();
            self.drop_dormant(key);
            if q < self.p.dormant_prune_weight {
                continue;
            }
            edge.weight = q;
            e.edge_index.insert(key, e.edges.len());
            e.edges.push(edge);
            self.edges.insert(key, (h, e.time));
            e.outgoing.entry(key.0).or_default().insert(key.1);
            e.incident.entry(key.0).or_default().insert(key.1);
            e.incident.entry(key.1).or_default().insert(key.0);
            self.edge_changed(e, key);
            self.count("revived");
        }
    }
    fn forget_node(&mut self, n: u64) {
        for k in self.contacts.get(&n).cloned().unwrap_or_default() {
            self.drop_dormant(k);
        }
        self.nodes.remove(&n);
        self.isolated.remove(&n);
        self.fatigue.remove(&n);
        self.salience.remove(&n);
        self.sleeping.remove(&n);
        self.wake_nodes.remove(&n);
        self.timer((0, n, 0), None);
    }
    fn delete_node(&mut self, e: &mut Engine, n: u64) {
        self.forget_node(n);
        let i = e.node_index.remove(&n).unwrap();
        let old = e.nodes.remove(i);
        // Preserve canonical reduction order. Only compacted vector offsets change;
        // receptor, edge and adjacency indexes are not rebuilt.
        for j in i..e.nodes.len() {
            e.node_index.insert(e.nodes[j].id, j);
        }
        e.receptors.remove(&old.channel);
        e.silenced_nodes.remove(&n);
        e.spatial_points.remove(&n);
        self.count("nodes_deleted");
    }
    pub fn intervene(&mut self, e: &mut Engine, nodes: &[u64], edges: &[Key], action: &str) {
        let mut touched: BTreeSet<u64> = nodes.iter().copied().collect();
        for &k in edges {
            touched.extend([k.0, k.1]);
            if ["disconnect_edges", "delete_nodes", "silence"].contains(&action) {
                self.drop_dormant(k);
            }
        }
        for &n in nodes {
            if ["disconnect_edges", "delete_nodes", "silence"].contains(&action) {
                for k in self.contacts.get(&n).cloned().unwrap_or_default() {
                    self.drop_dormant(k);
                }
            }
        }
        for &key in edges {
            if !e.edge_index.contains_key(&key) {
                self.removed_edge(e, key);
            }
        }
        for n in touched {
            if !e.node_index.contains_key(&n) {
                self.forget_node(n);
            } else if e.incident.get(&n).is_none_or(|v| v.is_empty()) {
                self.isolated.entry(n).or_insert(e.time);
                self.schedule_node(e, n);
            }
        }
    }
    pub fn settle_configuration(&mut self, e: &mut Engine) {
        for n in self.nodes.keys().copied().collect::<Vec<_>>() {
            self.settle_node(e, n);
        }
        for k in self.edges.keys().copied().collect::<Vec<_>>() {
            self.prepare_edge(e, k);
        }
        for k in self.dormant.keys().copied().collect::<Vec<_>>() {
            let (q, h) = self.edge_value(e, k, e.time);
            let row = self.dormant.get_mut(&k).unwrap();
            row.0.weight = q;
            row.1 = h;
            row.2 = e.time;
        }
        for n in self.fatigue.keys().copied().collect::<Vec<_>>() {
            self.fatigue
                .insert(n, (self.factor(&self.fatigue, n, e.time), e.time));
        }
        for n in self.salience.keys().copied().collect::<Vec<_>>() {
            self.salience
                .insert(n, (self.factor(&self.salience, n, e.time), e.time));
        }
    }
    pub fn configure(&mut self, e: &Engine, p: Parameters) {
        self.p = p;
        self.timers.clear();
        self.deadlines.clear();
        for (h, _) in self.nodes.values_mut().chain(self.edges.values_mut()) {
            *h = h.clamp(self.p.memory_half_life_min_s, self.p.memory_half_life_max_s);
        }
        for k in self.dormant.keys().copied().collect::<Vec<_>>() {
            if !self.p.dormant_traces_enabled
                || self.dormant[&k].0.weight < self.p.dormant_prune_weight
            {
                self.drop_dormant(k);
            } else {
                let row = self.dormant.get_mut(&k).unwrap();
                row.1 = row
                    .1
                    .clamp(self.p.memory_half_life_min_s, self.p.memory_half_life_max_s);
                self.schedule_dormant(e, k);
            }
        }
        if !self.p.revival_enabled {
            self.sleeping.clear();
            self.wake_nodes.clear();
            self.wake_edges.clear();
        }
        if !self.p.strong_fatigue_enabled {
            self.fatigue.clear();
        }
        for n in self.nodes.keys().copied().collect::<Vec<_>>() {
            self.schedule_node(e, n);
        }
        for k in self.edges.keys().copied().collect::<Vec<_>>() {
            self.schedule_edge(e, k);
        }
    }
    pub fn capture(&self) -> Value {
        serde_json::to_value(Saved {
            nodes: self
                .nodes
                .iter()
                .map(|(&n, &(h, t))| (n, h, t.to_string()))
                .collect(),
            edges: self
                .edges
                .iter()
                .map(|(&(a, b), &(h, t))| (a, b, h, t.to_string()))
                .collect(),
            dormant: self
                .dormant
                .values()
                .map(|(e, h, t)| (e.clone(), *h, t.to_string()))
                .collect(),
            isolated: self
                .isolated
                .iter()
                .map(|(&n, t)| (n, t.to_string()))
                .collect(),
            fatigue: self
                .fatigue
                .iter()
                .map(|(&n, &(v, t))| (n, v, t.to_string()))
                .collect(),
            salience: self
                .salience
                .iter()
                .map(|(&n, &(v, t))| (n, v, t.to_string()))
                .collect(),
            sleeping: self.sleeping.iter().copied().collect(),
            deadlines: self
                .deadlines
                .iter()
                .map(|&(t, (k, a, b))| (k, a, b, t.to_string()))
                .collect(),
            audit: self.audit.clone(),
        })
        .unwrap()
    }
    pub fn metrics(&self, e: &Engine) -> Value {
        let mut v = serde_json::to_value(&self.audit).unwrap();
        v["dormant"] = json!(self.dormant.len());
        v["isolated"] = json!(self.isolated.len());
        v["node_half_life_max_s"] = json!(self
            .nodes
            .keys()
            .map(|&n| self.node_value(e, n, e.time).1)
            .fold(0.0, f64::max));
        v["half_life_max_s"] = json!(self
            .edges
            .keys()
            .map(|&k| self.edge_value(e, k, e.time).1)
            .fold(0.0, f64::max));
        v
    }
    pub fn restore(p: Parameters, saved: Value, e: &Engine, version: Version) -> Result<Self> {
        let saved: Saved = serde_json::from_value(saved).map_err(|x| x.to_string())?;
        let mut op = Self::new(p, version);
        let time = |s: &str| -> Result<u128> {
            let t = parse_time(s)?;
            if t > e.time {
                Err("future retention anchor".into())
            } else {
                Ok(t)
            }
        };
        let half = |h: f64| {
            h.is_finite()
                && (op.p.memory_half_life_min_s..=op.p.memory_half_life_max_s).contains(&h)
        };
        for (n, h, t) in saved.nodes {
            let t = time(&t)?;
            if !e.node_index.contains_key(&n)
                || !half(h)
                || t < parse_time(&e.nodes[e.node_index[&n]].birth_us)?
                || op.nodes.insert(n, (h, t)).is_some()
            {
                return Err("invalid node retention state".into());
            }
        }
        for (a, b, h, t) in saved.edges {
            let k = (a, b);
            let t = time(&t)?;
            if !e.edge_index.contains_key(&k)
                || !half(h)
                || t < parse_time(&e.edges[e.edge_index[&k]].birth_us)?
                || op.edges.insert(k, (h, t)).is_some()
            {
                return Err("invalid edge retention state".into());
            }
        }
        if op.nodes.len() != e.nodes.len() || op.edges.len() != e.edges.len() {
            return Err("missing retention anchors".into());
        }
        for (edge, h, t) in saved.dormant {
            let k = (edge.source, edge.target);
            let t = time(&t)?;
            if !op.p.dormant_traces_enabled
                || !half(h)
                || e.edge_index.contains_key(&k)
                || op.dormant.contains_key(&k)
                || k.0 == k.1
                || !e.node_index.contains_key(&k.0)
                || !e.node_index.contains_key(&k.1)
                || !edge.weight.is_finite()
                || !(op.p.dormant_prune_weight..=1.0).contains(&edge.weight)
                || ![edge.stability, edge.eligibility]
                    .iter()
                    .all(|v| v.is_finite() && (0.0..=1.0).contains(v))
                || parse_time(&edge.birth_us)? > parse_time(&edge.last_touch_us)?
                || parse_time(&edge.last_touch_us)? > t
            {
                return Err("invalid dormant contact".into());
            }
            op.dormant.insert(k, (edge, h, t));
            for n in [k.0, k.1] {
                op.contacts.entry(n).or_default().insert(k);
            }
        }
        for (n, t) in saved.isolated {
            let t = time(&t)?;
            if !e.node_index.contains_key(&n)
                || op.isolated.contains_key(&n)
                || e.incident.get(&n).is_some_and(|v| !v.is_empty())
                || t < parse_time(&e.nodes[e.node_index[&n]].birth_us)?
            {
                return Err("invalid isolation clock".into());
            }
            op.isolated.insert(n, t);
        }
        if op.isolated.len()
            != e.nodes
                .iter()
                .filter(|n| e.incident.get(&n.id).is_none_or(|v| v.is_empty()))
                .count()
        {
            return Err("missing isolation clock".into());
        }
        for (name, rows) in [("fatigue", saved.fatigue), ("salience", saved.salience)] {
            for (n, v, t) in rows {
                let t = time(&t)?;
                if !e.node_index.contains_key(&n)
                    || !v.is_finite()
                    || !(0.0..=1e12).contains(&v)
                    || (name == "fatigue" && !op.p.strong_fatigue_enabled)
                    || t < parse_time(&e.nodes[e.node_index[&n]].birth_us)?
                {
                    return Err("invalid local fatigue state".into());
                }
                let dest = if name == "fatigue" {
                    &mut op.fatigue
                } else {
                    &mut op.salience
                };
                if dest.insert(n, (v, t)).is_some() {
                    return Err("duplicate local fatigue state".into());
                }
            }
        }
        for n in saved.sleeping {
            if !e.node_index.contains_key(&n)
                || !op.p.dormant_traces_enabled
                || !op.sleeping.insert(n)
            {
                return Err("invalid sleeping node".into());
            }
        }
        for (kind, a, b, t) in saved.deadlines {
            let t = parse_time(&t)?;
            let k = (kind, a, b);
            let valid = (kind == 0 && b == 0 && e.node_index.contains_key(&a))
                || (kind == 1 && e.edge_index.contains_key(&(a, b)))
                || (kind == 2 && op.dormant.contains_key(&(a, b)));
            if !valid
                || op.timers.contains_key(&k)
                || t <= e.time
                || t < e.next_propagation
                || (t - e.next_propagation) % e.config.propagation_interval_us as u128 != 0
            {
                return Err("invalid local expiry".into());
            }
            op.timer(k, Some(t));
        }
        if saved.audit.keys().ne(op.audit.keys()) {
            return Err("invalid retention audit".into());
        }
        op.audit = saved.audit;
        let timers = op.timers.clone();
        let deadlines = op.deadlines.clone();
        op.timers.clear();
        op.deadlines.clear();
        for &n in e.node_index.keys() {
            op.schedule_node(e, n);
        }
        for &k in e.edge_index.keys() {
            op.schedule_edge(e, k);
        }
        for k in op.dormant.keys().copied().collect::<Vec<_>>() {
            op.schedule_dormant(e, k);
        }
        if op.timers.keys().ne(timers.keys())
            || op
                .timers
                .iter()
                .any(|(k, t)| t.abs_diff(timers[k]) > e.config.propagation_interval_us as u128)
        {
            return Err("missing or inconsistent local expiry".into());
        }
        op.timers = timers;
        op.deadlines = deadlines;
        Ok(op)
    }
}
impl Engine {
    pub(super) fn automatic_node_retention(&self) -> bool {
        self.retention
            .as_ref()
            .is_some_and(|o| o.p.node_retention_mode == "automatic")
    }
    pub(super) fn fatigue_response(&self, id: u64) -> f64 {
        self.retention
            .as_ref()
            .map_or(1.0, |o| o.fatigue_response(id, self.time))
    }
    pub(super) fn retention_prepare_edge(&mut self, k: Key) {
        if let Some(mut op) = self.retention.take() {
            op.prepare_edge(self, k);
            self.retention = Some(op);
        }
    }
    pub(super) fn retention_edge_changed(&mut self, k: Key) {
        if let Some(mut op) = self.retention.take() {
            op.edge_changed(self, k);
            self.retention = Some(op);
        }
    }
    pub(super) fn retention_node_changed(&mut self, n: u64) {
        if let Some(mut op) = self.retention.take() {
            op.schedule_node(self, n);
            self.retention = Some(op);
        }
    }
    pub(super) fn retention_emitted(&mut self, k: Key, v: f64) {
        if let Some(mut op) = self.retention.take() {
            op.emitted(self, k, v);
            self.retention = Some(op);
        }
    }
    pub(super) fn retention_node_output(&mut self, n: &Node) {
        if let Some(mut op) = self.retention.take() {
            op.node_output(self, n);
            self.retention = Some(op);
        }
    }
    pub(super) fn retention_wake_arrivals(&mut self) {
        if let Some(mut op) = self.retention.take() {
            let rows = op.wake_arrivals(self);
            self.retention = Some(op);
            for (n, v) in rows {
                let amount = self.touch(n, v, false);
                if amount > 0.0 {
                    self.update_touched(&[(n, amount)]);
                }
            }
        }
    }
    pub(super) fn remove_local_edge(&mut self, k: Key) -> Option<Edge> {
        let i = self.edge_index.remove(&k)?;
        let edge = self.edges.swap_remove(i);
        if i < self.edges.len() {
            let e = &self.edges[i];
            self.edge_index.insert((e.source, e.target), i);
        }
        if let Some(s) = self.outgoing.get_mut(&k.0) {
            s.remove(&k.1);
            if s.is_empty() {
                self.outgoing.remove(&k.0);
            }
        }
        if !self.edge_index.contains_key(&(k.1, k.0)) {
            for (a, b) in [(k.0, k.1), (k.1, k.0)] {
                if let Some(s) = self.incident.get_mut(&a) {
                    s.remove(&b);
                    if s.is_empty() {
                        self.incident.remove(&a);
                    }
                }
            }
        }
        self.traversed.remove(&k);
        if let Some(o) = self.continuous.as_mut() {
            o.short_term.remove(&k);
            o.fast.remove(&k);
        }
        if let Some(o) = self.novelty.as_mut() {
            o.cancel(k);
        }
        Some(edge)
    }
    pub(super) fn intervene_retention(&mut self, nodes: &[u64], edges: &[Key], action: &str) {
        let mut op = self.retention.take().unwrap();
        let mut keys: BTreeSet<Key> = edges.iter().copied().collect();
        if action == "delete_nodes" {
            for &n in nodes {
                for &other in self.incident.get(&n).into_iter().flatten() {
                    for k in [(n, other), (other, n)] {
                        if self.edge_index.contains_key(&k) {
                            keys.insert(k);
                        }
                    }
                }
            }
        }
        for &k in &keys {
            if action == "disconnect_edges" || action == "delete_nodes" {
                self.remove_local_edge(k);
                op.removed_edge(self, k);
                self.silenced_edges.remove(&k);
            } else if action == "silence" {
                self.silenced_edges.insert(k);
            } else {
                self.silenced_edges.remove(&k);
            }
        }
        op.intervene(
            self,
            nodes,
            &keys.iter().copied().collect::<Vec<_>>(),
            action,
        );
        for &n in nodes {
            if action == "delete_nodes" {
                op.delete_node(self, n);
            } else if action == "silence" {
                self.silenced_nodes.insert(n);
                let row = &mut self.nodes[self.node_index[&n]];
                row.activation = 0.0;
                row.direct = 0.0;
                row.associative = 0.0;
                op.schedule_node(self, n);
            } else {
                self.silenced_nodes.remove(&n);
            }
        }
        self.retention = Some(op);
        self.sequence += 1;
        self.lifecycle();
    }
}
