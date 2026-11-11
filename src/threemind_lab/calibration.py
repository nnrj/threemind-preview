"""Frozen source admission and evidence publication for isolated probe jobs."""

import hashlib
import json
from dataclasses import asdict
from uuid import uuid4

import psutil
from psycopg.types.json import Jsonb

from threemind_runtime.calibration import calibrate, encode, parse_protocol
from threemind_runtime.sensory import TextSensorConfig

from .ai_providers import require_actor
from .database import Conflict, NotFound
from .notebooks import digest
from .protocols import RunSpec
from .provenance import capture_implementation


def request(database, project, run_id, actor, *, operation_id, protocol, checkpoint_id=None):
    supplied_protocol = dict(protocol)
    protocol = parse_protocol(protocol).model_dump(mode="json")
    fingerprint = digest(
        {"run": str(run_id), "checkpoint": str(checkpoint_id) if checkpoint_id else None, "protocol": protocol}
    )
    with database.tx(project) as db:
        require_actor(db, project, actor)
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("probe:" + str(operation_id),))
        prior = db.execute(
            "SELECT id,job_id,request_hash FROM probe_calibrations WHERE operation_id=%s", (operation_id,)
        ).fetchone()
        if prior:
            if prior["request_hash"] != fingerprint:
                raise Conflict("probe request ID reused with different content")
            return prior | {"replayed": True}
        run = db.execute("SELECT spec,revision FROM runs WHERE id=%s FOR SHARE", (run_id,)).fetchone()
        if not run:
            raise NotFound()
        cp = db.execute(
            "SELECT id,state_hash FROM checkpoints WHERE run_id=%s AND (%s::uuid IS NULL OR id=%s) "
            "ORDER BY revision DESC LIMIT 1 FOR SHARE",
            (run_id, checkpoint_id, checkpoint_id),
        ).fetchone()
        if not cp:
            raise Conflict("需要一个已保存的恢复点；原意识无需被校准推进。")
        # The scientific sensory configuration is inherited, not silently reset.
        spec = RunSpec.model_validate(run["spec"])
        context = db.execute(
            "SELECT context->'protocol' protocol FROM checkpoints WHERE id=%s", (cp["id"],)
        ).fetchone()["protocol"]
        if context:
            spec = RunSpec.model_validate(context)
        if protocol.get("mode") == "temporal" and "temporal_readout" not in supplied_protocol:
            protocol["temporal_readout"] = asdict(spec.temporal_readout)
        if (
            protocol.get("mode") == "temporal"
            and "activity_readout" not in supplied_protocol
            and spec.activity_readout.enabled
        ):
            protocol["activity_readout"] = asdict(spec.activity_readout)
        ident, job = uuid4(), uuid4()
        db.execute(
            "INSERT INTO jobs(id,project_id,kind,params) VALUES(%s,%s,'probe_calibration',%s)",
            (
                job,
                project,
                Jsonb({"calibration_id": str(ident), "observation_mode": protocol.get("mode", "fixed-window")}),
            ),
        )
        db.execute(
            "INSERT INTO probe_calibrations(id,project_id,actor_id,operation_id,request_hash,run_id,checkpoint_id,"
            "source_hash,protocol,sensor_config,sensor_seed,job_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                ident,
                project,
                actor,
                operation_id,
                fingerprint,
                run_id,
                cp["id"],
                cp["state_hash"],
                Jsonb(protocol),
                Jsonb(asdict(spec.text_sensor)),
                spec.seed,
                job,
            ),
        )
        return {
            "id": ident,
            "job_id": job,
            "checkpoint_id": cp["id"],
            "source_hash": cp["state_hash"],
            "replayed": False,
        }


def detail(database, project, ident):
    with database.tx(project) as db:
        row = db.execute(
            "SELECT c.*,j.status,j.result,j.error FROM probe_calibrations c JOIN jobs j ON j.id=c.job_id WHERE c.id=%s",
            (ident,),
        ).fetchone()
        if not row:
            raise NotFound()
        return row


def execute(database, job, *, backend="native", implementation=None):
    row = detail(database, job["project_id"], job["params"]["calibration_id"])
    with database.tx(job["project_id"]) as db:
        require_actor(db, job["project_id"], row["actor_id"])
        database.fence(db, job)
    _, image = database.load_checkpoint(job["project_id"], row["run_id"], row["checkpoint_id"])
    if image.digest != row["source_hash"]:
        raise ValueError("calibration source hash mismatch")

    def guard():
        if psutil.Process().memory_info().rss > 2 * 1024**3:
            raise MemoryError("calibration process memory budget exceeded")

    with database.tx(job["project_id"]) as db:
        source_context = db.execute(
            "SELECT context FROM checkpoints WHERE id=%s AND run_id=%s", (row["checkpoint_id"], row["run_id"])
        ).fetchone()["context"]

    result, raw = calibrate(
        image,
        seed=row["sensor_seed"],
        sensor_config=TextSensorConfig(**row["sensor_config"]),
        protocol=parse_protocol(row["protocol"]),
        backend=backend,
        guard=guard,
        source_context=source_context,
        provenance={
            "implementation": implementation or capture_implementation(backend),
            "source": {k: str(row[k]) for k in ("id", "run_id", "checkpoint_id", "source_hash")},
        },
    )
    with database.tx(job["project_id"]) as db:
        require_actor(db, job["project_id"], row["actor_id"])
        database.fence(db, job)
    archive = database.put_artifact(
        job,
        "probe-evidence.zip",
        "application/zip",
        raw,
        {"source_hash": image.digest, "sha256": hashlib.sha256(raw).hexdigest()},
    )
    display = database.put_artifact(
        job,
        "probe-calibration.json",
        "application/json",
        encode(result),
        {"source_hash": image.digest, "calibration_id": str(row["id"])},
    )
    return {
        "artifact_id": str(display["id"]),
        "bundle_artifact_id": str(archive["id"]),
        "source_hash": image.digest,
        "result_sha256": display["sha256"],
        "bundle_sha256": archive["sha256"],
    }


def result(database, project, ident):
    row = detail(database, project, ident)
    if row["status"] != "done":
        raise Conflict("校准尚未完成。")
    from .binary_reads import object_bytes

    raw = object_bytes(database, project, "artifact", row["result"]["artifact_id"], maximum=64 * 1024**2)
    if hashlib.sha256(raw).hexdigest() != row["result"]["result_sha256"]:
        raise ValueError("calibration result hash mismatch")
    return json.loads(raw)
