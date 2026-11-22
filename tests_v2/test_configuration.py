from dataclasses import asdict, fields, replace

import pytest

from threemind_core import Config, Engine, Stimulus
from threemind_lab.configuration import catalogue, default_spec, validate_configuration
from threemind_runtime import create_engine


def test_catalogue_covers_every_executable_parameter_and_rejects_invalid_contracts():
    catalog = catalogue()
    from threemind_kernels.registry import resolve_kernel

    for kernel in catalog["kernels"]:
        visible = [f for f in catalog["fields"] if not f.get("kernels") or kernel["kernel_id"] in f["kernels"]]
        retired = (
            {"propagation_limit", "edge_adaptation_limit"}
            if kernel["kernel_id"] in ("threemind.continuous-memory/3", "threemind.continuous-memory/3.1")
            else set()
        )
        if kernel["kernel_id"] in (
            "threemind.continuous-memory/4", "threemind.continuous-memory/5", "threemind.continuous-memory/5.1",
            "threemind.continuous-memory/5.2",
            "threemind.continuous-memory/5.3", "threemind.continuous-memory/6.0", "threemind.continuous-memory/6.1", "threemind.continuous-memory/6.2", "threemind.continuous-memory/6.3", "threemind.experimental-weight-decay/1",
        ):
            retired = {
                "propagation_limit",
                "edge_adaptation_limit",
                "homeostasis_enabled",
                "target_total_activation",
                "spatial_competition_rate",
                "attention_competition_enabled",
                "attention_budget",
                "edge_birth_policy",
                "association_window_us",
                "step_us",
            }
        assert {f["path"][7:] for f in visible if f["path"].startswith("config.")} == {
            f.name for f in fields(resolve_kernel(kernel["kernel_id"]).configuration()) if f.name not in retired
        }
        for key in retired - {"spatial_competition_rate", "target_total_activation", "edge_birth_policy"}:
            assert not validate_configuration(default_spec() | {"kernel_id": kernel["kernel_id"], "config": {key: 1}})[
                "valid"
            ]
    assert validate_configuration(default_spec())["valid"]
    for path, value in (("trace", "false"), ("sample_us", -1), ("duration_s", 0.0000001)):
        assert not validate_configuration(default_spec() | {path: value})["valid"]
    for key, value in (("unknown", 2), ("activation_tau", 0), ("plasticity", 1), ("activation_floor", 1)):
        assert not validate_configuration(default_spec() | {"config": {key: value}})["valid"]
    for node_id in (-1, 2**32, True):
        assert not validate_configuration(default_spec() | {"intervention": {"nodes": [node_id]}})["valid"]
    assert validate_configuration(default_spec() | {"intervention": {"edges": [[0, 2**32 - 1]]}})["valid"]
    original = default_spec()
    changed = original | {"config": original["config"] | {"propagation_interval_us": 5000, "seed": 7}}
    result = validate_configuration(changed, current=original)
    assert {e["path"] for e in result["errors"]} == {"config.propagation_interval_us", "config.seed"}
    assert not validate_configuration(original | {"seed": 1}, current=original)["valid"]
    frozen = original | {"study_id": "frozen", "condition": "A", "block_seed": 1}
    assert not validate_configuration(frozen | {"trace": True}, current=frozen)["valid"]
    assert validate_configuration(original, current=original, elapsed_us=60_000_000)["valid"]
    assert not validate_configuration(original | {"duration_s": 1}, current=original, elapsed_us=60_000_000)["valid"]


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_reconfiguration_materializes_old_decay_and_preserves_inflight_events(backend):
    config = Config(step_us=10000, delay_us=40000, plasticity=False)
    engine = create_engine(config, backend=backend)
    engine.inject(Stimulus(0, ((1, 0.8), (2, 0.5))))
    engine.advance_to(15001)
    before = engine.capture_state()
    engine.reconfigure(config)
    assert engine.capture_state().digest == before.digest  # identical settings introduce no solver boundary
    expected = Engine(state=before)
    expected._relax(expected.time_us)
    updated = replace(config, activation_tau=2, delay_us=90000)
    engine.reconfigure(updated)
    state = engine.capture_state().to_dict()
    assert state["state_time_us"] == state["time_us"] == "15001"
    assert state["next_step_us"] == before.to_dict()["next_step_us"]
    assert state["queue"] == before.to_dict()["queue"]
    assert state["nodes"][0]["activation"] == pytest.approx(expected.nodes[1].activation, abs=1e-14)
    with pytest.raises(ValueError, match="immutable"):
        engine.reconfigure(replace(updated, step_us=20000))
    saved = engine.capture_state()
    resumed = create_engine(state=saved, backend=backend)
    engine.advance_to(135007)
    resumed.advance_to(135007)
    assert engine.capture_state().digest == resumed.capture_state().digest


