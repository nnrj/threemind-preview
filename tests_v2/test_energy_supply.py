import csv
import io
import json
from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

import pytest
from test_api import client_for

from threemind_core import Config, Stimulus
from threemind_lab.configuration import default_spec
from threemind_lab.worker import Worker
from threemind_runtime import create_engine
from threemind_runtime.energy_supply import EnergySupplier, EnergySupplyConfig


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_external_reservoir_counts_acceptance_and_restores_promised_events(backend):
    e = create_engine(
        Config(energy_simulation_enabled=True, energy_direct_cost=1, inhibition=False, propagation_rate=0),
        backend=backend,
    )
    cfg = EnergySupplyConfig(enabled=True, rate_per_s=1, interval_us=1000, total_supply_limit=0.0015)
    p = EnergySupplier(cfg, e)
    offer = p.prepare(e)
    assert offer["time_us"] == "1000" and not e.activations()
    captured = p.capture()
    captured["pending"]["amount"] = 0.7
    assert p.capture()["pending"]["amount"] == 0.001
    with pytest.raises(ValueError, match="differs"):
        EnergySupplier(cfg, e, captured)
    p = EnergySupplier(cfg, e, p.capture())
    records = []

    def observe(event):
        if event["kind"] == "energy":
            records.append(p.delivered(event))

    e.advance_to(1000, observe, inputs_only=True)
    assert p.accepted_total == 0 and p.offered_total == 0.001  # capacity is already full
    e.inject(Stimulus(1001, ((1, 0.7),)))
    e.advance_to(1001)
    p.prepare(e)
    # Disabling the adapter does not revoke the previously promised supply.
    p = EnergySupplier(replace(cfg, enabled=False), e, p.capture())
    assert p.prepare(e) is None and p.deadline == 2000
    e.advance_to(2000, observe, inputs_only=True)
    assert p.accepted_total == 0.001 and p.prepare(e) is None
    p = EnergySupplier(cfg, e, p.capture())
    assert p.prepare(e, source_enabled=False) is None
    assert p.prepare(e)["amount"] == pytest.approx(0.0005)
    e.advance_to(p.deadline, observe, inputs_only=True)
    assert p.accepted_total == pytest.approx(0.0015) and p.prepare(e) is None
    assert p.sequence == 3 and len(records) == 3
    assert e.metrics()["energy"]["supplied_total"] == p.accepted_total


def test_provider_rejects_invalid_configuration_and_corrupt_pending_state():
    for config in (
        {"enabled": 1},
        {"interval_us": 0},
        {"rate_per_s": True},
        {"total_supply_limit": -1},
        {"rate_per_s": 1e12, "interval_us": 10000000},
    ):
        with pytest.raises(ValueError):
            EnergySupplyConfig(**config)
    e = create_engine(Config(energy_simulation_enabled=True))
    p = EnergySupplier(EnergySupplyConfig(enabled=True), e)
    p.prepare(e)
    for changes in (
        {"pending": {}},
        {"sequence": True},
        {"accepted_total": 99},
        {"pending": p.pending | {"sequence": False}},
    ):
        with pytest.raises(ValueError):
            EnergySupplier(p.config, e, p.capture() | changes)


def test_energy_statistics_keep_disabled_and_saturated_controls_missing():
    from threemind_lab.measurements import energy_endpoints
    from threemind_lab.statistics import compare_pairs, summarize

    e = create_engine(Config(energy_simulation_enabled=True, energy_initial_reserve=0.1))
    e.inject(Stimulus(0, ((1, 0.8),)))
    e.advance_to(10000)
    enabled = e.metrics()
    disabled = deepcopy(enabled)
    disabled["energy"]["parameters"]["energy_simulation_enabled"] = False
    saturated = deepcopy(enabled)
    saturated["energy"]["counter_overflowed"] = True
    assert energy_endpoints(enabled)["energy_consumed"] > 0
    for missing in (disabled, saturated, {}):
        assert all(value is None for value in energy_endpoints(missing).values())
    results = compare_pairs([{"control": summarize([enabled]), "treatment": summarize([disabled])}], resamples=10)
    record = next(r for r in results["metrics"] if r["metric"] == "energy_consumed")
    assert record["n"] == 0 and record["missing_pairs"] == 1 and record["difference"] is None


