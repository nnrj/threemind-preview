//! Continuous candidate, separate scientific/state identity from causal/9.
//! Internal Engine reuse never exposes a legacy capture as a candidate artifact.
use super::*;
use crate::mechanisms::{
    local_attention, FastTrace, FastTraceConfig, ShortTermConfig, ShortTermState,
};
use crate::restoration::{response, soft};

pub const KERNEL_ID: &str = "threemind.continuous/1";
pub const STATE_SCHEMA: &str = "threemind.continuous-state/1";
pub const MEMORY_ID: &str = "threemind.continuous-memory/1";
pub const MEMORY_STATE: &str = "threemind.continuous-memory-state/1";

#[derive(Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
struct MemoryControls {
    depletion_enabled: bool,
    edge_consolidation_enabled: bool,
}
impl Default for MemoryControls {
    fn default() -> Self {
        Self {
            depletion_enabled: true,
            edge_consolidation_enabled: true,
        }
    }
}
fn take_memory(value: &mut Value) -> Result<MemoryControls> {
    let object = value
        .as_object_mut()
        .ok_or("memory config must be an object")?;
    let mut controls = serde_json::Map::new();
    for key in ["depletion_enabled", "edge_consolidation_enabled"] {
        if let Some(value) = object.remove(key) {
            controls.insert(key.into(), value);
        }
    }
    serde_json::from_value(Value::Object(controls)).map_err(|e| e.to_string())
}
fn memory_definition(base: &Config, p: &Parameters, m: MemoryControls) -> Value {
    let mut value = definition(base, p);
    value["kernel_id"] = json!(MEMORY_ID);
    value["state_schema"] = json!(MEMORY_STATE);
    value["hypothesis_id"] = json!("threemind.hypotheses/continuous-memory1");
    value["config"].as_object_mut().unwrap().extend(
        serde_json::to_value(m)
            .unwrap()
            .as_object()
            .unwrap()
            .clone(),
    );
    value["operators"].as_array_mut().unwrap().extend([
        json!({"id":"threemind.resource-clamp-control/1", "phase":"before-emission"}),
        json!({"id":"threemind.edge-consolidation-control/1", "phase":"positive-edge-updates"}),
    ]);
    value
}

#[derive(Clone, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Parameters {
    pub stp_enabled: bool,
    pub stp_utilization: f64,
    pub stp_recovery_tau_s: f64,
    pub stp_active_tau_s: f64,
    pub stp_facilitation_tau_s: f64,
    pub fast_enabled: bool,
    pub fast_tau_s: f64,
    pub fast_learning_rate: f64,
    pub fast_gain: f64,
    pub context_enabled: bool,
    pub context_tau_s: f64,
    pub context_temperature: f64,
    pub context_mix: f64,
}
impl Default for Parameters {
    fn default() -> Self {
        Self {
            stp_enabled: true,
            stp_utilization: 0.5,
            stp_recovery_tau_s: 0.8,
            stp_active_tau_s: 0.003,
            stp_facilitation_tau_s: 0.0,
            fast_enabled: true,
            fast_tau_s: 2.0,
            fast_learning_rate: 0.1,
            fast_gain: 0.1,
            context_enabled: true,
            context_tau_s: 1.0,
            context_temperature: 1.0,
            context_mix: 1.0,
        }
    }
}
impl Parameters {
    pub fn enabled(&self) -> bool {
        self.stp_enabled || self.fast_enabled || self.context_enabled
    }
    pub fn short_term(&self) -> ShortTermConfig {
        ShortTermConfig {
            utilization: self.stp_utilization,
            recovery_tau_s: self.stp_recovery_tau_s,
            active_tau_s: self.stp_active_tau_s,
            facilitation_tau_s: self.stp_facilitation_tau_s,
        }
    }
    pub fn fast_trace(&self) -> FastTraceConfig {
        FastTraceConfig {
            tau_s: self.fast_tau_s,
            learning_rate: self.fast_learning_rate,
            gain: self.fast_gain,
        }
    }
    pub fn validate(&self) -> Result<()> {
        self.short_term().validate()?;
        self.fast_trace().validate()?;
        if !self.context_tau_s.is_finite() || !(1e-6..=1e9).contains(&self.context_tau_s) {
            return Err("invalid context_tau_s".into());
        }
        local_attention(&[0.0], &[], &[], self.context_temperature, self.context_mix)?;
        Ok(())
    }
}

pub fn parse_config(mut value: Value) -> Result<(Config, Parameters)> {
    let config = value
        .as_object_mut()
        .ok_or("candidate configuration must be an object")?;
    let defaults = serde_json::to_value(Parameters::default()).unwrap();
    let mut extra = serde_json::Map::new();
    for key in defaults.as_object().unwrap().keys() {
        if let Some(value) = config.remove(key) {
            extra.insert(key.clone(), value);
        }
    }
    let base: Config = serde_json::from_value(value).map_err(|e| e.to_string())?;
    let parameters: Parameters =
        serde_json::from_value(Value::Object(extra)).map_err(|e| e.to_string())?;
    base.validate()?;
    parameters.validate()?;
    if base.propagation_rate > 1e9
        || base.propagation_rate * (base.propagation_interval_us as f64 / 1e6) > 1e12
    {
        return Err("candidate emission gain exceeds numerical range".into());
    }
    Ok((base, parameters))
}

