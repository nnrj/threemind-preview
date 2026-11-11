"""On-demand immutable scalar evidence, captured under a fenced worker lease."""

import hashlib
import json
import math
from collections import Counter
from uuid import uuid4

from psycopg.types.json import Jsonb

from . import ai_evidence, assessments, report_ecology, report_events, report_evolution, report_temporal
from .database import Conflict, NotFound, wire_rows
from .measurements import ENERGY_METRICS, energy_endpoints
from .notebooks import digest
from .permissions import connection_access
from .report_schema import CaptureSource

MAX_ROWS = 2_000_000
MAX_BYTES = 512 * 1024 * 1024
ANALYSIS_BYTES = 32 * 1024 * 1024


def require_actor(db, project, actor):
    return connection_access(db, actor, project, action="reports.write", write=True)


CATALOG = {
    **report_temporal.CATALOG,
    "assessment": assessments.UNITS,
    "ecology_trajectory": report_ecology.POPULATION_UNITS,
    "ecology_members": report_ecology.MEMBER_UNITS,
    "evolution": report_evolution.UNITS,
    "trajectory": {
        "nodes": "count",
        "edges": "count",
        "activation": "a.u.",
        "inhibition": "a.u.",
        "mean_activation": "a.u.",
        "mean_weight": "a.u.",
        "active_fraction": "fraction",
        "saturated_fraction": "fraction",
        "edge_density": "fraction",
        "pending_events": "count",
        **{name: "model energy units" for name in ENERGY_METRICS},
    },
    "nodes": {
        key: "a.u." for key in ("activation", "inhibition", "trace", "direct", "associative", "stability", "support")
    },
    "edges": {key: "a.u." for key in ("weight", "stability", "eligibility")},
    "events": {"event_count": "log entries"},
    "analysis": {
        "n": "independent pairs",
        "missing_pairs": "pairs",
        "control_mean": "endpoint units",
        "treatment_mean": "endpoint units",
        "difference": "endpoint units",
        "ci95_low": "endpoint units",
        "ci95_high": "endpoint units",
        "paired_dz": "standardized difference",
        "p": "probability",
        "p_holm": "probability",
    },
}


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def scalar(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None


def display_manifest(manifest):
    result = dict(manifest)
    if "analysis" in result:
        analysis = result["analysis"]
        result["analysis"] = {key: value for key, value in analysis.items() if key not in ("pairs", "metrics")}
        result["analysis"].update(
            pair_count=analysis.get("pair_count", len(analysis.get("pairs", []))),
            endpoint_count=len(analysis.get("metrics", [])),
            full_pair_and_endpoint_evidence="available in the captured source manifest",
        )
    provenance = dict(result["provenance"])
    if provenance.get("protocol"):
        protocol = dict(provenance["protocol"])
        replay = protocol.pop("replay", [])
        protocol.setdefault(
            "replay_summary",
            {
                "events": result.get("replay_event_count", len(replay)),
                "content": "available in the captured source manifest",
            },
        )
        provenance["protocol"] = protocol
    result["provenance"] = provenance
    return result


def request(database, project, actor, body):
    body = CaptureSource.model_validate(body)
    selection = body.model_dump(mode="json", exclude={"operation_id"})
    if body.kind not in report_temporal.KINDS:
        selection.pop("calibration_id")
        selection.pop("window_ids")
    if body.kind != "assessment":
        selection.pop("assessment_id")
    if body.kind not in report_ecology.KINDS:
        for key in ("ecology_id", "ecology_checkpoint_id"):
            selection.pop(key)
    if body.kind != "evolution":
        for key in ("evolution_id", "evolution_generation", "evolution_stage"):
            selection.pop(key)
    if body.kind != "events":
        # Preserve fingerprints for in-flight retries issued before the event source extension.
        selection.pop("event_group")
        selection.pop("event_kinds")
    fingerprint = digest(selection)
    metrics = body.metrics or list(CATALOG[body.kind])
    if not set(metrics) <= CATALOG[body.kind].keys():
        raise ValueError("select metrics from the source catalog")
    with database.tx(project) as db:
        require_actor(db, project, actor)
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("report-source:" + str(body.operation_id),))
        previous = db.execute(
            "SELECT id,job_id,request_hash FROM report_source_requests WHERE operation_id=%s", (body.operation_id,)
        ).fetchone()
        if previous:
            if previous["request_hash"] != fingerprint:
                raise Conflict("source operation ID reused with a different selection")
            return {**previous, "replayed": True}
        selection["metrics"] = metrics
        cp_id = None
        if body.kind in report_temporal.KINDS and body.calibration_id:
            experiment = report_temporal.calibration_snapshot(db, body.calibration_id)
            cp_id = experiment["checkpoint_id"]
            provenance = ai_evidence.wire(
                {
                    "run_id": experiment["run_id"],
                    "source_hash": experiment["source_hash"],
                    "calibration_id": body.calibration_id,
                    "artifact_id": experiment["result"]["artifact_id"],
                    "artifact_hash": experiment["sha256"],
                    "protocol": experiment["protocol"],
                    "selection_boundary": "completed immutable temporal experiment artifact",
                }
            )
        elif body.kind == "assessment":
            provenance = assessments.snapshot(db, body.assessment_id)
        elif body.kind in report_ecology.KINDS:
            provenance, resolved = report_ecology.freeze(db, body)
            provenance = ai_evidence.wire(provenance)
            selection.update(resolved)
        elif body.kind == "evolution":
            provenance, metrics = report_evolution.freeze(db, body)
            selection["metrics"] = metrics
        elif body.kind == "analysis":
            artifact = db.execute(
                "SELECT a.*,j.params FROM artifacts a JOIN jobs j ON j.id=a.job_id "
                "WHERE a.id=%s AND j.kind='analysis' AND j.status='done' "
                "AND a.id::text=j.result->>'artifact_id' AND a.media_type='application/json' FOR SHARE OF a,j",
                (body.analysis_artifact_id,),
            ).fetchone()
            if not artifact:
                raise NotFound("select the JSON result of a completed statistical analysis")
            if artifact["bytes"] > ANALYSIS_BYTES:
                raise ValueError("analysis exceeds the 32 MiB document source budget")
            provenance = ai_evidence.wire(
                {
                    "artifact_id": artifact["id"],
                    "artifact_hash": artifact["sha256"],
                    "analysis_parameters": artifact["params"],
                    "metadata": artifact["metadata"],
                }
            )
        else:
            run = db.execute("SELECT * FROM runs WHERE id=%s FOR SHARE", (body.run_id,)).fetchone()
            if not run:
                raise NotFound()
            cp = ai_evidence.checkpoint(db, body.run_id, body.checkpoint_id)
            cp_id = cp["id"]
            context = db.execute("SELECT context FROM checkpoints WHERE id=%s FOR SHARE", (cp_id,)).fetchone()[
                "context"
            ]
            selection["checkpoint_id"] = cp_id
            if body.kind in ("trajectory", "events", *report_temporal.KINDS):
                selection["from_us"] = body.from_us or "0"
                selection["through_us"] = body.through_us or cp["time_us"]
                if int(selection["through_us"]) > int(cp["time_us"]) or int(selection["from_us"]) > int(
                    selection["through_us"]
                ):
                    raise ValueError("select an interval at or before the fixed checkpoint")
            protocol = context.get("protocol")
            provenance = ai_evidence.wire(
                {
                    "run_id": run["id"],
                    "run_name": run["name"],
                    "checkpoint": cp,
                    "origin_hash": run["origin_hash"],
                    "protocol": protocol,
                    "protocol_hash": digest(protocol) if protocol else None,
                    "implementation": context.get("implementation"),
                    "protocol_available": protocol is not None,
                    "selection_boundary": "time <= checkpoint time AND commit revision <= checkpoint revision",
                }
            )
        source, job = uuid4(), uuid4()
        db.execute(
            "INSERT INTO jobs(id,project_id,kind,params) VALUES(%s,%s,'report_source',%s)",
            (job, project, Jsonb({"source_id": str(source), "source_kind": body.kind})),
        )
        db.execute(
            "INSERT INTO report_source_requests(id,project_id,actor_id,operation_id,request_hash,kind,run_id,"
            "checkpoint_id,analysis_artifact_id,job_id,selection,provenance,evolution_id,ecology_id,ecology_checkpoint_id,assessment_id,calibration_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                source,
                project,
                actor,
                body.operation_id,
                fingerprint,
                body.kind,
                provenance.get("run_id") if body.calibration_id else body.run_id,
                cp_id,
                body.analysis_artifact_id,
                job,
                Jsonb(selection),
                Jsonb(provenance),
                body.evolution_id,
                body.ecology_id,
                selection.get("ecology_checkpoint_id"),
                body.assessment_id,
                body.calibration_id,
            ),
        )
        return {"id": source, "job_id": job, "replayed": False}


