"""Read-only audit of study instances and export of their parent states."""

import gzip
import hashlib
import shutil
import time
from collections import Counter

from common import GIB, WORK, Study, encoded, new_json, read_json


def main():
    study = Study()
    try:
        files = sorted((WORK / "cases").rglob("result.json"))
        assert len(files) == 341, len(files)
        parents, counts = {}, Counter()
        failed, elapsed = [], 0.0
        for path in files:
            value = read_json(path)
            elapsed += value["wall_seconds"]
            counts[value["key"].split("/")[0]] += 1
            if value["extra"].get("budget_stop"):
                failed.append(value["key"])
            if value["extra"].get("frames") == 210:
                _, image = study.db.load_checkpoint(study.project, value["id"])
                assert image.digest == value["state_sha256"]
                state = image.to_dict()
                parents[value["key"]] = {"state_sha256": image.digest, "nodes": len(state["nodes"]),
                                         "edges": len(state["edges"]), "structure_sha256": hashlib.sha256(encoded(
                                             {k: state[k] for k in ("nodes", "edges")})).hexdigest(),
                                         "weights": [e["weight"] for e in state["edges"]]}
                destination = path.parent / "parent-state.json.gz"
                if not destination.exists():
                    with gzip.open(destination, "xb") as f:
                        f.write(encoded(state))
        assert not failed, failed
        structural_parity = []
        for left, right in (("111", "110"), ("101", "100")):
            for swap in (0, 1):
                for reverse in (0, 1):
                    suffix = f"swap{swap}-reverse{reverse}"
                    a, b = f"factorial/{left}/{suffix}", f"factorial/{right}/{suffix}"
                    structural_parity.append({"a": a, "b": b, "exact_structure_equal": parents[a]["structure_sha256"] == parents[b]["structure_sha256"]})
        baseline_parity = []
        for swap in (0, 1):
            for reverse in (0, 1):
                suffix = f"swap{swap}-reverse{reverse}"
                a, b = f"factorial/000/{suffix}", f"baseline/{suffix}"
                baseline_parity.append({"a": a, "b": b, "exact_structure_equal": parents[a]["structure_sha256"] == parents[b]["structure_sha256"]})
        with study.db.tx(study.project) as tx:
            runs = tx.execute("SELECT status,count(*) AS n FROM runs GROUP BY status").fetchall()
            database_bytes = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        local = sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file())
        output = {"cases": len(files), "counts": dict(counts), "failed": failed,
                  "case_wall_seconds_sum": elapsed, "elapsed_since_registration_seconds": time.time()-study.meta["started_at_epoch"],
                  "parents": parents, "context_structure_parity": structural_parity, "baseline_structure_parity": baseline_parity,
                  "db_runs": runs, "database_bytes": database_bytes, "database_growth_bytes": database_bytes-study.meta["database_bytes_before"],
                  "local_bytes": local, "new_total_bytes": database_bytes-study.meta["database_bytes_before"]+local,
                  "disk_free_GiB": {d: shutil.disk_usage(d).free/GIB for d in ("C:/", "D:/", "E:/")}}
        new_json(WORK / "audit.json", output)
        print({k: v for k, v in output.items() if k not in ("parents", "context_structure_parity", "baseline_structure_parity")})
    finally:
        study.db.close()


if __name__ == "__main__":
    main()
