"""Bounded, authorized views and fixed transfer snapshots of existing Lab facts.

Scientific state remains in its existing tables. Snapshots here are immutable
transfer evidence, and never authorize a generic coordinator/runtime restore.
"""

from __future__ import annotations

import base64
import hashlib
import re
from contextlib import contextmanager
from datetime import datetime
from tempfile import TemporaryFile
from uuid import UUID, uuid4

from psycopg import sql
from psycopg.types.json import Jsonb

from . import permissions
from .database import Conflict, Forbidden, NotFound
from .database_stream import stream_rows
from .experiment_archive import CHUNK, canonical, safe_name
from .storage_files import checked_path

MAX_OBJECTS = 10000
MAX_SNAPSHOT = 512 * 1024**2
MAX_ROWS = 2_000_000

# An explicit registry excludes credentials, grants, live device connections and
# service processes. These tables are archival data, not executable SQL input.
RUN_TABLES = (
    "checkpoints", "state_chunks", "nodes", "edges", "events", "observations", "commands",
    "input_envelopes", "input_frames", "conversation_entries", "state_captures", "model_metadata_history",
    "research_operations", "research_plans", "development_sessions", "language_sessions", "language_turns",
    "media_prepared_frames",
)
CAMPAIGN_TABLES = {
    "evolution": ("evolution_campaigns", "evolution_members", "evolution_selections", "evolution_events"),
    "ecology": ("ecology_campaigns", "ecology_members", "ecology_checkpoints", "ecology_checkpoint_members",
                "ecology_events", "ecology_observer_revisions", "ecology_observers", "ecology_observer_entries"),
    "assessment": ("assessment_batches", "assessment_members", "assessment_actions"),
}
TABLES = {
    "experiment": "research_experiments",
    "run": "runs", "study": "studies", "document": "research_documents", "note": "notes",
    "source": "report_sources", "artifact": "artifacts", "media": "media_assets",
    "species": "species_assets", "experiment_bundle": "experiment_bundles",
    "evolution": "evolution_campaigns", "ecology": "ecology_campaigns", "assessment": "assessment_batches",
    "world": "world_documents", "probe": "probe_calibrations",
    "note_asset": "note_assets", "collection": "note_collections",
    "innate": "innate_versions",
}
SCHEMAS = {kind: "threemind.data." + kind + "/1" for kind in TABLES}
NATIVE = {"experiment", "document", "note", "note_asset", "collection", "source", "artifact", "media", "species"}


def actor_id(actor):
    return UUID(str(actor["id"] if isinstance(actor, dict) else actor))


def wire(value):
    if isinstance(value, dict):
        return {k: wire(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [wire(v) for v in value]
    if isinstance(value, (bytes, memoryview)):
        return {"$bytes": base64.b64encode(value).decode("ascii")}
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


@contextmanager
def authorized(database, project, actor, *, write=False, repeatable=False):
    principal = permissions.resolve_actor(database, actor)
    action = principal.get("_request_action")
    if not action:
        action = "data.manage" if write else "data.read"
    permissions.project_access(database, principal, project, write=write, action=action)
    with database.tx(project, repeatable=repeatable) as db:
        permissions.set_context(db, principal, project, action=action)
        db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(principal["id"]),))
        yield db


