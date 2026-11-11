mod artifact;
mod store;

use clap::{Parser, ValueEnum};
use std::{
    fs::{self, OpenOptions},
    io::{BufRead, BufReader, Write},
    path::PathBuf,
    time::{Duration, Instant},
};
use threemind_core::{kernel::Kernel, parse_time, retention, Stimulus};
type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;
const EMBEDDED_DEFINITION: &[u8] =
    include_bytes!(concat!(env!("OUT_DIR"), "/kernel-definition.json"));

#[derive(Clone, ValueEnum)]
enum Clock {
    Realtime,
    Scaled,
    Unbounded,
}

#[derive(Parser)]
#[command(
    version,
    about = "Independent plastic ThreeMind Runtime; no Python, PostgreSQL or online account required"
)]
struct Args {
    #[arg(
        long,
        help = "Print the compiled constructor definition without creating a model"
    )]
    inspect_definition: bool,
    #[arg(long, conflicts_with = "resume")]
    model: Option<PathBuf>,
    #[arg(long, conflicts_with_all=["model", "resume"])]
    config: Option<PathBuf>,
    #[arg(
        long,
        help = "Scientific kernel identity; restored models retain their identity"
    )]
    kernel: Option<String>,
    #[arg(long, conflicts_with_all=["model", "resume", "config", "kernel"], help = "Validated declarative kernel definition JSON")]
    definition: Option<PathBuf>,
    #[arg(
        long,
        help = "Timestamped anonymous sensory events, one JSON object per line"
    )]
    input: Option<PathBuf>,
    #[arg(long, help = "Explicit external supply JSONL: time_us, amount, source")]
    energy_input: Option<PathBuf>,
    #[arg(long, help = "Explicit timestamped scalar input modulations in JSONL")]
    modulation_input: Option<PathBuf>,
    #[arg(long, default_value = "1000000")]
    until_us: String,
    #[arg(long, value_enum, default_value = "realtime")]
    clock: Clock,
    #[arg(long, default_value_t = 1.0)]
    speed: f64,
    #[arg(long)]
    store: Option<PathBuf>,
    #[arg(long, default_value = "default")]
    instance: String,
    #[arg(long, requires = "store")]
    resume: bool,
    #[arg(
        long,
        help = "Declare the input stream closed after loading its scheduled events"
    )]
    close_inputs: bool,
    #[arg(
        long,
        help = "Explicit final export (.json or .tmind); existing files are never overwritten"
    )]
    export: Option<PathBuf>,
}

