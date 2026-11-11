//! Historical engines are separate dependencies, not branches in modern dynamics.
use crate::{Result, Stimulus};
use serde_json::{json, Value};

pub enum LegacyEngine {
    Compatible(&'static str, threemind_causal_legacy::Engine),
    V3(threemind_causal8_legacy::Engine),
}

fn identity(value: &str) -> Result<(&'static str, usize)> {
    match value {
        "threemind.causal/1" => Ok(("threemind.causal/1", 1)),
        "threemind.causal/2" => Ok(("threemind.causal/2", 2)),
        "threemind.causal/3" => Ok(("threemind.causal/3", 3)),
        "threemind.causal/4" => Ok(("threemind.causal/4", 4)),
        "threemind.causal/5" => Ok(("threemind.causal/5", 5)),
        "threemind.causal/6" => Ok(("threemind.causal/6", 6)),
        "threemind.causal/7" => Ok(("threemind.causal/7", 7)),
        "threemind.causal/8" => Ok(("threemind.causal/8", 8)),
        _ => Err("unknown historical causal identity".into()),
    }
}

fn normalized(id: &str, value: Value) -> Result<Value> {
    let defaults: Value = serde_json::from_str(include_str!("legacy-configs.json")).unwrap();
    let mut config = defaults[id].clone();
    let input = value
        .as_object()
        .ok_or("historical configuration must be an object")?;
    for (key, value) in input {
        if config.get(key).is_none() {
            return Err(format!("unknown configuration field {key} for {id}"));
        }
        config[key] = value.clone();
    }
    Ok(config)
}

fn validate_compatible(n: usize, config: &threemind_causal_legacy::Config) -> Result<()> {
    if n < 2 && config.has_optional_changes()
        || n < 3 && config.has_budget_limits()
        || n < 4 && config.has_energy_changes()
        || n < 5 && config.has_attention_changes()
        || n < 6 && config.has_spatial_changes()
    {
        return Err("configuration requires mechanisms absent from this historical kernel; identity is fixed at birth".into());
    }
    Ok(())
}

impl LegacyEngine {
    pub fn new(id: &str, config: Value) -> Result<Self> {
        let (id, n) = identity(id)?;
        let config = normalized(id, config)?;
        if n == 8 {
            return Ok(Self::V3(threemind_causal8_legacy::Engine::new(
                serde_json::from_value(config).map_err(|e| e.to_string())?,
            )?));
        }
        let config = serde_json::from_value(config).map_err(|e| e.to_string())?;
        validate_compatible(n, &config)?;
        Ok(Self::Compatible(
            id,
            threemind_causal_legacy::Engine::new_version(config, id)?,
        ))
    }
    pub fn restore(state: Value) -> Result<Self> {
        let (id, n) = identity(
            state["dynamics"]
                .as_str()
                .ok_or("missing historical identity")?,
        )?;
        normalized(id, state["config"].clone())?;
        if n == 8 {
            Ok(Self::V3(threemind_causal8_legacy::Engine::restore(
                serde_json::from_value(state).map_err(|e| e.to_string())?,
            )?))
        } else {
            Ok(Self::Compatible(
                id,
                threemind_causal_legacy::Engine::restore(
                    serde_json::from_value(state).map_err(|e| e.to_string())?,
                )?,
            ))
        }
    }
    pub fn identity(&self) -> &'static str {
        match self {
            Self::Compatible(id, _) => id,
            Self::V3(_) => "threemind.causal/8",
        }
    }
    pub fn config(&self) -> Value {
        let mut value = match self {
            Self::Compatible(_, e) => serde_json::to_value(&e.config).unwrap(),
            Self::V3(e) => serde_json::to_value(&e.config).unwrap(),
        };
        let defaults: Value = serde_json::from_str(include_str!("legacy-configs.json")).unwrap();
        value
            .as_object_mut()
            .unwrap()
            .retain(|k, _| defaults[self.identity()].get(k).is_some());
        value
    }
    pub fn definition(&self) -> Value {
        let (_, n) = identity(self.identity()).unwrap();
        json!({"schema":"threemind.kernel-definition/1", "kernel_id":self.identity(),
            "state_schema":format!("threemind.state/{}",if n <= 2 {2} else if n == 3 {3} else if n == 4 {4} else if n <= 7 {5} else {6}),
            "hypothesis_id":format!("threemind.hypotheses/causal{n}"),
            "operators":[{"id":format!("threemind.causal{n}-transition/1"),"phase":"historical-event-clock"}],
            "config":self.config()})
    }
    pub fn capture(&self) -> Result<Value> {
        match self {
            Self::Compatible(_, e) => serde_json::to_value(e.capture()).map_err(|e| e.to_string()),
            Self::V3(e) => serde_json::to_value(e.capture()).map_err(|e| e.to_string()),
        }
    }
    pub fn time(&self) -> u128 {
        match self {
            Self::Compatible(_, e) => e.time,
            Self::V3(e) => e.time,
        }
    }
    pub fn sequence(&self) -> u64 {
        match self {
            Self::Compatible(_, e) => e.sequence,
            Self::V3(e) => e.sequence,
        }
    }
    pub fn life(&self) -> &str {
        match self {
            Self::Compatible(_, e) => &e.life,
            Self::V3(e) => &e.life,
        }
    }
    pub fn is_empty(&self) -> bool {
        match self {
            Self::Compatible(_, e) => e.is_empty(),
            Self::V3(e) => e.is_empty(),
        }
    }
    pub fn metrics(&self) -> Value {
        match self {
            Self::Compatible(_, e) => e.metrics(),
            Self::V3(e) => e.metrics(),
        }
    }
    pub fn graph(&self, limit: Option<usize>) -> Value {
        match self {
            Self::Compatible(_, e) => e.graph(limit),
            Self::V3(e) => e.graph(limit),
        }
    }
    pub fn activations(&self) -> Vec<(u64, f64)> {
        match self {
            Self::Compatible(_, e) => e.activations(),
            Self::V3(e) => e.activations(),
        }
    }
    pub fn observation_nodes(&self) -> Value {
        match self {
            Self::Compatible(_, e) => serde_json::to_value(e.observation_nodes()).unwrap(),
            Self::V3(e) => serde_json::to_value(e.observation_nodes()).unwrap(),
        }
    }
    pub fn induced_edges(&self, nodes: Vec<u64>) -> Value {
        match self {
            Self::Compatible(_, e) => serde_json::to_value(e.induced_edges(nodes)).unwrap(),
            Self::V3(e) => serde_json::to_value(e.induced_edges(nodes)).unwrap(),
        }
    }
    pub fn spatial_geometry(&self) -> Result<Value> {
        match self {
            Self::Compatible(_, e) => e.spatial_geometry(),
            Self::V3(e) => e.spatial_geometry(),
        }
    }
    pub fn inject(&mut self, stimulus: Stimulus) -> Result<u64> {
        let (_, n) = identity(self.identity())?;
        if n < 7 && stimulus.bypass_attention {
            return Err(
                "per-frame attention bypass requires causal/7; kernel identity is fixed at birth"
                    .into(),
            );
        }
        let payload = serde_json::to_value(stimulus).map_err(|e| e.to_string())?;
        match self {
            Self::Compatible(_, e) => {
                e.inject(serde_json::from_value(payload).map_err(|e| e.to_string())?)
            }
            Self::V3(e) => e.inject(serde_json::from_value(payload).map_err(|e| e.to_string())?),
        }
    }
    pub fn close_inputs(&mut self) {
        match self {
            Self::Compatible(_, e) => e.close_inputs(),
            Self::V3(e) => e.close_inputs(),
        }
    }
    pub fn supply_energy(&mut self, time: u128, amount: f64, source: String) -> Result<u64> {
        if identity(self.identity())?.1 < 4 {
            return Err("historical kernel has no energy port".into());
        }
        match self {
            Self::Compatible(_, e) => e.supply_energy(time, amount, source),
            Self::V3(e) => e.supply_energy(time, amount, source),
        }
    }
    pub fn modulate_input(&mut self, time: u128, value: Value) -> Result<u64> {
        if identity(self.identity())?.1 < 5 {
            return Err("historical kernel has no attention modulation port".into());
        }
        match self {
            Self::Compatible(_, e) => e.modulate_input(time, value),
            Self::V3(e) => e.modulate_input(time, value),
        }
    }
    pub fn reconfigure(&mut self, config: Value) -> Result<()> {
        let (id, n) = identity(self.identity())?;
        let config = normalized(id, config)?;
        match self {
            Self::Compatible(_, e) => {
                let config = serde_json::from_value(config).map_err(|e| e.to_string())?;
                validate_compatible(n, &config)?;
                e.reconfigure(config)
            }
            Self::V3(e) => {
                e.reconfigure(serde_json::from_value(config).map_err(|e| e.to_string())?)
            }
        }
    }
    pub fn advance(&mut self, time: u128, record: bool) -> Result<Vec<Value>> {
        match self {
            Self::Compatible(_, e) => e.advance(time, record),
            Self::V3(e) => e.advance(time, record),
        }
    }
    pub fn advance_inputs(&mut self, time: u128, record: bool) -> Result<Vec<Value>> {
        let rows = match self {
            Self::Compatible(_, e) => e.advance_inputs(time),
            Self::V3(e) => e.advance_inputs(time),
        }?;
        Ok(if record { rows } else { Vec::new() })
    }
    pub fn intervene(
        &mut self,
        nodes: Vec<u64>,
        edges: Vec<(u64, u64)>,
        lesion: bool,
    ) -> Result<()> {
        match self {
            Self::Compatible(_, e) => e.intervene(nodes, edges, lesion),
            Self::V3(_) => {
                Err("historical causal/8 native executor has no intervention port".into())
            }
        }
    }
}
