import csv
import io
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from threemind_core import Config, StateImage, Stimulus
from threemind_core.resources import COUNTERS, Resources
from threemind_core.spec import MAX_TIME
from threemind_runtime import create_engine
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.store import SQLiteStore


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_causal2_frozen_continuation_and_unlimited_current_projection(backend):
    from threemind_runtime.codec import ArtifactCodec

    fixture = json.loads((Path(__file__).parent / "fixtures/causal2-continuation.json").read_text(encoding="utf-8"))
    before = StateImage.from_dict(fixture["before"])
    assert before.digest == fixture["before_hash"]
    for format in ("json", "tmind"):
        assert ArtifactCodec.decode(ArtifactCodec.encode(before, format)).digest == before.digest
    with pytest.raises(ValueError, match="read-only"):
        create_engine(state=before, backend=backend)


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_topology_capacity_counts_real_rejections_and_preserves_source_order(backend):
    e = create_engine(Config(inhibition=False, max_nodes=3, max_edges=2, propagation_rate=0), backend=backend)
    e.inject(Stimulus(0, ((9, 0.3), (2, 0.8), (5, 0.6), (8, 0.4))))
    e.advance_to(0)
    state = e.capture_state().to_dict()
    assert [n["channel"] for n in state["nodes"]] == [2, 5, 8]
    assert len(state["edges"]) == 2
    assert state["resources"]["node_capacity_rejections"] == "1"
    assert state["resources"]["edge_capacity_rejections"] == "4"
    e.reconfigure(replace(e.config, max_nodes=0, max_edges=0))
    e.inject(Stimulus(1001, ((2, 0.7), (5, 0.8), (12, 0.6))))
    e.advance_to(1001)
    after = e.capture_state().to_dict()
    assert len(after["nodes"]) == 3 and len(after["edges"]) == 2
    assert after["resources"]["node_capacity_rejections"] == "2"
    assert e.life == "active"
    create_engine(state=e.capture_state(), backend=backend)


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_adaptation_allowance_is_shared_by_events_and_propagation_and_survives_pause(backend):
    c = Config(inhibition=False, forgetting_rate=0, edge_adaptation_limit=3)
    e = create_engine(c, backend=backend)
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.7), (3, 0.6))))
    e.inject(Stimulus(1, ((4, 0.8), (5, 0.7))))
    e.advance_to(5001)
    a = e.capture_state().to_dict()
    assert len(a["edges"]) == 3
    assert a["resources"]["adaptations_used"] == 3
    assert a["resources"]["adaptation_budget_skips"] == "5"  # six first pairs -> 3; two more -> 0
    saved = e.capture_state()
    e.reconfigure(c)
    assert e.capture_state().digest == saved.digest
    resumed = create_engine(state=saved, backend=backend)
    # At a lattice boundary the input uses two slots; propagation has only one left.
    for engine in (e, resumed):
        engine.inject(Stimulus(100000, ((4, 0.5), (5, 0.4))))
    for t in (5002, 9001, 100000, 110001, 117001):
        e.advance_to(t)
    resumed.advance_to(117001)
    assert e.capture_state().digest == resumed.capture_state().digest
    b = e.capture_state().to_dict()["resources"]
    assert b["adaptation_period_us"] == "100000" and b["adaptations_used"] == 3
    assert int(b["adaptation_budget_skips"]) > 5
    # A limit change within this period does not refill what was already used.
    e.reconfigure(replace(c, edge_adaptation_limit=1))
    assert e.capture_state().to_dict()["resources"]["adaptations_used"] == 3


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_emission_budget_counts_skips_without_erasing_inflight_or_inhibition(backend):
    e = create_engine(Config(propagation_limit=1), backend=backend)
    e.inject(Stimulus(0, ((1, 0.9), (2, 0.8), (3, 0.7))))
    e.advance_to(100000)
    state = e.capture_state().to_dict()
    assert state["resources"]["propagation_budget_skips"] == "5"
    assert sum(len(q["payload"]["values"]) for q in state["queue"] if q["kind"] == "signal") == 1
    assert any(q["kind"] == "inhibition" for q in state["queue"])
    e.reconfigure(replace(e.config, propagation_limit=0))
    assert e.capture_state().to_dict()["queue"] == state["queue"]
    e.advance_to(200000)
    assert not any(q["kind"] == "signal" for q in e.capture_state().to_dict()["queue"])
    assert int(e.capture_state().to_dict()["resources"]["propagation_budget_skips"]) == 11


