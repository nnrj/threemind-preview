//! Historical memory/4 and /5 representations and routes.
use crate::local_runtime::{read_time, RuntimeTimestamp};
type Timestamp = String;
type ObjectMap<K, V> = std::collections::BTreeMap<K, V>;
type Payload = serde_json::Value;
const OPTIMIZED: bool = false;
pub type LocalEngine = LocalEngineImpl<false>;
pub type LocalEngine5 = LocalEngineImpl<true>;
pub const KERNEL_ID: &str = "threemind.continuous-memory/4";
pub const STATE_SCHEMA: &str = "threemind.continuous-memory-state/4.1";
fn stamp(value: u128) -> Timestamp {
    value.to_string()
}
fn signal_payload(messages: Vec<Message>) -> Payload {
    serde_json::json!({"messages": messages})
}
fn payload_view(value: &Payload) -> std::borrow::Cow<'_, serde_json::Value> {
    std::borrow::Cow::Borrowed(value)
}
fn payload_messages(value: &Payload) -> crate::Result<Vec<Message>> {
    serde_json::from_value(value["messages"].clone()).map_err(|e| e.to_string())
}
include!("local_shared.rs");
#[cfg(test)]
mod historical_tests {
    use super::*;

    #[test]
    fn version_five_never_learns_between_internal_packet_receivers() {
        let config = json!({"context_enabled":false,"reception_mode":"unified"});
        let mut old = LocalEngine::new(config.clone()).unwrap();
        let mut new = LocalEngine5::new(config).unwrap();
        for channel in 0..3 {
            old.birth(channel);
            new.birth(channel);
        }
        let packet = (
            0,
            vec![(0, 1, 0.8, vec![0.0; 4]), (0, 2, 0.8, vec![0.0; 4])],
            false,
            1.0,
        );
        old.receive(vec![packet.clone()], &BTreeMap::new()).unwrap();
        new.receive(vec![packet], &BTreeMap::new()).unwrap();
        assert_eq!(old.edges.len(), 2);
        assert!(new.edges.is_empty());
        assert!(new.nodes[&1].activation > 0.0);
        assert!(new.nodes[&2].activation > 0.0);
    }

    #[test]
    fn version_five_keeps_external_packets_separate_and_restores_current_state() {
        let mut engine = LocalEngine5::new(json!({})).unwrap();
        assert!(engine.s.choice("arrival_mode", "sequential"));
        assert!(engine.s.choice("reception_mode", "legacy-source"));
        for channel in [1, 2] {
            engine
                .inject(Stimulus {
                    time_us: "0".into(),
                    channels: vec![(channel, 0.8)],
                    intensity: 1.0,
                    bypass_attention: false,
                })
                .unwrap();
        }
        engine.advance(0, false).unwrap();
        assert!(engine.edges.is_empty());
        let captured = engine.capture().unwrap();
        engine.metrics();
        engine.graph(None);
        engine.observation_nodes();
        assert_eq!(captured, engine.capture().unwrap());
        assert!(LocalEngine::restore(captured.clone()).is_err());
        let mut restored = LocalEngine5::restore(captured).unwrap();
        engine.advance(500_000, false).unwrap();
        restored.advance(171_337, false).unwrap();
        restored.advance(500_000, false).unwrap();
        assert_eq!(engine.capture().unwrap(), restored.capture().unwrap());
    }

    #[test]
    fn version_five_legacy_birth_on_boundary_gets_current_discrete_update() {
        let mut engine = LocalEngine5::new(
            json!({"consolidation_mode":"legacy-stability", "propagation_rate":0.0}),
        )
        .unwrap();
        engine
            .inject(Stimulus {
                time_us: "100000".into(),
                channels: vec![(1, 0.8), (2, 0.8)],
                intensity: 1.0,
                bypass_attention: false,
            })
            .unwrap();
        engine.advance(100_000, false).unwrap();
        assert_eq!(engine.edges.len(), 2);
        for edge in engine.edges.values() {
            assert_eq!(edge.completed_period_us.as_deref(), Some("100000"));
            assert_eq!(engine.deadlines[&(2, edge.source, edge.target)], 200_000);
        }
    }

