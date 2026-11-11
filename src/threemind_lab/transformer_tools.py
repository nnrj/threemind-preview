"""Bounded optional Transformer jobs using existing project leases and artifact storage."""

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import Request
from psycopg.types.json import Jsonb
from pydantic import Field

from threemind_transformer.protocol import Prediction, Training, digest

from .ai_providers import require_actor
from .database import Conflict, NotFound
from .protocols import StrictModel


class TrainRequest(StrictModel):
    request_id: UUID
    protocol: Training


class PredictRequest(StrictModel):
    request_id: UUID
    query: Prediction


class FeedbackRequest(StrictModel):
    request_id: UUID
    run_id: UUID
    channel_ids: list[int] = Field(min_length=2, max_length=4096)
    intensity: float = Field(ge=0, le=1)


def submit(database, project, actor, identity, params):
    params = params | {"actor_id": str(actor)}
    with database.tx(project) as db:
        require_actor(db, project, actor)
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("transformer:" + str(identity),))
        existing = db.execute("SELECT id,project_id,params,kind FROM jobs WHERE id=%s", (identity,)).fetchone()
        if existing:
            if (
                str(existing["project_id"]) != str(project)
                or existing["kind"] != "transformer"
                or existing["params"] != params
            ):
                raise Conflict("相同请求编号已用于其他任务。")
            return {"id": str(identity), "replayed": True}
        db.execute(
            "INSERT INTO jobs(id,project_id,kind,params) VALUES(%s,%s,'transformer',%s)",
            (identity, project, Jsonb(params)),
        )
    return {"id": str(identity), "replayed": False}


def artifact_bytes(database, project, identity):
    with database.tx(project) as db:
        row = db.execute("SELECT bytes,sha256,metadata FROM artifacts WHERE id=%s", (identity,)).fetchone()
        if row is None:
            raise NotFound("Transformer model artifact")
        if row["metadata"].get("kind") != "tiny-transformer" or not 0 < row["bytes"] <= 64 * 1024 * 1024:
            raise ValueError("请选择本地 Transformer 数值模型文件。")
    from .binary_reads import object_bytes

    raw = object_bytes(database, project, "artifact", identity, maximum=64 * 1024**2)
    if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise ValueError("model artifact checksum mismatch")
    return raw


