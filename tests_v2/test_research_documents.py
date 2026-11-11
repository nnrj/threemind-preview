import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb
from test_api import client_for

from threemind_core import Stimulus
from threemind_lab import auth, report_sources, research_documents
from threemind_lab.database import LOCAL_USER, Conflict, NotFound
from threemind_lab.protocols import RunSpec
from threemind_lab.report_schema import DocumentSpec
from threemind_lab.worker import Worker
from threemind_runtime import create_engine


def setup(database):
    project = database.create_project({"id": LOCAL_USER}, "Research documents")["id"]
    protocol = RunSpec(environment="manual", clock="unbounded", duration_s=1).model_dump()
    run = database.create_run(project, "Research model", protocol)
    engine = create_engine()
    engine.inject(Stimulus(0, ((1, 0.8), (2, 0.7))))
    engine.advance_to(1_000_000)
    cp = database.save_checkpoint(
        project,
        run["id"],
        engine.capture_state(),
        expected_revision=0,
        context={"protocol": protocol},
        status="completed",
        observations=[engine.metrics()],
    )
    with database.tx(project) as db:
        for i in range(80):
            db.execute(
                "INSERT INTO observations(project_id,run_id,time_us,sequence,metrics,quality,commit_revision) VALUES(%s,%s,%s,0,%s,%s,%s)",
                (
                    project,
                    run["id"],
                    str(i * 1000),
                    Jsonb({"activation": None if i == 5 else float(i), "edges": i, "mean_weight": i / 80}),
                    "fixture missing" if i == 5 else "fixture",
                    2 if i == 78 else None if i == 79 else 1,
                ),
            )
    return project, run, cp, engine


def capture(database, project, run, **changes):
    body = {
        "operation_id": str(uuid4()),
        "kind": "trajectory",
        "run_id": str(run["id"]),
        "metrics": ["activation", "edges", "mean_weight"],
        **changes,
    }
    request = report_sources.request(database, project, LOCAL_USER, body)
    assert Worker(database, name="reports-test").once()
    row = report_sources.get_source(database, project, request["id"])
    assert row["manifest"] is not None, row["error"]
    return row, body


def save_body(spec, revision=0, **changes):
    return {"operation_id": str(uuid4()), "expected_revision": revision, "spec": spec, **changes}


def test_capture_full_boundary_idempotency_missing_and_network_projection(database):
    project, run, cp, engine = setup(database)
    row, body = capture(database, project, run)
    assert row["row_count"] == 79  # 78 synthetic rows plus the committed terminal sample.
    assert row["manifest"]["coverage"]["legacy_commit_unknown_omitted"] == 1
    assert row["manifest"]["coverage"]["missing"]["activation"] == 1
    assert report_sources.request(database, project, LOCAL_USER, body)["id"] == row["id"]
    with pytest.raises(Conflict):
        report_sources.request(database, project, LOCAL_USER, body | {"metrics": ["edges"]})
    all_rows, after = [], -1
    while True:
        page = report_sources.data_rows(database, project, row["id"], after=after, limit=13)
        all_rows += page["rows"]
        if not page["more"]:
            break
        after = all_rows[-1]["ordinal"]
    assert len(all_rows) == 79 and all(r["provenance"]["commit_revision"] == 1 for r in all_rows)
    # Recalculate the canonical content hash, including exact integer timestamps.
    manifest = dict(row["manifest"])
    coverage = manifest.pop("coverage")
    checksum = hashlib.sha256(report_sources.encode(manifest) + b"\n")
    for item in all_rows:
        checksum.update(report_sources.encode(item) + b"\n")
    checksum.update(report_sources.encode(coverage))
    assert checksum.hexdigest() == row["content_hash"]
    histogram = research_documents.render(
        database,
        project,
        spec={
            "kind": "record",
            "title": "Full selected distribution",
            "sources": [str(row["id"])],
            "blocks": [
                {
                    "id": "distribution",
                    "type": "chart",
                    "source": str(row["id"]),
                    "metric": "activation",
                    "chart": "histogram",
                    "bins": 8,
                }
            ],
        },
    )["blocks"][0]["data"]
    assert sum(bucket["count"] for bucket in histogram["rows"]) == 78
    assert histogram["statistics"]["missing"] == 1 and histogram["rows"][-1]["upper"] == 77
    engine.advance_to(2_000_000)
    database.save_checkpoint(project, run["id"], engine.capture_state(), expected_revision=1)
    assert report_sources.get_source(database, project, row["id"])["content_hash"] == row["content_hash"]
    old_nodes, _ = capture(database, project, run, kind="nodes", metrics=["activation"], checkpoint_id=str(cp["id"]))
    _, image = database.load_checkpoint(project, run["id"], cp["id"])
    expected = create_engine(state=image, backend="reference").observation_nodes()
    assert [
        r["values"]["activation"] for r in report_sources.data_rows(database, project, old_nodes["id"])["rows"]
    ] == [n["activation"] for n in expected]
    edges, _ = capture(database, project, run, kind="edges", metrics=["weight"])
    assert edges["manifest"]["kind"] == "edges"
    with database.tx(project) as db:
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState), db.transaction():
            db.execute("UPDATE report_source_rows SET quality='fabricated' WHERE source_id=%s", (row["id"],))
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState), db.transaction():
            db.execute(
                "INSERT INTO report_source_rows SELECT project_id,source_id,9999,time_us,label,quality,values,provenance FROM report_source_rows WHERE source_id=%s LIMIT 1",
                (row["id"],),
            )


