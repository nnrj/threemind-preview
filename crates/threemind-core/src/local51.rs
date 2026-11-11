//! memory/5.1: the /5 scientific transitions with compact runtime representations.
use crate::local_runtime::{read_time, ObjectMap, RuntimeTimestamp, Timestamp};
const OPTIMIZED: bool = true;
pub const KERNEL_ID: &str = "threemind.continuous-memory/5.1";
pub const STATE_SCHEMA: &str = "threemind.continuous-memory-state/5.1";
pub type LocalEngine51 = LocalEngineImpl<true>;
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
include!("local_shared.rs");

#[cfg(test)]
mod equivalence_tests {
    use super::*;

    // Only the three declared version identity strings and their derived hash differ.
    fn normalize(mut value: Value) -> Value {
        fn identities(value: &mut Value) {
            for (key, new, old) in [
                ("schema", STATE_SCHEMA, STATE5_SCHEMA),
                ("state_schema", STATE_SCHEMA, STATE5_SCHEMA),
                ("dynamics", KERNEL_ID, KERNEL5_ID),
                ("kernel_id", KERNEL_ID, KERNEL5_ID),
                (
                    "hypothesis_id",
                    "threemind.hypotheses/continuous-memory51",
                    "threemind.hypotheses/continuous-memory5",
                ),
            ] {
                if value.get(key).is_some_and(|v| v == new) {
                    value[key] = json!(old);
                }
            }
        }
        identities(&mut value);
        if let Some(definition) = value.get_mut("definition") {
            identities(definition);
        }
        if value.get("definition_hash").is_some() {
            value["definition_hash"] =
                json!(canonical_hash(&serde_json::to_vec(&value["definition"]).unwrap()).unwrap());
        }
        value
    }
    fn compare(old: &crate::local::LocalEngine5, new: &LocalEngine51) {
        let before = new.capture().unwrap();
        assert_eq!(old.capture().unwrap(), normalize(before.clone()));
        assert_eq!(old.metrics(), normalize(new.metrics()));
        assert_eq!(old.graph(None), normalize(new.graph(None)));
        assert_eq!(old.activations(), new.activations());
        assert_eq!(before, new.capture().unwrap(), "observation mutated state");
    }
    fn stimulus(time: u128, channels: Vec<(u32, f64)>, intensity: f64) -> Stimulus {
        Stimulus {
            time_us: time.to_string(),
            channels,
            intensity,
            bypass_attention: false,
        }
    }

    #[test]
    fn unsupported_rule_identity_cannot_be_constructed() {
        assert!(LocalEngineImpl::<false>::new(json!({})).is_err());
    }

    #[test]
    fn restored_noncanonical_clock_lexemes_remain_intact() {
        let mut old = crate::local::LocalEngine5::new(json!({})).unwrap();
        let mut new = LocalEngine51::new(json!({})).unwrap();
        let s = stimulus(0, vec![(1, 0.8), (2, 0.7)], 1.0);
        old.inject(s.clone()).unwrap();
        new.inject(s).unwrap();
        old.advance(100_000, false).unwrap();
        new.advance(100_000, false).unwrap();
        fn pad(mut state: Value) -> Value {
            for node in state["nodes"].as_array_mut().unwrap() {
                for key in [
                    "birth_us",
                    "state_us",
                    "last_touch_us",
                    "last_emit_us",
                    "energy_us",
                ] {
                    node[key] = json!(format!("000{}", node[key].as_str().unwrap()));
                }
            }
            state
        }
        old = crate::local::LocalEngine5::restore(pad(old.capture().unwrap())).unwrap();
        new = LocalEngine51::restore(pad(new.capture().unwrap())).unwrap();
        compare(&old, &new);
        assert_eq!(
            old.advance(500_000, true).unwrap(),
            new.advance(500_000, true).unwrap()
        );
        compare(&old, &new);
    }

