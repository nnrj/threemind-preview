"""Measure a complete evidence job in an isolated PostgreSQL database.

Run each variant in a fresh process. --reference-worker explicitly loads a
locally saved historical worker module, for before/after engineering checks.
No .env or research data is read. Generated events are performance fixtures.
"""

import argparse
import gc
import hashlib
import importlib.util
import json
import sys
import threading
import time
import tracemalloc
from pathlib import Path
from uuid import uuid4

import psutil
import psycopg
from psycopg import sql

from threemind_core import Engine, Stimulus
from threemind_lab.auth import create_user
from threemind_lab.bootstrap import provision
from threemind_lab.database import Database
from threemind_lab.protocols import RunSpec
from threemind_lab.statistics import figure
from threemind_lab.worker import Worker
from threemind_runtime import ArtifactCodec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=10000)
    parser.add_argument("--payload-bytes", type=int, default=4096)
    parser.add_argument("--output", type=Path, default=Path(".work/evidence-export-memory.json"))
    parser.add_argument("--reference-worker", type=Path)
    parser.add_argument(
        "--no-tracemalloc", action="store_true", help="Measure timing without Python allocation tracing"
    )
    args = parser.parse_args()
    if not 1 <= args.events <= 1000000 or not 1 <= args.payload_bytes <= 1048576:
        parser.error("generated data size out of range")
    worker_class, reference_hash = Worker, None
    if args.reference_worker:
        spec = importlib.util.spec_from_file_location("threemind_lab._benchmark_reference", args.reference_worker)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        worker_class = module.Worker
        reference_hash = hashlib.sha256(args.reference_worker.read_bytes()).hexdigest()
    admin_params = {
        "host": "127.0.0.1",
        "port": 55439,
        "user": "threemind_test",
        "dbname": "postgres",
        "connect_timeout": 3,
    }
    suffix = uuid4().hex[:12]
    name, owner, app = [f"tm2_evidence_bench_{kind}_{suffix}" for kind in ("db", "owner", "app")]
    _, url = provision(admin_params, database=name, owner=owner, app=app)
    database = Database(url)
    try:
        user = create_user(database, "evidence-bench", uuid4().hex)
        project = database.create_project(user, "Generated evidence benchmark")["id"]
        protocol = RunSpec(environment="manual", clock="unbounded").model_dump()
        run = database.create_run(project, "Synthetic history", protocol)["id"]
        engine = Engine()
        engine.inject(Stimulus(0, ((1, 0.5), (2, 0.3))))
        engine.advance_to(0)
        first = engine.metrics()
        engine.advance_to(args.events)
        image = engine.capture_state()
        cp = database.save_checkpoint(
            project,
            run,
            image,
            expected_revision=0,
            status="paused",
            context={"protocol": protocol},
            observations=[first, engine.metrics()],
        )
        with database.tx(project) as db:
            db.execute(
                "INSERT INTO events(project_id,run_id,event_key,time_us,kind,payload,commit_revision) "
                "SELECT %s,%s,'bench:'||i,i,'telemetry_sample',jsonb_build_object('ordinal',i,'generated',repeat('x',%s)),%s FROM generate_series(1,%s) i",
                (project, run, args.payload_bytes, cp["revision"], args.events),
            )
        worker = worker_class(database)
        assert not worker.once()  # Initialize worker capabilities outside measurement.
        ArtifactCodec.encode(image)
        for format in ("svg", "png", "pdf"):
            figure([first, engine.metrics()], format=format)
        task = database.enqueue(project, "export", {"format": "evidence", "checkpoint_id": str(cp["id"])}, run)
        gc.collect()
        process = psutil.Process()
        baseline = process.memory_info().rss
        samples = [baseline]
        stopped = threading.Event()

        def observe_memory():
            while not stopped.wait(0.01):
                samples.append(process.memory_info().rss)

        observer = threading.Thread(target=observe_memory, daemon=True)
        observer.start()
        if not args.no_tracemalloc:
            tracemalloc.start()
        started = time.perf_counter()
        try:
            assert worker.once()
            elapsed = time.perf_counter() - started
            peak = tracemalloc.get_traced_memory()[1] if not args.no_tracemalloc else None
        finally:
            tracemalloc.stop()
            stopped.set()
            observer.join(timeout=3)
        with database.tx(project) as db:
            job = db.execute("SELECT status,result,error FROM jobs WHERE id=%s", (task["id"],)).fetchone()
            if job["status"] != "done":
                raise RuntimeError(job["error"])
            artifact = db.execute(
                "SELECT bytes,sha256 FROM artifacts WHERE id=%s", (job["result"]["artifact_id"],)
            ).fetchone()
        report = {
            "schema": "threemind.evidence-memory-benchmark/1",
            "variant": "reference_worker" if reference_hash else "current_worker",
            "reference_source_sha256": reference_hash,
            "events": args.events,
            "payload_bytes_each": args.payload_bytes,
            "generated_payload_bytes": args.events * args.payload_bytes,
            "seconds": elapsed,
            "tracemalloc_enabled": not args.no_tracemalloc,
            "rss_baseline_bytes": baseline,
            "rss_peak_bytes": max(samples),
            "rss_peak_delta_bytes": max(samples) - baseline,
            "python_traced_peak_bytes": peak,
            "rss_sample_interval_ms": 10,
            "artifact_bytes": artifact["bytes"],
            "artifact_sha256": artifact["sha256"],
            "scope": "Complete export job through PostgreSQL artifact commit, native figure/model backends initialized first; isolated PostgreSQL 55439, fresh Python process per variant.",
            "limits": [
                "Generated compressible event history, two observation samples, two-node model",
                "Not a large-model or many-observation-sample benchmark",
                "tracemalloc changes timing and excludes native allocations; sampled RSS can miss short peaks",
                "No original data or .env read; database and temporary export files cleaned after run",
            ],
            "source_sha256": {
                str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in map(
                    Path,
                    (
                        "src/threemind_lab/evidence.py",
                        "src/threemind_lab/database_stream.py",
                        "src/threemind_lab/database.py",
                        "src/threemind_lab/worker.py",
                        "src/threemind_lab/inputs.py",
                    ),
                )
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "variant": report["variant"],
                    "seconds": elapsed,
                    "python_peak_MiB": round(peak / 1048576, 2) if peak is not None else None,
                    "rss_delta_MiB": round((max(samples) - baseline) / 1048576, 2),
                }
            )
        )
    finally:
        database.close()
        assert all(n.startswith("tm2_evidence_bench_") and n.endswith(suffix) for n in (name, owner, app))
        with psycopg.connect(**admin_params, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
            for role in (owner, app):
                admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


if __name__ == "__main__":
    main()
