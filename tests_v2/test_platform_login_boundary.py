"""Production has no local identity switch; old fixture identities stay in pytest."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from threemind_lab import auth, permissions
from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER


@pytest.mark.parametrize("mode", ["workstation", "server"])
def test_production_configuration_rejects_local_identity_switch(monkeypatch, mode):
    with pytest.raises(ValueError, match="requires authenticated sessions"):
        Settings(database_url="postgresql://isolated.invalid/database", mode=mode, authentication="local")
    monkeypatch.setattr("threemind_lab.config.load_env", lambda: None)
    monkeypatch.setenv("THREEMIND_DATABASE_URL", "postgresql://isolated.invalid/database")
    monkeypatch.setenv("THREEMIND_MODE", mode)
    monkeypatch.setenv("THREEMIND_AUTHENTICATION", "local")
    with pytest.raises(ValueError, match="requires authenticated sessions"):
        Settings.from_env()


@pytest.mark.session_auth
def test_loopback_and_http_flags_cannot_replace_platform_login(database):
    settings = Settings(database_url=database.test_url, backend="reference")
    assert settings.authentication == "session"
    with TestClient(create_app(settings, database)) as client:
        assert client.get("/api/v2/me").status_code == 401
        assert client.get(
            "/api/v2/me?authentication=local",
            headers={
                "X-ThreeMind-Authentication": "local",
                "X-ThreeMind-User": str(LOCAL_USER),
                "X-ThreeMind-Execution-Source": "ai",
            },
        ).status_code == 401
        assert client.get(
            "/api/v2/me", headers={"Authorization": "Bearer invalid-local-root"}
        ).status_code == 401


def test_legacy_fixture_never_overrides_an_explicit_bounded_bearer(database):
    # This unmarked legacy fixture exists only in pytest, never in Settings.
    settings = Settings(database_url=database.test_url, backend="reference")
    actor = permissions.enrich(database, {"id": LOCAL_USER})
    project = database.create_project(actor, "bounded bearer fixture")["id"]
    other = database.create_project(actor, "different fixture")["id"]
    signed = auth.delegate(
        database,
        actor,
        name="bounded read",
        source="ai",
        actions=[{"action": "runs.read", "scope": "member_projects"}],
        resources=[{"kind": "project", "id": str(project)}],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    with TestClient(create_app(settings, database)) as client:
        fixture = client.get("/api/v2/me").json()["user"]
        assert fixture["auth_type"] == "test-fixture" and fixture["superadmin"]
        assert settings.authentication == "session"
        header = {"Authorization": "Bearer " + signed["access_token"]}
        real = client.get("/api/v2/me", headers=header).json()["user"]
        assert real["auth_type"] == "delegation" and not real["superadmin"]
        assert real["id"] == str(LOCAL_USER)
        assert real["delegation_id"] == str(signed["delegation"]["id"])
        assert client.get(f"/api/v2/projects/{project}/runs", headers=header).status_code == 200
        assert client.get(f"/api/v2/projects/{other}/runs", headers=header).status_code == 403
        assert client.post(
            f"/api/v2/projects/{project}/runs",
            headers=header,
            json={"name": "must not be created", "spec": {}},
        ).status_code == 403
        assert client.get("/api/v2/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
