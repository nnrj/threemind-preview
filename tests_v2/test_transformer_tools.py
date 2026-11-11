import hashlib
import io
import zipfile
from uuid import uuid4

import httpx
import pytest

torch = pytest.importorskip("torch")
from threemind_transformer.adapter import contract, probability_frame, remote_probabilities
from threemind_transformer.model import TinyTransformer, decode, encode, probabilities, train
from threemind_transformer.protocol import Architecture, Training


def small_protocol(**changes):
    return Training(
        architecture=Architecture(vocabulary=8, context=8, width=16, heads=2, layers=1),
        sequences=[[1, 2, 3], [4, 5, 6]],
        steps=30,
        wall_seconds=30.0,
        **changes,
    )


def test_causal_mask_numeric_roundtrip_and_no_core_feedback():
    from threemind_runtime import create_engine

    torch.set_num_threads(1)
    model = TinyTransformer(Architecture(vocabulary=8, width=16, layers=1, heads=2))
    with torch.inference_mode():
        first = model(torch.tensor([[1, 2, 3]]))
        other = model(torch.tensor([[1, 2, 7]]))
    assert torch.allclose(first[:, :2], other[:, :2], atol=1e-6)
    original = create_engine()
    before = original.capture_state().digest
    raw = encode(model, {"purpose": "test"})
    restored, metadata = decode(raw)
    assert metadata == {"purpose": "test"}
    assert restored.predict([1, 2]) == model.predict([1, 2])
    response = probabilities(model, hashlib.sha256(raw).hexdigest(), [1, 2])
    frame = probability_frame(response, list(range(100, 108)), time_us=2000, intensity=0.3)
    assert frame["metadata"]["external_contribution"] and len(frame["stimulus"].channels) == 8
    assert original.capture_state().digest == before
    assert contract().topology_access == "none"


def test_small_training_learns_the_declared_sequence_and_records_resources():
    model, report = train(small_protocol())
    assert report["status"] == "completed" and report["steps_completed"] == 30
    assert report["loss_history"][-1]["loss"] < report["loss_history"][0]["loss"]
    assert report["training"]["next_token_accuracy"] >= 0.9
    assert report["peak_rss_bytes"] <= 2048 * 1024 * 1024
    assert model.predict([1, 2]).index(max(model.predict([1, 2]))) == 3
    with pytest.raises(ValueError, match="held-out"):
        small_protocol(evaluation=[[1, 2, 3]])
    with pytest.raises(ValueError):
        model.predict([100])


def test_budget_stop_is_explicit_and_malformed_arrays_are_rejected():
    protocol = small_protocol().model_copy(update={"wall_seconds": 0.000001})
    model, report = train(protocol)
    assert report["status"] == "wall_time_budget" and report["steps_completed"] == 0
    raw = encode(model)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    members["0.npy"] = b"invalid"
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, value in members.items():
            archive.writestr(name, value)
    with pytest.raises(ValueError, match="checksum"):
        decode(out.getvalue())


def test_remote_protocol_is_bounded_and_requires_explicit_remote_permission():
    model = TinyTransformer(Architecture(vocabulary=8, width=8, heads=2, layers=1))
    response = probabilities(model, "a" * 64, [1])
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=response))
    assert (
        remote_probabilities("http://127.0.0.1:8997/probabilities", [1], model_hash="a" * 64, transport=transport)
        == response
    )
    with pytest.raises(ValueError, match="allow_remote"):
        remote_probabilities("https://example.com/probabilities", [1], model_hash="a" * 64, transport=transport)
    with pytest.raises(ValueError, match="identity"):
        remote_probabilities("http://127.0.0.1/p", [1], model_hash="b" * 64, transport=transport)


