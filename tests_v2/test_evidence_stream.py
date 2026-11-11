import csv
import hashlib
import io
import json
import threading
import zipfile
from tempfile import SpooledTemporaryFile

import psycopg
import pytest
from lease_helpers import claim_as
from psycopg.types.json import Jsonb
from test_api import client_for

from threemind_core import Engine, Stimulus
from threemind_lab import evidence
from threemind_lab.database import CHUNK_BYTES, Conflict
from threemind_lab.database_stream import stream_rows
from threemind_lab.protocols import RunSpec
from threemind_lab.statistics import summarize
from threemind_lab.worker import Worker
from threemind_runtime import ArtifactCodec


def test_evidence_stream_pins_commit_boundary_preserves_unknown_rows_and_cleans_spool(database, monkeypatch):
    temporary = []

    def spool(*args, **kwargs):
        kwargs["max_size"] = 1  # Exercise the actual disk spill and cleanup.
        value = SpooledTemporaryFile(*args, **kwargs)  # noqa: SIM115 -- caller owns the returned context manager
        temporary.append(value)
        return value

    monkeypatch.setattr(evidence, "SpooledTemporaryFile", spool)
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Frozen streamed evidence"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        spec = RunSpec(environment="manual", clock="unbounded").model_dump()
        run = database.create_run(project, "Boundary", spec)["id"]
        engine = Engine()
        engine.inject(Stimulus(0, ((1, 0.5), (2, 0.3))))
        engine.advance_to(0)
        first = engine.metrics()
        database.save_checkpoint(
            project,
            run,
            engine.capture_state(),
            expected_revision=0,
            status="paused",
            observations=[first],
            context={"protocol": spec},
        )
        engine.advance_to(1000)
        last = engine.metrics()
        image = engine.capture_state()
        cp = database.save_checkpoint(
            project,
            run,
            image,
            expected_revision=1,
            status="paused",
            observations=[last],
            context={"protocol": spec},
            events=[
                {
                    "key": "visible",
                    "time_us": "1000",
                    "kind": "telemetry_sample",
                    "payload": {"label": '汉字\n"\\\t', "value": 0.5, "large": 2**100, "nested": [None, {}]},
                }
            ],
        )
        # Later commits can contain earlier timestamps; time alone is not an
        # immutable boundary. Unknown legacy commits must not enter statistics.
        database.save_checkpoint(
            project,
            run,
            image,
            expected_revision=2,
            status="paused",
            context={"protocol": spec},
            observations=[last | {"time_us": "500", "activation": 999.0}],
            events=[
                {
                    "key": "future-commit",
                    "time_us": "1000",
                    "kind": "telemetry_sample",
                    "payload": {"future": True},
                }
            ],
        )
        with database.tx(project) as db:
            db.execute(
                "INSERT INTO observations(project_id,run_id,time_us,sequence,metrics) VALUES(%s,%s,750,0,%s)",
                (project, run, Jsonb(last | {"time_us": "750", "activation": 888.0})),
            )
            db.execute(
                "INSERT INTO events(project_id,run_id,event_key,time_us,kind,payload) VALUES(%s,%s,'unknown',750,'telemetry_sample',%s)",
                (project, run, Jsonb({"legacy": True})),
            )
        task = client.post(
            f"{root}/runs/{run}/exports", json={"format": "evidence", "checkpoint_id": str(cp["id"])}
        ).json()
        assert Worker(database).once()
        job = next(j for j in client.get(root + "/jobs").json() if j["id"] == task["id"])
        assert job["status"] == "done", job.get("error")
        result = client.get(f"{root}/artifacts/{job['result']['artifact_id']}").content
        entry = next(a for a in client.get(root + "/artifacts").json() if a["id"] == job["result"]["artifact_id"])
        assert entry["metadata"]["evidence_boundary"]["unscoped_counts"] == {"events": 1, "observations": 1}
        with zipfile.ZipFile(io.BytesIO(result)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["summary"] == summarize([first, last], spec)
            assert manifest["commit_boundary"]["unscoped_counts"] == {"events": 1, "observations": 1}
            assert [r["time_us"] for r in csv.DictReader(io.StringIO(archive.read("observations.csv").decode()))] == [
                "0",
                "1000",
            ]
            scoped = [json.loads(r) for r in archive.read("events.jsonl").splitlines()]
            assert len(scoped) == 1 and scoped[0]["payload"] == {
                "label": '汉字\n"\\\t',
                "value": 0.5,
                "large": 2**100,
                "nested": [None, {}],
            }
            assert archive.read("telemetry-samples.jsonl") == archive.read("events.jsonl")
            assert json.loads(archive.read("unscoped-events.jsonl"))["payload"] == {"legacy": True}
            assert json.loads(archive.read("unscoped-observations.jsonl"))["metrics"]["activation"] == 888.0
            for name, digest in manifest["files"].items():
                raw = archive.read(name)
                assert hashlib.sha256(raw).hexdigest() == digest
                assert manifest["file_bytes"][name] == len(raw)
            assert ArtifactCodec.decode(archive.read("model.tmind")).digest == image.digest
        assert temporary[-1].closed and temporary[-1]._rolled

        # Failure after history was consumed still cleans the temporary file
        # and does not publish a partial database artifact.
        def failed_figure(*args, **kwargs):
            raise RuntimeError("intentional figure failure")

        monkeypatch.setattr(evidence, "figure", failed_figure)
        failed = database.enqueue(project, "export", {"format": "evidence", "checkpoint_id": str(cp["id"])}, run)
        assert Worker(database).once()
        with database.tx(project) as db:
            assert db.execute("SELECT status FROM jobs WHERE id=%s", (failed["id"],)).fetchone()["status"] == "failed"
            assert not db.execute("SELECT id FROM artifacts WHERE job_id=%s", (failed["id"],)).fetchall()
        assert len(temporary) == 2 and all(f.closed for f in temporary)


def test_failed_archive_write_closes_live_database_stream_before_rollback(database):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Interrupted evidence stream"}).json()["id"]

    class FailedMember(io.BytesIO):
        calls = 0

        def write(self, chunk):
            self.calls += 1
            if self.calls == 2:
                raise OSError("intentional disk failure during query")
            return super().write(chunk)

    class Archive:
        def open(self, *args, **kwargs):
            return FailedMember()

    package = evidence.EvidenceArchive(Archive())
    with pytest.raises(OSError, match="disk failure"), database.tx(project) as db:
        records = stream_rows(
            db,
            "SELECT i, jsonb_build_object('text', repeat('x',4096))::text AS payload_json FROM generate_series(1,10000) i",
            (),
        )
        encoded = evidence.database_json_lines(records, {"payload": "payload_json"})
        try:
            package.write("events.jsonl", encoded)
        finally:
            # Keep both generators referenced: cleanup must not rely on GC.
            assert encoded.gi_frame is None and records.gi_frame is None
            assert db.pgconn.transaction_status != psycopg.pq.TransactionStatus.ACTIVE
            assert db.lock.acquire(blocking=False)
            db.lock.release()
    assert not package.files and not package.sizes
    with database.tx(project) as db:
        assert db.execute("SELECT 1 AS ready").fetchone()["ready"] == 1


def test_database_json_lines_handles_null_empty_header_and_large_values(database, monkeypatch):
    # Exercise the compatibility path even on the bundled modern libpq.
    monkeypatch.setattr(psycopg.capabilities, "has_stream_chunked", lambda: False)
    with database.tx() as db:
        records = stream_rows(db, "SELECT NULL::text AS payload_json", ())
        assert b"".join(evidence.database_json_lines(records, {"payload": "payload_json"})) == b'{"payload": null}\n'


def test_streamed_artifact_all_or_nothing_heartbeat_and_final_lease_fence(database):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Streaming lease"}).json()["id"]
    body = b"a" * CHUNK_BYTES + b"tail"

    def leased():
        database.enqueue(project, "export", {})
        return claim_as(database, "stream-test", max_active=10)

    job = leased()
    heartbeat = []
    renewal_errors = []

    class LiveStream(io.BytesIO):
        calls = 0

        def read(self, size):
            assert size == CHUNK_BYTES
            self.calls += 1
            if self.calls == 2:
                # Artifact rows are invisible until the final transaction.
                with database.tx(project) as db:
                    assert db.execute("SELECT count(*) AS n FROM artifacts").fetchone()["n"] == 0
                done = threading.Event()

                def renew():
                    try:
                        database.renew(job)
                    except (Conflict, psycopg.Error) as error:
                        renewal_errors.append(error)
                    finally:
                        done.set()

                thread = threading.Thread(target=renew, daemon=True)
                heartbeat.append(thread)
                thread.start()
                assert done.wait(2), "artifact insert blocked the lease heartbeat"
                assert not renewal_errors
            return super().read(size)

    try:
        artifact = database.put_artifact_stream(job, "stream.bin", "application/octet-stream", LiveStream(body))
    finally:
        for thread in heartbeat:
            thread.join(timeout=3)
    assert artifact["bytes"] == len(body) and artifact["sha256"] == hashlib.sha256(body).hexdigest()
    database.finish(job, result={"artifact_id": str(artifact["id"])})
    with database.tx(project) as db:
        chunks = db.execute(
            "SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal", (artifact["id"],)
        ).fetchall()
        assert len(chunks) == 2 and b"".join(c["body"] for c in chunks) == body

    for mode in ("reader-failed", "expired", "replaced"):
        job = leased()

        class Interrupted(io.BytesIO):
            calls = 0

            def read(self, size, mode=mode, job=job):
                self.calls += 1
                if self.calls == 2:
                    if mode == "reader-failed":
                        raise OSError("intentional stream interruption")
                    with database.tx() as db:
                        if mode == "expired":
                            db.execute("UPDATE jobs SET lease_until=clock_timestamp() WHERE id=%s", (job["id"],))
                        else:
                            db.execute("UPDATE jobs SET generation=generation+1 WHERE id=%s", (job["id"],))
                return super().read(size)

        with pytest.raises(OSError if mode == "reader-failed" else Conflict):
            database.put_artifact_stream(job, mode, "application/octet-stream", Interrupted(body))
        with database.tx(project) as db:
            assert not db.execute("SELECT id FROM artifacts WHERE job_id=%s", (job["id"],)).fetchall()
            assert db.execute("SELECT count(*) AS n FROM artifact_chunks").fetchone()["n"] == 2
            db.execute("UPDATE jobs SET status='failed',lease_until=NULL WHERE id=%s", (job["id"],))
