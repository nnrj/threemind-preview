use crate::{parse_time, Config, Result, Stimulus};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Modulation {
    pub source: String,
    pub gain: f64,
    pub budget_multiplier: f64,
    pub competition_enabled: bool,
    pub ttl_us: u64,
}
impl Default for Modulation {
    fn default() -> Self {
        Self {
            source: "external-modulator".into(),
            gain: 1.0,
            budget_multiplier: 1.0,
            competition_enabled: false,
            ttl_us: 30_000_000,
        }
    }
}
impl Modulation {
    pub fn validate(&self) -> Result<()> {
        if self.source.is_empty()
            || self.source.chars().count() > 128
            || self.ttl_us == 0
            || self.ttl_us > 1_000_000_000_000
            || [self.gain, self.budget_multiplier]
                .iter()
                .any(|v| !v.is_finite() || !(0.0..=2.0).contains(v))
        {
            return Err("invalid input modulation".into());
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SavedModulation {
    source: String,
    gain: f64,
    budget_multiplier: f64,
    competition_enabled: bool,
    ttl_us: u64,
    updated_us: String,
    expires_us: String,
}
impl SavedModulation {
    fn payload(&self) -> Modulation {
        Modulation {
            source: self.source.clone(),
            gain: self.gain,
            budget_multiplier: self.budget_multiplier,
            competition_enabled: self.competition_enabled,
            ttl_us: self.ttl_us,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Attention {
    pub schema: String,
    pub since_us: String,
    pub evaluated_frames: String,
    pub considered_channels: String,
    pub passed_channels: String,
    pub suppressed_channels: String,
    pub counter_overflowed: bool,
    pub modulators: Vec<SavedModulation>,
}

#[derive(Serialize)]
pub struct Effective {
    gain: f64,
    budget_multiplier: f64,
    competition_enabled: bool,
    effective_budget: Option<usize>,
    sources: Vec<String>,
}
impl Attention {
    pub fn new(when: u128) -> Self {
        Self {
            schema: "threemind.attention/1".into(),
            since_us: when.to_string(),
            evaluated_frames: "0".into(),
            considered_channels: "0".into(),
            passed_channels: "0".into(),
            suppressed_channels: "0".into(),
            counter_overflowed: false,
            modulators: vec![],
        }
    }
    fn increment(field: &mut String, amount: u128, overflowed: &mut bool) {
        *field = match field.parse::<u128>().unwrap().checked_add(amount) {
            Some(total) => total,
            None => {
                *overflowed = true;
                u128::MAX
            }
        }
        .to_string();
    }
    pub fn update(&mut self, payload: Modulation, when: u128) -> Value {
        self.modulators
            .retain(|m| m.expires_us.parse::<u128>().unwrap() > when);
        let index = self
            .modulators
            .iter()
            .position(|m| m.source == payload.source);
        if index.is_none() && self.modulators.len() >= 64 {
            return json!({"status":"rejected","reason":"active_modulator_limit"});
        }
        let Some(expires) = when.checked_add(payload.ttl_us as u128) else {
            return json!({"status":"rejected","reason":"expiry_out_of_range"});
        };
        let saved = SavedModulation {
            source: payload.source,
            gain: payload.gain,
            budget_multiplier: payload.budget_multiplier,
            competition_enabled: payload.competition_enabled,
            ttl_us: payload.ttl_us,
            updated_us: when.to_string(),
            expires_us: expires.to_string(),
        };
        if let Some(i) = index {
            self.modulators[i] = saved;
        } else {
            self.modulators.push(saved);
        }
        self.modulators
            .sort_unstable_by(|a, b| a.source.cmp(&b.source));
        json!({"status":"applied", "expires_us":expires.to_string()})
    }
    pub fn effective(&self, when: u128, config: &Config) -> Effective {
        let (mut gain, mut budget, mut competition) =
            (1.0_f64, 1.0_f64, config.attention_competition_enabled);
        let mut sources = vec![];
        for item in &self.modulators {
            if when >= item.expires_us.parse::<u128>().unwrap() {
                continue;
            }
            gain *= item.gain;
            budget *= item.budget_multiplier;
            competition |= item.competition_enabled;
            sources.push(item.source.clone());
        }
        gain = gain.min(8.0);
        budget = budget.min(8.0);
        Effective {
            gain,
            budget_multiplier: budget,
            competition_enabled: competition,
            effective_budget: competition
                .then_some(((config.attention_budget as f64 * budget) as usize).min(100000)),
            sources,
        }
    }
    pub fn select(
        &mut self,
        mut stimulus: Stimulus,
        when: u128,
        config: &Config,
    ) -> (Stimulus, Option<Value>) {
        let effective = self.effective(when, config);
        if !effective.competition_enabled && effective.sources.is_empty() {
            return (stimulus, None);
        }
        let count = stimulus.channels.len();
        if effective.gain == 0.0 {
            stimulus.channels.clear();
        } else if let Some(limit) = effective
            .effective_budget
            .filter(|n| !stimulus.bypass_attention && *n < count)
        {
            let mut indices: Vec<usize> = (0..count).collect();
            indices.select_nth_unstable_by(limit, |a, b| {
                stimulus.channels[*b]
                    .1
                    .total_cmp(&stimulus.channels[*a].1)
                    .then(a.cmp(b))
            });
            indices.truncate(limit);
            indices.sort_unstable();
            stimulus.channels = indices.into_iter().map(|i| stimulus.channels[i]).collect();
        }
        stimulus.intensity *= effective.gain;
        let limited = !stimulus.intensity.is_finite();
        if limited {
            stimulus.intensity = f64::MAX;
        }
        let passed = stimulus.channels.len();
        Self::increment(&mut self.evaluated_frames, 1, &mut self.counter_overflowed);
        Self::increment(
            &mut self.considered_channels,
            count as u128,
            &mut self.counter_overflowed,
        );
        Self::increment(
            &mut self.passed_channels,
            passed as u128,
            &mut self.counter_overflowed,
        );
        Self::increment(
            &mut self.suppressed_channels,
            (count - passed) as u128,
            &mut self.counter_overflowed,
        );
        let mut decision = serde_json::to_value(effective).unwrap();
        if stimulus.bypass_attention {
            decision["competition_bypassed"] = json!(true);
        }
        decision.as_object_mut().unwrap().extend(json!({"schema":"threemind.input-selection/1", "scope":"one-timestamped-sensory-frame",
            "raw_channels":count,"passed_channels":passed,"suppressed_channels":count-passed,"intensity_saturated":limited,"effective_stimulus":stimulus}).as_object().unwrap().clone());
        (stimulus, Some(decision))
    }
    pub fn validate(&self, when: u128) -> Result<()> {
        let since = parse_time(&self.since_us)?;
        if self.schema != "threemind.attention/1" || since > when || self.modulators.len() > 64 {
            return Err("invalid attention ledger".into());
        }
        for value in [
            &self.evaluated_frames,
            &self.considered_channels,
            &self.passed_channels,
            &self.suppressed_channels,
        ] {
            parse_time(value)?;
        }
        if !self.counter_overflowed
            && parse_time(&self.passed_channels)?
                .checked_add(parse_time(&self.suppressed_channels)?)
                != Some(parse_time(&self.considered_channels)?)
        {
            return Err("attention counts do not balance".into());
        }
        let mut previous: Option<&str> = None;
        for item in &self.modulators {
            item.payload().validate()?;
            let updated = parse_time(&item.updated_us)?;
            if previous.is_some_and(|p| p >= item.source.as_str())
                || updated < since
                || updated > when
                || updated.checked_add(item.ttl_us as u128) != Some(parse_time(&item.expires_us)?)
            {
                return Err("invalid modulation identity or phase".into());
            }
            previous = Some(&item.source);
        }
        Ok(())
    }
}