def test_document_versions_cas_references_and_untrusted_measurements(database):
    project, run, _, _ = setup(database)
    source, _ = capture(database, project, run)
    spec = research_documents.defaults(database, project, source["id"])
    spec["blocks"].append(
        {"id": "missing", "type": "fact", "source": str(source["id"]), "metric": "activation", "statistic": "missing"}
    )
    record = uuid4()
    first = save_body(spec)
    with ThreadPoolExecutor(2) as pool:
        saved = list(
            pool.map(lambda _: research_documents.save(database, project, LOCAL_USER, record, first), range(2))
        )
    assert {r["revision"] for r in saved} == {1} and sum(r["replayed"] for r in saved) == 1
    rendered = research_documents.render(database, project, record, points=10)
    assert rendered["blocks"][-1]["value"] == 1
    line = next(b for b in rendered["blocks"] if b["type"] == "chart")
    assert line["data"]["method"] == "ordinal-bin-sample-mean-min-max/1" and len(line["data"]["rows"]) == 10
    assert sum(r["total"] for r in line["data"]["rows"]) == source["row_count"]
    report_spec = {
        "kind": "report",
        "title": "Synthesis",
        "blocks": [
            {"id": "ref", "type": "record_block", "record_id": str(record), "revision": 1, "block_id": "missing"}
        ],
    }
    report = uuid4()
    research_documents.save(database, project, LOCAL_USER, report, save_body(report_spec))
    original = research_documents.render(database, project, report)
    revised = spec | {"title": "A revised record", "blocks": []}
    research_documents.save(database, project, LOCAL_USER, record, save_body(revised, 1))
    assert research_documents.render(database, project, report) == original
    assert research_documents.save(database, project, LOCAL_USER, record, first)["revision"] == 1
    with pytest.raises(Conflict):
        research_documents.save(database, project, LOCAL_USER, record, save_body(spec, 1))
    with pytest.raises(ValueError):
        DocumentSpec.model_validate(spec | {"blocks": [spec["blocks"][-1] | {"value": 999}]})
    with pytest.raises(ValueError):
        research_documents.render(
            database, project, spec=spec | {"blocks": [spec["blocks"][-1] | {"metric": "arbitrary.fake"}]}
        )
    with pytest.raises(ValueError):
        research_documents.save(database, project, LOCAL_USER, uuid4(), save_body(report_spec | {"kind": "record"}))
    with database.tx(project) as db:
        with pytest.raises(psycopg.errors.ForeignKeyViolation), db.transaction():
            db.execute("DELETE FROM report_source_requests WHERE id=%s", (source["id"],))
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState), db.transaction():
            db.execute("UPDATE research_document_versions SET spec='{}' WHERE document_id=%s", (record,))


def test_source_limits_roll_back_and_old_workers_do_not_claim(database, monkeypatch):
    project, run, _, _ = setup(database)
    req = report_sources.request(
        database, project, LOCAL_USER, {"operation_id": str(uuid4()), "run_id": str(run["id"]), "kind": "trajectory"}
    )
    assert database.claim("old-worker", capabilities={"features": {"worker.core": {"state": "available"}}}) is None
    monkeypatch.setattr(report_sources, "MAX_ROWS", 3)
    assert Worker(database).once()
    source = report_sources.get_source(database, project, req["id"])
    assert source["status"] == "failed" and "no partial source" in source["error"]
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM report_source_rows").fetchone()["n"] == 0
        assert db.execute("SELECT count(*) AS n FROM report_sources").fetchone()["n"] == 0
    report_sources.release(database, project, LOCAL_USER, req["id"])
    with pytest.raises(NotFound):
        report_sources.get_source(database, project, req["id"])


def test_unused_source_release_keeps_saved_evidence_and_stale_worker_cannot_publish(database):
    project, run, _, _ = setup(database)
    source, _ = capture(database, project, run)
    report_sources.release(database, project, LOCAL_USER, source["id"])
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM report_source_rows").fetchone()["n"] == 0
    used, _ = capture(database, project, run)
    spec = research_documents.defaults(database, project, used["id"])
    research_documents.save(database, project, LOCAL_USER, uuid4(), save_body(spec))
    with pytest.raises(Conflict):
        report_sources.release(database, project, LOCAL_USER, used["id"])
    requested = report_sources.request(
        database, project, LOCAL_USER, {"operation_id": str(uuid4()), "run_id": str(run["id"]), "kind": "trajectory"}
    )
    features = {
        "features": {
            name: {"state": "available"} for name in ("worker.research_documents", "worker.research_events_v1")
        }
    }
    old = database.claim("stale-capture", capabilities=features)
    assert old["id"] == requested["job_id"]
    with database.tx() as db:
        db.execute("UPDATE jobs SET lease_until=now()-interval '1 second' WHERE id=%s", (old["id"],))
    current = database.claim("new-capture", capabilities=features)
    with pytest.raises(Conflict):
        report_sources.capture(database, old)
    result = report_sources.capture(database, current)
    database.finish(current, result=result)
    assert report_sources.get_source(database, project, requested["id"])["content_hash"] == result["content_hash"]


