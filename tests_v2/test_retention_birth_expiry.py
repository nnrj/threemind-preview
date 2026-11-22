"""Engineering regressions for /3.1; no historical individual or research trial."""

import copy
from dataclasses import asdict
from uuid import uuid4

import pytest
from test_causal9_baseline import assert_state_close

from threemind_core import StateImage, Stimulus
from threemind_kernels.definition import KernelDefinition
from threemind_kernels.local import LocalConfig, LocalEngine
from threemind_kernels.local_native import NativeLocalEngine
from threemind_kernels.registry import DEFAULT_KERNEL, kernel_catalog, resolve_kernel
from threemind_kernels.retention import RetentionConfig, RetentionEngine
from threemind_kernels.retention31 import KERNEL_ID, Retention31Config, Retention31Engine
from threemind_kernels.retention31_native import NativeRetention31Engine
from threemind_kernels.retention_native import NativeRetentionEngine
from threemind_runtime import ArtifactCodec, create_engine

BACKENDS = [Retention31Engine, NativeRetention31Engine]
MODES = ["automatic", "manual-threshold", "manual-wait"]


def recovery_parameters(mode="automatic", **extra):
    return {
        "energy_simulation_enabled": True,
        "energy_initial_reserve": 0.05,
        "energy_direct_cost": 0.2,
        # Explicit engineering-only extension: observe reclamation before death.
        "quiescence_death_us": 200_000_000,
        "node_retention_mode": "automatic" if mode == "automatic" else "manual",
        "prune_support": 0.0 if mode == "manual-wait" else 0.015,
        **extra,
    }


def stimulate(engine):
    engine.inject(Stimulus(0, ((1, 0.7), (2, 0.6))))
    engine.advance_to(0)
    return engine.capture_state()


@pytest.mark.parametrize("factory", [RetentionEngine, NativeRetentionEngine])
def test_original_memory3_zero_response_witness_remains_unchanged(factory):
    engine = factory(RetentionConfig(energy_simulation_enabled=True, energy_initial_reserve=0.05,
                                     energy_direct_cost=0.2))
    image = stimulate(engine)
    assert image.digest == "ba7714ed08fbb9283098a36101cbcf57aadc45294ea257e25f82489614d16fd6"
    with pytest.raises(ValueError, match="missing or inconsistent local expiry"):
        factory(state=image)


@pytest.mark.parametrize("factory", BACKENDS)
@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("formula", ["adaptive-half-life", "legacy-stability"])
def test_zero_response_has_expiry_without_learning_and_recovers(factory, mode, formula):
    engine = factory(Retention31Config(**recovery_parameters(mode, consolidation_mode=formula)))
    image = stimulate(engine)
    state = image.to_dict()
    zero = next(node for node in state["nodes"] if node["channel"] == 2)
    assert zero["activation"] == zero["support"] == zero["trace"] == zero["touches"] == 0
    retained = state["operator_state"]["retention"]
    assert [zero["id"], engine.config.memory_half_life_min_s, "0"] in retained["nodes"]
    assert zero["id"] not in {row[0] for row in retained["salience"] + retained["fatigue"]}
    deadline = next(int(row[3]) for row in retained["deadlines"] if row[:3] == [0, zero["id"], 0])
    assert deadline == (100_000 if mode == "automatic" else 80_000_000 if mode == "manual-wait" else 80_100_000)
    restored = factory(state=image)
    assert restored.capture_state().digest == image.digest
    # A rejected repeat does not reset the isolation/last-effective-touch clock.
    for subject in (engine, restored):
        subject.inject(Stimulus(50_000, ((2, 0.6),)))
        subject.advance_to(50_000)
        current = subject.capture_state().to_dict()
        node = next(row for row in current["nodes"] if row["id"] == zero["id"])
        assert node["last_touch_us"] == "0" and node["touches"] == node["support"] == 0
        assert [0, zero["id"], 0, str(deadline)] in current["operator_state"]["retention"]["deadlines"]
        subject.advance_to(deadline)
        assert zero["id"] not in {row["id"] for row in subject.capture_state().to_dict()["nodes"]}
    assert restored.capture_state().digest == engine.capture_state().digest
    assert factory(state=engine.capture_state()).capture_state().digest == engine.capture_state().digest


@pytest.mark.parametrize("factory", BACKENDS)
def test_effective_retouch_at_expiry_precedes_reclamation(factory):
    engine = factory(Retention31Config(**recovery_parameters()))
    stimulate(engine)
    engine.supply_energy(0.5, time_us=100_000, source="engineering-recovery")
    engine.inject(Stimulus(100_000, ((2, 0.6),)))
    engine.advance_to(100_000)
    node = next(row for row in engine.capture_state().to_dict()["nodes"] if row["channel"] == 2)
    assert node["activation"] > 0 and node["support"] > 0.006 and node["touches"] == 1
    assert factory(state=engine.capture_state()).capture_state().digest == engine.capture_state().digest