fn config_value(base: &Config, parameters: &Parameters) -> Value {
    let mut value = serde_json::to_value(base).unwrap();
    value.as_object_mut().unwrap().extend(
        serde_json::to_value(parameters)
            .unwrap()
            .as_object()
            .unwrap()
            .clone(),
    );
    value
}

pub fn definition(base: &Config, parameters: &Parameters) -> Value {
    json!({"schema":"threemind.kernel-definition/1", "kernel_id":KERNEL_ID, "state_schema":STATE_SCHEMA,
        "hypothesis_id":"threemind.hypotheses/continuous1", "config":config_value(base, parameters),
        "operators":[
            {"id":"threemind.causal9-transition/1", "phase":"hybrid-event-clock"},
            {"id":"threemind.leaky-fast-trace/1", "phase":"efficacy-and-emission"},
            {"id":"threemind.tm-synapse/1", "phase":"before-emission"},
            {"id":"threemind.local-context-attention/1", "phase":"after-arrival"}]})
}

type Message = (u64, u64, f64, Vec<f64>);

pub(super) struct Operators {
    pub parameters: Parameters,
    pub(super) short_term: BTreeMap<(u64, u64), ShortTermState>,
    pub(super) fast: BTreeMap<(u64, u64), FastTrace>,
    messages: Vec<Message>,
    pub(super) depletion_enabled: bool,
}
impl Operators {
    fn new(parameters: Parameters) -> Self {
        Self {
            parameters,
            short_term: BTreeMap::new(),
            fast: BTreeMap::new(),
            messages: vec![],
            depletion_enabled: true,
        }
    }
    fn features(&self, node: &Node, now: u128) -> Vec<f64> {
        vec![
            node.activation,
            node.trace,
            node.inhibition / (1.0 + node.inhibition),
            (-((now - parse_time(&node.last_touch_us).unwrap()) as f64)
                / 1e6
                / self.parameters.context_tau_s)
                .exp(),
        ]
    }
    fn effective_weight(&self, edge: &Edge, now: u128) -> Result<f64> {
        if !self.parameters.fast_enabled {
            return Ok(edge.weight);
        }
        let initial = FastTrace {
            value: 0.0,
            time_us: edge.birth_us.clone(),
        };
        self.fast
            .get(&(edge.source, edge.target))
            .unwrap_or(&initial)
            .efficacy(edge.weight, now, &self.parameters.fast_trace())
    }
    fn release_fraction(&mut self, edge: &Edge, now: u128) -> Result<f64> {
        if !self.parameters.stp_enabled {
            return Ok(1.0);
        }
        let initial = ShortTermState {
            time_us: edge.birth_us.clone(),
            ..Default::default()
        };
        let key = (edge.source, edge.target);
        if !self.depletion_enabled {
            let mut state = self
                .short_term
                .get(&key)
                .unwrap_or(&initial)
                .recovered(now, &self.parameters.short_term())?;
            state.available = 1.0;
            state.active = 0.0;
            let (mut state, fraction) = state.release(now, &self.parameters.short_term())?;
            state.available = 1.0;
            state.active = 0.0;
            self.short_term.insert(key, state);
            return Ok(fraction);
        }
        let (state, fraction) = self
            .short_term
            .get(&key)
            .unwrap_or(&initial)
            .release(now, &self.parameters.short_term())?;
        self.short_term.insert(key, state);
        Ok(fraction)
    }
    fn record_emission(
        &mut self,
        node: &Node,
        edge: &Edge,
        amount: f64,
        now: u128,
        plasticity: bool,
    ) -> Result<()> {
        if self.parameters.fast_enabled && plasticity {
            let key = (edge.source, edge.target);
            let initial = FastTrace {
                value: 0.0,
                time_us: edge.birth_us.clone(),
            };
            let state = self.fast.get(&key).unwrap_or(&initial).transmit(
                amount,
                now,
                &self.parameters.fast_trace(),
            )?;
            self.fast.insert(key, state);
        }
        if self.parameters.context_enabled {
            self.messages
                .push((edge.source, edge.target, amount, self.features(node, now)));
        }
        Ok(())
    }
    pub(super) fn receive(&mut self, engine: &mut Engine, payload: &mut Value) -> Result<()> {
        let values: Vec<(u64, f64)> =
            serde_json::from_value(payload["values"].clone()).map_err(|e| e.to_string())?;
        let use_context = self.parameters.context_enabled
            && self.parameters.context_mix > 0.0
            && payload.get("messages").is_some();
        let mut messages: BTreeMap<u64, Vec<Message>> = BTreeMap::new();
        if use_context {
            for message in serde_json::from_value::<Vec<Message>>(payload["messages"].clone())
                .map_err(|e| e.to_string())?
            {
                messages.entry(message.1).or_default().push(message);
            }
        }
        let (mut touched, mut contacts, mut reception) = (vec![], vec![], vec![]);
        for (target, raw) in values {
            let mut value = raw;
            if use_context {
                if engine.silenced_nodes.contains(&target)
                    || !engine.node_index.contains_key(&target)
                {
                    reception.push(
                        json!({"target":target,"raw":raw,"response":0.0,"status":"unavailable"}),
                    );
                    continue;
                }
                let batch = messages.get(&target).ok_or("missing contextual messages")?;
                let query = self.features(&engine.nodes[engine.node_index[&target]], engine.time);
                let keys: Vec<_> = batch.iter().map(|m| m.3.clone()).collect();
                let amounts: Vec<_> = batch.iter().map(|m| m.2).collect();
                let (response, coefficients) = local_attention(
                    &query,
                    &keys,
                    &amounts,
                    self.parameters.context_temperature,
                    self.parameters.context_mix,
                )?;
                value = response;
                let sources: Vec<_> = batch.iter().map(|m| m.0).collect();
                reception.push(json!({"target":target,"raw":raw,"response":value,"coefficients":coefficients,"sources":sources}));
            }
            let amount = engine.touch(target, value, false);
            if use_context {
                *engine.transport.get_mut("received").unwrap() += raw - value;
            }
            if amount > 0.0 {
                touched.push((target, 0.0));
                contacts.push((target, amount));
            }
        }
        if engine.config.edge_birth_policy == "temporal-association" {
            engine.associate(touched);
        }
        engine.update_touched(&contacts);
        if use_context {
            payload["reception"] = json!(reception);
        }
        Ok(())
    }
}

