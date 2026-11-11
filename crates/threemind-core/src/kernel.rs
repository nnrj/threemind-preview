//! Scientific kernel dispatch; changing implementation is not changing identity.

use crate::{continuous, lif, Engine, Result, Stimulus, DYNAMICS};
use serde_json::{json, Value};

pub enum Kernel {
    Causal(Engine),
    Continuous(continuous::ContinuousEngine),
    Lif(lif::LifEngine),
    Local(crate::local::LocalEngine),
    Local5(crate::local::LocalEngine5),
    Local51(crate::local51::LocalEngine51),
    Local53(crate::local53::LocalEngine53),
    WeightDecay(crate::weight_decay::LocalWeightDecayEngine),
    Local52(crate::local52::LocalEngine52),
    Legacy(crate::legacy::LegacyEngine),
}

impl Kernel {
    pub fn new(identity: &str, configuration: Value) -> Result<Self> {
        match identity {
            "threemind.causal/1" | "threemind.causal/2" | "threemind.causal/3" | "threemind.causal/4" | "threemind.causal/5" | "threemind.causal/6" | "threemind.causal/7" | "threemind.causal/8" => Ok(Self::Legacy(crate::legacy::LegacyEngine::new(identity, configuration)?)),
            crate::local51::KERNEL_ID => Ok(Self::Local51(crate::local51::LocalEngine51::new(configuration)?)),
            crate::local53::KERNEL_ID => Ok(Self::Local53(crate::local53::LocalEngine53::new(configuration)?)),
            crate::weight_decay::KERNEL_ID => Ok(Self::WeightDecay(crate::weight_decay::LocalWeightDecayEngine::new(configuration)?)),
            crate::local52::KERNEL_ID => Ok(Self::Local52(crate::local52::LocalEngine52::new(configuration)?)),
            crate::local::KERNEL5_ID => Ok(Self::Local5(crate::local::LocalEngine5::new(configuration)?)),
            crate::local::KERNEL_ID => Ok(Self::Local(crate::local::LocalEngine::new(configuration)?)),
            DYNAMICS => Ok(Self::Causal(Engine::new(
                serde_json::from_value(configuration).map_err(|e| e.to_string())?,
            )?)),
            continuous::KERNEL_ID => Ok(Self::Continuous(continuous::ContinuousEngine::new(
                configuration,
            )?)),
            continuous::MEMORY_ID => Ok(Self::Continuous(
                continuous::ContinuousEngine::new_memory(configuration)?,
            )),
            crate::novelty::KERNEL_ID => Ok(Self::Continuous(
                continuous::ContinuousEngine::new_novelty(configuration)?,
            )),
            crate::retention::KERNEL_ID => Ok(Self::Continuous(
                continuous::ContinuousEngine::new_retention(configuration)?,
            )),
            crate::retention::KERNEL31_ID => Ok(Self::Continuous(
                continuous::ContinuousEngine::new_retention31(configuration)?,
            )),
            lif::KERNEL_ID => Ok(Self::Lif(lif::LifEngine::new(configuration)?)),
            _ => Err("unsupported kernel; no automatic conversion or fallback".into()),
        }
    }
    pub fn restore(state: Value) -> Result<Self> {
        match state["dynamics"].as_str() {
            Some("threemind.causal/1" | "threemind.causal/2" | "threemind.causal/3" | "threemind.causal/4" | "threemind.causal/5" | "threemind.causal/6" | "threemind.causal/7" | "threemind.causal/8") => Ok(Self::Legacy(crate::legacy::LegacyEngine::restore(state)?)),
            Some(crate::local51::KERNEL_ID) => Ok(Self::Local51(crate::local51::LocalEngine51::restore(state)?)),
            Some(crate::local53::KERNEL_ID) => Ok(Self::Local53(crate::local53::LocalEngine53::restore(state)?)),
            Some(crate::weight_decay::KERNEL_ID) => Ok(Self::WeightDecay(crate::weight_decay::LocalWeightDecayEngine::restore(state)?)),
            Some(crate::local52::KERNEL_ID) => Ok(Self::Local52(crate::local52::LocalEngine52::restore(state)?)),
            Some(crate::local::KERNEL5_ID) => Ok(Self::Local5(crate::local::LocalEngine5::restore(state)?)),
            Some(crate::local::KERNEL_ID) => Ok(Self::Local(crate::local::LocalEngine::restore(state)?)),
            Some(DYNAMICS) => Ok(Self::Causal(Engine::restore(
                serde_json::from_value(state).map_err(|e| e.to_string())?,
            )?)),
            Some(continuous::KERNEL_ID) => Ok(Self::Continuous(
                continuous::ContinuousEngine::restore(state)?,
            )),
            Some(continuous::MEMORY_ID) => Ok(Self::Continuous(
                continuous::ContinuousEngine::restore_memory(state)?,
            )),
            Some(crate::novelty::KERNEL_ID) => Ok(Self::Continuous(
                continuous::ContinuousEngine::restore_novelty(state)?,
            )),
            Some(crate::retention::KERNEL_ID) => Ok(Self::Continuous(
                continuous::ContinuousEngine::restore_retention(state)?,
            )),
            Some(crate::retention::KERNEL31_ID) => Ok(Self::Continuous(
                continuous::ContinuousEngine::restore_retention31(state)?,
            )),
            Some(lif::KERNEL_ID) => Ok(Self::Lif(lif::LifEngine::restore(state)?)),
            _ => Err("unsupported kernel; no automatic conversion or fallback".into()),
        }
    }
    pub fn identity(&self) -> &'static str {
        match self {
            Self::Legacy(e) => e.identity(),
            Self::Local(_) => crate::local::KERNEL_ID,
            Self::Local5(_) => crate::local::KERNEL5_ID,
            Self::Local51(_) => crate::local51::KERNEL_ID,
            Self::Local53(_) => crate::local53::KERNEL_ID,
            Self::WeightDecay(_) => crate::weight_decay::KERNEL_ID,
            Self::Local52(_) => crate::local52::KERNEL_ID,
            Self::Causal(_) => DYNAMICS,
            Self::Continuous(e) => e.identity().0,
            Self::Lif(_) => lif::KERNEL_ID,
        }
    }
    pub fn from_definition(value: Value) -> Result<Self> {
        let identity = value["kernel_id"]
            .as_str()
            .ok_or("definition requires kernel_id")?;
        let engine = Self::new(identity, value["config"].clone())?;
        let mut normalized = value;
        normalized["config"] = engine.config();
        if normalized != engine.definition() {
            return Err("unsupported kernel definition, hypothesis or operator phase".into());
        }
        Ok(engine)
    }
    pub fn config(&self) -> Value {
        match self {
            Self::Legacy(e) => e.config(),
            Self::Local(e) => e.config(),
            Self::Local5(e) => e.config(),
            Self::Local51(e) => e.config(),
            Self::Local53(e) => e.config(),
            Self::WeightDecay(e) => e.config(),
            Self::Local52(e) => e.config(),
            Self::Causal(e) => serde_json::to_value(&e.config).unwrap(),
            Self::Continuous(e) => e.config(),
            Self::Lif(e) => e.config.value(),
        }
    }
    pub fn definition(&self) -> Value {
        match self {
            Self::Legacy(e) => e.definition(),
            Self::Local(e) => e.definition(),
            Self::Local5(e) => e.definition(),
            Self::Local51(e) => e.definition(),
            Self::Local53(e) => e.definition(),
            Self::WeightDecay(e) => e.definition(),
            Self::Local52(e) => e.definition(),
            Self::Lif(e) => e.definition(),
            Self::Causal(_) => {
                json!({"schema":"threemind.kernel-definition/1", "kernel_id":DYNAMICS,
                "state_schema":crate::SCHEMA, "hypothesis_id":"threemind.hypotheses/causal9",
                "operators":[{"id":"threemind.causal9-transition/1","phase":"hybrid-event-clock"}], "config":self.config()})
            }
            Self::Continuous(e) => e.definition(),
        }
    }
    pub fn capture(&self) -> Result<Value> {
        match self {
            Self::Legacy(e) => e.capture(),
            Self::Local(e) => e.capture(),
            Self::Local5(e) => e.capture(),
            Self::Local51(e) => e.capture(),
            Self::Local53(e) => e.capture(),
            Self::WeightDecay(e) => e.capture(),
            Self::Local52(e) => e.capture(),
            Self::Causal(e) => serde_json::to_value(e.capture()).map_err(|e| e.to_string()),
            Self::Continuous(e) => e.capture(),
            Self::Lif(e) => e.capture(),
        }
    }
    pub fn time(&self) -> u128 {
        match self {
            Self::Legacy(e) => e.time(),
            Self::Local(e) => e.time,
            Self::Local5(e) => e.time,
            Self::Local51(e) => e.time,
            Self::Local53(e) => e.time,
            Self::WeightDecay(e) => e.time,
            Self::Local52(e) => e.time,
            Self::Causal(e) => e.time,
            Self::Continuous(e) => e.time(),
            Self::Lif(e) => e.time,
        }
    }
    pub fn life(&self) -> &str {
        match self {
            Self::Legacy(e) => e.life(),
            Self::Local(e) => &e.life,
            Self::Local5(e) => &e.life,
            Self::Local51(e) => &e.life,
            Self::Local53(e) => &e.life,
            Self::WeightDecay(e) => &e.life,
            Self::Local52(e) => &e.life,
            Self::Causal(e) => &e.life,
            Self::Continuous(e) => e.life(),
            Self::Lif(e) => &e.life,
        }
    }
    pub fn is_empty(&self) -> bool {
        match self {
            Self::Legacy(e) => e.is_empty(),
            Self::Local(e) => e.is_empty(),
            Self::Local5(e) => e.is_empty(),
            Self::Local51(e) => e.is_empty(),
            Self::Local53(e) => e.is_empty(),
            Self::WeightDecay(e) => e.is_empty(),
            Self::Local52(e) => e.is_empty(),
            Self::Causal(e) => e.is_empty(),
            Self::Continuous(e) => e.is_empty(),
            Self::Lif(e) => e.is_empty(),
        }
    }
    pub fn metrics(&self) -> Value {
        match self {
            Self::Legacy(e) => e.metrics(),
            Self::Local(e) => e.metrics(),
            Self::Local5(e) => e.metrics(),
            Self::Local51(e) => e.metrics(),
            Self::Local53(e) => e.metrics(),
            Self::WeightDecay(e) => e.metrics(),
            Self::Local52(e) => e.metrics(),
            Self::Causal(e) => e.metrics(),
            Self::Continuous(e) => e.metrics(),
            Self::Lif(e) => e.metrics(),
        }
    }
    pub fn inject(&mut self, event: Stimulus) -> Result<u64> {
        match self {
            Self::Legacy(e) => e.inject(event),
            Self::Local(e) => e.inject(event),
            Self::Local5(e) => e.inject(event),
            Self::Local51(e) => e.inject(event),
            Self::Local53(e) => e.inject(event),
            Self::WeightDecay(e) => e.inject(event),
            Self::Local52(e) => e.inject(event),
            Self::Causal(e) => e.inject(event),
            Self::Continuous(e) => e.inject(event),
            Self::Lif(e) => e.inject(event),
        }
    }
    pub fn supply_energy(&mut self, time: u128, amount: f64, source: String) -> Result<u64> {
        match self {
            Self::Legacy(e) => e.supply_energy(time, amount, source),
            Self::Local(e) => e.supply_energy(time,amount,source),
            Self::Local5(e) => e.supply_energy(time,amount,source),
            Self::Local51(e) => e.supply_energy(time,amount,source),
            Self::Local53(e) => e.supply_energy(time,amount,source),
            Self::WeightDecay(e) => e.supply_energy(time,amount,source),
            Self::Local52(e) => e.supply_energy(time,amount,source),
            Self::Causal(e) => e.supply_energy(time, amount, source),
            Self::Continuous(e) => e.supply_energy(time, amount, source),
            Self::Lif(_) => Err("LIF currents are not a causal energy ledger".into()),
        }
    }
    pub fn modulate_input(&mut self, time: u128, value: Value) -> Result<u64> {
        match self {
            Self::Legacy(e) => e.modulate_input(time, value),
            Self::Local(e) => e.modulate_input(time,value),
            Self::Local5(e) => e.modulate_input(time,value),
            Self::Local51(e) => e.modulate_input(time,value),
            Self::Local53(e) => e.modulate_input(time,value),
            Self::WeightDecay(e) => e.modulate_input(time,value),
            Self::Local52(e) => e.modulate_input(time,value),
            Self::Causal(e) => e.modulate_input(time, value),
            Self::Continuous(e) => e.modulate_input(time, value),
            Self::Lif(_) => Err("LIF does not implement causal input modulation".into()),
        }
    }
    pub fn close_inputs(&mut self) {
        match self {
            Self::Legacy(e) => e.close_inputs(),
            Self::Local(e) => e.close_inputs(),
            Self::Local5(e) => e.close_inputs(),
            Self::Local51(e) => e.close_inputs(),
            Self::Local53(e) => e.close_inputs(),
            Self::WeightDecay(e) => e.close_inputs(),
            Self::Local52(e) => e.close_inputs(),
            Self::Causal(e) => e.close_inputs(),
            Self::Continuous(e) => e.close_inputs(),
            Self::Lif(e) => e.close_inputs(),
        }
    }
    pub fn advance(&mut self, time: u128, record: bool) -> Result<Vec<Value>> {
        match self {
            Self::Legacy(e) => e.advance(time, record),
            Self::Local(e) => e.advance(time,record),
            Self::Local5(e) => e.advance(time,record),
            Self::Local51(e) => e.advance(time,record),
            Self::Local53(e) => e.advance(time,record),
            Self::WeightDecay(e) => e.advance(time,record),
            Self::Local52(e) => e.advance(time,record),
            Self::Causal(e) => e.advance(time, record),
            Self::Continuous(e) => e.advance(time, record),
            Self::Lif(e) => e.advance(time, record),
        }
    }
}
