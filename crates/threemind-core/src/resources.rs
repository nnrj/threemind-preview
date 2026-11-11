use crate::{parse_time, Result};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Resources {
    pub schema: String,
    pub since_us: String,
    pub adaptation_period_us: String,
    pub adaptations_used: u64,
    pub node_capacity_rejections: String,
    pub edge_capacity_rejections: String,
    pub adaptation_budget_skips: String,
    pub propagation_budget_skips: String,
    pub counter_overflowed: bool,
}
impl Default for Resources {
    fn default() -> Self {
        Self {
            schema: "threemind.resources/1".into(),
            since_us: "0".into(),
            adaptation_period_us: "0".into(),
            adaptations_used: 0,
            node_capacity_rejections: "0".into(),
            edge_capacity_rejections: "0".into(),
            adaptation_budget_skips: "0".into(),
            propagation_budget_skips: "0".into(),
            counter_overflowed: false,
        }
    }
}
impl Resources {
    pub fn increment(&mut self, kind: Counter, amount: u128) {
        let value = match kind {
            Counter::Node => &mut self.node_capacity_rejections,
            Counter::Edge => &mut self.edge_capacity_rejections,
            Counter::Adaptation => &mut self.adaptation_budget_skips,
            Counter::Propagation => &mut self.propagation_budget_skips,
        };
        if let Some(next) = parse_time(value).unwrap().checked_add(amount) {
            *value = next.to_string();
        } else {
            *value = u128::MAX.to_string();
            self.counter_overflowed = true;
        }
    }
    pub fn available_adaptations(&self, when: u128, step: u64, limit: u64) -> u64 {
        let used = if parse_time(&self.adaptation_period_us).unwrap()
            == when / step as u128 * step as u128
        {
            self.adaptations_used
        } else {
            0
        };
        limit.saturating_sub(used)
    }
    pub fn use_adaptation(&mut self, when: u128, step: u64) {
        let period = when / step as u128 * step as u128;
        if parse_time(&self.adaptation_period_us).unwrap() != period {
            self.adaptation_period_us = period.to_string();
            self.adaptations_used = 0;
        }
        self.adaptations_used += 1;
    }
    pub fn validate(&self, time: u128, step: u64) -> Result<()> {
        if self.schema != "threemind.resources/1" || self.adaptations_used > (1 << 53) - 1 {
            return Err("invalid resource accounting schema or usage".into());
        }
        for value in [
            &self.since_us,
            &self.adaptation_period_us,
            &self.node_capacity_rejections,
            &self.edge_capacity_rejections,
            &self.adaptation_budget_skips,
            &self.propagation_budget_skips,
        ] {
            if parse_time(value)?.to_string() != *value {
                return Err("noncanonical resource counter".into());
            }
        }
        if parse_time(&self.since_us)? > time
            || parse_time(&self.adaptation_period_us)? > time
            || parse_time(&self.adaptation_period_us)? % step as u128 != 0
        {
            return Err("invalid resource accounting phase".into());
        }
        Ok(())
    }
}
pub enum Counter {
    Node,
    Edge,
    Adaptation,
    Propagation,
}

// Higher score wins; deterministic ascending identities resolve exact ties.
// The bounded set retains only the best K candidates, never an O(N^2) array.
#[derive(Clone, Debug)]
pub struct Candidate {
    pub score: f64,
    pub source: u64,
    pub target: u64,
    pub si: f64,
    pub ti: f64,
}
impl PartialEq for Candidate {
    fn eq(&self, other: &Self) -> bool {
        self.cmp(other).is_eq()
    }
}
impl Eq for Candidate {}
impl PartialOrd for Candidate {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}
impl Ord for Candidate {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        other
            .score
            .total_cmp(&self.score)
            .then_with(|| self.source.cmp(&other.source))
            .then_with(|| self.target.cmp(&other.target))
    }
}
