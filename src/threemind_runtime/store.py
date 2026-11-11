from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from threemind_core import StateImage
from threemind_kernels.registry import state_kernel

from .profile import profile_hash, validate_profile


class SQLiteStore:
    """Optional device recovery; deliberately not a second Lab database backend."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS instances (id TEXT PRIMARY KEY, revision INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS checkpoints (
                    instance TEXT NOT NULL, revision INTEGER NOT NULL, state_hash TEXT NOT NULL,
                    PRIMARY KEY (instance,revision));
                CREATE TABLE IF NOT EXISTS chunks (
                    instance TEXT NOT NULL, revision INTEGER NOT NULL, ordinal INTEGER NOT NULL, body BLOB NOT NULL,
                    PRIMARY KEY (instance,revision,ordinal));
                CREATE TABLE IF NOT EXISTS runtime_profiles (
                    instance TEXT NOT NULL, revision INTEGER NOT NULL, profile_json TEXT NOT NULL, profile_hash TEXT NOT NULL,
                    PRIMARY KEY (instance,revision));
                CREATE TABLE IF NOT EXISTS runtime_contexts (
                    instance TEXT NOT NULL, revision INTEGER NOT NULL, context_json TEXT NOT NULL, context_hash TEXT NOT NULL,
                    PRIMARY KEY (instance,revision));
            """)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA synchronous=FULL")
        return db

    def save(
        self, instance: str, image: StateImage, *, expected_revision: int | None = None, profile=None, context=None
    ) -> int:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT revision FROM instances WHERE id=?", (instance,)).fetchone()
            previous = row[0] if row else 0
            if expected_revision is not None and previous != expected_revision:
                raise ValueError("instance has another writer or a newer revision")
            revision = previous + 1
            if (
                context is None
                and db.execute(
                    "SELECT 1 FROM runtime_contexts WHERE instance=? AND revision=?", (instance, previous)
                ).fetchone()
            ):
                raise ValueError(
                    "this instance has external recovery state; its owning adapter must save it atomically"
                )
            if context is not None:
                if not isinstance(context, dict):
                    raise ValueError("runtime context must be an object")
                encoded = json.dumps(context, sort_keys=True, separators=(",", ":"), allow_nan=False)
                db.execute(
                    "INSERT INTO runtime_contexts VALUES(?,?,?,?)", (instance, revision, encoded, profile_hash(context))
                )
            if profile is None and previous:
                saved_profile = db.execute(
                    "SELECT profile_json,profile_hash FROM runtime_profiles WHERE instance=? AND revision=?",
                    (instance, previous),
                ).fetchone()
                profile = json.loads(saved_profile[0]) if saved_profile else None
                if saved_profile and profile_hash(profile) != saved_profile[1]:
                    raise ValueError("device runtime profile checksum failed")
            profile = validate_profile(profile)
            if profile is not None:
                db.execute(
                    "INSERT INTO runtime_profiles VALUES(?,?,?,?)",
                    (
                        instance,
                        revision,
                        json.dumps(profile, sort_keys=True, separators=(",", ":")),
                        profile_hash(profile),
                    ),
                )
            db.execute("INSERT INTO checkpoints VALUES (?,?,?)", (instance, revision, image.digest))
            block = 4 * 1024 * 1024
            db.executemany(
                "INSERT INTO chunks VALUES (?,?,?,?)",
                (
                    (instance, revision, i // block, image.payload[i : i + block])
                    for i in range(0, len(image.payload), block)
                ),
            )
            db.execute(
                "INSERT INTO instances VALUES (?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision",
                (instance, revision),
            )
            # Device recovery has a bounded window; this is not research-history retention.
            db.execute("DELETE FROM chunks WHERE instance=? AND revision<?", (instance, revision - 7))
            db.execute("DELETE FROM checkpoints WHERE instance=? AND revision<?", (instance, revision - 7))
            db.execute("DELETE FROM runtime_profiles WHERE instance=? AND revision<?", (instance, revision - 7))
            db.execute("DELETE FROM runtime_contexts WHERE instance=? AND revision<?", (instance, revision - 7))
            return revision

    def load(self, instance: str, *, with_profile=False, with_context=False):
        with self._connect() as db:
            db.execute("BEGIN")
            row = db.execute("SELECT revision FROM instances WHERE id=?", (instance,)).fetchone()
            if row is None:
                raise KeyError(instance)
            revision = row[0]
            parts = db.execute(
                "SELECT body FROM chunks WHERE instance=? AND revision=? ORDER BY ordinal", (instance, revision)
            ).fetchall()
            expected = db.execute(
                "SELECT state_hash FROM checkpoints WHERE instance=? AND revision=?", (instance, revision)
            ).fetchone()[0]
            image = StateImage(b"".join(p[0] for p in parts))
            if image.digest != expected:
                raise ValueError("device recovery checksum failed")
            state_kernel(image).create(state=image, backend="reference")
            saved = db.execute(
                "SELECT profile_json,profile_hash FROM runtime_profiles WHERE instance=? AND revision=?",
                (instance, revision),
            ).fetchone()
            profile = json.loads(saved[0]) if saved else None
            if saved and profile_hash(profile) != saved[1]:
                raise ValueError("device runtime profile checksum failed")
            profile = validate_profile(profile)
            if with_context:
                saved = db.execute(
                    "SELECT context_json,context_hash FROM runtime_contexts WHERE instance=? AND revision=?",
                    (instance, revision),
                ).fetchone()
                context = json.loads(saved[0]) if saved else None
                if saved and profile_hash(context) != saved[1]:
                    raise ValueError("device runtime context checksum failed")
                return (revision, image, profile, context) if with_profile else (revision, image, context)
            return (revision, image, profile) if with_profile else (revision, image)
