use crate::Result;
use arrow_array::{Array, ArrayRef, Float64Array, Int64Array, RecordBatch, StringArray};
use arrow_ipc::{
    reader::FileReader,
    writer::{FileWriter, IpcWriteOptions},
    CompressionType,
};
use arrow_schema::{DataType, Field, Schema};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    fs,
    io::{Cursor, Read, Write},
    path::Path,
    sync::Arc,
};
use threemind_core::kernel::Kernel;
use zip::{write::SimpleFileOptions, ZipArchive, ZipWriter};

const FORMAT: &str = "threemind.artifact/2";
const MAX_BYTES: usize = 512 * 1024 * 1024;
const NODES: &[&str] = &[
    "id",
    "channel",
    "activation",
    "inhibition",
    "trace",
    "support",
    "stability",
    "direct",
    "associative",
    "touches",
    "last_touch_us",
    "birth_us",
    "local_plasticity",
    "pending_inhibition",
    "generated_inhibition",
];
const EDGES: &[&str] = &[
    "source",
    "target",
    "weight",
    "stability",
    "eligibility",
    "touches",
    "birth_us",
    "last_touch_us",
];

// Local kernels add object-owned clocks without changing historical Arrow tables.
fn split_local_objects(value: &mut Value) {
    if value["dynamics"] != threemind_core::local::KERNEL_ID
        && value["dynamics"] != threemind_core::local::KERNEL5_ID
        && value["dynamics"] != threemind_core::local51::KERNEL_ID
        && value["dynamics"] != threemind_core::local53::KERNEL_ID
        && value["dynamics"] != threemind_core::weight_decay::KERNEL_ID
        && value["dynamics"] != threemind_core::local52::KERNEL_ID {
        return;
    }
    let mut extra = json!({"schema":"threemind.local-object-columns/1"});
    for (name, base) in [("nodes", NODES), ("edges", EDGES)] {
        extra[name] = Value::Array(
            value[name]
                .as_array()
                .unwrap()
                .iter()
                .map(|row| {
                    Value::Object(
                        row.as_object()
                            .unwrap()
                            .iter()
                            .filter(|(k, _)| !base.contains(&k.as_str()))
                            .map(|(k, v)| (k.clone(), v.clone()))
                            .collect(),
                    )
                })
                .collect(),
        );
    }
    value["local_object_columns"] = extra;
}
fn join_local_objects(value: &mut Value) -> Result<()> {
    if value["dynamics"] != threemind_core::local::KERNEL_ID
        && value["dynamics"] != threemind_core::local::KERNEL5_ID
        && value["dynamics"] != threemind_core::local51::KERNEL_ID
        && value["dynamics"] != threemind_core::local53::KERNEL_ID
        && value["dynamics"] != threemind_core::weight_decay::KERNEL_ID
        && value["dynamics"] != threemind_core::local52::KERNEL_ID {
        return Ok(());
    }
    let extra = value
        .as_object_mut()
        .unwrap()
        .remove("local_object_columns")
        .ok_or("missing local object columns")?;
    if extra["schema"] != "threemind.local-object-columns/1"
        || extra.as_object().is_none_or(|m| m.len() != 3)
    {
        return Err("invalid local object columns".into());
    }
    let v52 = value["dynamics"] == threemind_core::local52::KERNEL_ID;
    let v53 = value["dynamics"] == threemind_core::local53::KERNEL_ID
        || value["dynamics"] == threemind_core::weight_decay::KERNEL_ID;
    let v5 = value["dynamics"] == threemind_core::local::KERNEL5_ID
        || value["dynamics"] == threemind_core::local51::KERNEL_ID || v53 || v52;
    for (name, mut expected) in [
        (
            "nodes",
            vec![
                "state_us",
                "half_life",
                "fatigue",
                "salience",
                "isolated_us",
                "region",
                "reserve",
                "energy_us",
                "sleeping",
            ],
        ),
        (
            "edges",
            vec![
                "state_us",
                "half_life",
                "last_pass_us",
                "sleeping",
                "short_term",
                "fast",
                "novelty_deadline_us",
                "novelty_source",
                "novelty_target",
            ],
        ),
    ] {
        if v5 {
            expected.push(if name == "nodes" { "last_emit_us" } else { "completed_period_us" });
        }
        if v53 { expected.push("decay_age"); }
        if v52 { expected.extend(["decay_curve", "decay_contributions"]); }
        let rows = value[name].as_array_mut().ok_or("missing object rows")?;
        let columns = extra[name]
            .as_array()
            .ok_or("invalid local object columns")?;
        if rows.len() != columns.len() {
            return Err("invalid local object row count".into());
        }
        for (row, more) in rows.iter_mut().zip(columns) {
            let fields = more.as_object().ok_or("invalid local object fields")?;
            if fields.len() != expected.len() || expected.iter().any(|k| !fields.contains_key(*k)) {
                return Err("invalid local object fields".into());
            }
            row.as_object_mut().unwrap().extend(fields.clone());
        }
    }
    Ok(())
}

