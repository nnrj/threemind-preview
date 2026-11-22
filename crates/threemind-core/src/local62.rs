//! memory/6.2: single-age decay, clock-based deletion and directed joint transmission.
use crate::local_runtime::{read_time, ObjectMap, RuntimeTimestamp, Timestamp};
const OPTIMIZED: bool = true;
pub const KERNEL_ID: &str = "threemind.continuous-memory/6.2";
pub const STATE_SCHEMA: &str = "threemind.continuous-memory-state/6.2";
pub type LocalEngine62 = LocalEngineImpl<true>;
fn stamp(value: u128) -> Timestamp {
    Timestamp::new(value)
}

/// Serialization remains the /5 payload shape. Only actual signal events avoid JSON at runtime.
#[derive(Clone)]
enum Payload {
    Json(serde_json::Value),
    Signals(Vec<Message>),
}
impl From<serde_json::Value> for Payload {
    fn from(value: serde_json::Value) -> Self {
        Self::Json(value)
    }
}
impl serde::Serialize for Payload {
    fn serialize<S: serde::Serializer>(
        &self,
        serializer: S,
    ) -> std::result::Result<S::Ok, S::Error> {
        match self {
            Self::Json(value) => value.serialize(serializer),
            Self::Signals(messages) => {
                use serde::ser::SerializeMap;
                let mut map = serializer.serialize_map(Some(1))?;
                map.serialize_entry("messages", messages)?;
                map.end()
            }
        }
    }
}
impl<'de> serde::Deserialize<'de> for Payload {
    fn deserialize<D: serde::Deserializer<'de>>(
        deserializer: D,
    ) -> std::result::Result<Self, D::Error> {
        // Validation stays in restore; unknown fields are not dropped by eager conversion.
        Ok(Self::Json(serde_json::Value::deserialize(deserializer)?))
    }
}
fn signal_payload(messages: Vec<Message>) -> Payload {
    Payload::Signals(messages)
}
fn payload_view(value: &Payload) -> std::borrow::Cow<'_, serde_json::Value> {
    match value {
        Payload::Json(value) => std::borrow::Cow::Borrowed(value),
        Payload::Signals(messages) => {
            std::borrow::Cow::Owned(serde_json::json!({"messages": messages}))
        }
    }
}
fn payload_messages(value: &Payload) -> crate::Result<Vec<Message>> {
    match value {
        Payload::Signals(messages) => Ok(messages.clone()),
        Payload::Json(value) => {
            serde_json::from_value(value["messages"].clone()).map_err(|e| e.to_string())
        }
    }
}
include!("local62_transitions.rs");

impl Settings {
    /// Direct inverse of the single-age curve, then of the normalized-age clock.
    /// Extremely distant crossings use a bounded check of this object only.
    fn crossing_seconds(&self, value: f64, age: f64, h: f64, threshold: f64) -> Option<f64> {
        if threshold <= 0.0 { return None; }
        if value <= threshold { return Some(0.0); }
        let ratio = value / threshold;
        let switch = self.f.decay_transition_age;
        let delta = match self.f.decay_curve.as_str() {
            "exponential" => ratio.ln() / std::f64::consts::LN_2,
            "power-law" => (1.0 + age) * (ratio - 1.0),
            "inverse-logarithmic" => {
                let k = 1.0_f64.exp_m1();
                let base = if age < 1e300 { (k * age).ln_1p() } else { age.ln() + k.ln() };
                (1.0 / k + age) * ((ratio - 1.0) * (1.0 + base)).exp_m1()
            }
            "power-exponential" if age >= switch => (1.0 + switch) * ratio.ln(),
            "power-exponential" => {
                let target = (1.0 + age) * ratio - 1.0;
                if target <= switch { target - age } else { switch - age + (1.0 + switch) * ((1.0 + target) / (1.0 + switch)).ln() }
            }
            _ => unreachable!("validated curve"),
        };
        let rate = if self.f.retention_relaxation_enabled { self.r.memory_half_life_decay_rate } else { 0.0 };
        let lower = self.r.memory_half_life_min_s;
        let falling_age = if rate > 0.0 { (h / lower).ln() / rate } else { 0.0 };
        let seconds = if rate > 0.0 && delta <= falling_age { h * -(-rate * delta).exp_m1() / rate }
            else if rate > 0.0 { (h - lower) / rate + (delta - falling_age) * lower }
            else { delta * h };
        Some(seconds.clamp(0.0, 1e12))
    }
    fn log_remaining(&self, age: f64) -> f64 {
        match self.f.decay_curve.as_str() {
            "exponential" => -std::f64::consts::LN_2 * age,
            "power-law" => -age.ln_1p(),
            "inverse-logarithmic" => {
                let k = 1.0_f64.exp_m1();
                let x = if age < 1e300 { (k * age).ln_1p() } else { age.ln() + k.ln() };
                -x.ln_1p()
            }
            "power-exponential" => {
                let switch = self.num("decay_transition_age");
                if age <= switch { -age.ln_1p() } else { -switch.ln_1p() - (age - switch) / (1.0 + switch) }
            }
            _ => unreachable!("validated curve"),
        }
    }
    fn decay_value(&self, value: f64, age: f64, h: f64, dt: f64) -> (f64, f64, f64) {
        let rate = if self.f.retention_relaxation_enabled { self.r.memory_half_life_decay_rate } else { 0.0 };
        let end = self.r.memory_half_life_min_s.max(h - rate * dt);
        let falling = if rate > 0.0 { dt.min((h - self.r.memory_half_life_min_s) / rate) } else { 0.0 };
        let delta = (if falling > 0.0 { (rate * falling / end).ln_1p() / rate } else { 0.0 }) + (dt - falling) / end;
        let next = age + delta;
        let log_ratio = match self.f.decay_curve.as_str() {
            "exponential" => -std::f64::consts::LN_2 * delta,
            "power-law" => -(delta / (1.0 + age)).ln_1p(),
            "power-exponential" if age >= self.num("decay_transition_age") => -delta / (1.0 + self.num("decay_transition_age")),
            _ => self.log_remaining(next) - self.log_remaining(age),
        };
        (value * log_ratio.min(0.0).exp(), next, end)
    }
}

/// Fixed, injective address function over the complete stimulus-code domain.
pub fn node_address(code: u32) -> u64 { u64::from(code) }
