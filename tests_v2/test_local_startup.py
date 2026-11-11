"""Lab startup regressions; these are engineering tests, not research trials."""

from uuid import uuid4

import pytest
from test_api import client_for

from threemind_core import Stimulus
from threemind_kernels.registry import resolve_kernel
from threemind_lab.configuration import default_spec
from threemind_lab.measurements import energy_endpoints
from threemind_lab.worker import Worker
from threemind_runtime import create_engine
from threemind_runtime.energy_supply import EnergySupplier, EnergySupplyConfig


@pytest.mark.parametrize("kernel_id", ["threemind.continuous-memory/4", "threemind.continuous-memory/5", "threemind.continuous-memory/5.1"])
@pytest.mark.parametrize("backend", ["reference", "native"])
@pytest.mark.parametrize("energy_model", ["local-field", "global-ledger"])
@pytest.mark.parametrize("enabled", [False, True])
def test_local_energy_observation_is_read_only_and_has_explicit_configuration(kernel_id, backend, energy_model, enabled):
    LocalConfig = type(resolve_kernel(kernel_id).configuration())
    engine = create_engine(LocalConfig(energy_model=energy_model, energy_simulation_enabled=enabled),
                           kernel_id=kernel_id, backend=backend)
    engine.inject(Stimulus(0, ((1, 0.8), (2, 0.6))))
    engine.advance_to(10000)
    original = engine.capture_state()
    metric = engine.metrics()
    assert metric["energy"]["parameters"]["energy_simulation_enabled"] is enabled
    assert metric["energy"]["parameters"]["energy_model"] == energy_model
    assert metric["energy"]["settled_state_time_us"] == "10000"
    if enabled:
        assert energy_endpoints(metric)["energy_consumed"] > 0
    else:
        assert all(value is None for value in energy_endpoints(metric).values())
    # Old records lacking observation metadata cannot establish enablement.
    assert all(value is None for value in energy_endpoints({"energy": original.to_dict()["energy"]}).values())
    assert engine.capture_state().digest == original.digest
    assert "parameters" not in original.to_dict()["energy"]


@pytest.mark.parametrize("kernel_id", ["threemind.continuous-memory/4", "threemind.continuous-memory/5", "threemind.continuous-memory/5.1"])
@pytest.mark.parametrize("backend", ["reference", "native"])
@pytest.mark.parametrize("energy_model", ["local-field", "global-ledger"])
def test_local_energy_delivery_receipt_reports_actual_acceptance(kernel_id, backend, energy_model):
    LocalConfig = type(resolve_kernel(kernel_id).configuration())
    engine = create_engine(LocalConfig(energy_model=energy_model, energy_simulation_enabled=True,
                                      energy_initial_reserve=0), kernel_id=kernel_id, backend=backend)
    supplier = EnergySupplier(EnergySupplyConfig(enabled=True, rate_per_s=10, interval_us=1000), engine)
    offer = supplier.prepare(engine)
    rows = []
    engine.advance_to(int(offer["time_us"]), rows.append, inputs_only=True)
    receipt = next(row for row in rows if row["kind"] == "energy")
    assert receipt["payload"]["accepted"] == pytest.approx(offer["amount"])
    assert supplier.delivered(receipt)["accepted_total"] == pytest.approx(offer["amount"])
    assert supplier.accepted_total == pytest.approx(engine.metrics()["energy"]["supplied_total"])


@pytest.mark.parametrize("kernel_id", ["threemind.continuous-memory/4", "threemind.continuous-memory/5", "threemind.continuous-memory/5.1"])
@pytest.mark.parametrize("backend", ["reference", "native"])
@pytest.mark.parametrize("enabled", [False, True])
def test_prepared_local_physics_start_pause_and_whole_system_resume(database, kernel_id, backend, enabled):
    # The reported subject uses the /4 defaults, realtime MuJoCo and labeled text.
    spec = default_spec(kernel_id)
    assert spec["environment"] == "mujoco" and spec["clock"] == "realtime"
    spec["text_sensor"]["encoding"] = "labeled-observation"
    spec["config"]["energy_simulation_enabled"] = enabled
    if enabled:
        spec["energy_supply"]["enabled"] = True
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Startup compatibility"}).json()["id"]
        created = client.post(f"/api/v2/projects/{project}/runs", json={
            "name": "Local physics startup", "spec": spec, "execution": {"backend": backend},
            "start_immediately": False,
        })
        assert created.status_code == 201, created.text
        run = created.json()["id"]
        base = f"/api/v2/projects/{project}/runs/{run}"
        assert client.post(base + "/commands", json={"kind": "resume"}).status_code == 200
        # A queued pause still initializes and saves the full host at time zero.
        assert client.post(base + "/commands", json={"kind": "pause"}).status_code == 200
        worker = Worker(database, backend=backend, name="local-startup-test")
        with database.tx(project) as db:
            features = db.execute("SELECT required_features FROM jobs WHERE run_id=%s", (run,)).fetchone()
        worker.capabilities = {"queue": "runtime", "backend": backend,
                               "features": {key: {"state": "available"} for key in features["required_features"]}}
        assert worker.once()
        saved = database.get_run(project, run)
        assert saved["status"] == "paused" and saved["time_us"] == "0", saved["error"]
        assert saved["revision"] == 1 and saved["error"] is None
        sent = client.post(base + "/inputs", json={"request_id": str(uuid4()), "adapter_id": "text-sensor",
                                                  "payload": {"text": "测试", "intensity": 1.0}})
        assert sent.status_code == 202, sent.text
        for target in (40000, 80000):
            advance = client.post(base + "/research/actions", json={
                "request_id": str(uuid4()), "kind": "runtime.advance",
                "expected_revision": saved["revision"], "duration_us": 40000,
            })
            assert advance.status_code == 200, advance.text
            assert worker.once()
            saved = database.get_run(project, run)
            assert saved["status"] == "paused" and saved["time_us"] == str(target), saved["error"]
            checkpoint, image = database.load_checkpoint(project, run)
            assert checkpoint["context"]["environment"] and checkpoint["context"]["body_tools"]
            restored = create_engine(state=image, backend=backend)
            assert restored.capture_state().digest == image.digest
            assert saved["spec"] == spec
            assert client.get(base + "/energy").status_code == 200
        assert saved["metrics"]["nodes"] > 0
