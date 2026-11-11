//! Local edge-birth evidence, never semantic novelty or an external score.
use super::*;

pub const KERNEL_ID: &str = "threemind.continuous-memory/2";
pub const STATE_SCHEMA: &str = "threemind.continuous-memory-state/2";
const COUNTERS: [&str; 7] = [
    "births",
    "ineligible",
    "disabled",
    "no_reentry",
    "reference_reached",
    "awarded",
    "cancelled",
];
const TOTALS: [&str; 3] = ["requested_bonus", "weight_bonus", "stability_bonus"];

pub fn take_mode(value: &mut Value) -> Result<String> {
    let mode = value
        .as_object_mut()
        .ok_or("configuration must be an object")?
        .remove("novelty_mode")
        .unwrap_or(json!("arrival-window"));
    match mode.as_str() {
        Some("immediate" | "arrival-window") => Ok(mode.as_str().unwrap().into()),
        _ => Err("novelty_mode must be immediate or arrival-window".into()),
    }
}

pub fn definition(mut value: Value, mode: &str) -> Value {
    value["kernel_id"] = json!(KERNEL_ID);
    value["state_schema"] = json!(STATE_SCHEMA);
    value["hypothesis_id"] = json!("threemind.hypotheses/continuous-memory2");
    value["config"]["novelty_mode"] = json!(mode);
    value["operators"].as_array_mut().unwrap().push(json!({
        "id":"threemind.local-birth-novelty/2", "phase":"after-arrivals-before-emission"
    }));
    value
}

#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Pending {
    source: u64,
    target: u64,
    serial: u64,
    birth_us: String,
    deadline_us: String,
    gain: f64,
    reference: f64,
    source_touch: f64,
    target_touch: f64,
}

pub(super) struct Operator {
    pub mode: String,
    serial: u64,
    pending: BTreeMap<(u64, u64), Pending>,
    by_node: BTreeMap<u64, BTreeSet<(u64, u64)>>,
    deadlines: BTreeSet<(u128, u64, (u64, u64))>,
    pub audit: BTreeMap<String, Value>,
}

fn reason(eligible: bool, gain: f64, reentry: f64, reference: f64) -> &'static str {
    if !eligible {
        "ineligible"
    } else if gain == 0.0 {
        "disabled"
    } else if reentry <= 0.0 {
        "no_reentry"
    } else if reentry >= reference {
        "reference_reached"
    } else {
        "awarded"
    }
}

