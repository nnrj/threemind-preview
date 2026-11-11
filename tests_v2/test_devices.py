import json
from copy import deepcopy

import pytest
from lease_helpers import claim_as
from starlette.websockets import WebSocketDisconnect
from test_api import client_for

from threemind_core import Config
from threemind_lab import auth, inputs
from threemind_lab.input_cycle import RuntimeInputs
from threemind_lab.protocols import RunSpec
from threemind_lab.worker import Worker
from threemind_runtime import create_engine
from threemind_runtime.network import PROTOCOL, receptor


def setup(client, config=None, spec=None):
    project = client.post("/api/v2/projects", json={"name": "Network evidence"}).json()["id"]
    run = client.post(
        f"/api/v2/projects/{project}/runs",
        json={
            "name": "Device model",
            "spec": spec
            or {
                "environment": "manual",
                "clock": "unbounded",
                "duration_s": 0.08,
                "checkpoint_us": 10000,
            },
        },
    ).json()["id"]
    url = f"/api/v2/projects/{project}/runs/{run}"
    result = client.post(url + "/devices", json={"name": "Anonymous probe", "configuration": config or {}})
    assert result.status_code == 201, result.text
    device = result.json()["device"]["id"]
    return project, run, url, f"/api/v2/network/{project}/{run}/{device}", result.json()


def connect(client, root, token, mode="simulation", session_id=None):
    return client.post(
        root + "/sessions",
        headers={"Authorization": "Bearer " + token},
        json={
            "protocol": PROTOCOL,
            "type": "hello",
            "source_clock": {"mode": mode},
            **({"session_id": session_id} if session_id else {}),
        },
    )


def packet(seq=0, when=1000, capture=0):
    return {
        "protocol": PROTOCOL,
        "type": "input",
        "sequence": str(seq),
        "capture_us": str(capture),
        "frames": [{"time_us": str(when), "channels": [[12, -0.7], [15, 0.4]]}],
    }


def test_device_admission_delivery_idempotency_ports_and_exact_history(database):
    with client_for(database) as client:
        project, run, url, root, binding = setup(client, {"modulation": True, "output_nodes": 1, "output_edges": 0})
        token, device = binding["token"], binding["device"]["id"]
        headers = {"Authorization": "Bearer " + token}
        assert "token_hash" not in client.get(url + "/devices").text
        assert token not in client.get(url + "/devices").text
        assert client.get(url + "/sensory").json()["network_devices"][0]["id"] == device
        with database.tx(project) as db:
            saved = db.execute("SELECT token_hash FROM device_bindings WHERE id=%s", (device,)).fetchone()
            assert token not in saved["token_hash"] and len(saved["token_hash"]) == 64
        hello = connect(client, root, token)
        assert hello.status_code == 201, hello.text
        session = hello.json()["session"]["id"]
        endpoint = f"{root}/sessions/{session}"
        original = packet()
        result = client.post(endpoint + "/packets", headers=headers, json=original)
        assert result.status_code == 202, result.text
        receipt = result.json()
        assert client.post(endpoint + "/packets", headers=headers, json=original).json() == receipt
        assert client.post(endpoint + "/packets", headers=headers, json=packet(2)).status_code == 409
        assert client.post(endpoint + "/packets", headers=headers, json=packet(0, 2000)).status_code == 409
        assert (
            client.post(
                endpoint + "/packets",
                headers=headers,
                json={"protocol": PROTOCOL, "type": "energy", "sequence": "1", "value": {"amount": 5}},
            ).status_code
            == 403
        )
        modulation = {
            "protocol": PROTOCOL,
            "type": "modulation",
            "sequence": "1",
            "value": {"gain": 0.5},
            "delay_us": "0",
        }
        assert client.post(endpoint + "/packets", headers=headers, json=modulation).status_code == 202
        assert Worker(database).once()
        state = client.get(url).json()
        assert state["status"] == "completed", state["error"]
        result = client.get(endpoint + "/receipts?limit=1", headers=headers).json()
        assert result["more"] and result["rows"][0]["delivery_status"] == "completed"
        second = client.get(endpoint + "/receipts?after=0&limit=1", headers=headers).json()["rows"][0]
        assert second["port_outcome"]["status"] == "scheduled"
        assert second["port_outcome"]["source"] == f"remote:{device}"
        evidence = client.get(endpoint + "/evidence/" + receipt["envelope_id"], headers=headers).json()
        assert evidence["envelope"]["payload"]["remote"] == original
        assert evidence["envelope"]["source"] == f"remote:{device}"
        frame = evidence["frames"][0]
        assert frame["delivered_time_us"] == frame["scheduled_time_us"] == "1000"
        assert frame["stimulus"]["channels"][0] == [receptor(20260724, device, 12, negative=True), 0.7]
        exported = client.get(url + f"/inputs/export?records=envelopes&format=jsonl&source=remote:{device}").text
        assert json.loads(exported.splitlines()[1])["payload"]["remote"] == original
        output = client.get(endpoint + "/output?after_revision=0", headers=headers).json()
        assert not output["complete"] and len(output["nodes"]) == 1 and output["total_nodes"] == 2
        assert output["state_hash"] == state["state_hash"] and output["skipped_revisions"] > 0
        assert client.get(endpoint + "/observations?limit=1", headers=headers).json()["more"]
        assert len(client.get(url + "/inputs").json()["rows"]) == 1
        # A raw credential never becomes a platform session or reaches model artifacts.
        assert token not in json.dumps(database.load_checkpoint(project, run)[1].to_dict())
        assert connect(client, root, token, session_id=session).json()["session"]["next_sequence"] == "2"