def source(db, source_id, *, compact=False):
    fields = "r.*,s.manifest"
    if compact:
        # Prune replay carriers and pair-level analysis inside PostgreSQL, before decoding JSON in Lab.
        fields = (
            "r.id,r.project_id,r.actor_id,r.kind,r.run_id,r.checkpoint_id,r.analysis_artifact_id,r.job_id,r.selection,r.created_at,"
            "(r.provenance #- '{protocol,replay}') AS provenance,"
            "(s.manifest #- '{analysis,pairs}' #- '{provenance,protocol,replay}') || "
            "CASE WHEN s.manifest ? 'analysis' THEN jsonb_build_object('analysis',((s.manifest->'analysis')-'pairs') || "
            "jsonb_build_object('pair_count',jsonb_array_length(s.manifest->'analysis'->'pairs'))) ELSE '{}'::jsonb END || "
            "jsonb_build_object('summary_omits',jsonb_build_array('analysis.pairs','provenance.protocol.replay'),"
            "'replay_event_count',jsonb_array_length(s.manifest#>'{provenance,protocol,replay}')) AS manifest"
        )
    row = db.execute(
        f"SELECT {fields},s.content_hash,s.row_count,j.status,j.error FROM report_source_requests r "
        "JOIN jobs j ON j.id=r.job_id LEFT JOIN report_sources s ON s.id=r.id WHERE r.id=%s",
        (source_id,),
    ).fetchone()
    if not row:
        raise NotFound("research source is unavailable")
    return row