pub fn sha(raw: &[u8]) -> String {
    format!("{:x}", Sha256::digest(raw))
}
pub fn state_hash(state: &Value) -> Result<String> {
    Ok(threemind_core::canonical_hash(&serde_json::to_vec(state)?)?)
}
fn data_type(name: &str) -> DataType {
    if name.ends_with("_us") {
        DataType::Utf8
    } else if ["id", "channel", "source", "target", "touches"].contains(&name) {
        DataType::Int64
    } else {
        DataType::Float64
    }
}
fn arrow_bytes(rows: &[Value], fields: &[&str]) -> Result<Vec<u8>> {
    let schema = Arc::new(Schema::new(
        fields
            .iter()
            .map(|&n| Field::new(n, data_type(n), true))
            .collect::<Vec<_>>(),
    ));
    let options = IpcWriteOptions::default().try_with_compression(Some(CompressionType::ZSTD))?;
    let mut writer = FileWriter::try_new_with_options(Vec::new(), schema.as_ref(), options)?;
    for batch in rows.chunks(65536) {
        let mut columns: Vec<ArrayRef> = Vec::new();
        for &field in fields {
            columns.push(match data_type(field) {
                DataType::Int64 => Arc::new(Int64Array::from(
                    batch
                        .iter()
                        .map(|r| r[field].as_i64().ok_or("counter exceeds model int64 range"))
                        .collect::<std::result::Result<Vec<_>, _>>()?,
                )),
                DataType::Float64 => Arc::new(Float64Array::from(
                    batch
                        .iter()
                        .map(|r| r[field].as_f64().ok_or("missing numeric model field"))
                        .collect::<std::result::Result<Vec<_>, _>>()?,
                )),
                _ => Arc::new(StringArray::from(
                    batch
                        .iter()
                        .map(|r| r[field].as_str().ok_or("missing timestamp"))
                        .collect::<std::result::Result<Vec<_>, _>>()?,
                )),
            });
        }
        writer.write(&RecordBatch::try_new(schema.clone(), columns)?)?;
    }
    writer.finish()?;
    Ok(writer.into_inner()?)
}

