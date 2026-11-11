"""Formal data transfers and explicit new-identity record/runtime restoration."""

from __future__ import annotations

import hashlib
import io
import re
import shutil
import zipfile
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from tempfile import TemporaryFile
from uuid import UUID, uuid4, uuid5

from psycopg.types.json import Jsonb

from threemind_runtime.capabilities import kernel_feature

from . import permissions
from .blob_store import object_chunks
from .data_archive import RECOVERY_SCHEMA, SCHEMA, SET_SCHEMA, DataLimits, DataReader, stream_hash
from .data_catalog import NATIVE, SCHEMAS, DataCatalog, actor_id, authorized
from .database import Conflict, NotFound
from .experiment_archive import CHUNK, ArchiveWriter, canonical
from .experiment_bundles import TransferCancelled, TransferGuard
from .storage_files import checked_path

MAX_NATIVE_RECORDS = 256 * 1024**2


def _parts(values, size=CHUNK):
    pending = bytearray()
    iterator = iter(values)
    try:
        for value in iterator:
            view = memoryview(value)
            while view:
                take = min(size - len(pending), len(view))
                pending.extend(view[:take])
                view = view[take:]
                if len(pending) == size:
                    yield bytes(pending)
                    pending.clear()
        if pending:
            yield bytes(pending)
    finally:
        close = getattr(iterator, "close", None)
        if close:
            close()


