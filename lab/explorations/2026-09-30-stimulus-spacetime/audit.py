"""Read back every new checkpoint; never traverse old experiments."""

import gzip
import json

from common import GIB, WORK, Study, new_json, read_json

from threemind_core import StateImage


def main():
    s = Study()
    try:
        count = 0
        wall = 0
        for path in sorted((WORK / "cases").rglob("result.json")):
            r = read_json(path)
            _, image = s.db.load_checkpoint(s.project, r["id"])
            raw = gzip.decompress((path.parent / "parent-state.json.gz").read_bytes())
            assert image.digest == r["state_sha256"] == StateImage(raw).digest
            assert image.to_dict() == StateImage(raw).to_dict()
            assert not r["extra"].get("budget_stop")
            count += 1
            wall += r["wall_seconds"]
        a = read_json(WORK / "analysis-v3.json")
        assert count == 295 and a["cases"] == 260 and a["reproduced_core_hashes"] == 31
        with s.db.tx() as tx:
            current = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        local = sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file())
        assert local + max(0, current - s.meta["database_bytes_before"]) < 3 * GIB
        assert wall < 5400
        result = {
            "verified_checkpoints": count,
            "primary_design_cases": 260,
            "extension_cases": 4,
            "retained_registration_failures": 31,
            "core_hash_reproductions": 31,
            "simulation_wall_seconds": wall,
            "local_bytes": local,
            "database_growth_bytes": current - s.meta["database_bytes_before"],
            "usage_start_percent": s.meta["usage_start_percent"],
            "usage_end_percent": read_json(WORK / "usage.json")["used_percent"],
        }
        new_json(WORK / "audit.json", result)
        print(json.dumps(result))
        (WORK / "STOP").write_text(
            "Registered simulations and bounded extension completed; no new simulations.\n", encoding="utf-8"
        )
    finally:
        s.db.close()


if __name__ == "__main__":
    main()
