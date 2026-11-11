import hashlib
import json

import pytest

from threemind_transformer.language_protocol import LanguageProtocol
from threemind_transformer.language_senses import ProcessFeatures
from threemind_transformer.language_session import LanguageSession
from threemind_transformer.protocol import digest


def test_legacy_protocol_wire_and_hash_are_unchanged():
    p = LanguageProtocol()
    legacy = p.model_dump()
    assert "feature_layout" not in legacy
    assert p.mapping_hash == digest({k: v for k, v in legacy.items() if k not in ("mode", "maximum_tokens")})
    assert LanguageProtocol.model_validate(legacy).model_dump() == legacy
    with pytest.raises(ValueError, match="requires"):
        LanguageProtocol(feature_layout="unsigned-peak")


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_unprompted_observation_matches_direct_advance_and_restores(backend):
    p = LanguageProtocol(response_us=100000)
    s = LanguageSession(p.model_dump(), backend=backend)
    s.turn("甲是松子。")
    state, context = s.engine.capture_state(), s.context()
    control = LanguageSession(p.model_dump(), image=state, context=context, backend=backend)
    control.reader.advance_to(control.engine.time_us + p.response_us)
    result = s.observe()
    assert result["new_input"] is False
    assert result["text"] is None and result["stimuli"] == []
    assert result["pending_external_before"] == result["pending_external_after"] == 0
    assert s.engine.capture_state().digest == control.engine.capture_state().digest
    restored = LanguageSession(p.model_dump(), image=s.engine.capture_state(), context=s.context(), backend=backend)
    assert s.observe()["after_hash"] == restored.observe()["after_hash"]


def test_new_peak_projection_retains_cancelling_activity_without_mutating_nodes():
    p = LanguageProtocol()
    pairs = {}
    for channel in range(1000):
        h = int.from_bytes(
            hashlib.blake2s(f"language-readout/1:{p.seed}:{channel}".encode(), digest_size=4).digest(), "big"
        )
        bucket, sign = h % p.feature_buckets, bool(h & 0x80000000)
        if (bucket, not sign) in pairs:
            channels = [channel, pairs[(bucket, not sign)]]
            break
        pairs[bucket, sign] = channel
    frame = {"time_us": 0, "nodes": [{"id": i, "channel": c, "activation": 0.5} for i, c in enumerate(channels)]}
    old = ProcessFeatures(p, 0, 500000)
    new = ProcessFeatures(
        LanguageProtocol(schema_id="threemind.language-adapter/2", feature_layout="unsigned-peak"), 0, 500000
    )
    old.observe_frame(frame)
    new.observe_frame(frame)
    assert old.result()["has_activity"] and not any(old.result()["features"])
    assert max(new.result()["features"]) == 0.5
    assert old.result()["trajectory"] == new.result()["trajectory"]
    assert old.result()["mapping_hash"] != new.result()["mapping_hash"]


def test_cli_observe_stream_saves_windows_without_new_input(tmp_path, capsys):
    from threemind_transformer.language_cli import main

    protocol = tmp_path / "protocol.json"
    protocol.write_text(LanguageProtocol(response_us=100000).model_dump_json())
    store = tmp_path / "instance.sqlite"
    main(
        [
            "turn",
            "--protocol",
            str(protocol),
            "--store",
            str(store),
            "--text",
            "甲是松子。",
            "--output",
            str(tmp_path / "first.json"),
            "--backend",
            "reference",
        ]
    )
    target = tmp_path / "stream.jsonl"
    main(["observe", "--store", str(store), "--windows", "2", "--output", str(target), "--backend", "reference"])
    rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    assert [r["revision"] for r in rows] == [2, 3]
    assert all(r["stimuli"] == [] and not r["new_input"] for r in rows)
    with pytest.raises(FileExistsError):
        main(["observe", "--store", str(store), "--output", str(target)])


def test_unprompted_api_and_operation_parity(database):
    from uuid import uuid4

    from fastapi.testclient import TestClient

    from threemind_lab.api import create_app
    from threemind_lab.config import Settings
    from threemind_lab.worker import Worker

    with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
        project = client.post("/api/v2/projects", json={"name": "Unprompted observation"}).json()["id"]
        base = f"/api/v2/projects/{project}/language"
        run = client.post(
            base + "/sessions", json={"request_id": str(uuid4()), "protocol": {"response_us": 100000}}
        ).json()["run_id"]
        worker = Worker(database, name="observation-test")
        assert worker.once()
        assert (
            client.post(
                base + f"/sessions/{run}/turns",
                json={"request_id": str(uuid4()), "expected_revision": 1, "text": "松子"},
            ).status_code
            == 202
        )
        assert worker.once()
        request = {"request_id": str(uuid4()), "expected_revision": 2}
        response = client.post(base + f"/sessions/{run}/observations", json=request)
        assert response.status_code == 202, response.text
        assert client.post(base + f"/sessions/{run}/observations", json=request).json()["replayed"]
        old_capabilities = json.loads(json.dumps(worker.capabilities))
        old_capabilities["features"].pop("worker.language_observation_v1", None)
        assert database.claim("old-language-worker", capabilities=old_capabilities, max_active=1) is None
        assert worker.once()
        row = client.get(base + f"/sessions/{run}/turns").json()["rows"][0]
        assert row["status"] == "done", row
        assert row["result"]["new_input"] is False and row["result"]["text"] is None
        assert row["result"]["revision"] == 3
        operations = {r["id"] for r in client.get("/api/v2/operations/catalog").json()["operations"]}
        assert "language.observe" in operations
        new = client.post(
            base + "/sessions",
            json={
                "request_id": str(uuid4()),
                "protocol": {
                    "schema_id": "threemind.language-adapter/2",
                    "feature_layout": "unsigned-peak",
                    "response_us": 100000,
                },
            },
        )
        assert new.status_code == 202, new.text
        old_capabilities["features"].pop("worker.language_projection_v2", None)
        assert database.claim("old-language-worker", capabilities=old_capabilities, max_active=1) is None
        assert worker.once()
