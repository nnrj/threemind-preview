"""On-demand campaign evidence, sampled once per successful export job."""

import csv
import io
import zipfile
from tempfile import SpooledTemporaryFile
from uuid import UUID, uuid5

from psycopg.types.json import Jsonb

from .ai_providers import require_actor
from .database import Conflict
from .database_stream import closing_iterator, stream_rows
from .evidence import SPOOL_BYTES, EvidenceArchive, json_lines
from .evolution import _campaign

EXPORT_BYTES = 2 * 1024**3


class CampaignArchive(EvidenceArchive):
    """Fail atomically at the documented budget; never truncate evidence."""

    def write(self, name, chunks):
        consumed = sum(self.sizes.values())

        def bounded():
            nonlocal consumed
            with closing_iterator(chunks) as iterator:
                for chunk in iterator:
                    consumed += len(chunk)
                    if consumed > EXPORT_BYTES:
                        raise ValueError(
                            "多代证据超过 2 GiB 未压缩导出预算；未保存截断文件，请按个体或固定来源分别导出。"
                        )
                    yield chunk

        super().write(name, bounded())


def figures(rows):
    """Small aggregate series only; all underlying candidate scores stay in CSV."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    for metric in sorted({row["metric"] for row in rows}):
        series = [row for row in rows if row["metric"] == metric]
        chart = Figure(figsize=(10, 4.8), layout="constrained")
        FigureCanvasAgg(chart)
        axis = chart.subplots()
        generations = [row["generation"] + 1 for row in series]
        axis.fill_between(
            generations,
            [r["minimum"] for r in series],
            [r["maximum"] for r in series],
            color="#79a9a1",
            alpha=0.25,
            label="Candidate minimum to maximum (not a CI)",
        )
        marker = "o" if len(series) <= 100 else None
        axis.plot(
            generations,
            [r["mean"] for r in series],
            color="#257e70",
            marker=marker,
            markersize=3,
            label="All-candidate mean",
        )
        axis.plot(
            generations,
            [r["parent_mean"] for r in series],
            color="#b36c25",
            marker=marker,
            markersize=2,
            label="Selected-parent mean",
        )
        axis.set(xlabel="Generation (1-based)", ylabel=metric, title=f"Directed selection: {metric}")
        axis.grid(alpha=0.15)
        axis.legend(fontsize=8)
        for format in ("svg", "png"):
            output = io.BytesIO()
            chart.savefig(output, format=format, dpi=160)
            yield f"figures/{metric}.{format}", output.getvalue()
        chart.clear()


def enqueue(database, project, identity, actor, operation_id):
    job_id = uuid5(UUID(str(identity)), f"export:{operation_id}")
    with database.tx(project) as db:
        _campaign(db, identity, summary=True)
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"evolution-export:{job_id}",))
        previous = db.execute("SELECT * FROM jobs WHERE id=%s", (job_id,)).fetchone()
        if previous:
            if previous["kind"] != "evolution_export" or previous["params"]["actor_id"] != str(actor):
                raise Conflict("导出操作编号已由其他请求使用。")
            return {key: previous[key] for key in ("id", "status", "result", "error")}
        return db.execute(
            "INSERT INTO jobs(id,project_id,kind,params) VALUES(%s,%s,'evolution_export',%s) RETURNING id,status",
            (job_id, project, Jsonb({"campaign_id": str(identity), "actor_id": str(actor)})),
        ).fetchone()


def result(row):
    return {
        "artifact_id": str(row["id"]),
        "sha256": row["sha256"],
        "snapshot_revision": row["metadata"]["snapshot_revision"],
    }


def execute(database, job):
    project, identity = job["project_id"], job["params"]["campaign_id"]
    with database.tx(project) as db:
        require_actor(db, project, job["params"]["actor_id"])
        existing = db.execute(
            "SELECT id,sha256,metadata FROM artifacts WHERE job_id=%s ORDER BY id LIMIT 1", (job["id"],)
        ).fetchone()
        if existing:
            return result(existing)
    with SpooledTemporaryFile(max_size=SPOOL_BYTES, mode="w+b") as output:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            package = CampaignArchive(archive)
            with database.tx(project, repeatable=True) as db:
                declared = _campaign(db, identity)
                stamp = db.execute("SELECT transaction_timestamp() AS captured_at").fetchone()["captured_at"]
                metadata = {
                    "schema": "threemind.evolution-evidence/1",
                    "campaign_id": str(identity),
                    "snapshot_revision": declared["revision"],
                    "captured_at": str(stamp),
                    "scope": "one transaction snapshot when the export worker captures; completed outcomes are pinned, unfinished members remain explicitly unfinished",
                    "raw_scope": "all campaign members, declared endpoint metrics, selections and journal; full model/trajectory/input evidence remains available at each referenced run and checkpoint",
                    "interpretation": "directed selection under a declared protocol; not a consciousness measure or proof of ecological or biological evolution",
                    "indices": "generation, slot and block_index are zero-based in data; rank is one-based; figure generation axes are one-based",
                    "chart_scope": "descriptive aggregates of all completed selection generations at this snapshot; min/max are not confidence intervals; final verification is not selection",
                    "uncompressed_budget_bytes": EXPORT_BYTES,
                }
                package.json("campaign.json", declared)
                for name, query in (
                    (
                        "members.jsonl",
                        "SELECT m.*,r.status AS status_at_export FROM evolution_members m JOIN runs r ON r.id=m.run_id WHERE m.campaign_id=%s ORDER BY m.generation,m.stage,m.slot,m.block_index",
                    ),
                    (
                        "selections.jsonl",
                        "SELECT * FROM evolution_selections WHERE campaign_id=%s ORDER BY generation,rank",
                    ),
                    (
                        "journal.jsonl",
                        "SELECT revision,kind,payload,created_at FROM evolution_events WHERE campaign_id=%s ORDER BY revision",
                    ),
                    (
                        "checkpoint-provenance.jsonl",
                        (
                            "SELECT m.run_id,c.id AS checkpoint_id,c.revision,c.time_us,c.state_hash,"
                            "c.context#>>'{implementation,source_sha256}' AS implementation_source_sha256,"
                            "c.context#>>'{implementation,native_binary_sha256}' AS native_binary_sha256 "
                            "FROM evolution_members m JOIN checkpoints c ON c.id=m.checkpoint_id WHERE m.campaign_id=%s ORDER BY m.generation,m.stage,m.slot,m.block_index"
                        ),
                    ),
                    (
                        "implementations.jsonl",
                        (
                            "SELECT DISTINCT c.context->'implementation' AS implementation FROM evolution_members m "
                            "JOIN checkpoints c ON c.id=m.checkpoint_id WHERE m.campaign_id=%s"
                        ),
                    ),
                    (
                        "worker-assignments.jsonl",
                        (
                            "SELECT a.* FROM job_assignments a JOIN jobs j ON j.id=a.job_id WHERE j.id IN "
                            "(SELECT job_id FROM evolution_campaigns WHERE id=%s) OR j.run_id IN "
                            "(SELECT run_id FROM evolution_members WHERE campaign_id=%s) ORDER BY a.job_id,a.generation"
                        ),
                    ),
                ):
                    arguments = (identity, identity) if name == "worker-assignments.jsonl" else (identity,)
                    package.write(name, json_lines(stream_rows(db, query, arguments, batch=100)))

                def scores():
                    buffer = io.StringIO(newline="")
                    writer = csv.writer(buffer)
                    writer.writerow(
                        ["generation", "slot", "rank", "selected", "metric", "score", "candidate_version_id"]
                    )
                    yield buffer.getvalue().encode()
                    with closing_iterator(
                        stream_rows(
                            db,
                            "SELECT generation,slot,rank,selected,candidate_version_id,scores FROM evolution_selections WHERE campaign_id=%s ORDER BY generation,rank",
                            (identity,),
                            batch=100,
                        )
                    ) as rows:
                        for row in rows:
                            for metric, value in row["scores"].items():
                                buffer.seek(0)
                                buffer.truncate()
                                writer.writerow(
                                    [
                                        row["generation"],
                                        row["slot"],
                                        row["rank"],
                                        row["selected"],
                                        metric,
                                        value,
                                        row["candidate_version_id"],
                                    ]
                                )
                                yield buffer.getvalue().encode()

                package.write("scores.csv", scores())
                progress = db.execute(
                    "SELECT generation,s.key AS metric,min(s.value::double precision) AS minimum,"
                    "max(s.value::double precision) AS maximum,avg(s.value::double precision) AS mean,"
                    "avg(s.value::double precision) FILTER(WHERE selected) AS parent_mean,count(*) AS candidates "
                    "FROM evolution_selections CROSS JOIN LATERAL jsonb_each_text(scores) s "
                    "WHERE campaign_id=%s GROUP BY generation,s.key ORDER BY generation,s.key",
                    (identity,),
                ).fetchall()
                package.json("descriptive-series.json", progress)
                require_actor(db, project, job["params"]["actor_id"])
            # Plot the captured aggregates after releasing the database snapshot.
            for name, raw in figures(progress):
                package.bytes(name, raw)
            package.json("manifest.json", metadata | {"files": package.files, "file_bytes": package.sizes})
        output.seek(0)
        row = database.put_artifact_stream(job, "evolution-evidence.zip", "application/zip", output, metadata)
        return result(row)