/// Check IPC buffer expansion BEFORE Arrow allocates/decompresses the body.
fn preflight(raw: &[u8]) -> Result<usize> {
    if raw.len() < 10 || &raw[raw.len() - 6..] != b"ARROW1" {
        return Err("invalid Arrow file".into());
    }
    let n = u32::from_le_bytes(raw[raw.len() - 10..raw.len() - 6].try_into()?) as usize;
    let start = raw
        .len()
        .checked_sub(10 + n)
        .ok_or("invalid footer length")?;
    let footer =
        arrow_ipc::root_as_footer(&raw[start..raw.len() - 10]).map_err(|e| e.to_string())?;
    let mut expanded = 0usize;
    if footer.dictionaries().is_some_and(|d| !d.is_empty()) {
        return Err("dictionary-encoded models are not supported".into());
    }
    for block in footer.recordBatches().ok_or("missing record batches")? {
        let offset = usize::try_from(block.offset())?;
        let meta_len = usize::try_from(block.metaDataLength())?;
        let prefix = if raw.get(offset..offset + 4) == Some(&[255, 255, 255, 255]) {
            8
        } else {
            4
        };
        let metadata = raw
            .get(offset + prefix..offset + meta_len)
            .ok_or("truncated IPC metadata")?;
        let msg = arrow_ipc::root_as_message(metadata).map_err(|e| e.to_string())?;
        let batch = msg
            .header_as_record_batch()
            .ok_or("unexpected IPC message")?;
        if batch.length() < 0 || batch.length() > 10_000_000 {
            return Err("record batch exceeds row budget".into());
        }
        let body = raw
            .get(offset + meta_len..offset + meta_len + usize::try_from(block.bodyLength())?)
            .ok_or("truncated IPC body")?;
        for buffer in batch.buffers().ok_or("missing IPC buffers")? {
            let a = usize::try_from(buffer.offset())?;
            let len = usize::try_from(buffer.length())?;
            let bytes = body
                .get(a..a.checked_add(len).ok_or("buffer range overflow")?)
                .ok_or("invalid IPC buffer")?;
            let size = if batch.compression().is_some() && len > 0 {
                if bytes.len() < 8 {
                    return Err("invalid compressed IPC buffer".into());
                }
                let declared = i64::from_le_bytes(bytes[..8].try_into()?);
                if declared == -1 {
                    len - 8
                } else {
                    usize::try_from(declared)?
                }
            } else {
                len
            };
            expanded = expanded.checked_add(size).ok_or("IPC size overflow")?;
            if expanded > MAX_BYTES {
                return Err("expanded Arrow data exceeds import budget".into());
            }
        }
    }
    Ok(expanded)
}

fn arrow_rows(raw: &[u8], fields: &[&str]) -> Result<Vec<Value>> {
    let reader = FileReader::try_new(Cursor::new(raw), None)?;
    if reader.schema().fields().len() != fields.len() {
        return Err("unexpected Arrow schema".into());
    }
    for (field, &name) in reader.schema().fields().iter().zip(fields) {
        if field.name() != name || *field.data_type() != data_type(name) {
            return Err("unexpected Arrow column type".into());
        }
    }
    let mut rows = vec![];
    for batch in reader {
        let batch = batch?;
        if batch.columns().iter().any(|a| a.null_count() != 0) {
            return Err("null values are not valid model state".into());
        }
        for row in 0..batch.num_rows() {
            let mut item = serde_json::Map::new();
            for (i, &field) in fields.iter().enumerate() {
                let a = batch.column(i);
                let value = match data_type(field) {
                    DataType::Int64 => {
                        json!(a.as_any().downcast_ref::<Int64Array>().unwrap().value(row))
                    }
                    DataType::Float64 => {
                        let v = a
                            .as_any()
                            .downcast_ref::<Float64Array>()
                            .unwrap()
                            .value(row);
                        if !v.is_finite() {
                            return Err("nonfinite model number".into());
                        }
                        json!(v)
                    }
                    _ => json!(a.as_any().downcast_ref::<StringArray>().unwrap().value(row)),
                };
                item.insert(field.into(), value);
            }
            rows.push(Value::Object(item));
        }
    }
    Ok(rows)
}

