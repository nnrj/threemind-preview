import hashlib
import json
from pathlib import Path

import mujoco
import pytest
from psycopg.types.json import Jsonb
from test_api import client_for
from test_development import select, start

from threemind_lab.configuration import catalogue, default_spec, validate_configuration
from threemind_lab.database import LOCAL_USER
from threemind_lab.protocols import RunSpec
from threemind_lab.study_tools import study_catalogue, validate_study
from threemind_lab.worker import Worker
from threemind_runtime import birth, create_engine
from threemind_runtime.adapters import PlanarBody, channel_id
from threemind_runtime.body import AmbientConfig, AmbientField, EnvironmentHost
from threemind_runtime.capabilities import probe_worker


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def json_copy(value):
    return json.loads(json.dumps(value))


def test_legacy_environment_frames_and_states_match_frozen_prechange_fixture():
    fixture = json.loads((Path(__file__).parent / "fixtures/environment-seed-legacy.json").read_text())
    # Exact physical hashes are meaningful only with the recorded physics engine.
    assert mujoco.__version__ == fixture["mujoco_version"], "Validate a new physical baseline before changing MuJoCo."
    for row in fixture["rows"]:
        physical = PlanarBody(row["seed"])
        frames = [physical.sample(t, [(1, 0.25), (2, 0.5)]).to_dict() for t in range(0, 120000, 20000)]
        assert digest(frames) == row["physical_frames_sha256"]
        assert digest(physical.capture()) == row["physical_state_sha256"]
        ambient = AmbientField(AmbientConfig(), row["seed"])
        frames = [
            [{"source": name, "stimulus": frame.to_dict()} for name, frame in ambient.sample(t)]
            for t in range(0, 120000, 20000)
        ]
        assert digest(frames) == row["ambient_frames_sha256"]
        assert digest(ambient.capture()) == row["ambient_state_sha256"]
        for original, restored in (
            (physical, PlanarBody(row["seed"], json_copy(physical.capture()))),
            (ambient, AmbientField(AmbientConfig(), row["seed"], json_copy(ambient.capture()))),
        ):
            assert "environment_seed" not in original.capture()
            assert original.sample(120000) == restored.sample(120000)
            assert original.capture() == restored.capture()


def test_physical_randomization_preserves_receptor_namespace_and_actuator_mapping():
    identity = 17
    bodies = [PlanarBody(identity, environment_seed=seed) for seed in (91, 103)]
    assert bodies[0].capture()["qpos"] != bodies[1].capture()["qpos"]
    frames = [body.sample(0, [(1, 0.25), (2, 0.5)]) for body in bodies]
    assert frames[0] != frames[1]
    allowed_channels = {channel_id(identity, "planar-physical-v1", i) for i in range(16)}
    assert all({channel for channel, _ in frame.channels} <= allowed_channels for frame in frames)
    assert bodies[0]._wiring == bodies[1]._wiring
    assert bodies[0].capture()["ctrl"] == bodies[1].capture()["ctrl"]
    restored = PlanarBody(identity, json_copy(bodies[0].capture()), environment_seed=91)
    for time_us in (20000, 40000, 60000):
        assert bodies[0].sample(time_us, [(3, 0.8)]) == restored.sample(time_us, [(3, 0.8)])
    assert bodies[0].capture() == restored.capture()
    for seed in (None, 103):
        with pytest.raises(ValueError, match="environment version"):
            PlanarBody(identity, bodies[0].capture(), environment_seed=seed)


def test_synthetic_randomization_uses_identity_namespace_and_restores_rng():
    cfg = AmbientConfig(transient_rate_per_s=10)
    fields = [AmbientField(cfg, 17, environment_seed=seed) for seed in (91, 103)]
    samples = [field.sample(0) for field in fields]
    assert fields[0].capture()["phase"] != fields[1].capture()["phase"]
    allowed = {
        channel_id(17, "ambient-fixture-" + name, i)
        for name, count in (("slow", 8), ("fast", 11), ("drift", 13))
        for i in range(count)
    }
    assert all({channel for channel, _ in sample[0][1].channels} <= allowed for sample in samples)
    restored = AmbientField(cfg, 17, json_copy(fields[0].capture()), environment_seed=91)
    for time_us in range(100000, 1000000, 100000):
        assert fields[0].sample(time_us) == restored.sample(time_us)
    assert fields[0].capture() == restored.capture()
    for seed in (None, 103):
        with pytest.raises(ValueError, match="incompatible"):
            AmbientField(cfg, 17, fields[0].capture(), environment_seed=seed)


@pytest.mark.parametrize("environment", ["mujoco", "ambient"])
@pytest.mark.parametrize("backend", ["reference", "native"])
def test_host_explicit_seed_provenance_and_exact_resume(environment, backend):
    spec = RunSpec(environment=environment, environment_seed=91, clock="unbounded", body_filter={"enabled": True})
    engine = create_engine(backend=backend)
    host = EnvironmentHost(spec, 0)

    def sample(host, engine):
        frames = []

        def emit(key, source, frame, **metadata):
            frames.append((key, source, frame, metadata))
            if not metadata.get("filter_reason"):
                engine.inject(frame)

        host.poll(engine, emit)
        return frames

    first = sample(host, engine)
    assert first[0][3]["configuration"]["seed"] == spec.seed
    assert first[0][3]["configuration"]["environment_seed"] == 91
    engine.advance_to(10000)
    saved = json_copy(host.capture())
    restored = EnvironmentHost(spec, engine.time_us, state=saved, environment_state=json_copy(host.physical_state()))
    other = create_engine(state=engine.capture_state(), backend=backend)
    for time_us in range(20000, 240000, 10000):
        assert sample(host, engine) == sample(restored, other)
        engine.advance_to(time_us)
        other.advance_to(time_us)
    assert host.capture() == restored.capture() and host.physical_state() == restored.physical_state()
    assert engine.capture_state().digest == other.capture_state().digest
    with pytest.raises(ValueError, match="incompatible"):
        EnvironmentHost(spec.model_copy(update={"environment_seed": 103}), engine.time_us, state=saved)