def test_paused_configuration_is_atomic_validated_audited_and_used_on_resume(database):
    from fastapi.testclient import TestClient

    from threemind_lab.api import create_app
    from threemind_lab.config import Settings
    from threemind_lab.worker import Worker

    with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
        project = client.post("/api/v2/projects", json={"name": "Configuration acceptance"}).json()["id"]
        base = f"/api/v2/projects/{project}"
        # The creation endpoint must validate the submitted types before coercion too.
        rejected = client.post(f"{base}/runs", json={"name": "Invalid boolean", "spec": {"trace": "false"}})
        assert rejected.status_code == 422
        assert database.list_runs(project) == []
        spec = default_spec() | {"environment": "manual", "clock": "unbounded", "duration_s": 0.06}
        run = database.create_run(project, "Paused subject", spec)
        engine = create_engine(spec["config"], kernel_id=spec["kernel_id"])
        engine.inject(Stimulus(0, ((1, 0.7), (2, 0.5))))
        engine.advance_to(15001)
        cp = database.save_checkpoint(
            project,
            run["id"],
            engine.capture_state(),
            expected_revision=0,
            status="paused",
            context={"initialized": True, "start_us": "0", "end_us": "60000"},
        )
        url = f"{base}/runs/{run['id']}/configuration"
        invalid = spec | {"config": asdict(replace(Config(), step_us=1))}
        body = {"name": "Updated subject", "expected_revision": 1, "spec": invalid}
        checked = client.post(f"{base}/configuration/validate", json={"run_id": str(run["id"]), "spec": invalid})
        assert not checked.json()["valid"]
        assert client.put(url, json=body).status_code == 422  # no earlier validation is required
        assert database.get_run(project, run["id"])["revision"] == 1
        spec["config"]["propagation_rate"] = 0.0
        body["spec"] = spec
        response = client.put(url, json=body)
        assert response.status_code == 200, response.text
        assert response.json()["revision"] == 2 and response.json()["name"] == "Updated subject"
        assert client.put(url, json=body).status_code == 409
        current_cp, image = database.load_checkpoint(project, run["id"])
        assert current_cp["context"]["protocol"]["config"]["propagation_rate"] == 0
        assert image.to_dict()["config"]["propagation_rate"] == 0
        _, old_image = database.load_checkpoint(project, run["id"], cp["id"])
        assert old_image.to_dict()["config"]["propagation_rate"] == Config().propagation_rate
        history = client.get(f"{base}/runs/{run['id']}/events?kind=configuration_changed").json()
        assert len(history) == 1 and history[0]["payload"]["applied_at_us"] == "15001"
        assert history[0]["payload"]["previous_state_hash"] == old_image.digest
        # The actual worker resumes the changed model, not just the new form values.
        assert client.post(f"{base}/runs/{run['id']}/commands", json={"kind": "resume"}).status_code == 200
        expected = create_engine(state=image)
        expected.advance_to(60000)
        assert Worker(database).once()
        final_cp, final_image = database.load_checkpoint(project, run["id"])
        assert final_image.digest == expected.capture_state().digest
        assert final_cp["context"]["protocol"]["config"]["propagation_rate"] == 0
        # A historical checkpoint retains its own parameters even after the source was edited.
        forked = client.post(
            f"{base}/runs/{run['id']}/forks",
            json={"name": "Historical configuration", "checkpoint_id": str(cp["id"])},
        )
        assert forked.status_code == 201, forked.text
        assert forked.json()["spec"]["config"]["propagation_rate"] == Config().propagation_rate
        _, fork_image = database.load_checkpoint(project, forked.json()["id"])
        assert fork_image.digest == old_image.digest
        # Defaults are independently versioned and never rewrite existing subjects.
        defaults_url = f"{base}/configuration/defaults"
        assert client.get(defaults_url).json()["revision"] == 0
        saved = client.put(defaults_url, json={"spec": spec, "expected_revision": 0})
        assert saved.status_code == 200 and saved.json()["revision"] == 1
        assert client.put(defaults_url, json={"spec": spec, "expected_revision": 0}).status_code == 409
        assert database.get_run(project, run["id"])["state_hash"] == final_image.digest


def test_configuration_project_and_viewer_authorization(database):
    from fastapi.testclient import TestClient

    from threemind_lab import auth
    from threemind_lab.api import create_app
    from threemind_lab.config import Settings

    owner = auth.create_user(database, "config-owner", "long password for owner")
    viewer = auth.create_user(database, "config-viewer", "long password for viewer")
    project = database.create_project(owner, "Private configuration")["id"]
    run = database.create_run(project, "Private", default_spec())
    with TestClient(create_app(Settings(database_url=database.test_url, mode="server"), database)) as client:
        login = client.post("/api/v2/login", json={"username": "config-viewer", "password": "long password for viewer"})
        headers = {"X-CSRF-Token": login.json()["csrf"]}
        base = f"/api/v2/projects/{project}"
        assert client.get(f"{base}/configuration/defaults").status_code == 403
        assert (
            client.post(
                f"{base}/configuration/validate",
                json={"spec": default_spec(), "run_id": str(run["id"])},
                headers=headers,
            ).status_code
            == 403
        )
        with database.tx() as db:
            db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (project, viewer["id"]))
        assert client.get(f"{base}/configuration/defaults").status_code == 200
        assert (
            client.put(
                f"{base}/configuration/defaults", json={"spec": default_spec(), "expected_revision": 0}, headers=headers
            ).status_code
            == 403
        )
        assert (
            client.put(
                f"{base}/runs/{run['id']}/configuration",
                json={"name": "Denied", "spec": default_spec(), "expected_revision": 0},
                headers=headers,
            ).status_code
            == 403
        )
