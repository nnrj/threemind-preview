use crate::{parse_time, Config, Result};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Supply {
    pub amount: f64,
    pub source: String,
}
impl Supply {
    pub fn validate(&self) -> Result<()> {
        if !self.amount.is_finite()
            || !(0.0..=1e12).contains(&self.amount)
            || self.source.is_empty()
            || self.source.chars().count() > 128
        {
            return Err("invalid finite external energy supply".into());
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Energy {
    pub schema: String,
    pub since_us: String,
    pub reserve: f64,
    pub initial_total: f64,
    pub offered_total: f64,
    pub supplied_total: f64,
    pub consumed_direct: f64,
    pub consumed_associative: f64,
    pub consumed_inhibition: f64,
    pub consumed_maintenance: f64,
    pub unserved_total: f64,
    pub discarded_total: f64,
    pub last_settlement_us: String,
    pub last_maintenance_deficit: f64,
    pub starved_since_us: Option<String>,
    pub death_us: Option<String>,
    pub counter_overflowed: bool,
}
pub enum Cost {
    Direct,
    Associative,
    Inhibition,
    Maintenance,
}

fn add(value: &mut f64, amount: f64, overflow: &mut bool) {
    *value += amount;
    if !value.is_finite() {
        *value = f64::MAX;
        *overflow = true;
    }
}
impl Energy {
    pub fn initial(config: &Config, when: u128) -> Self {
        let reserve = config.energy_initial_reserve.min(config.energy_capacity);
        Self {
            schema: "threemind.energy/1".into(),
            since_us: when.to_string(),
            reserve,
            initial_total: config.energy_initial_reserve,
            offered_total: 0.0,
            supplied_total: 0.0,
            consumed_direct: 0.0,
            consumed_associative: 0.0,
            consumed_inhibition: 0.0,
            consumed_maintenance: 0.0,
            unserved_total: 0.0,
            discarded_total: config.energy_initial_reserve - reserve,
            last_settlement_us: when.to_string(),
            last_maintenance_deficit: 0.0,
            starved_since_us: None,
            death_us: None,
            counter_overflowed: false,
        }
    }
    pub fn afford(&mut self, requested: f64, cost: f64, kind: Cost) -> f64 {
        if requested <= 0.0 || cost <= 0.0 {
            return requested;
        }
        let accepted = requested.min(self.reserve / cost);
        let consumed = self.reserve.min(accepted * cost);
        self.reserve = (self.reserve - consumed).max(0.0);
        let value = match kind {
            Cost::Direct => &mut self.consumed_direct,
            Cost::Associative => &mut self.consumed_associative,
            Cost::Inhibition => &mut self.consumed_inhibition,
            Cost::Maintenance => &mut self.consumed_maintenance,
        };
        add(value, consumed, &mut self.counter_overflowed);
        add(
            &mut self.unserved_total,
            (requested * cost - consumed).max(0.0),
            &mut self.counter_overflowed,
        );
        accepted
    }
    pub fn supply(&mut self, amount: f64, capacity: f64, enabled: bool) -> Value {
        add(
            &mut self.offered_total,
            amount,
            &mut self.counter_overflowed,
        );
        let accepted = if enabled {
            amount.min((capacity - self.reserve).max(0.0))
        } else {
            0.0
        };
        self.reserve += accepted;
        add(
            &mut self.supplied_total,
            accepted,
            &mut self.counter_overflowed,
        );
        json!({"offered":amount,"accepted":accepted,"reserve":self.reserve,"status":if enabled {"accepted"} else {"disabled"}})
    }
    pub fn resize(&mut self, capacity: f64) {
        let discarded = (self.reserve - capacity).max(0.0);
        self.reserve = self.reserve.min(capacity);
        add(
            &mut self.discarded_total,
            discarded,
            &mut self.counter_overflowed,
        );
    }
    pub fn maintain(
        &mut self,
        when: u128,
        duration_us: u128,
        nodes: usize,
        edges: usize,
        config: &Config,
    ) -> f64 {
        if !(config.energy_simulation_enabled && config.irreversible_energy_death_enabled) {
            return 0.0;
        }
        let required = duration_us as f64 / 1e6
            * (nodes as f64 * config.energy_maintenance_cost_per_node
                + edges as f64 * config.energy_maintenance_cost_per_edge);
        let paid = self.afford(required, 1.0, Cost::Maintenance);
        let deficit = if required > 0.0 {
            (1.0 - paid / required).max(0.0)
        } else {
            0.0
        };
        self.last_settlement_us = when.to_string();
        self.last_maintenance_deficit = deficit;
        duration_us as f64 / 1e6 * deficit
    }
    pub fn validate(&self, when: u128, config: &Config) -> Result<()> {
        if self.schema != "threemind.energy/1" {
            return Err("invalid energy schema".into());
        }
        for value in [
            Some(&self.since_us),
            Some(&self.last_settlement_us),
            self.starved_since_us.as_ref(),
            self.death_us.as_ref(),
        ]
        .into_iter()
        .flatten()
        {
            if parse_time(value)?.to_string() != *value || parse_time(value)? > when {
                return Err("invalid energy timestamp".into());
            }
        }
        if parse_time(&self.last_settlement_us)? < parse_time(&self.since_us)? {
            return Err("invalid energy accounting phase".into());
        }
        for value in [
            self.reserve,
            self.initial_total,
            self.offered_total,
            self.supplied_total,
            self.consumed_direct,
            self.consumed_associative,
            self.consumed_inhibition,
            self.consumed_maintenance,
            self.unserved_total,
            self.discarded_total,
            self.last_maintenance_deficit,
        ] {
            if !value.is_finite() || value < 0.0 {
                return Err("invalid energy accounting value".into());
            }
        }
        if self.reserve > config.energy_capacity || self.last_maintenance_deficit > 1.0 {
            return Err("invalid energy reserve or deficit".into());
        }
        if self.starved_since_us.is_some()
            && !(config.energy_simulation_enabled
                && config.irreversible_energy_death_enabled
                && self.reserve == 0.0)
        {
            return Err("invalid starvation state".into());
        }
        Ok(())
    }
}
