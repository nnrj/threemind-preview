import copy
import csv
import io
import json
import zipfile
from dataclasses import asdict, fields, replace
from uuid import uuid4

import pytest
from test_api import client_for

from threemind_core import Config, Engine, Stimulus
from threemind_lab.configuration import catalogue, default_spec, validate_configuration
from threemind_lab.input_cycle import RuntimeInputs
from threemind_lab.protocols import RunSpec
from threemind_lab.readouts import ReadoutHost, reconfigure
from threemind_lab.worker import Worker
from threemind_runtime.host import NativeEngine
from threemind_runtime.readout_config import READOUT_CONFIGS, StructuralReadoutConfig, TemporalReadoutConfig
from threemind_runtime.readouts import StructuralReader, TemporalReader


def node(id=1, activation=0.5, **values):
    return dict(
        id=id,
        channel=id,
        activation=activation,
        direct=0.2,
        associative=0.1,
        inhibition=0.0,
        stability=0.0,
        trace=0.0,
        support=1.0,
        **values,
    )


def delivery(id="carrier", at=0, index=0, count=1, source="manual-text", **values):
    return dict(
        envelope_id=id,
        delivered_time_us=str(at),
        frame_index=index,
        frame_count=count,
        source=source,
        adapter_id="text-sensor",
        **values,
    )


def temporal(**values):
    return TemporalReadoutConfig(
        **(
            {
                "interval_us": 100000,
                "settle_us": 200000,
                "min_response_us": 1000000,
                "max_response_us": 2000000,
                "baseline_us": 0,
            }
            | values
        )
    )


def test_irregular_sampling_integrals_baseline_and_disappearance_are_explicit():
    reader = TemporalReader(temporal(baseline_us=1000000, baseline_noise_gain=0))
    reader.consume(0, 0, [node(activation=0.2)])
    reader.consume(400000, 1, [node(activation=0.4)])
    reader.consume(1000000, 2, [node(activation=0.8)], [delivery(at=1000000)])
    reader.consume(1300000, 3, [node(activation=0.6)])
    reader.consume(1700000, 4, [])
    reader.consume(1800000, 5, [])
    (record,) = reader.close(1800000, "run_ended")
    (row,) = record["nodes"]
    assert row["baseline_mean"] == pytest.approx(0.32)
    assert row["baseline_noise"] == pytest.approx((0.4 * 0.2**2 + 0.6 * 0.4**2 - 0.32**2) ** 0.5)
    assert row["activation_integral"] == pytest.approx(0.8 * 0.3 + 0.6 * 0.4)
    assert row["excess_integral"] == pytest.approx(0.48 * 0.3 + 0.28 * 0.4)
    assert row["direct_trace_integral"] == pytest.approx(0.2 * 0.7)
    assert row["active_us"] == "700000" and row["longest_run_us"] == "700000"
    assert record["coverage"]["observed_us"] == "800000" and record["coverage"]["baseline_complete"]
    assert record["coverage"]["method"].startswith("left-hold")
    assert record["classification"] == "censored" and len(record["series"]) == 4


@pytest.mark.parametrize(
    "mode, expected",
    [("constant", "converged"), ("decay", "residual_decay"), ("empty", "transient"), ("periodic", "oscillatory")],
)
def test_finite_window_classification_separates_amplitude_decay_and_period(mode, expected):
    reader = TemporalReader(temporal(min_response_us=600000))
    output = []
    for i in range(10):
        value = (
            []
            if mode == "empty"
            else [
                node(id=(1 + i % 2 if mode == "periodic" else 1), activation=(0.8 * 0.7**i if mode == "decay" else 0.7))
            ]
        )
        output += reader.consume(i * 100000, i, value, [delivery()] if i == 0 else [])
        if output:
            break
    assert len(output) == 1 and output[0]["classification"] == expected
    if mode == "decay":
        assert output[0]["convergence"]["mean_jaccard"] == 1
        assert output[0]["convergence"]["amplitude_drift"] > 0.12
    if mode == "periodic":
        assert output[0]["convergence"]["period_us"] == "200000"


