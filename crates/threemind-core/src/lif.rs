//! Independent adaptive leaky integrate-and-fire candidate; see candidate-mechanisms.md.
use crate::mechanisms::{cascade, ShortTermConfig, ShortTermState};
use crate::{canonical_hash, parse_time, Edge, Event, Node, Result, Stimulus};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet, BinaryHeap};

pub const KERNEL_ID: &str = "threemind.lif/1";
pub const STATE_SCHEMA: &str = "threemind.lif-state/1";

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Config {
    pub step_us: u64,
    pub delay_us: u64,
    pub refractory_us: u64,
    pub quiescence_death_us: u64,
    pub seed: u64,
    pub plasticity: bool,
    pub inhibition: bool,
    pub leak_enabled: bool,
    pub current_decay_enabled: bool,
    pub rest_mv: f64,
    pub reset_mv: f64,
    pub threshold_mv: f64,
    pub resistance_mohm: f64,
    pub membrane_tau_s: f64,
    pub current_tau_s: f64,
    pub adaptation_tau_s: f64,
    pub adaptation_jump_na: f64,
    pub input_gain_na: f64,
    pub spike_gain_na: f64,
    pub voltage_epsilon_mv: f64,
    pub current_epsilon_na: f64,
    pub birth_weight: f64,
    pub stdp_enabled: bool,
    pub stdp_tau_pre_s: f64,
    pub stdp_tau_post_s: f64,
    pub stdp_a_plus: f64,
    pub stdp_a_minus: f64,
    pub stp_enabled: bool,
    pub stp_utilization: f64,
    pub stp_recovery_tau_s: f64,
    pub stp_active_tau_s: f64,
    pub stp_facilitation_tau_s: f64,
    pub max_nodes: u64,
    pub max_edges: u64,
}
impl Default for Config {
    fn default() -> Self {
        Self {
            step_us: 250,
            delay_us: 1000,
            refractory_us: 2000,
            quiescence_death_us: 1000000,
            seed: 20260724,
            plasticity: true,
            inhibition: true,
            leak_enabled: true,
            current_decay_enabled: true,
            rest_mv: -65.0,
            reset_mv: -65.0,
            threshold_mv: -50.0,
            resistance_mohm: 100.0,
            membrane_tau_s: 0.02,
            current_tau_s: 0.005,
            adaptation_tau_s: 0.1,
            adaptation_jump_na: 0.01,
            input_gain_na: 1.0,
            spike_gain_na: 0.3,
            voltage_epsilon_mv: 1e-06,
            current_epsilon_na: 1e-08,
            birth_weight: 0.05,
            stdp_enabled: true,
            stdp_tau_pre_s: 0.02,
            stdp_tau_post_s: 0.02,
            stdp_a_plus: 0.01,
            stdp_a_minus: 0.0105,
            stp_enabled: true,
            stp_utilization: 0.5,
            stp_recovery_tau_s: 0.8,
            stp_active_tau_s: 0.003,
            stp_facilitation_tau_s: 0.0,
            max_nodes: 10000,
            max_edges: 200000,
        }
    }
}

impl Config {
    pub fn parse(mut value: Value) -> Result<Self> {
        let map = value
            .as_object_mut()
            .ok_or("LIF config must be an object")?;
        for (key, v) in map.iter_mut() {
            if key.ends_with("_us") {
                let n = if let Some(s) = v.as_str() {
                    parse_time(s)?
                } else {
                    v.as_u64().ok_or("invalid duration")? as u128
                };
                if n > (1u128 << 53) - 1 {
                    return Err("duration exceeds exact configuration range".into());
                }
                *v = json!(n as u64);
            }
        }
        let c: Self = serde_json::from_value(value).map_err(|e| e.to_string())?;
        c.validate()?;
        Ok(c)
    }
    pub fn value(&self) -> Value {
        let mut v = serde_json::to_value(self).unwrap();
        for (key, value) in v.as_object_mut().unwrap().iter_mut() {
            if key.ends_with("_us") {
                *value = json!(value.as_u64().unwrap().to_string());
            }
        }
        v
    }
    fn validate(&self) -> Result<()> {
        let values = serde_json::to_value(self).unwrap();
        for (key, v) in values.as_object().unwrap() {
            if v.is_boolean() || key.ends_with("_us") {
                continue;
            }
            if matches!(key.as_str(), "seed" | "max_nodes" | "max_edges") {
                if v.as_u64().unwrap() > u32::MAX as u64 {
                    return Err("integer out of range".into());
                }
            } else {
                finite(
                    v.as_f64().ok_or("invalid physical parameter")?,
                    if key.ends_with("_mv") { -1000.0 } else { 0.0 },
                    1e6,
                )?;
            }
        }
        if !(1..=1_000_000).contains(&self.step_us) || !(1..=10_000_000).contains(&self.delay_us) {
            return Err("LIF step or delay outside supported range".into());
        }
        if !(self.rest_mv <= self.reset_mv && self.reset_mv < self.threshold_mv)
            || self.threshold_mv - self.rest_mv < 0.0001
        {
            return Err("require rest <= reset < threshold".into());
        }
        for v in [
            self.resistance_mohm,
            self.membrane_tau_s,
            self.current_tau_s,
            self.adaptation_tau_s,
            self.stdp_tau_pre_s,
            self.stdp_tau_post_s,
            self.stp_recovery_tau_s,
            self.stp_active_tau_s,
        ] {
            if v <= 0.0 {
                return Err("time constants and resistance must be positive".into());
            }
        }
        for v in [
            self.birth_weight,
            self.stdp_a_plus,
            self.stdp_a_minus,
            self.stp_utilization,
        ] {
            finite(v, 0.0, 1.0)?;
        }
        if self.voltage_epsilon_mv < 0.0
            || self.voltage_epsilon_mv >= self.threshold_mv - self.rest_mv
        {
            return Err("invalid voltage epsilon".into());
        }
        self.short_term().validate()
    }
    fn short_term(&self) -> ShortTermConfig {
        ShortTermConfig {
            utilization: self.stp_utilization,
            recovery_tau_s: self.stp_recovery_tau_s,
            active_tau_s: self.stp_active_tau_s,
            facilitation_tau_s: self.stp_facilitation_tau_s,
        }
    }
}

