from dataclasses import asdict
from uuid import uuid4

from test_api import client_for

from threemind_core import Config
from threemind_lab.configuration import default_spec
from threemind_lab.graph_annotations import annotations
from threemind_lab.worker import Worker
from threemind_runtime.sensory import TextSensorConfig


def test_graph_budgets_labels_and_historical_boundary(database, monkeypatch):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Display evidence boundaries"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        spec = default_spec() | {
            "environment": "manual",
            "clock": "unbounded",
            "duration_s": 0.1,
            "text_sensor": asdict(TextSensorConfig(encoding="literal-character", frame_characters=2)),
            "config": asdict(Config(spatial_embedding=True)),
        }
        created = client.post(f"{root}/runs", json={"name": "Labels from carriers", "spec": spec})
        assert created.status_code == 201, created.text
        run_id = created.json()["id"]
        url = f"{root}/runs/{run_id}"
        client.post(f"{url}/commands", json={"kind": "pause"})
        worker = Worker(database)
        assert worker.once()
        before, _ = database.load_checkpoint(project, run_id)
        request_id = str(uuid4())
        accepted = client.post(
            f"{url}/inputs",
            json={
                "adapter_id": "text-sensor",
                "request_id": request_id,
                "payload": {"text": "A汉BA"},
                "delay_us": 5000,
            },
        )
        assert accepted.status_code == 202, accepted.text
        client.post(f"{url}/commands", json={"kind": "resume"})
        assert worker.once()
        cp, image = database.load_checkpoint(project, run_id)
        assert cp["revision"] > before["revision"]
        graph = client.get(f"{url}/graph?label_limit=3&edge_limit=1").json()
        assert graph["annotation_revision"] == cp["revision"]
        assert 0 < len(graph["annotations"]) <= 3
        assert {label for values in graph["annotations"].values() for label in values} == {"A", "汉", "B"}
        assert len(graph["edges"]) == 1 and graph["total_edges"] > 1 and not graph["complete"]
        assert client.get(f"{url}/graph?edge_limit=0").json()["edges"] == []
        assert "annotations" not in client.get(f"{url}/graph").json()
        historical = client.get(f"{url}/graph", params={"checkpoint_id": str(before["id"]), "label_limit": 100})
        assert historical.status_code == 200, historical.text
        assert historical.json()["annotations"] == {}
        # A carrier with a later commit must remain invisible even if a selected time equals its delivery.
        delivered = client.get(f"{url}/inputs/{request_id}").json()["frames"]
        with database.tx(project) as db:
            assert not annotations(db, run_id, before["revision"], cp["time_us"], graph["nodes"], 3)["annotations"]
            assert not annotations(
                db, run_id, cp["revision"], int(delivered[0]["delivered_time_us"]) - 1, graph["nodes"], 3
            )["annotations"]
        geometry = client.get(f"{url}/spatial/graph?edge_limit=1&label_limit=3").json()
        assert geometry["coordinates"] == "causal" and geometry["annotations"] == graph["annotations"]
        assert len(geometry["edges"]) == 1 and all(len(n["position"]) == 3 for n in geometry["nodes"])
        assert client.get(f"{url}/graph?since={cp['revision']}").status_code == 304
        assert client.get(f"{url}/graph?edge_limit=-1").status_code == 422
        other = client.post("/api/v2/projects", json={"name": "Other display project"}).json()["id"]
        assert client.get(f"/api/v2/projects/{other}/runs/{run_id}/graph?label_limit=10").status_code == 404
        with monkeypatch.context() as patch:

            def no_model_decode(*args, **kwargs):
                raise AssertionError("unchanged graph requests must not decode model chunks")

            patch.setattr(database, "load_checkpoint", no_model_decode)
            for suffix, selected in (("graph", before), ("spatial/graph", cp)):
                params = {"checkpoint_id": str(selected["id"]), "since": selected["revision"]}
                assert client.get(f"{url}/{suffix}", params=params).status_code == 304
                assert client.get(f"/api/v2/projects/{other}/runs/{run_id}/{suffix}", params=params).status_code == 404
            assert client.get(f"{url}/spatial/graph?since={cp['revision']}&axes=0,0,1").status_code == 422
        assert database.load_checkpoint(project, run_id)[1].digest == image.digest
