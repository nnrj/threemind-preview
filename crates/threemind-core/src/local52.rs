//! memory/5.2: faithful contribution-history decay and historical /5.2 signaling.
use crate::local_runtime::{read_time, ObjectMap, RuntimeTimestamp, Timestamp};
const OPTIMIZED: bool = true;
pub const KERNEL_ID: &str = "threemind.continuous-memory/5.2";
pub const STATE_SCHEMA: &str = "threemind.continuous-memory-state/5.2";
pub type LocalEngine52 = LocalEngineImpl<true>;
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
include!("local52_transitions.rs");


include!("decay52.rs");