def test_display_limits_do_not_change_scientific_measurements_and_capture_is_independent():
    a, b = TemporalReader(temporal(display_limit=1)), TemporalReader(temporal(display_limit=100))
    resumed = None
    for i in range(12):
        stimulus = [delivery(count=4, last_scheduled_index=0)] if i == 0 else []
        nodes = [node(1, 0.7), node(2, 0.4)]
        x = a.consume(i * 100000, i, nodes, stimulus)
        y = b.consume(i * 100000, i, nodes, stimulus)
        if resumed:
            assert resumed.consume(i * 100000, i, nodes, stimulus) == x
        if i == 3:
            captured = a.capture()
            resumed = TemporalReader(a.config, json.loads(json.dumps(captured)))
            captured["windows"]["carrier"]["nodes"]["1"]["active_us"] = -100
            assert a.capture()["windows"]["carrier"]["nodes"]["1"]["active_us"] >= 0
        if x:
            assert x[0]["nodes"] == y[0]["nodes"] and x[0]["convergence"] == y[0]["convergence"]
            assert x[0]["delivery_end_us"] == "0" and len(x[0]["nodes"]) == 2
            break
    else:
        pytest.fail("response did not finish")


def test_overlap_partial_input_and_observer_budgets_preserve_evidence():
    reader = TemporalReader(temporal(max_active_windows=1, max_response_us=1000000))
    assert not reader.consume(
        0, 0, [node()], [delivery(index=2, count=8), delivery("background", source="host-telemetry")]
    )
    (missing,) = reader.consume(100000, 1, [node()], [delivery("second", at=100000)])
    assert missing["classification"] == "not_observed" and missing["coverage"]["sample_count"] == 0
    (record,) = reader.consume(1000000, 2, [node()])
    assert record["reason"] == "maximum_window" and record["partial_start"] and record["delivery_end_us"] is None
    assert set(record["overlapping_envelopes"]) == {"background", "second"}
    assert not reader.consume(1100000, 3, [node()], [delivery(index=4, count=8, at=1100000)])
    assert not reader.consume(1200000, 4, [node()], [delivery(index=7, count=8, at=1200000)])
    assert not reader.closed_inflight
    reader = TemporalReader(temporal(max_node_entries=1))
    (record,) = reader.consume(0, 0, [node(1), node(2)], [delivery()])
    assert record["reason"] == "node_entry_budget" and record["coverage"]["reasons"] == ["node_entry_budget"]
    reader = TemporalReader(temporal(interval_us=1000, max_history_samples=24))
    records = []
    for i in range(25):
        records += reader.consume(i * 1000, i, [node()], [delivery()] if i == 0 else [])
    assert records[0]["reason"] == "history_sample_budget" and len(records[0]["series"]) == 24
    assert records[0]["coverage"]["last_sample_us"] == "23000"


def test_structure_recurrence_cooldown_and_complete_activity_are_separate():
    cfg = StructuralReadoutConfig(
        min_occurrences=3, min_span_us=200000, cooldown_us=300000, display_limit=1, max_nodes=3
    )
    reader = StructuralReader(cfg)
    nodes = [node(i, 0.8) for i in range(1, 9)]
    edges = [
        {"source": 1, "target": 2, "weight": 0.2, "stability": 0.1},
        {"source": 2, "target": 3, "weight": 0.2, "stability": 0.1},
    ]
    records = [reader.consume(i * 100000, i, nodes, edges) for i in range(6)]
    assert [r["structure"]["recurrence_notice"] for r in records] == [False, False, True, False, False, True]
    assert len(records[0]["activity_nodes"]) == 8 and len(records[0]["structure"]["nodes"]) == 3
    other = reader.consume(
        600000,
        6,
        [dict(n, id=n["id"] + 100) for n in nodes],
        [dict(e, source=e["source"] + 100, target=e["target"] + 100) for e in edges],
    )
    assert other["structure"]["topology_fingerprint"] == records[0]["structure"]["topology_fingerprint"]
    assert other["structure"]["structure_id"] != records[0]["structure"]["structure_id"]
    assert not other["structure"]["recurrent"]