impl Operator {
    pub fn new(mode: String) -> Self {
        Self {
            mode,
            serial: 0,
            pending: BTreeMap::new(),
            by_node: BTreeMap::new(),
            deadlines: BTreeSet::new(),
            audit: COUNTERS
                .into_iter()
                .map(|k| (k.into(), json!(0)))
                .chain(TOTALS.into_iter().map(|k| (k.into(), json!(0.0))))
                .collect(),
        }
    }
    fn count(&mut self, key: &str) {
        self.audit
            .insert(key.into(), json!(self.audit[key].as_u64().unwrap() + 1));
    }
    fn add(&mut self, key: &str, amount: f64) {
        self.audit.insert(
            key.into(),
            json!(self.audit[key].as_f64().unwrap() + amount),
        );
    }
    fn insert(&mut self, row: Pending) {
        let key = (row.source, row.target);
        for node in [row.source, row.target] {
            self.by_node.entry(node).or_default().insert(key);
        }
        self.deadlines
            .insert((parse_time(&row.deadline_us).unwrap(), row.serial, key));
        self.pending.insert(key, row);
    }
    fn remove(&mut self, key: (u64, u64)) -> Pending {
        let row = self.pending.remove(&key).unwrap();
        self.deadlines
            .remove(&(parse_time(&row.deadline_us).unwrap(), row.serial, key));
        for node in [key.0, key.1] {
            let keys = self.by_node.get_mut(&node).unwrap();
            keys.remove(&key);
            if keys.is_empty() {
                self.by_node.remove(&node);
            }
        }
        row
    }
    pub fn birth(
        &mut self,
        key: (u64, u64),
        eligible: bool,
        touches: (f64, f64),
        time: u128,
        deadline: u128,
        c: &Config,
    ) -> f64 {
        self.count("births");
        let reentry = touches.0.max(touches.1);
        let cause = reason(
            eligible,
            c.local_novelty_gain,
            reentry,
            c.novelty_touch_reference,
        );
        if self.mode == "immediate" {
            let bonus = if cause == "awarded" {
                c.local_novelty_gain
                    * (1.0 - (reentry / c.novelty_touch_reference).min(1.0)).max(0.0)
            } else {
                0.0
            };
            self.count(cause);
            self.add("requested_bonus", bonus);
            return bonus;
        }
        if !eligible || c.local_novelty_gain == 0.0 {
            self.count(if !eligible { "ineligible" } else { "disabled" });
            return 0.0;
        }
        self.serial += 1;
        self.insert(Pending {
            source: key.0,
            target: key.1,
            serial: self.serial,
            birth_us: time.to_string(),
            deadline_us: deadline.to_string(),
            gain: c.local_novelty_gain,
            reference: c.novelty_touch_reference,
            source_touch: touches.0,
            target_touch: touches.1,
        });
        0.0
    }
    pub fn touch(&mut self, node: u64, amount: f64) {
        if amount <= 0.0 {
            return;
        }
        if let Some(keys) = self.by_node.get(&node) {
            for key in keys {
                let row = self.pending.get_mut(key).unwrap();
                if key.0 == node {
                    row.source_touch += amount;
                } else {
                    row.target_touch += amount;
                }
            }
        }
    }
    pub fn deadline(&self) -> Option<u128> {
        self.deadlines.first().map(|row| row.0)
    }
    pub fn settle(&mut self, engine: &mut Engine) {
        while let Some(&(deadline, _, key)) = self.deadlines.first() {
            if deadline > engine.time {
                break;
            }
            let row = self.remove(key);
            if !engine.edge_index.contains_key(&key)
                || !engine.config.plasticity
                || engine.silenced_edges.contains(&key)
                || engine.silenced_nodes.contains(&key.0)
                || engine.silenced_nodes.contains(&key.1)
            {
                self.count("cancelled");
                continue;
            }
            let reentry = row.source_touch.max(row.target_touch);
            let cause = reason(true, row.gain, reentry, row.reference);
            self.count(cause);
            if cause == "awarded" {
                let bonus = row.gain * (1.0 - (reentry / row.reference).min(1.0)).max(0.0);
                engine.retention_prepare_edge(key);
                let edge = &mut engine.edges[engine.edge_index[&key]];
                self.add("requested_bonus", bonus);
                self.add("weight_bonus", (edge.weight + bonus).min(1.0) - edge.weight);
                self.add(
                    "stability_bonus",
                    (edge.stability + bonus).min(1.0) - edge.stability,
                );
                edge.weight = (edge.weight + bonus).min(1.0);
                edge.stability = (edge.stability + bonus).min(1.0);
                engine.retention_edge_changed(key);
            }
        }
    }
    pub(super) fn cancel(&mut self, key: (u64, u64)) {
        if self.pending.contains_key(&key) {
            self.remove(key);
            self.count("cancelled");
        }
    }
    pub fn retain(&mut self, edges: &HashMap<(u64, u64), usize>) {
        let removed: Vec<_> = self
            .pending
            .keys()
            .filter(|k| !edges.contains_key(k))
            .copied()
            .collect();
        for key in removed {
            self.remove(key);
            self.count("cancelled");
        }
    }
    pub fn capture(&self) -> Value {
        json!({"serial":self.serial,"pending":self.pending.values().collect::<Vec<_>>(),"audit":self.audit})
    }
    pub fn metrics(&self) -> Value {
        let mut value = serde_json::to_value(&self.audit).unwrap();
        value["pending"] = json!(self.pending.len());
        value
    }
    pub fn restore(mode: String, saved: Value, engine: &Engine) -> Result<Self> {
        if saved.as_object().is_none_or(|o| {
            o.len() != 3
                || !o.contains_key("serial")
                || !o.contains_key("pending")
                || !o.contains_key("audit")
        }) {
            return Err("invalid novelty state fields".into());
        }
        let mut result = Self::new(mode);
        result.serial = saved["serial"].as_u64().ok_or("invalid novelty serial")?;
        let audit = saved["audit"].as_object().ok_or("invalid novelty audit")?;
        if audit.len() != COUNTERS.len() + TOTALS.len() {
            return Err("invalid novelty audit keys".into());
        }
        for key in COUNTERS {
            audit
                .get(key)
                .and_then(Value::as_u64)
                .ok_or("invalid novelty counter")?;
        }
        for key in TOTALS {
            if audit
                .get(key)
                .and_then(Value::as_f64)
                .is_none_or(|v| !v.is_finite() || v < 0.0)
            {
                return Err("invalid novelty total".into());
            }
        }
        result.audit = audit.iter().map(|(k, v)| (k.clone(), v.clone())).collect();
        let rows: Vec<Pending> =
            serde_json::from_value(saved["pending"].clone()).map_err(|e| e.to_string())?;
        let mut serials = BTreeSet::new();
        for row in rows {
            let key = (row.source, row.target);
            let edge = engine.edge_index.get(&key).ok_or("invalid novelty edge")?;
            if row.birth_us != engine.edges[*edge].birth_us
                || parse_time(&row.birth_us)? > engine.time
                || parse_time(&row.deadline_us)? <= engine.time
                || row.serial == 0
                || row.serial > result.serial
                || !serials.insert(row.serial)
                || result.pending.contains_key(&key)
                || result.mode != "arrival-window"
                || [row.gain, row.source_touch, row.target_touch]
                    .iter()
                    .any(|v| !v.is_finite() || *v < 0.0)
                || !row.reference.is_finite()
                || row.reference < 1e-300
            {
                return Err("invalid pending novelty identity, lifetime or value".into());
            }
            result.insert(row);
        }
        Ok(result)
    }
}
