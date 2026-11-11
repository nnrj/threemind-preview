"""Read back every new checkpoint and verify local evidence without running Core."""

import gzip
import json
from collections import Counter

from common import ROOT, WORK, Study, new_json, read_json
from experiment import SEEDS, old_memory, warm

from threemind_core import StateImage


def audit():
    study = Study()
    try:
        paths = sorted((WORK / "cases" / "execution2").rglob("result.json"))
        assert len(paths) == 786
        families, classes, events = Counter(), Counter(), Counter()
        checks, max_saturation, compute, max_nodes, max_edges = [], 0.0, 0.0, 0, 0
        for index, path in enumerate(paths):
            result = read_json(path)
            assert not result["extra"].get("budget_stop"), result["key"]
            raw = gzip.decompress((path.parent / "parent-state.json.gz").read_bytes())
            assert StateImage(raw).digest == result["state_sha256"]
            checkpoint, image = study.db.load_checkpoint(study.project, result["id"])
            assert image.to_dict() == StateImage(raw).to_dict() and image.digest == result["state_sha256"]
            assert result["extra"]["energy"]["unserved_total"] == 0
            checks.append({"id": result["id"], "checkpoint_id": str(checkpoint["id"]), "sha256": image.digest})
            families[result["key"].split("/")[1]] += 1
            compute += result["wall_seconds"]
            with gzip.open(path.parent / "observations.jsonl.gz", "rb") as stream:
                for line in stream:
                    row = json.loads(line)
                    if row.get("saturated_fraction") is not None:
                        max_saturation = max(max_saturation, row["saturated_fraction"])
                    max_nodes, max_edges = max(max_nodes, row["nodes"]), max(max_edges, row["edges"])
            readers = Counter()
            with gzip.open(path.parent / "events.jsonl.gz", "rb") as stream:
                for line in stream:
                    event = json.loads(line)
                    events[event["kind"]] += 1
                    if event["kind"] == "temporal_readout":
                        read = event["payload"]
                        kind = "new" if read.get("analysis_schema") else "old"
                        readers[kind] += 1
                        classes[kind + ":" + str(read.get("classification"))] += 1
            if result["extra"].get("cue_intensity"):
                assert readers == {"old": 1, "new": 1}, (result["key"], readers)
            if (index + 1) % 100 == 0:
                print(json.dumps({"verified": index + 1}), flush=True)
        historical = []
        for seed in SEEDS:
            for parent, directory in [
                (warm(seed), "internal-activity-20260929"),
                (old_memory(seed, "none"), "experience-autonomy-20260929"),
                (old_memory(seed, "spaced_ordinary"), "experience-autonomy-20260929"),
            ]:
                parent_project = read_json(ROOT / ".work" / directory / "platform.json")["project_id"]
                with study.db.tx(parent_project) as db:
                    row = db.execute(
                        "SELECT project_id,id FROM checkpoints WHERE run_id=%s AND state_hash=%s ORDER BY revision LIMIT 1",
                        (parent["id"], parent["state_sha256"]),
                    ).fetchone()
                assert row is not None
                _, image = study.db.load_checkpoint(row["project_id"], parent["id"], row["id"])
                assert image.digest == parent["state_sha256"]
                historical.append({"id": parent["id"], "sha256": image.digest})
        with study.db.tx() as db:
            database_bytes = db.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        with study.db.tx(study.project) as db:
            runs = db.execute(
                "SELECT status,count(*) AS n FROM runs WHERE project_id=%s GROUP BY status", (study.project,)
            ).fetchall()
        local = sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file())
        value = {
            "verified_cases": len(checks),
            "families": dict(families),
            "readouts": dict(classes),
            "max_observed_saturated_fraction": max_saturation,
            "max_nodes": max_nodes,
            "max_edges": max_edges,
            "compute_seconds": compute,
            "energy_deficit_cases": 0,
            "events": dict(events),
            "local_bytes": local,
            "database_growth_bytes": max(0, database_bytes - study.meta["database_bytes_before"]),
            "database_run_statuses": {r["status"]: r["n"] for r in runs},
            "historical_parents_unchanged": historical,
            "checkpoint_checks": checks,
            "usage_start_percent": study.meta["usage_start_percent"],
            "usage_end_percent": read_json(WORK / "usage.json")["used_percent"],
        }
        new_json(WORK / "audit.json", value)
        print(
            json.dumps(
                {k: v for k, v in value.items() if k not in ("checkpoint_checks", "historical_parents_unchanged")}
            )
        )
    finally:
        study.db.close()


if __name__ == "__main__":
    audit()