def ready(db, source_id):
    row = source(db, source_id, compact=True)
    if row["manifest"] is None:
        raise Conflict("wait for the source capture to complete")
    return row


def capture(database, job):
    project, source_id = job["project_id"], job["params"]["source_id"]
    with database.tx(project) as db:
        request_row = source(db, source_id)
        if request_row["manifest"] is not None:
            database.fence(db, job)
            return {"source_id": source_id, "content_hash": request_row["content_hash"], "replayed": True}
        require_actor(db, project, request_row["actor_id"])
    selection, provenance = request_row["selection"], request_row["provenance"]
    kind, metrics = request_row["kind"], selection["metrics"]
    network_rows = None
    original_bytes = None
    if kind == "analysis" or kind in report_temporal.KINDS and selection.get("calibration_id"):
        from .blob_store import object_chunks

        original = request_row["analysis_artifact_id"] if kind == "analysis" else provenance["artifact_id"]
        original_bytes = b"".join(object_chunks(database, project, "artifact", original))
        if len(original_bytes) > 64 * 1024**2:
            raise ValueError("report original exceeds the evidence-source budget")
    if kind in ("nodes", "edges"):
        from threemind_runtime import create_engine

        _, image = database.load_checkpoint(project, request_row["run_id"], request_row["checkpoint_id"])
        engine = create_engine(backend="reference", state=image)
        if len(engine.nodes if kind == "nodes" else engine.edges) > MAX_ROWS:
            raise ValueError("network source exceeds the 2,000,000 row capture budget")
        network_rows = engine.observation_nodes() if kind == "nodes" else engine.induced_edges(engine.nodes)
        # Readout projection is supplied by the Core; document code never advances it.
        provenance = provenance | {"projection": "Core analytic observation at checkpoint time; no advance or mutation"}
    with database.tx(project) as db:
        # Hold no job row lock while scanning/inserting; the heartbeat can renew.
        if not db.execute(
            "SELECT 1 FROM jobs WHERE id=%s AND generation=%s AND status='leased' AND lease_until>clock_timestamp()",
            (job["id"], job["generation"]),
        ).fetchone():
            raise Conflict("source capture lease expired")
        db.execute("SELECT id FROM report_source_requests WHERE id=%s FOR SHARE", (source_id,))
        coverage = {"missing_values_are_zero": False, "rows_are_independent_replicates": False}
        extra = {}
        if kind == "assessment":
            coverage.update(
                trials_declared=len(provenance["trials"]),
                trials_complete=sum(row["complete"] for row in provenance["trials"]),
                row_unit=provenance["row_unit"],
                shared_inherited_source=True,
            )
            extra["assessment"] = {
                key: provenance[key]
                for key in ("criteria", "all_trials_complete", "inference_boundary", "seed_boundary")
            }

            def rows():
                for trial in provenance["trials"]:
                    yield {
                        "time_us": None,
                        "label": str(trial["environment_seed"]),
                        "quality": "completed independent birth"
                        if trial["complete"]
                        else "incomplete independent birth",
                        "values": trial["values"],
                        "provenance": {k: v for k, v in trial.items() if k != "values"},
                    }

        elif kind in report_ecology.KINDS:

            def rows():
                for item in report_ecology.evidence_rows(db, request_row, coverage):
                    yield ai_evidence.wire(item)

        elif kind == "evolution":

            def rows():
                for item in report_evolution.evidence_rows(db, request_row, coverage):
                    yield ai_evidence.wire(item)

        elif kind == "analysis":
            raw = original_bytes
            if hashlib.sha256(raw).hexdigest() != provenance["artifact_hash"]:
                raise ValueError("analysis artifact hash mismatch")
            analysis = json.loads(raw)
            extra["analysis"] = analysis

            def rows():
                for item in analysis["metrics"]:
                    ci = item.get("ci95") or [None, None]
                    yield {
                        "time_us": None,
                        "label": item["metric"],
                        "quality": "frozen paired analysis",
                        "values": item | {"ci95_low": ci[0], "ci95_high": ci[1]},
                        "provenance": {"artifact_id": str(request_row["analysis_artifact_id"])},
                    }
        elif kind in report_temporal.KINDS:

            def rows():
                yield from report_temporal.evidence_rows(db, request_row, coverage, original_bytes=original_bytes)

        elif kind == "events":

            def rows():
                yield from report_events.evidence_rows(db, request_row, coverage)

        elif kind in ("nodes", "edges"):

            def rows():
                for item in network_rows:
                    yield {
                        "time_us": provenance["checkpoint"]["time_us"],
                        "label": str(item["id"]) if kind == "nodes" else f"{item['source']}→{item['target']}",
                        "quality": "complete checkpoint distribution",
                        "values": item,
                        "provenance": {
                            key: item[key] for key in (("id",) if kind == "nodes" else ("source", "target"))
                        },
                    }
        else:
            cp = provenance["checkpoint"]
            bounds = (request_row["run_id"], selection["from_us"], selection["through_us"], cp["revision"])
            legacy = db.execute(
                "SELECT count(*) AS n FROM observations WHERE run_id=%s AND time_us BETWEEN %s AND %s AND commit_revision IS NULL",
                bounds[:3],
            ).fetchone()["n"]
            coverage.update(
                legacy_commit_unknown_omitted=legacy,
                requested_from_us=selection["from_us"],
                requested_through_us=selection["through_us"],
            )

            def rows():
                with db.cursor(name="report_trajectory_" + uuid4().hex, row_factory=wire_rows) as cursor:
                    cursor.execute(
                        "SELECT time_us,sequence,quality,commit_revision,metrics FROM observations WHERE run_id=%s AND time_us BETWEEN %s AND %s AND commit_revision<=%s ORDER BY time_us",
                        bounds,
                    )
                    for item in cursor:
                        yield {
                            "time_us": item["time_us"],
                            "label": item["time_us"],
                            "quality": item["quality"],
                            "values": item["metrics"] | energy_endpoints(item["metrics"]),
                            "provenance": {"commit_revision": item["commit_revision"], "sequence": item["sequence"]},
                        }

        manifest = {
            "schema": "threemind.research-source/1",
            "kind": kind,
            "selection": selection,
            "provenance": provenance,
            "metrics": {m: CATALOG[kind][m] for m in metrics},
            **extra,
        }
        checksum = hashlib.sha256(encode(manifest) + b"\n")
        size, count, first_time, last_time, gap = 0, 0, None, None, 0
        missing, qualities, batch = Counter(), Counter(), []
        batch_bytes = 0
        insert = "INSERT INTO report_source_rows(project_id,source_id,ordinal,time_us,label,quality,values,provenance) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)"
        with db.cursor() as writer:
            for item in rows():
                values = {metric: scalar(item["values"].get(metric)) for metric in metrics}
                item["values"] = values
                item["ordinal"] = count
                encoded = encode(item) + b"\n"
                batch_bytes += len(encoded)
                size += len(encoded)
                if count >= MAX_ROWS or size > MAX_BYTES:
                    raise ValueError(
                        "source exceeds 2,000,000 rows or 512 MiB; select a smaller interval or fewer metrics; no partial source was saved"
                    )
                checksum.update(encoded)
                missing.update(key for key, value in values.items() if value is None)
                qualities[item["quality"]] += 1
                if item["time_us"] is not None:
                    now = int(item["time_us"])
                    if first_time is None:
                        first_time = now
                    if last_time is not None:
                        gap = max(gap, now - last_time)
                    last_time = now
                batch.append(
                    (
                        project,
                        source_id,
                        count,
                        item["time_us"],
                        item["label"],
                        item["quality"],
                        Jsonb(values),
                        Jsonb(item["provenance"]),
                    )
                )
                count += 1
                if len(batch) >= 1000 or batch_bytes >= 8 * 1024 * 1024:
                    writer.executemany(insert, batch)
                    batch.clear()
                    batch_bytes = 0
            if batch:
                writer.executemany(insert, batch)
        coverage.update(
            row_count=count,
            missing={m: missing[m] for m in metrics},
            qualities=dict(qualities),
            first_time_us=str(first_time) if first_time is not None else None,
            last_time_us=str(last_time) if last_time is not None else None,
            max_gap_us=str(gap),
            numeric_projection_bytes=size,
            sample_mean_is_time_mean=False,
        )
        manifest["coverage"] = coverage
        checksum.update(encode(coverage))
        database.fence(db, job)
        require_actor(db, project, request_row["actor_id"])
        # Deferred FK makes rows + completed manifest an atomic immutable capture.
        db.execute(
            "INSERT INTO report_sources(id,project_id,manifest,content_hash,row_count) VALUES(%s,%s,%s,%s,%s)",
            (source_id, project, Jsonb(manifest), checksum.hexdigest(), count),
        )
        return {"source_id": source_id, "content_hash": checksum.hexdigest(), "row_count": count}


