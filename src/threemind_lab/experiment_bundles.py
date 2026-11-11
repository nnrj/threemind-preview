"""Portable experiment evidence and paused, version-checked continuation.

An archive is never executed on import. A separate authorized operation creates
a new identity. Scientific state and clocks are not reset as in a model fork.
"""

import hashlib
import os
import shutil
import tempfile
import time
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid4, uuid5

from psycopg import sql
from psycopg.types.json import Jsonb

from threemind_runtime import ArtifactCodec, create_engine

from .config import ROOT
from .database import Conflict, NotFound
from .database_stream import stream_rows
from .experiment_archive import SCHEMA, ArchiveReader, ArchiveWriter, canonical
from .inputs import digest
from .protocols import RunSpec
from .research_commands import parse_protocol

EVIDENCE_TABLES = (
    "commands",
    "input_envelopes",
    "input_frames",
    "events",
    "observations",
    "research_plans",
    "research_operations",
    "model_metadata_history",
    "media_prepared_frames",
)
GIB = 1024**3
PENDING_KINDS = {
    "sensory_input",
    "pause",
    "cancel",
    "close_inputs",
    "intervention",
    "stimulus",
    "energy_supply",
    "input_modulation",
}


class TransferCancelled(Exception):
    pass


@contextmanager
def scratch():
    directory = Path(os.getenv("THREEMIND_SCRATCH_DIR", ROOT / ".work" / "bundle-temp"))
    directory.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(directory).free < 15 * GIB:
        raise ValueError("实验临时目录所在盘剩余不足 15 GiB；请更换 THREEMIND_SCRATCH_DIR。")
    with tempfile.TemporaryFile(dir=directory, mode="w+b") as stream:
        yield stream


class TransferGuard:
    def __init__(self, store, job):
        self.store, self.job, self.last, self.bytes = store, job, 0, 0

    def __call__(self):
        now = time.monotonic()
        if now - self.last < 1:
            return
        self.last = now
        with self.store.tx(self.job["project_id"]) as db:
            self.store.fence(db, self.job)
            row = db.execute("SELECT params FROM jobs WHERE id=%s", (self.job["id"],)).fetchone()
            if row["params"].get("cancel_requested"):
                raise TransferCancelled("用户取消了实验包任务；原实验未修改。")
        directory = Path(os.getenv("THREEMIND_SCRATCH_DIR", ROOT / ".work" / "bundle-temp"))
        if directory.exists() and shutil.disk_usage(directory).free < 15 * GIB:
            raise ValueError("实验包任务达到磁盘预留限制 15 GiB，已停止。")


def get_bundle(db, bundle_id):
    row = db.execute("SELECT * FROM experiment_bundles WHERE id=%s", (bundle_id,)).fetchone()
    if row is None:
        raise NotFound("实验包不存在。")
    return row


def bundle_chunks(store, project, bundle):
    if bundle.get("artifact_id"):
        from .blob_store import object_chunks

        yield from object_chunks(store, project, "artifact", bundle["artifact_id"], actor=bundle["actor_id"])
        return
    after = -1
    while True:
        with store.tx(project) as db:
            db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(bundle["actor_id"]),))
            row = db.execute(
                "SELECT ordinal,body FROM bundle_upload_chunks WHERE upload_id=%s AND ordinal>%s ORDER BY ordinal LIMIT 1",
                (bundle["upload_id"], after),
            ).fetchone()
        if row is None:
            return
        after = row["ordinal"]
        yield bytes(row["body"])


@contextmanager
def open_bundle(store, project, bundle, *, check=lambda: None):
    with scratch() as stream:
        checksum, size = hashlib.sha256(), 0
        for chunk in bundle_chunks(store, project, bundle):
            check()
            size += len(chunk)
            if size > 8 * GIB or size > int(bundle["bytes"]):
                raise ValueError("实验包超过声明大小。")
            checksum.update(chunk)
            stream.write(chunk)
        if size != int(bundle["bytes"]) or bundle["sha256"] is not None and checksum.hexdigest() != bundle["sha256"]:
            raise ValueError("实验包整体校验失败。")
        reader = ArchiveReader(stream, check=check)
        reader.source_sha256 = checksum.hexdigest()
        try:
            yield reader
        finally:
            reader.close()


