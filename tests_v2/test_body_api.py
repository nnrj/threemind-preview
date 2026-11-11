import csv
import io
import json
from copy import deepcopy

from test_api import client_for

from threemind_lab.configuration import catalogue
from threemind_lab.worker import Worker


def test_body_runtime_history_raw_encoding_filters_full_exports_and_fork(database):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Body evidence"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        spec = {
            "environment": "ambient",
            "clock": "unbounded",
            "duration_s": 0.35,
            "sample_us": 10000,
            "checkpoint_us": 50000,
            "ambient_field": {"transient_rate_per_s": 0},
            "body_filter": {"enabled": True, "sample_us": 200000, "channel_count": 1, "noise": 0},
            "interoception": {"enabled": True, "sample_us": 100000},
        }
        response = client.post(f"{root}/runs", json={"name": "Body filter", "spec": spec})
        assert response.status_code == 201, response.text
        run = response.json()["id"]
        url = f"{root}/runs/{run}"
        assert client.get(f"{url}/body-tools").status_code == 404
        worker = Worker(database)
        assert worker.once()
        status = client.get(url).json()
        assert status["status"] == "completed", status.get("error")
        data = client.get(f"{url}/body-tools?limit=2").json()
        assert data["more"] and data["status"]["body_filter"]["counters"]["sampling_filtered"] == 2
        assert data["status"]["interoceptive_samples"] == 4
        assert "rng" not in data["status"]["body_filter"]
        rows = [*data["rows"]]
        more = data
        while more["more"]:
            more = client.get(
                f"{url}/body-tools?checkpoint_id={data['checkpoint_id']}&limit=2&before={more['next']}"
            ).json()
            rows.extend(more["rows"])
        assert len({r["frame_id"] for r in rows}) == len(rows) == 8
        ambient = [r for r in rows if r["source"] == "ambient-fixture"]
        assert all(len(r["raw"]["channels"]) == 3 for r in ambient)
        assert sum(r["status"] == "filtered" and r["reason"] == "body_sampling" for r in ambient) == 2
        assert all(r["stimulus"]["channels"] == [] for r in ambient if r["reason"] == "body_sampling")
        passed = [r for r in ambient if r["transduction"]["passed_channels"]]
        assert all(len(r["stimulus"]["channels"]) == 1 and r["stimulus"] != r["raw"] for r in passed)
        assert all(r["transduction"] is None for r in rows if r["source"] == "simulated-interoception")
        selected = client.get(f"{url}/checkpoint-history").json()["rows"][-1]
        old = client.get(f"{url}/body-tools?checkpoint_id={selected['id']}").json()
        # Earlier checkpoints must not reveal later delivery or input selection.
        assert any(r["status"] == "scheduled" for r in old["rows"])
        assert all(r["input_gate"] is None for r in old["rows"] if r["status"] == "scheduled")
        filtered = client.get(f"{url}/body-tools?source=ambient-fixture&after_us=200000&until_us=300000").json()
        assert len(filtered["rows"]) == 2
        raw = client.get(f"{url}/body-tools/export?checkpoint_id={data['checkpoint_id']}&format=jsonl")
        records = [json.loads(line) for line in raw.text.splitlines()]
        assert len(records) == 9 and records[0]["state_hash"] == data["state_hash"]
        csv_data = client.get(f"{url}/body-tools/export?source=ambient-fixture&format=csv")
        exported = list(csv.DictReader(io.StringIO(csv_data.content.decode("utf-8-sig"))))
        assert len(exported) == 4 and json.loads(exported[0]["raw"])["channels"]
        other = client.post("/api/v2/projects", json={"name": "Other"}).json()["id"]
        assert client.get(f"/api/v2/projects/{other}/runs/{run}/body-tools").status_code == 404
        assert client.get(f"{url}/body-tools?source=unknown").status_code == 422
        assert client.get(f"{url}/body-tools?after_us=2&until_us=1").status_code == 422
        # Ordinary continuation carries body state; new inherited birth starts a new external context.
        fork = client.post(f"{url}/forks", json={"name": "Continuation"})
        assert fork.status_code == 201, fork.text
        cp = database.load_checkpoint(project, fork.json()["id"])[0]
        assert cp["context"]["body_tools"]["body_filter"]["counters"] == data["status"]["body_filter"]["counters"]
        new_birth = client.post(f"{url}/forks", json={"name": "New development", "inherit": True}).json()
        assert "body_tools" not in database.load_checkpoint(project, new_birth["id"])[0]["context"]


def test_body_study_shared_external_origin_and_graphical_contract(database):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Body study"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        protocol = {
            "name": "Matched body contrast",
            "warmup_s": 0.15,
            "seeds": [11, 23],
            "base": {
                "environment": "ambient",
                "clock": "unbounded",
                "duration_s": 0.2,
                "body_filter": {"enabled": True, "channel_count": 1},
            },
            "arms": [{"name": "filtered"}, {"name": "unfiltered", "body_filter": {"enabled": False}}],
        }
        created = client.post(f"{root}/studies", json=protocol)
        assert created.status_code == 202, created.text
        worker = Worker(database)
        assert worker.once()
        study = created.json()["params"]["study_id"]
        arms = client.get(f"{root}/runs?study_id={study}").json()
        assert len(arms) == 4
        snapshots = [database.load_checkpoint(project, r["id"])[0]["context"] for r in arms]
        for seed in (11, 23):
            pair = [context for context in snapshots if context["body_tools"]["seed"] == seed]
            assert pair[0]["body_tools"] == pair[1]["body_tools"]
            assert pair[0]["paired_origin_hash"] == pair[1]["paired_origin_hash"]
        for _ in arms:
            assert worker.once()
        for r in client.get(f"{root}/runs?study_id={study}").json():
            assert r["status"] == "completed", r.get("error")
            records = client.get(f"{root}/runs/{r['id']}/body-tools?source=ambient-fixture").json()["rows"]
            encoded = {len(row["stimulus"]["channels"]) for row in records}
            assert encoded == ({1} if r["spec"]["condition"] == "filtered" else {3})
        fields = [f for f in catalogue()["fields"] if f["group"] in ("ambient_field", "body_filter", "interoception")]
        assert len(fields) == 20
        bad = deepcopy(catalogue()["defaults"])
        bad["ambient_field"].update(lifetime_min_us=100, lifetime_max_us=99)
        response = client.post(f"{root}/configuration/validate", json={"spec": bad})
        assert response.json()["errors"], response.text