def test_served_probabilities_keep_strict_contract_and_separate_compute_evidence(tmp_path, monkeypatch):
    import uvicorn
    from fastapi.testclient import TestClient

    from threemind_transformer.cli import serve

    model = TinyTransformer(Architecture(vocabulary=8, width=8, heads=2, layers=1))
    file = tmp_path / "served.tmt"
    file.write_bytes(encode(model))
    monkeypatch.setenv("THREEMIND_TRANSFORMER_TOKEN", "local-test-token")

    def run(app, **kwargs):
        with TestClient(app) as client:
            assert client.get("/compute").status_code == 401
            headers = {"Authorization": "Bearer local-test-token"}
            reply = client.post("/probabilities", headers=headers, json={"tokens": [1, 2]})
            assert reply.status_code == 200, reply.text
            assert set(reply.json()) == {
                "schema",
                "model_sha256",
                "request_hash",
                "tokens",
                "probabilities",
                "external_contribution",
                "core_feedback",
            }
            assert reply.headers["X-ThreeMind-Compute-Device"] == "cpu"
            assert client.get("/compute", headers=headers).json()["compute"]["resolved"] == "cpu"
            assert client.post("/probabilities", headers=headers, json={"tokens": [999]}).status_code == 422

    monkeypatch.setattr(uvicorn, "run", run)
    serve(file)


def test_lab_training_prediction_and_stable_request_id(database):
    from test_api import client_for

    from threemind_lab.worker import Worker

    with client_for(database) as client:
        p = client.post("/api/v2/projects", json={"name": "Transformer controls"}).json()["id"]
        base = f"/api/v2/projects/{p}/transformer"
        body = {"request_id": str(uuid4()), "protocol": small_protocol().model_dump()}
        started = client.post(base + "/training", json=body)
        assert started.status_code == 202, started.text
        duplicate = client.post(base + "/training", json=body)
        assert duplicate.json()["id"] == started.json()["id"] and duplicate.json()["replayed"]
        other = client.post("/api/v2/projects", json={"name": "isolated comparator"}).json()["id"]
        other_base = f"/api/v2/projects/{other}/transformer"
        assert client.get(other_base).json()["jobs"] == []
        assert client.post(other_base + "/training", json=body).status_code == 409
        worker = Worker(database)
        assert worker.once()
        result = client.get(base).json()
        job = result["jobs"][0]
        assert job["status"] == "done", job
        model = result["models"][0]["id"]
        assert client.get(other_base).json()["models"] == []
        assert (
            client.post(
                other_base + f"/models/{model}/predictions",
                json={"request_id": str(uuid4()), "query": {"tokens": [1, 2]}},
            ).status_code
            == 404
        )
        prediction = client.post(
            base + f"/models/{model}/predictions", json={"request_id": str(uuid4()), "query": {"tokens": [1, 2]}}
        )
        assert prediction.status_code == 202 and worker.once()
        summary = client.get(base).json()["jobs"][0]["result"]["summary"]
        assert summary["probabilities"].index(max(summary["probabilities"])) == 3
        assert summary["core_feedback"] is False
        run = client.post(
            f"/api/v2/projects/{p}/runs",
            json={
                "name": "explicit external input",
                "spec": {"environment": "manual", "clock": "unbounded", "duration_s": 0.05},
            },
        ).json()
        feedback_url = base + f"/predictions/{prediction.json()['id']}/inputs"
        feedback = {
            "request_id": str(uuid4()),
            "run_id": run["id"],
            "channel_ids": list(range(100, 108)),
            "intensity": 0.1,
        }
        receipt = client.post(feedback_url, json=feedback)
        assert receipt.status_code == 202, receipt.text
        assert receipt.json()["configuration"]["transduction"]["external_contribution"]
        assert client.post(feedback_url, json=feedback).json()["id"] == receipt.json()["id"]
        assert (
            client.post(
                feedback_url, json=feedback | {"request_id": str(uuid4()), "channel_ids": [100] * 8}
            ).status_code
            == 422
        )
        assert worker.once()
        state = database.load_checkpoint(p, run["id"])[1].to_dict()
        assert len(state["nodes"]) == 8
