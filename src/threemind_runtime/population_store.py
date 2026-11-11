"""Optional local, atomic population recovery and append-only evidence.

This is a standalone Runtime host, not a second backend for the multi-user Lab.
One SQLite transaction owns the world, ledger, every brain and its new evidence.
"""

import json
import sqlite3
from contextlib import contextmanager

from threemind_core import StateImage

from .cold_state import StateReference
from .ecology_job import parse_job
from .world_schema import digest

MAX_IMAGE_BYTES = 512 * 1024**2


class PopulationStore:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS population_schema(version INTEGER PRIMARY KEY CHECK(version=1));
                INSERT OR IGNORE INTO population_schema VALUES(1);
                CREATE TABLE IF NOT EXISTS population_instances(id TEXT PRIMARY KEY,revision INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS population_checkpoints(
                    instance TEXT NOT NULL,revision INTEGER NOT NULL,protocol_json TEXT NOT NULL,
                    protocol_hash TEXT NOT NULL,metadata_json TEXT NOT NULL,state_hash TEXT NOT NULL,
                    PRIMARY KEY(instance,revision));
                CREATE TABLE IF NOT EXISTS population_states(hash TEXT PRIMARY KEY,byte_count INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS population_chunks(
                    hash TEXT NOT NULL REFERENCES population_states(hash),ordinal INTEGER NOT NULL,body BLOB NOT NULL,
                    PRIMARY KEY(hash,ordinal));
                CREATE TABLE IF NOT EXISTS population_members(
                    instance TEXT NOT NULL,revision INTEGER NOT NULL,individual TEXT NOT NULL,
                    state_hash TEXT NOT NULL REFERENCES population_states(hash),
                    PRIMARY KEY(instance,revision,individual),
                    FOREIGN KEY(instance,revision) REFERENCES population_checkpoints(instance,revision));
                CREATE TABLE IF NOT EXISTS population_evidence(
                    id INTEGER PRIMARY KEY,instance TEXT NOT NULL,revision INTEGER NOT NULL,
                    event_json TEXT NOT NULL,
                    FOREIGN KEY(instance,revision) REFERENCES population_checkpoints(instance,revision));
                CREATE INDEX IF NOT EXISTS population_evidence_history ON population_evidence(instance,revision,id);
            """)
            if db.execute("SELECT version FROM population_schema").fetchall() != [(1,)]:
                raise ValueError("unsupported standalone population store schema")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        finally:
            db.close()

    def image(self, state_hash):
        with self.connect() as db:
            row = db.execute("SELECT byte_count FROM population_states WHERE hash=?", (state_hash,)).fetchone()
            if row is None or not 0 < row[0] <= MAX_IMAGE_BYTES:
                raise ValueError("missing or oversized population model")
            payload = bytearray()
            for ordinal, body in db.execute(
                "SELECT ordinal,body FROM population_chunks WHERE hash=? ORDER BY ordinal", (state_hash,)
            ):
                if ordinal != len(payload) // 1048576 or len(payload) + len(body) > row[0] or len(body) > 1048576:
                    raise ValueError("invalid population model chunks")
                payload.extend(body)
            if len(payload) != row[0]:
                raise ValueError("incomplete population model")
        image = StateImage(bytes(payload))
        if image.digest != state_hash:
            raise ValueError("population model checksum mismatch")
        return image

    def reference(self, state_hash):
        return StateReference(state_hash, lambda: self.image(state_hash))

    def save(self, instance, protocol, checkpoint, *, expected_revision, events=()):
        if not isinstance(instance, str) or not 1 <= len(instance) <= 120:
            raise ValueError("instance must be a nonempty name of at most 120 characters")
        protocol = parse_job(protocol.model_dump(mode="json") if hasattr(protocol, "model_dump") else protocol)
        metadata, images = checkpoint
        if metadata.get("checkpoint_hash") != digest({k: v for k, v in metadata.items() if k != "checkpoint_hash"}):
            raise ValueError("population checkpoint metadata checksum mismatch")
        if set(images) != set(metadata["members"]) or any(
            images[key].digest != member["state_hash"] for key, member in metadata["members"].items()
        ):
            raise ValueError("population checkpoint is missing or combines incompatible brains")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT revision FROM population_instances WHERE id=?", (instance,)).fetchone()
            previous = row[0] if row else 0
            if type(expected_revision) is not int or previous != expected_revision:
                raise ValueError("population has another writer or a newer revision")
            if previous:
                old = db.execute(
                    "SELECT protocol_hash FROM population_checkpoints WHERE instance=? AND revision=?",
                    (instance, previous),
                ).fetchone()
                if old[0] != protocol.digest:
                    raise ValueError("exact population continuation cannot replace the frozen protocol")
            revision = previous + 1
            db.execute(
                "INSERT INTO population_checkpoints VALUES(?,?,?,?,?,?)",
                (
                    instance,
                    revision,
                    protocol.model_dump_json(),
                    protocol.digest,
                    json.dumps(metadata, allow_nan=False),
                    metadata["checkpoint_hash"],
                ),
            )
            for identity, image in images.items():
                if db.execute("SELECT 1 FROM population_states WHERE hash=?", (image.digest,)).fetchone() is None:
                    payload = image.payload
                    if not 0 < len(payload) <= MAX_IMAGE_BYTES:
                        raise ValueError("population model exceeds the 512 MiB local recovery budget")
                    db.execute("INSERT INTO population_states VALUES(?,?)", (image.digest, len(payload)))
                    for ordinal, start in enumerate(range(0, len(payload), 1048576)):
                        db.execute(
                            "INSERT INTO population_chunks VALUES(?,?,?)",
                            (image.digest, ordinal, payload[start : start + 1048576]),
                        )
                db.execute(
                    "INSERT INTO population_members VALUES(?,?,?,?)", (instance, revision, identity, image.digest)
                )
            for event in events:
                db.execute(
                    "INSERT INTO population_evidence(instance,revision,event_json) VALUES(?,?,?)",
                    (instance, revision, json.dumps(event, allow_nan=False)),
                )
            db.execute(
                "INSERT INTO population_instances VALUES(?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision",
                (instance, revision),
            )
        return revision

    def load(self, instance, *, revision=None):
        with self.connect() as db:
            db.execute("BEGIN")
            if revision is None:
                row = db.execute("SELECT revision FROM population_instances WHERE id=?", (instance,)).fetchone()
                if row is None:
                    raise KeyError(instance)
                revision = row[0]
            row = db.execute(
                "SELECT protocol_json,protocol_hash,metadata_json,state_hash FROM population_checkpoints WHERE instance=? AND revision=?",
                (instance, revision),
            ).fetchone()
            if row is None:
                raise KeyError((instance, revision))
            members = db.execute(
                "SELECT individual,state_hash FROM population_members WHERE instance=? AND revision=?",
                (instance, revision),
            ).fetchall()
        protocol, metadata = parse_job(row[0]), json.loads(row[2])
        if (
            protocol.digest != row[1]
            or metadata.get("checkpoint_hash") != row[3]
            or digest({k: v for k, v in metadata.items() if k != "checkpoint_hash"}) != row[3]
        ):
            raise ValueError("population protocol or metadata checksum mismatch")
        if {key: value for key, value in members} != {
            key: value["state_hash"] for key, value in metadata["members"].items()
        }:
            raise ValueError("population manifest has incomplete member references")
        return revision, protocol, (metadata, {key: self.reference(value) for key, value in members})

    def evidence(self, instance, revision):
        with self.connect() as db:
            for (event,) in db.execute(
                "SELECT event_json FROM population_evidence WHERE instance=? AND revision<=? ORDER BY id",
                (instance, revision),
            ):
                yield json.loads(event)
