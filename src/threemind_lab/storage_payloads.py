"""Host storage changes for immutable payloads, never simulation operations.

Database source bytes are retained. Existing scientific identities and original
locators are not rewritten. External IO happens outside publication transactions.
"""

from __future__ import annotations

import hashlib
from contextlib import nullcontext
from uuid import UUID

from psycopg.types.json import Jsonb

from .blob_store import CHUNK, object_chunks
from .storage_files import StorageConflict, atomic_json, file_lock, read_json

OBJECTS = {
    "artifact": ("artifacts", "id", "bytes", "export"),
    "media": ("media_assets", "sha256", "byte_length", "media-original"),
    "note-image": ("note_assets", "id", "bytes", "note-image"),
    "checkpoint": ("checkpoints", "id", "byte_count", "checkpoint"),
    "blob": ("stored_blobs", "id", "bytes", "export"),
}


def visible_blob(alias="b", *, checkpoints=True):
    clauses = [
        f"EXISTS(SELECT 1 FROM artifacts a WHERE a.blob_id={alias}.id)",
        f"EXISTS(SELECT 1 FROM media_assets m WHERE m.blob_id={alias}.id)",
        f"EXISTS(SELECT 1 FROM note_assets n WHERE n.blob_id={alias}.id AND n.owner_id::text=current_setting('tm.note_user_id',true))",
        (
            f"EXISTS(SELECT 1 FROM data_bundle_volumes v JOIN data_bundles d ON d.id=v.bundle_id WHERE v.blob_id={alias}.id "
            "AND (NOT d.private OR d.actor_id::text=current_setting('tm.note_user_id',true)))"
        ),
    ]
    if checkpoints:
        clauses.append(f"EXISTS(SELECT 1 FROM checkpoints c WHERE c.blob_id={alias}.id)")
    return "(" + " OR ".join(clauses) + ")"


def physical_location(db, row):
    current = db.execute(
        "SELECT v.locator,v.version_id,v.revision FROM blob_location_heads h "
        "JOIN blob_location_versions v USING(project_id,blob_id,revision) WHERE h.blob_id=%s",
        (row["id"],),
    ).fetchone()
    return row if not current else row | current | {"original_locator": row.get("original_locator", row["locator"])}