fn execute(args: Args) -> Result<()> {
    let embedded = threemind_core::parse_document(EMBEDDED_DEFINITION)?;
    if args.inspect_definition {
        println!("{}", serde_json::to_string_pretty(&embedded)?);
        return Ok(());
    }
    if !embedded.is_null()
        && (args.kernel.is_some() || args.config.is_some() || args.definition.is_some())
    {
        return Err(
            "this runtime has a compiled constructor; creation overrides are not accepted".into(),
        );
    }
    if !args.speed.is_finite() || args.speed <= 0.0 {
        return Err("speed must be positive and finite".into());
    }
    if let Some(path) = &args.export {
        if path.exists() {
            return Err("export path already exists".into());
        }
        if !matches!(
            path.extension().and_then(|x| x.to_str()),
            Some("json" | "tmind")
        ) {
            return Err("use .json or .tmind for export".into());
        }
    }
    let mut store = args
        .store
        .as_ref()
        .map(|p| store::Store::open(p))
        .transpose()?;
    let (mut revision, state, profile) = if args.resume {
        let (r, s, profile) = store.as_mut().unwrap().load(&args.instance)?;
        (r, Some(s), profile)
    } else {
        if let Some(s) = &store {
            if s.exists(&args.instance)? {
                return Err("instance already exists; use --resume or another --instance".into());
            }
        }
        if let Some(path) = &args.model {
            let (state, profile) = artifact::read(path)?;
            (0, Some(state), profile)
        } else {
            (0, None, None)
        }
    };
    let mut engine = if let Some(state) = state {
        let restored = Kernel::restore(state)?;
        if !embedded.is_null() && embedded["kernel_id"].as_str() != Some(restored.identity()) {
            return Err("restored kernel differs from the compiled scientific identity".into());
        }
        if args
            .kernel
            .as_deref()
            .is_some_and(|k| k != restored.identity())
        {
            return Err("kernel identity mismatch; conversion is not restoration".into());
        }
        restored
    } else if !embedded.is_null() {
        Kernel::from_definition(embedded)?
    } else if let Some(path) = args.definition {
        let raw = fs::read(path)?;
        if raw.len() > 1_048_576 {
            return Err("kernel definition exceeds size limit".into());
        }
        Kernel::from_definition(threemind_core::parse_document(&raw)?)?
    } else {
        let config = if let Some(path) = args.config {
            threemind_core::parse_document(&fs::read(path)?)?
        } else {
            serde_json::json!({})
        };
        Kernel::new(
            args.kernel.as_deref().unwrap_or(retention::KERNEL_ID),
            config,
        )?
    };
    let until = parse_time(&args.until_us)?;
    if until < engine.time() {
        return Err("--until-us precedes the restored model time".into());
    }
    let mut saved_hash = if args.resume {
        Some(artifact::state_hash(&engine.capture()?)?)
    } else {
        None
    };
    if let Some(path) = args.input {
        for (i, line) in BufReader::new(fs::File::open(path)?).lines().enumerate() {
            let line = line?;
            if line.trim().is_empty() {
                continue;
            }
            let mut value = threemind_core::parse_document(line.as_bytes())
                .map_err(|e| format!("input line {}: {e}", i + 1))?;
            if value.get("intensity").is_none() {
                value["intensity"] = serde_json::json!(1.0);
            }
            let mut stimulus = serde_json::from_value::<Stimulus>(value)?;
            if let Some(p) = profile.as_ref().filter(|p| {
                p["schema"] == "threemind.runtime-profile/5"
                    || p["schema"] == "threemind.runtime-profile/6"
            }) {
                let policy = &p["source_policies"];
                if policy["manual_enabled"] != true || policy["anonymous_enabled"] != true {
                    return Err(
                        "anonymous input source is disabled by the model's source policy".into(),
                    );
                }
                stimulus.bypass_attention = policy["manual_bypass_attention"] == true
                    || policy["anonymous_bypass_attention"] == true;
            } else {
                stimulus.bypass_attention = false;
            }
            engine.inject(stimulus)?;
        }
    }
    if let Some(path) = args.energy_input {
        for (i, line) in BufReader::new(fs::File::open(path)?).lines().enumerate() {
            let line = line?;
            if line.trim().is_empty() {
                continue;
            }
            let value = threemind_core::parse_document(line.as_bytes())?;
            let record = value.as_object().ok_or("invalid energy input record")?;
            if record.len() != 3
                || !["time_us", "amount", "source"]
                    .iter()
                    .all(|k| record.contains_key(*k))
            {
                return Err(format!("invalid energy input line {}", i + 1).into());
            }
            engine.supply_energy(
                parse_time(
                    value["time_us"]
                        .as_str()
                        .ok_or("energy time must be a decimal string")?,
                )?,
                value["amount"]
                    .as_f64()
                    .ok_or("energy amount must be numeric")?,
                value["source"]
                    .as_str()
                    .ok_or("energy source must be text")?
                    .into(),
            )?;
        }
    }
    if let Some(path) = args.modulation_input {
        for (i, line) in BufReader::new(fs::File::open(path)?).lines().enumerate() {
            let line = line?;
            if line.trim().is_empty() {
                continue;
            }
            let mut value = threemind_core::parse_document(line.as_bytes())
                .map_err(|e| format!("modulation line {}: {e}", i + 1))?;
            let record = value
                .as_object_mut()
                .ok_or("modulation input must be an object")?;
            let time = record
                .remove("time_us")
                .ok_or("modulation input requires time_us")?;
            let time = parse_time(
                time.as_str()
                    .ok_or("modulation time must be a decimal string")?,
            )?;
            engine.modulate_input(time, value)?;
        }
    }
    if args.close_inputs {
        // Already queued external events keep their causal order.
        engine.close_inputs();
    }
    let anchor = Instant::now();
    let start = engine.time();
    let mut saved = engine.time();
    let speed = if matches!(args.clock, Clock::Realtime) {
        1.0
    } else {
        args.speed
    };
    while engine.time() < until && engine.life() != "dead" {
        let empty = engine.is_empty();
        let target = if empty && matches!(args.clock, Clock::Unbounded) {
            until
        } else {
            until.min(engine.time().saturating_add(20_000))
        };
        if !matches!(args.clock, Clock::Unbounded) {
            let due = (target - start) as f64 / 1e6 / speed;
            while anchor.elapsed().as_secs_f64() < due {
                std::thread::sleep(Duration::from_secs_f64(
                    (due - anchor.elapsed().as_secs_f64()).clamp(0.0, 0.05),
                ));
            }
        }
        engine.advance(target, false)?;
        if engine.time() - saved >= 1_000_000 {
            if let Some(s) = &mut store {
                let image = engine.capture()?;
                revision = s.save(&args.instance, &image, revision, profile.as_ref())?;
                saved_hash = Some(artifact::state_hash(&image)?);
            }
            saved = engine.time();
        }
    }
    let state = engine.capture()?;
    if let Some(s) = &mut store {
        if saved_hash.as_deref() != Some(artifact::state_hash(&state)?.as_str()) {
            revision = s.save(&args.instance, &state, revision, profile.as_ref())?;
        }
    }
    if let Some(path) = args.export {
        let bytes = artifact::encode(
            &state,
            path.extension().and_then(|x| x.to_str()) == Some("json"),
            profile.as_ref(),
        )?;
        let mut out = OpenOptions::new().create_new(true).write(true).open(path)?;
        out.write_all(&bytes)?;
        out.sync_all()?;
    }
    println!(
        "{}",
        serde_json::json!({"metrics":engine.metrics(),"state_hash":artifact::state_hash(&state)?,"recovery_revision":revision,"backend":"rust"})
    );
    Ok(())
}

fn main() {
    if let Err(error) = execute(Args::parse()) {
        eprintln!("ThreeMind Runtime: {error}");
        std::process::exit(1);
    }
}