def test_energy_study_warmup_supply_ablation_statistics_and_early_death(database):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Energy paired experiment"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        spec = run_spec()
        protocol = {
            "name": "Explicit energy conditions",
            "warmup_s": 0.015,
            "seeds": [11, 23],
            "base": spec | {"replay": []},  # Independent blocks below are the actual paired input.
            "replay_blocks": {
                str(seed): [Stimulus(i * 11007, ((seed, 0.7), (seed + 1, 0.5))).to_dict() for i in range(7)]
                for seed in (11, 23)
            },
            "arms": [
                {"name": "supplied"},
                {"name": "withdrawn", "energy_supply": {"enabled": False}},
                {"name": "disabled", "config_patch": {"energy_simulation_enabled": False}},
            ],
        }
        created = client.post(f"{root}/studies", json=protocol)
        assert created.status_code == 202, created.text
        study = created.json()["params"]["study_id"]
        worker = Worker(database)
        assert worker.once()
        arms = client.get(f"{root}/runs?study_id={study}").json()
        assert len(arms) == 6
        frozen = arms[0]["id"]
        assert (
            client.post(
                f"{root}/runs/{frozen}/energy/supply", json={"request_id": str(uuid4()), "amount": 0.1}
            ).status_code
            == 409
        )
        for _ in arms:
            assert worker.once()
        arms = client.get(f"{root}/runs?study_id={study}").json()
        assert all(r["status"] == "completed" for r in arms), arms
        for r in arms:
            cp, image = database.load_checkpoint(project, r["id"])
            amount = cp["context"]["energy_supplier"]["accepted_total"]
            expected = {"supplied": 0.03, "withdrawn": 0.021, "disabled": 0.014}[r["spec"]["condition"]]
            assert amount == pytest.approx(expected)
            assert image.to_dict()["energy"]["supplied_total"] == pytest.approx(expected)
        chart = client.get(f"{root}/studies/{study}/trajectories?metric=energy_reserve&buckets=10")
        assert chart.status_code == 200, chart.text
        for series in chart.json()["series"]:
            if series["name"] == "disabled":
                assert all(r["energy_reserve"] is None and r["n"] == 0 for r in series["rows"])
            else:
                assert any(r["n"] == 2 for r in series["rows"])
        analysis = client.post(
            f"{root}/analyses", json={"study_id": study, "control": "supplied", "treatment": "withdrawn"}
        )
        assert worker.once()
        job = next(j for j in client.get(f"{root}/jobs").json() if j["id"] == analysis.json()["id"])
        assert job["status"] == "done", job.get("error")
        difference = next(m for m in job["result"]["analysis"]["metrics"] if m["metric"] == "energy_supplied")
        assert difference["n"] == 2 and difference["difference"] == pytest.approx(-0.009)
        dying = deepcopy(protocol)
        dying["name"] = "Death during warmup"
        dying["warmup_s"] = 0.03
        dying["base"]["config"].update(
            energy_initial_reserve=0.001,
            energy_starvation_damage_enabled=True,
            activation_tau=0.0001,
            quiescence_death_us=7001,
        )
        dying["base"]["energy_supply"] = {"enabled": False}
        ended = client.post(f"{root}/studies", json=dying)
        assert ended.status_code == 202, ended.text
        assert worker.once()
        failed = next(j for j in client.get(f"{root}/jobs").json() if j["id"] == ended.json()["id"])
        assert failed["status"] == "failed" and "已死亡" in failed["error"]
        assert client.get(f"{root}/runs?study_id={ended.json()['params']['study_id']}").json() == []