def test_below_threshold_history_and_candidate_scope_are_not_silently_discarded():
    reader = TemporalReader(temporal(candidate_scope="associative-only"))
    reader.consume(0, 0, [dict(node(activation=0.01), direct=0, associative=0)], [delivery()])
    reader.consume(100000, 1, [dict(node(activation=0.8), direct=0, associative=0)])
    for i in range(2, 12):
        assert not reader.consume(i * 100000, i, [dict(node(activation=0.8), direct=0, associative=0)])
    (record,) = reader.close(1100000, "run_ended")
    assert record["nodes"][0]["activation_integral"] == pytest.approx(0.001 + 0.8)
    assert record["candidate_count"] == 0 and record["convergence"]["tail_has_activity"]
    assert not record["convergence"]["tail_has_candidates"]


@pytest.mark.parametrize("engine_class", [Engine, NativeEngine])
def test_observation_accessors_and_host_do_not_mutate_core_or_partitioned_trajectory(engine_class):
    engine = engine_class(Config(step_us=10000))
    spec = RunSpec(environment="manual", clock="unbounded", temporal_readout=temporal())
    run = str(uuid4())
    inputs = RuntimeInputs(None, str(uuid4()), run, engine, spec, {}, 0)
    inputs.replay([Stimulus(t, ((1, 0.7), (2, 0.6), (3, 0.4))).to_dict() for t in (0, 100123, 200456)])
    twin = engine_class(state=engine.capture_state())
    events = []
    host = ReadoutHost(spec, run, 0, record=events.append)
    for t in (0, 75123, 100123, 150371, 200456, 234567, 400000):
        engine.advance_to(t, lambda e: host.delivered(inputs.observe(e)), inputs_only=True)
        before = engine.capture_state().digest
        nodes = engine.observation_nodes()
        edges = engine.induced_edges([n["id"] for n in nodes[:2]])
        assert all(
            e["source"] in [n["id"] for n in nodes[:2]] and e["target"] in [n["id"] for n in nodes[:2]] for e in edges
        )
        host.observe(engine)
        assert engine.capture_state().digest == before
    twin.advance_to(400000)
    assert twin.capture_state().digest == engine.capture_state().digest
    saved = host.capture()
    clone = ReadoutHost(spec, run, 400000, state=json.loads(json.dumps(saved)), record=events.append)
    assert clone.capture() == saved
    changed = RunSpec(
        **(spec.model_dump() | {"temporal_readout": asdict(replace(spec.temporal_readout, enabled=False))})
    )
    state, closed = reconfigure(saved, changed, run, 400000)
    assert closed and closed[0]["payload"]["reason"] == "configuration_changed"
    assert not state["temporal"]["windows"] and saved["temporal"]["windows"]
    fresh = ReadoutHost(spec, str(uuid4()), 400000, state=saved, record=events.append)
    assert not fresh.temporal.windows


def test_readout_catalogue_covers_all_fields_and_validates_combinations():
    catalog = catalogue()
    actual = {f["path"] for f in catalog["fields"]}
    expected = {f"{root}.{field.name}" for root, cls in READOUT_CONFIGS.items() for field in fields(cls)}
    assert expected <= actual
    assert len([p for p in expected if not p.startswith("activity_readout.")]) == 38
    assert validate_configuration(default_spec())["valid"]
    spec = default_spec()
    spec["temporal_readout"]["interval_us"] = 1000000
    spec["temporal_readout"]["settle_us"] = 100000
    assert not validate_configuration(spec)["valid"]