impl Engine {
    pub(super) fn prune_operator_state(&mut self) {
        if self.retention.is_some() {
            return;
        }
        if let Some(novelty) = self.novelty.as_mut() {
            novelty.retain(&self.edge_index);
        }
        if let Some(operators) = &mut self.continuous {
            operators
                .short_term
                .retain(|key, _| self.edge_index.contains_key(key));
            operators
                .fast
                .retain(|key, _| self.edge_index.contains_key(key));
        }
    }
    pub(super) fn emit_continuous(&mut self, operators: &mut Operators) -> Result<()> {
        let c = self.config.clone();
        let dt = c.propagation_interval_us as f64 / 1e6;
        let gain = c.propagation_rate * dt;
        let diffusion = (c.inhibition_diffusion_rate * dt).min(1.0);
        for n in &mut self.nodes {
            if c.inhibition {
                n.inhibition = soft(&c, n.inhibition + n.pending_inhibition);
                n.pending_inhibition = 0.0;
            } else {
                n.inhibition = 0.0;
                n.pending_inhibition = 0.0;
            }
        }
        let (mut signals, mut inhibitors): (BTreeMap<u64, f64>, BTreeMap<u64, f64>) =
            (BTreeMap::new(), BTreeMap::new());
        let mut traversed = BTreeSet::new();
        let mut emissions = 0;
        let mut order: Vec<_> = self.nodes.iter().map(|n| n.id).collect();
        order.sort();
        if c.propagation_limit.is_some() {
            order.sort_by(|a, b| {
                self.nodes[self.node_index[b]]
                    .activation
                    .total_cmp(&self.nodes[self.node_index[a]].activation)
                    .then_with(|| a.cmp(b))
            });
        }
        for id in order {
            if self.silenced_nodes.contains(&id) {
                continue;
            }
            let index = self.node_index[&id];
            let n = self.nodes[index].clone();
            self.retention_node_output(&n);
            let mut targets: Vec<_> = self
                .outgoing
                .get(&id)
                .map(|s| s.iter().copied().collect())
                .unwrap_or_default();
            if c.propagation_limit.is_some() {
                targets.sort_by(|a, b| {
                    self.edges[self.edge_index[&(id, *b)]]
                        .weight
                        .total_cmp(&self.edges[self.edge_index[&(id, *a)]].weight)
                        .then_with(|| a.cmp(b))
                });
            }
            if n.activation > 0.0 && n.activation >= c.propagation_activation_min {
                for target in targets {
                    let key = (id, target);
                    if self.silenced_edges.contains(&key) {
                        continue;
                    }
                    self.retention_prepare_edge(key);
                    let i = self.edge_index[&key];
                    let mut amount = n.activation
                        * response(&c, &n)
                        * self.fatigue_response(id)
                        * operators.effective_weight(&self.edges[i], self.time)?
                        * gain;
                    if c.spatial_embedding && c.neighborhood_enabled {
                        amount *= (1.0
                            - spatial::distance(&self.spatial_points, id, target)
                                / c.spatial_radius)
                            .max(0.0);
                    }
                    if amount <= 0.0 || amount < c.activation_floor {
                        continue;
                    }
                    if c.propagation_limit.is_some_and(|limit| emissions >= limit) {
                        self.resources.increment(Counter::Propagation, 1);
                        continue;
                    }
                    amount *= operators.release_fraction(&self.edges[i], self.time)?;
                    if c.energy_simulation_enabled {
                        amount = self.energy.afford(
                            amount,
                            c.energy_associative_cost,
                            Cost::Associative,
                        );
                    }
                    *self.transport.get_mut("sent").unwrap() += amount;
                    if amount <= 0.0 || amount < c.activation_floor {
                        *self.transport.get_mut("discarded").unwrap() += amount;
                        continue;
                    }
                    emissions += 1;
                    *signals.entry(target).or_default() += amount;
                    operators.record_emission(
                        &n,
                        &self.edges[i],
                        amount,
                        self.time,
                        c.plasticity,
                    )?;
                    self.retention_emitted(key, amount);
                    traversed.insert(key);
                    if c.plasticity {
                        if let Some(limit) = c.edge_adaptation_limit {
                            if self.resources.available_adaptations(
                                self.time,
                                c.propagation_interval_us,
                                limit,
                            ) == 0
                            {
                                self.resources.increment(Counter::Adaptation, 1);
                                continue;
                            }
                            self.resources
                                .use_adaptation(self.time, c.propagation_interval_us);
                        }
                        let e = &mut self.edges[i];
                        e.eligibility = (0.7 * e.eligibility + amount).min(1.0);
                        if self.edge_consolidation_enabled {
                            e.weight = (e.weight + c.associative_gain * amount).min(1.0);
                            e.stability = (e.stability + c.stability_gain * amount).min(1.0);
                        }
                        e.touches += 1;
                        e.last_touch_us = self.time.to_string();
                        self.retention_edge_changed(key);
                    }
                }
            }
            if c.inhibition && n.generated_inhibition > 0.0 {
                self.nodes[index].inhibition =
                    soft(&c, self.nodes[index].inhibition + n.generated_inhibition);
            }
            self.nodes[index].generated_inhibition = 0.0;
            let field = self.nodes[index].inhibition;
            if c.inhibition && field >= c.inhibition_propagation_min {
                let neighbours = self.incident.get(&id).cloned().unwrap_or_default();
                let mut conductances = vec![];
                for target in neighbours {
                    let mut weight: f64 = 0.0;
                    for key in [(id, target), (target, id)] {
                        if !self.silenced_edges.contains(&key) {
                            self.retention_prepare_edge(key);
                            if let Some(&i) = self.edge_index.get(&key) {
                                weight = weight.max(self.edges[i].weight);
                            }
                        }
                    }
                    if weight > 0.0 {
                        conductances.push((target, weight));
                    }
                }
                let total: f64 = conductances.iter().map(|(_, w)| w).sum();
                let mut transfer = field * diffusion;
                if total > 0.0 && transfer >= c.inhibition_propagation_min {
                    if c.energy_simulation_enabled {
                        transfer = self.energy.afford(
                            transfer,
                            c.energy_inhibition_cost,
                            Cost::Inhibition,
                        );
                    }
                    if transfer >= c.inhibition_propagation_min {
                        self.nodes[index].inhibition -= transfer;
                        for (target, w) in conductances {
                            *inhibitors.entry(target).or_default() += transfer * w / total;
                        }
                    }
                }
            }
        }
        for (kind, values) in [("signal", signals), ("inhibition", inhibitors)] {
            if !values.is_empty() {
                let data: Vec<_> = values
                    .into_iter()
                    .map(|(id, v)| (id, if kind == "inhibition" { soft(&c, v) } else { v }))
                    .collect();
                let mut payload = json!({"values":data});
                if kind == "signal" && !operators.messages.is_empty() {
                    payload["messages"] = json!(std::mem::take(&mut operators.messages));
                }
                self.event(self.time + c.delay_us as u128, kind, payload);
            }
        }
        if c.plasticity {
            let retention = if c.eligibility_decay_enabled {
                (-dt / c.eligibility_tau).exp()
            } else {
                1.0
            };
            for e in &mut self.edges {
                e.eligibility *= retention;
                if c.stability_decay_enabled {
                    e.stability =
                        (e.stability - dt / c.stability_tau * (1.0 - e.eligibility)).max(0.0);
                }
                if !traversed.contains(&(e.source, e.target))
                    && self.retention.as_ref().is_none_or(|op| !op.p.adaptive())
                {
                    e.weight *= (1.0
                        - 0.1 * c.forgetting_rate * (1.0 - (0.08 + 0.92 * e.stability)))
                        .max(0.0)
                        .powf(dt / 0.1);
                    if e.weight < c.prune_weight {
                        if let Some(op) = self.retention.as_mut() {
                            op.legacy_expired((e.source, e.target), self.time);
                        }
                    }
                }
            }
        }
        self.traversed = traversed;
        for n in &mut self.nodes {
            n.direct = 0.0;
            n.associative = 0.0;
        }
        Ok(())
    }
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct StoredOperator<T> {
    source: u64,
    target: u64,
    state: T,
}

pub struct ContinuousEngine {
    inner: Engine,
    memory: Option<MemoryControls>,
}

impl ContinuousEngine {
    pub fn new_retention(value: Value) -> Result<Self> {
        Self::new_retention_version(value, retention::Version::Original)
    }
    pub fn new_retention31(value: Value) -> Result<Self> {
        Self::new_retention_version(value, retention::Version::LocalBirthExpiry)
    }
    fn new_retention_version(mut value: Value, version: retention::Version) -> Result<Self> {
        let p = retention::take(&mut value)?;
        let mut engine = Self::new_novelty(value)?;
        p.validate(&engine.inner.config)?;
        engine.inner.retention = Some(retention::Operator::new(p, version));
        Ok(engine)
    }
    pub fn restore_retention(value: Value) -> Result<Self> {
        Self::restore_retention_version(value, retention::Version::Original)
    }
    pub fn restore_retention31(value: Value) -> Result<Self> {
        Self::restore_retention_version(value, retention::Version::LocalBirthExpiry)
    }
    fn restore_retention_version(mut value: Value, version: retention::Version) -> Result<Self> {
        let (kernel, schema) = version.identity();
        if value["dynamics"] != kernel || value["schema"] != schema {
            return Err("retention state identity mismatch".into());
        }
        if value["config"]["revival_enabled"] == true
            && value["config"]["dormant_traces_enabled"] != true
        {
            return Err("revival requires dormant traces in saved state".into());
        }
        let p = retention::take(&mut value["config"])?;
        let template = Self::new_novelty(value["config"].clone())?;
        p.validate(&template.inner.config)?;
        let old = template.definition();
        let expected = retention::definition(old.clone(), &p, version);
        if value["definition"] != expected
            || value["definition_hash"] != canonical_hash(&serde_json::to_vec(&expected).unwrap())?
        {
            return Err("retention definition/hash mismatch".into());
        }
        let saved = value["operator_state"]
            .as_object_mut()
            .ok_or("invalid operator state")?
            .remove("retention")
            .ok_or("missing retention state")?;
        value["dynamics"] = json!(novelty::KERNEL_ID);
        value["schema"] = json!(novelty::STATE_SCHEMA);
        value["definition_hash"] = json!(canonical_hash(&serde_json::to_vec(&old).unwrap())?);
        value["definition"] = old;
        let mut engine = Self::restore_novelty(value)?;
        engine.inner.retention = Some(retention::Operator::restore(
            p,
            saved,
            &engine.inner,
            version,
        )?);
        Ok(engine)
    }
    pub fn new_novelty(mut value: Value) -> Result<Self> {
        let mode = novelty::take_mode(&mut value)?;
        let mut engine = Self::new_memory(value)?;
        engine.inner.novelty = Some(novelty::Operator::new(mode));
        Ok(engine)
    }
    pub fn restore_novelty(mut value: Value) -> Result<Self> {
        if value["dynamics"] != novelty::KERNEL_ID || value["schema"] != novelty::STATE_SCHEMA {
            return Err("novelty kernel state identity mismatch".into());
        }
        let mode = novelty::take_mode(&mut value["config"])?;
        let mut config = value["config"].clone();
        let controls = take_memory(&mut config)?;
        let (base, parameters) = parse_config(config)?;
        let memory = memory_definition(&base, &parameters, controls);
        let expected = novelty::definition(memory.clone(), &mode);
        if value["definition"] != expected
            || value["definition_hash"] != canonical_hash(&serde_json::to_vec(&expected).unwrap())?
        {
            return Err("novelty definition/hash mismatch".into());
        }
        let saved = value["operator_state"]
            .as_object_mut()
            .ok_or("invalid operator state")?
            .remove("novelty")
            .ok_or("missing novelty state")?;
        value["dynamics"] = json!(MEMORY_ID);
        value["schema"] = json!(MEMORY_STATE);
        value["definition_hash"] = json!(canonical_hash(&serde_json::to_vec(&memory).unwrap())?);
        value["definition"] = memory;
        let mut engine = Self::restore_memory(value)?;
        engine.inner.novelty = Some(novelty::Operator::restore(mode, saved, &engine.inner)?);
        Ok(engine)
    }
    pub fn new(config: Value) -> Result<Self> {
        let (base, parameters) = parse_config(config)?;
        let mut inner = Engine::new(base)?;
        inner.continuous = Some(Operators::new(parameters));
        Ok(Self {
            inner,
            memory: None,
        })
    }
    pub fn new_memory(mut value: Value) -> Result<Self> {
        let controls = take_memory(&mut value)?;
        let mut engine = Self::new(value)?;
        engine.set_memory(controls);
        Ok(engine)
    }
    fn set_memory(&mut self, controls: MemoryControls) {
        self.memory = Some(controls);
        self.inner.edge_consolidation_enabled = controls.edge_consolidation_enabled;
        self.inner.continuous.as_mut().unwrap().depletion_enabled = controls.depletion_enabled;
    }
    pub fn restore_memory(mut value: Value) -> Result<Self> {
        if value["dynamics"] != MEMORY_ID || value["schema"] != MEMORY_STATE {
            return Err("memory kernel state identity mismatch".into());
        }
        let controls = take_memory(&mut value["config"])?;
        let (base, parameters) = parse_config(value["config"].clone())?;
        let expected = memory_definition(&base, &parameters, controls);
        let hash = canonical_hash(&serde_json::to_vec(&expected).map_err(|e| e.to_string())?)?;
        if value["definition"] != expected || value["definition_hash"] != hash {
            return Err("memory definition/hash mismatch".into());
        }
        value["dynamics"] = json!(KERNEL_ID);
        value["schema"] = json!(STATE_SCHEMA);
        value["definition"] = definition(&base, &parameters);
        value["definition_hash"] = json!(canonical_hash(
            &serde_json::to_vec(&value["definition"]).unwrap()
        )?);
        let mut engine = Self::restore(value)?;
        engine.set_memory(controls);
        Ok(engine)
    }
    pub fn identity(&self) -> (&'static str, &'static str) {
        if let Some(op) = self.inner.retention.as_ref() {
            op.version.identity()
        } else if self.inner.novelty.is_some() {
            (novelty::KERNEL_ID, novelty::STATE_SCHEMA)
        } else if self.memory.is_some() {
            (MEMORY_ID, MEMORY_STATE)
        } else {
            (KERNEL_ID, STATE_SCHEMA)
        }
    }
    pub fn restore(mut value: Value) -> Result<Self> {
        if value["dynamics"] != KERNEL_ID || value["schema"] != STATE_SCHEMA {
            return Err("continuous kernel state identity mismatch".into());
        }
        let (base, parameters) = parse_config(value["config"].clone())?;
        let expected = definition(&base, &parameters);
        let hash = canonical_hash(&serde_json::to_vec(&expected).map_err(|e| e.to_string())?)?;
        if value["definition"] != expected || value["definition_hash"] != hash {
            return Err("continuous definition/hash does not match configuration".into());
        }
        let object = value.as_object_mut().ok_or("invalid continuous state")?;
        object.remove("definition");
        object.remove("definition_hash");
        let operators = object
            .remove("operator_state")
            .ok_or("missing continuous operator state")?;
        if operators.as_object().is_none_or(|o| {
            o.len() != 2 || !o.contains_key("short_term") || !o.contains_key("fast")
        }) {
            return Err("invalid continuous operator-state fields".into());
        }
        object.insert("config".into(), serde_json::to_value(&base).unwrap());
        object.insert("dynamics".into(), json!(DYNAMICS));
        object.insert("schema".into(), json!(SCHEMA));
        let mut inner = Engine::restore(serde_json::from_value(value).map_err(|e| e.to_string())?)?;
        let mut restored = Operators::new(parameters);
        for row in serde_json::from_value::<Vec<StoredOperator<ShortTermState>>>(
            operators["short_term"].clone(),
        )
        .map_err(|e| e.to_string())?
        {
            let key = (row.source, row.target);
            let edge = inner.edge_index.get(&key).ok_or("invalid operator edge")?;
            row.state.validate()?;
            let when = parse_time(&row.state.time_us)?;
            if when < parse_time(&inner.edges[*edge].birth_us)?
                || when > inner.time
                || restored.short_term.insert(key, row.state).is_some()
            {
                return Err("invalid or duplicate operator history".into());
            }
        }
        for row in
            serde_json::from_value::<Vec<StoredOperator<FastTrace>>>(operators["fast"].clone())
                .map_err(|e| e.to_string())?
        {
            let key = (row.source, row.target);
            let edge = inner.edge_index.get(&key).ok_or("invalid operator edge")?;
            row.state
                .projected(inner.time, &restored.parameters.fast_trace())?;
            let when = parse_time(&row.state.time_us)?;
            if when < parse_time(&inner.edges[*edge].birth_us)?
                || when > inner.time
                || restored.fast.insert(key, row.state).is_some()
            {
                return Err("invalid or duplicate operator history".into());
            }
        }
        for event in &inner.queue {
            if event.kind == "signal" {
                validate_messages(&event.payload, inner.next_node)?;
            }
        }
        inner.continuous = Some(restored);
        Ok(Self {
            inner,
            memory: None,
        })
    }
    pub fn capture(&self) -> Result<Value> {
        let operators = self.inner.continuous.as_ref().unwrap();
        let definition = self.definition();
        let hash = canonical_hash(&serde_json::to_vec(&definition).map_err(|e| e.to_string())?)?;
        let mut state = serde_json::to_value(self.inner.capture()).map_err(|e| e.to_string())?;
        state["dynamics"] = json!(self.identity().0);
        state["schema"] = json!(self.identity().1);
        state["config"] = self.config();
        state["definition"] = definition;
        state["definition_hash"] = json!(hash);
        let short: Vec<_> = operators
            .short_term
            .iter()
            .map(|(&(source, target), state)| StoredOperator {
                source,
                target,
                state,
            })
            .collect();
        let fast: Vec<_> = operators
            .fast
            .iter()
            .map(|(&(source, target), state)| StoredOperator {
                source,
                target,
                state,
            })
            .collect();
        state["operator_state"] = json!({"short_term":short,"fast":fast});
        if let Some(novelty) = self.inner.novelty.as_ref() {
            state["operator_state"]["novelty"] = novelty.capture();
        }
        if let Some(op) = self.inner.retention.as_ref() {
            state["operator_state"]["retention"] = op.capture();
        }
        Ok(state)
    }
    pub fn definition(&self) -> Value {
        let operators = self.inner.continuous.as_ref().unwrap();
        let value = match self.memory {
            Some(m) => memory_definition(&self.inner.config, &operators.parameters, m),
            None => definition(&self.inner.config, &operators.parameters),
        };
        let value = if let Some(novelty) = self.inner.novelty.as_ref() {
            novelty::definition(value, &novelty.mode)
        } else {
            value
        };
        if let Some(op) = self.inner.retention.as_ref() {
            retention::definition(value, &op.p, op.version)
        } else {
            value
        }
    }
    pub fn config(&self) -> Value {
        let mut value = config_value(
            &self.inner.config,
            &self.inner.continuous.as_ref().unwrap().parameters,
        );
        if let Some(m) = self.memory {
            value.as_object_mut().unwrap().extend(
                serde_json::to_value(m)
                    .unwrap()
                    .as_object()
                    .unwrap()
                    .clone(),
            );
        }
        if let Some(novelty) = self.inner.novelty.as_ref() {
            value["novelty_mode"] = json!(novelty.mode);
        }
        if let Some(op) = self.inner.retention.as_ref() {
            value.as_object_mut().unwrap().extend(
                serde_json::to_value(&op.p)
                    .unwrap()
                    .as_object()
                    .unwrap()
                    .clone(),
            );
        }
        value
    }
    pub fn reconfigure(&mut self, mut value: Value) -> Result<()> {
        let retention = if let Some(op) = self.inner.retention.as_ref() {
            let p = retention::take(&mut value)?;
            if p.consolidation_mode != op.p.consolidation_mode
                || p.memory_growth_formula != op.p.memory_growth_formula
            {
                return Err("consolidation_mode is immutable; choose a new birth".into());
            }
            Some(p)
        } else {
            None
        };
        if let Some(novelty) = self.inner.novelty.as_ref() {
            if novelty::take_mode(&mut value)? != novelty.mode {
                return Err("novelty_mode is immutable after creation; use a new birth".into());
            }
        }
        let memory = if self.memory.is_some() {
            Some(take_memory(&mut value)?)
        } else {
            None
        };
        let (base, parameters) = parse_config(value)?;
        if let Some(p) = retention.as_ref() {
            p.validate(&base)?;
        }
        let current = self.inner.continuous.as_ref().unwrap();
        let changed_base = base != self.inner.config;
        if !changed_base
            && current.parameters == parameters
            && memory == self.memory
            && retention.as_ref() == self.inner.retention.as_ref().map(|op| &op.p)
        {
            return Ok(());
        }
        if self.inner.life == "dead" {
            return Err("a dead instance requires an explicit new birth".into());
        }
        let mut short = BTreeMap::new();
        let mut fast = BTreeMap::new();
        for (&key, state) in &current.short_term {
            short.insert(
                key,
                state.recovered(self.inner.time, &current.parameters.short_term())?,
            );
        }
        for (&key, state) in &current.fast {
            fast.insert(
                key,
                FastTrace {
                    value: state.projected(self.inner.time, &current.parameters.fast_trace())?,
                    time_us: self.inner.time.to_string(),
                },
            );
        }
        if retention.is_some() {
            if base.step_us != self.inner.config.step_us
                || base.seed != self.inner.config.seed
                || base.energy_initial_reserve != self.inner.config.energy_initial_reserve
            {
                return Err("cannot change immutable kernel parameters".into());
            }
            if let Some(mut op) = self.inner.retention.take() {
                op.settle_configuration(&mut self.inner);
                self.inner.retention = Some(op);
            }
            self.inner.relax(self.inner.time);
        }
        self.inner.reconfigure(base)?;
        if !changed_base {
            self.inner.sequence += 1;
        }
        let operators = self.inner.continuous.as_mut().unwrap();
        operators.parameters = parameters;
        operators.short_term = short;
        operators.fast = fast;
        if let Some(controls) = memory {
            self.set_memory(controls);
        }
        if let Some(p) = retention {
            let mut op = self.inner.retention.take().unwrap();
            op.configure(&self.inner, p);
            self.inner.retention = Some(op);
        }
        Ok(())
    }
    pub fn time(&self) -> u128 {
        self.inner.time
    }
    pub fn is_empty(&self) -> bool {
        self.inner.is_empty()
    }
    pub fn sequence(&self) -> u64 {
        self.inner.sequence
    }
    pub fn life(&self) -> &str {
        &self.inner.life
    }
    pub fn inject(&mut self, stimulus: Stimulus) -> Result<u64> {
        self.inner.inject(stimulus)
    }
    pub fn close_inputs(&mut self) {
        self.inner.close_inputs();
    }
    pub fn supply_energy(&mut self, time: u128, amount: f64, source: String) -> Result<u64> {
        self.inner.supply_energy(time, amount, source)
    }
    pub fn modulate_input(&mut self, time: u128, value: Value) -> Result<u64> {
        self.inner.modulate_input(time, value)
    }
    pub fn advance(&mut self, time: u128, record: bool) -> Result<Vec<Value>> {
        self.inner.advance(time, record)
    }
    pub fn advance_inputs(&mut self, time: u128) -> Result<Vec<Value>> {
        self.inner.advance_inputs(time)
    }
    pub fn intervene_action(
        &mut self,
        nodes: Vec<u64>,
        edges: Vec<(u64, u64)>,
        action: &str,
    ) -> Result<()> {
        self.inner.intervene_action(nodes, edges, action)?;
        self.inner.prune_operator_state();
        Ok(())
    }
    pub fn intervene(
        &mut self,
        nodes: Vec<u64>,
        edges: Vec<(u64, u64)>,
        lesion: bool,
    ) -> Result<()> {
        self.inner.intervene(nodes, edges, lesion)?;
        self.inner.prune_operator_state();
        Ok(())
    }
    pub fn activations(&self) -> Vec<(u64, f64)> {
        self.inner.activations()
    }
    pub fn observation_nodes(&self) -> Vec<Node> {
        self.inner.observation_nodes()
    }
    pub fn induced_edges(&self, nodes: Vec<u64>) -> Vec<Edge> {
        self.inner.induced_edges(nodes)
    }
    pub fn spatial_geometry(&self) -> Result<Value> {
        self.inner.spatial_geometry()
    }
    pub fn graph(&self, limit: Option<usize>) -> Value {
        let mut value = self.inner.graph(limit);
        value["kernel_id"] = json!(self.identity().0);
        value["observation_quantity"] = json!("activation");
        value
    }
    pub fn metrics(&self) -> Value {
        let mut value = self.inner.metrics();
        let operators = self.inner.continuous.as_ref().unwrap();
        value["kernel_id"] = json!(self.identity().0);
        value["state_schema"] = json!(self.identity().1);
        value["operator_state"] = json!({"short_term_edges":operators.short_term.len(),"fast_edges":operators.fast.len()});
        if let Some(novelty) = self.inner.novelty.as_ref() {
            value["novelty"] = novelty.metrics();
        }
        if let Some(op) = self.inner.retention.as_ref() {
            value["retention"] = op.metrics(&self.inner);
            value["mean_weight"] = if self.inner.edges.is_empty() {
                Value::Null
            } else {
                json!(
                    self.inner
                        .edges
                        .iter()
                        .map(|e| op
                            .edge_value(&self.inner, (e.source, e.target), self.inner.time)
                            .0)
                        .sum::<f64>()
                        / self.inner.edges.len() as f64
                )
            };
        }
        value
    }
}

fn validate_messages(payload: &Value, next_node: u64) -> Result<()> {
    let fields = payload.as_object().ok_or("invalid signal payload")?;
    if !fields.contains_key("messages") {
        if fields.len() != 1 || !fields.contains_key("values") {
            return Err("unexpected signal fields".into());
        }
        return Ok(());
    }
    if fields.len() != 2 || !fields.contains_key("values") {
        return Err("unexpected contextual signal fields".into());
    }
    let messages: Vec<Message> =
        serde_json::from_value(payload["messages"].clone()).map_err(|e| e.to_string())?;
    let values: Vec<(u64, f64)> =
        serde_json::from_value(payload["values"].clone()).map_err(|e| e.to_string())?;
    let mut sums: BTreeMap<u64, f64> = BTreeMap::new();
    let mut pairs = BTreeSet::new();
    for (source, target, amount, key) in messages {
        if source == 0
            || target == 0
            || source >= next_node
            || target >= next_node
            || source == target
            || !pairs.insert((source, target))
            || !amount.is_finite()
            || !(0.0..=1e12).contains(&amount)
            || key.len() != 4
            || key
                .iter()
                .any(|v| !v.is_finite() || !(0.0..=1.0).contains(v))
        {
            return Err("invalid contextual message".into());
        }
        *sums.entry(target).or_default() += amount;
    }
    let mut seen = BTreeSet::new();
    if sums.len() != values.len() {
        return Err("raw arrival amounts disagree with contextual messages".into());
    }
    for (target, value) in values {
        let sum = *sums.get(&target).ok_or("missing message target")?;
        if !seen.insert(target)
            || (value - sum).abs() > 1e-14f64.max(1e-12 * value.abs().max(sum.abs()))
        {
            return Err("raw arrival amounts disagree with contextual messages".into());
        }
    }
    Ok(())
}
