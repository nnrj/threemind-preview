import copy
import io
import json
import zipfile
from pathlib import Path

import pytest

from threemind_core import Config, Stimulus
from threemind_runtime.calibration import calibrate, parse_protocol
from threemind_runtime.chat_readout import display_readout
from threemind_runtime.host import create_engine
from threemind_runtime.readout_session import ReadoutSession
from threemind_runtime.sensory import TextSensor, TextSensorConfig
from threemind_runtime.temporal_probe import TemporalProbeProtocol


def test_readable_order_matches_executed_legacy_fixture_without_losing_nodes():
    fixture = json.loads(
        (Path(__file__).parents[1] / "docs/benchmarks/chat-restoration-reference.json").read_text(encoding="utf-8")
    )
    rows = [dict(n, direct=n["direct_touch"], associative=n["associative_touch"]) for n in fixture["nodes"]]
    value = {
        "kind": "structural_readout",
        "raw_nodes": rows,
        "annotations": {k: [v] for k, v in fixture["labels"].items()},
    }
    original = copy.deepcopy(value)
    for case in fixture["cases"]:
        result = display_readout(value, order="activation" if case["sort_by_activation"] else "id")
        assert result["text"] == case["text"] and result["node_ids"] == case["node_ids"]
    assert value == original
    assert len(result["nodes"]) == 3 and len(result["readable_labels"]) == 2


def test_temporal_preview_uses_recorded_ranking_and_all_measurements_remain_accessible():
    value = {
        "kind": "temporal_readout",
        "window_id": "w",
        "candidate_ids": [9, 1, 8, 2, 7, 3, 6, 4],
        "nodes": [{"node_id": i, "peak_activation": i / 10, "last_activation": 0, "score": 0.1} for i in range(10)],
        "annotations": {str(i): [str(i)] for i in range(10)},
    }
    before = copy.deepcopy(value)
    assert display_readout(value)["node_ids"] == [9, 1, 8, 2, 7, 3, 6]
    assert display_readout(value, scope="all", limit=0)["node_ids"] == list(range(10))
    assert display_readout(value, offset=7)["node_ids"] == [4]
    assert value == before


@pytest.mark.parametrize("backend", ["native", "reference"])
def test_session_pause_restore_delivery_windows_and_core_neutrality(backend):
    config = Config(activation_decay_enabled=False, inhibition_gain=0, propagation_rate=0)
    engine = create_engine(config, backend=backend)
    sensor = TextSensor(1, TextSensorConfig(encoding="labeled-observation", frame_characters=1))
    frames = list(sensor.frames("甲。"))
    events = []
    session = ReadoutSession(engine, record=events.append, config={"structural_readout": {"enabled": False}})
    session.schedule(frames, envelope_id="cue")
    session.advance_to(400000)
    checkpoint, context = engine.capture_state(), session.capture()
    restored = create_engine(state=checkpoint, backend=backend)
    continuation = ReadoutSession(restored, record=events.append, state=context)
    continuation.advance_to(2000000)
    plain = create_engine(config, backend=backend)
    for f in frames:
        plain.inject(f["stimulus"])
    plain.advance_to(2000000)
    assert restored.capture_state().digest == plain.capture_state().digest
    temporal = [e["payload"] for e in events if e["kind"] == "temporal_readout"]
    assert len(temporal) == 1
    assert temporal[0]["classification"] == "converged"
    assert int(temporal[0]["end_us"]) - int(temporal[0]["delivery_end_us"]) >= 1200000
    assert temporal[0]["annotations"]


@pytest.mark.parametrize("backend", ["native", "reference"])
def test_temporal_probe_retains_source_and_observes_past_one_second(backend):
    engine = create_engine(Config(activation_decay_enabled=False, inhibition_gain=0), backend=backend)
    image = engine.capture_state()
    protocol = parse_protocol({"mode": "temporal", "cues": ["甲。"]})
    assert protocol.route == "continuation" and protocol.blank_us == 0 and protocol.learning_during_probe is None
    result, raw = calibrate(image, seed=3, sensor_config=TextSensorConfig(), protocol=protocol, backend=backend)
    window = result["rows"][0]["temporal"]
    assert int(window["end_us"]) >= 1200000
    assert result["source_hash"] == image.digest and result["source_unchanged"]
    assert result["rows"][0]["learning_during_probe"] == engine.config.plasticity
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert json.loads(z.read("result.json")) == result
        assert json.loads(z.read("probes/0/deliveries.json"))[0]["frame_count"] >= 1


