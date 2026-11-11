"""Read back all new checkpoints and verify portable input evidence."""

import gzip
import hashlib
import json
import time
from collections import Counter

from experiment import WORK, settings

from lab.tools.service_study import Study, digest, new_json, read_json
from threemind_core import StateImage, Stimulus
from threemind_lab import notebooks
from threemind_lab.database import LOCAL_USER
from threemind_lab.inputs import digest as input_digest
from threemind_lab.inputs import export_stream
from threemind_runtime import create_engine
from threemind_runtime.sensory import carrier_frames


def export_verified(study, folder, result):
    tables = {}
    for kind in ("envelopes", "frames"):
        path = folder / f"inputs-{kind}.jsonl.gz"
        if not path.exists():
            staging = path.with_suffix(f".partial-{time.time_ns()}")
            with gzip.open(staging, "xb") as out:
                for line in export_stream(study.db, study.project, result["id"], records=kind, format="jsonl"):
                    out.write(line.encode("utf-8"))
            staging.rename(path)
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            header = json.loads(next(stream))
            assert header["run_id"] == result["id"] and header["records"] == kind
            tables[kind] = [json.loads(line) for line in stream]
        assert all(r["run_id"] == result["id"] for r in tables[kind])
    envelopes = {r["id"]: r for r in tables["envelopes"]}
    originals = json.loads(gzip.decompress((folder / "inputs.json.gz").read_bytes()))
    delivered = {(r["envelope_id"], r["frame_index"]): r for r in originals["delivered"]}
    assert len(delivered) == len(tables["frames"]) == sum(r["frame_count"] for r in envelopes.values())
    assert not originals["rejected"]
    for env in envelopes.values():
        assert env["status"] == "completed" and env["filtered_count"] == 0
        assert input_digest(env["payload"]) == env["payload_hash"]
        assert input_digest(env["configuration"]) == env["configuration_hash"]
    for row in tables["frames"]:
        env = envelopes[row["envelope_id"]]
        decoded = list(carrier_frames(env["adapter_id"], env["payload"], result["seed"], {}))
        original = delivered[(row["envelope_id"], row["frame_index"])]
        assert row["status"] == "delivered" and row["input_gate"] is None
        assert input_digest(decoded[row["frame_index"]]["stimulus"].to_dict()) == input_digest(row["stimulus"])
        assert input_digest(original["stimulus"]) == input_digest(row["stimulus"])
        assert row["scheduled_time_us"] == row["delivered_time_us"] == row["stimulus"]["time_us"]
    return {k: len(v) for k, v in tables.items()}


def observation_replays(study):
    witnesses = []
    for f in (0, 1):
        for delay in (1, 30):
            key = f"matrix/930401/i0f{f}l1/single4/wait{delay}/cue0.5"
            folder = WORK / "cases" / key
            result = read_json(folder / "result.json")
            image = StateImage(gzip.decompress((folder / "pre-probe.json.gz").read_bytes()))
            engine = create_engine(state=image, backend="native")
            start = engine.time_us
            inputs = json.loads(gzip.decompress((folder / "inputs.json.gz").read_bytes()))
            for frame in inputs["frames"]:
                stimulus = Stimulus.from_dict(frame["stimulus"])
                if stimulus.time_us >= start:
                    engine.inject(stimulus)
            born = time.monotonic()
            while engine.time_us < int(result["time_us"]):
                study.guard()
                engine.advance_to(min(int(result["time_us"]), engine.time_us + 100000))
            final = engine.capture_state().digest
            assert final == result["state_sha256"], (key, "observation changed dynamics")
            witnesses.append(
                {
                    "key": key,
                    "observed_hash": result["state_sha256"],
                    "unobserved_hash": final,
                    "replay_wall_seconds": time.monotonic() - born,
                }
            )
    return witnesses


