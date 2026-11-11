"""Explicit synthetic fixed-topology engineering benchmark, NOT a learned research model.

Writes results only beneath .work. Uses an isolated PostgreSQL test database and
never connects to the configured workstation database or scans old data.
"""

import gc
import json
import statistics
import sys
import time
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

import psutil
import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from threemind_core import Config, Engine, StateImage
from threemind_core.engine import Edge, Node
from threemind_lab.bootstrap import provision
from threemind_lab.database import LOCAL_USER, Database
from threemind_runtime import ArtifactCodec
from threemind_runtime.host import NativeEngine


def synthetic(nodes, degree=10):
    state = Engine(Config(plasticity=False)).capture_state().to_dict()
    state.update(life="active", next_node=nodes + 1)
    state["nodes"] = [asdict(Node(i, i, activation=0.3, support=0.5, stability=0.2)) for i in range(1, nodes + 1)]
    state["edges"] = [
        asdict(Edge(i, (i + j - 1) % nodes + 1, 0.12, stability=0.2))
        for i in range(1, nodes + 1)
        for j in range(1, degree + 1)
    ]
    return StateImage.from_dict(state)


def timings(fn, n=5):
    values = []
    for _ in range(n):
        start = time.perf_counter()
        fn()
        values.append((time.perf_counter() - start) * 1000)
    return {"median_ms": statistics.median(values), "max_ms": max(values), "samples_ms": values}


def main():
    process = psutil.Process()
    results = {
        "kind": "synthetic fixed topology; no cognitive inference",
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "runs": [],
    }
    for size in (1000, 5000, 10000):
        image = synthetic(size)
        record = {"nodes": size, "edges": size * 10, "state_hash": image.digest}
        for name, implementation in (("reference", Engine), ("native", NativeEngine)):
            engine = implementation(state=image)
            engine.advance_to(10000)
            record[name] = timings(lambda engine=engine: engine.advance_to(engine.time_us + 10000))
            if name == "native":
                record["input_recording"] = timings(
                    lambda engine=engine: engine.advance_to(
                        engine.time_us + 10000, lambda event: None, inputs_only=True
                    )
                )
                record["capture"] = timings(engine.capture_state, 3)
                record["artifact_encode"] = timings(
                    lambda engine=engine: ArtifactCodec.encode(engine.capture_state()), 3
                )
                record["artifact_bytes"] = len(ArtifactCodec.encode(engine.capture_state()))
            del engine
            gc.collect()
        results["runs"].append(record)
    # Bounded host-time soak. Fixed graph memory and queue are reported separately.
    engine = NativeEngine(state=synthetic(1000))
    soak = []
    start = time.monotonic()
    while time.monotonic() - start < 60:
        engine.advance_to(engine.time_us + 10000)
        if not soak or time.monotonic() - start - soak[-1]["elapsed_s"] >= 5:
            gc.collect()
            soak.append(
                {"elapsed_s": time.monotonic() - start, "rss_bytes": process.memory_info().rss, **engine.metrics()}
            )
    results["soak"] = {"requested_host_seconds": 60, "samples": soak, "is_24h_validation": False}
    admin = {"host": "127.0.0.1", "port": 55439, "dbname": "postgres", "user": "threemind_test", "connect_timeout": 3}
    suffix = uuid4().hex[:12]
    name = f"tm2_test_bench_{suffix}"
    owner = f"tm2_test_owner_{suffix}"
    app = f"tm2_test_app_{suffix}"
    _, url = provision(admin, database=name, owner=owner, app=app)
    db = Database(url)
    try:
        project = db.create_project({"id": LOCAL_USER}, "Synthetic benchmark")
        run = db.create_run(project["id"], "Fixed 10k / 100k", {})
        engine = NativeEngine(state=synthetic(10000))
        revision = 0
        with db.tx() as conn:
            lsn = conn.execute("SELECT pg_current_wal_lsn() AS lsn").fetchone()["lsn"]

        def commit():
            nonlocal revision
            engine.advance_to(engine.time_us + 10000)
            cp = db.save_checkpoint(
                project["id"],
                run["id"],
                engine.capture_state(),
                expected_revision=revision,
                observations=[engine.metrics()],
            )
            revision = cp["revision"]

        results["postgres_commit"] = timings(commit, 3)
        results["postgres_query"] = timings(
            lambda: db.query_graph(project["id"], run["id"], table="edges", minimum=0.1, limit=200), 5
        )
        with db.tx() as conn:
            results["postgres_size"] = conn.execute(
                "SELECT pg_database_size(current_database()) AS database_bytes,pg_wal_lsn_diff(pg_current_wal_lsn(),%s) AS cluster_wal_delta_bytes",
                (lsn,),
            ).fetchone()
        results["database_roundtrip_hash_equal"] = (
            db.load_checkpoint(project["id"], run["id"])[1].digest == engine.capture_state().digest
        )
    finally:
        db.close()
        with psycopg.connect(**admin, autocommit=True) as conn:
            assert name.startswith("tm2_test_bench_")
            conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
            for role in (owner, app):
                conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
    path = ROOT / ".work/benchmark-v2.json"
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "result_path": str(path),
                "sizes": [r["nodes"] for r in results["runs"]],
                "database_roundtrip": results["database_roundtrip_hash_equal"],
            }
        )
    )


if __name__ == "__main__":
    main()