def test_device_limits_permissions_revocation_and_websocket_reconnect(database):
    with client_for(database) as client:
        project, _run, url, root, binding = setup(client, {"maximum_channels": 1})
        token, device = binding["token"], binding["device"]["id"]
        assert connect(client, root, "bad").status_code == 403
        assert connect(client, root, token, mode="device").status_code == 409
        foreign = client.post("/api/v2/projects", json={"name": "Foreign"}).json()["id"]
        assert connect(client, root.replace(project, foreign), token).status_code == 404
        for suffix, headers in (("?token=secret", {}), ("", {"Origin": "https://foreign.invalid"})):
            with pytest.raises(WebSocketDisconnect), client.websocket_connect(root + "/ws" + suffix, headers=headers):
                pass
        hello = {"protocol": PROTOCOL, "type": "hello", "token": token, "source_clock": {"mode": "simulation"}}
        with client.websocket_connect(root + "/ws") as ws:
            ws.send_json(hello)
            session = ws.receive_json()["session"]["id"]
            ws.send_json(packet())
            assert ws.receive_json()["type"] == "error"
            valid = packet()
            valid["frames"][0]["channels"] = [[12, -0.7]]
            ws.send_json(valid)
            receipt = ws.receive_json()
            assert receipt["status"] == "accepted"
        with client.websocket_connect(root + "/ws") as ws:
            ws.send_json(hello | {"session_id": session})
            assert ws.receive_json()["session"]["next_sequence"] == "1"
            ws.send_json(valid)
            assert ws.receive_json() == receipt
            ws.send_json({"protocol": PROTOCOL, "type": "output"})
            assert ws.receive_json()["type"] == "output"
            ws.send_json({"protocol": PROTOCOL, "type": "subscribe", "interval_ms": 100})
            assert ws.receive_json()["enabled"]
            assert ws.receive_json()["type"] == "output"
            ws.send_json({"protocol": PROTOCOL, "type": "unsubscribe"})
            assert not ws.receive_json()["enabled"]
            rotated = client.post(url + f"/devices/{device}/rotate").json()
            ws.send_json(valid)
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()
        assert connect(client, root, token).status_code == 403
        assert connect(client, root, rotated["token"], session_id=session).status_code == 409
        assert connect(client, root, rotated["token"]).status_code == 201
        with database.tx() as db:
            db.execute("UPDATE users SET enabled=false WHERE id=%s", (binding["device"]["issuer_id"],))
        assert connect(client, root, rotated["token"]).status_code == 403
    viewer = auth.create_user(database, "network-viewer", "network isolated viewer secret")
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (project, viewer["id"]))
    with client_for(database, "server") as client:
        login = client.post(
            "/api/v2/login", json={"username": "network-viewer", "password": "network isolated viewer secret"}
        )
        assert (
            client.post(
                url + "/devices", json={"name": "Denied"}, headers={"X-CSRF-Token": login.json()["csrf"]}
            ).status_code
            == 403
        )
        assert client.get(url + "/devices").status_code == 200


