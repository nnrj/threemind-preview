"""Explicit portable-device transfer; imports always create a paused identity."""

import hashlib
from uuid import uuid4

from psycopg.types.json import Jsonb

from threemind_transformer.language_bundle import metadata, unpack
from threemind_transformer.language_protocol import LanguageCompute
from threemind_transformer.protocol import digest

from .ai_providers import require_actor
from .database import CHUNK_BYTES, Conflict
from .protocols import RunSpec


def import_bundle(database, project, actor, identity, name, raw, *, backend="native", job=None):
    fingerprint = digest({"bundle_sha256": hashlib.sha256(raw).hexdigest(), "actor": str(actor), "name": name})
    session, assets = unpack(raw, backend=backend)
    image = session.engine.capture_state()
    spec = RunSpec(
        kernel_id=session.kernel_id,
        environment="manual",
        clock="unbounded",
        seed=session.seed,
        config=image.to_dict()["config"],
        text_sensor=session.sensor_config,
        **session.readout_config,
    )
    with database.tx(project) as db:
        require_actor(db, project, actor)
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("language:" + str(identity),))
        existing = db.execute("SELECT fingerprint FROM language_sessions WHERE run_id=%s", (identity,)).fetchone()
        if existing:
            if existing["fingerprint"] != fingerprint:
                raise Conflict("import identifier belongs to another language device")
            database.fence(db, job)
            return {"run_id": str(identity), "replayed": True}
        if db.execute("SELECT id FROM runs WHERE id=%s", (identity,)).fetchone():
            raise Conflict("import identifier already belongs to another consciousness")
        import_job = uuid4()
        # A completed, synchronous import is the provenance owner of its files.
        # All files and the restored consciousness commit in this one transaction.
        db.execute(
            "INSERT INTO jobs(id,project_id,kind,status,params,result) VALUES(%s,%s,'transformer','done',%s,%s)",
            (
                import_job,
                project,
                Jsonb({"operation": "language_import", "actor_id": str(actor), "fingerprint": fingerprint}),
                Jsonb({"run_id": str(identity), "state_hash": image.digest}),
            ),
        )
        ids = {}
        for role, value in assets.items():
            if value is None:
                continue
            artifact = uuid4()
            ids[role] = str(artifact)
            kind = "language-head" if role == "head" else "language-scratch"
            db.execute(
                "INSERT INTO artifacts(id,project_id,job_id,name,media_type,bytes,sha256,metadata) VALUES(%s,%s,%s,%s,'application/octet-stream',%s,%s,%s)",
                (
                    artifact,
                    project,
                    import_job,
                    role + ".safetensors",
                    len(value),
                    hashlib.sha256(value).hexdigest(),
                    Jsonb(
                        {
                            "kind": kind,
                            "protocol": session.protocol.model_dump(),
                            "training": metadata(value),
                            "imported": True,
                        }
                    ),
                ),
            )
            for ordinal, offset in enumerate(range(0, len(value), CHUNK_BYTES)):
                db.execute(
                    "INSERT INTO artifact_chunks VALUES(%s,%s,%s,%s)",
                    (project, artifact, ordinal, value[offset : offset + CHUNK_BYTES]),
                )
        db.execute(
            "INSERT INTO runs(id,project_id,name,spec,origin_hash,origin_kind) VALUES(%s,%s,%s,%s,%s,'imported')",
            (identity, project, name, Jsonb(spec.model_dump()), image.digest),
        )
        db.execute(
            "INSERT INTO language_sessions(run_id,project_id,actor_id,fingerprint,protocol,compute,assets) VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (
                identity,
                project,
                actor,
                fingerprint,
                Jsonb(session.protocol.model_dump()),
                Jsonb(LanguageCompute().model_dump()),
                Jsonb(ids),
            ),
        )
        database.save_checkpoint(
            project,
            identity,
            image,
            context={"language": session.context()},
            expected_revision=0,
            status="dead" if session.engine.life == "dead" else "paused",
            transaction=db,
        )
        database.fence(db, job)
        if job:
            from .experiment_bundles import TransferCancelled
            current = db.execute("SELECT params FROM jobs WHERE id=%s", (job["id"],)).fetchone()
            if current["params"].get("cancel_requested"):
                raise TransferCancelled("language data restoration cancelled before publication")
    return {"run_id": str(identity), "state_hash": image.digest, "replayed": False}
