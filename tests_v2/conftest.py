import os
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(autouse=True)
def explicit_legacy_test_authentication(monkeypatch, request, tmp_path):
    """Legacy identities are injected only here, never through production settings.

    New authentication tests mark ``session_auth`` or pass authentication=session.
    TestClient supplies an actual loopback address rather than making the server
    treat a special client string as an authentication exception.
    """
    from fastapi import HTTPException
    from fastapi.testclient import TestClient

    from threemind_lab import auth, permissions
    from threemind_lab.config import Settings
    from threemind_lab.database import LOCAL_USER

    settings_init = Settings.__init__
    client_init = TestClient.__init__
    real_identity = auth.identity
    legacy_settings = []
    # Tests must never reuse the workstation's migrated storage registry.
    monkeypatch.setenv("THREEMIND_STORAGE_CONTROL", str(tmp_path / "storage-control"))
    monkeypatch.setenv("THREEMIND_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.delenv("THREEMIND_STORAGE_RESTORE", raising=False)
    permissions.actor_context.set(None)

    def initialize_settings(self, *args, **kwargs):
        settings_init(self, *args, **kwargs)
        if (not request.node.get_closest_marker("session_auth") and "authentication" not in kwargs
                and len(args) < 3 and self.mode == "workstation"):
            legacy_settings.append(self)

    def legacy_identity(http_request, *, mutate=False):
        # Explicit credentials always use the real implementation, even in an
        # old test, so this fixture cannot flatten a restricted Bearer to root.
        if (not any(http_request.app.state.settings is value for value in legacy_settings)
                or http_request.headers.get("Authorization") or http_request.cookies.get("tm_session")):
            return real_identity(http_request, mutate=mutate)
        permissions.actor_context.set(None)
        if not http_request.client or http_request.client.host not in ("127.0.0.1", "::1"):
            raise HTTPException(403, "Legacy test identity requires loopback")
        user = permissions.enrich(http_request.app.state.db, {"id": LOCAL_USER})
        user.update(auth_type="test-fixture", source=auth._source(http_request),
                    _request_resources=permissions.request_resources(http_request),
                    _request_action=permissions.request_action(http_request))
        permissions.actor_context.set(user)
        return user

    def initialize_client(self, *args, **kwargs):
        kwargs.setdefault("client", ("127.0.0.1", 50000))
        client_init(self, *args, **kwargs)

    monkeypatch.setattr(Settings, "__init__", initialize_settings)
    monkeypatch.setattr(auth, "identity", legacy_identity)
    monkeypatch.setattr(TestClient, "__init__", initialize_client)


def pytest_configure(config):
    config.addinivalue_line("markers", "session_auth: require normal platform login in host tests")


@pytest.fixture
def database():
    from threemind_lab.bootstrap import provision
    from threemind_lab.database import Database

    # Only the explicitly named isolated test service is used by default.
    port = int(os.environ.get("THREEMIND_TEST_PG_PORT", "55439"))
    params = {"host": "127.0.0.1", "port": port, "user": "threemind_test", "dbname": "postgres", "connect_timeout": 3}
    try:
        probe = psycopg.connect(**params)
        probe.close()
    except psycopg.OperationalError:
        pytest.skip(f"isolated PostgreSQL test cluster on {port} is not running")
    suffix = uuid4().hex[:12]
    name, owner, app = (f"tm2_test_{prefix}_{suffix}" for prefix in ("db", "owner", "app"))
    migration_url, url = provision(params, database=name, owner=owner, app=app)
    db = Database(url)
    db.test_url = url
    db.test_migration_url = migration_url
    yield db
    db.close()
    assert all(n.startswith("tm2_test_") for n in (name, owner, app))
    with psycopg.connect(**params, autocommit=True) as admin:
        admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
        for role in (owner, app):
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
