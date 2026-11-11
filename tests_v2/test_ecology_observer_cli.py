import json
import os
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from test_ecology_runtime import configuration

from threemind_runtime.ecology_job import EcologyJob
from threemind_runtime.ecology_observer import ObserverConfig, WarningRule
from threemind_runtime.ecology_observer_cli import PopulationEvidenceReader, observe_checkpoint
from threemind_runtime.population_store import PopulationStore

ROOT = Path(__file__).resolve().parents[1]


def fixture(tmp_path):
    path = tmp_path / "有空格 population.sqlite"
    store = PopulationStore(path)
    job = EcologyJob(ecology=configuration())
    events = []
    runtime = job.open(record=lambda event: events.append({"scope": "ecology", **event}))
    store.save("sample", job, runtime.checkpoint(), expected_revision=0, events=events)
    events.clear()
    runtime.advance_to(20000)
    store.save("sample", job, runtime.checkpoint(), expected_revision=1, events=events)
    return path, store, job, runtime, events


def test_readonly_observer_works_without_reading_brain_blobs_and_releases_snapshots(tmp_path):
    path, store, job, runtime, events = fixture(tmp_path)

    class NoBrainReader(PopulationEvidenceReader):
        @contextmanager
        def connect(self):
            with super().connect() as db:
                db.set_authorizer(
                    lambda action, table, *rest: (
                        sqlite3.SQLITE_DENY
                        if action == sqlite3.SQLITE_READ and table in ("population_states", "population_chunks")
                        else sqlite3.SQLITE_OK
                    )
                )
                yield db

    try:
        reader = NoBrainReader(path, "sample")
        before = store.load("sample")[2]
        config = ObserverConfig(
            enabled=True,
            rules=[
                WarningRule(id="living", metric="living_bodies", threshold=1),
                WarningRule(id="core", metric="viable_cores", threshold=1),
            ],
        )
        records = list(observe_checkpoint(reader, 2, config, {}))
        assert [r["code"] for r in records if r.get("kind") == "warning"] == ["triggered", "missing_evidence"]
        assert records[-1]["type"] == "cursor" and records[-1]["checkpoint_revision"] == 2
        assert records[-1]["rule_state"]["core"]["status"] == "missing"
        assert next(r for r in records if r.get("kind") == "summary")["facts"]["births"] == 2
        assert before[0] == store.load("sample")[2][0]
        assert {k: v.digest for k, v in before[1].items()} == {
            k: v.digest for k, v in store.load("sample")[2][1].items()
        }
        with reader.connect() as db, pytest.raises(sqlite3.OperationalError, match="readonly"):
            db.execute("DELETE FROM population_instances")
        held = reader.events(2)
        next(held)
        events.clear()
        runtime.advance_to(40000)
        store.save("sample", job, runtime.checkpoint(), expected_revision=2, events=events)
        assert reader.latest() == 3
        with store.connect() as db:
            assert db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] == 0
        assert list(held)  # Pausing a console didn't pin its old SQLite snapshot.
        assert list(observe_checkpoint(reader, 999, ObserverConfig(), {})) == []
        with pytest.raises(ValueError, match="exceeds"):
            PopulationEvidenceReader(path, "sample", maximum_manifest_bytes=1).checkpoint(1)
    finally:
        runtime.close()


def cli(*args):
    program = "import sys; from threemind_runtime.ecology_observer_cli import main; main(); assert not any(n.startswith('threemind_lab') for n in sys.modules)"
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-c", program, *map(str, args)],
        cwd=ROOT,
        env=os.environ | {"PYTHONPATH": str(ROOT / "src")},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        timeout=25,
        check=False,
    )


def test_cli_fixed_scope_output_disabled_default_and_input_protection(tmp_path):
    path, _, _, runtime, _ = fixture(tmp_path)
    runtime.close()
    config_path = tmp_path / "observer.json"
    assert cli("--write-example", config_path).returncode == 0
    result = cli("--store", path, "--instance", "sample", "--configuration", config_path, "--format", "jsonl")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.splitlines()[-1])["reason"] == "observer_disabled"
    config_path.write_text(ObserverConfig(enabled=True, start_from="beginning").model_dump_json(), encoding="utf-8")
    output = tmp_path / "observations.jsonl"
    result = cli(
        "--store", path, "--instance", "sample", "--configuration", config_path, "--format", "jsonl", "--output", output
    )
    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["maximum_checkpoint_revision"] == 2
    assert rows[-1] == {"type": "end", "reason": "snapshot_complete", "through_revision": 2}
    assert len([r for r in rows if r.get("kind") == "summary"]) == 2
    result = cli(
        "--store",
        path,
        "--instance",
        "sample",
        "--configuration",
        config_path,
        "--through-revision",
        1,
        "--language",
        "en",
    )
    assert result.returncode == 0 and "Historical individuals" in result.stdout
    assert "[r2]" not in result.stdout and "training task" not in result.stdout.lower()
    original = output.read_bytes()
    refused = cli("--store", path, "--instance", "sample", "--configuration", config_path, "--output", output)
    assert refused.returncode != 0 and output.read_bytes() == original
    refused = cli("--store", path, "--instance", "sample", "--configuration", config_path, "--output", path)
    assert refused.returncode != 0 and "overwrite" in refused.stderr
    config_path.write_text('{"enabled":true,"enabled":false}', encoding="utf-8")
    refused = cli("--store", path, "--instance", "sample", "--configuration", config_path)
    assert refused.returncode != 0 and "duplicate" in refused.stderr
    config_path.write_text("[]", encoding="utf-8")
    refused = cli("--store", path, "--instance", "sample", "--configuration", config_path)
    assert refused.returncode == 2 and "Traceback" not in refused.stderr