def run_spec():
    return default_spec() | {
        "environment": "replay",
        "clock": "unbounded",
        "duration_s": 0.09,
        "sample_us": 10000,
        "checkpoint_us": 30000,
        "config": {"energy_simulation_enabled": True, "energy_initial_reserve": 0.05, "energy_direct_cost": 0.2},
        "replay": [Stimulus(i * 11007, ((1, 0.7), (2, 0.6))).to_dict() for i in range(5)],
        "energy_supply": {"enabled": True, "rate_per_s": 1, "interval_us": 7000, "total_supply_limit": 0.03},
        "structural_readout": {"enabled": False},
        "temporal_readout": {"enabled": False},
    }


def test_energy_worker_resume_idempotence_and_committed_evidence(database, monkeypatch):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Energy supply acceptance"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        ids = []
        for name in ("Continuous", "Resumed"):
            created = client.post(f"{root}/runs", json={"name": name, "spec": run_spec()})
            assert created.status_code == 201, created.text
            ids.append(created.json()["id"])
        worker = Worker(database)
        requests = []
        for run in ids:
            req = {"request_id": str(uuid4()), "amount": 0.01, "delay_us": 4000}
            requests.append(req)
            command = client.post(f"{root}/runs/{run}/energy/supply", json=req)
            assert command.status_code == 202, command.text
            assert client.post(f"{root}/runs/{run}/energy/supply", json=req).json()["id"] == command.json()["id"]
            assert client.post(f"{root}/runs/{run}/energy/supply", json=req | {"amount": 0.02}).status_code == 409
        assert worker.once()
        save = database.save_checkpoint

        def stop_after_commit(*args, **kwargs):
            result = save(*args, **kwargs)
            worker.stopping = True
            return result

        with monkeypatch.context() as patch:
            patch.setattr(database, "save_checkpoint", stop_after_commit)
            assert worker.once()
        url = f"{root}/runs/{ids[1]}"
        paused = client.get(url).json()
        assert paused["status"] == "paused", paused.get("error")
        cp, before = database.load_checkpoint(project, ids[1])
        assert cp["context"]["energy_supplier"]["sequence"] > 0
        invalid = deepcopy(paused["spec"])
        invalid["config"]["energy_initial_reserve"] = 0.6
        invalid_body = {"name": "Cannot refill", "expected_revision": paused["revision"], "spec": invalid}
        assert client.put(f"{url}/configuration", json=invalid_body).status_code == 422
        worker.stopping = False
        assert client.post(f"{url}/commands", json={"kind": "resume"}).status_code == 200
        assert worker.once()
        left, right = [database.load_checkpoint(project, run) for run in ids]
        assert left[1].digest == right[1].digest
        assert left[0]["context"]["energy_supplier"] == right[0]["context"]["energy_supplier"]
        assert right[0]["context"]["energy_supplier"]["accepted_total"] == pytest.approx(0.03)
        assert before.digest != right[1].digest
        # A lost successful response remains retriable after the run ended.
        assert client.post(f"{url}/energy/supply", json=requests[1]).status_code == 202
        assert client.post(f"{url}/energy/supply", json=requests[1] | {"request_id": str(uuid4())}).status_code == 409
        page = client.get(f"{url}/energy?after=10000&until=50000&limit=2").json()
        assert [r["time_us"] for r in page["rows"]] == ["10000", "20000"] and page["more"]
        assert page["latest"]["supplied_total"] == pytest.approx(0.04)
        assert page["provider"]["accepted_total"] == pytest.approx(0.03)
        assert page["latest"]["reserve"] == right[1].to_dict()["energy"]["reserve"]
        raw = client.get(f"{url}/energy/export?after=10000&until=50000")
        lines = [json.loads(line) for line in raw.text.splitlines()]
        assert len(lines) == 6 and lines[1:3] == page["rows"]
        assert lines[0]["selection"]["state_hash"] == right[1].digest
        csv_data = client.get(f"{url}/energy/export?after=10000&until=50000&format=csv")
        records = list(csv.DictReader(io.StringIO(csv_data.content.decode("utf-8-sig"))))
        assert len(records) == 5 and float(records[-1]["supplied_total"]) == lines[-1]["energy"]["supplied_total"]
        assert all(r["irreversible_energy_death_enabled"] == r["energy_starvation_death_us"] == "" for r in records)
        assert all(r["energy_starvation_damage_enabled"] == "False" for r in records)
        journal = client.get(f"{url}/energy/events/export")
        events = [json.loads(line) for line in journal.text.splitlines()][1:]
        deliveries = [e for e in events if e["kind"] == "energy_delivered"]
        assert len(deliveries) == 6 and sum(e["payload"]["accepted"] for e in deliveries) == pytest.approx(0.04)
        assert sum(e["payload"]["source"] == "manual-energy-port" for e in deliveries) == 1
        assert client.get(f"{url}/energy?after=10&until=9").status_code == 422
        foreign = client.post("/api/v2/projects", json={"name": "Unrelated"}).json()["id"]
        for suffix in ("energy", "energy/export", "energy/events/export"):
            assert client.get(f"/api/v2/projects/{foreign}/runs/{ids[1]}/{suffix}").status_code == 404


