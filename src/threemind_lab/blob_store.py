"""Immutable payload bytes. No Core computation or startup migration.

An external upload precedes the referencing transaction. Its durable candidate
receipt remains until a separately authorized, reference-checked cleanup. Reads
release database connections before external IO; all three readers verify SHA256.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import time
from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid4, uuid5

from psycopg.types.json import Jsonb

from .research_storage import ResearchStorage
from .storage_files import atomic_json, checked_path, file_lock, read_json, under_root

CHUNK = 1024 * 1024
CATEGORIES = ("media-original", "note-image", "export", "checkpoint")


class BlobStore:
    def __init__(
        self, storage=None, *, secret_box=None, maximum_bytes=20 * 1024**3, s3_factory=None, restore_projection=None
    ):
        self.storage = storage or ResearchStorage(os.getenv("THREEMIND_STORAGE_CONTROL") or None)
        self.secret_box = secret_box
        self.maximum_bytes = maximum_bytes
        self.s3_factory = s3_factory
        self.restore_projection = checked_path(restore_projection) if restore_projection else None
        self.location_resolver = None

    def policies(self):
        registered = self.storage._load().get("blob_policies")
        if registered is not None:
            return registered
        path = self.storage.control_dir / "blob-policies.json"
        return (
            read_json(path)
            if path.exists()
            else {"schema": "threemind.blob-policies/1", "revision": 0, "categories": {}}
        )

    def set_policy(self, category, target_id, *, expected_revision):
        if category not in CATEGORIES:
            raise ValueError("unsupported original-payload category")
        target = self.storage.target(target_id)
        with file_lock(self.storage.control_dir / "blob-policies.lock"):
            current = self.policies()
            if current["revision"] != expected_revision:
                raise ValueError("blob policy revision changed")
            current["categories"][category] = {"target_id": target_id, "config_revision": target["config_revision"]}
            current["revision"] += 1
            if "blob_policies" in self.storage._load():
                with self.storage._edit() as state:
                    state["blob_policies"] = current
            else:
                atomic_json(self.storage.control_dir / "blob-policies.json", current)
            return current

    def freeze(self, category):
        if category not in CATEGORIES:
            raise ValueError("invalid blob category")
        policy = self.policies()
        chosen = policy["categories"].get(category)
        if not chosen:
            return {"kind": "db", "category": category, "policy_revision": policy["revision"]}
        target = self.storage.target(chosen["target_id"], revision=chosen["config_revision"])
        return {
            "kind": target["kind"],
            "category": category,
            "policy_revision": policy["revision"],
            "target_id": target["id"],
            "config_revision": target["config_revision"],
            "host_id": target["host_id"],
        }

    def _target(self, frozen):
        target = self.storage.target(frozen["target_id"], revision=frozen["config_revision"])
        if target["kind"] != frozen["kind"] or target["host_id"] != frozen["host_id"]:
            raise ValueError("frozen storage identity mismatch")
        return target

    def _s3(self, target):
        config = target["configuration"]
        if self.s3_factory:
            return self.s3_factory(config)
        try:
            import boto3
            from botocore.config import Config
        except ImportError as error:
            raise ValueError("S3 requires the optional storage dependency") from error
        credentials = {}
        if config.get("encrypted_secret"):
            if not self.secret_box:
                raise ValueError("storage encryption key is unavailable")
            secret = self.secret_box.open(config["encrypted_secret"])
            credentials = {
                "aws_access_key_id": secret["access_key_id"],
                "aws_secret_access_key": secret["secret_access_key"],
            }
            if secret.get("session_token"):
                credentials["aws_session_token"] = secret["session_token"]
        else:
            # Never discover host/cloud credentials implicitly when merely using a target.
            raise ValueError("S3 requires explicitly encrypted credentials")
        return boto3.client(
            "s3",
            endpoint_url=config.get("endpoint"),
            region_name=config.get("region", "us-east-1"),
            config=Config(
                connect_timeout=5, read_timeout=30, retries={"max_attempts": 2}, s3={"addressing_style": "path"}
            ),
            **credentials,
        )

    def _receipt(self, row):
        atomic_json(self.storage.control_dir / "blob-candidates" / (str(row["id"]) + ".json"), row)

    def prepare(self, project, category, chunks, *, frozen=None):
        frozen = deepcopy(frozen or self.freeze(category))
        if frozen["category"] != category:
            raise ValueError("storage category differs from frozen policy")
        if frozen["kind"] == "db":
            return None
        target = self._target(frozen)
        scratch = checked_path(self.storage.control_dir / "blob-staging")
        scratch.mkdir(parents=True, exist_ok=True)
        temporary = scratch / (uuid4().hex + ".tmp")
        digest, size = hashlib.sha256(), 0
        try:
            with temporary.open("xb") as stream:
                for chunk in chunks:
                    if not isinstance(chunk, bytes) or not 0 < len(chunk) <= 4 * CHUNK:
                        raise ValueError("blob chunks must be bounded nonempty bytes")
                    size += len(chunk)
                    if size > self.maximum_bytes or shutil.disk_usage(scratch).free < len(chunk) + 16 * CHUNK:
                        raise ValueError("blob upload exceeds size or free-space budget")
                    digest.update(chunk)
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            sha = digest.hexdigest()
            blob_id = uuid5(UUID(str(project)), f"blob:{target['id']}:{target['config_revision']}:{sha}")
            key = f"objects/{project}/{sha[:2]}/{sha}"
            previous_receipt = self.storage.control_dir / "blob-candidates" / (str(blob_id) + ".json")
            if previous_receipt.exists() and read_json(previous_receipt).get("state") == "deleted":
                blob_id = uuid4()
                key += "/" + str(blob_id)
            row = {
                "id": str(blob_id),
                "project_id": str(project),
                "category": category,
                "bytes": size,
                "sha256": sha,
                "locator": {k: frozen[k] for k in ("kind", "target_id", "config_revision", "host_id")} | {"key": key},
                "policy": frozen,
                "state": "uploading",
                "version_id": None,
            }
            if target["kind"] == "filesystem":
                # Persist the final identity before publishing any bytes.
                self._receipt(row)
                path = under_root(Path(target["configuration"]["path"]), key)
                path.parent.mkdir(parents=True, exist_ok=True)
                with file_lock(path.with_suffix(".lock")):
                    if path.exists():
                        self._verify_file(path, sha, size)
                    else:
                        staged = path.with_name(path.name + "." + uuid4().hex + ".tmp")
                        try:
                            with temporary.open("rb") as source, staged.open("xb") as out:
                                shutil.copyfileobj(source, out, CHUNK)
                                out.flush()
                                os.fsync(out.fileno())
                            self._verify_file(staged, sha, size)
                            os.replace(staged, path)
                        finally:
                            staged.unlink(missing_ok=True)
            elif target["kind"] == "s3":
                client, config = self._s3(target), target["configuration"]
                key = config.get("prefix", "").strip("/") + "/" + key if config.get("prefix") else key
                row["locator"]["key"] = key
                # A unique key prevents a concurrent or foreign writer replacing this object.
                row["locator"]["key"] += "/" + uuid4().hex
                key = row["locator"]["key"]
                row["id"] = str(uuid5(UUID(str(project)), "s3:" + key))
                self._receipt(row)
                upload = client.create_multipart_upload(Bucket=config["bucket"], Key=key, Metadata={"sha256": sha})
                upload_id = upload["UploadId"]
                row["multipart_upload_id"] = upload_id
                self._receipt(row)
                try:
                    parts = []
                    with temporary.open("rb") as stream:
                        for number in range(1, 10001):
                            part = stream.read(8 * CHUNK)
                            if not part:
                                break
                            response = client.upload_part(
                                Bucket=config["bucket"], Key=key, UploadId=upload_id, PartNumber=number, Body=part
                            )
                            parts.append({"PartNumber": number, "ETag": response["ETag"]})
                    if not parts:
                        raise ValueError("external objects cannot be empty")
                    completed = client.complete_multipart_upload(
                        Bucket=config["bucket"], Key=key, UploadId=upload_id, MultipartUpload={"Parts": parts}
                    )
                    row["version_id"] = completed.get("VersionId")
                except BaseException:
                    client.abort_multipart_upload(Bucket=config["bucket"], Key=key, UploadId=upload_id)
                    row["state"] = "upload_failed"
                    self._receipt(row)
                    raise
            else:
                raise ValueError("unsupported external blob backend")
            row["state"] = "verified_candidate"
            # Read-back validates actual stored bytes, including S3, before attachment.
            for _ in self.read(row):
                pass
            self._receipt(row)
            return row
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _verify_file(path, sha, size):
        digest, count = hashlib.sha256(), 0
        with checked_path(path).open("rb") as stream:
            while chunk := stream.read(CHUNK):
                digest.update(chunk)
                count += len(chunk)
        if count != size or digest.hexdigest() != sha:
            raise ValueError("immutable storage object failed verification")

    def read(self, row, *, resolve=True):
        if resolve and self.location_resolver:
            row = self.location_resolver(row)
        digest, size = hashlib.sha256(), 0
        projected = None
        if self.restore_projection:
            projection = read_json(self.restore_projection)
            if (
                projection.get("schema") != "threemind.storage-restore/1"
                or projection.get("state") != "restored_unactivated"
            ):
                raise ValueError("unsupported explicit restore projection")
            matches = [r for r in projection["objects"] if r["id"] == str(row["id"])]
            if len(matches) != 1:
                raise ValueError("restored blob is absent from the explicit restore projection")
            item = matches[0]
            if (
                any(str(item[k]) != str(row[k]) for k in ("project_id", "sha256", "bytes"))
                or item["locator"] != row["locator"]
            ):
                raise ValueError("restore projection disagrees with immutable database evidence")
            projected = checked_path(item["restored_path"])
            if not projected.is_relative_to(self.restore_projection.parent):
                raise ValueError("restore projection leaves its isolated object root")
        target = self._target(row["locator"]) if projected is None else None
        if projected is not None:
            stream = projected.open("rb")
        elif target["kind"] == "filesystem":
            stream = under_root(Path(target["configuration"]["path"]), row["locator"]["key"]).open("rb")
        elif target["kind"] == "s3":
            kwargs = {"Bucket": target["configuration"]["bucket"], "Key": row["locator"]["key"]}
            if row.get("version_id"):
                kwargs["VersionId"] = row["version_id"]
            from botocore.exceptions import BotoCoreError, ClientError

            try:
                stream = self._s3(target).get_object(**kwargs)["Body"]
            except (BotoCoreError, ClientError) as error:
                raise OSError("registered S3 object is unavailable") from error
        else:
            raise ValueError("invalid external blob backend")
        try:
            while chunk := stream.read(CHUNK):
                digest.update(chunk)
                size += len(chunk)
                if size > row["bytes"]:
                    raise ValueError("storage object exceeds registered length")
                yield chunk
        finally:
            stream.close()
        if size != row["bytes"] or digest.hexdigest() != row["sha256"]:
            raise ValueError("storage object is missing or corrupt")

    def features(self):
        """Local capability advertisement only: never probes an S3 endpoint."""
        result = {}
        for row in self.storage._load()["targets"].values():
            for target in row["versions"].values():
                key = f"storage.target:{target['id']}:{target['config_revision']}@{target['host_id']}"
                available = False
                if target["kind"] == "filesystem":
                    path = checked_path(target["configuration"]["path"])
                    available = path.is_dir() and os.access(path, os.R_OK | os.W_OK)
                elif target["kind"] == "s3":
                    try:
                        self._s3(target)
                        available = True
                    except (ValueError, ImportError):
                        pass
                result[key] = {
                    "state": "available" if available else "unavailable",
                    "reason": "local target/dependency capability; remote health not probed",
                }
        return result

    def audit(
        self,
        database,
        project,
        *,
        actor=None,
        verify=False,
        maximum_objects=100,
        maximum_bytes=1024**3,
        cancelled=lambda: False,
    ):
        if not 1 <= maximum_objects <= 1000 or maximum_bytes <= 0:
            raise ValueError("invalid integrity audit budget")
        with database.tx(project) as db:
            if actor is not None:
                db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor),))
            from .storage_payloads import visible_blob

            visible = "WITH visible AS (SELECT b.* FROM stored_blobs b WHERE b.project_id=%s AND " + visible_blob() + ") "
            values = (project,)
            summary = db.execute(
                visible + "SELECT count(*) AS objects,coalesce(sum(bytes),0)::bigint AS logical_bytes FROM visible",
                values,
            ).fetchone()
            rows = db.execute(
                visible + "SELECT * FROM visible ORDER BY created_at,id LIMIT %s", (*values, maximum_objects + 1)
            ).fetchall()
        result, used = [], 0
        for row in rows[:maximum_objects]:
            item = {
                "id": str(row["id"]),
                "bytes": row["bytes"],
                "sha256": row["sha256"],
                "backend": row["locator"]["kind"],
                "status": "not_checked",
            }
            if verify:
                if cancelled():
                    item["status"] = "cancelled"
                elif used + row["bytes"] > maximum_bytes:
                    item["status"] = "budget_exhausted"
                else:
                    used += row["bytes"]
                    try:
                        for _ in self.read(row):
                            if cancelled():
                                raise InterruptedError("audit cancelled")
                        item["status"] = "verified"
                    except (OSError, ValueError) as error:
                        item["status"] = "unavailable_or_corrupt"
                        item["error"] = type(error).__name__
            result.append(item)
        return {
            "schema": "threemind.blob-audit/1",
            "summary": summary,
            "rows": result,
            "more": len(rows) > maximum_objects,
            "verified_budget_bytes": used,
            "physical_backend_bytes": None,
            "database_indexes_wal_bytes": None,
            "limitation": "logical registered object bytes; physical allocation/WAL are not inferred",
        }

    def candidate_inventory(self, database, project, *, maximum_records=200):
        """Bounded control-receipt inspection; no bucket or arbitrary-root scan."""
        if not 1 <= maximum_records <= 1000:
            raise ValueError("invalid candidate inventory budget")
        root = self.storage.control_dir / "blob-candidates"
        if not root.exists():
            return {"rows": [], "more": False, "inspected_receipts": 0, "logical_candidate_bytes": 0}
        receipts, inspected, incomplete_scan = [], 0, False
        with os.scandir(checked_path(root)) as entries:
            for entry in entries:
                inspected += 1
                if inspected > 5000:
                    incomplete_scan = True
                    break
                if not entry.name.endswith(".json") or not entry.is_file(follow_symlinks=False):
                    continue
                path = checked_path(entry.path)
                if path.stat().st_size > 128 * 1024:
                    continue
                row = read_json(path)
                if row.get("project_id") != str(project):
                    continue
                if str(UUID(str(row["id"]))) != path.stem:
                    raise ValueError("candidate receipt identity mismatch")
                receipts.append((row, path.stat().st_mtime))
        with database.tx(project) as db:
            registered = {
                str(r["id"])
                for r in db.execute(
                    "SELECT id FROM stored_blobs WHERE project_id=%s AND id=ANY(%s)",
                    (project, [UUID(row["id"]) for row, _ in receipts]),
                ).fetchall()
            }
        rows = []
        for row, updated_at in receipts:
            if row["id"] in registered or row["state"] == "deleted":
                continue
            expired = time.time() - updated_at >= 86400
            rows.append(
                {
                    "id": row["id"],
                    "bytes": row["bytes"],
                    "state": row["state"],
                    "reclaimable_candidate": expired and row["state"] == "verified_candidate",
                    "reason": "requires fresh reference check and human confirmation"
                    if expired and row["state"] == "verified_candidate"
                    else "incomplete/unverified or within 24 hour grace period; diagnose without automatic deletion",
                }
            )
        rows.sort(key=lambda item: item["id"])
        return {
            "rows": rows[:maximum_records],
            "more": incomplete_scan or len(rows) > maximum_records,
            "inspected_receipts": min(inspected, 5000),
            "logical_candidate_bytes": sum(row["bytes"] for row in rows),
            "complete_scan": not incomplete_scan,
            "physical_backend_bytes": None,
        }

    def cleanup_preview(self, database, project, candidate_id):
        identifier = str(UUID(str(candidate_id)))
        path = self.storage.control_dir / "blob-candidates" / (identifier + ".json")
        row = read_json(path)
        if row["project_id"] != str(project) or row["id"] != identifier:
            raise ValueError("candidate is outside this project")
        with database.tx(project) as db:
            registered = db.execute(
                "SELECT id FROM stored_blobs WHERE id=%s OR (locator=%s AND sha256=%s)",
                (identifier, Jsonb(row["locator"]), row["sha256"]),
            ).fetchone()
        reasons = []
        if registered:
            reasons.append(
                "registered immutable object; retained until its referencing records and backup leases are explicitly removed"
            )
        if row["state"] != "verified_candidate" or time.time() - path.stat().st_mtime < 86400:
            reasons.append("unfinished or recent upload; retain for retries and receipt recovery")
        plan = {
            "schema": "threemind.blob-cleanup/1",
            "id": identifier,
            "project_id": str(project),
            "name": identifier,
            "allowed": not reasons,
            "reasons": reasons,
            "scope": "one registered, unreferenced expired upload candidate; never a bucket prefix scan",
        }
        # A candidate UUID is not permission to inspect an attached private
        # original. Registered evidence is protected, regardless of ownership.
        if not registered:
            plan.update(
                bytes=row["bytes"],
                sha256=row["sha256"],
                locator=row["locator"],
                version_id=row.get("version_id"),
            )
        from .experiment_archive import canonical

        return plan | {"token": hashlib.sha256(canonical(plan)).hexdigest()}

    def cleanup_execute(self, database, project, candidate_id, *, token, confirm_name):
        with file_lock(self.storage.control_dir / "blob-candidates" / (str(UUID(str(candidate_id))) + ".lock")):
            plan = self.cleanup_preview(database, project, candidate_id)
            if not plan["allowed"] or plan["token"] != token or confirm_name != plan["name"]:
                raise ValueError("candidate cleanup blocked or preview changed; obtain a new human confirmation")
            # A durable tombstone fences concurrent attachments before irreversible IO.
            # It also survives a crash after DB commit but before object removal.
            with database.tx(project) as db:
                db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("blob:" + plan["id"],))
                if db.execute("SELECT id FROM stored_blobs WHERE id=%s", (plan["id"],)).fetchone():
                    raise ValueError("candidate gained an immutable registration")
                db.execute(
                    "INSERT INTO blob_tombstones(id,project_id,plan) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                    (plan["id"], project, Jsonb(plan)),
                )
            target = self._target(plan["locator"])
            if target["kind"] == "filesystem":
                path = under_root(Path(target["configuration"]["path"]), plan["locator"]["key"])
                with file_lock(path.with_suffix(".lock")):
                    # Fresh reference check while holding the same publication lock.
                    if not self.cleanup_preview(database, project, candidate_id)["allowed"]:
                        raise ValueError("candidate gained a reference")
                    path.unlink(missing_ok=True)
            else:
                kwargs = {"Bucket": target["configuration"]["bucket"], "Key": plan["locator"]["key"]}
                if plan.get("version_id"):
                    kwargs["VersionId"] = plan["version_id"]
                self._s3(target).delete_object(**kwargs)
            receipt = {"schema": "threemind.blob-cleanup-receipt/1", "preview": plan, "removed": True}
            atomic_json(self.storage.control_dir / "blob-cleanup-receipts" / (plan["id"] + ".json"), receipt)
            candidate_path = self.storage.control_dir / "blob-candidates" / (plan["id"] + ".json")
            candidate = read_json(candidate_path)
            candidate["state"] = "deleted"
            self._receipt(candidate)
            return receipt

    @staticmethod
    def attach(db, row):
        if row is None:
            return None
        # Candidate identities are immutable. Concurrent identical local uploads share it;
        # S3 uses unique keys and therefore a unique candidate identity.
        blob_id = row["id"]
        if row["locator"]["kind"] == "s3":
            blob_id = str(uuid5(UUID(str(row["project_id"])), "s3:" + row["locator"]["key"]))
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("blob:" + str(blob_id),))
        if db.execute("SELECT id FROM blob_tombstones WHERE id=%s", (blob_id,)).fetchone():
            raise ValueError("upload candidate was explicitly retired; prepare a new immutable candidate")
        db.execute(
            "INSERT INTO stored_blobs(id,project_id,bytes,sha256,locator,version_id) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (blob_id, row["project_id"], row["bytes"], row["sha256"], Jsonb(row["locator"]), row.get("version_id")),
        )
        existing = db.execute("SELECT * FROM stored_blobs WHERE id=%s", (blob_id,)).fetchone()
        if (
            not existing
            or existing["bytes"] != row["bytes"]
            or existing["sha256"] != row["sha256"]
            or existing["locator"] != row["locator"]
            or str(existing["project_id"]) != str(row["project_id"])
            or existing["version_id"] != row.get("version_id")
        ):
            raise ValueError("immutable blob identity conflict")
        return blob_id


def object_chunks(database, project, kind, identity, *, actor=None):
    """Lookup authority first; short DB chunk reads and no connection held for IO."""
    queries = {
        "artifact": ("artifacts", "id", "bytes", "artifact_chunks", "artifact_id", "ordinal"),
        "media": ("media_assets", "sha256", "byte_length", "media_chunks", "sha256", "chunk_index"),
    }
    if kind not in queries:
        raise ValueError("unsupported binary resource type")
    table, column, length, chunks, foreign, ordinal = queries[kind]
    with database.tx(project) as db:
        if actor is not None:
            db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor),))
        row = db.execute(
            f"SELECT {length} AS bytes,sha256,blob_id FROM {table} WHERE {column}=%s", (identity,)
        ).fetchone()
        if row is None:
            raise ValueError("binary resource is unavailable")
        blob = (
            db.execute("SELECT * FROM stored_blobs WHERE id=%s", (row["blob_id"],)).fetchone()
            if row["blob_id"]
            else None
        )
    if row["blob_id"]:
        if not blob or blob["sha256"] != row["sha256"] or blob["bytes"] != row["bytes"]:
            raise ValueError("binary resource reference is inconsistent")
        yield from database.blobs.read(blob)
        return
    digest, count, after = hashlib.sha256(), 0, -1
    while True:
        with database.tx(project) as db:
            if actor is not None:
                db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor),))
            part = db.execute(
                f"SELECT body,{ordinal} AS ordinal FROM {chunks} WHERE {foreign}=%s AND {ordinal}>%s ORDER BY {ordinal} LIMIT 1",
                (identity, after),
            ).fetchone()
        if part is None:
            break
        after = part["ordinal"]
        raw = bytes(part["body"])
        digest.update(raw)
        count += len(raw)
        yield raw
    if count != row["bytes"] or digest.hexdigest() != row["sha256"]:
        raise ValueError("database binary resource failed verification")