def resume_conditions(db, run, cp):
    blockers, changed = [], []
    if run["spec"].get("study_id"):
        blockers.append("属于冻结对照实验；单意识包不包含整个实验协调器。")
    for table in ("ecology_members", "evolution_members", "assessment_members"):
        if db.execute(
            sql.SQL("SELECT 1 FROM {} WHERE run_id=%s LIMIT 1").format(sql.Identifier(table)), (run["id"],)
        ).fetchone():
            blockers.append(f"属于 {table}；请保存完整种群/评估，不能单独恢复此个体。")
    if db.execute("SELECT 1 FROM language_sessions WHERE run_id=%s LIMIT 1", (run["id"],)).fetchone():
        blockers.append("此语言个体包含学习外设；单意识包未包含其完整外设状态，只可归档查看。")
    if db.execute(
        "SELECT 1 FROM input_envelopes WHERE run_id=%s AND status='accepted' AND (payload ? 'stream_session_id' OR payload ? 'device_session_id') LIMIT 1",
        (run["id"],),
    ).fetchone():
        blockers.append("有待处理的实时设备采集块；需先递送到提交边界。")
    pending = db.execute(
        "SELECT kind,payload FROM commands WHERE run_id=%s AND id>%s", (run["id"], run["last_command"])
    ).fetchall()
    if any(c["kind"] not in PENDING_KINDS or c["payload"].get("device") for c in pending):
        blockers.append("有尚未完成的设备/配置/命名捕获命令；请先处理到提交边界。")
    if db.execute(
        "SELECT 1 FROM research_operations WHERE run_id=%s AND status='pending' LIMIT 1", (run["id"],)
    ).fetchone():
        blockers.append("有未提交研究操作；请先完成或暂停该操作。")
    for table in ("device_sessions", "capture_sessions"):
        if db.execute(
            sql.SQL("SELECT 1 FROM {} WHERE run_id=%s AND status='active' LIMIT 1").format(sql.Identifier(table)),
            (run["id"],),
        ).fetchone():
            blockers.append(f"有活动 {table}；请先停止采集并提交已接收输入。")
    context = cp["context"]
    if not context.get("implementation"):
        blockers.append("检查点没有实现指纹，不能证明等价续行。")
    if not context.get("initialized"):
        blockers.append("尚未形成完整运行时边界。")
    if any(
        value.get("enabled") for key, value in run["spec"].items() if "telemetry" in key and isinstance(value, dict)
    ):
        changed.append("宿主/进程/运行时遥测将在新宿主重新采样；未来输入不是原记录的延续。")
    if db.execute("SELECT 1 FROM device_bindings WHERE run_id=%s LIMIT 1", (run["id"],)).fetchone():
        changed.append("外设绑定和凭证不随包转移；需在新意识上显式重新绑定。")
    if run["life"] == "dead":
        blockers.append("意识已死亡；可查看结构与证据，但不能复活原活动过程。")
    return {"blockers": blockers, "external_changes": changed}


def compatible(manifest, implementation):
    metadata = manifest.get("metadata", {})
    conditions = deepcopy(metadata.get("resume", {}))
    conditions.setdefault("blockers", [])
    conditions.setdefault("external_changes", [])
    old = metadata.get("implementation", {})
    for key in ("backend", "source_sha256", "native_binary_sha256", "python", "packages"):
        if old.get(key) != implementation.get(key):
            conditions["blockers"].append(f"实现依赖不一致：{key}；只读查看，不自动转换。")
    conditions["can_resume"] = not conditions["blockers"]
    conditions["requires_external_acknowledgement"] = bool(conditions["external_changes"])
    return conditions


def json_rows(rows):
    try:
        for row in rows:
            yield canonical(row) + b"\n"
    finally:
        close = getattr(rows, "close", None)
        if close:
            close()


def object_identity(row, kind):
    """Frozen scientific bytes plus physical identity, never exported as science."""
    return (
        str(row["sha256"] if kind == "media" else row["id"]),
        int(row["byte_length"] if kind == "media" else row["bytes"]),
        row["sha256"],
        str(row.get("blob_id")) if row.get("blob_id") else None,
    )


TARGET_FIELDS = ("kind", "target_id", "config_revision", "host_id")


def frozen_source_targets(blobs):
    """Capability identities only; object keys and credentials stay out of jobs."""
    targets = {
        canonical({key: row["locator"][key] for key in TARGET_FIELDS}): {
            key: row["locator"][key] for key in TARGET_FIELDS
        }
        for row in blobs
    }
    return [targets[key] for key in sorted(targets)]


def require_source_targets(params, blobs):
    declared = {canonical(target) for target in params.get("source_targets", [])}
    if any(canonical(target) not in declared for target in frozen_source_targets(blobs)):
        raise ValueError("实验包源存储目标在任务申请后变化；请重新申请任务。")


def export_external_selection(db, run_id, params):
    """Collect authorized references using a short metadata-only transaction."""
    db.execute("SELECT set_config('tm.note_user_id',%s,true)", (params["actor_id"],))
    media = db.execute(
        "SELECT DISTINCT a.* FROM media_assets a JOIN input_envelopes e ON e.asset_sha256=a.sha256 AND e.project_id=a.project_id WHERE e.run_id=%s AND a.blob_id IS NOT NULL",
        (run_id,),
    ).fetchall()
    resources = [("media", row) for row in media]
    from . import permissions
    actor = permissions.current_actor()
    superadmin = bool(actor and actor.get("superadmin") and str(actor["id"]) == params["actor_id"])
    for note_id in params.get("note_ids", []):
        if not db.execute("SELECT id FROM notes WHERE id=%s AND (owner_id=%s OR %s)", (note_id, params["actor_id"], superadmin)).fetchone():
            raise ValueError("所选笔记不存在或不是当前作者的笔记。")
        assets = db.execute(
            "SELECT DISTINCT a.id,a.bytes,a.sha256,a.blob_id FROM note_assets a JOIN note_asset_refs r ON r.asset_id=a.id WHERE r.note_id=%s AND a.blob_id IS NOT NULL",
            (note_id,),
        ).fetchall()
        resources.extend(("note", row) for row in assets)
    for artifact_id in params.get("artifact_ids", []):
        row = db.execute("SELECT * FROM artifacts WHERE id=%s", (artifact_id,)).fetchone()
        if row is None:
            raise ValueError("所选制品不存在。")
        if row.get("blob_id"):
            resources.append(("artifact", row))
    selected = {}
    for kind, row in resources:
        identity = object_identity(row, kind)
        blob = db.execute("SELECT * FROM stored_blobs WHERE id=%s", (row["blob_id"],)).fetchone()
        if blob is None or blob["sha256"] != identity[2] or int(blob["bytes"]) != identity[1]:
            raise ValueError("实验包外部原件引用或哈希不一致。")
        from .storage_payloads import physical_location
        selected[kind, identity[0]] = {"identity": identity, "blob": physical_location(db,blob)}
    return selected