def execute(database, job, *, backend="native"):
    if job["params"].get("operation", "").startswith("language_"):
        from .language_tools import execute as language_execute

        return language_execute(database, job, backend=backend)
    params, project = job["params"], job["project_id"]
    with database.tx(project) as db:
        require_actor(db, project, params["actor_id"])
        database.fence(db, job)
    # PyTorch lives in a bounded child, not the long-lived Core worker or web process.
    with tempfile.TemporaryDirectory(prefix="threemind-transformer-") as temporary:
        folder = Path(temporary)
        model_path = folder / "model.tmt"
        failure_path = folder / "compute-failure.json"
        if params["operation"] == "train":
            protocol = Training.model_validate(params["protocol"])
            source = folder / "protocol.json"
            source.write_text(protocol.model_dump_json(), encoding="utf-8")
            command = [
                sys.executable,
                "-m",
                "threemind_transformer.cli",
                "train",
                str(source),
                "--output",
                str(model_path),
            ]
            timeout = protocol.wall_seconds + 45
        else:
            query = Prediction.model_validate(params["query"])
            model_path.write_bytes(artifact_bytes(database, project, params["model_artifact_id"]))
            command = [
                sys.executable,
                "-m",
                "threemind_transformer.cli",
                "predict",
                str(model_path),
                "--tokens",
                json.dumps(query.tokens),
                "--compute-device",
                query.compute_device,
                "--gpu-memory-mib",
                str(query.gpu_memory_mib),
                "--gpu-headroom-mib",
                str(query.gpu_headroom_mib),
            ]
            timeout = 45
        command.extend(["--failure-report", str(failure_path)])
        response = subprocess.run(
            command,
            capture_output=True,
            check=False,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if response.returncode:
            if failure_path.exists() and failure_path.stat().st_size <= 4 * 1024 * 1024:
                failure = database.put_artifact(
                    job,
                    "compute-failure.json",
                    "application/json",
                    failure_path.read_bytes(),
                    {"kind": "compute-failure", "external_contribution": True},
                )
                error = ValueError(
                    "Transformer computation failed; attempted devices and failure evidence were preserved"
                )
                error.execution_evidence = {"failure_artifact_id": str(failure["id"])}
                raise error
            raise ValueError(response.stderr.decode("utf-8", errors="replace")[-2000:])
        if len(response.stdout) > 4 * 1024 * 1024:
            raise ValueError("Transformer report exceeds budget")
        result = json.loads(response.stdout)
        with database.tx(project) as db:
            require_actor(db, project, params["actor_id"])
            database.fence(db, job)
        if params["operation"] == "train":
            if model_path.stat().st_size > 64 * 1024 * 1024:
                raise ValueError("Transformer model exceeds budget")
            item = database.put_artifact(
                job,
                "local-transformer.tmt",
                "application/zip",
                model_path.read_bytes(),
                {
                    "kind": "tiny-transformer",
                    "protocol_hash": digest(params["protocol"]),
                    "external_contribution": True,
                },
            )
            result["model_artifact_id"] = str(item["id"])
        evidence = database.put_artifact(
            job,
            "transformer-result.json",
            "application/json",
            json.dumps(result, ensure_ascii=False, allow_nan=False).encode(),
            {"kind": "transformer-result", "external_contribution": True},
        )
        return {"result_artifact_id": str(evidence["id"]), "summary": result}


def register(app, access):
    base = "/api/v2/projects/{project}/transformer"

    @app.get(base)
    def status(project: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            jobs = db.execute(
                "SELECT id,status,error,result,created_at,params->>'operation' operation FROM jobs "
                "WHERE kind='transformer' AND project_id=%s ORDER BY created_at DESC,id DESC LIMIT 50",
                (project,),
            ).fetchall()
            models = db.execute(
                "SELECT id,name,bytes,sha256,created_at FROM artifacts WHERE metadata->>'kind'='tiny-transformer' "
                "ORDER BY created_at DESC,id DESC LIMIT 100"
            ).fetchall()
        return {
            "optional_dependency_installed_here": importlib.util.find_spec("torch") is not None,
            "jobs": jobs,
            "models": models,
            "defaults": Training(sequences=[[0, 1]]).model_dump(exclude={"sequences"}),
            "new_task_compute_device": "auto",
            "core_feedback": False,
        }

    @app.post(base + "/training", status_code=202)
    def training(project: UUID, body: TrainRequest, request: Request):
        actor = access(request, project, write=True)
        return submit(
            app.state.db,
            project,
            actor["id"],
            body.request_id,
            {"operation": "train", "protocol": body.protocol.model_dump()},
        )

    @app.post(base + "/models/{model}/predictions", status_code=202)
    def predict(project: UUID, model: UUID, body: PredictRequest, request: Request):
        actor = access(request, project, write=True)
        artifact_bytes(app.state.db, project, model)
        return submit(
            app.state.db,
            project,
            actor["id"],
            body.request_id,
            {"operation": "predict", "model_artifact_id": str(model), "query": body.query.model_dump()},
        )

    @app.post(base + "/predictions/{prediction}/inputs", status_code=202)
    def feedback(project: UUID, prediction: UUID, body: FeedbackRequest, request: Request):
        from .inputs import submit as admit

        actor = access(request, project, write=True)
        with app.state.db.tx(project) as db:
            job = db.execute(
                "SELECT params,result FROM jobs WHERE id=%s AND project_id=%s AND kind='transformer' AND status='done'",
                (prediction, project),
            ).fetchone()
            if job is None or job["params"]["operation"] != "predict":
                raise NotFound("completed probability query")
            summary = job["result"]["summary"]
            # Execution evidence belongs to the job, not the unchanged sensory probability protocol.
            response = {
                key: summary[key]
                for key in (
                    "schema",
                    "model_sha256",
                    "request_hash",
                    "tokens",
                    "probabilities",
                    "external_contribution",
                    "core_feedback",
                )
            }
        return admit(
            app.state.db,
            project,
            body.run_id,
            actor,
            adapter_id="transformer-probability",
            request_id=body.request_id,
            payload={
                "response": response,
                "channel_ids": body.channel_ids,
                "intensity": body.intensity,
                "prediction_job_id": str(prediction),
            },
        )
