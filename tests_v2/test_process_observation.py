import copy
import json
from dataclasses import asdict

import pytest
from test_activity_readout import config, observe
from test_readouts import delivery, node

from threemind_core import Stimulus
from threemind_runtime.activity_readout import ActivityReader
from threemind_runtime.host import create_engine
from threemind_runtime.observation_tools import analyze_record, compare_records
from threemind_runtime.process_observation import compare_observations, process_observation
from threemind_runtime.readout_session import ReadoutSession


def sample(t, values):
    return {"time_us": str(t), "activation_vector": {str(k): v for k, v in values.items()}}


def test_brief_weak_response_survives_empty_convergence_and_background():
    values = [[node(1, 0.8), node(2, 0.009 if i < 3 else 0)] for i in range(21)]
    (r,) = observe(values, config(analysis_version=2))
    assert r["analysis_schema"] == "threemind.activity-analysis/2"
    assert r["primary_result"]["nodes"] == [{"node_id": 1, "activation": 0.8}]
    n = next(n for n in r["nodes"] if n["node_id"] == 2)
    assert n["decision_activation"] == 0 and n["positive_change_peak"] == 0.009
    assert n["sampled_activation_integral"] == pytest.approx(0.0027)
    assert r["process"]["ended_node_count"] == 1
    assert r["process"]["coverage_complete"]
    assert observe(values, config(analysis_version=2), restore_at=8) == [r]


def test_transfer_and_recurrence_visible_with_unchanging_total_and_same_end_state():
    series = [sample(0, {1: 0.5}), sample(100000, {2: 0.5}), sample(200000, {1: 0.5})]
    p, ns = process_observation(series, [])
    assert all(x["activation_total"] == 0.5 for x in p["timeline"])
    assert p["maximum_pattern_distance"] == 1
    assert ns["1"]["activity_episode_count"] == 2
    assert ns["1"]["total_activation_variation"] == 1
    assert p["total_activation_variation"] == 2
    static = [sample(i * 100000, {1: 0.5}) for i in range(3)]
    c = compare_observations(series, static)
    assert c["maximum_l1_difference"] == 1 and c["series"][-1]["l1_difference"] == 0
    assert c["nodes"][0]["peak_time_us"] == "100000"


def test_signed_baseline_changes_include_disappeared_nodes_and_exact_integrals():
    p, ns = process_observation(
        [sample(0, {1: 0.2}), sample(100000, {}), sample(200000, {1: 0.1})],
        [{"node_id": 1, "baseline_mean": 0.3}, {"node_id": 9, "baseline_mean": 0.1}],
    )
    assert p["decrease_seen"] and not p["increase_seen"]
    assert ns["1"]["negative_change_integral"] == pytest.approx(0.04)
    assert ns["9"]["negative_change_integral"] == pytest.approx(0.02)
    assert ns["9"]["negative_change_peak"] == 0.1


def test_maximum_per_node_is_not_presented_as_a_simultaneous_state():
    p, ns = process_observation([sample(0, {1: 0.5}), sample(20, {2: 0.8})], [])
    assert p["peaks"]["increase"] == {"time_us": "20", "total": 0.8}
    assert ns["1"]["process_peak_activation"] == 0.5
    assert ns["1"]["response_peak_activation"] == 0
    assert ns["2"]["response_peak_activation"] == 0.8


def test_missing_samples_and_missing_vectors_are_not_zero_filled():
    p, _ = process_observation([sample(0, {}), sample(50000, {})], [], expected_interval_us=20000)
    assert p["sampling_gap_detected"]
    c = compare_observations([sample(0, {1: 0.1})], [sample(10, {1: 0.1})])
    assert c["status"] == "no_shared_samples" and c["maximum_l1_difference"] is None
    assert compare_observations([sample(0, {1: 0.1})], [sample(10, {1: 0.1})], relative=True)["changed_node_count"] == 0
    with pytest.raises(ValueError, match="complete activation"):
        process_observation([{"time_us": "0", "comparison": {"1": 0.1}}], [])
    with pytest.raises(ValueError):
        compare_observations([], [], epsilon=float("nan"))
    empty = compare_observations([], [sample(10, {1: 0.1})], relative=True)
    assert empty["status"] == "not_observed" and empty["maximum_l1_difference"] is None
    assert empty["right_unmatched_samples"] == 1 and empty["series"] == []