CATALOG = """
SELECT 'run'::text AS kind,id::text,name,'individual'::text AS type,'db'::text AS backend,
       created_at,archived_at,to_jsonb(tags) AS tags,spec->>'study_id' AS experiment,
       id::text AS individual,NULL::text AS batch,0::bigint AS bytes,state_hash AS sha256 FROM runs
UNION ALL SELECT 'experiment',id::text,title,classification,'db',created_at,NULL,'[]',id::text,NULL,NULL,0,content_hash FROM research_experiments
UNION ALL SELECT 'study',id::text,name,'experiment','db',created_at,NULL,'[]',id::text,NULL,NULL,0,protocol_hash FROM studies
UNION ALL SELECT 'document',id::text,title,kind,'db',created_at,archived_at,'[]',NULL,NULL,NULL,0,NULL FROM research_documents
UNION ALL SELECT 'note',id::text,title,kind,'db',created_at,archived_at,'[]',NULL,NULL,NULL,0,NULL FROM notes
UNION ALL SELECT 'artifact',a.id::text,a.name,coalesce(a.metadata->>'kind','artifact'),
  coalesce(b.locator->>'kind','db'),a.created_at,NULL,coalesce(a.metadata->'tags','[]'),
  coalesce(a.metadata->>'experiment',r.spec->>'study_id'),j.run_id::text,a.metadata->>'batch',a.bytes,a.sha256
  FROM artifacts a JOIN jobs j ON j.id=a.job_id LEFT JOIN runs r ON r.id=j.run_id LEFT JOIN stored_blobs b ON b.id=a.blob_id
UNION ALL SELECT 'media',a.sha256,a.sha256,'media',coalesce(b.locator->>'kind','db'),a.created_at,NULL,'[]',NULL,NULL,NULL,
  a.byte_length,a.sha256 FROM media_assets a LEFT JOIN stored_blobs b ON b.id=a.blob_id
UNION ALL SELECT 'source',s.id::text,r.kind,'source','db',s.created_at,NULL,'[]',NULL,r.run_id::text,
  r.assessment_id::text,0,s.content_hash FROM report_sources s JOIN report_source_requests r ON r.id=s.id
UNION ALL SELECT 'species',id::text,name,'species','db',created_at,NULL,'[]',NULL,NULL,NULL,octet_length(bundle),bundle_hash FROM species_assets
UNION ALL SELECT 'experiment_bundle',id::text,name,'experiment_bundle','db',created_at,NULL,'[]',NULL,
  manifest#>>'{metadata,run_id}',NULL,bytes,sha256 FROM experiment_bundles
UNION ALL SELECT 'evolution',id::text,name,'population','db',created_at,NULL,'[]',id::text,NULL,id::text,0,NULL FROM evolution_campaigns
UNION ALL SELECT 'ecology',id::text,name,'population','db',created_at,NULL,'[]',id::text,NULL,id::text,0,NULL FROM ecology_campaigns
UNION ALL SELECT 'assessment',id::text,name,'batch','db',created_at,NULL,'[]',id::text,NULL,id::text,0,NULL FROM assessment_batches
UNION ALL SELECT 'world',id::text,title,'world','db',created_at,NULL,'[]',NULL,NULL,NULL,0,NULL FROM world_documents
UNION ALL SELECT 'probe',id::text,'Probe '||id::text,'experiment','db',created_at,NULL,'[]',id::text,run_id::text,NULL,0,NULL FROM probe_calibrations
UNION ALL SELECT 'innate',id::text,name,'innate','db',created_at,NULL,'[]',NULL,run_id::text,NULL,0,state_hash FROM innate_versions
"""


