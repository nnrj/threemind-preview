"""Engineering witnesses for selection/routing, not research experiments."""

from dataclasses import fields

import pytest
from fastapi.testclient import TestClient

from threemind_kernels.registry import DEFAULT_KERNEL, kernel_catalog, resolve_kernel
from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.configuration import catalogue, default_spec, validate_configuration
from threemind_lab.database import LOCAL_USER
from threemind_lab.execution import select_execution
from threemind_lab.worker import Worker


def test_all_version_catalogues_are_pure_and_version_owned(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("configuration reading must not create dynamics")

    from threemind_kernels.registry import KernelDescriptor

    monkeypatch.setattr(KernelDescriptor, "create", forbidden)
    assert default_spec()["kernel_id"] == DEFAULT_KERNEL
    for row in kernel_catalog():
        identity = row["kernel_id"]
        catalog = catalogue(kernel_id=identity)
        assert catalog["defaults"]["kernel_id"] == identity
        assert validate_configuration(catalog["defaults"])["valid"]
        config = resolve_kernel(identity).configuration()
        accepted = {field.name for field in fields(config)}
        visible = {field["path"][7:] for field in catalog["fields"] if field["path"].startswith("config.")}
        assert visible <= accepted
        if identity.startswith("threemind.causal/") or identity == "unified-associative":
            assert accepted == visible
        assert row["display_name"] in next(field for field in catalog["fields"] if field["path"] == "kernel_id")["choices"][
            [item[0] for item in next(field for field in catalog["fields"] if field["path"] == "kernel_id")["choices"]].index(identity)
        ][1]
    assert select_execution("unified-associative", default="native") == {"backend": "reference"}
    with pytest.raises(ValueError, match="no automatic fallback"):
        select_execution("unified-associative", {"backend": "native"})


def test_routing_is_explicit_and_auxiliary_worker_cannot_steal_old_jobs(database):
    project = database.create_project({"id": LOCAL_USER}, "Routing engineering witness")["id"]
    with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
        spec = default_spec("unified-associative") | {"environment": "manual"}
        root = f"/api/v2/projects/{project}"
        result = client.post(root + "/runs", json={"name": "Old frame", "spec": spec, "start_immediately": False})
        assert result.status_code == 201, result.text
        run = result.json()
        assert run["execution"] == {"backend": "reference"}
        rejected = client.post(root + "/runs", json={"name": "Wrong backend", "spec": spec,
                                                     "execution": {"backend": "native"}, "start_immediately": False})
        assert rejected.status_code == 422, rejected.text
    # Legacy rows without a host backend remain host-default; the dedicated
    # reference pool must only accept explicitly routed reference work.
    old = database.create_run(project, "Old undecided host", default_spec() | {"environment": "manual"})
    old_job = database.enqueue(project, "run", run_id=old["id"])
    new_job = database.enqueue(project, "run", run_id=run["id"])
    all_features = set(old_job["required_features"]) | set(new_job["required_features"])
    report = {"queue": "runtime", "backend": "reference", "task_family": "kernel-reference",
              "features": {feature: {"state": "available"} for feature in all_features}}
    assert "worker.kernel_unified-associative" in new_job["required_features"]
    assert "worker.backend:reference" in new_job["required_features"]
    assert "worker.backend:reference" not in old_job["required_features"]
    database.announce_worker("reference-only", report)
    assert database.claim("reference-only", capabilities=report)["id"] == new_job["id"]
    assert database.claim("reference-only", capabilities=report) is None


@pytest.mark.parametrize("kernel,backend", [
    (f"threemind.causal/{version}", backend)
    for version in (1, 6, 8) for backend in ("reference", "native")
] + [("unified-associative", "reference")])
def test_historical_kernel_runs_through_lab_and_full_checkpoint(database, kernel, backend):
    from threemind_runtime import create_engine

    project = database.create_project({"id": LOCAL_USER}, "Historical host engineering witness")["id"]
    spec = default_spec(kernel) | {"environment": "manual", "clock": "unbounded", "duration_s": 0.6}
    with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
        root = f"/api/v2/projects/{project}"
        result = client.post(root + "/runs", json={"name": kernel, "spec": spec, "execution": {"backend": backend}})
        assert result.status_code == 201, result.text
        run = result.json()
        # Original anonymous stimulus endpoint is used here; its channel unit
        # is distinct from the old runtime's original text carrier adapter.
        with database.tx(project) as db:
            db.execute("INSERT INTO commands(project_id,run_id,kind,payload) VALUES(%s,%s,'stimulus',%s::jsonb)",
                       (project, run["id"], '{"channels":[[1,0.8],[2,0.6]]}'))
        if kernel == "unified-associative":
            from uuid import uuid4

            from threemind_lab.inputs import submit

            text = submit(database, project, run["id"], {"id": LOCAL_USER}, adapter_id="text-sensor",
                          payload={"text": "A" * 60, "intensity": 1.0}, request_id=uuid4())
            assert text["adapter_version"] == "legacy-unified-text/97d8592"
            assert text["frame_count"] == 3
        worker = Worker(database, backend=backend, name="historical-witness")
        with database.tx(project) as db:
            job = db.execute("SELECT required_features FROM jobs WHERE run_id=%s", (run["id"],)).fetchone()
        worker.capabilities = {"queue": "runtime", "backend": backend,
                               "features": {key: {"state": "available"} for key in job["required_features"]}}
        assert worker.once()
        saved = database.get_run(project, run["id"])
        assert saved["status"] == "completed", saved["error"]
        cp, image = database.load_checkpoint(project, run["id"])
        assert image.to_dict()["dynamics"] == kernel
        restored = create_engine(state=image, backend=backend)
        assert restored.capture_state().digest == image.digest
        graph = client.get(root + f"/runs/{run['id']}/graph").json()
        assert graph["total_nodes"] > 0, graph
        rows = client.get(root + f"/runs/{run['id']}/data/nodes").json()
        assert rows["rows"]
        assert cp["context"]["backend"] == backend
        if kernel == "unified-associative":
            with database.tx(project) as db:
                frames = db.execute("SELECT provenance FROM events WHERE run_id=%s AND kind='input_delivered' ORDER BY id",
                                    (run["id"],)).fetchall()
                epochs = db.execute("SELECT payload FROM events WHERE run_id=%s AND kind='legacy_epoch' ORDER BY id",
                                    (run["id"],)).fetchall()
            assert len(frames) == 4
            assert all(frame["provenance"]["delivery_stage"] == "legacy_input_queue" for frame in frames)
            assert len(epochs) == 6


def test_unified_observation_projection_matches_original_aliases_without_changing_state():
    import copy

    from threemind_kernels.legacy.unified_adapter import LegacyStimulus, UnifiedEngine
    from threemind_lab.legacy_graph import PROJECTION, display_identity, node_view, save, state_nodes

    engine = UnifiedEngine(consciousness_id="observation-engineering-witness")
    engine.inject(LegacyStimulus(0, {2**64 - 1: 0.8, 7: 0.6}))
    engine.advance_to(engine.config.step_us)
    image = engine.capture_state()
    state = image.to_dict()
    original = copy.deepcopy(state)
    expected = engine.observation_nodes()
    for node in expected:
        for key in ("id", "channel"):
            node[key] = display_identity(node[key])
    assert state_nodes(state) == expected
    assert any(node["channel"] == str(2**64 - 1) for node in expected)
    assert all(node["direct"] == node["direct_touch"] for node in expected)
    assert PROJECTION["aliases"]["channel"] == "package.state.receptor_index"

    class ProjectionWriter:
        def __init__(self):
            self.payloads = []

        def execute(self, sql, values):
            if sql.startswith("INSERT INTO"):
                self.payloads.append((values[2], values[4].obj))

    writer = ProjectionWriter()
    save(writer, "project", "run", state)
    saved_nodes = [node for kind, node in writer.payloads if kind == "nodes"]
    assert saved_nodes == expected
    assert [node_view(node) for node in saved_nodes] == expected
    assert state == original
    assert engine.capture_state().digest == image.digest


def test_unified_observation_identity_encoding_preserves_unsafe_ids_and_missing_measurements():
    from threemind_lab.legacy_graph import edge_view, state_nodes

    identity = 2**53 + 1
    state = {
        "nodes": [{"id": identity, "activation": 0.4, "direct_touch": 0.3}],
        "package": {"state": {"receptor_index": {str(2**64 - 1): identity}}},
    }
    node = state_nodes(state)[0]
    assert node["id"] == str(identity)
    assert node["channel"] == str(2**64 - 1)
    assert node["direct_touch"] == node["direct"] == 0.3
    assert node["associative"] is None
    assert node["touches"] is None
    assert edge_view({"source": identity, "target": "字/符&号", "weight": 0.2}) == {
        "source": str(identity), "target": "字/符&号", "weight": 0.2, "touches": None,
    }
    assert state["nodes"][0]["id"] == identity


def test_unified_current_and_historical_graph_queries_use_the_same_read_projection(database):
    import csv
    import io
    import json
    import zipfile

    import pyarrow as pa
    import pyarrow.parquet as pq

    from threemind_kernels.legacy.unified_adapter import LegacyStimulus, UnifiedEngine

    project = database.create_project({"id": LOCAL_USER}, "Observation read engineering witness")["id"]
    spec = default_spec("unified-associative") | {"environment": "manual"}
    run = database.create_run(project, "Projection subject", spec, execution={"backend": "reference"})
    engine = UnifiedEngine(consciousness_id=str(run["id"]))
    engine.inject(LegacyStimulus(0, {2**64 - 1: 0.8, 7: 0.6}))
    engine.advance_to(engine.config.step_us)
    image = engine.capture_state()
    database.save_checkpoint(project, run["id"], image, context={"protocol": spec}, expected_revision=0, status="paused")
    with database.tx(project) as db:
        checkpoint_id = db.execute("SELECT id FROM checkpoints WHERE run_id=%s", (run["id"],)).fetchone()["id"]
    with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
        base = f"/api/v2/projects/{project}/runs/{run['id']}"
        current = client.get(base + "/graph").json()
        historical = client.get(base + f"/graph?checkpoint_id={checkpoint_id}").json()
        assert current["projection"] == historical["projection"]
        current_nodes = {str(node["id"]): node for node in current["nodes"]}
        assert current_nodes == {str(node["id"]): node for node in historical["nodes"]}
        selected = next(node for node in current["nodes"] if node["channel"] == str(2**64 - 1))
        for suffix in ("", f"&checkpoint_id={checkpoint_id}"):
            result = client.get(base + f"/data/nodes?node_id={selected['id']}{suffix}")
            assert result.status_code == 200, result.text
            assert result.json()["rows"] == [selected]
            assert result.json()["projection"] == current["projection"]
        assert current["edges"]
        source = str(current["edges"][0]["source"])
        original_edges = [edge for edge in image.to_dict()["edges"] if str(edge["source"]) == source]
        for suffix in ("", f"&checkpoint_id={checkpoint_id}"):
            result = client.get(base + f"/data/edges?source={source}{suffix}")
            assert result.status_code == 200, result.text
            assert result.json()["rows"]
            assert all(str(edge["source"]) == source for edge in result.json()["rows"])
        export_jobs = []
        for format in ("csv", "jsonl", "parquet"):
            result = client.post(base + "/data-exports", json={"table": "edges", "format": format, "source": source,
                                                             "checkpoint_id": str(checkpoint_id)})
            assert result.status_code == 202, result.text
            export_jobs.append((format, result.json()["id"]))
        with database.tx(project) as db:
            required = {feature for job in db.execute("SELECT required_features FROM jobs WHERE run_id=%s",
                                                       (run["id"],)).fetchall() for feature in job["required_features"]}
        worker = Worker(database, backend="reference", name="read-only-exports-witness")
        worker.capabilities = {"queue": "runtime", "backend": "reference",
                               "features": {key: {"state": "available"} for key in required}}
        for _ in export_jobs:
            assert worker.once()
        with database.tx(project) as db:
            jobs = {str(job["id"]): job for job in db.execute("SELECT * FROM jobs WHERE run_id=%s",
                                                              (run["id"],)).fetchall()}
        for format, job_id in export_jobs:
            job = jobs[job_id]
            assert job["status"] == "done", job["error"]
            download = client.get(f"/api/v2/projects/{project}/artifacts/{job['result']['artifact_id']}")
            assert download.status_code == 200, download.text
            with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
                assert set(archive.namelist()) == {f"edges.{format}", "selection.json"}
                selection = json.loads(archive.read("selection.json"))
                assert selection["state_hash"] == image.digest
                assert selection["selection"]["source"] == source
                assert selection["checkpoint_id"] == str(checkpoint_id)
                assert selection["rows"] == len(original_edges)
                raw = archive.read(f"edges.{format}")
                if format == "jsonl":
                    assert [json.loads(line) for line in raw.splitlines()] == original_edges
                elif format == "csv":
                    exported = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
                    assert len(exported) == len(original_edges)
                    assert all(row["source"] == source for row in exported)
                    assert [float(row["weight"]) for row in exported] == [row["weight"] for row in original_edges]
                else:
                    table = pq.read_table(io.BytesIO(raw))
                    exported = table.to_pylist()
                    assert table.schema.field("source").type == pa.string()
                    assert exported == [{**row, "source": str(row["source"]), "target": str(row["target"])}
                                        for row in original_edges]
                    assert selection["identity_encoding"] == "original-string-or-decimal/1"
        fork = client.post(base + "/forks", json={"name": "Paused observational copy", "inherit": False, "paused": True})
        assert fork.status_code == 201, fork.text
        assert fork.json()["execution"] == {"backend": "reference"}
    assert database.load_checkpoint(project, run["id"])[1].digest == image.digest
    assert engine.capture_state().digest == image.digest
