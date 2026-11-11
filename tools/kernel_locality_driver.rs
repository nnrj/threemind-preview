//! New synthetic subjects only. No restoration, external state or filesystem writes.
use std::time::Instant;
use serde_json::{json, Value};
use threemind_core::{canonical_hash, kernel::Kernel, probe, Stimulus};
fn main() {
    let args: Vec<String> = std::env::args().collect();
    let configs: Value = serde_json::from_str(&std::fs::read_to_string(&args[1]).unwrap()).unwrap();
    let arm=&args[2];
    let n:u32=args[3].parse().unwrap();
    let seconds:u128=args[4].parse().unwrap();
    let version=if arm.starts_with("5.1") { "5.1" } else if arm.starts_with('4') { "4" } else if arm.starts_with('5') { "5" } else { arm };
    let pattern=args.get(5).map(String::as_str).unwrap_or("dense");
    assert!(n>0 && seconds>0 && (pattern=="dense" || (pattern=="pairs" && n%2==0)));
    let mut engine=Kernel::new(&format!("threemind.continuous-memory/{version}"), configs[arm].clone()).unwrap();
    probe::reset();
    let start=Instant::now();
    let mut advance_s=0.0;
    let mut injection_s=0.0;
    for tick in 0..seconds*20 {
        let t=tick*50_000;
        let first=if pattern=="pairs" { 2*((tick%(n/2) as u128) as u32) } else { 0 };
        let count=if pattern=="pairs" { 2 } else { n };
        let channels=(first..first+count).map(|i|(1000+i, 0.2+0.6*(((i as u128*7+tick*3)%19) as f64)/18.0)).collect();
        let inject_start=Instant::now();
        engine.inject(Stimulus{time_us:t.to_string(),channels,intensity:1.0,bypass_attention:false}).unwrap();
        injection_s+=inject_start.elapsed().as_secs_f64();
        let advance_start=Instant::now();
        engine.advance(t+50_000,false).unwrap();
        advance_s+=advance_start.elapsed().as_secs_f64();
    }
    let total_s=start.elapsed().as_secs_f64();
    let profile=probe::result();
    let state=engine.capture().unwrap();
    let hash=canonical_hash(&serde_json::to_vec(&state).unwrap()).unwrap();
    println!("{}",json!({"arm":arm,"channels":n,"simulation_s":seconds,"pattern":pattern,"advance_s":advance_s,"injection_s":injection_s,"total_s":total_s,"state_hash":hash,"metrics":engine.metrics(),"profile":profile}));
}