def export_source_targets(db, run_id, params):
    return frozen_source_targets(value["blob"] for value in export_external_selection(db, run_id, params).values())


def export_private(db, params):
    """A selected private carrier keeps its author boundary in every wrapper."""
    if params.get("private") or params.get("note_ids"):
        return True
    return bool(
        db.execute(
            "SELECT 1 FROM artifacts a WHERE a.id=ANY(%s::uuid[]) AND "
            "(coalesce(a.metadata->>'private','false')='true' OR EXISTS(SELECT 1 FROM data_private_carriers c "
            "WHERE c.kind='artifact' AND c.carrier_id=a.id)) LIMIT 1",
            (params.get("artifact_ids", []),),
        ).fetchone()
    )


def resume_source_targets(db, bundle):
    blobs = []
    if bundle.get("artifact_id"):
        blobs += db.execute(
            "SELECT b.* FROM artifacts a JOIN stored_blobs b ON b.id=a.blob_id WHERE a.id=%s",
            (bundle["artifact_id"],),
        ).fetchall()
    media = [
        name.split("/")[1]
        for name in bundle["manifest"]["files"]
        if name.startswith("media/") and name.endswith("/metadata.json") and len(name.split("/")) == 3
    ]
    if media:
        blobs += db.execute(
            "SELECT b.* FROM media_assets a JOIN stored_blobs b ON b.id=a.blob_id WHERE a.sha256=ANY(%s)",
            (media,),
        ).fetchall()
    from .storage_payloads import physical_location
    return frozen_source_targets(physical_location(db,blob) for blob in blobs)


@contextmanager
def preload_external(store, project, run_id, params, guard):
    """Spool verified immutable objects before acquiring the evidence snapshot.

    The authorization query is short. The later snapshot compares every used
    resource with this selection; changes require a fresh export, never a mixed
    package. Both aggregate temporary storage and individual chunks are bounded.
    """
    from .research_plans import actor_can_execute

    with store.tx(project) as db:
        actor_can_execute(db, project, params["actor_id"])
        selected = export_external_selection(db, run_id, params)
        require_source_targets(params, (value["blob"] for value in selected.values()))
    with ExitStack() as stack:
        total = 0
        for value in selected.values():
            stream = stack.enter_context(scratch())
            for chunk in store.blobs.read(value["blob"]):
                guard()
                total += len(chunk)
                if len(chunk) > 4 * 1024**2 or total > 8 * GIB:
                    raise ValueError("实验包外部原件超过有界暂存预算。")
                stream.write(chunk)
            stream.seek(0)
            value["stream"] = stream
        yield selected


def preloaded_chunks(selected, kind, row):
    identity = object_identity(row, kind)
    value = selected.get((kind, identity[0]))
    if value is None or value["identity"] != identity:
        raise Conflict("外部原件在打包快照前变化；请重新选择已提交边界。")
    stream = value["stream"]
    stream.seek(0)
    yield from iter(lambda: stream.read(1024**2), b"")


def scientific_metadata(row):
    return {key: value for key, value in row.items() if key != "blob_id"}


def add_original(package, path, chunks, row, kind):
    package.add(path, chunks, compressed=True)
    descriptor = package.files[path]
    identity = object_identity(row, kind)
    if descriptor["bytes"] != identity[1] or descriptor["sha256"] != identity[2]:
        raise ValueError("实验包原件实际字节与科学记录不一致。")


def verify_existing_media(store, project, reader, guard, params):
    """A same-project resume cannot silently reuse a missing external original."""
    from .blob_store import object_chunks

    existing, blobs = {}, []
    with store.tx(project) as db:
        for name in reader.manifest["files"]:
            if not name.startswith("media/") or not name.endswith("/metadata.json"):
                continue
            asset = reader.json(name, maximum=1024**2)
            descriptor = reader.manifest["files"][name.removesuffix("metadata.json") + "body"]
            if descriptor["sha256"] != asset["sha256"] or descriptor["bytes"] != int(asset["byte_length"]):
                raise ValueError("原始媒体校验失败。")
            row = db.execute("SELECT * FROM media_assets WHERE sha256=%s", (asset["sha256"],)).fetchone()
            if row:
                if row["byte_length"] != asset["byte_length"]:
                    raise ValueError("项目内已有媒体与包内原件不一致。")
                existing[row["sha256"]] = object_identity(row, "media")
                if row.get("blob_id"):
                    blob = db.execute("SELECT * FROM stored_blobs WHERE id=%s", (row["blob_id"],)).fetchone()
                    if blob is None:
                        raise ValueError("项目内已有媒体外部原件引用不存在。")
                    blobs.append(blob)
        require_source_targets(params, blobs)
    for sha in existing:
        for _ in object_chunks(store, project, "media", sha):
            guard()
    return existing


