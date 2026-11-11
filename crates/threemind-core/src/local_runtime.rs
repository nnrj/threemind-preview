//! Runtime-only representations. Stable scientific IDs and wire data remain authoritative.
use crate::{parse_time, Result};
use serde::{Deserialize, Deserializer, Serialize, Serializer};
use std::collections::{BTreeSet, HashMap};
use std::hash::Hash;
use std::ops::Index;

pub(crate) trait RuntimeTimestamp {
    fn read(&self) -> Result<u128>;
}
impl RuntimeTimestamp for str {
    fn read(&self) -> Result<u128> {
        parse_time(self)
    }
}
impl RuntimeTimestamp for String {
    fn read(&self) -> Result<u128> {
        parse_time(self)
    }
}
pub(crate) fn read_time<T: RuntimeTimestamp + ?Sized>(value: &T) -> Result<u128> {
    value.read()
}

/// Numeric local clocks avoid reparsing and allocation during transitions.
/// Width preserves accepted leading-zero wire timestamps on a restore/capture round trip.
#[derive(Clone, Copy, Debug)]
pub(crate) struct Timestamp {
    value: u128,
    width: usize,
}
impl Timestamp {
    pub(crate) fn new(value: u128) -> Self {
        Self { value, width: 0 }
    }
}
impl RuntimeTimestamp for Timestamp {
    fn read(&self) -> Result<u128> {
        Ok(self.value)
    }
}
impl std::fmt::Display for Timestamp {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{:0width$}", self.value, width = self.width)
    }
}
impl From<&str> for Timestamp {
    fn from(value: &str) -> Self {
        Self {
            value: parse_time(value).expect("internal clock literal"),
            width: value.len(),
        }
    }
}
impl Serialize for Timestamp {
    fn serialize<S: Serializer>(&self, serializer: S) -> std::result::Result<S::Ok, S::Error> {
        serializer.collect_str(self)
    }
}
impl<'de> Deserialize<'de> for Timestamp {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> std::result::Result<Self, D::Error> {
        let text = String::deserialize(deserializer)?;
        Ok(Self {
            value: parse_time(&text).map_err(serde::de::Error::custom)?,
            width: text.len(),
        })
    }
}

/// Compact slots are private physical addresses. Messages, adjacency and timers carry keys.
/// Hash lookup is never used for iteration: observations and configuration use sorted IDs.
pub(crate) struct ObjectMap<K, V> {
    slots: Vec<Option<V>>,
    lookup: HashMap<K, usize>,
    ordered: BTreeSet<K>,
    free: Vec<usize>,
}
impl<K: Copy + Eq + Hash + Ord, V> ObjectMap<K, V> {
    pub(crate) fn new() -> Self {
        Self {
            slots: Vec::new(),
            lookup: HashMap::new(),
            ordered: BTreeSet::new(),
            free: Vec::new(),
        }
    }
    pub(crate) fn len(&self) -> usize {
        self.lookup.len()
    }
    pub(crate) fn is_empty(&self) -> bool {
        self.lookup.is_empty()
    }
    pub(crate) fn contains_key(&self, key: &K) -> bool {
        self.lookup.contains_key(key)
    }
    pub(crate) fn get(&self, key: &K) -> Option<&V> {
        self.lookup.get(key).and_then(|&i| self.slots[i].as_ref())
    }
    pub(crate) fn get_mut(&mut self, key: &K) -> Option<&mut V> {
        self.lookup.get(key).and_then(|&i| self.slots[i].as_mut())
    }
    pub(crate) fn insert(&mut self, key: K, value: V) -> Option<V> {
        if let Some(&index) = self.lookup.get(&key) {
            return self.slots[index].replace(value);
        }
        let index = if let Some(index) = self.free.pop() {
            self.slots[index] = Some(value);
            index
        } else {
            self.slots.push(Some(value));
            self.slots.len() - 1
        };
        self.lookup.insert(key, index);
        self.ordered.insert(key);
        None
    }
    pub(crate) fn remove(&mut self, key: &K) -> Option<V> {
        let index = self.lookup.remove(key)?;
        self.ordered.remove(key);
        self.free.push(index);
        self.slots[index].take()
    }
    pub(crate) fn keys(&self) -> std::collections::btree_set::Iter<'_, K> {
        self.ordered.iter()
    }
    pub(crate) fn iter(&self) -> Iter<'_, K, V> {
        Iter {
            keys: self.ordered.iter(),
            store: self,
        }
    }
    pub(crate) fn values(&self) -> impl Iterator<Item = &V> {
        self.iter().map(|(_, value)| value)
    }
    // Only used to clear each node's sleeping flag on an explicit reconfigure; no reduction.
    pub(crate) fn values_mut(&mut self) -> impl Iterator<Item = &mut V> {
        self.slots.iter_mut().filter_map(Option::as_mut)
    }
}
impl<K: Copy + Eq + Hash + Ord, V> Index<&K> for ObjectMap<K, V> {
    type Output = V;
    fn index(&self, key: &K) -> &Self::Output {
        self.get(key).expect("live scientific object ID")
    }
}
pub(crate) struct Iter<'a, K, V> {
    keys: std::collections::btree_set::Iter<'a, K>,
    store: &'a ObjectMap<K, V>,
}
impl<'a, K: Copy + Eq + Hash + Ord, V> Iterator for Iter<'a, K, V> {
    type Item = (&'a K, &'a V);
    fn next(&mut self) -> Option<Self::Item> {
        self.keys
            .next()
            .map(|key| (key, self.store.get(key).unwrap()))
    }
}
impl<'a, K: Copy + Eq + Hash + Ord, V> IntoIterator for &'a ObjectMap<K, V> {
    type Item = (&'a K, &'a V);
    type IntoIter = Iter<'a, K, V>;
    fn into_iter(self) -> Self::IntoIter {
        self.iter()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn clock_keeps_full_range_and_wire_lexeme() {
        for text in [
            "0",
            "000000",
            "00017",
            "340282366920938463463374607431768211455",
        ] {
            let clock: Timestamp = serde_json::from_value(serde_json::json!(text)).unwrap();
            assert_eq!(clock.read().unwrap(), parse_time(text).unwrap());
            assert_eq!(
                serde_json::to_value(clock).unwrap(),
                serde_json::json!(text)
            );
        }
        for text in [
            "",
            "-1",
            "+1",
            "1.0",
            "340282366920938463463374607431768211456",
        ] {
            assert!(serde_json::from_value::<Timestamp>(serde_json::json!(text)).is_err());
        }
    }
    #[test]
    fn recycled_slot_does_not_reassign_stable_identity_or_iteration_order() {
        let mut store = ObjectMap::new();
        store.insert((9, 1), 91);
        store.insert((2, 8), 28);
        assert_eq!(store.remove(&(9, 1)), Some(91));
        store.insert((7, 3), 73);
        assert_eq!(store.get(&(9, 1)), None);
        assert_eq!(store.values().copied().collect::<Vec<_>>(), vec![28, 73]);
        assert_eq!(store.insert((2, 8), 29), Some(28));
        assert_eq!(store[&(7, 3)], 73);
    }
}