def list_sources(database, project, *, offset=0):
    with database.tx(project) as db:
        rows = db.execute(
            "SELECT r.id,r.kind,r.run_id,r.checkpoint_id,r.created_at,r.provenance->>'run_name' AS run_name,"
            "j.status,j.error,s.row_count,s.content_hash FROM report_source_requests r JOIN jobs j ON j.id=r.job_id "
            "LEFT JOIN report_sources s ON s.id=r.id ORDER BY r.created_at DESC,r.id DESC LIMIT 51 OFFSET %s",
            (offset,),
        ).fetchall()
    return {"rows": rows[:50], "more": len(rows) > 50}


def get_source(database, project, source_id, *, compact=False):
    with database.tx(project) as db:
        return source(db, source_id, compact=compact)


def release(database, project, actor, source_id):
    import psycopg

    try:
        with database.tx(project) as db:
            require_actor(db, project, actor)
            row = db.execute(
                "SELECT job_id FROM report_source_requests WHERE id=%s FOR UPDATE", (source_id,)
            ).fetchone()
            if not row:
                raise NotFound()
            status = db.execute("SELECT status FROM jobs WHERE id=%s FOR SHARE", (row["job_id"],)).fetchone()["status"]
            if status in ("pending", "leased"):
                raise Conflict("wait for the capture job to finish before releasing its evidence")
            if db.execute(
                "SELECT 1 FROM research_document_sources WHERE source_id=%s LIMIT 1", (source_id,)
            ).fetchone():
                raise Conflict("a saved document revision references this source; its evidence must remain available")
            db.execute("DELETE FROM report_source_requests WHERE id=%s", (source_id,))
            db.execute(
                "INSERT INTO audit(user_id,action,resource) VALUES(%s,'research_source.release',%s)",
                (actor, str(source_id)),
            )
            return {"id": source_id, "released": True}
    except psycopg.errors.ForeignKeyViolation:
        raise Conflict("this source acquired a new reference; release was rolled back") from None


def data_rows(database, project, source_id, *, after=-1, limit=100):
    with database.tx(project) as db:
        row = ready(db, source_id)
        fields = report_events.PREVIEW_FIELDS if row["kind"] == "events" else report_events.FULL_FIELDS
        items = db.execute(
            f"SELECT {fields} FROM report_source_rows WHERE source_id=%s AND ordinal>%s ORDER BY ordinal LIMIT %s",
            (source_id, after, limit + 1),
        ).fetchall()
        return {
            "rows": items[:limit],
            "more": len(items) > limit,
            "row_count": row["row_count"],
            "content_hash": row["content_hash"],
        }


def full_row(database, project, source_id, ordinal):
    with database.tx(project) as db:
        source_row = ready(db, source_id)
        row = db.execute(
            f"SELECT {report_events.FULL_FIELDS} FROM report_source_rows WHERE source_id=%s AND ordinal=%s",
            (source_id, ordinal),
        ).fetchone()
        if row is None:
            raise NotFound("source row is unavailable")
        return {"row": row, "content_hash": source_row["content_hash"]}