def test_report_tolerance_does_not_erase_raw_activity():
    p, ns = process_observation([sample(0, {1: 1e-14})], [], epsilon=1e-12)
    assert p["raw_activity_seen"] and not p["increase_seen"]
    assert ns["1"]["process_peak_activation"] == 1e-14


def test_manual_window_observes_reactivation_after_first_response_ends_and_records_trigger_gap():
    reader = ActivityReader(config(analysis_version=2))
    reader.begin_observation(0, "no-cue")
    out = []
    for i in range(21):
        out += reader.consume(
            i * 100000, i, [node(1, 0.1 if i in (0, 15) else 0)], [delivery(source="device-test")] if i == 0 else []
        )
    assert len(out) == 1
    record = out[0]
    assert record["envelope_id"] is None and record["delivery_end_us"] is None
    assert record["observation_id"] == "observation:no-cue"
    assert record["nodes"][0]["post_input_activation_integral"] is None
    assert record["process"]["reactivated_node_count"] == 1
    assert record["nodes"][0]["last_positive_us"] == "1500000"
    assert reader.capture()["diagnostics"]["untriggered_frames"] == 1


def test_legacy_restore_normalizes_only_new_config_fields_not_window_identity():
    old = ActivityReader(config())
    old.consume(0, 0, [node(1, 0.5)], [delivery()])
    saved = old.capture()
    for cfg in [saved["configuration"], *[w["configuration"] for w in saved["windows"].values()]]:
        cfg.pop("analysis_version")
        cfg.pop("process_epsilon")
    restored = ActivityReader(config(), copy.deepcopy(saved))
    assert restored.capture()["windows"] == saved["windows"]
    with pytest.raises(ValueError, match="incompatible"):
        ActivityReader(config(analysis_version=2), saved)


@pytest.mark.parametrize("backend", ["reference", "native"])
@pytest.mark.parametrize(
    "kernel",
    [
        "threemind.causal/9",
        "threemind.continuous/1",
        "threemind.continuous-memory/1",
        "threemind.continuous-memory/2",
        "threemind.continuous-memory/3",
        "threemind.continuous-memory/4",
        "threemind.lif/1",
    ],
)
def test_observer_cadence_and_recovery_preserve_core_and_old_reader(backend, kernel):
    def run(v2, recover):
        e = create_engine(kernel_id=kernel, backend=backend)
        records = []
        cfg = {"activity_readout": asdict(config(enabled=v2, analysis_version=2, interval_us=20000))}
        session = ReadoutSession(e, record=records.append, config=cfg)
        session.schedule([{"stimulus": Stimulus(0, ((1, 0.8), (2, 0.4)))}], envelope_id="fixed")
        session.advance_to(1000000)
        if recover:
            session = ReadoutSession(e, record=records.append, state=json.loads(json.dumps(session.capture())))
        session.advance_to(2000000)
        session.host.close(e.time_us, "run_ended")
        return e.capture_state().digest, records

    control, observed, restored = run(False, False), run(True, False), run(True, True)
    assert observed == restored
    assert control[0] == observed[0]

    def legacy(r):
        result = []
        for event in r:
            if not event["payload"].get("analysis_schema"):
                value = copy.deepcopy(event)
                value["payload"].pop("chat_primary", None)
                result.append(value)
        return result

    assert legacy(control[1]) == legacy(observed[1])


def test_offline_tools_preserve_original_and_compare_all_nodes():
    (record,) = observe([[node(1, 0.1 if i < 3 else 0)] for i in range(21)])
    original = copy.deepcopy(record)
    result = analyze_record(record)
    assert result["process"]["raw_activity_seen"] and result["original_classification"] == record["classification"]
    assert compare_records(record, record)["changed_node_count"] == 0
    assert record == original


def test_probe_copy_explicit_intervention_and_restore_leave_source_untouched():
    from threemind_runtime.observation_probe import probe_copy

    e = create_engine()
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.8))))
    e.advance_to(100000)
    image = e.capture_state()
    before = image.payload
    edges = [(r["source"], r["target"]) for r in image.to_dict()["edges"]]
    assert edges
    normal = probe_copy(image, duration_us=300000)
    restored = probe_copy(
        image,
        duration_us=300000,
        interventions=[{"action": "silence", "edges": edges}, {"action": "unsilence", "edges": edges}],
    )
    assert image.payload == before
    a, b = normal["final_state"].to_dict(), restored["final_state"].to_dict()
    a.pop("sequence")
    b.pop("sequence")
    assert a == b
    assert normal["records"][0]["payload"]["series"] == restored["records"][0]["payload"]["series"]