def main():
    study = Study(settings())
    try:
        registered_notes = []
        for phase in ("design", "extension", "phase-extension"):
            for language in ("zh", "en"):
                saved = notebooks.note(
                    study.db, study.project, LOCAL_USER, study.identity(f"{phase}:{language}"), revision=1
                )
                assert saved["body"]["text"] == (study.here / f"{phase}.{language}.md").read_text(encoding="utf-8")
                registered_notes.append(
                    {
                        "phase": phase,
                        "language": language,
                        "id": str(saved["id"]),
                        "content_hash": saved["content_hash"],
                    }
                )
        rows, bundles, counts = [], set(), Counter()
        for path in sorted((WORK / "cases").rglob("result.json")):
            study.guard()
            row = read_json(path)
            assert not row["extra"].get("failure"), row["key"]
            checkpoint, image = study.db.load_checkpoint(study.project, row["id"])
            local = StateImage(gzip.decompress((path.parent / "parent-state.json.gz").read_bytes()))
            assert image.digest == local.digest == row["state_sha256"]
            expected_config = dict(row["config"])
            for change in row["extra"].get("interventions", []):
                expected_config.update(change.get("configuration", {}))
            assert image.to_dict()["config"] == expected_config
            context = checkpoint["context"]
            signature = context["runner_manifest_sha256"]
            root = WORK / "runner-revisions" / signature
            manifest = read_json(root / "manifest.json")
            assert digest(manifest) == signature
            assert context["runner_sha256"] == manifest["lab/tools/service_study.py"]
            if signature not in bundles:
                for name, sha in manifest.items():
                    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == sha
                bundles.add(signature)
            assert context["implementation"] == study.implementation
            counts.update(export_verified(study, path.parent, row))
            rows.append(row)
            if len(rows) % 128 == 0:
                print(json.dumps({"verified_cases": len(rows), **counts}), flush=True)
        coverage = Counter(r["key"].split("/")[0] for r in rows)
        expected = {"parents": 4, "representations": 4, "matrix": 1076, "formation": 72, "facilitation": 90}
        # matrix includes 96 extra strengths, 52 expression controls and 32 phase switches.
        # Original matrix has 128 training + 768 probes = 896 cases.
        assert dict(coverage) == expected, coverage
        assert len({r["id"] for r in rows}) == len(rows) == 1246
        replays = observation_replays(study)
        analysis = read_json(WORK / "analysis-final.json")
        assert not analysis["failures"]
        with study.db.tx(study.project) as tx:
            runs = tx.execute("SELECT id FROM runs WHERE project_id=%s", (study.project,)).fetchall()
            pending = tx.execute(
                "SELECT id FROM jobs WHERE project_id=%s AND status IN ('pending','leased')", (study.project,)
            ).fetchall()
            for table, kind in (("input_envelopes", "envelopes"), ("input_frames", "frames")):
                n = tx.execute(f"SELECT count(*) AS n FROM {table} WHERE project_id=%s", (study.project,)).fetchone()[
                    "n"
                ]
                assert n == counts[kind]
        assert not pending
        assert {str(r["id"]) for r in runs} == {r["id"] for r in rows}
        with study.db.tx() as tx:
            size = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        output = {
            "cases": len(rows),
            "coverage": dict(coverage),
            "inputs": dict(counts),
            "verified_runner_bundles": len(bundles),
            "unchanged_core": True,
            "observation_replays": replays,
            "verified_registration_notes": registered_notes,
            "simulation_wall_seconds": sum(r["wall_seconds"] for r in rows),
            "local_bytes": sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file()),
            "database_growth_bytes": size - study.meta["database_bytes_before"],
            "usage_start": study.settings.usage_start,
            "usage_end": read_json(WORK / "usage.json")["used_percent"],
        }
        assert output["simulation_wall_seconds"] <= study.settings.wall_seconds
        assert output["local_bytes"] + max(0, output["database_growth_bytes"]) < study.settings.storage_soft
        new_json(WORK / "audit.json", output)
        (WORK / "STOP").write_text("Registered simulations complete; no further simulations.\n", encoding="utf-8")
        print(json.dumps(output), flush=True)
    finally:
        study.db.close()


if __name__ == "__main__":
    main()
