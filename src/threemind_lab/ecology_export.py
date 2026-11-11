"""Immutable population evidence, streamed only when explicitly requested."""

import csv
import io
import math
import zipfile
from tempfile import SpooledTemporaryFile
from uuid import UUID, uuid5

from psycopg.types.json import Jsonb

from threemind_runtime import ArtifactCodec
from threemind_runtime.profile import profile_from_spec

from .ai_providers import require_actor
from .database import Conflict, NotFound
from .database_stream import closing_iterator, stream_rows
from .ecology_store import campaign
from .evidence import SPOOL_BYTES, json_lines
from .evolution_export import CampaignArchive


def enqueue(database, project, identity, actor, request):
    job_id = uuid5(UUID(str(identity)), f"ecology-export:{request.operation_id}")
    with database.tx(project) as db:
        row = campaign(db, identity)
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"ecology-export:{job_id}",))
        previous = db.execute("SELECT * FROM jobs WHERE id=%s", (job_id,)).fetchone()
        if previous:
            if previous["params"]["actor_id"] != str(actor) or previous["params"]["request"] != request.model_dump(
                mode="json"
            ):
                raise Conflict("导出操作编号已用于其他请求。")
            return {k: previous[k] for k in ("id", "status", "result", "error")}
        cp = db.execute(
            "SELECT id FROM ecology_checkpoints WHERE id=%s AND campaign_id=%s",
            (request.checkpoint_id or row["checkpoint_id"], identity),
        ).fetchone()
        if cp is None:
            raise Conflict("尚无完整的种群恢复点可导出。")
        return db.execute(
            "INSERT INTO jobs(id,project_id,kind,params) VALUES(%s,%s,'ecology_export',%s) RETURNING id,status",
            (
                job_id,
                project,
                Jsonb(
                    {
                        "campaign_id": str(identity),
                        "actor_id": str(actor),
                        "checkpoint_id": str(cp["id"]),
                        "request": request.model_dump(mode="json"),
                    }
                ),
            ),
        ).fetchone()


def csv_stream(rows, fields):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(fields)
    yield output.getvalue().encode()
    with closing_iterator(rows) as iterator:
        for row in iterator:
            output.seek(0)
            output.truncate()
            writer.writerow([row.get(k) for k in fields])
            yield output.getvalue().encode()