def test_resource_accounting_is_strict_and_observing_does_not_refill():
    state = Resources(adaptation_period_us="10000", adaptations_used=2).to_dict()
    ledger = Resources.restore(state, 20001, 10000)
    assert ledger.available_adaptations(20001, 10000, 3) == 3
    assert ledger.to_dict() == state
    for key, value in [
        ("since_us", "20002"),
        ("adaptation_period_us", "10001"),
        ("adaptations_used", True),
        ("node_capacity_rejections", "00"),
        ("counter_overflowed", 1),
    ]:
        with pytest.raises(ValueError):
            Resources.restore(state | {key: value}, 20001, 10000)
    ledger.node_capacity_rejections = str(MAX_TIME)
    ledger.increment("node_capacity_rejections")
    assert ledger.counter_overflowed and ledger.node_capacity_rejections == str(MAX_TIME)
    for value in (-1, 1.5, True, 2**53):
        with pytest.raises(ValueError):
            Config(max_nodes=value)
    assert Config(max_nodes=0).has_budget_limits()


def test_resource_backend_numerics_counters_and_recovery_match():
    config = Config(
        max_nodes=6,
        max_edges=3,
        propagation_limit=1,
        edge_adaptation_limit=4,
        edge_birth_policy="temporal-association",
        local_novelty_gain=0.018,
    )
    engines = [create_engine(config, backend=b) for b in ("reference", "native")]
    for e in engines:
        for i in range(12):
            e.inject(Stimulus(i * 11007, ((i % 8, 0.8), ((i + 2) % 8, 0.4), ((i + 5) % 8, 0.3))))
        e.advance_to(170001)
        before = e.capture_state()
        e.metrics()
        assert e.capture_state().digest == before.digest
        assert create_engine(state=before).capture_state().digest == before.digest
    left, right = [e.capture_state().to_dict() for e in engines]
    assert left["resources"] == right["resources"]
    assert all(int(left["resources"][k]) > 0 for k in COUNTERS)
    for collection in ("nodes", "edges"):
        for a, b in zip(left[collection], right[collection], strict=True):
            for key in a:
                assert (
                    a[key] == pytest.approx(b[key], rel=1e-11, abs=1e-13)
                    if isinstance(a[key], float)
                    else a[key] == b[key]
                )


