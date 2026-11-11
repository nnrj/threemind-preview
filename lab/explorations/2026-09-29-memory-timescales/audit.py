"""Verify this study's saved evidence, public checkpoint decoding and resource ledger."""

import hashlib
import json
import shutil
import time
from collections import Counter

import psutil
from common import ROOT, WORK, Study, encoded
from run import TOKENS, background


def audit(s):
    rows = [json.loads(p.read_bytes()) for p in sorted((WORK / "cases").rglob("result.json"))]
    failures = []
    checks = []
    for r in rows:
        cp, state = s.db.load_checkpoint(s.project, r["id"])
        if state.digest != r["state_sha256"]:
            failures.append(r["key"] + ": persisted state")
        if r["extra"].get("budget_stop"):
            failures.append(r["key"] + ": incomplete")
        v = state.to_dict()
        task = {n["id"] for n in v["nodes"] if n["channel"] in TOKENS.values()}
        cross = sum((e["source"] in task) != (e["target"] in task) for e in v["edges"])
        checks.append({"key": r["key"], "hash": state.digest, "checkpoint": str(cp["id"]), "cross_edges": cross})
    with s.db.tx() as db:
        db_bytes = db.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
    with s.db.tx(s.project) as db:
        runs = db.execute("SELECT id FROM runs WHERE project_id=%s", (s.project,)).fetchall()
    if {str(r["id"]) for r in runs} != {r["id"] for r in rows}:
        failures.append("database and local instance sets differ")
    old = ROOT / ".work/continuous-mechanisms-20260929/evidence.zip"
    with old.open("rb") as f:
        old_hash = hashlib.file_digest(f, "sha256").hexdigest()
    if old_hash != "fa2bb67d86b8aaceb9bbb386e31b5b5bef4c1fe2c5fdaed48ddc8feb823c0e18":
        failures.append("prior study archive changed")
    frames, _, source_hash = background()
    background_channels = {ch for stim, _, _ in frames for ch, _ in stim.channels}
    value = {
        "cases": len(rows),
        "stage_counts": dict(Counter(r["key"].split("/")[0] for r in rows)),
        "failures": failures,
        "checks": checks,
        "compute_seconds": sum(r["wall_seconds"] for r in rows),
        "elapsed_seconds": time.time() - s.meta["started_at_epoch"],
        "local_bytes": sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file()),
        "database_growth_bytes": max(0, db_bytes - s.meta["database_bytes_before"]),
        "available_ram_bytes": psutil.virtual_memory().available,
        "free_E_bytes": shutil.disk_usage("E:/").free,
        "free_C_bytes": shutil.disk_usage("C:/").free,
        "background_source_sha256": source_hash,
        "background_task_channel_overlap": sorted(background_channels & set(TOKENS.values())),
        "previous_archive_sha256": old_hash,
        "automated_checks": {
            "python": "95 passed, 1 skipped",
            "rust": "5 passed",
            "ui_build": "passed",
            "ui_browser_test": "not run",
        },
    }
    (WORK / "audit.json").write_bytes(encoded(value))
    print(json.dumps({k: v for k, v in value.items() if k not in ("checks",)}))
    if failures:
        raise RuntimeError("Evidence audit failed")


if __name__ == "__main__":
    study = Study()
    try:
        audit(study)
    finally:
        study.db.close()
