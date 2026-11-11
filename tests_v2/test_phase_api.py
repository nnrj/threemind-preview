import io
import json
import zipfile

from fastapi.testclient import TestClient

from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.protocols import RunSpec
from threemind_lab.worker import Worker


def test_phased_study_trajectories_frozen_commands_and_exports(database):
    with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
        project = client.post("/api/v2/projects", json={"name": "Phase API"}).json()["id"]
        base = f"/api/v2/projects/{project}"
        phases = [
            {"name": "drive", "duration_s": 0.1},
            {"name": "quiet", "duration_s": 0.1},
            {"name": "recovery", "duration_s": 0.1},
        ]
        requested = client.post(
            f"{base}/studies",
            json={
                "name": "Withdrawal",
                "warmup_s": 0.035,
                "seeds": [11, 23],
                "base": {"duration_s": 0.3, "clock": "unbounded", "sample_us": 10000, "phases": phases},
                "arms": [
                    {"name": "drive"},
                    {"name": "withdrawn", "phases": [phases[0], phases[1] | {"input_enabled": False}, phases[2]]},
                ],
            },
        )
        assert requested.status_code == 202, requested.text
        study = requested.json()["params"]["study_id"]
        assert (
            client.post(
                f"{base}/runs",
                json={"name": "Unregistered", "spec": {"study_id": study, "condition": "drive", "block_seed": 11}},
            ).status_code
            == 422
        )
        worker = Worker(database)
        for _ in range(5):
            assert worker.once()
        runs = client.get(f"{base}/runs?study_id={study}").json()
        assert len(runs) == 4 and all(r["status"] == "completed" for r in runs), runs
        with database.tx(project) as db:
            warmups = db.execute("SELECT spec FROM runs WHERE spec->>'study_id' IS NULL").fetchall()
        assert len(warmups) == 2
        assert all(not RunSpec(**r["spec"]).phases for r in warmups)
        plot = client.get(f"{base}/studies/{study}/trajectories?metric=saturated_fraction&buckets=30")
        assert plot.status_code == 200, plot.text
        assert plot.json()["expected_n"] == 2
        assert len(plot.json()["series"]) == 2
        assert any(row["n"] == 2 for row in plot.json()["series"][0]["rows"])
        other = client.post("/api/v2/projects", json={"name": "Other"}).json()["id"]
        assert client.get(f"/api/v2/projects/{other}/studies/{study}/trajectories").status_code == 404
        run = next(r for r in runs if r["spec"]["condition"] == "withdrawn")
        for command in ({"kind": "stimulus", "payload": {"channels": [[1, 0.7]]}}, {"kind": "close_inputs"}):
            assert client.post(f"{base}/runs/{run['id']}/commands", json=command).status_code == 409
        task = client.post(f"{base}/analyses", json={"study_id": study, "control": "drive", "treatment": "withdrawn"})
        assert task.status_code == 202
        assert worker.once()
        result = next(j for j in client.get(f"{base}/jobs").json() if j["id"] == task.json()["id"])
        assert result["status"] == "done", result.get("error")
        csv_result = client.get(f"{base}/artifacts/{result['result']['csv_artifact_id']}")
        assert csv_result.status_code == 200 and "ci95_low" in csv_result.text
        phases = result["result"]["analysis"]["pairs"][0]["phase_evidence"]["treatment"]
        assert phases[1]["complete"] and phases[1]["settling"]["right_censored"]
        export = client.post(f"{base}/runs/{run['id']}/exports", json={"format": "evidence"})
        assert worker.once()
        exported = next(j for j in client.get(f"{base}/jobs").json() if j["id"] == export.json()["id"])
        assert exported["status"] == "done", exported.get("error")
        data = client.get(f"{base}/artifacts/{exported['result']['artifact_id']}").content
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert json.loads(archive.read("phase-evidence.json"))[1]["complete"]
            assert "phase-evidence.json" in json.loads(archive.read("manifest.json"))["files"]
        fork = client.post(f"{base}/runs/{run['id']}/forks", json={"name": "Independent", "inherit": False})
        assert fork.status_code == 201, fork.text
        assert fork.json()["spec"]["study_id"] is None
        assert not fork.json()["spec"]["phases"]
        assert worker.once()
        assert client.get(f"{base}/runs/{fork.json()['id']}").json()["status"] == "completed"
        assert len(client.get(f"{base}/runs?study_id={study}").json()) == 4