class DataBundles:
    def __init__(self, database, *, limits=None, volume_bytes=7 * 1024**3):
        limits = limits or DataLimits()
        if volume_bytes < 16384 or volume_bytes > limits.volume.compressed - 8192:
            raise ValueError("invalid data volume packing budget")
        self.database, self.limits, self.volume_bytes = database, limits, volume_bytes
        self.part_bytes = min(CHUNK, volume_bytes // 4)

    def _scratch(self):
        directory = checked_path(self.database.blobs.storage.control_dir / "data-transfers")
        directory.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(directory).free < 15 * 1024**3:
            raise ValueError("data transfer scratch directory requires 15 GiB free reserve")
        return TemporaryFile(dir=directory)

    def _get(self, db, bundle_id):
        bundle = db.execute("SELECT * FROM data_bundles WHERE id=%s", (bundle_id,)).fetchone()
        if not bundle:
            raise NotFound("data bundle is unavailable to this actor")
        return bundle

    def list(self, project, actor, offset=0, limit=50):
        if not 0 <= offset <= 100000 or not 1 <= limit <= 200:
            raise ValueError("invalid bundle pagination budget")
        with authorized(self.database, project, actor) as db:
            rows = db.execute("SELECT id,name,private,bytes,created_at,job_id,plan_id "
                              "FROM data_bundles ORDER BY created_at DESC,id LIMIT %s OFFSET %s", (limit + 1, offset)).fetchall()
        return {"rows": rows[:limit], "more": len(rows) > limit, "offset": offset, "limit": limit}

    def detail(self, project, actor, bundle_id):
        with authorized(self.database, project, actor) as db:
            bundle = self._get(db, bundle_id)
            mappings = db.execute("SELECT * FROM data_import_mappings WHERE bundle_id=%s ORDER BY object_id", (bundle_id,)).fetchall()
        return bundle | {"volumes": bundle["manifest"]["volumes"], "mappings": mappings,
                         "mode": "read_only_original", "starts_running": False}

    def chunks(self, project, actor, bundle_id, volume=0):
        with authorized(self.database, project, actor) as db:
            self._get(db, bundle_id)
            row = db.execute("SELECT * FROM data_bundle_volumes WHERE bundle_id=%s AND ordinal=%s", (bundle_id, volume)).fetchone()
            if not row:
                raise NotFound("data volume is unavailable")
            blob = db.execute("SELECT * FROM stored_blobs WHERE id=%s", (row["blob_id"],)).fetchone() if row["blob_id"] else None
        checksum, size = hashlib.sha256(), 0
        if blob:
            if blob["sha256"] != row["sha256"] or blob["bytes"] != row["bytes"]:
                raise Conflict("data volume carrier identity is inconsistent")
            values = self.database.blobs.read(blob)
        else:
            values = self._database_chunks(project, actor, bundle_id, volume)
        for chunk in values:
            checksum.update(chunk)
            size += len(chunk)
            yield chunk
        if size != row["bytes"] or checksum.hexdigest() != row["sha256"]:
            raise ValueError("data volume failed recorded size/hash verification")

    def _database_chunks(self, project, actor, bundle_id, volume):
        after = -1
        while True:
            with authorized(self.database, project, actor) as db:
                row = db.execute("SELECT ordinal,body FROM data_bundle_chunks WHERE bundle_id=%s AND volume=%s "
                                 "AND ordinal>%s ORDER BY ordinal LIMIT 1", (bundle_id, volume, after)).fetchone()
            if row is None:
                break
            after = row["ordinal"]
            yield bytes(row["body"])

    @contextmanager
    def _open(self, project, actor, bundle_id, *, check=lambda: None):
        bundle = self.detail(project, actor, bundle_id)
        with ExitStack() as stack:
            streams = []
            for volume in bundle["volumes"]:
                stream = stack.enter_context(self._scratch())
                for chunk in self.chunks(project, actor, bundle_id, volume["ordinal"]):
                    check()
                    stream.write(chunk)
                stream.seek(0)
                streams.append(stream)
            reader = stack.enter_context(DataReader({"manifest": bundle["manifest"], "volumes": streams}, limits=self.limits, check=check))
            yield reader

    def preflight(self, project, actor, stream, backend="native"):
        if backend not in ("native", "reference"):
            raise ValueError("unknown explicit runtime backend")
        with authorized(self.database, project, actor, write=True):
            pass
        with DataReader(stream, limits=self.limits) as reader:
            result = reader.preflight()
            self._validate_records(reader)
            native_bytes = sum(reader.files[o["payload"]]["bytes"] for o in reader.objects.values()
                               if o["kind"] in NATIVE and SCHEMAS.get(o["kind"]) == o["schema"] and o.get("payload") in reader.files)
            if native_bytes > MAX_NATIVE_RECORDS:
                result["can_restore"] = False
                result["limitations"].append("native metadata recovery exceeds the 256 MiB transaction budget; originals remain read-only")
            result["backend"] = backend
            result["restorers"] = [self._adapter(reader, item, backend) for item in reader.objects.values()
                                   if item.get("adapter") and SCHEMAS.get(item["kind"]) == item["schema"]]
            result["can_resume"] = not result["missing_required"] and any(r["can_resume"] for r in result["restorers"])
            return result

    def _validate_records(self, reader):
        from pydantic import TypeAdapter

        from .note_schema import Body, NoteEdit, body_links
        from .report_schema import DocumentSpec

        private = False
        for item in reader.objects.values():
            if SCHEMAS.get(item["kind"]) != item["schema"] or item.get("payload") not in reader.files:
                continue
            payload = reader.json(item["payload"])
            if not isinstance(payload, dict) or not isinstance(payload.get("record"), dict):
                raise ValueError("known data object requires its typed original record")  # noqa: TRY004 - Invalid archive data uses the public validation error contract.
            row, kind = payload["record"], item["kind"]
            private = private or bool(row.get("private")) or bool(row.get("metadata", {}).get("private")) or kind in ("note", "note_asset", "collection")
            required, origin_required = set(), set()
            identity = row.get("sha256") if kind == "media" else row.get("id")
            if (str(identity) != item.get("source_id") or str(row.get("project_id")) != item.get("source_project")
                or item.get("source_project") != reader.manifest["recovery"]["source_project"]):
                raise ValueError("typed data record identity does not agree with its recovery descriptor")
            if kind != "media":
                UUID(str(identity))
            if kind == 'experiment':
                from .record_schema import ExperimentSpec
                from .research_records import digest
                ExperimentSpec.model_validate(row['spec'])
                if digest(row['spec']) != row['content_hash']:
                    raise ValueError('experiment original metadata hash differs')
                seen = set()
                for evidence in payload.get('evidence', []):
                    if evidence['logical_id'] in seen:
                        raise ValueError('duplicate logical evidence identity')
                    seen.add(evidence['logical_id'])
                    location = evidence['locator']
                    if location['kind'] in ('document', 'note', 'artifact'):
                        required.add(location['kind'] + ':' + location['id'])
                    elif location['kind'] in ('file', 'package'):
                        original = reader.files.get(evidence.get('bytes_entry'))
                        if not original or original['sha256'] != evidence['sha256'] or original['bytes'] != int(evidence['byte_count']):
                            raise ValueError('experiment original bytes are absent or disagree with registered identity')
                    if evidence.get('private_actor_id'):
                        private = True
                for entry in payload.get('entries', []):
                    if digest(entry['content']) != entry['content_hash']:
                        raise ValueError('experiment entry hash differs')
            if kind in ("document", "note"):
                versions = payload.get("versions")
                if not isinstance(versions, list) or [v.get("revision") for v in versions] != list(range(1, int(row["revision"]) + 1)):
                    raise ValueError("formal record recovery requires complete ordered revision history")
                for version in versions:
                    if str(version.get("project_id")) != item["source_project"] or str(version.get("document_id" if kind == "document" else "note_id")) != item["source_id"]:
                        raise ValueError("historical version belongs to another typed record")
                    if kind == "document":
                        if "import_ai_generated" in version and type(version["import_ai_generated"]) is not bool:
                            raise ValueError("imported AI provenance must be an explicit boolean")
                        spec = DocumentSpec.model_validate(version["spec"])
                        if version.get("review") not in ("draft", "reviewed"):
                            raise ValueError("invalid original research review state")
                        required.update("source:" + str(source) for source in spec.sources)
                        required.update("document:" + str(block.record_id) for block in spec.blocks if block.type == "record_block")
                    else:
                        TypeAdapter(Body).validate_python(version["body"])
                        NoteEdit.model_validate(version["metadata"] | {"operation_id": version["operation_id"],
                            "expected_revision": version["revision"] - 1, "body": version["body"]})
                        collection = version["metadata"].get("collection_id")
                        if collection:
                            required.add("collection:" + collection)
                        for link in body_links(version["body"]):
                            match = re.fullmatch(r"/api/v2/projects/([0-9a-fA-F-]{36})/note-assets/([0-9a-fA-F-]{36})", link)
                            if match:
                                if str(UUID(match[1])) != item["source_project"]:
                                    raise ValueError("private historical note attachment belongs to another project")
                                required.add("note_asset:" + str(UUID(match[2])))
                head = versions[-1]["spec" if kind == "document" else "metadata"]
                if head.get("title") != row.get("title") or head.get("kind") != row.get("kind"):
                    raise ValueError("record head disagrees with its complete revision history")
                if kind == "document":
                    ai_revisions = [str(v["revision"]) for v in versions if v.get("ai_call_id") or v.get("import_ai_generated")]
                    if "ai_generated_revisions" in payload and payload["ai_generated_revisions"] != ai_revisions:
                        raise ValueError("AI revision provenance disagrees with its original versions")
                    expected_sources = {(v["revision"], source) for v in versions for source in v["spec"]["sources"]}
                    actual_sources = {(r["revision"], r["source_id"]) for r in payload.get("sources", [])}
                    expected_refs = {(v["revision"], b["record_id"], b["revision"], b["block_id"])
                                     for v in versions for b in v["spec"]["blocks"] if b["type"] == "record_block"}
                    actual_refs = {(r["revision"], r["record_id"], r["record_revision"], r["block_id"]) for r in payload.get("refs", [])}
                    if expected_sources != actual_sources or expected_refs != actual_refs:
                        raise ValueError("fixed historical document references are incomplete")
                else:
                    required.update("note_asset:" + r["asset_id"] for r in payload.get("asset_refs", []))
            if kind in ("artifact", "media", "note_asset", "species", "experiment_bundle"):
                name = payload.get("bytes_entry")
                if name not in reader.files:
                    raise ValueError("known binary record is missing its required original bytes")
                expected_size = row.get("byte_length", row.get("bytes"))
                expected_sha = row.get("sha256", row.get("bundle_hash"))
                if reader.files[name]["bytes"] != expected_size or reader.files[name]["sha256"] != expected_sha:
                    raise ValueError("binary data record differs from its recovery bytes")
                if kind == "note_asset" and expected_size > 8 * 1024**2:
                    raise ValueError("note image exceeds its native recovery budget")
            if kind == "source":
                if not isinstance(payload.get("request"), dict) or payload.get("rows_entry") not in reader.files:
                    raise ValueError("fixed evidence capture requires its request provenance and complete rows")
                if (str(payload["request"].get("id")) != item["source_id"]
                    or str(payload["request"].get("project_id")) != item["source_project"]
                    or not isinstance(row.get("manifest"), dict)):
                    raise ValueError("fixed evidence request identity or manifest is invalid")
                count, previous = 0, -1
                for record in reader.rows(payload["rows_entry"]):
                    if not isinstance(record, dict) or type(record.get("ordinal")) is not int or record["ordinal"] <= previous:
                        raise ValueError("fixed source rows must have ordered unique ordinals")
                    if not isinstance(record.get("values"), dict) or not isinstance(record.get("provenance"), dict):
                        raise ValueError("invalid typed fixed evidence row")  # noqa: TRY004 - Invalid archive data uses the public validation error contract.
                    if str(record.get("source_id")) != item["source_id"] or str(record.get("project_id")) != item["source_project"]:
                        raise ValueError("fixed evidence row belongs to another original source")
                    previous, count = record["ordinal"], count + 1
                if count != row.get("row_count"):
                    raise ValueError("fixed source recovery rows are incomplete")
                if payload["request"].get("analysis_artifact_id"):
                    required.add("artifact:" + payload["request"]["analysis_artifact_id"])
                calibration = payload["request"].get("calibration_id")
                if calibration:
                    origin_required.add("probe:" + calibration)
                    for group in ("selection", "provenance"):
                        declared_calibration = payload["request"].get(group, {}).get("calibration_id")
                        if declared_calibration and declared_calibration != calibration:
                            raise ValueError("fixed calibration capture has inconsistent original identities")
            if kind == "probe":
                execution = payload.get("execution")
                if (not isinstance(execution, dict) or execution.get("id") != str(row.get("job_id"))
                    or execution.get("project_id") != item["source_project"]
                    or hashlib.sha256(canonical(execution)).hexdigest() != payload.get("execution_hash")):
                    raise ValueError("probe execution provenance is incomplete or inconsistent")
                for field, checksum in (("artifact_id", "result_sha256"), ("bundle_artifact_id", "bundle_sha256")):
                    identity = (execution.get("result") or {}).get(field)
                    if identity:
                        dependency = "artifact:" + identity
                        required.add(dependency)
                        original = reader.objects.get(dependency)
                        if not original or original["schema"] != SCHEMAS["artifact"]:
                            raise ValueError("probe original artifact dependency is absent")
                        artifact = reader.json(original["payload"])["record"]
                        if artifact["sha256"] != execution["result"].get(checksum):
                            raise ValueError("probe execution result hash differs from its archive original")
            declared = {d["object_id"] for d in item["dependencies"] if isinstance(d, dict) and d.get("required", True) and d.get("mode") != "read_only_origin"}
            if required - declared:
                raise ValueError("typed original references are absent from the required recovery dependency declaration")
            declared_origin = {d["object_id"] for d in item["dependencies"] if isinstance(d, dict) and d.get("required", True)
                               and d.get("mode") == "read_only_origin" and d["object_id"] in reader.objects}
            if origin_required - declared_origin:
                raise ValueError("fixed evidence requires its read-only original calibration dependency")
        return private

    def _action(self, db, project, actor, op_id, kind, fingerprint):
        op_id = UUID(str(op_id))
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,61))", (f"data-action:{project}:{actor_id(actor)}:{op_id}",))
        row = db.execute("SELECT * FROM data_bundle_actions WHERE actor_id=%s AND operation_id=%s", (actor_id(actor), op_id)).fetchone()
        if row and (row["fingerprint"] != fingerprint or row["kind"] != kind):
            raise Conflict("data operation identity belongs to a different action")
        return row

    def _queue(self, project, actor, kind, body, op_id):
        fingerprint = hashlib.sha256(canonical(body)).hexdigest()
        with authorized(self.database, project, actor, write=True) as db:
            previous = self._action(db, project, actor, op_id, kind, fingerprint)
            if previous:
                return db.execute("SELECT * FROM jobs WHERE id=%s", (previous["job_id"],)).fetchone()
            job_id = uuid4()
            params = body | {"actor_id": str(actor_id(actor)), "operation_id": str(op_id), "storage_policy": self.database.blobs.freeze("export")}
            params["execution_actor"] = permissions.execution_actor(permissions.resolve_actor(self.database, actor))
            params["source_targets"] = self._source_targets(db, kind, body)
            if kind == "data_restore":
                params["restore_policies"] = {category: self.database.blobs.freeze(category)
                                               for category in ("export", "media-original", "note-image")}
            job = db.execute("INSERT INTO jobs(id,project_id,kind,params) VALUES(%s,%s,%s,%s) RETURNING *",
                             (job_id, project, kind, Jsonb(params))).fetchone()
            db.execute("INSERT INTO data_bundle_actions(project_id,actor_id,operation_id,fingerprint,kind,job_id) VALUES(%s,%s,%s,%s,%s,%s)",
                       (project, actor_id(actor), op_id, fingerprint, kind, job_id))
            return job

    def _source_targets(self, db, kind, body):
        if kind == "data_export":
            locators = db.execute("SELECT DISTINCT b.id,b.project_id,b.locator FROM data_plan_files f "
                "LEFT JOIN artifacts a ON a.id=f.artifact_id LEFT JOIN media_assets m ON m.sha256=f.media_sha256 "
                "LEFT JOIN note_assets n ON n.id=f.note_asset_id JOIN stored_blobs b ON b.id="
                "CASE WHEN f.recipe ? 'blob_id' THEN (f.recipe->>'blob_id')::uuid ELSE coalesce(a.blob_id,m.blob_id,n.blob_id) END "
                "WHERE f.plan_id=%s", (body["plan_id"],)).fetchall()
            media = []
        else:
            bundle = self._get(db, body["bundle_id"])
            locators = db.execute("SELECT DISTINCT b.id,b.project_id,b.locator FROM data_bundle_volumes v JOIN stored_blobs b ON b.id=v.blob_id "
                                  "WHERE v.bundle_id=%s", (body["bundle_id"],)).fetchall()
            media = body.get("source_media", []) if kind == "data_resume" else [
                item["source_id"] for item in bundle["manifest"]["recovery"]["objects"]
                if item["kind"] == "media" and item["schema"] == SCHEMAS["media"]]
        if media:
            locators += db.execute("SELECT DISTINCT b.id,b.project_id,b.locator FROM media_assets m JOIN stored_blobs b ON b.id=m.blob_id WHERE m.sha256=ANY(%s)", (media,)).fetchall()
        locators = [self.database.payloads.location(row,transaction=db) for row in locators]
        targets = {canonical({key: row["locator"][key] for key in ("kind", "target_id", "config_revision", "host_id")}):
                   {key: row["locator"][key] for key in ("kind", "target_id", "config_revision", "host_id")}
                   for row in locators if row["locator"]["kind"] in ("filesystem", "s3")}
        return [targets[key] for key in sorted(targets)]

    def export(self, project, actor, plan_id, op_id):
        DataCatalog(self.database).plan(project, actor, plan_id)
        return self._queue(project, actor, "data_export", {"plan_id": str(plan_id)}, op_id)

    def restore_records(self, project, actor, bundle_id, op_id):
        bundle = self.detail(project, actor, bundle_id)
        if not any(o["kind"] in NATIVE and SCHEMAS.get(o["kind"]) == o["schema"] for o in bundle["manifest"]["recovery"]["objects"]):
            raise Conflict("this archive has no registered native record restorer; its original bytes remain read-only")
        return self._queue(project, actor, "data_restore", {"bundle_id": str(bundle_id)}, op_id)

    def status(self, project, actor, job_id):
        with authorized(self.database, project, actor) as db:
            job = db.execute("SELECT * FROM jobs WHERE id=%s", (job_id,)).fetchone()
            if (not job or job["kind"] not in ("data_export", "data_restore", "data_resume")
                or job["kind"] == "data_export" and "plan_id" not in job["params"]
                or job["params"].get("actor_id") != str(actor_id(actor)) and not permissions.resolve_actor(self.database, actor)["superadmin"]):
                raise NotFound("data task is unavailable to this actor")
            return job

    def cancel(self, project, actor, job_id):
        self.status(project, actor, job_id)
        with authorized(self.database, project, actor, write=True) as db:
            job = db.execute("SELECT status FROM jobs WHERE id=%s FOR UPDATE", (job_id,)).fetchone()
            if job["status"] == "pending":
                db.execute("UPDATE jobs SET status='cancelled',error='user cancelled' WHERE id=%s", (job_id,))
            elif job["status"] == "leased":
                db.execute("UPDATE jobs SET params=params || '{\"cancel_requested\":true}'::jsonb WHERE id=%s", (job_id,))
        return {"accepted": True, "job_id": str(job_id),
                "meaning": "stop before atomic publication; committed original packages and records remain"}

    def _fence(self, db, job):
        self._job_actor(job)
        self.database.fence(db, job)
        row = db.execute("SELECT params FROM jobs WHERE id=%s", (job["id"],)).fetchone()
        if row["params"].get("cancel_requested"):
            raise TransferCancelled("data task cancelled before publication; existing evidence remains")

    def _job_actor(self, job):
        action = "data.export" if job["kind"] == "data_export" else "runs.restore" if job["kind"] == "data_resume" else "data.import"
        lineage = job["params"].get("execution_actor")
        if not lineage:
            # Pre-upgrade jobs preserve their declared account, never root.
            lineage = {"user_id": job["params"]["actor_id"], "source": "script"}
        return permissions.restore_execution_actor(self.database, lineage, action=action,
            project=job["project_id"], resources=[{"kind": "project", "id": str(job["project_id"])}])

    def import_register(self, project, actor, stream, op_id, name="Imported data bundle"):
        if not isinstance(name, str) or not 1 <= len(name) <= 160:
            raise ValueError("a bounded data bundle name is required")
        with authorized(self.database, project, actor, write=True):
            frozen = self.database.blobs.freeze("export")
        with DataReader(stream, limits=self.limits) as reader:
            private = self._validate_records(reader)
            fingerprint = hashlib.sha256(canonical({"manifest": reader.manifest, "name": name})).hexdigest()
            with authorized(self.database, project, actor, write=True) as db:
                previous = self._action(db, project, actor, op_id, "import", fingerprint)
                if previous:
                    return self.detail(project, actor, previous["result"]["bundle_id"])
            prepared = []
            for volume in reader.readers:
                volume.stream.seek(0)
                prepared.append(self.database.blobs.prepare(project, "export", iter(lambda volume=volume: volume.stream.read(CHUNK), b""), frozen=frozen))
            bundle_id = uuid5(UUID(str(project)), f"data-import:{actor_id(actor)}:{UUID(str(op_id))}")
            with authorized(self.database, project, actor, write=True) as db:
                previous = self._action(db, project, actor, op_id, "import", fingerprint)
                if previous:
                    return {"id": previous["result"]["bundle_id"], "replayed": True}
                self._store(db, project, actor, bundle_id, name, reader.manifest, [r.stream for r in reader.readers], prepared, private_override=private)
                db.execute("INSERT INTO data_bundle_actions(project_id,actor_id,operation_id,fingerprint,kind,result) VALUES(%s,%s,%s,%s,'import',%s)",
                           (project, actor_id(actor), op_id, fingerprint, Jsonb({"bundle_id": str(bundle_id)})))
            return self.detail(project, actor, bundle_id)

    def _store(self, db, project, actor, bundle_id, name, manifest, streams, prepared, *, plan_id=None, job=None, private_override=False):
        recovery = manifest["recovery"]
        if len(manifest["volumes"]) != len(streams) or len(streams) != len(prepared):
            raise ValueError("all verified data volume carriers must commit together")
        private = bool(private_override) or bool(recovery.get("private")) or any(
            item.get("private") or item["kind"] in ("note", "note_asset", "collection") for item in recovery["objects"])
        db.execute("INSERT INTO data_bundles(id,project_id,actor_id,name,private,manifest,bytes,plan_id,job_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                   (bundle_id, project, actor_id(actor), name, private, Jsonb(manifest), sum(v["bytes"] for v in manifest["volumes"]),
                    plan_id, job["id"] if job else None))
        for volume, stream, blob in zip(manifest["volumes"], streams, prepared):
            blob_id = self.database.blobs.attach(db, blob)
            db.execute("INSERT INTO data_bundle_volumes VALUES(%s,%s,%s,%s,%s,%s)",
                       (project, bundle_id, volume["ordinal"], volume["bytes"], volume["sha256"], blob_id))
            if not blob:
                stream.seek(0)
                ordinal = 0
                while chunk := stream.read(CHUNK):
                    db.execute("INSERT INTO data_bundle_chunks VALUES(%s,%s,%s,%s,%s)",
                               (project, bundle_id, volume["ordinal"], ordinal, chunk))
                    ordinal += 1
        for item in recovery["objects"]:
            db.execute("INSERT INTO data_origin_objects VALUES(%s,%s,%s,%s,%s,%s)",
                       (project, bundle_id, item["object_id"], item["kind"], item["schema"], Jsonb(item)))

    def _plan_chunks(self, project, actor, plan_id, file):
        with authorized(self.database, project, actor) as db:
            row = db.execute("SELECT * FROM data_plan_files WHERE plan_id=%s AND name=%s", (plan_id, file["name"])).fetchone()
        recipe = row["recipe"]
        if recipe["kind"] in ("artifact", "media", "note_asset") and "blob_id" in recipe:
            kind = recipe["kind"]
            table, column = {"artifact": ("artifacts", "id"), "media": ("media_assets", "sha256"), "note_asset": ("note_assets", "id")}[kind]
            with authorized(self.database, project, actor) as db:
                carrier = db.execute(f"SELECT blob_id FROM {table} WHERE {column}=%s", (recipe["id"],)).fetchone()
            current = str(carrier["blob_id"]) if carrier and carrier["blob_id"] else None
            if not carrier or current != recipe["blob_id"]:
                raise Conflict("a pinned export carrier changed after snapshot; make a new export plan")
        if recipe["kind"] == "checkpoint-payload":
            with authorized(self.database, project, actor) as db:
                carrier = db.execute(
                    "SELECT b.* FROM checkpoints c JOIN stored_blobs b ON b.id=c.blob_id "
                    "WHERE c.id=%s AND c.run_id=%s AND c.blob_id=%s",
                    (recipe["id"], recipe["run_id"], recipe["blob_id"]),
                ).fetchone()
            if not carrier:
                raise Conflict("a pinned checkpoint carrier changed after snapshot; make a new export plan")
            values = self.database.blobs.read(carrier)
        elif recipe["kind"] in ("artifact", "media"):
            values = object_chunks(self.database, project, recipe["kind"], recipe["id"], actor=actor_id(actor))
        elif recipe["kind"] == "note_asset":
            from .notebooks import asset
            raw = bytes(asset(self.database, project, actor_id(actor), recipe["id"])["content"])
            values = (raw[i:i + CHUNK] for i in range(0, len(raw), CHUNK))
        elif recipe['kind'] == 'research-evidence':
            from .research_records import ResearchRecords
            values = ResearchRecords(self.database).chunks(project, actor, recipe['id'])
        else:
            values = self._snapshot_chunks(project, actor, plan_id, file["name"])
        checksum, size = hashlib.sha256(), 0
        for chunk in values:
            checksum.update(chunk)
            size += len(chunk)
            yield chunk
        if size != file["bytes"] or checksum.hexdigest() != file["sha256"]:
            raise Conflict("a pinned export file changed or lost its registered bytes")

    def _snapshot_chunks(self, project, actor, plan_id, name):
        after = -1
        while True:
            with authorized(self.database, project, actor) as db:
                row = db.execute("SELECT ordinal,body FROM data_plan_chunks WHERE plan_id=%s AND name=%s AND ordinal>%s "
                                 "ORDER BY ordinal LIMIT 1", (plan_id, name, after)).fetchone()
            if not row:
                break
            after = row["ordinal"]
            yield bytes(row["body"])

    def _export_job(self, worker, job):
        self._job_actor(job)
        project, actor = job["project_id"], job["params"]["actor_id"]
        plan = DataCatalog(self.database).plan(project, actor, job["params"]["plan_id"])
        bundle_id = uuid5(UUID(str(job["id"])), "data-export")
        with authorized(self.database, project, actor, write=True) as db:
            old = db.execute("SELECT id FROM data_bundles WHERE id=%s", (bundle_id,)).fetchone()
            if old:
                self._fence(db, job)
                return {"bundle_id": str(bundle_id), "replayed": True}
        recovery = {key: deepcopy(plan[key]) for key in ("source_project", "source_actor", "scope", "snapshot_id", "objects", "private", "limitations", "complete_history")}
        recovery["schema"], recovery["files"] = RECOVERY_SCHEMA, []
        groups, volume_size = [[]], 0
        for file in plan["files"]:
            row = deepcopy(file) | {"parts": []}
            for index in range((file["bytes"] + self.part_bytes - 1) // self.part_bytes):
                size = min(self.part_bytes, file["bytes"] - index * self.part_bytes)
                if groups[-1] and volume_size + size > self.volume_bytes:
                    groups.append([])
                    volume_size = 0
                part = {"volume": len(groups) - 1, "name": file["name"] + f"/part-{index:06d}"}
                row["parts"].append(part)
                groups[-1].append(part)
                volume_size += size
            recovery["files"].append(row)
        if len(groups) > self.limits.volumes:
            raise ValueError("export requires more volumes than its declared budget")
        guard = TransferGuard(self.database, job)
        with ExitStack() as stack:
            streams = [stack.enter_context(self._scratch()) for _ in groups]
            writers = [ArchiveWriter(stream, {"bundle_id": str(bundle_id), "volume": ordinal,
                        "volume_count": len(groups), "recovery": recovery}, schema=SCHEMA,
                        limits=self.limits.volume, check=guard) for ordinal, stream in enumerate(streams)]
            for writer in writers:
                stack.callback(writer.close)
            for file, recovery_file in zip(plan["files"], recovery["files"]):
                iterator = _parts(self._plan_chunks(project, actor, plan["id"], file), self.part_bytes)
                try:
                    for part in recovery_file["parts"]:
                        writers[part["volume"]].add(part["name"], [next(iterator)])
                    if next(iterator, None) is not None:
                        raise Conflict("export source exceeds its saved plan")
                finally:
                    iterator.close()
            for writer in writers:
                writer.finish()
            volumes = []
            for ordinal, stream in enumerate(streams):
                size, sha = stream_hash(stream)
                volumes.append({"ordinal": ordinal, "bytes": size, "sha256": sha,
                                "filename": f"{bundle_id}.v{ordinal + 1:03d}.tmdata"})
            manifest = {"schema": SET_SCHEMA, "bundle_id": str(bundle_id), "recovery": recovery, "volumes": volumes}
            with DataReader({"manifest": manifest, "volumes": streams}, limits=self.limits, check=guard) as reader:
                private = self._validate_records(reader)
            prepared = []
            for stream in streams:
                guard()
                stream.seek(0)
                prepared.append(self.database.blobs.prepare(project, "export", iter(lambda stream=stream: stream.read(CHUNK), b""), frozen=job["params"]["storage_policy"]))
            with authorized(self.database, project, actor, write=True) as db:
                self._fence(db, job)
                self._store(db, project, actor, bundle_id, "Research data snapshot", manifest, streams, prepared, plan_id=plan["id"], job=job, private_override=private)
            return {"bundle_id": str(bundle_id), "volumes": volumes, "mode": "read_only_original", "starts_running": False}

    def object(self, project, actor, bundle_id, object_id):
        with self._open(project, actor, bundle_id) as reader:
            item = reader.objects.get(object_id)
            if not item:
                raise NotFound("origin data object is unavailable")
            value = None
            if item.get("payload") in reader.files:
                if SCHEMAS.get(item["kind"]) == item["schema"]:
                    value = reader.json(item["payload"])
                else:
                    value = {"file": item["payload"], "bytes": reader.files[item["payload"]]["bytes"],
                             "sha256": reader.files[item["payload"]]["sha256"], "read_as": "opaque original bytes"}
        with authorized(self.database, project, actor) as db:
            mapping = db.execute("SELECT * FROM data_import_mappings WHERE bundle_id=%s AND object_id=%s", (bundle_id, object_id)).fetchone()
        return {"descriptor": item, "original": value, "mapping": mapping, "mode": "read_only_original"}

    def _restore_job(self, worker, job):
        self._job_actor(job)
        project, actor, bundle_id = job["project_id"], job["params"]["actor_id"], job["params"]["bundle_id"]
        guard = TransferGuard(self.database, job)
        with self._open(project, actor, bundle_id, check=guard) as reader:
            self._validate_records(reader)
            preflight = reader.preflight()
            if preflight["missing_required"]:
                raise Conflict("required recovery dependencies are missing; original package remains read-only")
            known = {k: v for k, v in reader.objects.items() if v["kind"] in NATIVE and SCHEMAS.get(v["kind"]) == v["schema"]}
            if sum(reader.files[o["payload"]]["bytes"] for o in known.values()) > MAX_NATIVE_RECORDS:
                raise Conflict("native metadata recovery exceeds its transaction budget; original package remains read-only")
            payloads = {key: reader.json(item["payload"]) for key, item in known.items()}
            existing_media = self._verified_media(project, actor, known, payloads, guard, job["params"]["source_targets"])
            identities = {str(reader.manifest["recovery"]["source_project"]): str(project)}
            new_ids = {}
            for key, item in known.items():
                row = payloads[key]["record"]
                new_id = row["sha256"] if item["kind"] == "media" else str(uuid5(UUID(str(bundle_id)), "record:" + key))
                new_ids[key] = new_id
                identities[item["kind"] + ":" + str(item["source_id"])] = new_id
            # Prepare immutable external bytes before holding the restore
            # transaction. Actual scientific weights keep their existing DB form.
            prepared = {}
            for key, item in known.items():
                kind, payload = item["kind"], payloads[key]
                category = {"media": "media-original", "note_asset": "note-image"}.get(kind)
                if kind == "artifact" and payload["record"].get("metadata", {}).get("kind") in ("export", "report-export", "experiment-bundle"):
                    category = "export"
                if category:
                    if kind == "media" and existing_media.get(payload["record"]["sha256"]) is not None:
                        continue
                    guard()
                    prepared[key] = self.database.blobs.prepare(
                        project, category, reader.chunks(payload["bytes_entry"]),
                        frozen=job["params"]["restore_policies"][category],
                    )
            with authorized(self.database, project, actor, write=True) as db:
                db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,61))", ("data-restore:" + str(bundle_id),))
                existing = db.execute("SELECT * FROM data_import_mappings WHERE bundle_id=%s", (bundle_id,)).fetchall()
                if existing:
                    self._fence(db, job)
                    return {"bundle_id": str(bundle_id), "mappings": existing, "replayed": True, "starts_running": False}
                for key, item in known.items():
                    for dependency in item["dependencies"]:
                        if dependency.get("required", True) and dependency["object_id"] not in known and dependency.get("mode") != "read_only_origin":
                            raise Conflict("a native record needs an unsupported dependency; use its read-only origin")
                mappings = []
                for kind in ("collection", "artifact", "media", "note_asset", "species", "source", "document", "note", "experiment"):
                    for key, item in known.items():
                        if item["kind"] != kind:
                            continue
                        payload, new_id = payloads[key], new_ids[key]
                        origin = {"schema": "threemind.data.import-projection/1", "origin_bundle_id": str(bundle_id),
                                  "origin_object_id": key, "source_project": item["source_project"],
                                  "source_id": item["source_id"], "original": payload["record"]}
                        if kind == "collection":
                            row = payload["record"]
                            db.execute("INSERT INTO note_collections(id,project_id,owner_id,kind,name,color,is_default,auto_named,revision,archived_at,created_at,updated_at) "
                                       "VALUES(%s,%s,%s,%s,%s,%s,false,false,%s,%s,%s,%s)",
                                       (new_id, project, actor_id(actor), row["kind"], row["name"], row["color"], row["revision"],
                                        row.get("archived_at"), row["created_at"], row["updated_at"]))
                            projection_hash = hashlib.sha256(canonical(row | {"id": new_id, "owner_id": str(actor_id(actor))})).hexdigest()
                        elif kind in ("artifact", "media", "note_asset", "species"):
                            new_id, projection_hash = self._restore_binary(db, project, actor, job, reader, item, payload, new_id, prepared.get(key), origin, existing_media)
                            new_ids[key] = new_id
                            identities[item["kind"] + ":" + str(item["source_id"])] = new_id
                        elif kind == "source":
                            projection_hash = self._restore_source(db, project, actor, job, reader, payload, new_id, origin)
                        elif kind == "document":
                            origin["ai_generated_revisions"] = [str(v["revision"]) for v in payload["versions"]
                                if v.get("ai_call_id") or v.get("import_ai_generated")]
                            projection_hash = self._restore_document(db, project, actor, payload, new_id, identities, origin)
                        elif kind == 'experiment':
                            from .research_records import ResearchRecords
                            projection_hash = ResearchRecords(self.database).restore_archive(
                                db, project, actor, reader, payload, new_id, identities, bundle_id, origin)
                        else:
                            projection_hash = self._restore_note(db, project, actor, payload, new_id, identities, origin)
                        original_hash = payload["record"].get("content_hash", payload["record"].get("sha256"))
                        if kind in ("document", "note"):
                            original_hash = payload["versions"][-1]["content_hash"]
                        db.execute("INSERT INTO data_import_mappings VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                   (project, bundle_id, key, kind, item["source_id"], new_id, original_hash, projection_hash, Jsonb(origin)))
                        mappings.append({"object_id": key, "kind": kind, "old_id": item["source_id"], "new_id": new_id,
                                         "original_hash": original_hash, "projection_hash": projection_hash})
                # All document versions exist before creating fixed cross-record
                # references, so cycles between different historical revisions
                # never require a fabricated placeholder version.
                for key, item in known.items():
                    if item["kind"] == "document":
                        payload, new_id = payloads[key], new_ids[key]
                        for reference in payload.get("sources", []):
                            db.execute("INSERT INTO research_document_sources VALUES(%s,%s,%s,%s)",
                                       (project, new_id, reference["revision"], identities["source:" + reference["source_id"]]))
                        for reference in payload.get("refs", []):
                            db.execute("INSERT INTO research_document_refs VALUES(%s,%s,%s,%s,%s,%s)",
                                       (project, new_id, reference["revision"], identities["document:" + reference["record_id"]],
                                        reference["record_revision"], reference["block_id"]))
                self._fence(db, job)
                return {"bundle_id": str(bundle_id), "mappings": mappings, "readonly_objects": [k for k in reader.objects if k not in known],
                        "starts_running": False, "status": "records_restored"}

    def _verified_media(self, project, actor, known, payloads, guard, frozen_targets):
        existing = {}
        for key, item in known.items():
            if item["kind"] != "media":
                continue
            original = payloads[key]["record"]
            with authorized(self.database, project, actor) as db:
                row = db.execute("SELECT byte_length,blob_id FROM media_assets WHERE sha256=%s", (original["sha256"],)).fetchone()
                blob = db.execute("SELECT locator FROM stored_blobs WHERE id=%s", (row["blob_id"],)).fetchone() if row and row["blob_id"] else None
            if blob and {key: blob["locator"][key] for key in ("kind", "target_id", "config_revision", "host_id")} not in frozen_targets:
                raise Conflict("existing media source target changed after task admission; make a new restore task")
            if row and row["byte_length"] != original["byte_length"]:
                raise Conflict("existing media length conflicts with its imported byte identity")
            if row:
                try:
                    for _ in object_chunks(self.database, project, "media", original["sha256"], actor=actor_id(actor)):
                        guard()
                except (OSError, ValueError) as error:
                    raise ValueError("existing media original is unavailable or corrupt; no implicit replacement was performed") from error
            existing[original["sha256"]] = row
        return existing

    def _restore_binary(self, db, project, actor, job, reader, item, payload, new_id, prepared, origin, existing_media):
        kind, row = item["kind"], payload["record"]
        blob_id = self.database.blobs.attach(db, prepared)
        if kind == "artifact":
            metadata = deepcopy(row.get("metadata", {})) | {"import_origin": origin}
            if item.get("private") or row.get("metadata", {}).get("private"):
                metadata.update(private=True, private_actor_id=str(actor_id(actor)))
            db.execute("INSERT INTO artifacts(id,project_id,job_id,name,media_type,bytes,sha256,metadata,blob_id) "
                       "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                       (new_id, project, job["id"], row["name"], row["media_type"], row["bytes"], row["sha256"], Jsonb(metadata), blob_id))
            if not blob_id:
                for ordinal, chunk in enumerate(_parts(reader.chunks(payload["bytes_entry"]))):
                    db.execute("INSERT INTO artifact_chunks VALUES(%s,%s,%s,%s)", (project, new_id, ordinal, chunk))
        elif kind == "media":
            old = db.execute("SELECT byte_length,blob_id FROM media_assets WHERE sha256=%s FOR SHARE", (new_id,)).fetchone()
            if old != existing_media[new_id]:
                raise Conflict("existing media carrier changed after original-byte verification; retry explicitly")
            if not old:
                db.execute("INSERT INTO media_assets(project_id,sha256,byte_length,blob_id) VALUES(%s,%s,%s,%s)",
                           (project, new_id, row["byte_length"], blob_id))
                if not blob_id:
                    for ordinal, chunk in enumerate(_parts(reader.chunks(payload["bytes_entry"]), 1024**2)):
                        db.execute("INSERT INTO media_chunks VALUES(%s,%s,%s,%s)", (project, new_id, ordinal, chunk))
            elif old["byte_length"] != row["byte_length"]:
                raise Conflict("existing media byte identity conflicts with the import")
        elif kind == "note_asset":
            raw = b"".join(reader.chunks(payload["bytes_entry"]))
            self._validate_image(raw, row["mime"])
            db.execute("INSERT INTO note_assets(id,project_id,owner_id,name,mime,bytes,sha256,content,blob_id,created_at) "
                       "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                       (new_id, project, actor_id(actor), row["name"], row["mime"], row["bytes"], row["sha256"],
                        None if blob_id else raw, blob_id, row["created_at"]))
        else:
            from .species_library import inspect_bundle
            raw = b"".join(reader.chunks(payload["bytes_entry"]))
            manifest, _ = inspect_bundle(raw)
            old = db.execute("SELECT id FROM species_assets WHERE bundle_hash=%s", (row["bundle_hash"],)).fetchone()
            if old:
                new_id = str(old["id"])
            else:
                db.execute("INSERT INTO species_assets(id,project_id,actor_id,name,bundle_hash,manifest,bundle) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                           (new_id, project, actor_id(actor), manifest["name"], row["bundle_hash"], Jsonb(manifest), raw))
        return new_id, hashlib.sha256(canonical({"id": new_id, "origin": origin})).hexdigest()

    @staticmethod
    def _validate_image(raw, mime):
        import warnings

        from PIL import Image

        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                types = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
                if types.get(image.format) != mime or image.width * image.height > 16000000 or getattr(image, "n_frames", 1) != 1:
                    raise ValueError("invalid native note image recovery")
                image.verify()

    def _restore_source(self, db, project, actor, job, reader, payload, new_id, origin):
        source, request = payload["record"], payload["request"]
        provenance = {"origin": origin, "original_capture": request["provenance"], "management_job_id": str(job["id"]),
                      "management_job_kind": "data_restore", "meaning": "imported fixed evidence; no new experimental execution"}
        db.execute("INSERT INTO report_source_requests(id,project_id,actor_id,operation_id,request_hash,kind,job_id,selection,provenance,origin_bundle_id,origin_object_id) "
                   "VALUES(%s,%s,%s,%s,%s,%s,%s,'{}',%s,%s,%s)",
                   (new_id, project, actor_id(actor), uuid5(UUID(new_id), "capture-import"),
                    hashlib.sha256(canonical(payload)).hexdigest(), request["kind"], job["id"], Jsonb(provenance),
                    origin["origin_bundle_id"], origin["origin_object_id"]))
        checksum = hashlib.sha256()
        for row in reader.rows(payload["rows_entry"]):
            db.execute("INSERT INTO report_source_rows VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                       (project, new_id, row["ordinal"], row.get("time_us"), row["label"], row["quality"],
                        Jsonb(row["values"]), Jsonb(row["provenance"])))
            checksum.update(canonical(row))
        manifest = deepcopy(source["manifest"]) | {"import_origin": origin, "provenance": provenance}
        checksum.update(canonical(manifest))
        projection_hash = checksum.hexdigest()
        db.execute("INSERT INTO report_sources VALUES(%s,%s,%s,%s,%s,%s)",
                   (new_id, project, Jsonb(manifest), projection_hash, source["row_count"], source["created_at"]))
        return projection_hash

    def _restore_document(self, db, project, actor, payload, new_id, identities, origin):
        row = payload["record"]
        db.execute("INSERT INTO research_documents(id,project_id,kind,title,revision,archived_at,created_at,updated_at) "
                   "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                   (new_id, project, row["kind"], row["title"], row["revision"], row.get("archived_at"), row["created_at"], row["updated_at"]))
        for version in payload["versions"]:
            spec = _remap(version["spec"], identities)
            projection_hash = hashlib.sha256(canonical({"spec": spec, "review": version["review"], "origin": origin,
                                                        "original_hash": version["content_hash"]})).hexdigest()
            db.execute("INSERT INTO research_document_versions(project_id,document_id,revision,actor_id,operation_id,request_hash,spec,review,ai_call_id,content_hash,created_at,import_ai_generated) "
                       "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s)",
                       (project, new_id, version["revision"], actor_id(actor), uuid5(UUID(new_id), f"version:{version['revision']}"),
                        hashlib.sha256(canonical(version)).hexdigest(), Jsonb(spec), version["review"], projection_hash, version["created_at"],
                        str(version["revision"]) in origin["ai_generated_revisions"]))
        return projection_hash

    def _restore_note(self, db, project, actor, payload, new_id, identities, origin):
        from .note_schema import search_text

        row = payload["record"]
        last_body = _remap(payload["versions"][-1]["body"], identities)
        db.execute("INSERT INTO notes(id,project_id,owner_id,title,kind,collection_id,revision,search_text,archived_at,created_at,updated_at) "
                   "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                   (new_id, project, actor_id(actor), row["title"], row["kind"], identities.get("collection:" + str(row.get("collection_id"))),
                    row["revision"], search_text(last_body), row.get("archived_at"), row["created_at"], row["updated_at"]))
        for version in payload["versions"]:
            body, metadata = _remap(version["body"], identities), _remap(version["metadata"], identities)
            projection_hash = hashlib.sha256(canonical({"metadata": metadata, "body": body, "origin": origin,
                                                        "original_hash": version["content_hash"]})).hexdigest()
            db.execute("INSERT INTO note_versions VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                       (project, actor_id(actor), new_id, version["revision"], uuid5(UUID(new_id), f"version:{version['revision']}"),
                        hashlib.sha256(canonical(version)).hexdigest(), Jsonb(metadata), Jsonb(body), projection_hash, version["created_at"]))
        for reference in payload.get("asset_refs", []):
            db.execute("INSERT INTO note_asset_refs VALUES(%s,%s,%s,%s,%s)",
                       (project, actor_id(actor), new_id, reference["revision"], identities["note_asset:" + reference["asset_id"]]))
        return projection_hash

    def _adapter(self, reader, item, backend):
        try:
            return self._adapter_checked(reader, item, backend)
        except (ValueError, KeyError, TypeError, OSError, RuntimeError, zipfile.BadZipFile) as error:
            # A valid archival carrier may contain an invalid, unsupported or
            # unavailable specialized runtime. Keep the archive readable and
            # refuse continuation; never execute it to discover compatibility.
            return {"object_id": item["object_id"], "adapter": item.get("adapter"), "can_resume": False,
                    "blockers": ["specialized whole-system validation refused: " + str(error)[:800]],
                    "external_changes": [], "status": "read_only"}

    def _adapter_checked(self, reader, item, backend):
        if backend not in ("native", "reference"):
            raise ValueError("unknown explicit runtime backend")
        result = {"object_id": item["object_id"], "adapter": item.get("adapter"), "can_resume": False,
                  "blockers": [], "external_changes": [], "status": "read_only"}
        if SCHEMAS.get(item["kind"]) != item["schema"]:
            result["blockers"].append("unknown object schema cannot be natively restored or continued")
            return result
        if not item.get("adapter"):
            result["blockers"].append("no complete-system runtime restorer is registered for this object")
            return result
        if reader.preflight()["missing_required"]:
            result["blockers"].append("required recovery dependencies are missing")
            return result
        payload = reader.json(item["payload"])
        name = payload.get("bytes_entry")
        if name not in reader.files:
            result["blockers"].append("the complete specialized recovery bytes are unavailable")
            return result
        if item["adapter"] == "experiment":
            from .experiment_archive import ArchiveReader
            from .experiment_bundles import compatible
            from .provenance import capture_implementation

            with self._scratch() as stream:
                for chunk in reader.chunks(name):
                    stream.write(chunk)
                source = ArchiveReader(stream, check=reader.check)
                try:
                    source.verify()
                    result.update(compatible(source.manifest, capture_implementation(backend)))
                    self._experiment_boundary(source, backend, result)
                finally:
                    source.close()
            if result["can_resume"]:
                result["status"] = "validated_paused_restore_available"
        elif item["adapter"] == "language":
            from threemind_transformer.language_bundle import MAX_BYTES, unpack

            if reader.files[name]["bytes"] > MAX_BYTES:
                raise ValueError("language archive exceeds its existing validator budget")
            session, _ = unpack(b"".join(reader.chunks(name)), backend=backend)
            result["kernel_id"] = session.kernel_id
            if session.engine.life == "dead":
                result["blockers"].append("a dead language subject cannot be revived")
            else:
                result.update(can_resume=True, status="validated_paused_restore_available")
                result["external_changes"].append("future external model/device inputs are independently supplied on this host")
        elif item["adapter"] == "species":
            from .species_library import MAX_BYTES, inspect_bundle

            if reader.files[name]["bytes"] > MAX_BYTES:
                raise ValueError("species archive exceeds its existing validator budget")
            inspect_bundle(b"".join(reader.chunks(name)))
            result["blockers"].append("species inheritance creates a separately declared offspring; it is not subject continuation")
            result["can_restore_records"] = True
        else:
            result["blockers"].append("the declared adapter is not registered")
        return result

    @staticmethod
    def _experiment_boundary(source, backend, result):
        from threemind_runtime import ArtifactCodec, create_engine

        from .experiment_bundles import PENDING_KINDS
        from .inputs import digest
        from .protocols import RunSpec
        from .research_commands import parse_protocol

        run = source.json("run.json", maximum=64 * 1024**2)
        checkpoint = source.json("checkpoint.json", maximum=512 * 1024**2)
        spec = RunSpec(**run["spec"])
        result["kernel_id"] = spec.kernel_id
        context = checkpoint["context"]
        metadata = source.manifest["metadata"]
        if not context.get("initialized") or context.get("implementation") != metadata.get("implementation"):
            raise ValueError("checkpoint implementation is absent or differs from the runtime manifest")
        if (run.get("life") == "dead" or spec.study_id or run["revision"] != checkpoint["revision"]
            or str(run["id"]) != str(checkpoint["run_id"]) or context.get("language")):
            raise ValueError("the archive is not an independent live complete-system boundary")
        pending = source.json("pending-commands.json", maximum=16 * 1024**2)
        if not isinstance(pending, list) or any(
            c["kind"] not in PENDING_KINDS or c["payload"].get("device") or int(c["id"]) <= int(run["last_command"])
            for c in pending
        ):
            raise ValueError("unsupported or already consumed pending command")
        if any(row["status"] == "pending" for row in source.rows("evidence/research_operations.jsonl")):
            raise ValueError("uncommitted research operations prevent continuation")
        identities = set()
        for row in source.rows("evidence/input_envelopes.jsonl"):
            identities.add(row["id"])
            if len(identities) > 100000 or row["status"] == "accepted" and any(
                key in row["payload"] for key in ("device_session_id", "stream_session_id")
            ):
                raise ValueError("unsupported live device input or input identity budget exceeded")
        for name in ("evidence/input_frames.jsonl", "evidence/media_prepared_frames.jsonl"):
            if any(row["envelope_id"] not in identities for row in source.rows(name)):
                raise ValueError("an input frame has no original carrier")
        for plan in source.json("plans.json", maximum=16 * 1024**2):
            protocol = parse_protocol(plan["protocol"])
            if digest(protocol.model_dump()) != plan["protocol_hash"] or not 0 <= plan["next_step"] <= protocol.step_count:
                raise ValueError("original research plan protocol or cursor is inconsistent")
        for name in source.manifest["files"]:
            if name.startswith("media/") and name.endswith("/metadata.json"):
                asset = source.json(name)
                body = source.manifest["files"].get(name.removesuffix("metadata.json") + "body", {})
                if body.get("sha256") != asset["sha256"] or body.get("bytes") != int(asset["byte_length"]):
                    raise ValueError("original sensory media dependency is incomplete")
                result.setdefault("source_media", []).append(asset["sha256"])
        image = ArtifactCodec.decode(source.read("model.tmind", maximum=512 * 1024**2), max_bytes=512 * 1024**2)
        if image.digest != metadata["state_hash"] or image.digest != checkpoint["state_hash"]:
            raise ValueError("whole-system model hash differs from checkpoint and manifest")
        create_engine(state=image, backend=backend, kernel_id=spec.kernel_id)
        if any(v.get("enabled") for key, v in run["spec"].items() if "telemetry" in key and isinstance(v, dict)):
            result["external_changes"].append("future telemetry input conditions require explicit acknowledgement")
        result["can_resume"] = not result["blockers"]

    def resume_plan(self, project, actor, bundle_id, object_id, backend="native"):
        with self._open(project, actor, bundle_id) as reader:
            self._validate_records(reader)
            item = reader.objects.get(object_id)
            if not item:
                raise NotFound("runtime origin object is unavailable")
            return self._adapter(reader, item, backend) | {"bundle_id": str(bundle_id), "backend": backend,
                                                         "starts_running": False, "restored_status": "paused"}

    def resume(self, project, actor, bundle_id, object_id, op_id, name="Imported subject", acknowledge_external_changes=False, backend="native"):
        if not isinstance(name, str) or not 1 <= len(name) <= 160:
            raise ValueError("a bounded restored subject name is required")
        plan = self.resume_plan(project, actor, bundle_id, object_id, backend)
        if not plan["can_resume"]:
            raise Conflict("; ".join(plan["blockers"]))
        if plan["external_changes"] and not acknowledge_external_changes:
            raise Conflict("acknowledge the actual external conditions before explicit paused restoration")
        kernel_id = plan["kernel_id"]
        return self._queue(project, actor, "data_resume", {"bundle_id": str(bundle_id), "object_id": object_id,
                           "adapter": plan["adapter"], "backend": backend, "name": name,
                           "kernel_id": kernel_id, "kernel_feature": kernel_feature(kernel_id),
                           "source_media": plan.get("source_media", []),
                           "acknowledge_external_changes": bool(acknowledge_external_changes)}, op_id)

    def _resume_job(self, worker, job):
        self._job_actor(job)
        project, params = job["project_id"], job["params"]
        actor, bundle_id = params["actor_id"], params["bundle_id"]
        if params["backend"] != worker.backend:
            raise Conflict("the claimed worker backend does not match the explicit resume plan")
        guard = TransferGuard(self.database, job)
        with self._open(project, actor, bundle_id, check=guard) as reader:
            self._validate_records(reader)
            item = reader.objects[params["object_id"]]
            conditions = self._adapter(reader, item, worker.backend)
            if not conditions["can_resume"]:
                raise Conflict("; ".join(conditions["blockers"]))
            if conditions["external_changes"] and not params["acknowledge_external_changes"]:
                raise Conflict("actual external condition changes were not acknowledged")
            payload = reader.json(item["payload"])
            operation_id = UUID(params["operation_id"])
            if conditions["adapter"] == "language":
                from .language_archive import import_bundle

                raw = b"".join(reader.chunks(payload["bytes_entry"]))
                identity = uuid5(operation_id, f"data-language:{project}:{actor}")
                result = import_bundle(self.database, project, actor, identity, params["name"], raw,
                                       backend=worker.backend, job=job)
                return result | {"status": "paused", "origin_bundle_id": str(bundle_id), "origin_object_id": item["object_id"]}
            if conditions["adapter"] != "experiment":
                raise Conflict("no subject continuation is registered for this adapter")
            from types import SimpleNamespace

            from .experiment_archive import ArchiveReader
            from .experiment_bundles import resume_bundle

            inner_id = uuid5(UUID(str(job["id"])), "experiment-origin")
            upload_id = uuid5(UUID(str(job["id"])), "experiment-upload")
            with self._scratch() as stream:
                for chunk in reader.chunks(payload["bytes_entry"]):
                    stream.write(chunk)
                size, sha = stream_hash(stream)
                source = ArchiveReader(stream, check=guard)
                try:
                    manifest = source.verify()
                finally:
                    source.close()
                with authorized(self.database, project, actor, write=True) as db:
                    self._fence(db, job)
                    existing = db.execute("SELECT id FROM experiment_bundles WHERE id=%s", (inner_id,)).fetchone()
                    if not existing:
                        private = self._get(db, bundle_id)["private"]
                        db.execute("INSERT INTO bundle_uploads(id,project_id,actor_id,request_id,name,bytes,sha256,status,job_id) "
                                   "VALUES(%s,%s,%s,%s,%s,%s,%s,'ready',%s)",
                                   (upload_id, project, actor_id(actor), uuid5(operation_id, "experiment-upload"), params["name"], size, sha, job["id"]))
                        stream.seek(0)
                        ordinal = 0
                        while chunk := stream.read(CHUNK):
                            db.execute("INSERT INTO bundle_upload_chunks VALUES(%s,%s,%s,%s,%s)",
                                       (project, upload_id, ordinal, hashlib.sha256(chunk).hexdigest(), chunk))
                            ordinal += 1
                        db.execute("INSERT INTO experiment_bundles(id,project_id,actor_id,name,job_id,upload_id,sha256,bytes,manifest,private,origin_data_bundle_id) "
                                   "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                   (inner_id, project, actor_id(actor), params["name"], job["id"], upload_id, sha, size, Jsonb(manifest), private, bundle_id))
            scoped = _ActorDatabase(self.database, actor)
            adapted_worker = SimpleNamespace(db=scoped, backend=worker.backend, implementation=worker.implementation)
            adapted_job = job | {"params": params | {"bundle_id": str(inner_id), "request_id": str(operation_id),
                                                       "data_bundle_id": str(bundle_id)}}
            result = resume_bundle(adapted_worker, adapted_job)
            return result | {"origin_bundle_id": str(bundle_id), "origin_object_id": item["object_id"], "starts_running": False}


def execute(worker, job):
    service = DataBundles(worker.db)
    if job["kind"] == "data_export":
        return service._export_job(worker, job)
    if job["kind"] == "data_restore":
        return service._restore_job(worker, job)
    if job["kind"] == "data_resume":
        return service._resume_job(worker, job)
    raise ValueError("unsupported formal data task")


def _remap(value, identities, key=""):
    if isinstance(value, dict):
        return {k: _remap(v, identities, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_remap(v, identities, key) for v in value]
    if not isinstance(value, str):
        return value
    kind = {"source": "source", "sources": "source", "record_id": "document", "collection_id": "collection"}.get(key)
    if kind and kind + ":" + value in identities:
        return identities[kind + ":" + value]
    # Rewrite only the registered local link namespace. Ordinary prose,
    # numerical state, code snippets and original origin bytes remain intact.
    pattern = re.compile(r"/api/v2/projects/([0-9a-fA-F-]{36})/(artifacts|note-assets|report-sources|media|documents|notes)/([0-9a-fA-F-]{36}|[0-9a-f]{64})(?![0-9a-fA-F-])")
    families = {"artifacts": "artifact", "note-assets": "note_asset", "report-sources": "source", "media": "media", "documents": "document", "notes": "note"}
    def link(match):
        mapped = identities.get(families[match[2]] + ":" + match[3])
        if match[1] not in identities or mapped is None:
            return match[0]
        return f"/api/v2/projects/{identities[match[1]]}/{match[2]}/{mapped}"
    if key not in ("markdown", "text", "href", "src"):
        return value
    if key in ("markdown", "text"):
        pieces = re.split(r"(```[\s\S]*?```|~~~[\s\S]*?~~~|`+[^`\n]*`+)", value)
        return "".join(piece if index % 2 else pattern.sub(link, piece) for index, piece in enumerate(pieces))
    return pattern.sub(link, value)


class _ActorDatabase:
    """Keep private nested archives private through the existing restorer."""
    def __init__(self, database, actor):
        self.database, self.actor = database, actor

    @contextmanager
    def tx(self, project=None, **kwargs):
        with self.database.tx(project, **kwargs) as db:
            db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(self.actor),))
            yield db

    def __getattr__(self, name):
        return getattr(self.database, name)