def test_device_clock_checkpoint_rollback_restore_pause_and_late_input(database, monkeypatch):
    spec = {"environment": "manual", "clock": "realtime", "duration_s": 10}
    with client_for(database) as client:
        project, run, _url, root, binding = setup(client, spec=spec)
        with database.tx(project) as db:
            db.execute("UPDATE runs SET status='running' WHERE id=%s", (run,))
        headers = {"Authorization": "Bearer " + binding["token"]}
        session = connect(client, root, binding["token"], "device").json()["session"]["id"]
        endpoint = root + f"/sessions/{session}"
        assert client.post(endpoint + "/packets", json=packet(capture=5), headers=headers).status_code == 422
        result = client.post(endpoint + "/packets", json=packet(when=0), headers=headers)
        assert result.status_code == 202, result.text
        engine = create_engine(Config())
        host = RuntimeInputs(database, project, run, engine, RunSpec(**spec), {}, 0)
        assert host.accepted(result.json()["envelope_id"])["scheduled_start_us"] == "500000"
        changes = deepcopy(host.changes)
        context = {"input_bus_run_id": run, "input_bus": host.bus.capture(), "device_streams": host.device_streams}
        real = inputs.commit_inputs

        def fail(*args, **kwargs):
            real(*args, **kwargs)
            raise ValueError("injected device rollback")

        with monkeypatch.context() as patch:
            patch.setattr(inputs, "commit_inputs", fail)
            with pytest.raises(ValueError, match="rollback"):
                database.save_checkpoint(
                    project, run, engine.capture_state(), expected_revision=0, context=context, input_changes=changes
                )
        with database.tx(project) as db:
            assert (
                db.execute("SELECT origin_sim_us FROM device_sessions WHERE id=%s", (session,)).fetchone()[
                    "origin_sim_us"
                ]
                is None
            )
            assert not db.execute("SELECT 1 FROM input_frames WHERE run_id=%s", (run,)).fetchone()
        database.save_checkpoint(
            project,
            run,
            engine.capture_state(),
            expected_revision=0,
            context=context,
            input_changes=changes,
            status="running",
        )
        restored = RuntimeInputs(database, project, run, engine, RunSpec(**spec), context, 0)
        assert restored.device_streams == host.device_streams
        result = client.post(endpoint + "/packets", json=packet(1, when=0, capture=20000), headers=headers)
        assert result.status_code == 202, result.text
        assert restored.accepted(result.json()["envelope_id"])["scheduled_start_us"] == "500000"
        assert restored.changes["frames"][0]["scheduled_time_us"] == "520000"
        restored.interrupt_capture("paused")
        database.save_checkpoint(
            project,
            run,
            engine.capture_state(),
            expected_revision=1,
            context=context,
            input_changes=restored.take_changes(),
            status="paused",
        )
        assert connect(client, root, binding["token"], "device", session).status_code == 409
        assert client.post(endpoint + "/packets", json=packet(2, capture=30000), headers=headers).status_code == 409
        # Queued promises already in Core survive a session interruption.
        assert len(engine.capture_state().to_dict()["queue"]) == 2


