use crate::{artifact, Result};
use rusqlite::{params, Connection, OptionalExtension, TransactionBehavior};
use serde_json::Value;
use std::{path::Path, time::Duration};
use threemind_core::kernel::Kernel;

pub struct Store {
    db: Connection,
}
impl Store {
    pub fn open(path: &Path) -> Result<Self> {
        let db = Connection::open(path)?;
        db.busy_timeout(Duration::from_secs(10))?;
        db.execute_batch("PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS instances(id TEXT PRIMARY KEY,revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS checkpoints(instance TEXT NOT NULL,revision INTEGER NOT NULL,state_hash TEXT NOT NULL,PRIMARY KEY(instance,revision));
            CREATE TABLE IF NOT EXISTS chunks(instance TEXT NOT NULL,revision INTEGER NOT NULL,ordinal INTEGER NOT NULL,body BLOB NOT NULL,PRIMARY KEY(instance,revision,ordinal));
            CREATE TABLE IF NOT EXISTS runtime_profiles(instance TEXT NOT NULL,revision INTEGER NOT NULL,profile_json TEXT NOT NULL,profile_hash TEXT NOT NULL,PRIMARY KEY(instance,revision));
            CREATE TABLE IF NOT EXISTS runtime_contexts(instance TEXT NOT NULL,revision INTEGER NOT NULL,context_json TEXT NOT NULL,context_hash TEXT NOT NULL,PRIMARY KEY(instance,revision));")?;
        Ok(Self { db })
    }
    pub fn exists(&self, id: &str) -> Result<bool> {
        Ok(self
            .db
            .query_row("SELECT 1 FROM instances WHERE id=?", [id], |r| {
                r.get::<_, i64>(0)
            })
            .optional()?
            .is_some())
    }
    pub fn save(
        &mut self,
        id: &str,
        state: &Value,
        expected: i64,
        profile: Option<&serde_json::Value>,
    ) -> Result<i64> {
        let raw = serde_json::to_vec(state)?;
        let hash = artifact::state_hash(state)?;
        let tx = self
            .db
            .transaction_with_behavior(TransactionBehavior::Immediate)?;
        let old = tx
            .query_row("SELECT revision FROM instances WHERE id=?", [id], |r| {
                r.get::<_, i64>(0)
            })
            .optional()?
            .unwrap_or(0);
        if old != expected {
            return Err("instance has another writer or a newer revision".into());
        }
        if tx
            .query_row(
                "SELECT 1 FROM runtime_contexts WHERE instance=? AND revision=?",
                params![id, old],
                |r| r.get::<_, i64>(0),
            )
            .optional()?
            .is_some()
        {
            return Err("this instance has external recovery state; use its owning adapter (e.g. threemind-world)".into());
        }
        let next = old + 1;
        if let Some(profile) = profile {
            artifact::validate_profile(profile)?;
            tx.execute(
                "INSERT INTO runtime_profiles VALUES(?,?,?,?)",
                params![
                    id,
                    next,
                    serde_json::to_string(profile)?,
                    artifact::profile_hash(profile)?
                ],
            )?;
        }
        tx.execute(
            "INSERT INTO checkpoints VALUES(?,?,?)",
            params![id, next, hash],
        )?;
        for (i, block) in raw.chunks(4 * 1024 * 1024).enumerate() {
            tx.execute(
                "INSERT INTO chunks VALUES(?,?,?,?)",
                params![id, next, i as i64, block],
            )?;
        }
        tx.execute("INSERT INTO instances VALUES(?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision",params![id,next])?;
        tx.execute(
            "DELETE FROM chunks WHERE instance=? AND revision<?",
            params![id, next - 7],
        )?;
        tx.execute(
            "DELETE FROM checkpoints WHERE instance=? AND revision<?",
            params![id, next - 7],
        )?;
        tx.execute(
            "DELETE FROM runtime_profiles WHERE instance=? AND revision<?",
            params![id, next - 7],
        )?;
        tx.commit()?;
        Ok(next)
    }
    pub fn load(&mut self, id: &str) -> Result<(i64, Value, Option<serde_json::Value>)> {
        let tx = self.db.transaction()?;
        let revision: i64 =
            tx.query_row("SELECT revision FROM instances WHERE id=?", [id], |r| {
                r.get(0)
            })?;
        let expected: String = tx.query_row(
            "SELECT state_hash FROM checkpoints WHERE instance=? AND revision=?",
            params![id, revision],
            |r| r.get(0),
        )?;
        if tx
            .query_row(
                "SELECT 1 FROM runtime_contexts WHERE instance=? AND revision=?",
                params![id, revision],
                |r| r.get::<_, i64>(0),
            )
            .optional()?
            .is_some()
        {
            return Err("this instance has external recovery state; use its owning adapter (e.g. threemind-world)".into());
        }
        let mut raw = vec![];
        {
            let mut q = tx.prepare(
                "SELECT body FROM chunks WHERE instance=? AND revision=? ORDER BY ordinal",
            )?;
            for block in q.query_map(params![id, revision], |r| r.get::<_, Vec<u8>>(0))? {
                raw.extend(block?);
            }
        }
        let state = threemind_core::parse_document(&raw)?;
        if artifact::state_hash(&state)? != expected {
            return Err("device recovery checksum failed".into());
        }
        Kernel::restore(state.clone())?;
        let saved_profile: Option<(String,String)> = tx.query_row("SELECT profile_json,profile_hash FROM runtime_profiles WHERE instance=? AND revision=?", params![id,revision], |r| Ok((r.get(0)?,r.get(1)?))).optional()?;
        let profile = if let Some((raw, hash)) = saved_profile {
            let value = threemind_core::parse_document(raw.as_bytes())?;
            artifact::validate_profile(&value)?;
            if artifact::profile_hash(&value)? != hash {
                return Err("device runtime profile checksum failed".into());
            }
            Some(value)
        } else {
            None
        };
        tx.commit()?;
        Ok((revision, state, profile))
    }
}
