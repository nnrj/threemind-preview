"""Read-only checks scoped to this study and pre-existing project metadata."""

import argparse
import hashlib
import json
import shutil
import time
from collections import Counter

from common import KERNELS, ROOT, WORK, Study, new_json, read_json
from run import tokens


def main(usage, after_publication):
    study = Study()
    try:
        study.guard(force=True)
        previous = read_json(ROOT / ".work/study-environment-before.json")
        changed = []
        for project, expected in previous["old_metadata"].items():
            with study.db.tx(project) as db:
                runs = db.execute("SELECT id,revision,state_hash,status FROM runs ORDER BY id").fetchall()
                docs = db.execute("SELECT id,revision FROM research_documents ORDER BY id").fetchall()
            actual = hashlib.sha256(json.dumps([runs, docs], sort_keys=True, default=str).encode()).hexdigest()
            if actual != expected:
                changed.append(project)
        records = [read_json(p) for p in (WORK / "cases").rglob("result.json")]
        counts = Counter(r["key"].split("/")[0] for r in records)
        assert all(counts[f"block-{b}"] == 526 for b in range(6)), counts
        assert counts["calibration"] == 72 and counts["verification"] == 1, counts
        pulse_errors = []
        for r in records:
            parts = r["key"].split("/")
            if not parts[0].startswith("block-") or len(parts) != 3:
                continue
            condition = parts[2]
            expected = (
                20
                if condition.startswith("adapt-")
                else 210
                if condition.startswith("sequence-")
                else 0
                if condition.endswith("-untrained")
                else 180
                if condition.endswith("-remapped")
                else 140
            )
            if len(r["pulses"]) != expected and r["life"] != "dead":
                pulse_errors.append(r["key"])
        topology = []
        for block in range(6):
            task = set(tokens(block))
            for kernel in KERNELS:
                short = kernel.split(".")[-1].replace("/", "-")
                for bg in (0, 1):
                    for condition in ("pair", "remapped", "sequence-pure", "sequence-overlap"):
                        name = (
                            f"pair-bg{bg}-{'trained' if condition == 'pair' else 'remapped'}"
                            if condition in ("pair", "remapped")
                            else (f"sequence-bg{bg}-overlap{int(condition.endswith('overlap'))}-swap0")
                        )
                        r = read_json(WORK / "cases" / f"block-{block}/{short}/{name}/result.json")
                        _, image = study.db.load_checkpoint(study.project, r["id"])
                        assert image.digest == r["state_sha256"]
                        state = image.to_dict()
                        channels = {n["id"]: n["channel"] for n in state["nodes"]}
                        edges = state["edges"]
                        within = [e for e in edges if channels[e["source"]] in task and channels[e["target"]] in task]
                        cross = [e for e in edges if (channels[e["source"]] in task) != (channels[e["target"]] in task)]
                        topology.append(
                            {
                                "block": block,
                                "kernel": kernel,
                                "background": bg,
                                "condition": condition,
                                "run_id": r["id"],
                                "state_sha256": image.digest,
                                "task_nodes": sum(ch in task for ch in channels.values()),
                                "task_edges": len(within),
                                "cross_background_edges": len(cross),
                                "task_edge_weights": [e["weight"] for e in within],
                            }
                        )
        with study.db.tx(study.project) as db:
            size = db.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
            run_counts = db.execute(
                "SELECT status,revision,count(*) AS n FROM runs GROUP BY status,revision"
            ).fetchall()
            background_doses = db.execute(
                "SELECT DISTINCT f.stimulus->>'intensity' AS actual,e.configuration->>'dose' AS requested,"
                "e.payload->'frames'->0->>'intensity' AS encoder_output "
                "FROM input_frames f JOIN input_envelopes e ON e.id=f.envelope_id "
                "WHERE e.source='host-telemetry'"
            ).fetchall()
        result = {
            "phase": "post-publication" if after_publication else "before-publication",
            "captured_at_epoch": time.time(),
            "wall_seconds": time.time() - study.meta["started_at_epoch"],
            "usage_used_percent": usage,
            "usage_increase_percentage_points": usage - study.meta["usage_start_percent"],
            "previous_projects_checked": len(previous["old_metadata"]),
            "changed_previous_metadata": changed,
            "case_counts": dict(counts),
            "pulse_count_errors": pulse_errors,
            "run_counts": run_counts,
            "database_bytes": size,
            "database_bytes_increase": size - study.meta["database_bytes_before"],
            "local_bytes": sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file()),
            "free_bytes": {d: shutil.disk_usage(d).free for d in ("C:/", "D:/", "E:/")},
            "background_doses": background_doses,
            "topology": topology,
            "payload_note": "Host payload.frames records encoder output before the study's explicit gain. input_frames.stimulus records actual scheduled/delivered intensity 0.2.",
        }
        assert not changed and not pulse_errors
        assert all(row["revision"] == 1 for row in run_counts)
        assert all(float(row["actual"]) == 0.2 and float(row["requested"]) == 0.2 for row in background_doses)
        new_json(WORK / ("post-publication-closure.json" if after_publication else "closure.json"), result)
        print(json.dumps({k: v for k, v in result.items() if k != "topology"}, default=str))
    finally:
        study.db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--usage-percent", type=int, required=True)
    parser.add_argument("--after-publication", action="store_true")
    args = parser.parse_args()
    main(args.usage_percent, args.after_publication)