fn finite(v: f64, low: f64, high: f64) -> Result<()> {
    if !v.is_finite() || v < low || v > high {
        Err("nonfinite or out-of-range physical quantity".into())
    } else {
        Ok(())
    }
}
mod decimal {
    use serde::{Deserialize, Deserializer, Serializer};
    pub fn serialize<S: Serializer>(v: &u128, s: S) -> std::result::Result<S::Ok, S::Error> {
        s.serialize_str(&v.to_string())
    }
    pub fn deserialize<'de, D: Deserializer<'de>>(d: D) -> std::result::Result<u128, D::Error> {
        let s = String::deserialize(d)?;
        crate::parse_time(&s).map_err(serde::de::Error::custom)
    }
}
mod optional_decimal {
    use serde::{Deserialize, Deserializer, Serializer};
    pub fn serialize<S: Serializer>(
        v: &Option<u128>,
        s: S,
    ) -> std::result::Result<S::Ok, S::Error> {
        match v {
            Some(n) => s.serialize_some(&n.to_string()),
            None => s.serialize_none(),
        }
    }
    pub fn deserialize<'de, D: Deserializer<'de>>(
        d: D,
    ) -> std::result::Result<Option<u128>, D::Error> {
        Option::<String>::deserialize(d)?
            .map(|s| crate::parse_time(&s).map_err(serde::de::Error::custom))
            .transpose()
    }
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Membrane {
    id: u64,
    channel: u32,
    voltage_mv: f64,
    current_na: f64,
    adaptation_na: f64,
    #[serde(with = "decimal")]
    refractory_until_us: u128,
    #[serde(with = "optional_decimal")]
    last_spike_us: Option<u128>,
    spikes: u64,
    touches: u64,
    #[serde(with = "decimal")]
    birth_us: u128,
    #[serde(with = "decimal")]
    last_touch_us: u128,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Synapse {
    id: u64,
    source: u64,
    target: u64,
    weight: f64,
    pre: f64,
    post: f64,
    #[serde(with = "decimal")]
    trace_time_us: u128,
    #[serde(with = "decimal")]
    birth_us: u128,
    #[serde(with = "decimal")]
    last_touch_us: u128,
    touches: u64,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Resource {
    source: u64,
    target: u64,
    state: ShortTermState,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Traffic {
    sent_na: f64,
    received_na: f64,
    unavailable_na: f64,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Rejections {
    nodes: u64,
    edges: u64,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Snapshot {
    schema: String,
    dynamics: String,
    config: Value,
    definition: Value,
    definition_hash: String,
    #[serde(with = "decimal")]
    time_us: u128,
    #[serde(with = "decimal")]
    state_time_us: u128,
    #[serde(with = "decimal")]
    next_step_us: u128,
    sequence: u64,
    next_event: u64,
    next_node: u64,
    next_synapse: u64,
    life: String,
    sources_open: bool,
    #[serde(with = "optional_decimal")]
    quiet_since_us: Option<u128>,
    nodes: Vec<Node>,
    edges: Vec<Edge>,
    membranes: Vec<Membrane>,
    synapses: Vec<Synapse>,
    active: Vec<u64>,
    silenced_nodes: Vec<u64>,
    silenced_edges: Vec<(u64, u64)>,
    short_term: Vec<Resource>,
    queue: Vec<crate::SavedEvent>,
    transport: Traffic,
    capacity_rejections: Rejections,
}
type Key = (u64, u64);
type Message = (u64, u64, u64, f64);

pub struct LifEngine {
    pub config: Config,
    pub time: u128,
    state_time: u128,
    next_step: u128,
    pub sequence: u64,
    next_event: u64,
    next_node: u64,
    next_synapse: u64,
    pub life: String,
    sources_open: bool,
    quiet: Option<u128>,
    nodes: BTreeMap<u64, Membrane>,
    edges: BTreeMap<Key, Synapse>,
    channels: BTreeMap<u32, u64>,
    outgoing: BTreeMap<u64, BTreeSet<u64>>,
    incoming: BTreeMap<u64, BTreeSet<u64>>,
    resources: BTreeMap<Key, ShortTermState>,
    active: BTreeSet<u64>,
    silenced_nodes: BTreeSet<u64>,
    silenced_edges: BTreeSet<Key>,
    queue: BinaryHeap<Event>,
    transport: Traffic,
    rejected: Rejections,
}
impl LifEngine {
    pub fn new(value: Value) -> Result<Self> {
        let config = Config::parse(value)?;
        Ok(Self {
            next_step: config.step_us as u128,
            config,
            time: 0,
            state_time: 0,
            sequence: 0,
            next_event: 0,
            next_node: 1,
            next_synapse: 1,
            life: "waiting".into(),
            sources_open: true,
            quiet: None,
            nodes: BTreeMap::new(),
            edges: BTreeMap::new(),
            channels: BTreeMap::new(),
            outgoing: BTreeMap::new(),
            incoming: BTreeMap::new(),
            resources: BTreeMap::new(),
            active: BTreeSet::new(),
            silenced_nodes: BTreeSet::new(),
            silenced_edges: BTreeSet::new(),
            queue: BinaryHeap::new(),
            transport: Traffic {
                sent_na: 0.0,
                received_na: 0.0,
                unavailable_na: 0.0,
            },
            rejected: Rejections { nodes: 0, edges: 0 },
        })
    }
    pub fn definition(&self) -> Value {
        json!({"schema":"threemind.kernel-definition/1","kernel_id":KERNEL_ID,"state_schema":STATE_SCHEMA,
        "hypothesis_id":"threemind.hypotheses/lif1","config":self.config.value(),"operators":[
            {"id":"threemind.adaptive-rc/1","phase":"passive-evolution"},
            {"id":"threemind.co-input-growth/1","phase":"external-contact"},
            {"id":"threemind.lif-threshold-reset/1","phase":"fixed-grid"},
            {"id":"threemind.arrival-pair-stdp/1","phase":"arrival-and-spike"},
            {"id":"threemind.tm-synapse/1","phase":"before-spike-emission"},
            {"id":"threemind.physical-activity-life/1","phase":"after-arrivals-and-spikes"}]})
    }
    fn grid_after(&self, now: u128) -> Result<u128> {
        (now / self.config.step_us as u128 + 1)
            .checked_mul(self.config.step_us as u128)
            .ok_or("clock overflow".into())
    }
    fn event(&mut self, time: u128, kind: &str, payload: Value) -> u64 {
        let id = self.next_event;
        self.next_event += 1;
        self.queue.push(Event {
            time,
            id,
            kind: kind.into(),
            payload,
        });
        id
    }
    pub fn inject(&mut self, stimulus: Stimulus) -> Result<u64> {
        stimulus.validate()?;
        let when = parse_time(&stimulus.time_us)?;
        if self.life == "dead" || !self.sources_open || when < self.time {
            return Err("inputs closed, dead, or input in the past".into());
        }
        Ok(self.event(when, "stimulus", serde_json::to_value(stimulus).unwrap()))
    }
    pub fn close_inputs(&mut self) {
        if self.sources_open {
            self.sources_open = false;
            self.sequence += 1;
        }
    }
    pub fn is_empty(&self) -> bool {
        self.nodes.is_empty()
    }
    fn present(&self, n: &Membrane) -> bool {
        let c = &self.config;
        (n.voltage_mv - c.rest_mv).abs() > 0.0
            && (n.voltage_mv - c.rest_mv).abs() >= c.voltage_epsilon_mv
            || n.current_na > 0.0 && n.current_na >= c.current_epsilon_na
            || n.adaptation_na > 0.0 && n.adaptation_na >= c.current_epsilon_na
    }
    fn project(&self, n: &Membrane, when: u128) -> Membrane {
        let mut n = n.clone();
        let c = &self.config;
        let mut start = self.state_time;
        if when <= start {
            return n;
        }
        let held = when.min(start.max(n.refractory_until_us)) - start;
        if held > 0 {
            let dt = held as f64 / 1e6;
            n.voltage_mv = c.reset_mv;
            if c.current_decay_enabled {
                n.current_na *= (-dt / c.current_tau_s).exp();
            }
            n.adaptation_na *= (-dt / c.adaptation_tau_s).exp();
            start += held;
        }
        let dt = (when - start) as f64 / 1e6;
        if dt > 0.0 {
            let coupling = |tau: f64, decays: bool| -> f64 {
                if !c.leak_enabled {
                    if decays {
                        tau / c.membrane_tau_s * -(-dt / tau).exp_m1()
                    } else {
                        dt / c.membrane_tau_s
                    }
                } else if decays {
                    cascade(dt, tau, c.membrane_tau_s)
                } else {
                    -(-dt / c.membrane_tau_s).exp_m1()
                }
            };
            let mut v = c.rest_mv
                + (n.voltage_mv - c.rest_mv)
                    * if c.leak_enabled {
                        (-dt / c.membrane_tau_s).exp()
                    } else {
                        1.0
                    };
            v += c.resistance_mohm
                * n.current_na
                * coupling(c.current_tau_s, c.current_decay_enabled);
            if c.inhibition {
                v -= c.resistance_mohm * n.adaptation_na * coupling(c.adaptation_tau_s, true);
            }
            n.voltage_mv = v;
            if c.current_decay_enabled {
                n.current_na *= (-dt / c.current_tau_s).exp();
            }
            n.adaptation_na *= (-dt / c.adaptation_tau_s).exp();
        }
        if !c.inhibition {
            n.adaptation_na = 0.0;
        }
        n
    }
    fn relax(&mut self, when: u128) -> Result<()> {
        for id in &self.active {
            let n = self.project(&self.nodes[id], when);
            finite(n.voltage_mv, -f64::MAX, f64::MAX)?;
            finite(n.current_na, 0.0, f64::MAX)?;
            finite(n.adaptation_na, 0.0, f64::MAX)?;
            self.nodes.insert(*id, n);
        }
        self.state_time = when;
        Ok(())
    }
    fn current(&mut self, id: u64, amount: f64) -> Result<()> {
        self.transport.received_na += amount;
        if self.silenced_nodes.contains(&id) || !self.nodes.contains_key(&id) {
            self.transport.unavailable_na += amount;
            return Ok(());
        }
        if amount <= 0.0 {
            return Ok(());
        }
        let n = self.nodes.get_mut(&id).unwrap();
        n.current_na += amount;
        finite(n.current_na, 0.0, f64::MAX)?;
        n.touches += 1;
        n.last_touch_us = self.state_time;
        self.active.insert(id);
        Ok(())
    }
    fn grow(&mut self, contacts: &[(u64, f64)]) {
        if !self.config.plasticity || self.config.birth_weight == 0.0 {
            return;
        }
        for &(source, a) in contacts {
            for &(target, b) in contacts {
                if source == target || self.edges.contains_key(&(source, target)) {
                    continue;
                }
                if self.edges.len() >= self.config.max_edges as usize {
                    self.rejected.edges += 1;
                    continue;
                }
                self.edges.insert(
                    (source, target),
                    Synapse {
                        id: self.next_synapse,
                        source,
                        target,
                        weight: self.config.birth_weight * a * b,
                        pre: 0.0,
                        post: 0.0,
                        trace_time_us: self.state_time,
                        birth_us: self.state_time,
                        last_touch_us: self.state_time,
                        touches: 0,
                    },
                );
                self.next_synapse += 1;
                self.outgoing.entry(source).or_default().insert(target);
                self.incoming.entry(target).or_default().insert(source);
            }
        }
    }
    fn input(&mut self, payload: Value) -> Result<()> {
        let s: Stimulus = serde_json::from_value(payload).map_err(|e| e.to_string())?;
        let mut contacts = vec![];
        for (channel, amplitude) in s.channels {
            let amount = amplitude * s.intensity * self.config.input_gain_na;
            if amount <= 0.0 {
                continue;
            }
            finite(amount, 0.0, f64::MAX)?;
            let id = if let Some(id) = self.channels.get(&channel) {
                *id
            } else {
                if self.nodes.len() >= self.config.max_nodes as usize {
                    self.rejected.nodes += 1;
                    continue;
                }
                let id = self.next_node;
                self.next_node += 1;
                self.nodes.insert(
                    id,
                    Membrane {
                        id,
                        channel,
                        voltage_mv: self.config.rest_mv,
                        current_na: 0.0,
                        adaptation_na: 0.0,
                        refractory_until_us: 0,
                        last_spike_us: None,
                        spikes: 0,
                        touches: 0,
                        birth_us: self.state_time,
                        last_touch_us: self.state_time,
                    },
                );
                self.channels.insert(channel, id);
                id
            };
            self.current(id, amount)?;
            if !self.silenced_nodes.contains(&id) {
                contacts.push((id, (amplitude * s.intensity).min(1.0)));
            }
        }
        self.grow(&contacts);
        Ok(())
    }
    fn stdp_relax(e: &mut Synapse, now: u128, c: &Config) {
        let dt = (now - e.trace_time_us) as f64 / 1e6;
        e.pre *= (-dt / c.stdp_tau_pre_s).exp();
        e.post *= (-dt / c.stdp_tau_post_s).exp();
        e.trace_time_us = now;
    }
    fn arrival(&mut self, payload: Value) -> Result<()> {
        let messages: Vec<Message> =
            serde_json::from_value(payload["messages"].clone()).map_err(|e| e.to_string())?;
        for (source, target, id, amount) in messages {
            self.current(target, amount)?;
            if let Some(e) = self.edges.get_mut(&(source, target)) {
                if e.id != id
                    || self.silenced_nodes.contains(&target)
                    || !self.config.plasticity
                    || !self.config.stdp_enabled
                {
                    continue;
                }
                Self::stdp_relax(e, self.state_time, &self.config);
                e.weight = (e.weight - self.config.stdp_a_minus * e.post).max(0.0);
                e.pre += 1.0;
                e.touches += 1;
                e.last_touch_us = self.state_time;
            }
        }
        Ok(())
    }
    fn spikes(&mut self) -> Result<Vec<u64>> {
        let now = self.state_time;
        let c = &self.config;
        let firing: Vec<u64> = self
            .active
            .iter()
            .copied()
            .filter(|id| {
                !self.silenced_nodes.contains(id)
                    && self.nodes[id].refractory_until_us <= now
                    && self.nodes[id].voltage_mv >= c.threshold_mv
            })
            .collect();
        for id in &firing {
            let n = self.nodes.get_mut(id).unwrap();
            n.spikes += 1;
            n.last_spike_us = Some(now);
            n.voltage_mv = c.reset_mv;
            n.refractory_until_us = now
                .checked_add(c.refractory_us as u128)
                .ok_or("clock overflow")?;
            if c.inhibition {
                n.adaptation_na += c.adaptation_jump_na;
            }
            if let Some(incoming) = self.incoming.get(id) {
                for source in incoming {
                    let key = (*source, *id);
                    if self.silenced_edges.contains(&key) || !c.plasticity || !c.stdp_enabled {
                        continue;
                    }
                    let e = self.edges.get_mut(&key).unwrap();
                    Self::stdp_relax(e, now, c);
                    e.weight = (e.weight + c.stdp_a_plus * e.pre).min(1.0);
                    e.post += 1.0;
                    e.touches += 1;
                    e.last_touch_us = now;
                }
            }
        }
        let mut messages: Vec<Message> = vec![];
        for id in &firing {
            if let Some(outgoing) = self.outgoing.get(id) {
                for target in outgoing {
                    let key = (*id, *target);
                    if self.silenced_edges.contains(&key) {
                        continue;
                    }
                    let e = &self.edges[&key];
                    let mut amount = e.weight * c.spike_gain_na;
                    if amount <= 0.0 {
                        continue;
                    }
                    if c.stp_enabled {
                        let initial = ShortTermState {
                            time_us: e.birth_us.to_string(),
                            ..Default::default()
                        };
                        let (state, fraction) = self
                            .resources
                            .get(&key)
                            .unwrap_or(&initial)
                            .release(now, &c.short_term())?;
                        self.resources.insert(key, state);
                        amount *= fraction;
                    }
                    if amount > 0.0 {
                        messages.push((*id, *target, e.id, amount));
                        self.transport.sent_na += amount;
                    }
                }
            }
        }
        if !messages.is_empty() {
            let arrival = now
                .checked_add(c.delay_us as u128)
                .ok_or("clock overflow")?;
            self.event(arrival, "spike_arrival", json!({"messages":messages}));
        }
        Ok(firing)
    }
    fn update_life(&mut self) {
        let mut live = BTreeSet::new();
        for id in &self.active {
            if self.present(&self.nodes[id]) {
                live.insert(*id);
            } else {
                let n = self.nodes.get_mut(id).unwrap();
                n.voltage_mv = self.config.rest_mv;
                n.current_na = 0.0;
                n.adaptation_na = 0.0;
            }
        }
        self.active = live;
        if !self.active.is_empty() {
            self.life = "alive".into();
            self.quiet = None;
        } else if self.life == "alive" {
            let quiet = *self.quiet.get_or_insert(self.state_time);
            if self.state_time - quiet >= self.config.quiescence_death_us as u128 {
                self.life = "dead".into();
            }
        }
    }
    pub fn advance(&mut self, target: u128, record: bool) -> Result<Vec<Value>> {
        self.advance_mode(target, record, false, false)
    }
    pub fn advance_inputs(&mut self, target: u128) -> Result<Vec<Value>> {
        self.advance_mode(target, true, true, false)
    }
    pub fn advance_inputs_and_spikes(&mut self, target: u128) -> Result<Vec<Value>> {
        self.advance_mode(target, true, true, true)
    }
    fn advance_mode(
        &mut self,
        target: u128,
        record: bool,
        inputs_only: bool,
        record_spikes: bool,
    ) -> Result<Vec<Value>> {
        if target < self.time {
            return Err("time cannot go backwards".into());
        }
        let mut rows = vec![];
        if self.life == "dead" {
            return Ok(rows);
        }
        loop {
            let mut next = self.queue.peek().map(|e| e.time);
            if !self.active.is_empty() {
                next = Some(next.map_or(self.next_step, |n| n.min(self.next_step)));
            }
            if let Some(quiet) = self.quiet {
                let deadline = quiet
                    .checked_add(self.config.quiescence_death_us as u128)
                    .ok_or("clock overflow")?;
                next = Some(next.map_or(deadline, |n| n.min(deadline)));
            }
            let Some(now) = next.filter(|n| *n <= target) else {
                break;
            };
            self.relax(now)?;
            self.time = now;
            while self.queue.peek().is_some_and(|e| e.time == now) {
                let e = self.queue.pop().unwrap();
                if e.kind == "stimulus" {
                    self.input(e.payload.clone())?;
                } else {
                    self.arrival(e.payload.clone())?;
                }
                self.sequence += 1;
                if record && (!inputs_only || e.kind == "stimulus") {
                    rows.push(json!({"kind":e.kind,"event_id":e.id,"time_us":now.to_string(),"sequence":self.sequence,"payload":e.payload}));
                }
            }
            if now % self.config.step_us as u128 == 0 {
                let firing = self.spikes()?;
                self.sequence += 1;
                if record && (!inputs_only || record_spikes) && !firing.is_empty() {
                    rows.push(json!({"kind":"spikes","time_us":now.to_string(),"sequence":self.sequence,"payload":{"nodes":firing}}));
                }
            }
            self.next_step = self.grid_after(now)?;
            self.update_life();
            if self.life == "dead" {
                return Ok(rows);
            }
        }
        self.time = target;
        Ok(rows)
    }
    fn node_rows(&self, when: u128) -> Vec<Node> {
        self.nodes
            .values()
            .map(|n| {
                let n = self.project(n, when);
                Node {
                    id: n.id,
                    channel: n.channel,
                    activation: ((n.voltage_mv - self.config.rest_mv)
                        / (self.config.threshold_mv - self.config.rest_mv))
                        .clamp(0.0, 1.0),
                    inhibition: n.adaptation_na,
                    trace: 0.0,
                    support: 0.0,
                    stability: 0.0,
                    direct: 0.0,
                    associative: 0.0,
                    touches: n.touches,
                    last_touch_us: n.last_touch_us.to_string(),
                    birth_us: n.birth_us.to_string(),
                    local_plasticity: 1.0,
                    pending_inhibition: 0.0,
                    generated_inhibition: 0.0,
                }
            })
            .collect()
    }
    pub fn observation_nodes(&self) -> Vec<Node> {
        self.node_rows(self.time)
    }
    pub fn physical_nodes(&self) -> Vec<Membrane> {
        self.nodes
            .values()
            .map(|n| self.project(n, self.time))
            .collect()
    }
    pub fn activations(&self) -> Vec<(u64, f64)> {
        self.observation_nodes()
            .iter()
            .map(|n| (n.id, n.activation))
            .collect()
    }
    pub fn induced_edges(&self, ids: Vec<u64>) -> Vec<Edge> {
        let selected: BTreeSet<u64> = ids.into_iter().collect();
        self.edges
            .values()
            .filter(|e| selected.contains(&e.source) && selected.contains(&e.target))
            .map(|e| Edge {
                source: e.source,
                target: e.target,
                weight: e.weight,
                stability: 0.0,
                eligibility: 0.0,
                touches: e.touches,
                birth_us: e.birth_us.to_string(),
                last_touch_us: e.last_touch_us.to_string(),
            })
            .collect()
    }
    pub fn graph(&self, limit: Option<usize>) -> Value {
        let mut nodes = self.observation_nodes();
        if let Some(n) = limit {
            nodes.sort_by(|a, b| b.activation.total_cmp(&a.activation).then(a.id.cmp(&b.id)));
            nodes.truncate(n);
        }
        let ids: Vec<_> = nodes.iter().map(|n| n.id).collect();
        let selected: BTreeSet<_> = ids.iter().copied().collect();
        let physical: Vec<_> = self
            .physical_nodes()
            .into_iter()
            .filter(|n| selected.contains(&n.id))
            .collect();
        json!({"nodes":nodes,"edges":self.induced_edges(ids),"time_us":self.time.to_string(),"sequence":self.sequence,
            "life":self.life,"kernel_id":KERNEL_ID,"observation_quantity":"normalized-depolarization","physical_nodes":physical})
    }
    pub fn metrics(&self) -> Value {
        json!({"nodes":self.nodes.len(),"edges":self.edges.len(),"life":self.life,"time_us":self.time.to_string(),
            "sequence":self.sequence,"activation":self.activations().iter().map(|n|n.1).sum::<f64>(),"kernel_id":KERNEL_ID,
            "state_schema":STATE_SCHEMA,"observation_quantity":"normalized-depolarization",
            "spikes":self.nodes.values().map(|n|n.spikes).sum::<u64>(),
            "active_membranes":self.physical_nodes().iter().filter(|n|self.present(n)).count(),
            "transport":self.transport,"capacity_rejections":self.rejected})
    }
    fn remove_edge(&mut self, key: Key) {
        if self.edges.remove(&key).is_some() {
            self.resources.remove(&key);
            self.silenced_edges.remove(&key);
            self.outgoing.get_mut(&key.0).unwrap().remove(&key.1);
            self.incoming.get_mut(&key.1).unwrap().remove(&key.0);
        }
    }
    pub fn intervene(&mut self, nodes: Vec<u64>, edges: Vec<Key>, lesion: bool) -> Result<()> {
        self.intervene_action(
            nodes,
            edges,
            if lesion { "delete_nodes" } else { "silence" },
        )
    }
    pub fn intervene_action(
        &mut self,
        nodes: Vec<u64>,
        edges: Vec<Key>,
        action: &str,
    ) -> Result<()> {
        if self.life == "dead" {
            return Err("dead consciousness cannot be changed".into());
        }
        let nodes: BTreeSet<_> = nodes.into_iter().collect();
        let mut links: BTreeSet<_> = edges.into_iter().collect();
        if nodes.iter().any(|n| !self.nodes.contains_key(n))
            || links.iter().any(|k| !self.edges.contains_key(k))
        {
            return Err("damage requires existing identities".into());
        }
        if !matches!(
            action,
            "silence" | "unsilence" | "delete_nodes" | "disconnect_edges"
        ) || action == "disconnect_edges" && !nodes.is_empty()
        {
            return Err("invalid structural operation".into());
        }
        self.relax(self.time)?;
        self.next_step = self.grid_after(self.time)?;
        match action {
            "silence" => {
                self.silenced_nodes.extend(&nodes);
                self.silenced_edges.extend(&links);
                for id in nodes {
                    let n = self.nodes.get_mut(&id).unwrap();
                    n.voltage_mv = self.config.rest_mv;
                    n.current_na = 0.0;
                    n.adaptation_na = 0.0;
                    self.active.remove(&id);
                }
            }
            "unsilence" => {
                for id in nodes {
                    self.silenced_nodes.remove(&id);
                }
                for key in links {
                    self.silenced_edges.remove(&key);
                }
            }
            _ => {
                links.extend(
                    self.edges
                        .keys()
                        .filter(|k| nodes.contains(&k.0) || nodes.contains(&k.1))
                        .copied(),
                );
                for key in links {
                    self.remove_edge(key);
                }
                for id in nodes {
                    let n = self.nodes.remove(&id).unwrap();
                    self.channels.remove(&n.channel);
                    self.active.remove(&id);
                    self.silenced_nodes.remove(&id);
                }
            }
        }
        self.sequence += 1;
        self.update_life();
        Ok(())
    }
    pub fn reconfigure(&mut self, value: Value) -> Result<()> {
        let c = Config::parse(value)?;
        if c == self.config {
            return Ok(());
        }
        if self.life == "dead" {
            return Err("cannot reconfigure a dead consciousness".into());
        }
        if c.step_us != self.config.step_us
            || c.seed != self.config.seed
            || c.rest_mv != self.config.rest_mv
            || c.reset_mv != self.config.reset_mv
            || c.threshold_mv != self.config.threshold_mv
        {
            return Err("immutable LIF parameter".into());
        }
        self.relax(self.time)?;
        self.next_step = self.grid_after(self.time)?;
        for e in self.edges.values_mut() {
            Self::stdp_relax(e, self.time, &self.config);
        }
        for s in self.resources.values_mut() {
            *s = s.recovered(self.time, &self.config.short_term())?;
        }
        self.config = c;
        self.sequence += 1;
        self.update_life();
        Ok(())
    }
    pub fn capture(&self) -> Result<Value> {
        let definition = self.definition();
        let mut queue: Vec<_> = self.queue.iter().cloned().collect();
        queue.sort_by_key(|e| (e.time, e.id));
        let snapshot = Snapshot {
            schema: STATE_SCHEMA.into(),
            dynamics: KERNEL_ID.into(),
            config: self.config.value(),
            definition_hash: canonical_hash(&serde_json::to_vec(&definition).unwrap())?,
            definition,
            time_us: self.time,
            state_time_us: self.state_time,
            next_step_us: self.next_step,
            sequence: self.sequence,
            next_event: self.next_event,
            next_node: self.next_node,
            next_synapse: self.next_synapse,
            life: self.life.clone(),
            sources_open: self.sources_open,
            quiet_since_us: self.quiet,
            nodes: self.node_rows(self.state_time),
            edges: self.induced_edges(self.nodes.keys().copied().collect()),
            membranes: self.nodes.values().cloned().collect(),
            synapses: self.edges.values().cloned().collect(),
            active: self.active.iter().copied().collect(),
            silenced_nodes: self.silenced_nodes.iter().copied().collect(),
            silenced_edges: self.silenced_edges.iter().copied().collect(),
            short_term: self
                .resources
                .iter()
                .map(|((a, b), s)| Resource {
                    source: *a,
                    target: *b,
                    state: s.clone(),
                })
                .collect(),
            queue: queue
                .into_iter()
                .map(|e| crate::SavedEvent {
                    time_us: e.time.to_string(),
                    id: e.id,
                    kind: e.kind,
                    payload: e.payload,
                })
                .collect(),
            transport: self.transport.clone(),
            capacity_rejections: self.rejected.clone(),
        };
        serde_json::to_value(snapshot).map_err(|e| e.to_string())
    }
    pub fn restore(value: Value) -> Result<Self> {
        let original = canonical_hash(&serde_json::to_vec(&value).unwrap())?;
        let s: Snapshot = serde_json::from_value(value).map_err(|e| e.to_string())?;
        if s.schema != STATE_SCHEMA || s.dynamics != KERNEL_ID {
            return Err("LIF state identity mismatch".into());
        }
        let mut e = Self::new(s.config)?;
        if s.definition != e.definition()
            || s.definition_hash != canonical_hash(&serde_json::to_vec(&e.definition()).unwrap())?
        {
            return Err("LIF definition mismatch".into());
        }
        e.time = s.time_us;
        e.state_time = s.state_time_us;
        e.next_step = s.next_step_us;
        if e.state_time > e.time || e.next_step != e.grid_after(e.state_time)? {
            return Err("inconsistent clocks".into());
        }
        for n in [s.sequence, s.next_event, s.next_node, s.next_synapse] {
            if n >= 1u64 << 63 {
                return Err("invalid identity counter".into());
            }
        }
        e.sequence = s.sequence;
        e.next_event = s.next_event;
        e.next_node = s.next_node;
        e.next_synapse = s.next_synapse;
        e.life = s.life;
        e.sources_open = s.sources_open;
        e.quiet = s.quiet_since_us;
        if !matches!(e.life.as_str(), "waiting" | "alive" | "dead")
            || e.quiet.is_some_and(|t| t > e.state_time)
        {
            return Err("invalid lifecycle state".into());
        }
        for n in s.membranes {
            if n.id == 0
                || n.id >= e.next_node
                || e.nodes.contains_key(&n.id)
                || e.channels.contains_key(&n.channel)
            {
                return Err("invalid membrane identity".into());
            }
            if n.birth_us > n.last_touch_us
                || n.last_touch_us > e.state_time
                || n.last_spike_us.is_some_and(|t| t > e.state_time)
            {
                return Err("invalid membrane history".into());
            }
            if n.last_spike_us.is_none() != (n.spikes == 0)
                || n.last_spike_us.is_none() && n.refractory_until_us != 0
                || n.last_spike_us.is_some_and(|t| n.refractory_until_us < t)
            {
                return Err("inconsistent spike history".into());
            }
            finite(n.voltage_mv, -f64::MAX, f64::MAX)?;
            finite(n.current_na, 0.0, f64::MAX)?;
            finite(n.adaptation_na, 0.0, f64::MAX)?;
            e.channels.insert(n.channel, n.id);
            e.nodes.insert(n.id, n);
        }
        let mut ids = BTreeSet::new();
        for syn in s.synapses {
            let key = (syn.source, syn.target);
            if syn.source == syn.target
                || !e.nodes.contains_key(&syn.source)
                || !e.nodes.contains_key(&syn.target)
                || e.edges.contains_key(&key)
                || syn.id == 0
                || syn.id >= e.next_synapse
                || !ids.insert(syn.id)
            {
                return Err("invalid synapse identity".into());
            }
            finite(syn.weight, 0.0, 1.0)?;
            finite(syn.pre, 0.0, f64::MAX)?;
            finite(syn.post, 0.0, f64::MAX)?;
            if syn.birth_us > syn.last_touch_us
                || syn.last_touch_us > e.state_time
                || syn.birth_us > syn.trace_time_us
                || syn.trace_time_us > e.state_time
            {
                return Err("invalid synapse history".into());
            }
            e.outgoing.entry(syn.source).or_default().insert(syn.target);
            e.incoming.entry(syn.target).or_default().insert(syn.source);
            e.edges.insert(key, syn);
        }
        e.active = s.active.into_iter().collect();
        e.silenced_nodes = s.silenced_nodes.into_iter().collect();
        e.silenced_edges = s.silenced_edges.into_iter().collect();
        if e.active.iter().any(|n| !e.nodes.contains_key(n))
            || e.silenced_nodes.iter().any(|n| !e.nodes.contains_key(n))
            || e.silenced_edges.iter().any(|k| !e.edges.contains_key(k))
        {
            return Err("invalid active or silenced identity".into());
        }
        let present: BTreeSet<_> = e
            .nodes
            .iter()
            .filter(|(_, n)| e.present(n))
            .map(|(id, _)| *id)
            .collect();
        if e.active != present || !e.active.is_disjoint(&e.silenced_nodes) {
            return Err("active index differs from physical activity".into());
        }
        if (e.life == "waiting" || e.life == "dead") && !e.active.is_empty()
            || !e.active.is_empty() && e.quiet.is_some()
        {
            return Err("lifecycle disagrees with activity".into());
        }
        if e.life == "waiting" && (e.nodes.values().any(|n| n.spikes > 0) || e.quiet.is_some()) {
            return Err("invalid waiting history".into());
        }
        if e.life != "waiting" && e.active.is_empty() {
            let quiet = e.quiet.ok_or("inactive state requires quiet timer")?;
            if (e.life == "dead") != (e.state_time - quiet >= e.config.quiescence_death_us as u128)
            {
                return Err("death deadline mismatch".into());
            }
        }
        for r in s.short_term {
            let key = (r.source, r.target);
            let syn = e.edges.get(&key).ok_or("invalid short-term edge")?;
            r.state.validate()?;
            let now = parse_time(&r.state.time_us)?;
            if e.resources.contains_key(&key) || now < syn.birth_us || now > e.state_time {
                return Err("invalid short-term history".into());
            }
            e.resources.insert(key, r.state);
        }
        ids.clear();
        for row in s.queue {
            let time = parse_time(&row.time_us)?;
            if time < e.time || row.id >= e.next_event || !ids.insert(row.id) {
                return Err("invalid pending event".into());
            }
            match row.kind.as_str() {
                "stimulus" => {
                    let stimulus: Stimulus =
                        serde_json::from_value(row.payload.clone()).map_err(|e| e.to_string())?;
                    stimulus.validate()?;
                    if parse_time(&stimulus.time_us)? != time {
                        return Err("stimulus clock mismatch".into());
                    }
                }
                "spike_arrival" => {
                    if row
                        .payload
                        .as_object()
                        .is_none_or(|m| m.len() != 1 || !m.contains_key("messages"))
                    {
                        return Err("invalid spike arrival".into());
                    }
                    let messages: Vec<Message> =
                        serde_json::from_value(row.payload["messages"].clone())
                            .map_err(|e| e.to_string())?;
                    for (a, b, id, amount) in messages {
                        if a == 0
                            || b == 0
                            || a >= e.next_node
                            || b >= e.next_node
                            || id == 0
                            || id >= e.next_synapse
                        {
                            return Err("invalid in-flight identity".into());
                        }
                        finite(amount, 0.0, f64::MAX)?;
                    }
                }
                _ => return Err("unknown LIF event".into()),
            }
            e.queue.push(Event {
                time,
                id: row.id,
                kind: row.kind,
                payload: row.payload,
            });
        }
        for n in [
            s.transport.sent_na,
            s.transport.received_na,
            s.transport.unavailable_na,
        ] {
            finite(n, 0.0, f64::MAX)?;
        }
        e.transport = s.transport;
        e.rejected = s.capacity_rejections;
        if canonical_hash(&serde_json::to_vec(&e.capture()?).unwrap())? != original {
            return Err("inconsistent projections or state fields".into());
        }
        Ok(e)
    }
}