def export_bundle(worker, job):
    store, project, run_id = worker.db, job["project_id"], job["run_id"]
    params, guard = job["params"], TransferGuard(store, job)
    from .research_plans import actor_can_execute

    with store.tx(project) as db:
        actor_can_execute(db, project, params["actor_id"])
        db.execute("SELECT set_config('tm.note_user_id',%s,true)", (params["actor_id"],))
        existing = db.execute("SELECT * FROM experiment_bundles WHERE job_id=%s", (job["id"],)).fetchone()
        if existing:
            return {
                "bundle_id": str(existing["id"]),
                "artifact_id": str(existing["artifact_id"]),
                "sha256": existing["sha256"],
                "replayed": True,
            }
    # State rows are immutable, and the later locked run revision must match.
    cp, image = store.load_checkpoint(project, run_id, params["checkpoint_id"])
    with preload_external(store, project, run_id, params, guard) as selected, scratch() as stream:
        with store.tx(project, repeatable=True) as db:
            actor_can_execute(db, project, params["actor_id"])
            db.execute("SELECT set_config('tm.note_user_id',%s,true)", (params["actor_id"],))
            run = db.execute("SELECT * FROM runs WHERE id=%s FOR SHARE", (run_id,)).fetchone()
            if run is None:
                raise NotFound()
            if run["revision"] != params["expected_revision"] or run["revision"] != cp["revision"]:
                raise Conflict("实验在打包前发生变化；请重新选择已提交边界。")
            if (
                run["status"] in ("queued", "running")
                or db.execute(
                    "SELECT 1 FROM jobs WHERE run_id=%s AND kind IN ('run','research_plan') AND status IN ('pending','leased')",
                    (run_id,),
                ).fetchone()
            ):
                raise Conflict("请先暂停意识及实验计划，再保存实验包。")
            metadata = {
                "origin_project": str(project),
                "origin_run": str(run_id),
                "origin_checkpoint": str(cp["id"]),
                "revision": cp["revision"],
                "time_us": cp["time_us"],
                "state_hash": image.digest,
                "implementation": cp["context"].get("implementation", {}),
                "resume": resume_conditions(db, run, cp),
                "scope": "one committed consciousness plus its research plans; selected notes/reports/artifacts",
                "units": {"time": "microseconds", "activation": "kernel-specific; see state config", "bytes": "bytes"},
                "credentials_included": False,
                "private": export_private(db, params),
            }
            package = ArchiveWriter(stream, metadata, check=guard)
            try:
                package.add("model.tmind", [ArtifactCodec.encode(image)], compressed=True)
                package.json("run.json", run)
                package.json("checkpoint.json", {k: v for k, v in cp.items() if k != "body"})
                for table in EVIDENCE_TABLES:
                    # Table names are a fixed internal whitelist, never input SQL.
                    query = sql.SQL("SELECT * FROM {} WHERE run_id=%s").format(sql.Identifier(table))
                    package.add(
                        f"evidence/{table}.jsonl",
                        json_rows(stream_rows(db, query, (run_id,))),
                        media_type="application/x-ndjson",
                    )
                for kind in ("temporal", "structural"):
                    rows = stream_rows(
                        db, "SELECT * FROM events WHERE run_id=%s AND kind=%s ORDER BY id", (run_id, kind + "_readout")
                    )
                    package.add(f"readouts/{kind}.jsonl", json_rows(rows), media_type="application/x-ndjson")
                pending = db.execute(
                    "SELECT * FROM commands WHERE run_id=%s AND id>%s ORDER BY id", (run_id, run["last_command"])
                ).fetchall()
                package.json("pending-commands.json", pending)
                for asset in db.execute(
                    "SELECT DISTINCT a.* FROM media_assets a JOIN input_envelopes e ON e.asset_sha256=a.sha256 AND e.project_id=a.project_id WHERE e.run_id=%s",
                    (run_id,),
                ).fetchall():
                    name = f"media/{asset['sha256']}"
                    package.json(name + "/metadata.json", scientific_metadata(asset))
                    parts = stream_rows(
                        db,
                        "SELECT body FROM media_chunks WHERE sha256=%s ORDER BY chunk_index",
                        (asset["sha256"],),
                        batch=1,
                    )
                    if asset.get("blob_id"):
                        add_original(
                            package, name + "/body", preloaded_chunks(selected, "media", asset), asset, "media"
                        )
                    else:
                        add_original(package, name + "/body", (bytes(p["body"]) for p in parts), asset, "media")
                plans = db.execute(
                    "SELECT * FROM research_plans WHERE run_id=%s ORDER BY created_at,id", (run_id,)
                ).fetchall()
                package.json("plans.json", plans)
                # Only explicitly selected, authorized notes enter the archive.
                # Original authorship is preserved even when superadmin exports.
                from . import permissions
                principal = permissions.current_actor()
                superadmin = bool(principal and principal.get("superadmin") and str(principal["id"]) == params["actor_id"])
                for note_id in params.get("note_ids", []):
                    note = db.execute(
                        "SELECT * FROM notes WHERE id=%s AND (owner_id=%s OR %s)", (note_id, params["actor_id"], superadmin)
                    ).fetchone()
                    if note is None:
                        raise ValueError("所选笔记不存在或不是当前作者的笔记。")
                    package.json(f"notes/{note_id}.json", note)
                    versions = stream_rows(
                        db, "SELECT * FROM note_versions WHERE note_id=%s ORDER BY revision", (note_id,)
                    )
                    package.add(
                        f"notes/{note_id}/versions.jsonl", json_rows(versions), media_type="application/x-ndjson"
                    )
                    assets = stream_rows(
                        db,
                        "SELECT DISTINCT a.* FROM note_assets a JOIN note_asset_refs r ON r.asset_id=a.id WHERE r.note_id=%s",
                        (note_id,),
                        batch=1,
                    )
                    for asset in assets:
                        path = f"note-assets/{asset['id']}"
                        if path + "/body" not in package.files:
                            content = asset.pop("content")
                            chunks = (
                                preloaded_chunks(selected, "note", asset) if asset.get("blob_id") else [bytes(content)]
                            )
                            add_original(package, path + "/body", chunks, asset, "note")
                            package.json(path + "/metadata.json", scientific_metadata(asset))
                document_queue = list(dict.fromkeys(params.get("document_ids", [])))
                completed_documents = set()
                while document_queue:
                    document_id = document_queue.pop(0)
                    if document_id in completed_documents:
                        continue
                    completed_documents.add(document_id)
                    if len(completed_documents) > 100:
                        raise ValueError("报告引用闭包超过 100 份文档预算；请缩小选择。")
                    document = db.execute("SELECT * FROM research_documents WHERE id=%s", (document_id,)).fetchone()
                    if document is None:
                        raise ValueError("所选研究记录/报告不存在。")
                    package.json(f"reports/{document_id}.json", document)
                    referenced = db.execute(
                        "SELECT DISTINCT record_id FROM research_document_refs WHERE document_id=%s", (document_id,)
                    ).fetchall()
                    document_queue.extend(
                        str(r["record_id"]) for r in referenced if str(r["record_id"]) not in completed_documents
                    )
                    for table in ("research_document_versions", "research_document_sources", "research_document_refs"):
                        rows = stream_rows(
                            db,
                            sql.SQL("SELECT * FROM {} WHERE document_id=%s").format(sql.Identifier(table)),
                            (document_id,),
                        )
                        package.add(
                            f"reports/{document_id}/{table}.jsonl", json_rows(rows), media_type="application/x-ndjson"
                        )
                    sources = db.execute(
                        "SELECT DISTINCT s.* FROM report_sources s JOIN research_document_sources r ON r.source_id=s.id WHERE r.document_id=%s",
                        (document_id,),
                    ).fetchall()
                    for source in sources:
                        path = f"report-sources/{source['id']}"
                        if path + "/metadata.json" not in package.files:
                            package.json(path + "/metadata.json", source)
                            package.add(
                                path + "/rows.jsonl",
                                json_rows(
                                    stream_rows(
                                        db,
                                        "SELECT * FROM report_source_rows WHERE source_id=%s ORDER BY ordinal",
                                        (source["id"],),
                                    )
                                ),
                                media_type="application/x-ndjson",
                            )
                for artifact_id in params.get("artifact_ids", []):
                    artifact = db.execute("SELECT * FROM artifacts WHERE id=%s", (artifact_id,)).fetchone()
                    if artifact is None:
                        raise ValueError("所选制品不存在。")
                    if db.execute(
                        "SELECT 1 FROM jobs WHERE id=%s AND status IN ('pending','leased')", (artifact["job_id"],)
                    ).fetchone():
                        raise ValueError("Transformer/制品任务仍在执行；首版只支持任务边界。")
                    package.json(f"artifacts/{artifact_id}/metadata.json", scientific_metadata(artifact))
                    parts = stream_rows(
                        db,
                        "SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal",
                        (artifact_id,),
                        batch=1,
                    )
                    if artifact.get("blob_id"):
                        add_original(
                            package,
                            f"artifacts/{artifact_id}/body",
                            preloaded_chunks(selected, "artifact", artifact),
                            artifact,
                            "artifact",
                        )
                    else:
                        add_original(
                            package,
                            f"artifacts/{artifact_id}/body",
                            (bytes(p["body"]) for p in parts),
                            artifact,
                            "artifact",
                        )
                manifest = package.finish()
            finally:
                package.close()
        artifact = store.put_artifact_stream(
            job,
            f"experiment-r{cp['revision']}.tmexperiment",
            "application/zip",
            stream,
            {
                "schema": SCHEMA,
                "origin_run": str(run_id),
                "state_hash": image.digest,
                "private": metadata["private"],
                "private_actor_id": params["actor_id"],
            },
        )
    with store.tx(project) as db:
        store.fence(db, job)
        actor_can_execute(db, project, params["actor_id"])
        db.execute("SELECT set_config('tm.note_user_id',%s,true)", (params["actor_id"],))
        row = db.execute(
            "INSERT INTO experiment_bundles(id,project_id,actor_id,name,job_id,artifact_id,sha256,bytes,manifest,private) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(job_id) DO UPDATE SET job_id=excluded.job_id RETURNING *",
            (
                uuid4(),
                project,
                params["actor_id"],
                params["name"],
                job["id"],
                artifact["id"],
                artifact["sha256"],
                artifact["bytes"],
                Jsonb(manifest),
                metadata["private"],
            ),
        ).fetchone()
    return {
        "bundle_id": str(row["id"]),
        "artifact_id": str(artifact["id"]),
        "sha256": row["sha256"],
        "resume": metadata["resume"],
    }