@pytest.mark.parametrize("factory", BACKENDS)
@pytest.mark.parametrize("disabled", [{"retain_nodes": True}, {"plasticity": False}])
def test_expiry_fix_respects_explicit_no_reclamation(factory, disabled):
    engine = factory(Retention31Config(**recovery_parameters(**disabled)))
    image = stimulate(engine)
    assert not image.to_dict()["operator_state"]["retention"]["deadlines"]
    restored = factory(state=image)
    restored.advance_to(100_000_000)
    assert restored.metrics()["nodes"] == 2
    assert factory(state=restored.capture_state()).capture_state().digest == restored.capture_state().digest


@pytest.mark.parametrize("backend", ["reference", "native"])
@pytest.mark.parametrize("formula", ["adaptive-half-life", "legacy-stability"])
def test_effective_learning_is_unchanged_from_memory3(backend, formula):
    original = create_engine(kernel_id="threemind.continuous-memory/3", backend=backend,
                             config={"consolidation_mode": formula, "quiescence_death_us": 200_000_000})
    fixed = create_engine(kernel_id=KERNEL_ID, backend=backend,
                          config={"consolidation_mode": formula, "quiescence_death_us": 200_000_000})
    for subject in (original, fixed):
        for t in (0, 73_000, 180_000, 610_000):
            subject.inject(Stimulus(t, ((10, 0.8), (11, 0.6), (20, 0.4))))
    for t in (0, 123_456, 1_200_000, 3_000_000):
        original.advance_to(t)
        fixed.advance_to(t)
        old, new = original.capture_state().to_dict(), fixed.capture_state().to_dict()
        for state in (old, new):
            for key in ("dynamics", "schema", "definition", "definition_hash"):
                state.pop(key)
        assert_state_close(new, old)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("formula", ["adaptive-half-life", "legacy-stability"])
def test_independent_backends_cross_restore_and_observation_batching(mode, formula):
    config = Retention31Config(**recovery_parameters(mode, consolidation_mode=formula))
    a, b = Retention31Engine(config), NativeRetention31Engine(config)
    stimulate(a)
    stimulate(b)
    assert_state_close(a.capture_state().to_dict(), b.capture_state().to_dict())
    a = Retention31Engine(state=b.capture_state())
    b = NativeRetention31Engine(state=a.capture_state())
    for subject in (a, b):
        subject.supply_energy(0.5, time_us=30_000, source="engineering-recovery")
        subject.inject(Stimulus(50_000, ((2, 0.6), (3, 0.3))))
    for t in (60_000, 100_000, 1_000_000):
        a.advance_to(t, lambda _: (a.metrics(), a.graph(), a.capture_state()))
    b.advance_to(1_000_000)
    assert_state_close(a.capture_state().to_dict(), b.capture_state().to_dict())


@pytest.mark.parametrize("factory", BACKENDS)
def test_missing_deadline_is_still_rejected_instead_of_repaired_on_read(factory):
    engine = factory(Retention31Config(**recovery_parameters()))
    image = stimulate(engine).to_dict()
    image["operator_state"]["retention"]["deadlines"] = [
        row for row in image["operator_state"]["retention"]["deadlines"] if row[:3] != [0, 2, 0]
    ]
    with pytest.raises(ValueError, match="missing or inconsistent local expiry"):
        factory(state=StateImage.from_dict(image))


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_version_routing_export_and_no_silent_upgrade(backend):
    engine = create_engine(Retention31Config(), backend=backend)
    assert engine.capture_state().to_dict()["dynamics"] == KERNEL_ID
    assert KernelDefinition.default(KERNEL_ID).create(backend=backend).capture_state().digest == engine.capture_state().digest
    for format in ("tmind", "json"):
        image = ArtifactCodec.decode(ArtifactCodec.encode(engine.capture_state(), format))
        assert create_engine(state=image, backend=backend).capture_state().digest == image.digest
        with pytest.raises(ValueError, match="identity|schema"):
            resolve_kernel("threemind.continuous-memory/3").create(state=image, backend=backend)
    old = create_engine(kernel_id="threemind.continuous-memory/3", backend=backend).capture_state()
    assert create_engine(state=old, backend=backend).capture_state().digest == old.digest
    with pytest.raises(ValueError, match="identity|schema"):
        resolve_kernel(KERNEL_ID).create(state=old, backend=backend)
    assert DEFAULT_KERNEL == "threemind.continuous-memory/6.1"