pub fn validate_profile(profile: &Value) -> Result<()> {
    let intensity = profile["schema"] == "threemind.runtime-profile/6";
    let policies = intensity || profile["schema"] == "threemind.runtime-profile/5";
    let output_cadence = policies || profile["schema"] == "threemind.runtime-profile/4";
    let telemetry = output_cadence || profile["schema"] == "threemind.runtime-profile/3";
    let media = telemetry || profile["schema"] == "threemind.runtime-profile/2";
    if (!media && profile["schema"] != "threemind.runtime-profile/1")
        || profile.as_object().map(|v| v.len())
            != Some(if policies {
                11
            } else if telemetry {
                10
            } else if media {
                7
            } else {
                3
            })
        || !profile["sensory_seed"]
            .as_u64()
            .is_some_and(|v| v < 1u64 << 32)
    {
        return Err("unsupported runtime profile".into());
    }
    if policies {
        let defaults: Value = serde_json::from_str(include_str!("source-policy-contract.json"))?;
        let rules = defaults
            .as_object()
            .ok_or("invalid source policy contract")?;
        let cfg = profile["source_policies"]
            .as_object()
            .ok_or("missing source policy profile")?;
        if cfg.len() != rules.len()
            || rules
                .keys()
                .any(|key| !cfg.get(key).is_some_and(Value::is_boolean))
        {
            return Err("unknown, missing or invalid source policy profile field".into());
        }
    }
    let cfg = &profile["text_sensor"];
    if cfg.as_object().map(|v| v.len()) != Some(8)
        || cfg["enabled"].as_bool().is_none()
        || ![
            "anonymous-distributed",
            "labeled-observation",
            "literal-character",
        ]
        .contains(&cfg["encoding"].as_str().unwrap_or(""))
        || !["NFKC", "none"].contains(&cfg["normalization"].as_str().unwrap_or(""))
        || !cfg["gain"]
            .as_f64()
            .is_some_and(|v| v.is_finite() && (0.0..=100.0).contains(&v))
    {
        return Err("invalid text sensor profile".into());
    }
    for (field, lower, upper) in [
        ("channel_count", 32, 4096),
        ("frame_characters", 1, 1024),
        ("frame_interval_us", 1, 10_000_000),
        ("max_carrier_characters", 1, 1_000_000),
    ] {
        if !cfg[field]
            .as_u64()
            .is_some_and(|v| (lower..=upper).contains(&v))
        {
            return Err(format!("invalid runtime profile {field}").into());
        }
    }
    if media {
        let contract: Value = serde_json::from_str(if output_cadence {
            include_str!("media-profile-contract.json")
        } else {
            include_str!("media-profile-contract-v3.json")
        })?;
        for (root, rules) in contract.as_object().ok_or("invalid media contract")? {
            let cfg = profile[root].as_object().ok_or("missing media profile")?;
            let rules = rules.as_object().ok_or("invalid media rules")?;
            if cfg.len() != rules.len() {
                return Err("unknown or missing media profile field".into());
            }
            for (field, rule) in rules {
                let value = cfg.get(field).ok_or("missing media field")?;
                let typed = match rule["type"].as_str() {
                    Some("bool") => value.is_boolean(),
                    Some("int") => value.as_u64().is_some(),
                    Some("float") => value.as_f64().is_some_and(f64::is_finite),
                    Some("str") => value.is_string(),
                    _ => false,
                };
                let range = rule["minimum"].as_f64().is_none_or(|lo| {
                    value
                        .as_f64()
                        .is_some_and(|v| v >= lo && v <= rule["maximum"].as_f64().unwrap_or(lo))
                });
                let choice = rule["choices"]
                    .as_array()
                    .is_none_or(|options| options.iter().any(|c| c[0] == *value));
                if !typed || !range || !choice {
                    return Err(format!("invalid {root}.{field}").into());
                }
            }
        }
        let a = &profile["auditory_sensor"];
        let number = |cfg: &Value, key: &str| cfg[key].as_f64().unwrap_or(0.0);
        if output_cadence
            && number(&profile["acoustic_output"], "maximum_frequency")
                <= number(&profile["acoustic_output"], "minimum_frequency")
        {
            return Err("inconsistent acoustic output frequency range".into());
        }
        if number(a, "minimum_frequency") > number(a, "maximum_frequency")
            || number(a, "maximum_frequency") >= number(a, "target_sample_rate") / 2.0
            || (a["encoding"] == "waveform"
                && number(a, "waveform_bins")
                    > (number(a, "target_sample_rate") * number(a, "window_us") / 1e6)
                        .round_ties_even())
        {
            return Err("inconsistent auditory profile".into());
        }
        let v = &profile["visual_sensor"];
        let patches = (number(v, "target_width") / number(v, "patch_width")).ceil()
            * (number(v, "target_height") / number(v, "patch_height")).ceil();
        if (patches - 1.0) * number(v, "patch_interval_us") >= number(v, "frame_interval_us") {
            return Err("overlapping retinal scans".into());
        }
    }
    if telemetry {
        let contract: Value =
            serde_json::from_str(include_str!("telemetry-profile-contract.json"))?;
        fn leaves<'a>(value: &'a Value, path: String, result: &mut BTreeMap<String, &'a Value>) {
            if let Some(object) = value.as_object() {
                if object.is_empty() {
                    result.insert(path, value);
                    return;
                }
                for (key, child) in object {
                    leaves(
                        child,
                        if path.is_empty() {
                            key.clone()
                        } else {
                            format!("{path}.{key}")
                        },
                        result,
                    );
                }
            } else {
                result.insert(path, value);
            }
        }
        for (root, rules) in contract.as_object().ok_or("invalid telemetry contract")? {
            let mut values = BTreeMap::new();
            leaves(&profile[root], String::new(), &mut values);
            let rules = rules.as_object().ok_or("invalid telemetry rules")?;
            if values.len() != rules.len() - usize::from(!intensity) {
                return Err("missing or unknown telemetry field".into());
            }
            for (path, rule) in rules {
                if path == "intensity" && !intensity {
                    continue;
                }
                let value = values.get(path).ok_or("missing telemetry field")?;
                let typed = match rule["type"].as_str() {
                    Some("bool") => value.is_boolean(),
                    Some("int") => value.as_u64().is_some(),
                    Some("float") => value.as_f64().is_some_and(f64::is_finite),
                    _ => false,
                };
                let ranged = rule["minimum"].as_f64().is_none_or(|lo| {
                    value
                        .as_f64()
                        .is_some_and(|n| n >= lo && n <= rule["maximum"].as_f64().unwrap_or(lo))
                });
                if !typed || !ranged {
                    return Err(format!("invalid {root}.{path}").into());
                }
            }
        }
    }
    Ok(())
}