def test_project_access_api_defaults_archive_and_validation(database):
    project, run, _, _ = setup(database)
    source, _ = capture(database, project, run)
    other = database.create_project({"id": LOCAL_USER}, "Other")["id"]
    with pytest.raises(NotFound):
        report_sources.get_source(database, other, source["id"])
    with client_for(database) as client:
        base = f"/api/v2/projects/{project}"
        spec = client.get(base + f"/report-sources/{source['id']}/template").json()
        record = uuid4()
        response = client.put(base + f"/research-documents/{record}", json=save_body(spec))
        assert response.status_code == 200, response.text
        assert client.get(base + f"/research-documents/{record}/render").status_code == 200
        assert (
            client.post(
                base + "/research-documents/preview",
                json=spec
                | {
                    "blocks": [
                        {
                            "id": "bad",
                            "type": "chart",
                            "source": str(source["id"]),
                            "metric": "activation",
                            "chart": "bar",
                        }
                    ]
                },
            ).status_code
            == 422
        )
        assert client.get(base + "/report-catalog").json()["limits"]["source_rows"] == report_sources.MAX_ROWS
        assert (
            client.post(
                base + f"/research-documents/{record}/archive", json={"expected_revision": 1, "archived": True}
            ).status_code
            == 200
        )
        assert client.get(base + "/research-documents").json()["rows"] == []
        assert len(client.get(base + "/research-documents?archived=true").json()["rows"]) == 1
    reader = auth.create_user(database, "document-reader", "test password for document reader")
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (project, reader["id"]))
    with client_for(database, "server") as client:
        csrf = client.post(
            "/api/v2/login", json={"username": "document-reader", "password": "test password for document reader"}
        ).json()["csrf"]
        client.headers["X-CSRF-Token"] = csrf
        assert client.get(base + f"/research-documents/{record}").status_code == 200
        assert client.put(base + f"/research-documents/{uuid4()}", json=save_body(spec)).status_code == 403
        assert client.get(f"/api/v2/projects/{other}/report-sources").status_code == 403


def test_frozen_analysis_keeps_pair_unit_ci_missing_and_phase_provenance(database):
    from lease_helpers import claim_as

    from threemind_lab.statistics import compare_pairs

    project, _, _, _ = setup(database)
    result = compare_pairs(
        [
            {
                "seed": i,
                "control": {"mean_activation": i, "unknown": None},
                "treatment": {"mean_activation": i + 0.5, "unknown": None},
                "phase_evidence": {"control": [{"complete": False, "settling": {"right_censored": True}}]},
            }
            for i in range(3)
        ],
        resamples=100,
    )
    queued = database.enqueue(project, "analysis", {"study_id": str(uuid4())})
    job = claim_as(database, "analysis-fixture")
    assert job["id"] == queued["id"]
    artifact = database.put_artifact(job, "paired-analysis.json", "application/json", json.dumps(result).encode())
    database.finish(job, result={"artifact_id": str(artifact["id"])})
    request = report_sources.request(
        database,
        project,
        LOCAL_USER,
        {"operation_id": str(uuid4()), "kind": "analysis", "analysis_artifact_id": str(artifact["id"])},
    )
    assert Worker(database).once()
    source = report_sources.get_source(database, project, request["id"])
    assert source["manifest"] is not None, source["error"]
    assert source["manifest"]["analysis"] == result
    spec = research_documents.defaults(database, project, source["id"])
    rendered = research_documents.render(database, project, spec=spec)
    table = next(b for b in rendered["blocks"] if b["type"] == "table")
    measured = next(row for row in table["rows"] if row["label"] == "mean_activation")["values"]
    missing = next(row for row in table["rows"] if row["label"] == "unknown")["values"]
    assert measured["n"] == 3 and measured["difference"] == 0.5 and measured["ci95_low"] == 0.5
    assert missing["n"] == 0 and missing["missing_pairs"] == 3 and missing["difference"] is None
    selected = {
        "id": "endpoint",
        "type": "chart",
        "chart": "bar",
        "source": str(source["id"]),
        "metric": "difference",
        "analysis_metric": "mean_activation",
    }
    chart = research_documents.render(database, project, spec=spec | {"blocks": [selected]})["blocks"][0]["data"]
    assert len(chart["rows"]) == 1 and chart["rows"][0]["value"] == 0.5
    with pytest.raises(ValueError):
        research_documents.render(database, project, spec=spec | {"blocks": [selected | {"analysis_metric": None}]})
