//! Numeric short-term state for 6.1; wire fields and arithmetic match mechanisms.rs.
use crate::local_runtime::{Timestamp, RuntimeTimestamp};
use crate::mechanisms::{cascade, ShortTermConfig, FastTraceConfig};
use crate::Result;
use serde::{Deserialize, Serialize};
fn bounded(value: f64, low: f64, high: f64, name: &str) -> Result<()> {
    if !value.is_finite() || value < low || value > high { return Err(format!("{name} outside valid bounds")); }
    Ok(())
}
fn elapsed(now: u128, previous: &Timestamp) -> Result<f64> {
    let previous = previous.read()?;
    if now < previous { return Err("operator time cannot go backwards".into()); }
    Ok((now - previous) as f64 / 1e6)
}
#[derive(Clone, Copy, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ShortTermState {
    pub available: f64,
    pub active: f64,
    pub utilization: f64,
    pub time_us: Timestamp,
}
impl Default for ShortTermState {
    fn default() -> Self {
        Self {
            available: 1.0,
            active: 0.0,
            utilization: 0.0,
            time_us: Timestamp::new(0),
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
        self.time_us.read()?;
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
            return Ok(*self);
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
            time_us: Timestamp::new(now),
        })
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
                time_us: Timestamp::new(now),
            },
            released,
        )
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct FastTrace {
    pub value: f64,
    pub time_us: Timestamp,
}
impl Default for FastTrace {
    fn default() -> Self {
        Self {
            value: 0.0,
            time_us: Timestamp::new(0),
        }
    }
}
impl FastTrace {
    pub fn projected(&self, now: u128, c: &FastTraceConfig) -> Result<f64> {
        bounded(self.value, 0.0, 1.0, "fast trace")?;
        c.validate()?;
        Ok(self.value * (-elapsed(now, &self.time_us)? / c.tau_s).exp())
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
            time_us: Timestamp::new(now),
        })
    }

}