pub fn profile_hash(profile: &Value) -> Result<String> {
    fn ordered(value: &Value) -> Value {
        match value {
            Value::Object(map) => Value::Object(
                map.iter()
                    .map(|(k, v)| (k.clone(), ordered(v)))
                    .collect::<BTreeMap<_, _>>()
                    .into_iter()
                    .collect(),
            ),
            Value::Array(items) => Value::Array(items.iter().map(ordered).collect()),
            _ => value.clone(),
        }
    }
    Ok(sha(&serde_json::to_vec(&ordered(profile))?))
}

fn read_profile(document: &Value) -> Result<Option<Value>> {
    if let Some(profile) = document.get("runtime_profile") {
        validate_profile(profile)?;
        if document["runtime_profile_hash"] != profile_hash(profile)? {
            return Err("runtime profile checksum failed".into());
        }
        return Ok(Some(profile.clone()));
    }
    if document.get("runtime_profile_hash").is_some() {
        return Err("missing runtime profile".into());
    }
    Ok(None)
}

fn attach_profile(document: &mut Value, profile: Option<&Value>) -> Result<()> {
    if let Some(profile) = profile {
        validate_profile(profile)?;
        document["runtime_profile"] = profile.clone();
        document["runtime_profile_hash"] = Value::String(profile_hash(profile)?);
    }
    Ok(())
}

