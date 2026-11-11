import json
from uuid import uuid4

import psycopg
import pytest
from test_api import client_for
from test_devices import connect, packet, setup

from threemind_core import Stimulus
from threemind_lab.database import migrate
from threemind_lab.input_cycle import RuntimeInputs
from threemind_lab.protocols import RunSpec
from threemind_lab.worker import Worker
from threemind_runtime import ArtifactCodec, create_engine
from threemind_runtime.network import decode_frames
from threemind_runtime.network_wiring import MAX_WIRING_BYTES, make_wiring, read_wiring, validate_wiring
from threemind_runtime.profile import profile_from_spec


def test_wiring_roundtrip_rejects_corruption_ambiguity_and_unsupported_identity():
    wiring = make_wiring(37, uuid4())
    assert read_wiring(json.dumps(wiring)) == validate_wiring(wiring) == wiring
    for altered in (
        wiring | {"sensory_seed": True},
        wiring | {"sensory_seed": 38},
        wiring | {"wiring_id": str(uuid4())},
        wiring | {"protocol": "threemind-network/1"},
        wiring | {"token": "not-a-wiring-field"},
        wiring | {"sha256": "0" * 64},
    ):
        with pytest.raises(ValueError):
            validate_wiring(altered)
    for raw in (
        json.dumps(wiring)[:-1] + ',"sensory_seed":37}',
        "[]",
        "null",
        b"x" * (MAX_WIRING_BYTES + 1),
    ):
        with pytest.raises(ValueError):
            read_wiring(raw)


def test_learned_model_import_new_binding_and_credentials_preserve_dynamics(database):
    with client_for(database) as client:
        project, run, url, root, binding = setup(client)
        token, identity = binding["token"], binding["device"]["id"]
        response = client.get(url + f"/devices/{identity}/wiring")
        assert response.status_code == 200
        assert ".wiring.json" in response.headers["content-disposition"]
        wiring = read_wiring(response.content)
        assert wiring["wiring_id"] == identity
        assert token not in response.text
        session = connect(client, root, token).json()["session"]["id"]
        assert (
            client.post(
                root + f"/sessions/{session}/packets", headers={"Authorization": "Bearer " + token}, json=packet()
            ).status_code
            == 202
        )
        assert Worker(database).once()
        _, initial = database.load_checkpoint(project, run)
        assert len(initial.to_dict()["nodes"]) == 2
        original_spec = client.get(url).json()["spec"]
        raw = ArtifactCodec.encode(initial, "tmind", profile=profile_from_spec(original_spec))
        # A new database project/deployment identity and credential reuse learned receptors.
        other = client.post("/api/v2/projects", json={"name": "Imported deployment"}).json()["id"]
        imported = client.post(f"/api/v2/projects/{other}/imports", files={"file": ("model.tmind", raw)})
        assert imported.status_code == 201, imported.text
        next_run = imported.json()["id"]
        next_url = f"/api/v2/projects/{other}/runs/{next_run}"
        reused = client.post(
            next_url + "/devices",
            json={
                "name": "New hardware",
                "wiring": wiring,
                "configuration": {"modulation": True},
            },
        )
        assert reused.status_code == 201, reused.text
        reuse = reused.json()
        assert reuse["device"]["id"] != identity and reuse["token"] != token
        assert reuse["device"]["wiring_id"] == wiring["wiring_id"]
        assert client.get(next_url + f"/devices/{reuse['device']['id']}/wiring").json() == wiring
        next_root = f"/api/v2/network/{other}/{next_run}/{reuse['device']['id']}"
        next_session = connect(client, next_root, reuse["token"]).json()["session"]["id"]
        stimulus = packet(when=int(initial.to_dict()["time_us"]) + 1000)
        receipt = client.post(
            next_root + f"/sessions/{next_session}/packets",
            headers={"Authorization": "Bearer " + reuse["token"]},
            json=stimulus,
        )
        assert receipt.status_code == 202, receipt.text
        spec = RunSpec(**client.get(next_url).json()["spec"])
        _, imported_state = database.load_checkpoint(other, next_run)
        assert imported_state.digest == initial.digest
        actual = create_engine(state=imported_state)
        reference = create_engine(state=initial)
        host = RuntimeInputs(database, other, next_run, actual, spec, {}, 0)
        admitted = host.accepted(receipt.json()["envelope_id"])
        assert not admitted.get("rejected"), admitted
        for frame in decode_frames(stimulus["frames"], seed=wiring["sensory_seed"], wiring_id=identity)[0]:
            reference.inject(Stimulus.from_dict(frame))
        for time in (81000, 85000, 100000):
            actual.advance_to(time)
            reference.advance_to(time)
            assert actual.capture_state().digest == reference.capture_state().digest
        assert database.load_checkpoint(project, run)[1].digest == initial.digest
        control = client.post(
            next_root + f"/sessions/{next_session}/packets",
            headers={"Authorization": "Bearer " + reuse["token"]},
            json={
                "protocol": wiring["protocol"],
                "type": "modulation",
                "sequence": "1",
                "value": {"gain": 0.8},
            },
        )
        assert control.status_code == 202, control.text
        with database.tx(other) as db:
            payload = db.execute(
                "SELECT payload FROM commands WHERE id=%s", (control.json()["command_id"],)
            ).fetchone()["payload"]
            assert payload["source"] == f"remote:{identity}"
            assert payload["device"]["device_id"] == reuse["device"]["id"]
            assert payload["device"]["wiring_id"] == identity
        # Credential changes cannot rewrite already scheduled stimuli or the manifest.
        queued = actual.capture_state().digest
        rotated = client.post(next_url + f"/devices/{reuse['device']['id']}/rotate").json()
        assert rotated["device"]["wiring_id"] == identity
        assert client.get(next_url + f"/devices/{reuse['device']['id']}/wiring").json() == wiring
        assert actual.capture_state().digest == queued
        assert connect(client, next_root, reuse["token"]).status_code == 403
        assert connect(client, next_root, rotated["token"]).status_code == 201