def test_seed_configuration_defaults_strictness_immutability_and_paired_blocks():
    defaults = default_spec()
    assert defaults["environment_seed"] is None
    field = next(field for field in catalogue()["fields"] if field["path"] == "environment_seed")
    assert field["nullable"] and field["immutable"] and field["null_label"] == "沿用感官身份种子"
    for seed in (-1, 2**32, True, 1.5, "91"):
        result = validate_configuration(defaults | {"environment_seed": seed})
        assert not result["valid"] and result["errors"][0]["path"] == "environment_seed"
    changed = defaults | {"environment_seed": 91}
    assert validate_configuration(changed)["valid"]
    assert not validate_configuration(changed, current=defaults)["valid"]
    # Pausing a seeded run must not trap it in an automatic input environment.
    assert validate_configuration(changed | {"environment": "manual"}, current=changed)["valid"]
    host = EnvironmentHost(RunSpec(**changed | {"environment": "manual"}), 0)
    assert host.deadline() is None and host.physical is None and host.ambient is None
    paired = study_catalogue()["defaults"]
    paired["base"]["environment_seed"] = 91
    assert not validate_study(paired)["valid"]
    assert "environment_seed" in study_catalogue()["shared_paths"]


def test_inherited_identity_accepts_new_environment_and_worker_resume(database):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Independent environment"}).json()["id"]
        base = f"/api/v2/projects/{project}"
        spec = default_spec() | {
            "environment": "mujoco",
            "clock": "unbounded",
            "duration_s": 0.06,
            "checkpoint_us": 20000,
            "sample_us": 10000,
            "seed": 17,
            "environment_seed": 91,
        }
        parent, _ = start(client, base, spec=spec)
        assert Worker(database).once()
        cp, parent_image = database.load_checkpoint(project, parent["run_id"])
        version, _ = select(client, base, parent["run_id"], cp)
        child_spec = spec | {"environment_seed": 103}
        child, _ = start(client, base, version["id"], child_spec)
        stopper = Worker(database)
        stopper.stopping = True
        assert stopper.once()
        _, child_image = database.load_checkpoint(project, child["run_id"])
        for table in ("nodes", "edges"):
            assert child_image.to_dict()[table] == birth(parent_image).to_dict()[table]
        assert database.get_run(project, child["run_id"])["status"] == "paused"
        database.command(project, child["run_id"], "resume", {})
        assert Worker(database).once()
        _, child_image = database.load_checkpoint(project, child["run_id"])
        sibling, _ = start(client, base, version["id"], child_spec)
        assert Worker(database).once()
        assert database.load_checkpoint(project, sibling["run_id"])[1].digest == child_image.digest
        assert database.load_checkpoint(project, parent["run_id"])[1].digest == parent_image.digest
        detail = client.get(base + f"/innate-versions/{version['id']}").json()
        assert "seed" in detail["locked_paths"] and "environment_seed" not in detail["locked_paths"]
        assert detail["protocol"]["environment_seed"] == 91


def test_new_protocols_require_capable_worker_even_with_null_seed(database):
    project = database.create_project({"id": LOCAL_USER}, "Worker protocol matching")["id"]
    spec = default_spec() | {"environment": "manual", "clock": "unbounded", "duration_s": 0.02}
    run = database.create_run(project, "New protocol", spec)
    job = database.enqueue(project, "run", run_id=run["id"])
    assert "worker.environment_seed_v1" in job["required_features"]
    old_caps = probe_worker("native")
    # Isolate the seed capability: this synthetic report supports raw readouts.
    old_caps["features"]["worker.raw_readout_v1"] = {"state": "available"}
    old_caps["features"]["worker.development_v1"] = {"state": "available"}
    database.announce_worker("v31-worker", old_caps)
    assert database.claim("v31-worker", capabilities=old_caps) is None
    with database.tx(project) as db:
        for kind, run_id, params in (
            ("research_plan", run["id"], {}),
            ("study", None, {"protocol": study_catalogue()["defaults"]}),
        ):
            requirements = db.execute(
                "SELECT required_job_features(%s,%s,%s) AS features", (kind, run_id, Jsonb(params))
            ).fetchone()["features"]
            assert "worker.environment_seed_v1" in requirements
    old_spec = {key: value for key, value in spec.items() if key != "environment_seed"}
    old = database.create_run(project, "Stored legacy protocol", old_spec)
    legacy_job = database.enqueue(project, "run", run_id=old["id"])
    assert "worker.environment_seed_v1" not in legacy_job["required_features"]
    claimed = database.claim("v31-worker", capabilities=old_caps)
    assert claimed["id"] == legacy_job["id"]
    database.finish(claimed, result={"claim_checked": True})
    assert Worker(database).once()
    assert database.get_run(project, run["id"])["status"] == "completed"
