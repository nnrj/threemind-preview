"""Developmental training and explicit, immutable checkpoint selection.

The ordinary Runtime executes each individual. This module owns provenance and
inheritance, not a second learning algorithm or an implicit fitness function.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import asdict
from typing import Literal
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb
from pydantic import Field, field_validator

from threemind_kernels.registry import resolve_kernel, state_kernel
from threemind_runtime import ArtifactCodec
from threemind_runtime.inheritance import BIRTH_RULE, KERNEL60_BIRTH_RULE, birth, birth_rule
from threemind_runtime.profile import profile_from_spec

from .configuration import PROTOCOL_IMMUTABLE
from .database import Conflict, NotFound
from .protocols import RunSpec, StrictModel
from .record_schema import ExecutionRecordOptions

IDENTITY_PATHS = sorted(
    PROTOCOL_IMMUTABLE
    - {"world_protocol", "robot_protocol", "environment_seed", "replay", "phases", "intervention", "study_id", "condition", "block_seed"}
)


class DevelopmentRequest(ExecutionRecordOptions):
    operation_id: UUID
    name: str = Field(min_length=1, max_length=120)
    objective: str = Field(min_length=1, max_length=8000)
    source_version_id: UUID | None = None
    spec: RunSpec

    @field_validator("spec", mode="before")
    @classmethod
    def strict_protocol(cls, value):
        if isinstance(value, RunSpec):
            return value
        return RunSpec.model_validate_json(json.dumps(value, allow_nan=False), strict=True)

    @field_validator("name", "objective")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("名称与研究目标不能为空。")
        return value.strip()


class RegistrationRequest(StrictModel):
    operation_id: UUID
    name: str = Field(min_length=1, max_length=120)
    selection_note: str = Field(min_length=1, max_length=8000)
    run_id: UUID
    checkpoint_id: UUID
    expected_state_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("name", "selection_note")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("名称与选择依据不能为空。")
        return value.strip()


class InnateExport(StrictModel):
    format: Literal["tmind", "json", "bundle"] = "tmind"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def value_at(value, path):
    for part in path.split("."):
        value = value[part]
    return value


def normalized(spec):
    return spec.model_dump() | {"config": asdict(resolve_kernel(spec.kernel_id).configuration(spec.config))}


def validate_spec(spec, source, max_seconds):
    if spec.duration_s is not None and spec.duration_s > max_seconds:
        raise ValueError("发育时长超过本部署的单次运行上限；可以登记恢复点后创建下一次发育。")
    if any(getattr(spec, key) is not None for key in ("study_id", "condition", "block_seed")):
        raise ValueError("发育训练不能携带配对实验的成员标识。")
    result = normalized(spec)
    if source:
        before = normalized(RunSpec(**source["protocol"]))
        changed = [path for path in ["config", *IDENTITY_PATHS] if value_at(before, path) != value_at(result, path)]
        if changed:
            raise ValueError("继承出生须保留内核参数与感官身份；请在出生后单独记录实验性修改：" + ", ".join(changed))
    return result


def _version(db, version):
    row = db.execute("SELECT * FROM innate_versions WHERE id=%s", (version,)).fetchone()
    if row is None:
        raise NotFound()
    return row


def _retry(db, table, project, actor, request):
    from psycopg import sql

    # Serialize the user nonce across retries, including a lost HTTP response.
    db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"{table}:{project}:{request.operation_id}",))
    row = db.execute(
        sql.SQL("SELECT * FROM {} WHERE operation_id=%s").format(sql.Identifier(table)), (request.operation_id,)
    ).fetchone()
    facts = request.model_dump(mode="json", exclude={"operation_id"})
    # Preserve old request hashes when the new host-only options use defaults.
    for key, default in (('record_executor', 'human'), ('record_classification', 'formal')):
        if facts.get(key) == default:
            facts.pop(key)
    request_hash = digest(facts)
    if row and (row["request_hash"] != request_hash or str(row["actor_id"]) != str(actor)):
        raise Conflict("该操作标识已用于其他内容，请重新提交新的操作。")
    return row, request_hash


def create(database, project, actor, request, max_seconds):
    with database.tx(project) as db:
        session = create_in(db, project, actor, request, max_seconds)
        from .native_records import register_execution
        if not db.execute('SELECT 1 FROM research_experiments WHERE source_key=%s',
                          ('native-run:' + str(session['run_id']),)).fetchone():
            register_execution(database, db, project, {'id': actor}, 'run', session['run_id'], request.name,
                               session['protocol'], executor=request.record_executor,
                               classification=request.record_classification, question=request.objective,
                               metadata={'development_session_id': str(session['id'])})
        return session


def create_in(db, project, actor, request, max_seconds):
    previous, request_hash = _retry(db, "development_sessions", project, actor, request)
    if previous:
        return previous
    source = _version(db, request.source_version_id) if request.source_version_id else None
    spec = validate_spec(request.spec, source, max_seconds)
    run_id, session_id = uuid4(), uuid4()
    db.execute(
        "INSERT INTO runs(id,project_id,name,spec,parent_id,origin_hash,origin_checkpoint_id,origin_kind) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            run_id,
            project,
            request.name,
            Jsonb(spec),
            source["run_id"] if source else None,
            source["state_hash"] if source else None,
            source["checkpoint_id"] if source else None,
            "inherited" if source else "created",
        ),
    )
    session = db.execute(
        "INSERT INTO development_sessions(id,project_id,actor_id,operation_id,request_hash,name,objective,run_id,source_version_id,protocol,protocol_hash) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (
            session_id,
            project,
            actor,
            request.operation_id,
            request_hash,
            request.name,
            request.objective,
            run_id,
            request.source_version_id,
            Jsonb(spec),
            digest(spec),
        ),
    ).fetchone()
    db.execute(
        "INSERT INTO jobs(id,project_id,run_id,kind,params) VALUES(%s,%s,%s,'run',%s)",
        (uuid4(), project, run_id, Jsonb({"development_id": str(session_id)})),
    )
    return session


def register(database, project, actor, request):
    with database.tx(project) as db:
        return register_in(db, project, actor, request)


def register_in(db, project, actor, request):
    previous, request_hash = _retry(db, "innate_versions", project, actor, request)
    if previous:
        return previous
    # Same subject lock as archive cleanup; the FK then pins the complete run.
    if not db.execute("SELECT id FROM runs WHERE id=%s FOR UPDATE", (request.run_id,)).fetchone():
        raise NotFound()
    cp = db.execute(
        "SELECT id,revision,time_us,state_hash,context->'protocol' AS protocol FROM checkpoints WHERE id=%s AND run_id=%s",
        (request.checkpoint_id, request.run_id),
    ).fetchone()
    if cp is None:
        raise NotFound()
    if cp["state_hash"] != request.expected_state_hash:
        raise Conflict("所选恢复点与预览的状态校验和不符，请重新选择。")
    if not cp["protocol"]:
        raise ValueError("该历史恢复点缺少当时的感官协议，不能猜测先天身份；请先从明确配置的运行提交新的恢复点。")
    protocol = normalized(RunSpec(**cp["protocol"]))
    parent = db.execute(
        "SELECT v.id,v.generation FROM development_sessions d JOIN innate_versions v ON v.id=d.source_version_id WHERE d.run_id=%s",
        (request.run_id,),
    ).fetchone()
    return db.execute(
        "INSERT INTO innate_versions(id,project_id,actor_id,operation_id,request_hash,name,selection_note,run_id,checkpoint_id,state_hash,source_revision,source_time_us,protocol,protocol_hash,birth_rule,parent_version_id,generation) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (
            uuid4(),
            project,
            actor,
            request.operation_id,
            request_hash,
            request.name,
            request.selection_note,
            request.run_id,
            cp["id"],
            cp["state_hash"],
            cp["revision"],
            cp["time_us"],
            Jsonb(protocol),
            digest(protocol),
            birth_rule(protocol["kernel_id"]),
            parent["id"] if parent else None,
            parent["generation"] + 1 if parent else 0,
        ),
    ).fetchone()


def initial_state(database, project, run):
    """Lazy birth under the ordinary run lease, repeated deterministically on crash.

    No separate initialization job or partially populated graph is exposed. Once
    a checkpoint exists, the normal recovery path continues it exactly.
    """
    with database.tx(project) as db:
        session = db.execute(
            "SELECT id,source_version_id FROM development_sessions WHERE run_id=%s", (run["id"],)
        ).fetchone()
        source = _version(db, session["source_version_id"]) if session and session["source_version_id"] else None
    if source is None:
        return None, None
    image = born_image(database, project, source)
    return image, {
        "key": "development-birth",
        "time_us": "0",
        "kind": "development_birth",
        "payload": {
            "session_id": str(session["id"]),
            "version_id": str(source["id"]),
            "birth_rule": source["birth_rule"],
            "source_hash": source["state_hash"],
            "initial_hash": image.digest,
        },
    }


def born_image(database, project, version):
    if version["birth_rule"] not in (BIRTH_RULE, KERNEL60_BIRTH_RULE):
        raise ValueError("unsupported inheritance rule")
    _, image = database.load_checkpoint(project, version["run_id"], version["checkpoint_id"])
    if image.digest != version["state_hash"]:
        raise ValueError("innate source integrity mismatch")
    descriptor = state_kernel(image)
    recorded = RunSpec(**version["protocol"])
    if recorded.kernel_id != descriptor.kernel_id or descriptor.configuration(
        image.to_dict()["config"]
    ) != descriptor.configuration(recorded.config):
        raise ValueError("checkpoint Core configuration differs from its recorded protocol")
    return birth(image, rule=version["birth_rule"])


def listing(database, project, kind, q="", offset=0):
    with database.tx(project) as db:
        if kind == "sessions":
            rows = db.execute(
                "SELECT d.id,d.name,d.objective,d.run_id,d.source_version_id,d.protocol_hash,d.created_at,"
                "r.status,r.revision,r.time_us,r.state_hash,r.metrics,r.archived_at,v.name AS source_name "
                "FROM development_sessions d JOIN runs r ON r.id=d.run_id LEFT JOIN innate_versions v ON v.id=d.source_version_id "
                "WHERE strpos(lower(d.name),lower(%s))>0 ORDER BY d.created_at DESC,d.id DESC LIMIT 31 OFFSET %s",
                (q, offset),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT id,name,run_id,checkpoint_id,state_hash,source_revision,source_time_us,birth_rule,parent_version_id,generation,created_at "
                "FROM innate_versions WHERE strpos(lower(name),lower(%s))>0 ORDER BY created_at DESC,id DESC LIMIT 31 OFFSET %s",
                (q, offset),
            ).fetchall()
        return {"rows": rows[:30], "more": len(rows) > 30}


def version_detail(database, project, version):
    with database.tx(project) as db:
        row = _version(db, version)
        lineage = db.execute(
            "WITH RECURSIVE chain AS (SELECT id,name,parent_version_id,generation,state_hash,run_id,0 AS depth FROM innate_versions WHERE id=%s "
            "UNION ALL SELECT v.id,v.name,v.parent_version_id,v.generation,v.state_hash,v.run_id,c.depth+1 FROM innate_versions v JOIN chain c ON v.id=c.parent_version_id WHERE c.depth<100) "
            "SELECT * FROM chain ORDER BY depth",
            (version,),
        ).fetchall()
        children = db.execute(
            "SELECT id,name,generation FROM innate_versions WHERE parent_version_id=%s ORDER BY created_at,id LIMIT 31",
            (version,),
        ).fetchall()
        development = db.execute(
            "SELECT id,name,objective,protocol_hash FROM development_sessions WHERE run_id=%s", (row["run_id"],)
        ).fetchone()
        return row | {
            "lineage": lineage,
            "lineage_truncated": bool(lineage and lineage[-1]["parent_version_id"]),
            "children": children[:30],
            "children_more": len(children) > 30,
            "development": development,
            "locked_paths": ["config", *IDENTITY_PATHS],
        }


def export(database, job):
    project = job["project_id"]
    with database.tx(project) as db:
        version = _version(db, job["params"]["innate_version_id"])
    image = born_image(database, project, version)
    profile = profile_from_spec(version["protocol"])
    fmt = job["params"]["format"]
    model = ArtifactCodec.encode(image, "json" if fmt == "json" else "tmind", profile=profile)
    metadata = {
        "innate_version_id": str(version["id"]),
        "birth_rule": version["birth_rule"],
        "source_hash": version["state_hash"],
        "state_hash": image.digest,
        "time_us": "0",
    }
    if fmt == "bundle":
        manifest = version_detail(database, project, version["id"])
        # Later descendants and UI controls are not part of this fixed version's
        # formation history. Re-export must not acquire facts from its future.
        for field in ("request_hash", "children", "children_more", "locked_paths"):
            manifest.pop(field)
        # The manifest describes formation; raw carriers remain in ordinary evidence exports.
        manifest = {
            "schema": "threemind.innate-package/1",
            "version": manifest,
            "model": metadata | {"sha256": hashlib.sha256(model).hexdigest()},
            "raw_evidence_included": False,
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("model.tmind", model)
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
        model = buffer.getvalue()
    artifact = database.put_artifact(
        job,
        f"innate-{version['id']}.{'zip' if fmt == 'bundle' else fmt}",
        "application/json" if fmt == "json" else "application/zip",
        model,
        metadata,
    )
    return {"artifact_id": str(artifact["id"]), **metadata}
