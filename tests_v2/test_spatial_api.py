import csv
import io
import json
from copy import deepcopy
from pathlib import Path

from test_api import client_for

from threemind_core import Config, StateImage, Stimulus
from threemind_lab.configuration import catalogue, default_spec
from threemind_runtime import create_engine


def test_spatial_checkpoint_history_configuration_projection_and_complete_exports(database):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Spatial evidence"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        spec = default_spec() | {
            "environment": "manual",
            "config": {"spatial_embedding": True, "spatial_radius": 100, "inhibition": False},
        }
        run = client.post(f"{root}/runs", json={"name": "Developmental geometry", "spec": spec}).json()["id"]
        url = f"{root}/runs/{run}"
        assert client.get(f"{url}/checkpoint-history").json()["rows"] == []
        engine = create_engine(Config(**spec["config"]))
        engine.inject(Stimulus(0, tuple((i, 0.8) for i in range(20))))
        engine.advance_to(1000)
        database.save_checkpoint(
            project, run, engine.capture_state(), expected_revision=0, status="paused", context={"protocol": spec}
        )
        # This fixture installs a paused state directly instead of executing the creation job.
        with database.tx(project) as db:
            db.execute("UPDATE jobs SET status='done' WHERE run_id=%s", (run,))
        # save_checkpoint returns the committed row; history fixes its identity even after edits.
        old = client.get(f"{url}/checkpoint-history").json()["rows"][0]
        old_image = database.load_checkpoint(project, run, old["id"])[1]
        page = client.get(f"{url}/spatial?checkpoint_id={old['id']}&limit=3").json()
        assert len(page["nodes"]) == 3 and len(page["edges"]) == 3
        assert page["nodes_more"] and page["edges_more"]
        assert page["summary"]["neighbor_edges"] == 380 and page["summary"]["clusters"] == 1
        assert page["time_us"] == "1000" and page["state_time_us"] == "0"
        second = client.get(
            f"{url}/spatial?checkpoint_id={old['id']}&node_after={page['nodes_next']}&edge_after={page['edges_next']}&limit=3"
        ).json()
        assert second["nodes"][0]["id"] == 4 and second["edges"][0] != page["edges"][0]
        model = client.get(url).json()
        changed = deepcopy(model["spec"])
        changed["config"].update(spatial_dimensions=4, spatial_radius=0.01)
        edited = client.put(
            f"{url}/configuration",
            json={"name": model["name"], "expected_revision": model["revision"], "spec": changed},
        )
        assert edited.status_code == 200, edited.text
        latest = client.get(f"{url}/spatial").json()
        assert latest["revision"] == 2 and latest["summary"]["neighbor_edges"] == 0
        assert latest["summary"]["parameters"]["spatial_dimensions"] == 4
        assert client.get(url).json()["metrics"]["spatial"]["neighbor_edges"] == 0
        assert database.load_checkpoint(project, run, old["id"])[1].digest == old_image.digest
        old_again = client.get(f"{url}/spatial?checkpoint_id={old['id']}&limit=3").json()
        assert old_again == page
        assert latest["nodes"][0]["position"][:3] == page["nodes"][0]["position"]
        graph = client.get(f"{url}/spatial/graph?checkpoint_id={old['id']}&axes=2,0,-1&limit=3").json()
        assert graph["revision"] == 1 and not graph["complete"] and graph["coordinates"] == "causal"
        coords = page["nodes"][0]["position"]
        assert graph["nodes"][0]["position"] == [coords[2], coords[0], 0]
        assert len(graph["edges"]) == 6
        assert client.get(f"{url}/spatial/graph?checkpoint_id={old['id']}&since=1").status_code == 304
        for axes in ("0,0,1", "3,1,2", "-1,-1,-1", "x,0,1", "0,1"):
            assert client.get(f"{url}/spatial/graph?checkpoint_id={old['id']}&axes={axes}").status_code == 422
        history = client.get(f"{url}/checkpoint-history?limit=1&after_us=1000&until_us=1000").json()
        assert history["more"] and history["rows"][0]["revision"] == 2
        older = client.get(f"{url}/checkpoint-history?limit=1&before={history['next']}").json()
        assert older["rows"][0]["id"] == old["id"] and not older["more"]
        for kind, count in (("nodes", 20), ("edges", 380)):
            exported = client.get(f"{url}/spatial/export?checkpoint_id={old['id']}&records={kind}&format=csv")
            assert exported.status_code == 200, exported.text
            records = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
            assert len(records) == count and all(r["state_hash"] == old["state_hash"] for r in records)
            assert json.loads(records[0]["parameters"])["spatial_dimensions"] == 3
            if kind == "nodes":
                assert json.loads(records[0]["position"]) == coords and float(records[0]["activation"]) > 0
            else:
                assert float(records[0]["weight"]) > 0 and float(records[0]["distance"]) == page["edges"][0]["distance"]
        lines = [
            json.loads(line) for line in client.get(f"{url}/spatial/export?checkpoint_id={old['id']}").text.splitlines()
        ]
        assert len(lines) == 401 and lines[0]["selection"]["checkpoint_id"] == old["id"]
        other = client.post("/api/v2/projects", json={"name": "Unrelated geometry"}).json()["id"]
        for path in ("spatial", "spatial/graph", "spatial/export", "checkpoint-history"):
            assert client.get(f"/api/v2/projects/{other}/runs/{run}/{path}").status_code == 404


def test_geometry_is_unavailable_for_old_version_and_accessible_to_readonly_member(database):
    from threemind_lab import auth

    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Old spatial contract"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        run = client.post(f"{root}/runs", json={"name": "Old version", "spec": default_spec()}).json()["id"]
        control = json.loads((Path(__file__).parent / "fixtures/causal5-continuation.json").read_text(encoding="utf-8"))
        database.save_checkpoint(
            project, run, StateImage.from_dict(control["before"]), expected_revision=0, status="paused"
        )
        url = f"{root}/runs/{run}"
        assert client.get(f"{url}/spatial").json()["supported"] is False
        assert client.get(f"{url}/spatial/graph").status_code == 422
    viewer = auth.create_user(database, "spatial-viewer", "isolated spatial viewer secret")
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (project, viewer["id"]))
    with client_for(database, "server") as client:
        client.post("/api/v2/login", json={"username": "spatial-viewer", "password": "isolated spatial viewer secret"})
        assert client.get(f"{url}/spatial").status_code == 200
        assert client.get(f"{url}/spatial/export").status_code == 200
    fields = {f["path"]: f for f in catalogue()["fields"]}
    for key in (
        "spatial_embedding",
        "spatial_dimensions",
        "neighborhood_enabled",
        "spatial_radius",
        "spatial_competition_rate",
    ):
        assert fields[f"config.{key}"]["group"] == "spatial"
    assert fields["config.seed"]["immutable"]