@pytest.mark.parametrize("format", ["json", "tmind"])
def test_budget_model_is_plastic_without_database_and_preserves_ledger_in_sqlite(tmp_path, format):
    from tests_v2.test_runtime_interop import RUNTIME

    config = Config(max_nodes=5, max_edges=8, propagation_limit=4, edge_adaptation_limit=3)
    e = create_engine(config)
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.7), (3, 0.6))))
    e.inject(Stimulus(71001, ((4, 0.7), (5, 0.6), (6, 0.8))))
    e.advance_to(5001)
    original = e.capture_state()
    model, output, store = tmp_path / f"source.{format}", tmp_path / "result.tmind", tmp_path / "device.sqlite"
    model.write_bytes(ArtifactCodec.encode(original, format))
    command = [
        str(RUNTIME),
        "--model",
        str(model),
        "--clock",
        "unbounded",
        "--until-us",
        "133003",
        "--export",
        str(output),
        "--store",
        str(store),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    e.advance_to(133003)
    assert ArtifactCodec.decode(output.read_bytes()).digest == e.capture_state().digest
    assert SQLiteStore(store).load("default")[1].digest == e.capture_state().digest
    assert ArtifactCodec.decode(model.read_bytes()).digest == original.digest
    assert len(e.capture_state().to_dict()["nodes"]) > len(original.to_dict()["nodes"])


def test_resource_evidence_is_committed_filterable_exact_and_project_scoped(database):
    from test_api import client_for

    from threemind_lab.configuration import default_spec
    from threemind_lab.worker import Worker

    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Budget evidence"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        spec = default_spec() | {
            "environment": "replay",
            "clock": "unbounded",
            "duration_s": 0.17,
            "sample_us": 20000,
            "config": {"max_nodes": 4, "max_edges": 4, "propagation_limit": 2, "edge_adaptation_limit": 3},
            "replay": [Stimulus(i * 11007, ((i, 0.8), (i + 2, 0.6), (i + 5, 0.4))).to_dict() for i in range(6)],
            "structural_readout": {"enabled": False},
            "temporal_readout": {"enabled": False},
        }
        run = client.post(f"{root}/runs", json={"name": "Limited model", "spec": spec}).json()["id"]
        assert Worker(database).once()
        url = f"{root}/runs/{run}"
        assert client.get(url).json()["status"] == "completed"
        response = client.get(f"{url}/resources?limit=2&after=20000&until=100000")
        assert response.status_code == 200, response.text
        page = response.json()
        assert [row["time_us"] for row in page["rows"]] == ["20000", "40000"] and page["more"]
        assert all(isinstance(page["latest"][k], str) for k in COUNTERS)
        second = client.get(f"{url}/resources?after={page['next']}&until=100000").json()
        assert second["rows"][0]["time_us"] == "60000"
        raw = client.get(f"{url}/resources/export?after=20000&until=100000")
        assert raw.status_code == 200, raw.text
        lines = [json.loads(line) for line in raw.text.splitlines()]
        assert lines[0]["selection"]["state_hash"] == client.get(url).json()["state_hash"]
        assert len(lines) == 6 and lines[1:] == page["rows"] + second["rows"]
        exported = client.get(f"{url}/resources/export?after=20000&until=100000&format=csv")
        records = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
        assert len(records) == 5 and records[0]["max_nodes"] == "4" and records[0]["after_us"] == "20000"
        assert records[-1]["adaptation_budget_skips"] == lines[-1]["resources"]["adaptation_budget_skips"]
        assert client.get(f"{url}/resources?after=20&until=19").status_code == 422
        assert client.get(f"{url}/resources/export?after=-1").status_code == 422
        foreign = client.post("/api/v2/projects", json={"name": "Foreign resources"}).json()["id"]
        for suffix in ("resources", "resources/export"):
            assert client.get(f"/api/v2/projects/{foreign}/runs/{run}/{suffix}").status_code == 404
        cp, saved = database.load_checkpoint(project, run)
        state = saved.to_dict()
        exact = str(2**53 + 17)
        state["resources"]["node_capacity_rejections"] = exact
        database.save_checkpoint(
            project, run, StateImage.from_dict(state), expected_revision=cp["revision"], status="paused"
        )
        # With no new observation, latest is still the true new checkpoint, not the old sample.
        after = client.get(f"{url}/resources").json()
        assert after["latest"]["node_capacity_rejections"] == exact
        assert after["rows"][-1]["resources"]["node_capacity_rejections"] != exact
        legacy = json.loads((Path(__file__).parent / "fixtures/causal2-continuation.json").read_text())["before"]
        old_run = database.create_run(project, "Uncounted old control", default_spec())
        database.save_checkpoint(
            project, old_run["id"], StateImage.from_dict(legacy), expected_revision=0, status="paused"
        )
        assert client.get(f"{root}/runs/{old_run['id']}/resources").json()["latest"] is None