def test_default_and_omitted_identity_are_separate():
    from threemind_lab.configuration import default_spec
    from threemind_lab.protocols import RunSpec

    assert default_spec()["activity_readout"]["analysis_version"] == 2
    assert default_spec()["activity_readout"]["interval_us"] == 20000
    assert default_spec()["activity_readout"]["periodic_max_samples"] * 20000 == 1200000
    assert RunSpec().activity_readout.analysis_version == 1
    assert not RunSpec().activity_readout.enabled


def test_budget_failure_is_not_no_activity():
    (r,) = observe([[node(1, 0.1), node(2, 0.2)] for _ in range(21)], config(analysis_version=2, max_series_values=10))
    assert r["censored"] and not r["process"]["coverage_complete"]
    assert r["process"]["raw_activity_seen"]


def test_cli_batch_uses_registered_tools_and_never_overwrites(tmp_path):
    from threemind_runtime.observation_cli import main

    (r,) = observe([[node(1, 0.1)] for _ in range(21)])
    path, manifest, result = (tmp_path / p for p in ("record.json", "batch.json", "result.jsonl"))
    path.write_text(json.dumps(r), encoding="utf-8")
    original = path.read_bytes()
    manifest.write_text(
        json.dumps(
            {
                "schema": "threemind.observation-batch/1",
                "steps": [
                    {"tool": "process", "inputs": {"record": {"path": "record.json"}}},
                    {"tool": "compare", "inputs": {"left": {"path": "record.json"}, "right": {"path": "record.json"}}},
                ],
            }
        ),
        encoding="utf-8",
    )
    main(["batch", "--input", str(manifest), "--output", str(result)])
    rows = [json.loads(r)["result"] for r in result.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["process"]["raw_activity_seen"] and rows[1]["changed_node_count"] == 0
    saved = result.read_bytes()
    with pytest.raises(SystemExit):
        main(["batch", "--input", str(manifest), "--output", str(result)])
    assert result.read_bytes() == saved and path.read_bytes() == original


def test_api_process_comparison_chat_and_new_worker_requirement(database):
    from uuid import uuid4

    from test_api import client_for

    from threemind_lab.database import LOCAL_USER
    from threemind_lab.protocols import RunSpec
    from threemind_runtime.readout_host import ReadoutHost

    engine = create_engine()
    spec = RunSpec(environment="manual", activity_readout=config(analysis_version=2))
    project = database.create_project({"id": LOCAL_USER}, "Process observation test")["id"]
    run = database.create_run(project, "Process copy", spec.model_dump())
    events = []
    host = ReadoutHost(spec, run["id"], 0, record=events.append)
    engine.inject(Stimulus(0, ((1, 0.8), (2, 0.4))))
    host.delivered(delivery(id=str(uuid4())))
    for at in range(0, 2100000, 100000):
        engine.advance_to(at)
        host.observe(engine)
    host.close(engine.time_us, "run_ended")
    database.save_checkpoint(
        project,
        run["id"],
        engine.capture_state(),
        expected_revision=0,
        status="paused",
        context={"protocol": spec.model_dump(), "readouts": host.capture()},
        events=events,
    )
    with database.tx(project) as db:
        features = db.execute("SELECT required_job_features('run',%s,'{}') AS features", (run["id"],)).fetchone()[
            "features"
        ]
    assert "worker.activity_analysis_v2" in features
    with client_for(database) as client:
        base = f"/api/v2/projects/{project}/runs/{run['id']}"
        rows = client.get(base + "/readouts?kind=temporal_readout").json()["rows"]
        current = next(r for r in rows if r["payload"].get("process"))
        assert "timeline" not in current["payload"]["process"]
        rid = current["id"]
        original = client.get(base + f"/readouts/{rid}/export").content
        derived = client.get(base + f"/readouts/{rid}/process").json()
        assert derived["process"]["raw_activity_seen"]
        comparison = client.get(base + f"/readouts/compare?left_id={rid}&right_id={rid}").json()
        assert comparison["changed_node_count"] == 0
        target_ids = ",".join(str(n["node_id"]) for n in derived["nodes"])
        scoped = client.get(base + f"/readouts/{rid}/target", params={"node_ids": target_ids})
        assert scoped.status_code == 200, scoped.text
        assert scoped.json()["process"]["raw_activity_seen"]
        download = client.get(base + f"/readouts/{rid}/target", params={"node_ids": target_ids, "download": True})
        assert "attachment" in download.headers["content-disposition"]
        assert download.json()["source_sha256"] == scoped.json()["source_sha256"]
        assert client.get(base + f"/readouts/{rid}/target", params={"node_ids": "999999999"}).status_code == 422
        response = client.get(base + f"/readouts/{rid}/response", params={"limit": 1})
        assert response.status_code == 200, response.text
        response = response.json()
        assert response["status"] == "response_observed"
        assert len(response["timeline"]) == 1
        assert len(response["selected_event"]["ranking"]) == 1
        assert all("ranking" not in e for e in response["events"])
        full = client.get(base + f"/readouts/{rid}/response?download=true")
        assert full.json()["source_sha256"] == response["source_sha256"]
        assert "attachment" in full.headers["content-disposition"]
        full = full.json()
        selected = full["events"][response["selected_event"]["index"]]
        assert response["selected_event"]["ranking_count"] == len(selected["ranking"])
        if len(selected["ranking"]) > 1:
            page = client.get(base + f"/readouts/{rid}/response?limit=1&rank_offset=1").json()
            assert page["selected_event"]["ranking"][0] == selected["ranking"][1]
        assert client.get(base + f"/readouts/{rid}/response?node_ids=999999999").status_code == 422
        assert client.get(base + f"/readouts/{rid}/response?event_index=999999999").status_code == 422
        from threemind_runtime.observation_tools import analyze_responses

        assert full == analyze_responses(json.loads(original)["payload"])
        assert client.get(base + f"/readouts/{rid}/export").content == original
        assert client.get(base + f"/readouts/{rid}?order=variation").status_code == 200
        chat = client.get(base + "/conversation?passive=false").json()["rows"]
        assert chat[0]["readout"]["process"]["raw_activity_seen"]
        assert "timeline" not in chat[0]["readout"]["process"]
        assert client.post(base + "/commands", json={"kind": "readout_observe", "payload": {}}).status_code == 200
        ops = client.get("/api/v2/operations/catalog").json()["operations"]
        assert {"observation.process", "observation.compare", "observation.target", "observation.response"} <= {
            r["id"] for r in ops
        }


def test_cli_stimulus_free_observation_preserves_model(tmp_path):
    import subprocess
    import sys

    from threemind_runtime.codec import ArtifactCodec

    e = create_engine()
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.4))))
    e.advance_to(100000)
    source = tmp_path / "source.tmind"
    source.write_bytes(ArtifactCodec.encode(e.capture_state()))
    original = source.read_bytes()
    output, evidence = tmp_path / "result.tmind", tmp_path / "observation.jsonl"
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "threemind_runtime.cli",
            "--model",
            str(source),
            "--clock",
            "unbounded",
            "--until-us",
            "500000",
            "--readouts",
            str(evidence),
            "--observe",
            "--export",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    e.advance_to(500000)
    assert ArtifactCodec.decode(output.read_bytes()).digest == e.capture_state().digest
    assert source.read_bytes() == original
    records = [json.loads(line) for line in evidence.read_text(encoding="utf-8").splitlines()]
    assert records[0]["kind"] == "readout_manifest"
    window = next(r["payload"] for r in records if r["kind"] == "temporal_readout")
    assert window["observation_kind"] == "stimulus-free-marker" and window["envelope_id"] is None