def test_cutoff_is_not_convergence_and_missing_is_not_zero():
    engine = create_engine()
    records = []
    session = ReadoutSession(engine, record=records.append, config={"structural_readout": {"enabled": False}})
    session.schedule([{"stimulus": Stimulus(0, ((1, 1.0),))}])
    session.advance_to(200000)
    session.host.close(engine.time_us, "run_ended")
    assert records[-1]["payload"]["classification"] == "censored"
    result, _ = calibrate(
        engine.capture_state(),
        seed=1,
        sensor_config=TextSensorConfig(enabled=False),
        protocol=TemporalProbeProtocol(cues=["甲"]),
    )
    assert result["rows"][0]["classification"] == "not_observed"
    assert result["rows"][0]["temporal"] is None


def test_forward_feed_never_skips_a_burst_and_projection_is_read_only(database):
    from psycopg.types.json import Jsonb
    from test_api import client_for
    from test_conversation import fixture, stimulus

    with client_for(database) as client:
        project, run, base = fixture(client)
        with database.tx(project) as db:
            for i in range(145):
                stimulus(db, project, run, "manual-text", f"carrier {i}")
            payload = {
                "kind": "temporal_readout",
                "window_id": "fixture",
                "source": "manual-text",
                "nodes": [{"node_id": i, "peak_activation": i / 10} for i in range(10)],
                "candidate_ids": [9, 8, 7, 6, 5, 4, 3, 2],
                "annotations": {},
                "classification": "unresolved",
            }
            payload["chat"] = display_readout(payload)
            event = db.execute(
                "INSERT INTO events(project_id,run_id,event_key,time_us,kind,payload,commit_revision) "
                "VALUES(%s,%s,'temporal-test',0,'temporal_readout',%s,0) RETURNING id",
                (project, run, Jsonb(payload)),
            ).fetchone()["id"]
        ids, after = [], "0"
        while True:
            r = client.get(base + f"/conversation?after={after}&limit=20").json()
            ids.extend(x["id"] for x in r["rows"])
            if not r["more"]:
                break
            after = r["next"]
        assert len(ids) == len(set(ids)) == 146
        assert list(map(int, ids)) == sorted(map(int, ids))
        response = client.get(base + f"/conversation/{ids[-1]}/presentation?scope=all&limit=4&offset=4")
        assert response.status_code == 200, response.text
        assert response.json()["display"]["node_ids"] == [4, 5, 6, 7]
        with database.tx(project) as db:
            assert db.execute("SELECT payload FROM events WHERE id=%s", (event,)).fetchone()["payload"] == payload


def test_lab_temporal_mode_keeps_readout_provenance_and_source_state(database):
    from uuid import uuid4

    from test_api import client_for

    from threemind_lab.protocols import RunSpec
    from threemind_lab.worker import Worker

    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Temporal acceptance"}).json()["id"]
        spec = RunSpec(environment="manual", temporal_readout={"min_response_us": 1500000})
        run = database.create_run(project, "Independent source", spec.model_dump())
        image = create_engine().capture_state()
        database.save_checkpoint(
            project, run["id"], image, expected_revision=0, status="completed", context={"protocol": spec.model_dump()}
        )
        root = f"/api/v2/projects/{project}"
        response = client.post(
            root + f"/runs/{run['id']}/calibrations",
            json={"operation_id": str(uuid4()), "protocol": {"mode": "temporal", "cues": ["甲。"]}},
        )
        assert response.status_code == 202, response.text
        ident = response.json()["id"]
        assert Worker(database).once()
        result = client.get(root + f"/calibrations/{ident}/result")
        assert result.status_code == 200, result.text
        assert result.json()["protocol"]["temporal_readout"]["min_response_us"] == 1500000
        assert result.json()["rows"][0]["temporal"] is not None
        assert database.load_checkpoint(project, run["id"])[1].digest == image.digest