def test_energy_supply_access_source_closure_and_transaction_rollback(database, monkeypatch):
    from threemind_lab import auth
    from threemind_lab import inputs as storage

    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Energy permissions"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        created = client.post(f"{root}/runs", json={"name": "Explicit source", "spec": run_spec()}).json()
        run, url = created["id"], f"{root}/runs/{created['id']}"
        request = {"request_id": str(uuid4()), "amount": 0.01}
        assert client.post(f"{url}/energy/supply", json=request | {"amount": True}).status_code == 422
        engine = create_engine(Config(**run_spec()["config"]))
        engine.supply_energy(0.01, time_us=1000)
        events = []
        engine.advance_to(
            1000,
            lambda e: events.append(
                {
                    "key": f"energy:{e['event_id']}",
                    "time_us": e["time_us"],
                    "kind": "energy_delivered",
                    "payload": e["payload"],
                }
            ),
            inputs_only=True,
        )
        commit = storage.commit_inputs

        def fail(*args, **kwargs):
            commit(*args, **kwargs)
            raise ValueError("injected energy checkpoint failure")

        with monkeypatch.context() as patch:
            patch.setattr(storage, "commit_inputs", fail)
            with pytest.raises(ValueError, match="injected"):
                database.save_checkpoint(
                    project,
                    run,
                    engine.capture_state(),
                    expected_revision=0,
                    events=events,
                    input_changes={"frames": []},
                )
        assert database.get_run(project, run)["revision"] == 0
        assert client.get(f"{url}/events?kind=energy_delivered").json() == []
        database.save_checkpoint(
            project, run, engine.capture_state(), expected_revision=0, events=events, status="paused"
        )
        assert client.get(f"{url}/energy").json()["latest"]["supplied_total"] == 0.01
        assert client.post(f"{url}/commands", json={"kind": "close_inputs"}).status_code == 200
        assert client.post(f"{url}/energy/supply", json=request).status_code == 409
        disabled = client.post(f"{root}/runs", json={"name": "Off", "spec": default_spec()}).json()["id"]
        assert client.post(f"{root}/runs/{disabled}/energy/supply", json=request).status_code == 409
    viewer = auth.create_user(database, "energy-viewer", "long isolated energy viewer secret")
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (project, viewer["id"]))
    with client_for(database, "server") as client:
        login = client.post(
            "/api/v2/login", json={"username": "energy-viewer", "password": "long isolated energy viewer secret"}
        )
        assert client.get(f"{url}/energy").status_code == 200
        assert (
            client.post(
                f"{url}/energy/supply", json=request, headers={"X-CSRF-Token": login.json()["csrf"]}
            ).status_code
            == 403
        )
