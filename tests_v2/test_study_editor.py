import copy

import pytest
from test_api import client_for

from threemind_core import Config, Stimulus
from threemind_lab.protocols import Arm, RunSpec, filter_stimulus, resolve_arm
from threemind_lab.study_tools import study_catalogue, validate_study
from threemind_lab.worker import Worker


def protocol():
    return {
        "name": "Runtime condition controls",
        "seeds": [31, 47],
        "warmup_s": 0.025,
        "base": {
            "environment": "ambient",
            "clock": "unbounded",
            "duration_s": 0.1,
            "sample_us": 10000,
            "checkpoint_us": 20000,
        },
        "arms": [
            {"name": "baseline"},
            {
                "name": "receptor gate",
                "runtime_patch": {
                    "body_filter": {"enabled": True, "channel_count": 1},
                    "source_policies": {"environment_bypass_attention": True},
                    "interoception": {"enabled": True},
                },
            },
        ],
    }


def test_study_shared_contract_and_frozen_attention_flag():
    catalogue = study_catalogue()
    assert set(catalogue["defaults"]["base"]["config"]) == set(Config.__dataclass_fields__)
    assert "source_policies" in catalogue["runtime_roots"]
    assert "text_sensor.encoding" in catalogue["shared_paths"]
    assert validate_study(catalogue["defaults"])["valid"]
    configured = resolve_arm(
        RunSpec(environment="ambient"),
        Arm(
            name="typed",
            runtime_patch={"body_filter": {"enabled": True, "channel_count": 1}, "temporal_readout": {"enabled": True}},
        ),
    )
    assert configured.body_filter.enabled and configured.body_filter.channel_count == 1
    assert configured.temporal_readout.enabled
    # Existing queued competition decisions survive phase/bandwidth filtering.
    incoming = Stimulus(10, ((1, 0.5), (2, 0.7)), 1, bypass_attention=True)
    selected = filter_stimulus(RunSpec(max_channels=1), incoming, 0)
    assert selected.bypass_attention and selected.channels == ((2, 0.7),)


@pytest.mark.parametrize(
    "arm,match",
    [
        ({"runtime_patch": {"config": {}}}, "config"),
        ({"runtime_patch": {"duration_s": 2}}, "duration_s"),
        ({"runtime_patch": {"body_filter": {"enabled": "false"}}}, "body_filter"),
        ({"runtime_patch": {"body_filter": {"unknown": 1}}}, "body_filter"),
        ({"runtime_patch": {"body_filter": []}}, "body_filter"),
        ({"body_filter": {"enabled": True}, "runtime_patch": {"body_filter": {"gain": 2}}}, "同时"),
        ({"config_patch": {"step_us": 7000}}, "lattice"),
        ({"runtime_patch": {"text_sensor": {"encoding": "literal-character"}}}, "身份"),
        ({"runtime_patch": {"host_telemetry": {"enabled": True}}}, "实时"),
    ],
)
def test_study_invalid_conditions_rejected(arm, match):
    value = protocol()
    value["arms"][1] = {"name": "invalid", **arm}
    result = validate_study(value)
    assert not result["valid"] and match in str(result["errors"]), result


def test_study_validation_never_ignores_common_or_recording_inputs():
    value = protocol()
    value["base"]["intervention"] = {"nodes": [1]}
    assert not validate_study(value)["valid"]
    value = protocol()
    value["seeds"] = [True, 2]
    assert not validate_study(value)["valid"]
    value = protocol()
    assert not validate_study(value, maximum_duration=0.02)["valid"]
    value["base"]["environment"] = "replay"
    assert not validate_study(value)["valid"]
    value["replay_blocks"] = {"31": [], "47": []}
    assert validate_study(value)["warnings"]


@pytest.mark.parametrize("backend", ["native", "reference"])
def test_study_runtime_patches_execute_and_preview_is_readonly(database, backend):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Graphical study protocol"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        preview = client.post(root + "/studies/validate", json=protocol())
        assert preview.status_code == 200 and preview.json()["valid"], preview.text
        assert client.get(root + "/studies").json() == []
        assert client.get(root + "/jobs").json() == []
        invalid = copy.deepcopy(protocol())
        invalid["arms"][1]["runtime_patch"]["body_filter"]["enabled"] = "false"
        assert client.post(root + "/studies", json=invalid).status_code == 422
        job = client.post(root + "/studies", json=protocol())
        assert job.status_code == 202, job.text
        study_id = job.json()["params"]["study_id"]
        listing = client.get(root + "/study-library?q=Runtime&limit=1").json()
        assert len(listing["rows"]) == 1 and "protocol" not in listing["rows"][0]
        assert client.get(root + f"/studies/{study_id}").json()["protocol"] == preview.json()["protocol"]
        other = client.post("/api/v2/projects", json={"name": "Other research"}).json()["id"]
        assert client.get(f"/api/v2/projects/{other}/studies/{study_id}").status_code == 404
        assert client.get(f"/api/v2/projects/{other}/study-library").json()["rows"] == []
        worker = Worker(database, backend=backend)
        for _ in range(5):
            assert worker.once()
        runs = client.get(root + f"/runs?study_id={study_id}").json()
        assert len(runs) == 4 and all(r["status"] == "completed" for r in runs)
        assert all(r["execution"] == {"backend": backend} for r in runs)
        for parent_id in {r["parent_id"] for r in runs}:
            assert database.get_run(project, parent_id)["execution"] == {"backend": backend}
        summaries = client.get(root + f"/runs?study_id={study_id}&summary=true").json()
        assert len(summaries) == 4 and all("config" not in r["spec"] and "replay" not in r["spec"] for r in summaries)
        for run in runs:
            url = root + f"/runs/{run['id']}"
            if run["spec"]["condition"] == "receptor gate":
                assert run["spec"]["body_filter"]["channel_count"] == 1
                assert run["spec"]["source_policies"]["environment_bypass_attention"]
                records = client.get(url + "/body-tools?limit=100").json()
                assert any(r["source"] == "simulated-interoception" for r in records["rows"])
                # Evidence schema and actual Core gate are checked directly.
                with database.tx(project) as db:
                    evidence = db.execute(
                        "SELECT source_policy FROM input_frames WHERE run_id=%s AND source_policy IS NOT NULL",
                        (run["id"],),
                    ).fetchall()
                assert evidence and any(row["source_policy"].get("bypass_attention") for row in evidence)
            else:
                assert not run["spec"]["body_filter"]["enabled"]
