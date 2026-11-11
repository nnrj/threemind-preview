from copy import deepcopy
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb
from test_api import client_for

from threemind_lab.organ_controls import switch_spec, validate_change
from threemind_lab.protocols import RunSpec
from threemind_lab.worker import Worker
from threemind_runtime.chat_readout import display_readout


def test_switch_scope_and_accepted_carriers_survive_capture_off():
    before = RunSpec().model_dump()
    before["source_policies"]["background_enabled"] = False
    enabled = switch_spec(before, "ear", True)
    assert enabled["live_capture"]["microphone_enabled"]
    assert enabled["auditory_sensor"]["enabled"]
    assert enabled["source_policies"]["background_enabled"]
    assert enabled["source_policies"]["microphone_enabled"]
    assert not enabled["source_policies"]["camera_enabled"]
    disabled = switch_spec(enabled, "ear", False)
    assert not disabled["live_capture"]["microphone_enabled"]
    # Delivery keeps the sensor and gate used by frames already accepted.
    assert disabled["source_policies"] == enabled["source_policies"]
    assert disabled["auditory_sensor"] == enabled["auditory_sensor"]
    assert disabled["config"] == before["config"]
    change = {"before": before, "after": enabled, "operations": [{"control": "ear", "enabled": True}]}
    validate_change(change)
    change["after"] = deepcopy(enabled)
    change["after"]["config"]["learning_rate"] = 100
    with pytest.raises(ValueError, match="unrelated"):
        validate_change(change)


def test_worker_acknowledges_inline_controls_atomically(database):
    with client_for(database) as client:
        p = client.post("/api/v2/projects", json={"name": "Inline organs"}).json()["id"]
        run = client.post(
            f"/api/v2/projects/{p}/runs",
            json={"name": "Controls", "spec": {"environment": "manual", "clock": "unbounded", "duration_s": 0.21}},
        ).json()
        base = f"/api/v2/projects/{p}/runs/{run['id']}"
        receipts = []
        for control in ("mouth", "image", "ear", "eye"):
            response = client.post(base + "/organ-controls", json={"control": control, "enabled": True})
            assert response.status_code == 200, response.text
            pending = response.json()
            assert pending["status"] == "pending"
            receipts.append(pending["command_id"])
        assert client.get(base).json()["spec"] == run["spec"]
        assert Worker(database).once()
        result = client.get(base).json()
        assert result["status"] == "completed", result.get("error")
        assert result["spec"]["config"] == run["spec"]["config"]
        for cid in receipts:
            receipt = client.get(base + f"/organ-controls/{cid}").json()
            assert receipt["status"] == "applied" and receipt["time_us"] == "0"
        assert result["spec"]["acoustic_output"]["enabled"]
        assert result["spec"]["activation_projector"]["enabled"]
        assert client.get(base + "/organs").json()["rows"]
        cp, state = database.load_checkpoint(p, run["id"])
        assert state.to_dict()["dynamics"] == "threemind.causal/9"
        assert cp["context"]["protocol"] == result["spec"]
        assert client.post(base + "/organ-controls", json={"control": "mouth", "enabled": False}).status_code == 409


def test_paused_controls_keep_model_and_use_scoped_configuration_validation(database):
    with client_for(database) as client:
        p = client.post("/api/v2/projects", json={"name": "Paused organs"}).json()["id"]
        run = client.post(
            f"/api/v2/projects/{p}/runs",
            json={"name": "Controls", "spec": {"environment": "manual", "clock": "unbounded"}},
        ).json()
        base = f"/api/v2/projects/{p}/runs/{run['id']}"
        client.post(base + "/commands", json={"kind": "pause"})
        assert Worker(database).once()
        before = client.get(base).json()
        result = client.post(base + "/organ-controls", json={"control": "media-video", "enabled": True})
        assert result.status_code == 200, result.text
        assert result.json()["status"] == "applied"
        after = client.get(base).json()
        assert before["state_hash"] == after["state_hash"]
        assert after["spec"]["visual_sensor"]["enabled"]
        assert after["spec"]["auditory_sensor"] == before["spec"]["auditory_sensor"]
        assert after["spec"]["config"] == before["spec"]["config"]
        assert (
            client.post(base + "/organ-controls", json={"control": "mouth", "enabled": True, "config": {}}).status_code
            == 422
        )
        other = client.post("/api/v2/projects", json={"name": "Other"}).json()["id"]
        assert (
            client.post(
                f"/api/v2/projects/{other}/runs/{run['id']}/organ-controls", json={"control": "mouth", "enabled": True}
            ).status_code
            == 404
        )


def test_chat_projects_all_actual_activity_without_candidate_or_causal_filtering():
    rows = [{"id": i, "activation": 0.1 if i else 0} for i in range(140)]
    raw = {
        "kind": "structural_readout",
        "raw_nodes": rows,
        "activity_nodes": [],
        "candidate_ids": [],
        "classification": "unresolved",
        "annotations": {"3": ["旧吊灯"], "4": ["蜂蜜"]},
    }
    before = deepcopy(raw)
    chat = display_readout(raw)
    assert raw == before
    assert chat["active_count"] == 139 and len(chat["nodes"]) == 128 and chat["truncated"]
    assert [n["id"] for n in chat["nodes"]] == list(range(1, 129))
    assert chat["nodes"][2]["labels"] == ["旧吊灯"]
    assert chat["nodes"][0]["labels"] == [] and not chat["semantic_reply"]
    temporal = display_readout(
        {"kind": "temporal_readout", "nodes": [{"node_id": 7, "peak_activation": 0.2}], "annotations": {}}
    )
    assert temporal["nodes"] == [{"id": 7, "activation": 0.2, "labels": []}]


def test_conversation_inlines_plaintext_and_separate_ai_observation(database):
    with client_for(database) as client:
        p = client.post("/api/v2/projects", json={"name": "Readable evidence"}).json()["id"]
        run = client.post(
            f"/api/v2/projects/{p}/runs",
            json={
                "name": "Plaintext",
                "spec": {
                    "environment": "manual",
                    "clock": "unbounded",
                    "duration_s": 0.2,
                    "text_sensor": {"encoding": "literal-character"},
                },
            },
        )
        assert run.status_code == 201, run.text
        rid = run.json()["id"]
        base = f"/api/v2/projects/{p}/runs/{rid}"
        sent = client.post(
            base + "/inputs",
            json={"adapter_id": "text-sensor", "payload": {"text": "蜂蜜"}, "request_id": str(uuid4())},
        )
        assert sent.status_code == 202, sent.text
        assert Worker(database).once()
        before = client.get(base).json()
        assert before["status"] == "completed", before.get("error")
        feed = client.get(base + "/conversation?background=true").json()["rows"]
        displays = [r["readout"]["display"] for r in feed if r["readout"] and r["readout"]["display"]]
        assert any("蜂" in label for d in displays for n in d["nodes"] for label in n["labels"])
        with database.tx(p) as db:
            db.execute(
                "INSERT INTO events(project_id,run_id,event_key,time_us,kind,payload) VALUES(%s,%s,%s,200000,'external_interpretation',%s)",
                (
                    p,
                    rid,
                    str(uuid4()),
                    Jsonb({"source": "ai-interpreter", "text": "An external interpretation", "evidence_ids": []}),
                ),
            )
        feed = client.get(base + "/conversation").json()["rows"]
        ai = next(r for r in feed if r["kind"] == "external_interpretation")
        assert ai["readout"]["text"] == "An external interpretation"
        assert client.get(base).json()["state_hash"] == before["state_hash"]