def test_queued_no_stimulus_observation_runs_without_creating_inputs(database):
    from threemind_lab.database import LOCAL_USER
    from threemind_lab.protocols import RunSpec
    from threemind_lab.worker import Worker

    spec = RunSpec(
        environment="manual",
        clock="unbounded",
        duration_s=0.2,
        activity_readout=config(analysis_version=2),
        structural_readout={"enabled": False},
    )
    project = database.create_project({"id": LOCAL_USER}, "Observer worker test")["id"]
    run = database.create_run(project, "No-cue window", spec.model_dump())
    command = database.command(project, run["id"], "readout_observe", {})
    database.enqueue(project, "run", run_id=run["id"])
    assert Worker(database).once()
    updated = database.get_run(project, run["id"])
    assert updated["status"] == "completed", updated.get("error")
    with database.tx(project) as db:
        windows = db.execute(
            "SELECT payload FROM events WHERE run_id=%s AND kind='temporal_readout'", (run["id"],)
        ).fetchall()
        assert (
            db.execute("SELECT count(*) AS n FROM input_envelopes WHERE run_id=%s", (run["id"],)).fetchone()["n"] == 0
        )
    assert len(windows) == 1
    assert windows[0]["payload"]["observation_id"] == f"observation:command-{command['id']}"