class DataCatalog:
    def __init__(self, database):
        self.database = database

    def _list(self, db, filters, offset, limit):
        filters = dict(filters or {})
        aliases = {"q": "query", "run": "individual", "population": "experiment", "dataset": "batch",
                   "after": "from", "before": "through"}
        for original, normalized in aliases.items():
            if original in filters:
                filters[normalized] = filters.pop(original)
        if filters.get("kind") in ("report", "record"):
            filters["type"], filters["kind"] = filters["kind"], "document"
        allowed = {"kind", "type", "backend", "experiment", "individual", "batch", "tag", "query", "from", "through", "archived"}
        if set(filters) - allowed or not 0 <= offset <= 100000 or not 1 <= limit <= MAX_OBJECTS:
            raise ValueError("invalid data catalog filter or pagination budget")
        conditions, arguments = [], []
        for key in ("kind", "type", "backend", "experiment", "individual", "batch"):
            if filters.get(key):
                conditions.append(key + "=%s")
                arguments.append(str(filters[key]))
        if filters.get("tag"):
            conditions.append("tags ? %s")
            arguments.append(str(filters["tag"]))
        if filters.get("query"):
            conditions.append("strpos(lower(name),lower(%s))>0")
            arguments.append(str(filters["query"]))
        for key, operator in (("from", ">="), ("through", "<=")):
            if filters.get(key):
                value = datetime.fromisoformat(str(filters[key]))
                if value.tzinfo is None:
                    raise ValueError("catalog time filters must include a timezone")
                conditions.append("created_at" + operator + "%s")
                arguments.append(value)
        if filters.get("archived", "all") != "all":
            if filters["archived"] not in ("active", "archived"):
                raise ValueError("invalid archive filter")
            conditions.append("(archived_at IS NOT NULL)=%s")
            arguments.append(filters["archived"] == "archived")
        return db.execute(
            "WITH resources AS (" + CATALOG + ") SELECT * FROM resources WHERE "
            + (" AND ".join(conditions) or "true") + " ORDER BY created_at DESC,kind,id LIMIT %s OFFSET %s",
            tuple(arguments) + (limit + 1, offset),
        ).fetchall()

    def list(self, project, actor, filters=None, offset=0, limit=50):
        if not 1 <= limit <= 200:
            raise ValueError("catalog pages are limited to 200 resources")
        with authorized(self.database, project, actor) as db:
            rows = self._list(db, filters, offset, limit)
        return {"rows": rows[:limit], "more": len(rows) > limit, "offset": offset, "limit": limit}

    def _record(self, db, kind, identity, *, compact=False):
        kind = "document" if kind in ("report", "record") else kind
        if kind not in TABLES:
            raise ValueError("unknown resource kind")
        column = "sha256" if kind == "media" else "id"
        fields = "*"
        if kind == "species":
            fields = "id,project_id,actor_id,name,bundle_hash,manifest,created_at,octet_length(bundle) AS bytes"
        elif kind == "note_asset":
            fields = "id,project_id,owner_id,name,mime,bytes,sha256,blob_id,created_at"
        elif kind == "source" and compact:
            fields = "id,project_id,content_hash,row_count,created_at,jsonb_build_object('schema',manifest->'schema','kind',manifest->'kind') AS manifest"
        row = db.execute(sql.SQL("SELECT {} FROM {} WHERE {}=%s").format(
            sql.SQL(fields), sql.Identifier(TABLES[kind]), sql.Identifier(column)), (identity,)).fetchone()
        if not row:
            raise NotFound("data resource is unavailable")
        return row

    def detail(self, project, actor, kind, id):
        kind = "document" if kind in ("report", "record") else kind
        with authorized(self.database, project, actor) as db:
            record = self._record(db, kind, id, compact=True)
            result = {"kind": kind, "id": str(id), "schema": SCHEMAS[kind], "record": record,
                      "can_view": True, "can_restore_records": kind in NATIVE, "can_resume": False}
            if kind in ("document", "note"):
                table, foreign = ("research_document_versions", "document_id") if kind == "document" else ("note_versions", "note_id")
                result["versions"] = db.execute(sql.SQL(
                    "SELECT revision,content_hash,created_at FROM {} WHERE {}=%s ORDER BY revision DESC LIMIT 201"
                ).format(sql.Identifier(table), sql.Identifier(foreign)), (id,)).fetchall()
                result["more_versions"] = len(result["versions"]) > 200
                result["versions"] = result["versions"][:200]
            if kind == "source":
                result["request"] = db.execute("SELECT id,kind,job_id,actor_id,created_at,origin_bundle_id,origin_object_id FROM report_source_requests WHERE id=%s", (id,)).fetchone()
                result["content_mode"] = "index_metadata; full fixed rows and original provenance require explicit reading"
                result["can_restore_records"] = True
            result["references"] = {"known": True, "blocks_cleanup": kind in ("source", "document", "note", "run"),
                                    "meaning": "permanent cleanup must recheck the existing reference constraints"}
            return result

    def plan(self, project, actor, plan_id):
        with authorized(self.database, project, actor) as db:
            row = db.execute("SELECT * FROM data_export_plans WHERE id=%s AND actor_id=%s", (plan_id, actor_id(actor))).fetchone()
            if not row:
                raise NotFound("export plan is unavailable to this actor")
            return row["snapshot"] | {"id": row["id"], "created_at": row["created_at"], "selection": row["selection"]}

    def export_plan(self, project, actor, selection, op_id=None):
        selection = wire(dict(selection or {}))
        op_id = UUID(str(op_id)) if op_id else uuid4()
        fingerprint = hashlib.sha256(canonical(selection)).hexdigest()
        with authorized(self.database, project, actor, write=True, repeatable=True) as db:
            db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,61))", (f"data-plan:{project}:{actor_id(actor)}:{op_id}",))
            old = db.execute("SELECT * FROM data_export_plans WHERE actor_id=%s AND operation_id=%s",
                             (actor_id(actor), op_id)).fetchone()
            if old:
                if old["fingerprint"] != fingerprint:
                    raise Conflict("export request identity belongs to different selection")
                return old["snapshot"] | {"id": old["id"], "created_at": old["created_at"], "selection": old["selection"]}
            plan_id = uuid4()
            db.execute("INSERT INTO data_export_plans(id,project_id,actor_id,operation_id,fingerprint,selection,snapshot) "
                       "VALUES(%s,%s,%s,%s,%s,%s,'{}')",
                       (plan_id, project, actor_id(actor), op_id, fingerprint, Jsonb(selection)))
            created_at = db.execute("SELECT created_at FROM data_export_plans WHERE id=%s", (plan_id,)).fetchone()["created_at"]
            builder = _SnapshotBuilder(self, db, project, actor, plan_id)
            selected = selection.get("resources")
            if selected is None and selection.get("ids"):
                selected = [{"kind": selection["kind"], "id": identity} for identity in selection["ids"]]
            if selected is None:
                filters = selection.get("filters")
                if filters is None:
                    filters = {k: v for k, v in selection.items() if k not in ("name", "scope", "include_notes")}
                rows = self._list(db, filters, 0, MAX_OBJECTS)
                if len(rows) > MAX_OBJECTS:
                    raise ValueError("export scope exceeds object budget; select a narrower explicit scope")
                selected = [{"kind": r["kind"], "id": r["id"]} for r in rows]
            if not isinstance(selected, list) or not 1 <= len(selected) <= MAX_OBJECTS:
                raise ValueError("select a nonempty bounded set of data resources")
            for item in selected:
                builder.capture(item["kind"], item["id"])
            snapshot = {
                "schema": "threemind.data-export-plan/1", "source_project": str(project),
                "source_actor": str(actor_id(actor)), "scope": "repeatable-read committed facts and immutable byte identities",
                "snapshot_id": db.execute("SELECT pg_current_snapshot()::text AS id").fetchone()["id"],
                "objects": list(builder.objects.values()), "files": builder.files, "bytes": builder.total_bytes,
                "private": builder.private, "blockers": [], "limitations": builder.limitations,
                "complete_history": True, "generic_runtime_restore": False,
                "selection_boundary": "filters select resource heads; every selected record keeps all committed historical versions and required dependencies",
            }
            db.execute("UPDATE data_export_plans SET snapshot=%s WHERE id=%s", (Jsonb(snapshot), plan_id))
            return snapshot | {"id": plan_id, "selection": selection, "created_at": created_at}