pub fn encode(state: &Value, as_json: bool, profile: Option<&Value>) -> Result<Vec<u8>> {
    let hash = state_hash(state)?;
    let mut value = serde_json::to_value(state)?;
    if as_json {
        let mut document = json!({"format":FORMAT,"state_hash":hash,"state":value});
        attach_profile(&mut document, profile)?;
        return Ok(serde_json::to_vec_pretty(&document)?);
    }
    let mut parts = BTreeMap::new();
    split_local_objects(&mut value);
    for (name, fields) in [("nodes", NODES), ("edges", EDGES)] {
        let rows = value.as_object_mut().unwrap().remove(name).unwrap();
        parts.insert(
            format!("{name}.arrow"),
            arrow_bytes(rows.as_array().unwrap(), fields)?,
        );
    }
    parts.insert("state.json".into(), serde_json::to_vec(&value)?);
    let mut manifest = json!({"format":FORMAT,"state_hash":hash,"files":parts.iter().map(|(n,b)|(n.clone(),json!({"bytes":b.len(),"sha256":sha(b)}))).collect::<serde_json::Map<_,_>>()});
    attach_profile(&mut manifest, profile)?;
    parts.insert("manifest.json".into(), serde_json::to_vec(&manifest)?);
    let mut archive = ZipWriter::new(Cursor::new(Vec::new()));
    for (name, bytes) in parts {
        archive.start_file(
            name,
            SimpleFileOptions::default().compression_method(zip::CompressionMethod::Stored),
        )?;
        archive.write_all(&bytes)?;
    }
    Ok(archive.finish()?.into_inner())
}

pub fn read(path: &Path) -> Result<(Value, Option<Value>)> {
    if fs::metadata(path)?.len() > MAX_BYTES as u64 {
        return Err("model exceeds import budget".into());
    }
    decode(&fs::read(path)?)
}
pub fn decode(raw: &[u8]) -> Result<(Value, Option<Value>)> {
    if raw.len() > MAX_BYTES {
        return Err("model exceeds import budget".into());
    }
    let (value, expected, profile) = if raw.iter().find(|b| !b.is_ascii_whitespace()) == Some(&b'{')
    {
        let doc = threemind_core::parse_document(raw)?;
        if doc["format"] != FORMAT {
            return Err("unsupported model format".into());
        }
        (
            doc["state"].clone(),
            doc["state_hash"]
                .as_str()
                .ok_or("missing state hash")?
                .to_string(),
            read_profile(&doc)?,
        )
    } else {
        let mut archive = ZipArchive::new(Cursor::new(raw))?;
        if archive.len() != 4 {
            return Err("unexpected model members".into());
        }
        let mut parts = BTreeMap::new();
        let mut total = 0u64;
        for i in 0..archive.len() {
            let mut f = archive.by_index(i)?;
            total = total.checked_add(f.size()).ok_or("model size overflow")?;
            if total > MAX_BYTES as u64 {
                return Err("expanded model exceeds import budget".into());
            }
            if !["manifest.json", "state.json", "nodes.arrow", "edges.arrow"].contains(&f.name()) {
                return Err("unknown model member".into());
            }
            let name = f.name().to_owned();
            let mut bytes = Vec::new();
            f.read_to_end(&mut bytes)?;
            if parts.insert(name, bytes).is_some() {
                return Err("duplicate model member".into());
            }
        }
        let doc =
            threemind_core::parse_document(parts.get("manifest.json").ok_or("missing manifest")?)?;
        if doc["format"] != FORMAT || doc["files"].as_object().map(|o| o.len()) != Some(3) {
            return Err("invalid manifest".into());
        }
        for name in ["state.json", "nodes.arrow", "edges.arrow"] {
            let bytes = parts.get(name).ok_or("missing state member")?;
            if doc["files"][name]["bytes"].as_u64() != Some(bytes.len() as u64)
                || doc["files"][name]["sha256"] != sha(bytes)
            {
                return Err("member checksum failed".into());
            }
        }
        let mut value = threemind_core::parse_document(&parts["state.json"])?;
        if preflight(&parts["nodes.arrow"])? + preflight(&parts["edges.arrow"])? > MAX_BYTES {
            return Err("expanded model exceeds import budget".into());
        }
        value["nodes"] = Value::Array(arrow_rows(&parts["nodes.arrow"], NODES)?);
        value["edges"] = Value::Array(arrow_rows(&parts["edges.arrow"], EDGES)?);
        join_local_objects(&mut value)?;
        (
            value,
            doc["state_hash"]
                .as_str()
                .ok_or("missing hash")?
                .to_string(),
            read_profile(&doc)?,
        )
    };
    let state = value;
    if state_hash(&state)? != expected {
        return Err("logical state checksum failed".into());
    }
    Kernel::restore(state.clone())?;
    Ok((state, profile))
}
