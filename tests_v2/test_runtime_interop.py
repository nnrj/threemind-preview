import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from threemind_core import Engine, Stimulus
from threemind_runtime import ArtifactCodec
from threemind_runtime.adapters import PlanarBody
from threemind_runtime.store import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path(
    os.environ.get(
        "THREEMIND_TEST_RUNTIME",
        ROOT / "target/release" / ("threemind-runtime.exe" if sys.platform == "win32" else "threemind-runtime"),
    )
)


def test_physics_causal_delivery_and_resume():
    a = PlanarBody(23)
    event = a.sample(0)
    assert event.time_us == 20000
    for t in range(20000, 200000, 20000):
        a.sample(t)
    b = PlanarBody(23, a.capture())
    for t in range(200000, 600000, 20000):
        left, right = a.sample(t), b.sample(t)
        assert left.time_us == right.time_us
        assert [c for c, _ in left.channels] == [c for c, _ in right.channels]
        assert [v for _, v in left.channels] == pytest.approx([v for _, v in right.channels], abs=1e-13)
    assert a.capture() == b.capture()


@pytest.mark.parametrize("format", ["tmind", "json"])
@pytest.mark.parametrize(
    "kernel_id",
    [
        "threemind.causal/9",
        "threemind.continuous/1",
        "threemind.continuous-memory/1",
        "threemind.continuous-memory/2",
        "threemind.continuous-memory/3",
        "threemind.continuous-memory/3.1",
        "threemind.continuous-memory/4",
        "threemind.continuous-memory/5",
        "threemind.continuous-memory/5.1",
        "threemind.continuous-memory/5.2",
        "threemind.continuous-memory/5.3",
        "threemind.lif/1",
    ],
)
def test_independent_rust_artifact_and_sqlite_interop(tmp_path, format, kernel_id):
    if not RUNTIME.exists():
        pytest.skip("build the independent Runtime first")
    from threemind_runtime import create_engine

    a = create_engine(kernel_id=kernel_id)
    a.inject(Stimulus(0, ((7, 0.5), (9, 0.8))))
    a.inject(Stimulus(57123, ((12, 0.2), (9, 0.6))))
    a.advance_to(12345)
    initial = a.capture_state()
    original_bytes = ArtifactCodec.encode(initial, format)
    source = tmp_path / f"input.{format}"
    source.write_bytes(original_bytes)
    output = tmp_path / "after.tmind"
    db = tmp_path / "device.sqlite"
    result = subprocess.run(
        [
            str(RUNTIME),
            "--model",
            str(source),
            "--clock",
            "unbounded",
            "--until-us",
            "67890",
            "--export",
            str(output),
            "--store",
            str(db),
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    a.advance_to(67890)
    restored = ArtifactCodec.decode(output.read_bytes())
    assert restored.digest == a.capture_state().digest
    assert source.read_bytes() == original_bytes
    assert ArtifactCodec.decode(source.read_bytes()).digest == initial.digest
    local = SQLiteStore(db)
    revision, state = local.load("default")
    assert state.digest == restored.digest
    a.advance_to(90123)
    local.save("default", a.capture_state(), expected_revision=revision)
    final = tmp_path / "final.json"
    result = subprocess.run(
        [
            str(RUNTIME),
            "--resume",
            "--store",
            str(db),
            "--clock",
            "unbounded",
            "--until-us",
            "150000",
            "--export",
            str(final),
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    a.advance_to(150000)
    assert ArtifactCodec.decode(final.read_bytes()).digest == a.capture_state().digest


@pytest.mark.parametrize(
    "kernel_id",
    [
        "threemind.causal/9",
        "threemind.continuous/1",
        "threemind.continuous-memory/1",
        "threemind.continuous-memory/2",
        "threemind.continuous-memory/3",
        "threemind.continuous-memory/3.1",
        "threemind.continuous-memory/4",
        "threemind.continuous-memory/5",
        "threemind.continuous-memory/5.1",
        "threemind.continuous-memory/5.2",
        "threemind.continuous-memory/5.3",
        "threemind.lif/1",
    ],
)
def test_standalone_definition_selects_kernel_and_rejects_invented_operators(tmp_path, kernel_id):
    from threemind_kernels.definition import KernelDefinition

    if not RUNTIME.exists():
        pytest.skip("build the independent Runtime first")
    definition = KernelDefinition.default(kernel_id)
    path, output = tmp_path / "definition.json", tmp_path / "model.json"
    path.write_bytes(definition.payload)
    args = [str(RUNTIME), "--definition", str(path), "--clock", "unbounded", "--until-us", "0", "--export", str(output)]
    result = subprocess.run(args, capture_output=True, check=False, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert ArtifactCodec.decode(output.read_bytes()).digest == definition.create().capture_state().digest
    altered = definition.to_dict()
    altered["operators"][0]["id"] = "unregistered.eval/1"
    path.write_text(json.dumps(altered), encoding="utf-8")
    result = subprocess.run(args[:-2], capture_output=True, check=False, text=True, timeout=15)
    assert result.returncode != 0 and "operator" in result.stderr


def test_solver_convergence_and_impulse_independence():
    from threemind_core import Config

    states = []
    # Same physical stimulus times/delay and duration; only solver resolution changes.
    for step in (10000, 5000, 2500, 1250):
        e = Engine(Config(step_us=step, activation_floor=1e-9))
        e.inject(Stimulus(0, ((1, 0.3), (2, 0.4))))
        e.advance_to(0)
        states.append((e.capture_state(), e))
    weights = [i.to_dict()["edges"][0]["weight"] for i, _ in states]
    assert len(set(weights)) == 1  # Solver granularity cannot change an external impulse.
    for _, e in states:
        e.advance_to(500000)
    activation = [e.metrics()["activation"] for _, e in states]
    errors = [abs(v - activation[-1]) for v in activation[:-1]]
    assert errors[2] < errors[1] < errors[0]
    assert errors[0] < 0.03


def test_runtime_clock_does_not_change_dynamics(tmp_path):
    if not RUNTIME.exists():
        pytest.skip("build the independent Runtime first")
    source = tmp_path / "stimuli.jsonl"
    source.write_text(json.dumps({"time_us": "0", "channels": [[1, 0.4], [2, 0.6]], "intensity": 1.0}) + "\n")
    hashes = []
    for clock in ("realtime", "scaled", "unbounded"):
        result = subprocess.run(
            [str(RUNTIME), "--input", str(source), "--until-us", "50000", "--clock", clock, "--speed", "5"],
            capture_output=True,
            check=False,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        hashes.append(json.loads(result.stdout)["state_hash"])
    assert len(set(hashes)) == 1


def test_independent_rust_creation_default_matches_python(tmp_path):
    from threemind_runtime import create_engine

    if not RUNTIME.exists():
        pytest.skip("build the independent Runtime first")
    output = tmp_path / "default.json"
    result = subprocess.run(
        [str(RUNTIME), "--clock", "unbounded", "--until-us", "0", "--export", str(output)],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert ArtifactCodec.decode(output.read_bytes()).digest == create_engine().capture_state().digest


@pytest.mark.parametrize("format", ["tmind", "json"])
def test_local_checkpoint_preserves_transport_resources_and_object_clocks(tmp_path, format):
    from threemind_kernels.local import LocalConfig
    from threemind_kernels.local_native import NativeLocalEngine

    if not RUNTIME.exists():
        pytest.skip("build the independent Runtime first")
    e = NativeLocalEngine(
        LocalConfig(
            energy_simulation_enabled=True,
            energy_region_count=1,
            energy_initial_reserve=2.0,
            dormant_traces_enabled=True,
            quiescence_death_us=10**12,
        )
    )
    for t in (0, 73000, 1200000):
        e.inject(Stimulus(t, ((1, 0.8), (2, 0.6))))
    e.supply_energy(0.5, time_us=100000)
    e.supply_energy(0.5, time_us=1300000)
    e.advance_to(611337)
    image = e.capture_state()
    state = image.to_dict()
    assert any(edge["short_term"] and edge["fast"] for edge in state["edges"])
    assert state["queue"] and state["timers"] and state["energy_serial"] > 0
    source, output = tmp_path / ("local." + format), tmp_path / "after.tmind"
    source.write_bytes(ArtifactCodec.encode(image, format))
    assert ArtifactCodec.decode(source.read_bytes()).digest == image.digest
    result = subprocess.run(
        [
            str(RUNTIME),
            "--model",
            str(source),
            "--clock",
            "unbounded",
            "--until-us",
            "2000000",
            "--export",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    e.advance_to(2000000)
    assert ArtifactCodec.decode(output.read_bytes()).digest == e.capture_state().digest