class PayloadStorage:
    def __init__(self, database):
        self.database = database

    @property
    def blobs(self):
        return self.database.blobs

    @property
    def storage(self):
        return self.blobs.storage

    def location(self, row, *, transaction=None):
        with self.database.tx(row["project_id"]) if transaction is None else nullcontext(transaction) as db:
            return physical_location(db, row)

    def prepare_checkpoint(self, project, raw):
        root = self.storage.writable_root()
        with file_lock(self.storage.control_dir / "checkpoint-policy.lock"):
            frozen = self.blobs.freeze("checkpoint")
            if frozen["kind"] == "db":
                target_id = "checkpoints-" + hashlib.sha256(str(root).encode()).hexdigest()[:24]
                try:
                    self.storage.target(target_id)
                except ValueError:
                    self.storage.register_target(root / "checkpoints", "File checkpoints", target_id=target_id)
                self.blobs.set_policy("checkpoint", target_id, expected_revision=self.blobs.policies()["revision"])
                frozen = self.blobs.freeze("checkpoint")
            if frozen["kind"] != "filesystem":
                raise ValueError("filesystem checkpoint backend requires a filesystem checkpoint target")
        return self.blobs.prepare(
            project, "checkpoint", (raw[i : i + CHUNK] for i in range(0, len(raw), CHUNK)), frozen=frozen
        )

    def inventory(self, project, *, actor=None, limit=10000):
        rows = []
        with self.database.tx(project, read_only=True) as db:
            if actor:
                db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor),))
            locations = bool(db.execute("SELECT to_regclass('tm2.run_storage_seals') present").fetchone()["present"])
            for kind, (table, key, length, _) in OBJECTS.items():
                if kind == "checkpoint" and not locations:
                    continue
                condition = " WHERE project_id=%s" + ("" if kind == "blob" else " AND blob_id IS NULL")
                if kind == "blob":
                    condition += " AND " + visible_blob("stored_blobs", checkpoints=locations)
                    if locations:
                        condition += (
                            " AND NOT EXISTS (SELECT 1 FROM checkpoints c LEFT JOIN run_storage_seals s ON s.run_id=c.run_id "
                            "JOIN runs r ON r.id=c.run_id WHERE c.blob_id=stored_blobs.id AND (s.run_id IS NULL "
                            "OR s.revision<>r.revision OR s.state_hash<>r.state_hash "
                            "OR r.status NOT IN ('completed','dead','cancelled','failed')))"
                        )
                # Only an explicitly sealed, unchanged, stopped run is eligible.
                if kind == "checkpoint":
                    condition += (
                        " AND run_id IN (SELECT s.run_id FROM run_storage_seals s JOIN runs r ON r.id=s.run_id "
                    )
                    condition += "WHERE s.revision=r.revision AND s.state_hash=r.state_hash AND r.status IN ('completed','dead','cancelled','failed'))"
                records = db.execute(
                    f"SELECT {key} AS id,{length} AS bytes"
                    + (",sha256" if kind != "checkpoint" else ",run_id")
                    + f" FROM {table}{condition} ORDER BY {key} LIMIT %s",
                    (project, limit + 1),
                ).fetchall()
                if len(records) > limit:
                    raise ValueError("payload inventory exceeds its explicit object budget")
                rows.extend(
                    {
                        "kind": kind,
                        "project_id": str(project),
                        "id": str(r["id"]),
                        "bytes": int(r["bytes"]),
                        **({"sha256": r["sha256"]} if "sha256" in r else {"run_id": str(r["run_id"])}),
                    }
                    for r in records
                )
        return rows

    def _path(self, identity):
        return self.storage.control_dir / "payload-migrations" / (str(UUID(str(identity))) + ".json")

    def _row(self, db, kind, identity):
        table, key, length, _ = OBJECTS[kind]
        row = db.execute(f"SELECT *,{length} AS payload_bytes FROM {table} WHERE {key}=%s", (identity,)).fetchone()
        if not row:
            raise ValueError("payload is missing or not authorized")
        return row

    def _chunks(self, project, kind, row, *, actor=None):
        if kind in ("artifact", "media"):
            yield from object_chunks(self.database, project, kind, row[OBJECTS[kind][1]], actor=actor)
        elif kind == "blob":
            yield from self.blobs.read(row)
        elif kind == "note-image":
            from .notebooks import asset

            raw = bytes(asset(self.database, project, actor or row["owner_id"], row["id"])["content"])
            yield from (raw[i : i + CHUNK] for i in range(0, len(raw), CHUNK))
        else:
            if row.get("blob_id"):
                with self.database.tx(project) as db:
                    blob = db.execute("SELECT * FROM stored_blobs WHERE id=%s", (row["blob_id"],)).fetchone()
                yield from self.blobs.read(blob)
            else:
                after = -1
                while True:
                    with self.database.tx(project) as db:
                        part = db.execute(
                            "SELECT ordinal,body,sha256 FROM state_chunks WHERE checkpoint_id=%s AND ordinal>%s ORDER BY ordinal LIMIT 1",
                            (row["id"], after),
                        ).fetchone()
                    if not part:
                        break
                    if part["ordinal"] != after + 1 or hashlib.sha256(part["body"]).hexdigest() != part["sha256"]:
                        raise StorageConflict("checkpoint chunk sequence/checksum differs")
                    after = part["ordinal"]
                    yield bytes(part["body"])

    def _eligible(self, db, kind, row):
        if kind == "blob":
            if not db.execute(
                "SELECT 1 FROM stored_blobs b WHERE b.id=%s AND " + visible_blob(), (row["id"],)
            ).fetchone():
                raise StorageConflict("blob has no authorized visible scientific reference")
            for checkpoint in db.execute("SELECT * FROM checkpoints WHERE blob_id=%s", (row["id"],)).fetchall():
                self._eligible(db, "checkpoint", checkpoint)
            return
        if kind != "checkpoint":
            return
        run = db.execute("SELECT * FROM runs WHERE id=%s FOR SHARE", (row["run_id"],)).fetchone()
        seal = db.execute("SELECT * FROM run_storage_seals WHERE run_id=%s", (row["run_id"],)).fetchone()
        if (
            not seal
            or run["status"] not in ("completed", "dead", "cancelled", "failed")
            or seal["revision"] != run["revision"]
            or seal["state_hash"] != run["state_hash"]
        ):
            raise StorageConflict("checkpoint requires an unchanged completed and explicitly sealed subject")
        if db.execute(
            "SELECT 1 FROM jobs WHERE run_id=%s AND status IN ('pending','leased')", (row["run_id"],)
        ).fetchone():
            raise StorageConflict("checkpoint subject has an active writer")

    def migrate(self, project, kind, identity, target_id, *, operation_id, actor=None, cancelled=lambda: False):
        if kind not in OBJECTS:
            raise ValueError("unsupported payload type")
        operation_id = UUID(str(operation_id))
        arguments = {
            "project": str(project),
            "kind": kind,
            "object": str(identity),
            "target": target_id,
            "actor": str(actor) if actor else None,
        }
        path = self._path(operation_id)
        with file_lock(path.with_suffix(".lock")):
            receipt = read_json(path) if path.exists() else None
            if receipt and receipt["arguments"] != arguments:
                raise StorageConflict("payload request ID was reused with different arguments")
            if receipt and receipt["state"] == "activated":
                self.verify(receipt)
                return receipt
            with self.database.tx(project) as db:
                if actor:
                    db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor),))
                row = self._row(db, kind, identity)
                self._eligible(db, kind, row)
                source_revision = 0
                if kind == "blob":
                    previous = db.execute(
                        "SELECT revision FROM blob_location_heads WHERE blob_id=%s", (identity,)
                    ).fetchone()
                    source_revision = previous["revision"] if previous else 0
                    published = db.execute(
                        "SELECT v.*,b.bytes,b.sha256 FROM blob_location_versions v JOIN stored_blobs b ON b.id=v.carrier_blob_id "
                        "WHERE v.blob_id=%s AND v.operation_id=%s",
                        (identity, operation_id),
                    ).fetchone()
                    if published and receipt:
                        receipt.update(
                            state="activated",
                            placement_revision=published["revision"],
                            new_blob_id=str(published["carrier_blob_id"]),
                            bytes=published["bytes"],
                            sha256=published["sha256"],
                            locator=published["locator"],
                        )
                if receipt and receipt["state"] == "activated":
                    atomic_json(path, receipt)
            if receipt and receipt["state"] == "activated":
                self.verify(receipt)
                return receipt
            if kind != "blob" and row.get("blob_id"):
                if receipt and receipt.get("new_blob_id") == str(row["blob_id"]):
                    receipt["state"] = "activated"
                    atomic_json(path, receipt)
                    self.verify(receipt)
                    return receipt
                raise StorageConflict("payload was already moved by another operation")
            if kind == "checkpoint":
                # Entire delta lineage + exact state hash is checked before copying.
                self.database.load_checkpoint(project, row["run_id"], row["id"])
            target = self.storage.target(target_id)
            if target["kind"] != "filesystem":
                raise ValueError("this migration phase supports local filesystem targets")
            frozen = {
                "category": OBJECTS[kind][3],
                "policy_revision": self.blobs.policies()["revision"],
                **{k: target[k] for k in ("kind", "target_id", "config_revision", "host_id")},
            }
            receipt = receipt or {
                "schema": "threemind.payload-migration/1",
                "id": str(operation_id),
                "arguments": arguments,
                "state": "copying",
                "source_blob_id": str(row.get("blob_id")) if row.get("blob_id") else None,
                "source_placement_revision": source_revision,
                "source_retained": True,
            }
            if receipt.get("source_placement_revision", 0) != source_revision:
                raise StorageConflict("payload placement changed before retry; make a new migration")
            atomic_json(path, receipt)

            def copying():
                for chunk in self._chunks(project, kind, row, actor=actor):
                    if cancelled():
                        raise InterruptedError("payload migration cancelled before publication")
                    yield chunk

            prepared = self.blobs.prepare(project, frozen["category"], copying(), frozen=frozen)
            if (
                prepared["bytes"] != int(row["payload_bytes"])
                or kind != "checkpoint"
                and prepared["sha256"] != row["sha256"]
            ):
                raise StorageConflict("copied original differs from registered scientific size/hash")
            receipt.update(
                state="copied",
                new_blob_id=prepared["id"],
                sha256=prepared["sha256"],
                bytes=prepared["bytes"],
                locator=prepared["locator"],
            )
            atomic_json(path, receipt)
            if cancelled():
                raise InterruptedError("payload migration cancelled before publication")
            with self.database.tx(project) as db:
                if actor:
                    db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor),))
                db.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("payload:" + kind + ":" + str(identity),)
                )
                current = self._row(db, kind, identity)
                self._eligible(db, kind, current)
                if current["payload_bytes"] != row["payload_bytes"] or current.get("blob_id") != row.get("blob_id"):
                    raise StorageConflict("payload source changed before activation")
                carrier = self.blobs.attach(db, prepared)
                if kind == "blob":
                    existing = db.execute(
                        "SELECT * FROM blob_location_versions WHERE blob_id=%s AND operation_id=%s",
                        (identity, operation_id),
                    ).fetchone()
                    if existing:
                        if existing["locator"] != prepared["locator"]:
                            raise StorageConflict("physical location retry differs")
                        revision = existing["revision"]
                    else:
                        head = db.execute(
                            "SELECT revision FROM blob_location_heads WHERE blob_id=%s", (identity,)
                        ).fetchone()
                        if (head["revision"] if head else 0) != receipt["source_placement_revision"]:
                            raise StorageConflict("payload placement changed before activation")
                        revision = (
                            1
                            + db.execute(
                                "SELECT coalesce(max(revision),0) revision FROM blob_location_versions WHERE blob_id=%s",
                                (identity,),
                            ).fetchone()["revision"]
                        )
                        db.execute(
                            "INSERT INTO blob_location_versions(project_id,blob_id,revision,locator,version_id,carrier_blob_id,operation_id) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                            (
                                project,
                                identity,
                                revision,
                                Jsonb(prepared["locator"]),
                                prepared.get("version_id"),
                                carrier,
                                operation_id,
                            ),
                        )
                        db.execute(
                            "INSERT INTO blob_location_heads VALUES(%s,%s,%s) ON CONFLICT(blob_id) DO UPDATE SET revision=EXCLUDED.revision",
                            (project, identity, revision),
                        )
                    receipt["placement_revision"] = revision
                else:
                    table, key, _, _ = OBJECTS[kind]
                    db.execute(f"UPDATE {table} SET blob_id=%s WHERE {key}=%s", (carrier, identity))
            receipt["state"] = "activated"
            atomic_json(path, receipt)
            self.verify(receipt)
            return receipt

    def verify(self, receipt):
        """Never fall back to the retained DB chunks for external verification."""
        project = receipt["arguments"]["project"]
        with self.database.tx(project) as db:
            blob = db.execute("SELECT * FROM stored_blobs WHERE id=%s", (receipt["new_blob_id"],)).fetchone()
        if not blob or blob["sha256"] != receipt["sha256"] or blob["bytes"] != receipt["bytes"]:
            raise StorageConflict("payload migration reference is inconsistent")
        for _ in self.blobs.read(blob):
            pass
        return {"id": receipt["id"], "state": "verified", "source_fallback": False}

    def rollback(self, receipt):
        receipt = read_json(self._path(receipt["id"]))
        if receipt["state"] == "rolled_back":
            return receipt
        args = receipt["arguments"]
        self.verify(receipt)
        # A rollback is a new read-location decision, not permission to trust an
        # old retained copy. Prove its bytes before changing any pointer.
        checksum, size = hashlib.sha256(), 0
        with self.database.tx(args["project"]) as db:
            if args.get("actor"):
                db.execute("SELECT set_config('tm.note_user_id',%s,true)", (args["actor"],))
            original = self._row(db, args["kind"], args["object"])
            if args["kind"] == "blob":
                revision = receipt["source_placement_revision"]
                previous = (
                    db.execute(
                        "SELECT locator,version_id FROM blob_location_versions WHERE blob_id=%s AND revision=%s",
                        (args["object"], revision),
                    ).fetchone()
                    if revision
                    else None
                )
                source_blob = original | (previous or {})
                source = None
            elif args["kind"] == "note-image":
                source_blob = None
                source = [bytes(original["content"])] if original["content"] is not None else []
            else:
                table, key, ordinal = {
                    "artifact": ("artifact_chunks", "artifact_id", "ordinal"),
                    "media": ("media_chunks", "sha256", "chunk_index"),
                    "checkpoint": ("state_chunks", "checkpoint_id", "ordinal"),
                }[args["kind"]]
                source_blob = None
                # Rollback is explicitly bounded by the original payload size;
                # server-side streaming avoids loading an archive into memory.
                source = db.cursor(name="rollback_payload")
                source.execute(f"SELECT body FROM {table} WHERE {key}=%s ORDER BY {ordinal}", (args["object"],))
            for part in self.blobs.read(source_blob, resolve=False) if source_blob else source:
                raw = part if isinstance(part, bytes) else bytes(part["body"])
                checksum.update(raw)
                size += len(raw)
        if checksum.hexdigest() != receipt["sha256"] or size != receipt["bytes"]:
            raise StorageConflict("retained source failed rollback verification")
        with self.database.tx(args["project"]) as db:
            if args.get("actor"):
                db.execute("SELECT set_config('tm.note_user_id',%s,true)", (args["actor"],))
            if args["kind"] == "blob":
                head = db.execute(
                    "SELECT revision FROM blob_location_heads WHERE blob_id=%s FOR UPDATE", (args["object"],)
                ).fetchone()
                if not head or head["revision"] != receipt["placement_revision"]:
                    raise StorageConflict("blob has a newer placement; use a reverse migration")
                if receipt["source_placement_revision"] == 0:
                    db.execute("DELETE FROM blob_location_heads WHERE blob_id=%s", (args["object"],))
                else:
                    db.execute(
                        "UPDATE blob_location_heads SET revision=%s WHERE blob_id=%s",
                        (receipt["source_placement_revision"], args["object"]),
                    )
            else:
                row = self._row(db, args["kind"], args["object"])
                if str(row.get("blob_id")) != receipt["new_blob_id"]:
                    raise StorageConflict("payload has a different active placement")
                table, key, _, _ = OBJECTS[args["kind"]]
                # Source presence/checksum is verified before switching to it.
                self._eligible(db, args["kind"], row)
                db.execute(f"UPDATE {table} SET blob_id=%s WHERE {key}=%s", (receipt["source_blob_id"], args["object"]))
        receipt["state"] = "rolled_back"
        atomic_json(self._path(receipt["id"]), receipt)
        return receipt

    def seal(self, project, run_id):
        """Seal only a complete supported recovery boundary; never pause a run."""
        cp, image = self.database.load_checkpoint(project, run_id)
        from .experiment_bundles import resume_conditions

        with self.database.tx(project) as db:
            run = db.execute("SELECT * FROM runs WHERE id=%s FOR UPDATE", (run_id,)).fetchone()
            if run["status"] not in ("completed", "cancelled", "failed") or run["revision"] != cp["revision"]:
                raise StorageConflict("sealing requires a stopped completed subject at the unchanged latest checkpoint")
            proof = resume_conditions(db, run, cp)
            if proof["blockers"]:
                raise StorageConflict("incomplete/unsupported whole-system recovery: " + "; ".join(proof["blockers"]))
            if db.execute(
                "SELECT 1 FROM jobs WHERE run_id=%s AND status IN ('pending','leased')", (run_id,)
            ).fetchone():
                raise StorageConflict("subject has an active writer")
            proof.update(verified_state_hash=image.digest, scope="supported complete Lab recovery boundary")
            db.execute(
                "INSERT INTO run_storage_seals(project_id,run_id,checkpoint_id,revision,state_hash,proof) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(run_id) DO NOTHING",
                (project, run_id, cp["id"], cp["revision"], image.digest, Jsonb(proof)),
            )
        return proof
