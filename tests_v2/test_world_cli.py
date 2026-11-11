import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from threemind_core import Stimulus
from threemind_runtime import ArtifactCodec, create_engine
from threemind_runtime.store import SQLiteStore
from threemind_runtime.world_schema import default_world


def invoke(*args, module="threemind_runtime.world_cli", check=True):
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", module, *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    if check:
        assert result.returncode == 0, result.stderr
    return result


@pytest.mark.parametrize("kernel_id", [None, "threemind.continuous-memory/5.1"])
def test_world_cli_no_postgres_atomic_recovery_model_export_and_closed_adapter(tmp_path, kernel_id):
    protocol = tmp_path / "world.json"
    invoke("--write-example", protocol)
    assert json.loads(protocol.read_text(encoding="utf-8")) == default_world().model_dump(mode="json")
    model = tmp_path / "model.tmind"
    store_path = tmp_path / "device.sqlite"
    initial_model = []
    if kernel_id:
        source = tmp_path / "initial.tmind"
        source.write_bytes(ArtifactCodec.encode(create_engine(kernel_id=kernel_id).capture_state(), "tmind"))
        initial_model = ["--model", source]
    first = invoke("--world", protocol, *initial_model, "--store", store_path, "--until-us", 87000, "--clock", "unbounded")
    assert json.loads(first.stdout)["metrics"]["nodes"] > 0
    invoke("--resume", "--store", store_path, "--until-us", 240000, "--clock", "unbounded", "--export", model)
    continuous = tmp_path / "continuous.tmind"
    evidence = tmp_path / "stimuli.jsonl"
    invoke(
        "--world",
        protocol,
        *initial_model,
        "--until-us",
        240000,
        "--clock",
        "scaled",
        "--speed",
        100,
        "--export",
        continuous,
        "--evidence",
        evidence,
    )
    assert ArtifactCodec.decode(model.read_bytes()).digest == ArtifactCodec.decode(continuous.read_bytes()).digest
    lines = [json.loads(line) for line in evidence.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 13 and lines[0]["kind"] == "protocol"
    assert lines[1]["raw_stimulus"]["time_us"] == "20000"
    assert lines[-1]["observation"]["physical_time_us"] == "240000"
    rejected = invoke(
        "--resume",
        "--store",
        store_path,
        "--instance",
        "world",
        "--clock",
        "unbounded",
        module="threemind_runtime.cli",
        check=False,
    )
    assert rejected.returncode and "owning adapter" in rejected.stderr
    local = SQLiteStore(store_path)
    revision, image, profile, context = local.load("world", with_profile=True, with_context=True)
    with pytest.raises(ValueError, match="owning adapter"):
        local.save("world", image, expected_revision=revision, profile=profile)
    assert local.load("world")[0] == revision
    altered = tmp_path / "altered.json"
    value = json.loads(protocol.read_text(encoding="utf-8"))
    value["physics"]["step_us"] = 1000
    altered.write_text(json.dumps(value), encoding="utf-8")
    assert invoke("--resume", "--store", store_path, "--world", altered, check=False).returncode
    with sqlite3.connect(store_path) as db:
        db.execute(
            "UPDATE runtime_contexts SET context_json=? WHERE instance=? AND revision=?",
            (json.dumps(context | {"next_world_us": 1}), "world", revision),
        )
    with pytest.raises(ValueError, match="context checksum"):
        local.load("world", with_context=True)


def test_world_sqlite_context_retention_and_cas_are_atomic(tmp_path):
    store = SQLiteStore(tmp_path / "local.sqlite")
    engine = create_engine(backend="reference")
    for index in range(10):
        engine.advance_to(index * 1000)
        store.save("fixture", engine.capture_state(), expected_revision=index, context={"time": engine.time_us})
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT count(*) FROM runtime_contexts").fetchone()[0] == 8
    with pytest.raises(ValueError, match="another writer"):
        store.save("fixture", engine.capture_state(), expected_revision=9, context={"time": -1})
    assert store.load("fixture", with_context=True)[-1] == {"time": 9000}


def test_rust_accepts_exported_world_brain_but_not_partial_world_continuation(tmp_path):
    runtime = (
        Path(__file__).resolve().parents[1]
        / "target"
        / "release"
        / ("threemind-runtime.exe" if sys.platform == "win32" else "threemind-runtime")
    )
    if not runtime.exists():
        pytest.skip("build the independent Runtime first")
    protocol = tmp_path / "world.json"
    protocol.write_text(default_world().model_dump_json(), encoding="utf-8")
    exported, path = tmp_path / "brain.tmind", tmp_path / "device.sqlite"
    invoke("--world", protocol, "--until-us", 87000, "--clock", "unbounded", "--store", path, "--export", exported)
    store = SQLiteStore(path)
    previous = store.load("world", with_context=True)
    failed = subprocess.run(
        [str(runtime), "--resume", "--store", str(path), "--instance", "world", "--clock", "unbounded"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert failed.returncode and "owning adapter" in failed.stderr
    after = store.load("world", with_context=True)
    assert after[0] == previous[0] and after[1].digest == previous[1].digest and after[-1] == previous[-1]
    original = exported.read_bytes()
    image = ArtifactCodec.decode(original)
    engine = create_engine(state=image, backend="native")
    stimulus = Stimulus(90123, ((3972524015, 0.75), (3827712894, 0.65)))
    data = tmp_path / "new-sensation.jsonl"
    data.write_text(json.dumps({"time_us": str(stimulus.time_us), "channels": stimulus.channels}), encoding="utf-8")
    output = tmp_path / "continued.tmind"
    result = subprocess.run(
        [
            str(runtime),
            "--model",
            str(exported),
            "--input",
            str(data),
            "--until-us",
            "130000",
            "--clock",
            "unbounded",
            "--export",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    engine.inject(stimulus)
    engine.advance_to(130000)
    assert ArtifactCodec.decode(output.read_bytes()).digest == engine.capture_state().digest
    assert engine.metrics()["nodes"] > len(image.to_dict()["nodes"])
    assert exported.read_bytes() == original