    #[test]
    fn version_five_keeps_subfloor_inputs_until_time_advances() {
        let mut engine =
            LocalEngine5::new(json!({"activation_floor":0.004,"direct_gain":0.9})).unwrap();
        for _ in 0..2 {
            engine
                .inject(Stimulus {
                    time_us: "0".into(),
                    channels: vec![(1, 0.003)],
                    intensity: 1.0,
                    bypass_attention: false,
                })
                .unwrap();
        }
        engine.advance(0, false).unwrap();
        assert!((engine.nodes[&0].activation - 0.0054).abs() < 1e-15);
        assert_eq!(engine.nodes[&0].touches, 2);
        assert!(engine.metrics()["activation"].as_f64().unwrap() > 0.004);
    }

    #[test]
    fn version_five_current_time_input_keeps_completed_phase() {
        let config = json!({"inhibition":false,"context_enabled":false,"stp_enabled":false,"fast_enabled":false,
            "propagation_rate":10.0,"forgetting_rate":0.0,"eligibility_decay_enabled":false,"stability_decay_enabled":false});
        let mut old = crate::continuous::ContinuousEngine::new_novelty(config.clone()).unwrap();
        let mut config = config;
        config["consolidation_mode"] = json!("legacy-stability");
        config["node_retention_mode"] = json!("manual");
        config["strong_fatigue_enabled"] = json!(false);
        let mut new = LocalEngine5::new(config).unwrap();
        for (time, channels) in [
            (0, vec![(1, 1.0), (2, 1.0)]),
            (100_000, vec![(1, 0.1), (2, 0.1)]),
        ] {
            let stimulus = Stimulus {
                time_us: time.to_string(),
                channels,
                intensity: 1.0,
                bypass_attention: false,
            };
            old.inject(stimulus.clone()).unwrap();
            new.inject(stimulus).unwrap();
            old.advance(100_000, false).unwrap();
            new.advance(100_000, false).unwrap();
        }
        let state = old.capture().unwrap();
        for (old, new) in state["edges"]
            .as_array()
            .unwrap()
            .iter()
            .zip(new.edges.values())
        {
            assert!((old["weight"].as_f64().unwrap() - new.weight).abs() < 1e-12);
        }
        new = LocalEngine5::restore(new.capture().unwrap()).unwrap();
        new.inject(Stimulus {
            time_us: "100000".into(),
            channels: vec![(1, 0.1), (3, 0.1)],
            intensity: 1.0,
            bypass_attention: false,
        })
        .unwrap();
        new.advance(100_000, false).unwrap();
        assert!(new
            .edges
            .values()
            .filter(|e| e.target == 2 || e.source == 2)
            .all(|e| e.novelty_deadline_us.as_deref() == Some("210000")));
        assert_eq!(new.deadlines[&(0, 2, 0)], 200_000);
    }

    #[test]
    fn version_five_disabled_learning_does_not_defer_decay() {
        let mut engine = LocalEngine5::new(json!({"propagation_rate":0.0})).unwrap();
        engine
            .inject(Stimulus {
                time_us: "0".into(),
                channels: vec![(1, 0.8), (2, 0.8)],
                intensity: 1.0,
                bypass_attention: false,
            })
            .unwrap();
        engine.advance(100_000, false).unwrap();
        let mut config = engine.config();
        config["plasticity"] = json!(false);
        engine.reconfigure(config.clone()).unwrap();
        let before = engine.edges.values().next().unwrap().clone();
        engine.advance(1_000_000, false).unwrap();
        config["plasticity"] = json!(true);
        engine.reconfigure(config).unwrap();
        let after = engine.edges.values().next().unwrap();
        assert_eq!(before.eligibility, after.eligibility);
        assert_eq!(before.stability, after.stability);
        assert_eq!(after.completed_period_us.as_deref(), Some("1000000"));
    }

    #[test]
    fn local_state_restores_with_zero_prune_floor_and_no_global_tick() {
        let mut engine = LocalEngine::new(
            json!({"prune_weight":0.0,"quiescence_death_us":1_000_000_000_000u64}),
        )
        .unwrap();
        engine
            .inject(Stimulus {
                time_us: "0".into(),
                channels: vec![(1, 0.8), (2, 0.8)],
                intensity: 1.0,
                bypass_attention: false,
            })
            .unwrap();
        engine.advance(611337, false).unwrap();
        let mut restored = LocalEngine::restore(engine.capture().unwrap()).unwrap();
        engine.advance(2000000, false).unwrap();
        restored.advance(2000000, false).unwrap();
        assert_eq!(engine.capture().unwrap(), restored.capture().unwrap());
        assert_eq!(engine.audit["scan_visits"], 0);
    }
}