def inspect_upload(worker, job):
    store, project, upload_id = worker.db, job["project_id"], job["params"]["upload_id"]
    with store.tx(project) as db:
        row = db.execute("SELECT * FROM bundle_uploads WHERE id=%s", (upload_id,)).fetchone()
    if row is None:
        raise NotFound()
    guard = TransferGuard(store, job)
    with open_bundle(store, project, row | {"upload_id": upload_id}, check=guard) as reader:
        manifest = reader.verify()
        checksum = reader.source_sha256
    with store.tx(project) as db:
        store.fence(db, job)
        db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(row["actor_id"]),))
        bundle = db.execute(
            "INSERT INTO experiment_bundles(id,project_id,actor_id,name,job_id,upload_id,sha256,bytes,manifest,private) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(job_id) DO UPDATE SET job_id=excluded.job_id RETURNING id",
            (
                uuid4(),
                project,
                row["actor_id"],
                row["name"],
                job["id"],
                upload_id,
                checksum,
                row["bytes"],
                Jsonb(manifest),
                bool(manifest.get("metadata", {}).get("private"))
                or any(name.startswith("notes/") for name in manifest["files"]),
            ),
        ).fetchone()
        db.execute("UPDATE bundle_uploads SET status='ready',sha256=%s WHERE id=%s", (checksum, upload_id))
    return {
        "bundle_id": str(bundle["id"]),
        "mode": "read_only",
        "sha256": checksum,
        "compatibility": compatible(manifest, worker.implementation),
    }


