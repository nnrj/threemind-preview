from uuid import uuid4

import pytest
from test_api import client_for

from threemind_lab.operation_catalog import catalog
from threemind_lab.operation_receipts import HEADER
from threemind_lab.operations_client import OperationsClient


def test_catalog_uses_real_schemas_and_services(database):
    with client_for(database) as http:
        value = http.get("/api/v2/operations/catalog").json()
        rows = {r["id"]: r for r in value["operations"]}
        assert len(rows) == len(value["operations"])
        assert rows["consciousness.create"]["request_receipt"]
        assert rows["stimulus.submit"]["request_body"]["application/json"]["schema"]
        assert not rows["consciousness.list"]["request_receipt"]
        assert not any("/admin/" in r["path"] for r in rows.values())
        assert not any(part in r["path"] for r in rows.values() for part in ("/auth/", "/account/", "/accounts/"))
        assert rows["configuration.defaults"]["path"] == "/api/v2/configuration/defaults"
        assert rows["configuration.templates"]["effect"] == "read"
        client = OperationsClient()
        client.catalogue = catalog(http.app)
        project = str(uuid4())
        valid = client.preflight(
            "consciousness.create",
            {"path": {"project": project}, "body": {"name": "test", "spec": {}}},
            request_id=uuid4(),
        )
        assert valid["coverage"] == "schema_only" and valid["unchecked"]
        with pytest.raises(ValueError):
            client.preflight("consciousness.create", {"path": {"project": "not-uuid"}, "body": {}}, request_id=uuid4())
        with pytest.raises(ValueError, match="stable"):
            client.preflight("consciousness.create", {"path": {"project": project}, "body": {"name": "x"}})
        client.close()


def test_request_replay_changed_arguments_unknown_and_project_boundary(database):
    from threemind_lab.database import LOCAL_USER
    from threemind_lab.operation_receipts import reserve

    with client_for(database) as http:
        project = http.post("/api/v2/projects", json={"name": "receipt test"}).json()["id"]
        path = f"/api/v2/projects/{project}/runs"
        identity = str(uuid4())
        headers = {HEADER: identity}
        body = {"name": "one consciousness", "spec": {"environment": "manual", "clock": "unbounded"}}
        first = http.post(path, headers=headers, json=body)
        assert first.status_code == 201, first.text
        second = http.post(path, headers=headers, json=body)
        assert second.status_code == 201 and second.json()["id"] == first.json()["id"]
        assert second.headers["X-ThreeMind-Replayed"] == "true"
        assert http.post(path, headers=headers, json=body | {"name": "different"}).status_code == 409
        assert len(http.get(path).json()) == 1
        receipt = http.get(f"/api/v2/projects/{project}/operation-receipts/{identity}").json()
        assert receipt["response"]["id"] == first.json()["id"]
        other = http.post("/api/v2/projects", json={"name": "other"}).json()["id"]
        assert http.get(f"/api/v2/projects/{other}/operation-receipts/{identity}").status_code == 404
        ambiguous = uuid4()
        reserve(database, project, LOCAL_USER, ambiguous, "POST", path, body)
        response = http.post(path, headers={HEADER: str(ambiguous)}, json=body)
        assert response.status_code == 409 and response.json()["status"] == "pending"
        assert len(http.get(path).json()) == 1


def test_transport_does_not_accept_other_hosts_or_relative_paths():
    for url in ("file:///tmp", "https://user:pass@example.com", "http://example.com", "https://example.com/path"):
        with pytest.raises(ValueError):
            OperationsClient(url)
    with OperationsClient() as client:
        for path in ("https://example.com", "/api/v2/../secrets", "/outside"):
            with pytest.raises(ValueError):
                client.request("GET", path)