def test_device_budget_does_not_consume_sequence_and_closed_sources_reject(database):
    with client_for(database) as client:
        project, _run, url, root, binding = setup(client, {"packets_per_second": 2})
        headers = {"Authorization": "Bearer " + binding["token"]}
        session = connect(client, root, binding["token"]).json()["session"]["id"]
        endpoint = root + f"/sessions/{session}"
        assert client.post(endpoint + "/packets", json=packet(), headers=headers).status_code == 202
        assert client.post(endpoint + "/packets", json=packet(1, 2000), headers=headers).status_code == 409
        with database.tx(project) as db:
            assert (
                db.execute("SELECT next_sequence FROM device_sessions WHERE id=%s", (session,)).fetchone()[
                    "next_sequence"
                ]
                == 1
            )
            db.execute("UPDATE device_bindings SET rate_count=0 WHERE id=%s", (binding["device"]["id"],))
        assert client.post(url + "/commands", json={"kind": "close_inputs"}).status_code == 200
        assert client.post(endpoint + "/packets", json=packet(1, 2000), headers=headers).status_code == 409
        with database.tx(project) as db:
            assert (
                db.execute("SELECT rate_count FROM device_bindings WHERE id=%s", (binding["device"]["id"],)).fetchone()[
                    "rate_count"
                ]
                == 1
            )
            assert (
                db.execute("SELECT next_sequence FROM device_sessions WHERE id=%s", (session,)).fetchone()[
                    "next_sequence"
                ]
                == 1
            )
        assert client.post(endpoint + "/packets", content=b"x" * 131073, headers=headers).status_code == 413
        assert (
            client.post(
                endpoint + "/packets",
                content='{"protocol":"threemind-network/2","sequence":0,"sequence":1}',
                headers=headers,
            ).status_code
            == 422
        )


def test_device_worker_replacement_and_revoked_pending_ports(database):
    with client_for(database) as client:
        project, run, url, root, binding = setup(
            client,
            {"modulation": True},
            {
                "environment": "manual",
                "clock": "realtime",
                "duration_s": 0.02,
            },
        )
        headers = {"Authorization": "Bearer " + binding["token"]}
        with database.tx(project) as db:
            db.execute("UPDATE runs SET status='running' WHERE id=%s", (run,))
        session = connect(client, root, binding["token"], "device").json()["session"]["id"]
        endpoint = root + f"/sessions/{session}"
        assert client.post(endpoint + "/packets", headers=headers, json=packet(when=0)).status_code == 202
        assert (
            client.post(
                endpoint + "/packets",
                headers=headers,
                json={"protocol": PROTOCOL, "type": "modulation", "sequence": "1", "value": {}},
            ).status_code
            == 202
        )
        old = claim_as(database, "disconnected-device-worker")
        with database.tx(project) as db:
            db.execute("UPDATE jobs SET lease_until=now()-interval '1 second' WHERE id=%s", (old["id"],))
        replacement = claim_as(database, "replacement-device-worker")
        assert replacement["attempts"] == 2
        Worker(database, name="replacement-device-worker").run(replacement)
        database.finish(replacement, result={})
        rows = client.get(endpoint + "/receipts", headers=headers).json()["rows"]
        assert rows[0]["delivery_status"] == "rejected"
        assert rows[1]["port_outcome"]["status"] == "rejected"
        assert connect(client, root, binding["token"], "device", session).status_code == 409
        assert (
            client.get(url + f"/devices/{binding['device']['id']}/sessions").json()["rows"][0]["reason"]
            == "worker_replaced"
        )


def test_device_actual_clock_rejects_late_without_reanchoring_or_partial_queue(database):
    spec = {"environment": "manual", "clock": "realtime", "duration_s": 10}
    with client_for(database) as client:
        project, run, _url, root, binding = setup(client, spec=spec)
        with database.tx(project) as db:
            db.execute("UPDATE runs SET status='running' WHERE id=%s", (run,))
        headers = {"Authorization": "Bearer " + binding["token"]}
        session = connect(client, root, binding["token"], "device").json()["session"]["id"]
        endpoint = root + f"/sessions/{session}"
        first = client.post(endpoint + "/packets", json=packet(when=0), headers=headers).json()
        engine = create_engine(Config())
        host = RuntimeInputs(database, project, run, engine, RunSpec(**spec), {}, 0)
        host.accepted(first["envelope_id"])
        engine.advance_to(700000)
        late = client.post(endpoint + "/packets", json=packet(1, when=0, capture=10000), headers=headers)
        assert late.status_code == 202  # Database projection is intentionally still at zero.
        queue_before = engine.capture_state().to_dict()["queue"]
        result = host.accepted(late.json()["envelope_id"])
        assert result["rejected"] and "不能倒填时间" in result["reason"]
        assert host.device_streams[session]["closed"]
        assert host.device_streams[session]["origin_us"] == "500000"
        assert engine.capture_state().to_dict()["queue"] == queue_before