def remap_context(value, identities, key=""):
    # This walks runtime metadata, never the numerical Core state or channel IDs.
    if isinstance(value, str) and key in {"run_id", "input_bus_run_id", "envelope_id", "plan_id"}:
        return identities.get(value, value)
    if isinstance(value, list):
        return [remap_context(v, identities, key) for v in value]
    if isinstance(value, dict):
        return {k: remap_context(v, identities, k) for k, v in value.items()}
    return value


def insert_record(db, table, values):
    # Tables/fields originate in an explicit server-side allowlist below.
    db.execute(
        sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(table),
            sql.SQL(",").join(map(sql.Identifier, values)),
            sql.SQL(",").join(sql.Placeholder() for _ in values),
        ),
        [Jsonb(v) if isinstance(v, (dict, list)) else v for v in values.values()],
    )


ENVELOPE_FIELDS = (
    "id",
    "project_id",
    "run_id",
    "adapter_id",
    "adapter_version",
    "source",
    "actor_id",
    "request_hash",
    "payload",
    "payload_hash",
    "configuration",
    "configuration_hash",
    "frame_count",
    "channel_count",
    "delivered_count",
    "filtered_count",
    "status",
    "error",
    "command_id",
    "delay_us",
    "requested_time_us",
    "last_delivery_us",
    "processed_revision",
    "source_id",
    "source_policy",
    "delivery_status",
    "delivery_error",
)
FRAME_FIELDS = (
    "project_id",
    "run_id",
    "envelope_id",
    "frame_index",
    "core_event_id",
    "scheduled_time_us",
    "delivered_time_us",
    "core_sequence",
    "stimulus",
    "labels",
    "channel_count",
    "status",
    "reason",
    "scheduled_revision",
    "delivered_revision",
    "source_policy",
)