def test_database_readouts_resume_paging_exports_configuration_and_isolation(database, monkeypatch):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "readout validation"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        spec = RunSpec(
            environment="replay",
            clock="unbounded",
            duration_s=1.5,
            checkpoint_us=100000,
            replay=[Stimulus(t, ((1, 0.8), (2, 0.7), (3, 0.5))).to_dict() for t in (0, 100123, 200456)],
            temporal_readout=temporal(min_response_us=300000),
        )
        response = client.post(f"{root}/runs", json={"name": "Readouts", "spec": spec.model_dump()})
        assert response.status_code == 201, response.text
        run = response.json()["id"]
        url = f"{root}/runs/{run}"
        original = ReadoutHost.observe
        saved = []

        def stop_after_sample(host, engine, **kwargs):
            original(host, engine, **kwargs)
            if engine.time_us >= 200000 and not saved:
                saved.append(host.capture())
                worker.stopping = True

        worker = Worker(database)
        with monkeypatch.context() as patch:
            patch.setattr(ReadoutHost, "observe", stop_after_sample)
            assert worker.once()
        paused = client.get(url).json()
        assert paused["status"] == "paused", paused.get("error")
        page = client.get(f"{url}/readouts").json()
        assert page["active"] and page["active"][0]["delivery_end_us"] is None
        cp, image = database.load_checkpoint(project, run)
        assert cp["context"]["readouts"] == saved[0]
        expected = NativeEngine(state=image)
        expected.advance_to(1500000)
        changed = copy.deepcopy(paused["spec"])
        changed["temporal_readout"]["baseline_noise_gain"] = 0.5
        result = client.put(
            f"{url}/configuration", json={"name": "Readouts", "spec": changed, "expected_revision": paused["revision"]}
        )
        assert result.status_code == 200, result.text
        interrupted = client.get(f"{url}/readouts?classification=interrupted").json()["rows"]
        assert len(interrupted) == 1 and interrupted[0]["payload"]["reason"] == "configuration_changed"
        assert client.post(f"{url}/commands", json={"kind": "resume"}).status_code == 200
        assert Worker(database).once()
        completed = client.get(url).json()
        assert completed["status"] == "completed", completed.get("error")
        assert completed["state_hash"] == expected.capture_state().digest
        rows = []
        before = None
        while True:
            response = client.get(f"{url}/readouts", params={"limit": 1, **({"before_id": before} if before else {})})
            assert response.status_code == 200, response.text
            page = response.json()
            rows += page["rows"]
            if not page["more"]:
                break
            before = page["next"]
        assert len(rows) > 3 and len({r["id"] for r in rows}) == len(rows)
        assert all("nodes" not in r["payload"] and "series" not in r["payload"] for r in rows)
        temporal_row = next(
            r
            for r in rows
            if r["payload"]["kind"] == "temporal_readout" and r["payload"]["classification"] != "interrupted"
        )
        record_id = temporal_row["id"]
        full = client.get(f"{url}/readouts/{record_id}/export").json()
        detail = client.get(f"{url}/readouts/{record_id}?candidates_only=false&limit=1").json()
        assert detail["total"] == len(full["payload"]["nodes"]) and detail["more"]
        assert "nodes" not in detail["record"]["payload"]
        series = client.get(f"{url}/readouts/{record_id}?section=series&limit=2").json()
        assert len(series["rows"]) == 2 and series["total"] == len(full["payload"]["series"])
        csvrows = list(
            csv.DictReader(
                io.StringIO(client.get(f"{url}/readouts/{record_id}/export?format=csv").text.lstrip("\ufeff"))
            )
        )
        assert len(csvrows) == len(full["payload"]["nodes"])
        assert len(client.get(f"{url}/readouts/export").text.splitlines()) == len(rows)
        for format, magic in [("png", b"\x89PNG"), ("pdf", b"%PDF"), ("svg", b"<?xml")]:
            drawing = client.get(f"{url}/readouts/{record_id}/export?format={format}")
            assert drawing.status_code == 200 and drawing.content.startswith(magic)
        assert not any(e["kind"].endswith("_readout") for e in client.get(f"{url}/events").json())
        other = client.post("/api/v2/projects", json={"name": "Other readouts"}).json()["id"]
        assert client.get(f"/api/v2/projects/{other}/runs/{run}/readouts/{record_id}").status_code == 404
        assert client.get(f"{url}/readouts?classification=fiction").status_code == 422
        assert client.get(f"{url}/readouts/{record_id}?section=fiction").status_code == 422
        export = client.post(f"{url}/exports", json={"format": "evidence", "checkpoint_id": str(cp["id"])}).json()
        assert Worker(database).once()
        job = next(j for j in client.get(f"{root}/jobs").json() if j["id"] == export["id"])
        assert job["status"] == "done", job.get("error")
        package = client.get(f"{root}/artifacts/{job['result']['artifact_id']}").content
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            assert archive.read("temporal-readouts.jsonl") == b""
            snapshots = [json.loads(line) for line in archive.read("structural-readouts.jsonl").splitlines()]
            assert snapshots and all(r["commit_revision"] <= cp["revision"] for r in snapshots)
            context = json.loads(archive.read("recovery-context.json"))
            assert context["readouts"]["temporal"]["windows"]