def execute(database, job):
    project, params = job["project_id"], job["params"]
    with database.tx(project) as db:
        require_actor(db, project, params["actor_id"])
        previous = db.execute("SELECT id,sha256 FROM artifacts WHERE job_id=%s LIMIT 1", (job["id"],)).fetchone()
        if previous:
            return {
                "artifact_id": str(previous["id"]),
                "sha256": previous["sha256"],
                "checkpoint_id": params["checkpoint_id"],
            }
    with SpooledTemporaryFile(max_size=SPOOL_BYTES, mode="w+b") as output:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            package = CampaignArchive(archive)
            with database.tx(project, repeatable=True) as db:
                row = campaign(db, params["campaign_id"])
                cp = db.execute(
                    "SELECT * FROM ecology_checkpoints WHERE id=%s AND campaign_id=%s",
                    (params["checkpoint_id"], row["id"]),
                ).fetchone()
                if cp is None:
                    raise NotFound()
                metadata = {
                    "schema": "threemind.ecology-evidence/1",
                    "campaign_id": str(row["id"]),
                    "checkpoint_id": str(cp["id"]),
                    "revision": cp["revision"],
                    "model_time_us": str(cp["time_us"]),
                    "state_hash": cp["state_hash"],
                    "include_models": params["request"]["include_models"],
                    "scope": "all individuals and committed ecological evidence up to the fixed population checkpoint; full per-brain input/readout histories are available through the referenced run checkpoints",
                    "units": "body resource accounting uses declared abstract units, not joules or Core energy",
                    "censoring": "living bodies and viable cores at this endpoint are right-censored; shared-world individuals are not independent replicates",
                }
                package.json("protocol.json", row["protocol"])
                package.json("population-state.json", cp["context"])
                package.json("physical-observation.json", cp["observation"])
                package.write(
                    "individuals.jsonl",
                    json_lines(
                        stream_rows(
                            db,
                            "SELECT m.*,c.checkpoint_id,c.state_hash,c.outcome FROM ecology_checkpoint_members c JOIN ecology_members m USING(campaign_id,individual) WHERE c.population_checkpoint_id=%s ORDER BY length(m.individual),m.individual",
                            (cp["id"],),
                            batch=50,
                        )
                    ),
                )
                package.write(
                    "events.jsonl",
                    json_lines(
                        stream_rows(
                            db,
                            "SELECT e.* FROM ecology_events e JOIN ecology_checkpoints c ON c.id=e.population_checkpoint_id WHERE e.campaign_id=%s AND c.revision<=%s ORDER BY e.id",
                            (row["id"], cp["revision"]),
                            batch=100,
                        )
                    ),
                )
                fields = [
                    "revision",
                    "time_us",
                    "individuals",
                    "living_bodies",
                    "viable_cores",
                    "births",
                    "body_failures",
                    "maximum_generation",
                    "deferred_population",
                    "deferred_budget",
                ]

                def metrics():
                    with closing_iterator(
                        stream_rows(
                            db,
                            "SELECT revision,time_us,observation->'population' AS metrics FROM ecology_checkpoints WHERE campaign_id=%s AND revision<=%s ORDER BY revision",
                            (row["id"], cp["revision"]),
                            batch=100,
                        )
                    ) as rows:
                        for item in rows:
                            yield {"revision": item["revision"], "time_us": item["time_us"], **item["metrics"]}

                package.write("population.csv", csv_stream(metrics(), fields))
                stride = max(1, math.ceil(cp["revision"] / 2000))
                series = db.execute(
                    "SELECT time_us,observation->'population' AS metrics FROM ecology_checkpoints WHERE campaign_id=%s AND revision<=%s AND (revision %% %s=0 OR revision=1 OR revision=%s) ORDER BY revision",
                    (row["id"], cp["revision"], stride, cp["revision"]),
                ).fetchall()
                metadata["figure_sampling"] = {"stride_commits": stride, "points": len(series), "complete_csv": True}
                if params["request"]["include_models"]:
                    profile = profile_from_spec(row["protocol"]["base"])
                    with closing_iterator(
                        stream_rows(
                            db,
                            "SELECT individual,run_id,checkpoint_id FROM ecology_checkpoint_members WHERE population_checkpoint_id=%s ORDER BY individual",
                            (cp["id"],),
                            batch=20,
                        )
                    ) as members:
                        for member in members:
                            _, image = database.load_checkpoint(project, member["run_id"], member["checkpoint_id"])
                            package.bytes(
                                f"models/{member['individual']}.tmind",
                                ArtifactCodec.encode(image, "tmind", profile=profile),
                            )
                require_actor(db, project, params["actor_id"])
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            from matplotlib.figure import Figure

            chart = Figure(figsize=(10, 4.8), layout="constrained")
            FigureCanvasAgg(chart)
            axis = chart.subplots()
            for key, label in (
                ("living_bodies", "Living bodies"),
                ("viable_cores", "Cores not observed dead"),
                ("births", "Cumulative offspring births"),
            ):
                axis.step(
                    [int(item["time_us"]) / 1e6 for item in series],
                    [item["metrics"][key] for item in series],
                    where="post",
                    label=label,
                )
            axis.set(
                xlabel="Global simulated time (s)",
                ylabel="Count",
                title="Ecological observations at committed checkpoints",
            )
            axis.legend()
            axis.grid(alpha=0.15)
            for fmt in ("svg", "png"):
                image = io.BytesIO()
                chart.savefig(image, format=fmt, dpi=160)
                package.bytes("population." + fmt, image.getvalue())
            chart.clear()
            package.json("manifest.json", metadata | {"files": package.files, "file_bytes": package.sizes})
        output.seek(0)
        saved = database.put_artifact_stream(job, "ecology-evidence.zip", "application/zip", output, metadata)
        return {"artifact_id": str(saved["id"]), "sha256": saved["sha256"], "checkpoint_id": params["checkpoint_id"]}