class _SnapshotBuilder:
    def __init__(self, catalog, db, project, actor, plan_id):
        self.catalog, self.db, self.project, self.actor, self.plan_id = catalog, db, project, actor, plan_id
        self.objects, self.files, self.total_bytes, self.snapshot_bytes = {}, [], 0, 0
        self.private, self.limitations = False, []

    def _snapshot(self, name, values):
        safe_name(name)
        directory = checked_path(self.catalog.database.blobs.storage.control_dir / "data-snapshots")
        directory.mkdir(parents=True, exist_ok=True)
        digest, size = hashlib.sha256(), 0
        # Consume the snapshot cursor before issuing writes on its connection,
        # and use bounded memory even for hundreds of MiB of immutable rows.
        with TemporaryFile(dir=directory) as temporary:
            iterator = iter(values)
            try:
                for value in iterator:
                    size += len(value)
                    self.snapshot_bytes += len(value)
                    if self.snapshot_bytes > MAX_SNAPSHOT:
                        raise ValueError("fixed snapshot exceeds 512 MiB; narrow the export selection")
                    digest.update(value)
                    temporary.write(value)
            finally:
                close = getattr(iterator, "close", None)
                if close:
                    close()
            self._file(name, size, digest.hexdigest(), {"kind": "snapshot"})
            temporary.seek(0)
            ordinal = 0
            while part := temporary.read(CHUNK):
                self.db.execute("INSERT INTO data_plan_chunks VALUES(%s,%s,%s,%s,%s)",
                                (self.project, self.plan_id, name, ordinal, part))
                ordinal += 1
        return name

    def _file(self, name, size, sha, recipe, **pins):
        self.db.execute("INSERT INTO data_plan_files(project_id,plan_id,name,bytes,sha256,recipe,artifact_id,media_sha256,note_asset_id) "
                        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (self.project, self.plan_id, name, size, sha, Jsonb(recipe), pins.get("artifact"),
                         pins.get("media"), pins.get("note_asset")))
        self.files.append({"name": name, "bytes": int(size), "sha256": sha})
        self.total_bytes += int(size)
        if self.total_bytes > 160 * 1024**3:
            raise ValueError("export plan exceeds the formal total expanded-byte budget; narrow the selection")
        return name

    def _rows(self, table, where, params):
        for count, row in enumerate(stream_rows(self.db, sql.SQL("SELECT * FROM {} WHERE ").format(sql.Identifier(table)) + where, params, batch=100), 1):
            raw = canonical(wire(row)) + b"\n"
            if count > MAX_ROWS or len(raw) > 16 * 1024**2:
                raise ValueError("data snapshot exceeds row budget")
            yield raw

    def capture(self, kind, identity):
        kind = "document" if kind in ("report", "record") else kind
        identity = str(identity)
        object_id = kind + ":" + identity
        if object_id in self.objects:
            return object_id
        if len(self.objects) >= MAX_OBJECTS:
            raise ValueError("dependency closure exceeds object budget")
        row = self.catalog._record(self.db, kind, identity)
        private = bool(row.get("private"))
        if kind == "artifact":
            private = private or bool(row.get("metadata", {}).get("private")) or bool(self.db.execute(
                "SELECT 1 FROM data_private_carriers WHERE kind='artifact' AND carrier_id=%s LIMIT 1", (identity,)).fetchone())
        self.private = self.private or private
        slug = hashlib.sha256(object_id.encode()).hexdigest()[:32]
        descriptor = {"object_id": object_id, "kind": kind, "schema": SCHEMAS[kind], "source_id": identity,
                      "source_project": str(self.project), "payload": f"objects/{slug}/record.json",
                      "dependencies": [], "can_restore_records": kind in NATIVE, "can_resume": False}
        if private:
            descriptor["private"] = True
        self.objects[object_id] = descriptor
        payload = {"record": wire(row)}

        def depend(dependent_kind, dependent_id, *, mode=None):
            key = self.capture(dependent_kind, dependent_id)
            if key not in {d["object_id"] for d in descriptor["dependencies"]}:
                descriptor["dependencies"].append({"object_id": key, "required": True} | ({"mode": mode} if mode else {}))
            return key

        if kind == "experiment":
            native = row['spec']['metadata']
            if not native.get('import_origin') and native.get('entry') == 'platform-execution' and native.get('runtime_kind') in ('study', *CAMPAIGN_TABLES):
                depend(native['runtime_kind'], native['runtime_id'], mode='read_only_origin')
            payload['entries'] = wire(self.db.execute('SELECT * FROM research_record_entries WHERE experiment_id=%s ORDER BY recorded_at,id', (identity,)).fetchall())
            rows = self.db.execute('SELECT * FROM research_record_evidence WHERE experiment_id=%s ORDER BY logical_id', (identity,)).fetchall()
            # Invisible personal references must not silently masquerade as a
            # complete export. The FK table knows their existence without leaking
            # text, titles or identities to the requesting actor.
            hidden = self.db.execute('SELECT EXISTS(SELECT 1 FROM research_record_private_counts WHERE experiment_id=%s AND actor_id<>%s) AS yes', (identity, actor_id(self.actor))).fetchone()['yes']
            if hidden and not permissions.resolve_actor(self.catalog.database, self.actor).get("superadmin"):
                raise Forbidden('experiment includes another author\'s private references; export your visible records separately')
            payload['evidence'] = wire(rows)
            for entry in payload['evidence']:
                location = entry['locator']
                if location['kind'] in ('document', 'note', 'artifact'):
                    depend(location['kind'], location['id'])
                elif location['kind'] in ('file', 'package'):
                    if entry['byte_count'] is None or not entry['sha256']:
                        raise Conflict('file evidence lacks a fixed size/hash; verify and register it before export')
                    file = f'objects/{slug}/originals/{entry["id"]}'
                    self._file(file, entry['byte_count'], entry['sha256'], {'kind': 'research-evidence', 'id': entry['id']})
                    entry['bytes_entry'] = file
                elif location['kind'] in ('run', 'checkpoint'):
                    run_id = entry.get('run_id')
                    if location['kind'] == 'checkpoint':
                        run_id = self.db.execute('SELECT run_id FROM checkpoints WHERE id=%s', (location['id'],)).fetchone()['run_id']
                    depend('run', run_id, mode='read_only_origin')
                elif location['kind'] == 'missing':
                    self.limitations.append(f'{object_id}: missing original {entry["logical_id"]}; metadata is preserved, bytes cannot be reconstructed')
                self.private = self.private or bool(entry.get('private_actor_id'))
            self.limitations.append(f'{object_id}: restores research index and original evidence, never starts an experimental subject')
        elif kind == "document":
            self._history_budget("research_document_versions", "document_id", "spec", identity)
            versions = self.db.execute("SELECT * FROM research_document_versions WHERE document_id=%s ORDER BY revision", (identity,)).fetchall()
            payload["versions"] = wire(versions)
            payload["ai_generated_revisions"] = [str(v["revision"]) for v in versions
                if v.get("ai_call_id") or v.get("import_ai_generated")]
            payload["sources"] = wire(self.db.execute("SELECT * FROM research_document_sources WHERE document_id=%s ORDER BY revision,source_id", (identity,)).fetchall())
            payload["refs"] = wire(self.db.execute("SELECT * FROM research_document_refs WHERE document_id=%s ORDER BY revision,record_id", (identity,)).fetchall())
            for entry in payload["sources"]:
                depend("source", entry["source_id"])
            for entry in payload["refs"]:
                depend("document", entry["record_id"])
            self._link_dependencies(payload, depend)
        elif kind == "note":
            self.private = True
            self._history_budget("note_versions", "note_id", "body", identity)
            payload["versions"] = wire(self.db.execute("SELECT * FROM note_versions WHERE note_id=%s ORDER BY revision", (identity,)).fetchall())
            payload["asset_refs"] = wire(self.db.execute("SELECT * FROM note_asset_refs WHERE note_id=%s ORDER BY revision,asset_id", (identity,)).fetchall())
            if row["collection_id"]:
                depend("collection", row["collection_id"])
            for entry in payload["asset_refs"]:
                depend("note_asset", entry["asset_id"])
            for version in payload["versions"]:
                collection = version["metadata"].get("collection_id")
                if collection:
                    depend("collection", collection)
            self._link_dependencies(payload, depend)
        elif kind in ("artifact", "media", "note_asset", "species", "experiment_bundle"):
            file = f"objects/{slug}/bytes"
            if kind == "species":
                binary = self.db.execute("SELECT bundle FROM species_assets WHERE id=%s", (identity,)).fetchone()["bundle"]
                self._snapshot(file, [bytes(binary)])
                descriptor["adapter"] = "species"
            elif kind == "experiment_bundle":
                # Pin the actual carrier, not the current export policy.
                if row["artifact_id"]:
                    depend("artifact", row["artifact_id"])
                    carrier = self.catalog._record(self.db, "artifact", row["artifact_id"])
                    self._file(file, row["bytes"], row["sha256"], {"kind": "artifact", "id": str(row["artifact_id"]),
                        "blob_id": str(carrier["blob_id"]) if carrier.get("blob_id") else None}, artifact=row["artifact_id"])
                else:
                    self._snapshot(file, (bytes(r["body"]) for r in stream_rows(self.db,
                        "SELECT body FROM bundle_upload_chunks WHERE upload_id=%s ORDER BY ordinal", (row["upload_id"],), batch=1)))
                descriptor["adapter"] = "experiment"
                descriptor["can_restore_records"] = False
                descriptor["can_resume"] = True  # The dedicated validator still decides actual eligibility.
            else:
                size = row["byte_length"] if kind == "media" else row["bytes"]
                self._file(file, size, row["sha256"], {"kind": kind, "id": identity,
                    "blob_id": str(row["blob_id"]) if row.get("blob_id") else None}, **{kind: identity})
                if kind == "note_asset":
                    self.private = True
                if row.get("blob_id"):
                    self.db.execute("INSERT INTO blob_backup_leases(backup_id,blob_id,project_id) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                                    (self.plan_id, row["blob_id"], self.project))
                if kind == "artifact" and row.get("metadata", {}).get("kind") == "language-bundle":
                    descriptor["adapter"] = "language"
                    descriptor["can_resume"] = True
            payload["bytes_entry"] = file
        elif kind == "source":
            request = self.db.execute("SELECT * FROM report_source_requests WHERE id=%s", (identity,)).fetchone()
            payload["request"] = wire(request)
            payload["execution"] = self._execution(request["job_id"])
            payload["rows_entry"] = self._snapshot(f"objects/{slug}/rows.jsonl", self._rows(
                "report_source_rows", sql.SQL("source_id=%s ORDER BY ordinal"), (identity,)))
            if request.get("analysis_artifact_id"):
                depend("artifact", request["analysis_artifact_id"])
            if request.get("calibration_id"):
                depend("probe", request["calibration_id"], mode="read_only_origin")
            self._link_dependencies(payload, depend)
        elif kind == "run":
            payload["tables"] = {}
            for table in RUN_TABLES:
                if table == "state_chunks":
                    where = sql.SQL("checkpoint_id IN (SELECT id FROM checkpoints WHERE run_id=%s) ORDER BY checkpoint_id,ordinal")
                else:
                    where = sql.SQL("run_id=%s")
                payload["tables"][table] = self._snapshot(f"objects/{slug}/{table}.jsonl", self._rows(table, where, (identity,)))
            payload["checkpoint_payloads"] = []
            for checkpoint in self.db.execute(
                "SELECT c.id,c.blob_id,b.bytes,b.sha256 FROM checkpoints c JOIN stored_blobs b ON b.id=c.blob_id "
                "WHERE c.run_id=%s ORDER BY c.id", (identity,),
            ).fetchall():
                file = f"objects/{slug}/checkpoint-payloads/{checkpoint['id']}"
                self._file(file, checkpoint["bytes"], checkpoint["sha256"], {
                    "kind": "checkpoint-payload", "id": str(checkpoint["id"]),
                    "run_id": identity, "blob_id": str(checkpoint["blob_id"]),
                })
                self.db.execute(
                    "INSERT INTO blob_backup_leases(backup_id,blob_id,project_id) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                    (self.plan_id, checkpoint["blob_id"], self.project),
                )
                payload["checkpoint_payloads"].append({"checkpoint_id": str(checkpoint["id"]), "bytes_entry": file})
            for asset in self.db.execute("SELECT DISTINCT asset_sha256 FROM input_envelopes WHERE run_id=%s AND asset_sha256 IS NOT NULL", (identity,)).fetchall():
                depend("media", asset["asset_sha256"])
            for session in self.db.execute("SELECT assets FROM language_sessions WHERE run_id=%s", (identity,)).fetchall():
                for asset in session["assets"].values():
                    if asset:
                        depend("artifact", asset)
            for session in self.db.execute("SELECT source_version_id FROM development_sessions WHERE run_id=%s AND source_version_id IS NOT NULL", (identity,)).fetchall():
                depend("innate", session["source_version_id"])
            if row["spec"].get("study_id"):
                depend("study", row["spec"]["study_id"])
            self.limitations.append(f"{object_id}: archived committed facts; generic restoration of this live system is disabled")
        elif kind in CAMPAIGN_TABLES:
            payload["tables"] = {}
            tables = CAMPAIGN_TABLES[kind]
            if kind == "assessment":
                foreign, members = "batch_id", "assessment_members"
            else:
                foreign, members = "campaign_id", kind + "_members"
            for table in tables[1:]:
                payload["tables"][table] = self._snapshot(f"objects/{slug}/{table}.jsonl", self._rows(
                    table, sql.SQL("{}=%s").format(sql.Identifier(foreign)), (identity,)))
            for member in self.db.execute(sql.SQL("SELECT run_id FROM {} WHERE {}=%s").format(
                sql.Identifier(members), sql.Identifier(foreign)), (identity,)).fetchall():
                if member["run_id"]:
                    depend("run", member["run_id"])
            if row.get("source_version_id"):
                depend("innate", row["source_version_id"])
            self.limitations.append(f"{object_id}: coordinator archive is read-only; no reconstructed coordinator is invented")
        elif kind == "world":
            payload["versions_entry"] = self._snapshot(f"objects/{slug}/versions.jsonl", self._rows(
                "world_versions", sql.SQL("document_id=%s ORDER BY revision"), (identity,)))
        elif kind in ("innate", "probe"):
            depend("run", row["run_id"])
            if kind == "probe":
                execution = self._execution(row["job_id"])
                payload["execution"] = execution
                payload["execution_hash"] = hashlib.sha256(canonical(execution)).hexdigest()
                for field, hash_field in (("artifact_id", "result_sha256"), ("bundle_artifact_id", "bundle_sha256")):
                    if execution["result"].get(field):
                        carrier = self.catalog._record(self.db, "artifact", execution["result"][field])
                        if carrier["sha256"] != execution["result"].get(hash_field):
                            raise ValueError("probe execution result hash differs from its original artifact")
                        depend("artifact", execution["result"][field])
            if row.get("parent_version_id"):
                depend("innate", row["parent_version_id"])
        elif kind == "study":
            for member in self.db.execute("SELECT id FROM runs WHERE spec->>'study_id'=%s", (identity,)).fetchall():
                depend("run", member["id"])
            self.limitations.append(f"{object_id}: study archive is read-only; no new control coordinator is invented")
        raw = canonical(payload)
        if len(raw) > 64 * 1024**2:
            raise ValueError("one record history exceeds the formal 64 MiB JSON object budget")
        self._snapshot(descriptor["payload"], [raw])
        return object_id

    def _link_dependencies(self, payload, depend):
        from .note_schema import body_links

        pattern = re.compile(r"/api/v2/projects/([0-9a-fA-F-]{36})/(artifacts|note-assets|report-sources|media|documents|notes)/([0-9a-fA-F-]{36}|[0-9a-f]{64})(?![0-9a-fA-F-])")
        mapping = {"artifacts": "artifact", "note-assets": "note_asset", "report-sources": "source", "media": "media", "documents": "document", "notes": "note"}
        links = set()
        for version in payload.get("versions", []):
            if "body" in version:
                links.update(body_links(version["body"]))
            for block in version.get("spec", {}).get("blocks", []):
                if block.get("type") == "commentary":
                    links.update(body_links({"format": "markdown", "text": block["markdown"]}))
        for project, family, identity in (match for link in links for match in pattern.findall(link)):
            if UUID(project) != UUID(str(self.project)):
                self.limitations.append("cross-project link preserved as original text; source permission was not bypassed")
                continue
            depend(mapping[family], identity)

    def _execution(self, identity):
        return wire(self.db.execute("SELECT id,project_id,run_id,kind,status,result,error,created_at FROM jobs WHERE id=%s", (identity,)).fetchone())

    def _history_budget(self, table, foreign, field, identity):
        row = self.db.execute(sql.SQL("SELECT coalesce(sum(octet_length({}::text)),0) AS bytes FROM {} WHERE {}=%s").format(
            sql.Identifier(field), sql.Identifier(table), sql.Identifier(foreign)), (identity,)).fetchone()
        if row["bytes"] > 60 * 1024**2:
            raise ValueError("one complete record history exceeds the bounded metadata recovery budget")
