use serde::{
    de::{self, MapAccess, SeqAccess, Visitor},
    Deserialize, Deserializer,
};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::fmt;

struct StrictValue(Value);
impl<'de> Deserialize<'de> for StrictValue {
    fn deserialize<D: Deserializer<'de>>(d: D) -> std::result::Result<Self, D::Error> {
        struct V;
        impl<'de> Visitor<'de> for V {
            type Value = StrictValue;
            fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
                f.write_str("JSON without duplicate fields")
            }
            fn visit_bool<E: de::Error>(self, v: bool) -> std::result::Result<StrictValue, E> {
                Ok(StrictValue(json!(v)))
            }
            fn visit_i64<E: de::Error>(self, v: i64) -> std::result::Result<StrictValue, E> {
                Ok(StrictValue(json!(v)))
            }
            fn visit_u64<E: de::Error>(self, v: u64) -> std::result::Result<StrictValue, E> {
                Ok(StrictValue(json!(v)))
            }
            fn visit_f64<E: de::Error>(self, v: f64) -> std::result::Result<StrictValue, E> {
                if !v.is_finite() {
                    return Err(E::custom("nonfinite number"));
                }
                Ok(StrictValue(json!(v)))
            }
            fn visit_str<E: de::Error>(self, v: &str) -> std::result::Result<StrictValue, E> {
                Ok(StrictValue(json!(v)))
            }
            fn visit_string<E: de::Error>(self, v: String) -> std::result::Result<StrictValue, E> {
                Ok(StrictValue(Value::String(v)))
            }
            fn visit_unit<E: de::Error>(self) -> std::result::Result<StrictValue, E> {
                Ok(StrictValue(Value::Null))
            }
            fn visit_seq<A: SeqAccess<'de>>(
                self,
                mut a: A,
            ) -> std::result::Result<StrictValue, A::Error> {
                let mut values = vec![];
                while let Some(v) = a.next_element::<StrictValue>()? {
                    values.push(v.0);
                }
                Ok(StrictValue(Value::Array(values)))
            }
            fn visit_map<A: MapAccess<'de>>(
                self,
                mut a: A,
            ) -> std::result::Result<StrictValue, A::Error> {
                let mut map = serde_json::Map::new();
                while let Some(key) = a.next_key::<String>()? {
                    if map.contains_key(&key) {
                        return Err(de::Error::custom("duplicate JSON field"));
                    }
                    map.insert(key, a.next_value::<StrictValue>()?.0);
                }
                Ok(StrictValue(Value::Object(map)))
            }
        }
        d.deserialize_any(V)
    }
}
pub fn parse_document(raw: &[u8]) -> crate::Result<Value> {
    serde_json::from_slice::<StrictValue>(raw)
        .map(|v| v.0)
        .map_err(|e| e.to_string())
}

const HEX: &[u8; 16] = b"0123456789abcdef";

fn string(value: &str, hash: &mut Sha256) {
    hash.update(b"\"");
    // Most state field names and timestamps are entirely plain ASCII.
    if value
        .bytes()
        .all(|c| (32..127).contains(&c) && c != b'"' && c != b'\\')
    {
        hash.update(value.as_bytes());
    } else {
        for ch in value.chars() {
            match ch {
                '"' => hash.update(b"\\\""),
                '\\' => hash.update(b"\\\\"),
                '\n' => hash.update(b"\\n"),
                '\r' => hash.update(b"\\r"),
                '\t' => hash.update(b"\\t"),
                '\u{8}' => hash.update(b"\\b"),
                '\u{c}' => hash.update(b"\\f"),
                ' '..='~' => hash.update([ch as u8]),
                _ => {
                    for unit in ch.encode_utf16(&mut [0u16; 2]) {
                        hash.update([
                            b'\\',
                            b'u',
                            HEX[(*unit >> 12) as usize],
                            HEX[(*unit >> 8 & 15) as usize],
                            HEX[(*unit >> 4 & 15) as usize],
                            HEX[(*unit & 15) as usize],
                        ]);
                    }
                }
            }
        }
    }
    hash.update(b"\"");
}

fn feed(value: &Value, hash: &mut Sha256) {
    match value {
        Value::Number(n) if n.is_f64() => {
            hash.update(b"{\"$f64\":\"");
            let bits = n.as_f64().unwrap().to_bits();
            let mut text = [0u8; 16];
            for (i, c) in text.iter_mut().enumerate() {
                *c = HEX[(bits >> ((15 - i) * 4) & 15) as usize];
            }
            hash.update(text);
            hash.update(b"\"}");
        }
        Value::Number(n) => hash.update(n.to_string().as_bytes()),
        Value::String(s) => string(s, hash),
        Value::Bool(true) => hash.update(b"true"),
        Value::Bool(false) => hash.update(b"false"),
        Value::Null => hash.update(b"null"),
        Value::Array(items) => {
            hash.update(b"[");
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    hash.update(b",");
                }
                feed(item, hash);
            }
            hash.update(b"]");
        }
        Value::Object(items) => {
            hash.update(b"{");
            // Sort explicitly even if another crate enables serde's preserve_order feature.
            let mut entries: Vec<_> = items.iter().collect();
            entries.sort_unstable_by(|a, b| a.0.cmp(b.0));
            for (i, (key, item)) in entries.into_iter().enumerate() {
                if i > 0 {
                    hash.update(b",");
                }
                string(key, hash);
                hash.update(b":");
                feed(item, hash);
            }
            hash.update(b"}");
        }
    }
}

/// Stream canonical bytes to SHA-256 without a second object tree or serialized copy.
/// Contract: Python ensure_ascii JSON, sorted keys and exact IEEE-754 float bits.
pub fn canonical_hash(raw: &[u8]) -> crate::Result<String> {
    let value = parse_document(raw)?;
    let mut hash = Sha256::new();
    feed(&value, &mut hash);
    Ok(format!("{:x}", hash.finalize()))
}
