"""Immutable world revisions and validation; never mutate a running brain."""

from uuid import uuid5

from psycopg.types.json import Jsonb

from threemind_runtime.world import PhysicalWorld, compile_xml
from threemind_runtime.world_schema import CameraSensor, digest, parse_world

from .database import Conflict, NotFound


def validate(value, seed=0):
    if isinstance(value, dict) and value.get("schema_id") in ("threemind.robot-task/1", "threemind.robot-task/2"):
        from .robot_api import validate_robot

        return validate_robot(value, seed)
    spec = parse_world(value)
    # Static geometry validation does not require a GPU or fabricate sensory
    # frames. Cameras are still present in the compiled XML and original schema.
    import mujoco

    model = mujoco.MjModel.from_xml_string(compile_xml(spec))
    # Sensors never influence initial mechanics. Reuse the same initialization,
    # omitting their execution only for this explicitly non-running preview.
    preview = spec.model_copy(update={"sensors": []})
    with PhysicalWorld(preview, seed) as world:
        layout = world.observation()
    required = ["worker.world_v1"]
    if any(isinstance(s, CameraSensor) for s in spec.sensors):
        required.append("worker.world_rgb_v1")
    return {
        "valid": True,
        "protocol": spec.model_dump(mode="json"),
        "protocol_hash": spec.digest,
        "physical_hash": spec.physical_digest,
        "layout": layout,
        "model": {"bodies": model.nbody - 1, "geometries": model.ngeom, "dofs": model.nv, "motors": model.nu},
        "required_capabilities": required,
        "mujoco_version": mujoco.__version__,
    }


def get(db, identity, revision=None):
    row = db.execute(
        "SELECT v.*,d.title,d.archived FROM world_documents d JOIN world_versions v ON v.document_id=d.id "
        "WHERE d.id=%s AND v.revision=COALESCE(%s,d.revision)",
        (identity, revision),
    ).fetchone()
    if row is None:
        raise NotFound("World revision not found")
    return row


def save(database, project, actor, request):
    checked = validate(request.protocol)
    protocol = checked["protocol"]
    title = protocol.get("label", protocol.get("name", ""))
    if not title.strip():
        raise ValueError("请填写世界名称。")
    raw = request.model_dump(mode="json")
    if request.ai_call_id is None:
        raw.pop("ai_call_id")  # Preserve idempotency of requests submitted before schema 38.
    fingerprint = digest(raw)
    identity = request.document_id or uuid5(project, f"world:{request.operation_id}")
    with database.tx(project) as db:
        previous = db.execute("SELECT * FROM world_versions WHERE operation_id=%s", (request.operation_id,)).fetchone()
        if previous:
            if previous["request_hash"] != fingerprint:
                raise Conflict("同一个世界保存请求不能改为另一份内容。")
            return get(db, previous["document_id"], previous["revision"])
        if request.document_id is None:
            if request.expected_revision != 0:
                raise ValueError("新世界的起始修订必须为 0。")
            db.execute(
                "INSERT INTO world_documents(id,project_id,title,revision) VALUES(%s,%s,%s,0) ON CONFLICT(id) DO NOTHING",
                (identity, project, title),
            )
        document = db.execute("SELECT * FROM world_documents WHERE id=%s FOR UPDATE", (identity,)).fetchone()
        if document is None:
            raise NotFound("World document not found")
        # A concurrent retry may have committed while this transaction waited.
        previous = db.execute("SELECT * FROM world_versions WHERE operation_id=%s", (request.operation_id,)).fetchone()
        if previous:
            if previous["request_hash"] != fingerprint:
                raise Conflict("同一个世界保存请求不能改为另一份内容。")
            return get(db, previous["document_id"], previous["revision"])
        if document["revision"] != request.expected_revision or document["archived"]:
            raise Conflict("世界已被更新或归档，请刷新后重试。")
        ai_hash = None
        if request.ai_call_id:
            from .world_ai import review

            ai_hash = review(db, request.ai_call_id)
        revision = document["revision"] + 1
        db.execute(
            "INSERT INTO world_versions(project_id,document_id,revision,actor_id,operation_id,request_hash,protocol,protocol_hash,physical_hash,ai_call_id,ai_protocol_hash) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                project,
                identity,
                revision,
                actor,
                request.operation_id,
                fingerprint,
                Jsonb(protocol),
                checked["protocol_hash"],
                checked["physical_hash"],
                request.ai_call_id,
                ai_hash,
            ),
        )
        db.execute(
            "UPDATE world_documents SET title=%s,revision=%s,updated_at=clock_timestamp() WHERE id=%s",
            (title, revision, identity),
        )
        return get(db, identity, revision)