def resume_bundle(worker, job):
    store, project, params = worker.db, job["project_id"], job["params"]
    actor, request_id = params["actor_id"], UUID(params["request_id"])
    fingerprint = digest(params)
    with store.tx(project) as db:
        from .research_plans import actor_can_execute

        actor_can_execute(db, project, actor)
        db.execute("SELECT set_config('tm.note_user_id',%s,true)", (actor,))
        old = db.execute(
            "SELECT * FROM bundle_resumes WHERE project_id=%s AND actor_id=%s AND request_id=%s",
            (project, actor, request_id),
        ).fetchone()
        if old:
            if old["fingerprint"] != fingerprint:
                raise Conflict("恢复请求编号已用于其他参数。")
            return {"run_id": str(old["run_id"]), "replayed": True}
        bundle = get_bundle(db, params["bundle_id"])
        require_source_targets(params, ({"locator": target} for target in resume_source_targets(db, bundle)))
    conditions = compatible(bundle["manifest"], worker.implementation)
    if not conditions["can_resume"]:
        raise ValueError("；".join(conditions["blockers"]))
    if conditions["external_changes"] and not params.get("acknowledge_external_changes"):
        raise ValueError("需要明确确认现实设备/遥测条件变化。")
    run_id = uuid5(request_id, f"bundle-resume:{project}:{actor}")
    guard = TransferGuard(store, job)
    with open_bundle(store, project, bundle, check=guard) as reader:
        reader.verify()
        run = reader.json("run.json", maximum=64 * 1024**2)
        cp = reader.json("checkpoint.json", maximum=512 * 1024**2)
        spec = RunSpec(**run["spec"])
        pending = reader.json("pending-commands.json", maximum=16 * 1024**2)
        # The manifest is an index, not an authority to execute imported state.
        context_source = cp["context"]
        if not context_source.get("initialized") or context_source.get("implementation") != bundle["manifest"][
            "metadata"
        ].get("implementation"):
            raise ValueError("检查点实现与清单不一致，不能恢复。")
        if (
            run.get("life") == "dead"
            or spec.study_id
            or run["revision"] != cp["revision"]
            or str(run["id"]) != str(cp["run_id"])
        ):
            raise ValueError("实验包不是可恢复的独立存活边界。")
        if any(
            c["kind"] not in PENDING_KINDS or c["payload"].get("device") or int(c["id"]) <= int(run["last_command"])
            for c in pending
        ):
            raise ValueError("实验包含不支持恢复的待执行命令。")
        if any(r["status"] == "pending" for r in reader.rows("evidence/research_operations.jsonl")):
            raise ValueError("实验包含未提交的研究操作。")
        if any(
            v.get("enabled") for k, v in run["spec"].items() if "telemetry" in k and isinstance(v, dict)
        ) and not params.get("acknowledge_external_changes"):
            raise ValueError("需要明确确认遥测输入条件变化。")
        image = ArtifactCodec.decode(reader.read("model.tmind", maximum=512 * 1024**2), max_bytes=512 * 1024**2)
        if image.digest != bundle["manifest"]["metadata"]["state_hash"] or image.digest != cp["state_hash"]:
            raise ValueError("实验包状态哈希不一致。")
        # Validate candidate/baseline state through its real engine. No stepping.
        create_engine(state=image, backend=worker.backend, kernel_id=spec.kernel_id)
        existing_media = verify_existing_media(store, project, reader, guard, params)
        identities = {str(run["id"]): str(run_id)}
        # Only pending input/readout envelope identifiers need translation; keep
        # their complete original history as separately hashed archive evidence.
        for envelope in reader.rows("evidence/input_envelopes.jsonl"):
            if envelope["status"] == "accepted" and any(
                k in envelope["payload"] for k in ("device_session_id", "stream_session_id")
            ):
                raise ValueError("不能恢复待处理的实时设备采集块。")
            if len(identities) > 100000:
                raise ValueError("当前恢复预算最多 100,000 个载体；实验包仍可只读查看。")
            identities[envelope["id"]] = str(uuid5(run_id, "envelope:" + envelope["id"]))
        plans = reader.json("plans.json", maximum=16 * 1024**2)
        for plan in plans:
            identities[plan["id"]] = str(uuid5(run_id, "plan:" + plan["id"]))
        context = remap_context(cp["context"], identities)
        for key in (
            "commit_fingerprint",
            "persistence",
            "research_completion",
            "configuration_change",
            "organ_controls",
            "input_audit_hash",
        ):
            context.pop(key, None)
        context.update(
            {
                "last_command": 0,
                "input_bus_run_id": str(run_id),
                "bundle_origin": {
                    "bundle_id": str(bundle["id"]),
                    "sha256": bundle["sha256"],
                    "run_id": run["id"],
                    "checkpoint_id": cp["id"],
                    "conditions": conditions,
                },
            }
        )
        with store.tx(project) as db:
            # Recheck authorization at commit, not only at job admission.
            from .research_plans import actor_can_execute

            actor_can_execute(db, project, actor)
            db.execute("SELECT set_config('tm.note_user_id',%s,true)", (actor,))
            db.execute(
                "INSERT INTO runs(id,project_id,name,spec,origin_hash,origin_kind,status) VALUES(%s,%s,%s,%s,%s,'imported','paused')",
                (run_id, project, params["name"], Jsonb(spec.model_dump()), bundle["sha256"]),
            )
            new_cp = store.save_checkpoint(
                project,
                run_id,
                image,
                context=context,
                expected_revision=0,
                status="paused",
                last_command=0,
                transaction=db,
            )
            # Original media are content addressed. References in immutable
            # carrier payloads stay valid without re-encoding any stimulus.
            for name in reader.manifest["files"]:
                if not name.startswith("media/") or not name.endswith("/metadata.json"):
                    continue
                asset = reader.json(name)
                data_name = name.removesuffix("metadata.json") + "body"
                descriptor = reader.manifest["files"][data_name]
                if descriptor["sha256"] != asset["sha256"] or descriptor["bytes"] != int(asset["byte_length"]):
                    raise ValueError("原始媒体校验失败。")
                inserted = db.execute(
                    "INSERT INTO media_assets(project_id,sha256,byte_length) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING RETURNING sha256",
                    (project, asset["sha256"], asset["byte_length"]),
                ).fetchone()
                if inserted:
                    ordinal = 0
                    for chunk in reader.iter_bytes(data_name):
                        for offset in range(0, len(chunk), 1024**2):
                            db.execute(
                                "INSERT INTO media_chunks VALUES(%s,%s,%s,%s)",
                                (project, asset["sha256"], ordinal, chunk[offset : offset + 1024**2]),
                            )
                            ordinal += 1
                else:
                    current = db.execute(
                        "SELECT * FROM media_assets WHERE sha256=%s FOR SHARE", (asset["sha256"],)
                    ).fetchone()
                    if existing_media.get(asset["sha256"]) != object_identity(current, "media"):
                        raise ValueError("项目内已有媒体在恢复验证后变化；请重新恢复。")
            command_ids = {}
            for command in pending:
                fresh = db.execute(
                    "INSERT INTO commands(project_id,run_id,kind,payload) VALUES(%s,%s,%s,%s) RETURNING id",
                    (project, run_id, command["kind"], Jsonb(remap_context(command["payload"], identities))),
                ).fetchone()
                command_ids[int(command["id"])] = fresh["id"]
            # Schema fields are selected from the installed schema, then limited
            # to the scientific input whitelist; remote columns cannot inject SQL.
            installed = {
                r["column_name"]
                for r in db.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema='tm2' AND table_name='input_envelopes'"
                ).fetchall()
            }
            for row in reader.rows("evidence/input_envelopes.jsonl"):
                values = {k: row[k] for k in ENVELOPE_FIELDS if k in installed and k in row}
                values.update(
                    id=identities[row["id"]],
                    project_id=project,
                    run_id=run_id,
                    actor_id=actor,
                    command_id=command_ids.get(row["command_id"]),
                )
                if "processed_revision" in values:
                    values["processed_revision"] = 1 if values["processed_revision"] is not None else None
                # Delivery uses frames already queued, never decodes old carriers
                # again. The payload and configuration retain their original hash.
                insert_record(db, "input_envelopes", values)
            for row in reader.rows("evidence/input_frames.jsonl"):
                values = {k: row[k] for k in FRAME_FIELDS if k in row}
                values.update(
                    project_id=project,
                    run_id=run_id,
                    envelope_id=identities[row["envelope_id"]],
                    scheduled_revision=1,
                    delivered_revision=1 if row["delivered_revision"] is not None else None,
                )
                insert_record(db, "input_frames", values)
            for row in reader.rows("evidence/media_prepared_frames.jsonl"):
                insert_record(
                    db,
                    "media_prepared_frames",
                    {
                        "project_id": project,
                        "run_id": run_id,
                        "envelope_id": identities[row["envelope_id"]],
                        "frame_index": row["frame_index"],
                        "stimulus": row["stimulus"],
                    },
                )
            plan_ids = []
            for plan in plans:
                protocol = parse_protocol(plan["protocol"])
                if (
                    digest(protocol.model_dump()) != plan["protocol_hash"]
                    or not 0 <= plan["next_step"] <= protocol.step_count
                ):
                    raise ValueError("阶段协议或游标不一致。")
                if plan["status"] not in ("ready", "paused"):
                    continue
                pid = identities[plan["id"]]
                plan_ids.append(pid)
                values = {
                    k: plan[k]
                    for k in ("name", "protocol", "protocol_hash", "next_step", "step_attempt", "wait_target_us")
                }
                values.update(
                    id=pid,
                    project_id=project,
                    run_id=run_id,
                    actor_id=actor,
                    request_id=uuid5(run_id, "plan-request:" + plan["id"]),
                    fingerprint=digest({"bundle": str(bundle["id"]), "plan": plan["id"]}),
                    origin="human",
                    status="paused",
                    expected_revision=1,
                    expected_command=max(command_ids.values(), default=0),
                    checkpoint_id=new_cp["id"],
                )
                insert_record(db, "research_plans", values)
            guard.last = 0
            guard()
            store.fence(db, job)
            db.execute(
                "INSERT INTO bundle_resumes(project_id,bundle_id,run_id,actor_id,request_id,fingerprint,conditions) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (project, bundle["id"], run_id, actor, request_id, fingerprint, Jsonb(conditions)),
            )
    return {
        "run_id": str(run_id),
        "plan_ids": plan_ids,
        "status": "paused",
        "state_hash": image.digest,
        "conditions": conditions,
    }


def execute(worker, job):
    if job["kind"] == "bundle_export":
        return export_bundle(worker, job)
    if job["kind"] == "bundle_import":
        return inspect_upload(worker, job)
    return resume_bundle(worker, job)
