"""Isolated engineering benchmark: readout, sparse/dense commits, bounded writer soak.

No legacy data or workstation database is read. Synthetic topology is an
engineering fixture, never evidence for learning or consciousness.
"""

import argparse
import copy
import gc
import json
import runpy
import sys
import time
from pathlib import Path
from uuid import uuid4

import psutil
import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from threemind_core import StateImage
from threemind_lab.bootstrap import provision
from threemind_lab.checkpoints import CheckpointWriter
from threemind_lab.database import LOCAL_USER, Database
from threemind_runtime.host import NativeEngine

helpers = runpy.run_path(str(ROOT / "scripts/benchmark-v2.py"))
synthetic, timings = helpers["synthetic"], helpers["timings"]


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--seconds", type=int, default=300)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 86400:
        parser.error("seconds must be 1..86400")
    results = {
        "kind": "synthetic engineering fixture; no cognitive inference",
        "cases": {},
        "timing": "Commit comparison excludes state capture and uses precomputed identical state hashes in both paths.",
    }
    engine = NativeEngine(state=synthetic(10000))
    results["readout_10000_nodes_100000_edges"] = {
        "full_graph": timings(engine.graph, 5),
        "activations": timings(engine.activations, 5),
    }
    initial = engine.capture_state()
    _ = initial.digest
    admin = {"host": "127.0.0.1", "port": 55439, "dbname": "postgres", "user": "threemind_test", "connect_timeout": 3}
    suffix = uuid4().hex[:12]
    name, owner, app = (f"tm2_test_{prefix}_{suffix}" for prefix in ("pipeline", "owner", "app"))
    _, url = provision(admin, database=name, owner=owner, app=app)
    db = Database(url)
    try:
        project = db.create_project({"id": LOCAL_USER}, "Synthetic checkpoint benchmark")
        for scenario in ("sparse", "dense"):
            images = []
            state = initial.to_dict()
            for i in range(3):
                state = copy.deepcopy(state)
                for row in state["nodes"][: 10 if scenario == "sparse" else len(state["nodes"])]:
                    row["activation"] += 0.01
                for row in state["edges"][: 50 if scenario == "sparse" else len(state["edges"])]:
                    row["weight"] += 0.001
                image = StateImage.from_dict(state)
                _ = image.digest
                images.append(image)
            case = {}
            for incremental in (False, True):
                run = db.create_run(project["id"], f"{scenario} {incremental}", {})
                cp = db.save_checkpoint(project["id"], run["id"], initial, expected_revision=0)
                previous = (cp, initial.to_dict())
                samples, byte_counts, formats = [], [], []
                with db.tx() as conn:
                    lsn = conn.execute("SELECT pg_current_wal_lsn() AS lsn").fetchone()["lsn"]
                for image in images:
                    started = time.perf_counter()
                    cp = db.save_checkpoint(
                        project["id"],
                        run["id"],
                        image,
                        expected_revision=previous[0]["revision"],
                        previous=previous if incremental else None,
                    )
                    samples.append((time.perf_counter() - started) * 1000)
                    previous = (cp, image.to_dict())
                    byte_counts.append(cp["byte_count"])
                    formats.append(cp["storage_format"])
                with db.tx() as conn:
                    wal = conn.execute("SELECT pg_wal_lsn_diff(pg_current_wal_lsn(),%s) AS bytes", (lsn,)).fetchone()[
                        "bytes"
                    ]
                case["incremental" if incremental else "full"] = {
                    "samples_ms": samples,
                    "bytes_per_checkpoint": byte_counts,
                    "formats": formats,
                    "cluster_wal_delta_bytes": int(wal),
                    "exact_recovery": db.load_checkpoint(project["id"], run["id"])[1].digest == images[-1].digest,
                }
            results["cases"][scenario] = case
        del images, previous, state, initial, engine
        gc.collect()
        engine = NativeEngine(state=synthetic(1000))
        run = db.create_run(project["id"], "Bounded 1k / 10k writer soak", {})
        process, samples = psutil.Process(), []
        start = time.monotonic()
        next_commit = 0
        with CheckpointWriter(db, project["id"], run["id"], 0) as writer:
            while time.monotonic() - start < args.seconds:
                engine.advance_to(engine.time_us + 20000)
                if engine.time_us >= next_commit:
                    writer.drain()
                    writer.submit(engine.capture_state(), observations=[engine.metrics()])
                    next_commit = engine.time_us + 2000000
                if not samples or time.monotonic() - start - samples[-1]["host_s"] >= 10:
                    gc.collect()
                    samples.append(
                        {
                            "host_s": time.monotonic() - start,
                            "rss_bytes": process.memory_info().rss,
                            "committed_revision": writer.revision,
                            **engine.metrics(),
                        }
                    )
            writer.drain()
            writer.submit(engine.capture_state(), observations=[engine.metrics()], status="completed")
            writer.drain()
            results["soak"] = {
                "requested_host_seconds": args.seconds,
                "elapsed_host_seconds": time.monotonic() - start,
                "nodes": 1000,
                "edges": 10000,
                "samples": samples,
                "committed_revision": writer.revision,
                "exact_recovery": db.load_checkpoint(project["id"], run["id"])[1].digest
                == engine.capture_state().digest,
                "is_24h_validation": False,
            }
    finally:
        db.close()
        with psycopg.connect(**admin, autocommit=True) as conn:
            assert all(n.startswith("tm2_test_") for n in (name, owner, app))
            conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
            for role in (owner, app):
                conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
    path = ROOT / ".work/benchmark-checkpoints.json"
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps({"result": str(path), "soak_recovery": results["soak"]["exact_recovery"]}))


if __name__ == "__main__":
    main()