def test_wiring_validation_duplicate_binding_seed_and_project_boundaries(database):
    with client_for(database) as client:
        project, run, url, _root, binding = setup(client)
        device = binding["device"]
        wiring = client.get(url + f"/devices/{device['id']}/wiring").json()
        assert client.post(url + "/devices/wiring/validate", json=wiring).json() == {"valid": True, "wiring": wiring}
        assert client.post(url + "/devices", json={"name": "Duplicate", "wiring": wiring}).status_code == 409
        wrong_seed = make_wiring(wiring["sensory_seed"] + 1, uuid4())
        for value in (wrong_seed, wiring | {"sha256": "0" * 64}):
            assert client.post(url + "/devices/wiring/validate", json=value).status_code in (409, 422)
            assert client.post(url + "/devices", json={"name": "Wrong", "wiring": value}).status_code in (409, 422)
        duplicate = json.dumps(wiring)[:-1] + ',"sensory_seed":20260724}'
        assert client.post(url + "/devices/wiring/validate", content=duplicate).status_code == 422
        assert client.post(url + "/devices/wiring/validate", content=b"x" * (MAX_WIRING_BYTES + 1)).status_code == 422
        assert (
            client.put(
                url + f"/devices/{device['id']}",
                json={
                    "name": "Rewire",
                    "configuration": device["configuration"],
                    "enabled": True,
                    "wiring": make_wiring(1, uuid4()),
                },
            ).status_code
            == 422
        )
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM device_bindings WHERE run_id=%s", (run,)).fetchone()["n"] == 1
        with pytest.raises(psycopg.errors.CheckViolation), database.tx(project) as db:
            db.execute("UPDATE device_bindings SET wiring_id=%s WHERE id=%s", (uuid4(), device["id"]))
        foreign = client.post("/api/v2/projects", json={"name": "Unrelated"}).json()["id"]
        assert client.get(url.replace(project, foreign) + f"/devices/{device['id']}/wiring").status_code == 404
        assert client.post(url.replace(project, foreign) + "/devices/wiring/validate", json=wiring).status_code == 404


def test_schema_40_upgrade_preserves_wiring_across_forced_rls_projects(database):
    with client_for(database) as client:
        entries = [setup(client) for _ in range(2)]
        with psycopg.connect(database.test_migration_url) as db:
            assert db.info.dbname.startswith("tm2_test_db_")
            from migration_helpers import remove_observer_schema

            remove_observer_schema(db)
            db.execute("DROP TRIGGER device_wiring_immutable ON tm2.device_bindings")
            db.execute("DROP FUNCTION tm2.preserve_device_wiring()")
            db.execute("ALTER TABLE tm2.device_bindings DROP COLUMN wiring_id")
            db.execute("DELETE FROM tm2.schema_version WHERE version=41")
        migrate(database.test_migration_url)
        migrate(database.test_migration_url)
        for project, _run, url, _root, binding in entries:
            devices = client.get(url + "/devices").json()
            assert len(devices) == 1 and devices[0]["wiring_id"] == binding["device"]["id"]
            with database.tx(project) as db:
                assert db.execute("SELECT count(*) AS n FROM device_bindings").fetchone()["n"] == 1
                flags = db.execute(
                    "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='device_bindings'::regclass"
                ).fetchone()
                assert flags["relrowsecurity"] and flags["relforcerowsecurity"]