    #[test]
    fn scientific_state_events_and_restore_match_at_each_input_and_causal_boundary() {
        for config in [
            json!({}),
            json!({"consolidation_mode":"legacy-stability", "node_retention_mode":"manual"}),
            json!({"arrival_mode":"coincident", "reception_mode":"unified", "propagation_phase":"asynchronous"}),
            json!({"propagation_mode":"scan-control", "memory_growth_formula":"linear-saturating"}),
            json!({"plasticity":false, "inhibition":false, "context_enabled":false, "stp_enabled":false, "fast_enabled":false}),
            json!({"eligibility_decay_enabled":false, "stability_decay_enabled":false, "support_decay_enabled":false}),
            json!({"spatial_embedding":true, "neighborhood_enabled":true}),
            json!({"dormant_traces_enabled":true, "revival_enabled":true, "node_wake_threshold":0.5, "edge_wake_threshold":0.5}),
        ] {
            let mut old = crate::local::LocalEngine5::new(config.clone()).unwrap();
            let mut new = LocalEngine51::new(config).unwrap();
            for (i, time) in [0, 0, 50_000, 100_000, 100_000, 110_000, 200_000, 257_113]
                .into_iter()
                .enumerate()
            {
                let s = stimulus(
                    time,
                    vec![(1, 0.8), (2 + (i % 3) as u32, 0.6), (7, 0.003)],
                    if i == 4 { 3.0 } else { 1.0 },
                );
                assert_eq!(old.inject(s.clone()).unwrap(), new.inject(s).unwrap());
                compare(&old, &new);
                assert_eq!(
                    old.advance(time, true).unwrap(),
                    new.advance(time, true).unwrap()
                );
                compare(&old, &new);
                if i % 2 == 1 {
                    let saved = new.capture().unwrap();
                    assert!(crate::local::LocalEngine5::restore(saved.clone()).is_err());
                    assert!(LocalEngine51::restore(old.capture().unwrap()).is_err());
                    new = LocalEngine51::restore(saved).unwrap();
                    old = crate::local::LocalEngine5::restore(old.capture().unwrap()).unwrap();
                    compare(&old, &new);
                }
            }
            for time in [300_000, 310_000, 411_337, 1_000_000] {
                assert_eq!(
                    old.advance(time, true).unwrap(),
                    new.advance(time, true).unwrap()
                );
                compare(&old, &new);
            }
        }
    }

    #[test]
    fn deletion_reuse_pending_messages_and_reconfiguration_keep_original_behavior() {
        let mut old = crate::local::LocalEngine5::new(json!({})).unwrap();
        let mut new = LocalEngine51::new(json!({})).unwrap();
        for engine in [&mut old] {
            engine
                .inject(stimulus(0, vec![(1, 0.8), (2, 0.7), (3, 0.9)], 1.0))
                .unwrap();
        }
        new.inject(stimulus(0, vec![(1, 0.8), (2, 0.7), (3, 0.9)], 1.0))
            .unwrap();
        old.advance(100_000, false).unwrap();
        new.advance(100_000, false).unwrap();
        old.intervene_action(vec![1], vec![], "delete_nodes")
            .unwrap();
        new.intervene_action(vec![1], vec![], "delete_nodes")
            .unwrap();
        compare(&old, &new);
        let s = stimulus(100_000, vec![(1, 0.7), (44, 0.9)], 1.0);
        old.inject(s.clone()).unwrap();
        new.inject(s).unwrap();
        assert_eq!(
            old.advance(110_000, true).unwrap(),
            new.advance(110_000, true).unwrap()
        );
        compare(&old, &new);
        for (time, learning, tau) in [
            (200_000, false, 7.0),
            (300_000, true, 31.0),
            (700_000, true, 2.0),
        ] {
            old.advance(time, false).unwrap();
            new.advance(time, false).unwrap();
            let mut config = old.config();
            config["plasticity"] = json!(learning);
            config["eligibility_tau"] = json!(tau);
            old.reconfigure(config.clone()).unwrap();
            new.reconfigure(config).unwrap();
            compare(&old, &new);
            new = LocalEngine51::restore(new.capture().unwrap()).unwrap();
        }
        assert_eq!(
            old.advance(1_000_000, true).unwrap(),
            new.advance(1_000_000, true).unwrap()
        );
        compare(&old, &new);
    }

    #[test]
    fn local_energy_and_record_modes_do_not_change_the_scientific_trajectory() {
        for energy_model in ["local-field", "global-ledger"] {
            let config = json!({"energy_simulation_enabled":true,"energy_starvation_damage_enabled":true,"energy_model":energy_model});
            let mut old = crate::local::LocalEngine5::new(config.clone()).unwrap();
            let mut new = LocalEngine51::new(config).unwrap();
            old.supply_energy(10_000, 0.4, "test".into()).unwrap();
            new.supply_energy(10_000, 0.4, "test".into()).unwrap();
            let s = stimulus(0, vec![(1, 0.9), (2, 0.8)], 1.0);
            old.inject(s.clone()).unwrap();
            new.inject(s).unwrap();
            for time in [0, 10_000, 100_000, 111_337, 500_000] {
                old.advance(time, false).unwrap();
                new.advance(time, true).unwrap();
                compare(&old, &new);
            }
        }
    }
}
