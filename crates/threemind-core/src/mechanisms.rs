//! Local candidate primitives. Not selected by causal/9. See the bilingual spec.
use crate::{parse_time, Result};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

fn bounded(value: f64, low: f64, high: f64, name: &str) -> Result<()> {
    if !value.is_finite() || value < low || value > high {
        return Err(format!("{name} must be finite and lie in [{low}, {high}]"));
    }
    Ok(())
}

fn elapsed(now: u128, previous: &str) -> Result<f64> {
    let previous = parse_time(previous)?;
    if now < previous {
        return Err("operator time cannot go backwards".into());
    }
    Ok((now - previous) as f64 / 1e6)
}

pub(crate) fn cascade(dt: f64, source_tau: f64, target_tau: f64) -> f64 {
    let rate = 1.0 / target_tau - 1.0 / source_tau;
    if rate == 0.0 {
        return (dt / target_tau) * (-dt / target_tau).exp();
    }
    if rate > 0.0 {
        (-dt / source_tau).exp() * -(-dt * rate).exp_m1() / (target_tau * rate)
    } else {
        (-dt / target_tau).exp() * (dt * rate).exp_m1() / (target_tau * rate)
    }
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(default, deny_unknown_fields)]
pub struct ShortTermConfig {
    pub utilization: f64,
    pub recovery_tau_s: f64,
    pub active_tau_s: f64,
    pub facilitation_tau_s: f64,
}
impl Default for ShortTermConfig {
    fn default() -> Self {
        Self {
            utilization: 0.5,
            recovery_tau_s: 0.8,
            active_tau_s: 0.003,
            facilitation_tau_s: 0.0,
        }
    }
}
impl ShortTermConfig {
    pub fn validate(&self) -> Result<()> {
        bounded(self.utilization, 0.0, 1.0, "utilization")?;
        bounded(self.recovery_tau_s, 1e-6, 1e9, "recovery_tau_s")?;
        bounded(self.active_tau_s, 1e-6, 1e9, "active_tau_s")?;
        bounded(self.facilitation_tau_s, 0.0, 1e9, "facilitation_tau_s")
    }
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ShortTermState {
    pub available: f64,
    pub active: f64,
    pub utilization: f64,
    pub time_us: String,
}
impl Default for ShortTermState {
    fn default() -> Self {
        Self {
            available: 1.0,
            active: 0.0,
            utilization: 0.0,
            time_us: "0".into(),
        }
    }
}
impl ShortTermState {
    pub fn validate(&self) -> Result<()> {
        bounded(self.available, 0.0, 1.0, "available")?;
        bounded(self.active, 0.0, 1.0, "active")?;
        bounded(self.utilization, 0.0, 1.0, "utilization")?;
        if self.available + self.active > 1.0 + 1e-14 {
            return Err("short-term resources exceed one".into());
        }
        parse_time(&self.time_us)?;
        Ok(())
    }
    pub fn recovered(&self, now: u128, c: &ShortTermConfig) -> Result<Self> {
        self.validate()?;
        c.validate()?;
        self.recovered_validated(now, c)
    }
    /// Internal path for an engine whose configuration and stored state were
    /// checked at construction/restoration. The clock check remains mandatory.
    pub(crate) fn recovered_validated(&self, now: u128, c: &ShortTermConfig) -> Result<Self> {
        let dt = elapsed(now, &self.time_us)?;
        if dt == 0.0 {
            return Ok(self.clone());
        }
        let active = self.active * (-dt / c.active_tau_s).exp();
        let inactive = (1.0 - self.available - self.active).max(0.0);
        let inactive = inactive * (-dt / c.recovery_tau_s).exp()
            + self.active
                * (c.recovery_tau_s / c.active_tau_s)
                * cascade(dt, c.active_tau_s, c.recovery_tau_s);
        let available = (1.0 - active - inactive).clamp(0.0, 1.0);
        let utilization = if c.facilitation_tau_s > 0.0 {
            self.utilization * (-dt / c.facilitation_tau_s).exp()
        } else {
            c.utilization
        };
        Ok(Self {
            available,
            active,
            utilization,
            time_us: now.to_string(),
        })
    }
    pub fn release(&self, now: u128, c: &ShortTermConfig) -> Result<(Self, f64)> {
        let state = self.recovered(now, c)?;
        Ok(Self::release_recovered(state, now, c))
    }
    pub(crate) fn release_validated(&self, now: u128, c: &ShortTermConfig) -> Result<(Self, f64)> {
        let state = self.recovered_validated(now, c)?;
        Ok(Self::release_recovered(state, now, c))
    }
    fn release_recovered(state: Self, now: u128, c: &ShortTermConfig) -> (Self, f64) {
        let u = if c.facilitation_tau_s > 0.0 {
            state.utilization + c.utilization * (1.0 - state.utilization)
        } else {
            c.utilization
        };
        let released = u * state.available;
        (
            Self {
                available: state.available - released,
                active: state.active + released,
                utilization: u,
                time_us: now.to_string(),
            },
            released,
        )
    }
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(default, deny_unknown_fields)]
pub struct FastTraceConfig {
    pub tau_s: f64,
    pub learning_rate: f64,
    pub gain: f64,
}
impl Default for FastTraceConfig {
    fn default() -> Self {
        Self {
            tau_s: 2.0,
            learning_rate: 0.1,
            gain: 0.1,
        }
    }
}
impl FastTraceConfig {
    pub fn validate(&self) -> Result<()> {
        bounded(self.tau_s, 1e-6, 1e9, "fast tau_s")?;
        bounded(self.learning_rate, 0.0, 1.0, "fast learning_rate")?;
        bounded(self.gain, 0.0, 1.0, "fast gain")
    }
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct FastTrace {
    pub value: f64,
    pub time_us: String,
}
impl Default for FastTrace {
    fn default() -> Self {
        Self {
            value: 0.0,
            time_us: "0".into(),
        }
    }
}
impl FastTrace {
    pub fn projected(&self, now: u128, c: &FastTraceConfig) -> Result<f64> {
        bounded(self.value, 0.0, 1.0, "fast trace")?;
        c.validate()?;
        Ok(self.value * (-elapsed(now, &self.time_us)? / c.tau_s).exp())
    }
    pub fn transmit(&self, amount: f64, now: u128, c: &FastTraceConfig) -> Result<Self> {
        bounded(amount, 0.0, 1e12, "transmitted amount")?;
        let mut value = self.projected(now, c)?;
        value += -(-c.learning_rate * amount).exp_m1() * (1.0 - value);
        Ok(Self {
            value,
            time_us: now.to_string(),
        })
    }
    /// Reuse an already validated projection from the same emission attempt.
    pub(crate) fn transmit_projected(
        mut value: f64,
        amount: f64,
        now: u128,
        c: &FastTraceConfig,
    ) -> Result<Self> {
        bounded(amount, 0.0, 1e12, "transmitted amount")?;
        value += -(-c.learning_rate * amount).exp_m1() * (1.0 - value);
        Ok(Self {
            value,
            time_us: now.to_string(),
        })
    }
    pub fn efficacy(&self, slow_weight: f64, now: u128, c: &FastTraceConfig) -> Result<f64> {
        bounded(slow_weight, 0.0, 1.0, "slow weight")?;
        Ok((slow_weight + c.gain * self.projected(now, c)?).min(1.0))
    }
}

pub fn local_attention(
    query: &[f64],
    keys: &[Vec<f64>],
    amounts: &[f64],
    temperature: f64,
    mix: f64,
) -> Result<(f64, Vec<f64>)> {
    bounded(temperature, 1e-6, 1e6, "temperature")?;
    bounded(mix, 0.0, 1.0, "attention mix")?;
    if !(1..=64).contains(&query.len()) || keys.len() != amounts.len() {
        return Err("invalid local attention dimensions".into());
    }
    for &v in query {
        bounded(v, -1.0, 1.0, "query")?;
    }
    for key in keys {
        if key.len() != query.len() {
            return Err("local key dimension differs from query".into());
        }
        for &v in key {
            bounded(v, -1.0, 1.0, "key")?;
        }
    }
    for &amount in amounts {
        bounded(amount, 0.0, 1e12, "arrival")?;
    }
    if amounts.is_empty() {
        return Ok((0.0, vec![]));
    }
    let scores: Vec<f64> = keys
        .iter()
        .map(|key| {
            query.iter().zip(key).map(|(q, k)| q * k).sum::<f64>()
                / (query.len() as f64).sqrt()
                / temperature
        })
        .collect();
    let maximum = scores.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    let weights: Vec<f64> = scores.iter().map(|score| (score - maximum).exp()).collect();
    let total: f64 = weights.iter().sum();
    let factors: Vec<f64> = weights
        .iter()
        .map(|weight| (1.0 - mix) + mix * (weight / total))
        .collect();
    let response = amounts
        .iter()
        .zip(&factors)
        .map(|(amount, factor)| amount * factor)
        .sum();
    Ok((response, factors))
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(default, deny_unknown_fields)]
pub struct MembraneConfig {
    pub rest_mv: f64,
    pub resistance_mohm: f64,
    pub membrane_tau_s: f64,
    pub current_tau_s: f64,
}
impl Default for MembraneConfig {
    fn default() -> Self {
        Self {
            rest_mv: -65.0,
            resistance_mohm: 100.0,
            membrane_tau_s: 0.02,
            current_tau_s: 0.005,
        }
    }
}
impl MembraneConfig {
    pub fn response(&self, voltage_mv: f64, current_na: f64, dt_s: f64) -> Result<(f64, f64)> {
        bounded(voltage_mv, -1e9, 1e9, "voltage_mv")?;
        bounded(current_na, -1e9, 1e9, "current_na")?;
        bounded(dt_s, 0.0, 1e40, "dt_s")?;
        bounded(self.rest_mv, -1e9, 1e9, "rest_mv")?;
        bounded(self.resistance_mohm, 1e-6, 1e9, "resistance_mohm")?;
        bounded(self.membrane_tau_s, 1e-6, 1e9, "membrane_tau_s")?;
        bounded(self.current_tau_s, 1e-6, 1e9, "current_tau_s")?;
        let voltage = self.rest_mv
            + (voltage_mv - self.rest_mv) * (-dt_s / self.membrane_tau_s).exp()
            + self.resistance_mohm
                * current_na
                * cascade(dt_s, self.current_tau_s, self.membrane_tau_s);
        Ok((voltage, current_na * (-dt_s / self.current_tau_s).exp()))
    }
}

/// Small bounded diagnostic interface, using the same primitives as compiled kernels.
#[derive(Deserialize)]
#[serde(tag = "operator", deny_unknown_fields)]
enum Probe {
    #[serde(rename = "threemind.tm-synapse/1")]
    ShortTerm {
        config: ShortTermConfig,
        state: ShortTermState,
        time_us: String,
        release: bool,
    },
    #[serde(rename = "threemind.leaky-fast-trace/1")]
    Fast {
        config: FastTraceConfig,
        state: FastTrace,
        time_us: String,
        amount: f64,
        slow_weight: f64,
    },
    #[serde(rename = "threemind.local-context-attention/1")]
    Attention {
        query: Vec<f64>,
        keys: Vec<Vec<f64>>,
        amounts: Vec<f64>,
        temperature: f64,
        mix: f64,
    },
    #[serde(rename = "threemind.rc-membrane/1")]
    Membrane {
        config: MembraneConfig,
        voltage_mv: f64,
        current_na: f64,
        dt_s: f64,
    },
}

pub fn probe(raw: &[u8]) -> Result<Value> {
    if raw.len() > 1_048_576 {
        return Err("mechanism probe exceeds size limit".into());
    }
    // Shared parser rejects duplicate keys and nonfinite JSON, before typed dispatch.
    let request: Probe =
        serde_json::from_value(crate::parse_document(raw)?).map_err(|e| e.to_string())?;
    match request {
        Probe::ShortTerm {
            config,
            state,
            time_us,
            release,
        } => {
            let time = parse_time(&time_us)?;
            let (next, amount) = if release {
                state.release(time, &config)?
            } else {
                (state.recovered(time, &config)?, 0.0)
            };
            Ok(json!({"state": next, "released": amount}))
        }
        Probe::Fast {
            config,
            state,
            time_us,
            amount,
            slow_weight,
        } => {
            let time = parse_time(&time_us)?;
            let efficacy = state.efficacy(slow_weight, time, &config)?;
            let next = state.transmit(amount, time, &config)?;
            Ok(json!({"state": next, "efficacy_before_transmission": efficacy}))
        }
        Probe::Attention {
            query,
            keys,
            amounts,
            temperature,
            mix,
        } => {
            let (response, coefficients) =
                local_attention(&query, &keys, &amounts, temperature, mix)?;
            Ok(json!({"response": response, "coefficients": coefficients}))
        }
        Probe::Membrane {
            config,
            voltage_mv,
            current_na,
            dt_s,
        } => {
            let (voltage_mv, current_na) = config.response(voltage_mv, current_na, dt_s)?;
            Ok(json!({"voltage_mv": voltage_mv, "current_na": current_na}))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn resources_and_equal_tau_limit() {
        let c = ShortTermConfig {
            recovery_tau_s: 0.01,
            active_tau_s: 0.01,
            ..Default::default()
        };
        let (state, q) = ShortTermState::default().release(0, &c).unwrap();
        assert_eq!(q, 0.5);
        let next = state.recovered(10_000, &c).unwrap();
        assert!((next.active - 0.5 / std::f64::consts::E).abs() < 1e-14);
        assert!((next.available - (1.0 - 1.0 / std::f64::consts::E)).abs() < 1e-14);
        assert_eq!(state.release(0, &c).unwrap().1, 0.25);
    }

    #[test]
    fn long_elapsed_and_membrane_partition() {
        let c = MembraneConfig::default();
        let (v, i) = c.response(-63.0, 0.3, 0.031).unwrap();
        let split = c.response(v, i, 0.069).unwrap();
        let direct = c.response(-63.0, 0.3, 0.1).unwrap();
        assert!((split.0 - direct.0).abs() < 1e-12);
        assert_eq!(c.response(-55.0, 0.1, 1e30).unwrap(), (-65.0, 0.0));
    }

    #[test]
    fn attention_neutral_and_transmission_trace() {
        let (response, factors) =
            local_attention(&[1.0], &[vec![1.0], vec![0.0]], &[0.7, 0.2], 1.0, 0.0).unwrap();
        assert_eq!(response, 0.7 + 0.2);
        assert_eq!(factors, [1.0, 1.0]);
        let c = FastTraceConfig::default();
        let next = FastTrace::default().transmit(0.7, 0, &c).unwrap();
        assert!((next.value - (1.0 - (-0.07f64).exp())).abs() < 1e-14);
    }

    #[test]
    fn validated_internal_paths_preserve_operator_results() {
        for facilitation in [0.0, 0.3] {
            for active_tau in [0.003, 0.8] {
                let c = ShortTermConfig {
                    facilitation_tau_s: facilitation,
                    active_tau_s: active_tau,
                    ..Default::default()
                };
                let state = ShortTermState {
                    available: 0.2,
                    active: 0.4,
                    utilization: 0.6,
                    time_us: "10".into(),
                };
                for t in [10, 73_000, 100_000, 10_000_000_000] {
                    let normal = state.release(t, &c).unwrap();
                    let cached = state.release_validated(t, &c).unwrap();
                    assert_eq!(
                        serde_json::to_value(normal.0).unwrap(),
                        serde_json::to_value(cached.0).unwrap()
                    );
                    assert_eq!(normal.1, cached.1);
                }
            }
        }
        let c = FastTraceConfig::default();
        let state = FastTrace {
            value: 0.4,
            time_us: "0".into(),
        };
        for t in [0, 73_000, 1_000_000, 10_000_000_000] {
            let projected = state.projected(t, &c).unwrap();
            for amount in [0.0, 0.001, 0.7, 1e12] {
                let old = state.transmit(amount, t, &c).unwrap();
                let reused = FastTrace::transmit_projected(projected, amount, t, &c).unwrap();
                assert_eq!(old.value, reused.value);
                assert_eq!(old.time_us, reused.time_us);
            }
        }
        let invalid = ShortTermState {
            available: 2.0,
            ..Default::default()
        };
        assert!(invalid.recovered(0, &ShortTermConfig::default()).is_err());
        assert!(FastTrace::transmit_projected(0.0, -1.0, 0, &c).is_err());
    }
}
