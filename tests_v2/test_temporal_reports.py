from uuid import uuid4

import pytest

from threemind_core import Config
from threemind_lab import calibration, report_sources, research_documents
from threemind_lab.database import LOCAL_USER
from threemind_lab.protocols import RunSpec
from threemind_lab.worker import Worker
from threemind_runtime.host import create_engine
from threemind_runtime.readout_session import ReadoutSession
from threemind_runtime.sensory import TextSensor, TextSensorConfig


def fixture(database):
    project = database.create_project({"id": LOCAL_USER}, "Temporal report acceptance")["id"]
    engine = create_engine(Config(propagation_rate=0, activation_decay_enabled=False, inhibition_gain=0))
    spec = RunSpec(environment="manual", clock="unbounded", config=engine.config.to_dict())
    run = database.create_run(project, "Temporal evidence source", spec.model_dump())
    events = []
    host = ReadoutSession(engine, record=events.append, config={"structural_readout": {"enabled": False}})
    host.schedule(TextSensor(1, TextSensorConfig()).frames("甲。"), envelope_id=str(uuid4()))
    host.advance_to(2000000)
    value = next(e["payload"] for e in events if e["kind"] == "temporal_readout")
    database.save_checkpoint(
        project,
        run["id"],
        engine.capture_state(),
        expected_revision=0,
        status="completed",
        context={"protocol": spec.model_dump()},
        events=events,
    )
    return project, run, engine, value


def source(database, project, **selection):
    request = report_sources.request(database, project, LOCAL_USER, {"operation_id": str(uuid4()), **selection})
    assert Worker(database).once()
    result = report_sources.get_source(database, project, request["id"])
    assert result["manifest"] is not None, result["error"]
    return result, report_sources.data_rows(database, project, request["id"])["rows"]


def test_complete_window_node_and_series_sources_use_recorded_values(database):
    project, run, _engine, raw = fixture(database)
    initial = database.load_checkpoint(project, run["id"])[1].digest
    windows, rows = source(database, project, kind="temporal_windows", run_id=str(run["id"]))
    assert len(rows) == 1 and rows[0]["quality"] == "converged"
    assert rows[0]["provenance"]["readout"] == raw
    assert rows[0]["values"]["convergence_seconds"] == (int(raw["end_us"]) - int(raw["delivery_end_us"])) / 1e6
    _nodes, rows = source(database, project, kind="temporal_nodes", run_id=str(run["id"]))
    assert len(rows) == len(raw["nodes"])
    assert [r["values"]["last_activation"] for r in rows] == [n["last_activation"] for n in raw["nodes"]]
    series, rows = source(
        database, project, kind="temporal_series", run_id=str(run["id"]), window_ids=[raw["window_id"]]
    )
    assert [r["values"]["total"] for r in rows] == [p["total"] for p in raw["series"]]
    assert series["manifest"]["coverage"]["rows_are_independent_replicates"] is False
    assert database.load_checkpoint(project, run["id"])[1].digest == initial
    spec = {
        "kind": "record",
        "title": "Temporal report",
        "sources": [str(series["id"]), str(windows["id"])],
        "blocks": [
            {"id": "curve", "type": "chart", "source": str(series["id"]), "metric": "total", "chart": "line"},
            {"id": "data", "type": "table", "source": str(windows["id"]), "metrics": ["convergence_seconds"]},
        ],
    }
    preview = research_documents.render(database, project, spec=spec)
    assert len(preview["blocks"][0]["data"]["rows"]) == len(raw["series"])
    assert "score" in _nodes["manifest"]["metrics"]
    node_template = research_documents.defaults(database, project, _nodes["id"])
    node_preview = research_documents.render(database, project, spec=node_template)
    assert node_preview["blocks"][1]["chart"] == "bar"
    assert len(node_preview["blocks"][1]["data"]["rows"]) == len(raw["nodes"])


def test_temporal_report_exports_pin_full_measurements(database):
    import io
    import json
    import zipfile

    from test_report_exports import artifact
    from test_research_documents import save_body

    from threemind_lab import report_exports

    project, run, _engine, raw = fixture(database)
    series, _rows = source(database, project, kind="temporal_series", run_id=str(run["id"]), window_ids=[raw["window_id"]])
    doc = uuid4()
    spec = research_documents.defaults(database, project, series["id"])
    research_documents.save(database, project, LOCAL_USER, doc, save_body(spec))
    for fmt in ("markdown", "html", "docx", "pdf"):
        requested = report_exports.request(database, project, LOCAL_USER, doc, {
            "operation_id": str(uuid4()), "revision": 1, "format": fmt,
            "include_data": True, "table_rows": 100, "chart_points": 500,
        })
        assert Worker(database).once()
        record = next(r for r in report_exports.listing(database, project, doc)["rows"] if r["id"] == requested["id"])
        assert record["status"] == "done", record["error"]
        assert len(artifact(database, project, record["result"]["artifact_id"])) > 100
        with zipfile.ZipFile(io.BytesIO(artifact(database, project, record["result"]["bundle_artifact_id"]))) as archive:
            rows = [json.loads(line) for line in archive.read(f"sources/{series['id']}/rows.jsonl").splitlines()]
            assert [r["values"]["total"] for r in rows] == [p["total"] for p in raw["series"]]


def test_temporal_experiment_report_includes_unobserved_cases_without_zero_fill(database):
    project, _run, engine, _raw = fixture(database)
    # Explicitly disabled sensory control: every planned probe must remain accounted for.
    spec = RunSpec(environment="manual", text_sensor={"enabled": False})
    controlled = database.create_run(project, "Disabled sensor control", spec.model_dump())
    database.save_checkpoint(
        project,
        controlled["id"],
        engine.capture_state(),
        expected_revision=0,
        status="completed",
        context={"protocol": spec.model_dump()},
    )
    probe = calibration.request(
        database,
        project,
        controlled["id"],
        LOCAL_USER,
        operation_id=uuid4(),
        protocol={"mode": "temporal", "cues": ["甲。", "乙。"]},
    )
    assert Worker(database).once()
    captured, rows = source(database, project, kind="temporal_windows", calibration_id=str(probe["id"]))
    assert len(rows) == 2 and all(r["quality"] == "not_observed" for r in rows)
    assert all(r["values"]["converged"] is None and r["values"]["convergence_seconds"] is None for r in rows)
    assert captured["manifest"]["coverage"]["classifications"]["not_observed"] == 2
    from threemind_lab.report_schema import CaptureSource

    with pytest.raises(ValueError):
        CaptureSource(operation_id=uuid4(), kind="temporal_series", calibration_id=probe["id"])
