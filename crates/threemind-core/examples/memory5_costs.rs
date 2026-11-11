//! Fresh synthetic engineering fixture; never opens research subjects.
use serde_json::{json, Value};
use std::time::Instant;
use threemind_core::{canonical_hash, kernel::Kernel, Stimulus};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let configs: Value = serde_json::from_str(&std::fs::read_to_string(&args[1]).unwrap()).unwrap();
    let arm = &args[2];
    let n: u32 = args[3].parse().unwrap();
    let seconds: u128 = args[4].parse().unwrap();
    let pattern = args.get(5).map(String::as_str).unwrap_or("dense");
    assert!(n > 0 && seconds > 0);
    assert!(["dense", "chain", "burst"].contains(&pattern) || (pattern == "pairs" && n % 2 == 0));
    let row = &configs[arm];
    let mut engine = Kernel::new(row["kernel"].as_str().unwrap(), row["config"].clone()).unwrap();
    let mut advance_s = 0.0;
    let mut injection_s = 0.0;
    for tick in 0..seconds * 20 {
        let t = tick * 50_000;
        let first = match pattern { "pairs" => 2 * ((tick % (n / 2) as u128) as u32), "chain" => (tick % n as u128) as u32, _ => 0 };
        let count = match pattern { "pairs" | "chain" => 2, "burst" if tick % 40 >= 4 => 0, _ => n };
        let channels = (first..first + count).map(|j| {
            let i = j % n;
            (1000 + i, 0.2 + 0.6 * (((i as u128 * 7 + tick * 3) % 19) as f64) / 18.0)
        }).collect();
        let start = Instant::now();
        engine.inject(Stimulus { time_us: t.to_string(), channels, intensity: 1.0, bypass_attention: false }).unwrap();
        injection_s += start.elapsed().as_secs_f64();
        let start = Instant::now();
        engine.advance(t + 50_000, false).unwrap();
        advance_s += start.elapsed().as_secs_f64();
    }
    let start = Instant::now();
    let state = engine.capture().unwrap();
    let capture_s = start.elapsed().as_secs_f64();
    let start = Instant::now();
    let bytes = serde_json::to_vec(&state).unwrap();
    let encoding_s = start.elapsed().as_secs_f64();
    let hash = canonical_hash(&bytes).unwrap();
    let start = Instant::now();
    let metrics = engine.metrics();
    let observation_s = start.elapsed().as_secs_f64();
    // Observation and capture are outside the Core timing and must be read-only.
    assert_eq!(hash, canonical_hash(&serde_json::to_vec(&engine.capture().unwrap()).unwrap()).unwrap());
    // Comparison metadata only; never restore this normalized copy into an engine.
    let mut compared = state.clone();
    if compared["dynamics"] == "threemind.continuous-memory/5.1" {
        assert_eq!(compared["schema"], "threemind.continuous-memory-state/5.1");
        assert_eq!(compared["definition"]["hypothesis_id"], "threemind.hypotheses/continuous-memory51");
        compared["dynamics"] = json!("threemind.continuous-memory/5");
        compared["schema"] = json!("threemind.continuous-memory-state/5");
        compared["definition"]["kernel_id"] = compared["dynamics"].clone();
        compared["definition"]["state_schema"] = compared["schema"].clone();
        compared["definition"]["hypothesis_id"] = json!("threemind.hypotheses/continuous-memory5");
        compared["definition_hash"] = json!(canonical_hash(&serde_json::to_vec(&compared["definition"]).unwrap()).unwrap());
    }
    let comparison_hash = canonical_hash(&serde_json::to_vec(&compared).unwrap()).unwrap();
    println!("{}", json!({"arm": arm, "channels": n, "simulation_s": seconds, "pattern": pattern,
        "advance_s": advance_s, "injection_s": injection_s, "capture_s": capture_s,
        "encoding_s": encoding_s, "observation_s": observation_s, "state_bytes": bytes.len(),
        "state_hash": hash, "comparison_hash": comparison_hash, "metrics": metrics}));
}
