import csv
import io
import json
import subprocess
import sys
from uuid import uuid4

import pytest
from test_api import client_for

from threemind_core import Config, Stimulus
from threemind_lab.configuration import default_spec
from threemind_lab.worker import Worker, birth
from threemind_runtime import create_engine
from threemind_runtime.bus import InputBus
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.store import SQLiteStore


@pytest.mark.parametrize("runtime", ["rust", "python"])
@pytest.mark.parametrize("format", ["json", "tmind"])
def test_independent_modulation_port_pending_and_sqlite_resume(tmp_path, runtime, format):
    from test_runtime_interop import RUNTIME

    engine = create_engine(Config(attention_budget=1))
    for t in (1000, 14003, 20000):
        engine.inject(Stimulus(t, ((1, 0.4), (2, 0.7), (3, 0.7))))
    model = tmp_path / f"input.{format}"
    model.write_bytes(ArtifactCodec.encode(engine.capture_state(), format))
    mod = {
        "source": "explicit-test-port",
        "gain": 0.5,
        "budget_multiplier": 1.0,
        "competition_enabled": True,
        "ttl_us": 15001,
    }
    source = tmp_path / "modulation.jsonl"
    source.write_text(json.dumps({"time_us": "0", **mod}) + "\n", encoding="utf-8")
    prefix = [str(RUNTIME)] if runtime == "rust" else [sys.executable, "-m", "threemind_runtime.cli"]
    store, output = tmp_path / "local.sqlite", tmp_path / "final.tmind"
    result = subprocess.run(
        prefix
        + [
            "--model",
            str(model),
            "--modulation-input",
            str(source),
            "--clock",
            "unbounded",
            "--until-us",
            "12345",
            "--store",
            str(store),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    engine.modulate_input(time_us=0, **mod)
    engine.advance_to(12345)
    assert SQLiteStore(store).load("default")[1].digest == engine.capture_state().digest
    result = subprocess.run(
        prefix
        + ["--store", str(store), "--resume", "--clock", "unbounded", "--until-us", "22000", "--export", str(output)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    engine.advance_to(22000)
    assert ArtifactCodec.decode(output.read_bytes()).digest == engine.capture_state().digest
    assert engine.metrics()["attention"]["evaluated_frames"] == "2"
    assert birth(engine.capture_state()).to_dict()["attention"]["modulators"] == []


def test_input_bus_exposes_actual_selection_without_rewriting_observed_input():
    engine = create_engine(Config(attention_competition_enabled=True, attention_budget=1))
    bus = InputBus(engine)
    raw = Stimulus(0, ((2, 0.8), (1, 0.8), (3, 0.5)))
    bus.schedule(raw, {"envelope_id": "carrier", "frame_index": 0})
    events = []
    engine.advance_to(0, events.append, inputs_only=True)
    delivered = bus.observe(events[0])
    assert events[0]["payload"] == raw.to_dict()
    assert delivered["stimulus"]["channels"] == [[2, 0.8]]
    assert delivered["input_gate"]["raw_channels"] == 3
    assert bus.pending_count() == 0


def spec():
    return default_spec() | {
        "environment": "replay",
        "replay": [],
        "duration_s": 0.045,
        "clock": "unbounded",
        "sample_us": 5000,
        "checkpoint_us": 10000,
        "config": {"attention_budget": 1},
        "structural_readout": {"enabled": False},
        "temporal_readout": {"enabled": False},
    }


def test_worker_input_selection_resume_raw_evidence_and_idempotence(database, monkeypatch):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Input selection"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        runs, requests, envelopes = [], [], []
        frames = [
            Stimulus(0, ((9, 0.4), (2, 0.9), (8, 0.9))).to_dict(),
            Stimulus(11007, ((3, 0.6), (6, 0.4))).to_dict(),
            Stimulus(25007, ((5, 0.8), (4, 0.7))).to_dict(),
        ]
        for name in ("Continuous", "Resumed"):
            created = client.post(f"{root}/runs", json={"name": name, "spec": spec()})
            assert created.status_code == 201, created.text
            run = created.json()["id"]
            runs.append(run)
            url = f"{root}/runs/{run}"
            request = {"request_id": str(uuid4()), "gain": 0.5, "competition_enabled": True, "ttl_us": 15000}
            requests.append(request)
            command = client.post(f"{url}/attention/modulate", json=request)
            assert command.status_code == 202, command.text
            assert client.post(f"{url}/attention/modulate", json=request).json()["id"] == command.json()["id"]
            assert client.post(f"{url}/attention/modulate", json=request | {"gain": 0.4}).status_code == 409
            carrier = client.post(
                f"{url}/inputs",
                json={
                    "request_id": str(uuid4()),
                    "adapter_id": "anonymous-frames",
                    "payload": {"frames": frames},
                    "delay_us": 10000,
                },
            )
            assert carrier.status_code == 202, carrier.text
            envelopes.append(carrier.json()["id"])
        worker = Worker(database)
        assert worker.once()
        save = database.save_checkpoint

        def pause(*args, **kwargs):
            result = save(*args, **kwargs)
            worker.stopping = True
            return result

        with monkeypatch.context() as patch:
            patch.setattr(database, "save_checkpoint", pause)
            assert worker.once()
        url = f"{root}/runs/{runs[1]}"
        assert client.get(url).json()["status"] == "paused"
        worker.stopping = False
        assert client.post(f"{url}/commands", json={"kind": "resume"}).status_code == 200
        assert worker.once()
        left, right = [database.load_checkpoint(project, r)[1] for r in runs]
        assert left.digest == right.digest
        assert client.post(f"{url}/attention/modulate", json=requests[1]).status_code == 202
        assert (
            client.post(f"{url}/attention/modulate", json=requests[1] | {"request_id": str(uuid4())}).status_code == 409
        )
        detail = client.get(f"{url}/inputs/{envelopes[1]}").json()
        for i, frame in enumerate(detail["frames"]):
            assert frame["stimulus"]["channels"] == frames[i]["channels"]
            assert frame["stimulus"]["intensity"] == 1
        assert detail["frames"][0]["input_gate"]["effective_stimulus"]["channels"] == [[2, 0.9]]
        assert detail["frames"][1]["input_gate"]["passed_channels"] == 1
        assert detail["frames"][2]["input_gate"] is None
        evidence = client.get(f"{url}/attention?after=5000&until=20000&limit=2").json()
        assert evidence["more"] and len(evidence["rows"]) == 2
        assert evidence["latest"]["considered_channels"] == "5"
        assert evidence["latest"]["passed_channels"] == "2"
        assert evidence["latest"]["effective"]["sources"] == []
        exported = client.get(f"{url}/attention/export?format=csv&after=5000&until=20000")
        records = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
        assert len(records) == 4 and json.loads(records[-1]["effective"])["competition_enabled"]
        events = client.get(f"{url}/attention/events").json()["rows"]
        assert len(events) == 3
        delivered = next(e for e in events if e["kind"] == "input_modulation_delivered")
        assert delivered["payload"]["status"] == "applied"
        assert len(client.get(f"{url}/attention/events/export").text.splitlines()) == 3
        audit = client.get(f"{url}/inputs/export?records=frames&format=jsonl").text
        assert '"input_gate"' in audit and '"effective_stimulus"' in audit
        foreign = client.post("/api/v2/projects", json={"name": "Other"}).json()["id"]
        for path in ("attention", "attention/export", "attention/events", "attention/events/export"):
            assert client.get(f"/api/v2/projects/{foreign}/runs/{runs[1]}/{path}").status_code == 404


def test_modulation_authorization_closed_port_and_atomic_checkpoint(database, monkeypatch):
    from threemind_lab import auth, inputs

    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Scalar permissions"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        run = client.post(f"{root}/runs", json={"name": "Input gate", "spec": spec()}).json()["id"]
        url = f"{root}/runs/{run}"
        request = {"request_id": str(uuid4()), "gain": 0.5}
        for invalid in ({"gain": True}, {"competition_enabled": 1}, {"ttl_us": 0}, {"node_id": 1}):
            assert client.post(f"{url}/attention/modulate", json=request | invalid).status_code == 422
        e = create_engine(Config(attention_competition_enabled=True, attention_budget=0))
        e.inject(Stimulus(0, ((1, 0.5),)))
        e.advance_to(0)

        def fail(*args, **kwargs):
            raise ValueError("injected selection commit failure")

        with monkeypatch.context() as patch:
            patch.setattr(inputs, "commit_inputs", fail)
            with pytest.raises(ValueError, match="injected"):
                database.save_checkpoint(
                    project,
                    run,
                    e.capture_state(),
                    expected_revision=0,
                    observations=[e.metrics()],
                    input_changes={"frames": []},
                )
        assert client.get(f"{url}/attention").json()["latest"] is None
        database.save_checkpoint(project, run, e.capture_state(), expected_revision=0, status="paused")
        assert client.get(f"{url}/attention").json()["latest"]["suppressed_channels"] == "1"
        assert client.post(f"{url}/commands", json={"kind": "close_inputs"}).status_code == 200
        assert client.post(f"{url}/attention/modulate", json=request).status_code == 409
    viewer = auth.create_user(database, "scalar-viewer", "isolated scalar viewer secret")
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (project, viewer["id"]))
    with client_for(database, "server") as client:
        login = client.post(
            "/api/v2/login", json={"username": "scalar-viewer", "password": "isolated scalar viewer secret"}
        )
        assert client.get(f"{url}/attention").status_code == 200
        assert (
            client.post(
                f"{url}/attention/modulate", json=request, headers={"X-CSRF-Token": login.json()["csrf"]}
            ).status_code
            == 403
        )