def test_catalogue_and_validation_include_same_parameters_and_birth_locks():
    from threemind_lab.configuration import catalogue, validate_configuration

    catalog = catalogue(kernel_id=KERNEL_ID)
    fields = {field["path"]: field for field in catalog["fields"]}
    assert {key[7:] for key in fields if key.startswith("config.")} == set(asdict(Retention31Config())) - {
        "propagation_limit", "edge_adaptation_limit",
    }
    row = next(kernel for kernel in kernel_catalog() if kernel["kernel_id"] == KERNEL_ID)
    assert row["version"] == "3.1" and row["display_name"] == "continuous-memory/3.1"
    assert Retention31Config().to_dict() == RetentionConfig().to_dict()
    assert validate_configuration(catalog["defaults"])["valid"]
    altered = copy.deepcopy(catalog["defaults"])
    altered["config"]["memory_growth_formula"] = "linear-saturating"
    result = validate_configuration(altered, current=catalog["defaults"])
    assert not result["valid"] and any(error["path"] == "config.memory_growth_formula" for error in result["errors"])
    altered = copy.deepcopy(catalog["defaults"])
    altered["config"]["propagation_limit"] = 1
    assert not validate_configuration(altered)["valid"]


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_zero_response_settles_only_the_addressed_object(backend):
    visits = []
    for unrelated in (0, 200):
        engine = create_engine(kernel_id=KERNEL_ID, backend=backend,
                               config=recovery_parameters(energy_initial_reserve=0))
        if unrelated:
            engine.inject(Stimulus(0, tuple((channel, 0.6) for channel in range(100, 100 + unrelated))))
            engine.advance_to(0)
        before = engine.metrics()["retention"]["node_settlements"]
        engine.inject(Stimulus(0, ((2, 0.6),)))
        engine.advance_to(0)
        visits.append(engine.metrics()["retention"]["node_settlements"] - before)
    assert visits == [1, 1]


@pytest.mark.parametrize("factory", [LocalEngine, NativeLocalEngine])
@pytest.mark.parametrize("energy_model", ["local-field", "global-ledger"])
@pytest.mark.parametrize("formula", ["adaptive-half-life", "legacy-stability"])
@pytest.mark.parametrize("mode", MODES)
def test_memory4_zero_energy_birth_already_has_local_expiry(factory, energy_model, formula, mode):
    engine = factory(LocalConfig(**recovery_parameters(mode, energy_initial_reserve=0,
                                                       energy_model=energy_model, consolidation_mode=formula)))
    image = stimulate(engine)
    state = image.to_dict()
    assert state["dynamics"] == "threemind.continuous-memory/4"
    assert len(state["nodes"]) == 2 and not state["edges"]
    for node in state["nodes"]:
        assert node["activation"] == node["support"] == 0
        assert node["half_life"] == engine.config.memory_half_life_min_s
        assert any(timer[:3] == [3, node["id"], 0] for timer in state["timers"])
    restored = factory(state=image)
    assert restored.capture_state().digest == image.digest
    final_time = max(int(timer[3]) for timer in state["timers"])
    engine.advance_to(final_time)
    restored.advance_to(final_time)
    assert engine.metrics()["nodes"] == 0
    assert restored.capture_state().digest == engine.capture_state().digest


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_memory31_lab_prepare_start_save_and_zero_energy_resume(database, backend):
    from test_api import client_for

    from threemind_lab.configuration import default_spec
    from threemind_lab.worker import Worker

    spec = default_spec(KERNEL_ID) | {"environment": "manual", "clock": "unbounded"}
    spec["config"].update(energy_simulation_enabled=True, energy_initial_reserve=0)
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Local birth expiry regression"}).json()["id"]
        root = f"/api/v2/projects/{project}/runs"
        result = client.post(root, json={"name": "Blank /3.1", "spec": spec,
                                         "execution": {"backend": backend}, "start_immediately": False})
        assert result.status_code == 201, result.text
        run = result.json()["id"]
        base = root + "/" + run
        assert client.post(base + "/commands", json={"kind": "resume"}).status_code == 200
        assert client.post(base + "/commands", json={"kind": "pause"}).status_code == 200
        worker = Worker(database, backend=backend, name="birth-expiry-test")
        with database.tx(project) as db:
            features = db.execute("SELECT required_features FROM jobs WHERE run_id=%s", (run,)).fetchone()
        worker.capabilities = {"queue": "runtime", "backend": backend,
                               "features": {key: {"state": "available"} for key in features["required_features"]}}
        assert worker.once()
        saved = database.get_run(project, run)
        assert saved["status"] == "paused" and saved["error"] is None
        sent = client.post(base + "/inputs", json={"request_id": str(uuid4()), "adapter_id": "text-sensor",
                                                  "payload": {"text": "A", "intensity": 1.0}})
        assert sent.status_code == 202, sent.text
        for target in (50_000, 150_000):
            duration = target - int(saved["time_us"])
            action = client.post(base + "/research/actions", json={
                "request_id": str(uuid4()), "kind": "runtime.advance", "expected_revision": saved["revision"],
                "duration_us": duration,
            })
            assert action.status_code == 200, action.text
            assert worker.once()
            saved = database.get_run(project, run)
            assert saved["status"] == "paused" and saved["time_us"] == str(target), saved["error"]
            checkpoint, image = database.load_checkpoint(project, run)
            assert image.to_dict()["dynamics"] == KERNEL_ID and checkpoint["context"]
            assert create_engine(state=image, backend=backend).capture_state().digest == image.digest
            if target == 50_000:
                assert saved["metrics"]["nodes"] > 0
            else:
                assert saved["metrics"]["nodes"] == 0
        assert saved["spec"] == spec

