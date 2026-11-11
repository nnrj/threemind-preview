"""Raw-carrier memory benchmark against the explicitly isolated test PostgreSQL.

Run with the development dependencies and test service on 127.0.0.1:55439.
Creates and drops only its own random tm2_media_bench_* database and roles.
The generated RIFF padding is compressible: this is NOT a video decode or disk
throughput benchmark. No .env credentials or existing research data are read.
"""

import gc
import hashlib
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests_v2"))

from test_api import client_for
from test_media_uploads import PaddedWav, fixture

from threemind_lab.bootstrap import provision
from threemind_lab.database import LOCAL_USER, Database
from threemind_lab.media_store import CHUNK
from threemind_lab.media_uploads import begin, finalize, put


def measure(database, settings, project, run, padding_mb):
    generated = PaddedWav(padding_mb * CHUNK)
    identifier, actor = uuid4(), {"id": LOCAL_USER}
    metadata = {"kind": "audio", "filename": "generated-padding.wav", "intensity": 1.0, "delay_us": 0}
    begin(database, settings, project, run, actor, identifier, metadata, generated.length)
    gc.collect()
    process = psutil.Process()
    baseline = process.memory_info().rss
    samples = [baseline]
    stopped = threading.Event()

    def sample():
        while not stopped.wait(0.01):
            samples.append(process.memory_info().rss)

    observer = threading.Thread(target=sample, daemon=True)
    observer.start()
    tracemalloc.start()
    started = time.perf_counter()
    try:
        for i, at in enumerate(range(0, generated.length, CHUNK)):
            raw = generated.part(at)
            put(database, project, run, identifier, actor, i, raw, hashlib.sha256(raw).hexdigest())
        uploaded = time.perf_counter()
        result = finalize(database, project, run, identifier, actor)
        ended = time.perf_counter()
        _, python_peak = tracemalloc.get_traced_memory()
        samples.append(process.memory_info().rss)
    finally:
        tracemalloc.stop()
        stopped.set()
        observer.join(timeout=5)
    return {
        "raw_bytes": generated.length,
        "upload_seconds": round(uploaded - started, 3),
        "hash_decode_admit_seconds": round(ended - uploaded, 3),
        "rss_baseline_bytes": baseline,
        "rss_peak_bytes": max(samples),
        "rss_peak_delta_bytes": max(samples) - baseline,
        "python_traced_peak_bytes": python_peak,
        "rss_sample_interval_ms": 10,
        "frame_count": result["frame_count"],
        "largest_carrier_read_bytes": result["configuration"]["transduction"]["upload"]["largest_read_bytes"],
    }


def main():
    params = {"host": "127.0.0.1", "port": 55439, "user": "threemind_test", "dbname": "postgres", "connect_timeout": 3}
    suffix = uuid4().hex[:12]
    name, owner, app = [f"tm2_media_bench_{prefix}_{suffix}" for prefix in ("db", "owner", "app")]
    _, url = provision(params, database=name, owner=owner, app=app)
    database = Database(url)
    database.test_url = url
    try:
        with client_for(database) as client:
            project, run, _ = fixture(client)
            cases = [measure(database, client.app.state.settings, project, run, n) for n in (2, 257)]
        report = {
            "schema": "threemind.media-upload-benchmark/1",
            "date": "2026-09-06",
            "cases": cases,
            "scope": "sequential API-store pipeline in one Python process; isolated local PostgreSQL",
            "limits": [
                "compressible generated RIFF padding with 321 real PCM samples",
                "not long-video decode or disk throughput",
                "RSS is sampled, not every allocation; tracemalloc omits native allocations",
                "no prior data or .env read",
            ],
            "source_sha256": {
                p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                for p in (
                    "src/threemind_lab/media_uploads.py",
                    "src/threemind_lab/media_codec.py",
                    "scripts/benchmark-media-upload.py",
                )
            },
        }
        output = ROOT / ".work/media-upload-memory.json"
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(output), "cases": cases}, ensure_ascii=False))
    finally:
        database.close()
        assert all(n.startswith("tm2_media_bench_") and n.endswith(suffix) for n in (name, owner, app))
        with psycopg.connect(**params, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
            for role in (owner, app):
                admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


if __name__ == "__main__":
    main()