def test_chat_receipts_are_scoped_and_passive_filter_does_not_hide_temporal(database):
    from test_api import client_for
    from test_conversation import fixture, readout, stimulus

    with client_for(database) as client:
        project, run, base = fixture(client)
        other_project, other_run, other_base = fixture(client, "Other project")
        with database.tx(project) as db:
            input_id = stimulus(db, project, run, "manual-text")
            readout(db, project, run, kind="structural_readout")
            readout(db, project, run, "manual-text", input_id)
        with database.tx(other_project) as db:
            stimulus(db, other_project, other_run, "manual-text")
        rows = client.get(base + "/conversation?background=true&passive=false").json()["rows"]
        assert {r["kind"] for r in rows} == {"input", "temporal_readout"}
        entry_id = next(r["id"] for r in rows if r["kind"] == "input")
        foreign_id = client.get(other_base + "/conversation").json()["rows"][0]["id"]
        before = client.get(base).json()
        with database.tx(project) as db:
            db.execute(
                "UPDATE input_envelopes SET status='completed',delivered_count=1,last_delivery_us=100000 WHERE id=%s",
                (input_id,),
            )
        result = client.get(base + f"/conversation/statuses?entry={entry_id}&entry={foreign_id}")
        assert result.status_code == 200
        assert result.json()["rows"] == [
            {
                "id": entry_id,
                "status": "completed",
                "frame_count": 1,
                "delivered_count": 1,
                "filtered_count": 0,
                "last_delivery_us": "100000",
            }
        ]
        assert client.get(base + "/conversation/statuses?entry=-1").status_code == 422
        assert client.get(base + "/conversation/statuses", params=[("entry", entry_id)] * 321).status_code == 422
        assert client.get(base).json()["revision"] == before["revision"]


def test_temporal_json_validation_keeps_unset_inheritance_and_does_not_create_jobs(database):
    from test_api import client_for
    from test_conversation import fixture

    with client_for(database) as client:
        project, run, base = fixture(client)
        body = {"protocol": {"mode": "temporal", "cues": ["甲是松子。"], "max_wall_seconds": 70}}
        with database.tx(project) as db:
            before = db.execute("SELECT count(*) AS n FROM jobs WHERE run_id=%s", (run,)).fetchone()["n"]
        valid = client.post(base + "/calibrations/validate", json=body)
        assert valid.status_code == 200 and valid.json() == body
        invalid = {"protocol": body["protocol"] | {"unknown_mapping_override": False}}
        assert client.post(base + "/calibrations/validate", json=invalid).status_code == 422
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM jobs WHERE run_id=%s", (run,)).fetchone()["n"] == before


def test_temporal_source_policy_and_interrupted_budget_are_explicit():
    engine = create_engine(Config(activation_decay_enabled=False, inhibition_gain=0))
    image = engine.capture_state()
    protocol = TemporalProbeProtocol(cues=["甲。", "乙。"])
    disabled, _ = calibrate(
        image,
        seed=1,
        sensor_config=TextSensorConfig(),
        protocol=protocol,
        source_context={"protocol": {"source_policies": {"cli_text_enabled": False}}},
    )
    assert all(row["reason"] == "input_source_disabled" for row in disabled["rows"])
    ticks = 0

    def guard():
        nonlocal ticks
        ticks += 1
        if ticks > 8:
            raise TimeoutError("test_budget")

    result, raw = calibrate(image, seed=1, sensor_config=TextSensorConfig(), protocol=protocol, guard=guard)
    assert result["batch_budget_reached"]
    assert result["rows"][0]["classification"] == "censored"
    assert result["rows"][0]["reason"] == "test_budget"
    assert result["rows"][1]["classification"] == "not_observed" and result["rows"][1]["temporal"] is None
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert json.loads(archive.read("result.json")) == result
    assert image.digest == engine.capture_state().digest
