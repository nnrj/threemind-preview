"""Verify every new study checkpoint and the preregistered coverage ledger."""

import gzip
import hashlib
import json
from collections import Counter

from common import GIB, WORK, Study, new_json, read_json

from threemind_core import StateImage


def main():
    study = Study()
    try:
        rows = []
        runner_verified = set()
        legacy_without_bundle = []
        shorthand_mismatches = []
        for path in sorted((WORK / "cases").rglob("result.json")):
            r = read_json(path)
            checkpoint, image = study.db.load_checkpoint(study.project, r["id"])
            local = StateImage(gzip.decompress((path.parent / "parent-state.json.gz").read_bytes()))
            assert image.digest == local.digest == r["state_sha256"]
            assert image.to_dict() == local.to_dict()
            assert not r["extra"].get("budget_stop"), r["key"]
            context = checkpoint["context"]
            signature = context.get("runner_manifest_sha256")
            if signature:
                root = WORK / "runner-revisions" / signature
                manifest = read_json(root / "manifest.json")
                if signature not in runner_verified:
                    for name, sha in manifest.items():
                        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == sha
                    runner_verified.add(signature)
                if context["runner_sha256"] != manifest["common.py"]:
                    shorthand_mismatches.append(r["id"])
            else:
                legacy_without_bundle.append(r["id"])
            rows.append(r)
        expected = {
            "calibration": 16,
            "memory": 520,
            "sequence": 320,
            "transfer": 240,
            "adaptation": 336,
            "memory-intervention": 96,
            "transfer-trace": 8,
        }
        coverage = Counter(r["extra"]["family"] for r in rows)
        assert dict(coverage) == expected, coverage
        assert len({r["id"] for r in rows}) == len(rows) == 1536
        analysis = read_json(WORK / "analysis-final.json")
        assert analysis["complete_cases"] == len(rows)
        assert {r["id"] for r in rows} == {r["id"] for r in analysis["rows"]}
        restored = [r for r in analysis["rows"] if r.get("intervention_condition") == "restore"]
        assert len(restored) == 32 and all(r["max_pointwise_activation_difference"] < 1e-12 for r in restored)
        replayed = [r for r in rows if r["extra"]["family"] == "transfer-trace"]
        assert len(replayed) == 8 and all(r["state_sha256"] == r["extra"]["original_state_sha256"] for r in replayed)
        with study.db.tx(study.project) as tx:
            saved = tx.execute("SELECT id FROM runs WHERE project_id=%s", (study.project,)).fetchall()
            jobs = tx.execute(
                "SELECT status, count(*) AS n FROM jobs WHERE project_id=%s GROUP BY status", (study.project,)
            ).fetchall()
        assert {str(r["id"]) for r in saved} == {r["id"] for r in rows}
        assert all(j["status"] not in ("pending", "leased") for j in jobs)
        with study.db.tx() as tx:
            current = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        local_bytes = sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file())
        assert local_bytes + max(0, current - study.meta["database_bytes_before"]) < 3 * GIB
        wall = sum(r["wall_seconds"] for r in rows)
        assert wall < 14400
        result = {
            "verified_checkpoints": len(rows),
            "coverage": dict(coverage),
            "restored_full_activation_trajectories": len(restored),
            "observation_only_replays_with_identical_core_hashes": len(replayed),
            "simulation_wall_seconds": wall,
            "local_bytes": local_bytes,
            "database_growth_bytes": current - study.meta["database_bytes_before"],
            "usage_start_percent": study.meta["usage_start_percent"],
            "usage_end_percent": read_json(WORK / "usage.json")["used_percent"],
            "core_implementation_unchanged": study.implementation == study.meta["implementation"],
            "pending_study_jobs": 0,
            "verified_runner_bundles": len(runner_verified),
            "legacy_cases_without_runner_bundle": legacy_without_bundle,
            "legacy_live_file_shorthand_mismatches": shorthand_mismatches,
            "runner_provenance_note": "Process-start frozen bundles are authoritative. The early single-file shorthand was read at finish and could reflect later tool edits; the complete bundle remains unchanged. The calibration predates bundle capture.",
        }
        new_json(WORK / "audit.json", result)
        (WORK / "STOP").write_text(
            "Registered simulations completed and checkpoints verified. No new simulations.\n", encoding="utf-8"
        )
        print(json.dumps({k: len(v) if isinstance(v, list) else v for k, v in result.items()}))
    finally:
        study.db.close()


if __name__ == "__main__":
    main()
