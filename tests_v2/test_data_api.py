import hashlib
import json
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from threemind_lab.ai_secrets import SecretBox
from threemind_lab.blob_store import BlobStore
from threemind_lab.config import Settings
from threemind_lab.data_api import register
from threemind_lab.database import Forbidden, NotFound
from threemind_lab.host_receipts import inspect, reserve
from threemind_lab.operation_catalog import catalog
from threemind_lab.operation_receipts import HEADER
from threemind_lab.operation_receipts import register as receipts
from threemind_lab.research_storage import ResearchStorage
from threemind_lab.storage_files import StorageConflict, atomic_json
from threemind_lab.storage_migration import MigrationService


@pytest.fixture
def facade(tmp_path, monkeypatch):
    actor = {
        "id": uuid4(),
        "admin": True,
        "enabled": True,
        "username": "fixture",
        "csrf": "fixture-csrf",
        "role": "owner",
    }
    storage = ResearchStorage(tmp_path / "control", repository_root=tmp_path)
    blobs = BlobStore(storage, secret_box=SecretBox((Fernet.generate_key().decode(),)))

    class DB:
        def __init__(self):
            self.blobs = blobs
            self.checkpoint_backend = "database"

        @contextmanager
        def tx(self, *_args, **_kwargs):
            yield self

        def execute(self, *_args):
            return SimpleNamespace(fetchone=lambda: actor)

    app = FastAPI()
    app.state.db = DB()
    app.state.settings = Settings("postgresql://fixture", docs_root=tmp_path)

    @app.exception_handler(ValueError)
    async def invalid(_, error):
        return JSONResponse({"detail": str(error)}, 422)

    @app.exception_handler(NotFound)
    async def missing(_, error):
        return JSONResponse({"detail": str(error)}, 404)

    @app.exception_handler(Forbidden)
    async def forbidden(_, error):
        return JSONResponse({"detail": str(error)}, 403)

    def access(request, project, *, write=False, owner=False):
        from threemind_lab.auth import identity

        user = identity(request, mutate=write or owner)
        if str(project) != "00000000-0000-0000-0000-000000000001":
            raise Forbidden("fixture project")
        if owner and user["role"] != "owner":
            raise Forbidden("fixture project owner required")
        return user

    class MigrationFixture(MigrationService):
        def __init__(self, storage):
            super().__init__(storage, min_free_bytes=0)

    monkeypatch.setattr("threemind_lab.data_api.MigrationService", MigrationFixture)
    receipts(app, access)
    register(app, access)
    with TestClient(app) as client:
        yield SimpleNamespace(app=app, client=client, storage=storage, actor=actor, root=tmp_path)


def test_host_admin_and_csrf(facade):
    facade.actor["admin"] = False
    assert facade.client.get("/api/v2/storage").status_code == 403
    assert not facade.storage.control_dir.exists()
    facade.actor["admin"] = True
    facade.app.state.settings = Settings("postgresql://fixture", mode="server", docs_root=facade.root)
    body = {"kind": "filesystem", "name": "data", "path": str(facade.root / "target"), "expected_revision": 0}
    assert facade.client.post("/api/v2/storage/targets", json=body).status_code == 403
    assert (
        facade.client.post("/api/v2/storage/targets", json=body, headers={"X-CSRF-Token": "fixture-csrf"}).status_code
        == 201
    )


def test_checkpoint_setting_and_root_preview_keep_host_auth_and_agent_catalog(facade, monkeypatch):
    seen = []

    def preview(self, destination, actor):
        seen.append((destination, actor["id"]))
        return {"resource_count": 0, "payload_count": 0, "bytes": 0, "resources": [], "payloads": []}

    monkeypatch.setattr("threemind_lab.storage_root.RootChanges.preview", preview)
    facade.actor["admin"] = False
    assert (
        facade.client.post(
            "/api/v2/storage/root-changes/preview", json={"destination": str(facade.root / "new")}
        ).status_code
        == 403
    )
    assert not seen
    facade.actor["admin"] = True
    assert (
        facade.client.post(
            "/api/v2/storage/root-changes/preview", json={"destination": str(facade.root / "new")}
        ).status_code
        == 200
    )
    assert seen[-1][1] == facade.actor["id"]
    response = facade.client.put(
        "/api/v2/storage/checkpoint-backend", json={"backend": "filesystem", "expected_revision": 0}
    )
    assert response.status_code == 200 and facade.storage.checkpoint_settings()["backend"] == "filesystem"
    assert (
        facade.client.put(
            "/api/v2/storage/checkpoint-backend", json={"backend": "invalid", "expected_revision": 1}
        ).status_code
        == 422
    )
    operations = catalog(facade.app)
    assert "/api/v2/storage/root-changes/preview" in str(operations)
    assert "/api/v2/projects/{project}/storage/payload-migrations" in str(operations)


def test_target_secrets_are_encrypted_redacted_and_receipted(facade):
    request_id = str(uuid4())
    body = {
        "kind": "s3",
        "name": "archive",
        "expected_revision": 0,
        "configuration": {"bucket": "test"},
        "credentials": {"access_key_id": "fixture-access", "secret_access_key": "fixture-secret"},
    }
    response = facade.client.post("/api/v2/storage/targets", json=body, headers={HEADER: request_id})
    assert response.status_code == 201, response.text
    target = response.json()
    assert target["has_secret"] and "encrypted_secret" not in target["configuration"]
    repeated = facade.client.post("/api/v2/storage/targets", json=body, headers={HEADER: request_id})
    assert repeated.json() == target and repeated.headers["X-ThreeMind-Replayed"] == "true"
    assert len(facade.storage.targets()) == 1
    public = facade.client.get("/api/v2/storage").text
    receipt = facade.client.get(f"/api/v2/storage/operation-receipts/{request_id}").text
    files = "\n".join(path.read_text() for path in facade.storage.control_dir.rglob("*.json"))
    for text in (public, receipt, files):
        assert "fixture-secret" not in text and "fixture-access" not in text
    assert "encrypted_secret" not in public and "encrypted_secret" not in receipt
    changed = dict(body, name="other")
    assert facade.client.post("/api/v2/storage/targets", json=changed, headers={HEADER: request_id}).status_code == 409


def test_pending_host_receipt_cannot_execute_again(facade):
    request_id = uuid4()
    body = {"target_id": "missing", "expected_revision": 0}
    path = "/api/v2/storage/policies/export"
    assert reserve(facade.storage, facade.actor["id"], request_id, "PUT", path, body) is None
    response = facade.client.put(path, json=body, headers={HEADER: str(request_id)})
    assert response.status_code == 409 and response.json()["status"] == "pending"
    assert inspect(facade.storage, facade.actor["id"], request_id)["status"] == "pending"


def test_migration_copy_verify_and_separate_activation(facade):
    source = facade.root / "source"
    source.mkdir()
    (source / "subject").mkdir()
    (source / "subject/evidence.json").write_bytes(b"original evidence\r\n")
    old = facade.storage.register_target(source, "source")
    new = facade.storage.register_target(facade.root / "destination", "destination")
    resource = facade.storage.register_resource(
        "subject", facade.storage.locator(old["id"], "subject"), writer_mode="sealed"
    )
    body = {
        "resource_id": "subject",
        "target_id": new["id"],
        "relative_path": "relocated",
        "expected_revision": 1,
        "request_id": str(uuid4()),
    }
    planned = facade.client.post("/api/v2/storage/migrations", json=body)
    assert planned.status_code == 201, planned.text
    row = planned.json()
    assert row["state"] == "planned" and row["entries_count"] >= 1 and "entries" not in row
    assert not (facade.root / "destination/relocated").exists()
    base = f"/api/v2/storage/migrations/{row['id']}"
    assert facade.client.post(base + "/activate", json={"expected_revision": 1}).status_code == 409
    copied = facade.client.post(base + "/execute", json={"request_id": str(uuid4())})
    assert copied.status_code == 200 and copied.json()["state"] == "copied", copied.text
    assert facade.storage.resource("subject")["locator"] == resource["locator"]
    assert facade.client.post(base + "/verify", json={}).json()["state"] == "verified"
    assert facade.client.post(base + "/activate", json={"expected_revision": 1}).json()["state"] == "activated"
    assert (source / "subject/evidence.json").read_bytes() == b"original evidence\r\n"
    assert facade.storage.resolve_resource("subject").is_dir()
    assert facade.client.post(base + "/rollback", json={"expected_revision": 2}).json()["state"] == "rolled_back"


def test_private_registered_artifacts_only_and_hash_checked(facade):
    path = facade.root / "data/experiments/E1/evidence.json"
    path.parent.mkdir(parents=True)
    raw = b'{"original":true}'
    path.write_bytes(raw)
    entry = {
        "resource_id": "research-artifact:fixture",
        "legacy_path": "lab/E1/result.json",
        "archive_path": "data/experiments/E1/evidence.json",
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "state": "verified",
    }
    atomic_json(
        facade.root / "lab/artifact-index/fixture-relocations.json",
        {"schema": "threemind.research-artifact-relocations/1", "entries": [entry]},
    )
    endpoint = "/api/v2/storage/research-artifacts/research-artifact:fixture/content"
    (path.parent / "unregistered-secret.json").write_bytes(b"must not be enumerated")
    listing = facade.client.get("/api/v2/storage/research-artifacts?limit=1")
    assert listing.status_code == 200 and listing.json()["matched"] == 1
    assert listing.json()["rows"][0]["resource_id"] == entry["resource_id"]
    assert "unregistered-secret" not in listing.text
    assert facade.client.get("/api/v2/storage/research-artifacts?q=missing").json()["rows"] == []
    assert facade.client.get("/api/v2/storage/research-artifacts?offset=1").json()["rows"] == []
    assert facade.client.get(endpoint).content == raw
    assert facade.client.get("/api/v2/storage/research-artifacts/unknown/content").status_code == 404
    facade.actor["admin"] = False
    assert facade.client.get(endpoint).status_code == 403
    assert facade.client.get("/api/v2/storage/research-artifacts").status_code == 403
    facade.actor["admin"] = True
    path.write_bytes(b"tampered")
    assert facade.client.get(endpoint).status_code == 409


def test_integrity_api_passes_exact_authorized_actor(facade, monkeypatch):
    actors = []
    monkeypatch.setattr(
        facade.app.state.db.blobs, "audit", lambda db, project, **kwargs: actors.append(kwargs["actor"]) or {"rows": []}
    )
    response = facade.client.get("/api/v2/projects/00000000-0000-0000-0000-000000000001/data/integrity")
    assert response.status_code == 200 and actors == [facade.actor["id"]]


def test_candidate_inventory_requires_project_owner_and_is_bounded(facade, monkeypatch):
    budgets = []
    monkeypatch.setattr(
        facade.app.state.db.blobs,
        "candidate_inventory",
        lambda db, project, **kwargs: budgets.append(kwargs["maximum_records"]) or {"rows": [], "more": False},
    )
    path = "/api/v2/projects/00000000-0000-0000-0000-000000000001/data/blob-candidates"
    assert facade.client.get(path + "?maximum_records=1000").status_code == 200
    assert budgets == [1000]
    assert facade.client.get(path + "?maximum_records=1001").status_code == 422
    facade.actor["role"] = "researcher"
    assert facade.client.get(path).status_code == 403
    assert budgets == [1000]


def test_catalog_host_scope_truthful_undo_and_agent_cleanup_preview(facade):
    rows = catalog(facade.app)["operations"]
    target = next(row for row in rows if row["path"].endswith("/storage/targets"))
    assert target["scope"] == "host" and target["human_confirmation"] and target["request_receipt"]
    cleanup = next(row for row in rows if row["path"].endswith("/blob-candidates/{candidate_id}/cleanup"))
    assert cleanup["human_confirmation"] and not cleanup["request_receipt"]
    preview = next(row for row in rows if row["path"].endswith("/blob-candidates/{candidate_id}/cleanup-preview"))
    assert not preview["human_confirmation"] and preview["undo"] is None
    assert all(row["undo"] != "checkpoint_fork" for row in rows)
    assert all(row["undo"] is None for row in rows if row["method"] == "GET")


def test_offline_export_uses_fixed_control_path_revision_and_registered_download(facade):
    source = facade.root / "source"
    source.mkdir()
    (source / "evidence").mkdir()
    (source / "evidence/original.json").write_bytes(b'{"original":"bytes"}\r\n')
    target = facade.storage.register_target(source, "source")
    facade.storage.register_resource(
        "offline-fixture", facade.storage.locator(target["id"], "evidence"), writer_mode="sealed"
    )
    identity = str(uuid4())
    body = {"operation_id": identity, "resource_id": "offline-fixture", "expected_revision": 1}
    base = "/api/v2/storage/data-exports"
    wrong_revision = facade.client.post(base, json=body | {"expected_revision": 2})
    assert wrong_revision.status_code == 409, wrong_revision.text
    created = facade.client.post(base, json=body, headers={HEADER: identity})
    assert created.status_code == 201, created.text
    receipt = created.json()
    assert receipt["state"] == "complete" and receipt["private"]
    assert (facade.storage.control_dir / "data-transfers" / ("host-" + identity) / "receipt.json").exists()
    repeated = facade.client.post(base, json=body, headers={HEADER: identity})
    assert repeated.json() == receipt and repeated.headers["X-ThreeMind-Replayed"] == "true"
    assert facade.client.get(base + "/" + identity).json()["id"] == identity
    master = facade.client.get(base + "/" + identity + "/manifest")
    assert hashlib.sha256(master.content).hexdigest() == receipt["manifest_sha256"]
    downloaded = facade.client.get(base + "/" + identity + "/volumes/0")
    assert hashlib.sha256(downloaded.content).hexdigest() == receipt["volumes"][0]["sha256"]
    assert facade.client.get(base + "/" + identity + "/volumes/1").status_code == 404
    facade.actor["admin"] = False
    assert facade.client.get(base + "/" + identity).status_code == 403
    assert facade.client.get(base + "/" + identity + "/volumes/0").status_code == 403
    facade.actor["admin"] = True
    path = facade.storage.control_dir / "data-transfers" / ("host-" + identity) / receipt["volumes"][0]["filename"]
    path.write_bytes(b"tampered")
    assert facade.client.get(base + "/" + identity + "/volumes/0").status_code == 409
    assert (source / "evidence/original.json").read_bytes() == b'{"original":"bytes"}\r\n'


def test_project_transport_and_multivolume_import(facade, monkeypatch):
    calls = []

    class Catalog:
        def __init__(self, _):
            pass

        def list(self, project, actor, filters, **paging):
            calls.append(("list", project, actor, filters, paging))
            return {"rows": [], "more": False}

        def detail(self, project, actor, kind, identity):
            return {"kind": kind, "id": identity}

    class Bundles:
        def __init__(self, _):
            pass

        def preflight(self, project, actor, stream, backend="native"):
            if isinstance(stream, dict):
                calls.append((json.load(stream["manifest"]), [item.read() for item in stream["volumes"]]))
            else:
                calls.append(stream.read())
            return {"missing_required": [], "can_restore": False, "can_resume": False, "backend": backend}

        def import_register(self, project, actor, stream, operation_id, *, name):
            calls.append((str(operation_id), name, stream.read()))
            return {"id": str(uuid4()), "registered": True}

    monkeypatch.setitem(sys.modules, "threemind_lab.data_catalog", SimpleNamespace(DataCatalog=Catalog))
    monkeypatch.setitem(sys.modules, "threemind_lab.data_bundles", SimpleNamespace(DataBundles=Bundles))
    base = "/api/v2/projects/00000000-0000-0000-0000-000000000001/data"
    assert facade.client.get(base + "?q=test&run=source&tag=fixture").status_code == 200
    assert calls[-1][3] == {"q": "test", "run": "source", "tag": "fixture", "archived": "all"}
    bad = facade.client.post(
        base.replace("000000000001", "000000000002") + "/imports", files={"files": ("x.tmdata", b"data")}
    )
    assert bad.status_code == 403
    response = facade.client.post(
        base + "/imports/preflight",
        files=[
            ("files", ("a.tmdata", b"first")),
            ("files", ("b.tmdata", b"second")),
            ("manifest", ("set.json", b'{"schema":"set"}')),
        ],
    )
    assert response.status_code == 200, response.text
    assert calls[-1] == ({"schema": "set"}, [b"first", b"second"])
    assert response.json()["backend"] == "native"
    explicit = facade.client.post(
        base + "/imports/preflight", files={"files": ("x.tmdata", b"native")}, data={"backend": "reference"}
    )
    assert explicit.status_code == 200 and explicit.json()["backend"] == "reference"
    facade.app.state.settings = Settings("postgresql://fixture", docs_root=facade.root, backend="reference")
    default_backend = facade.client.post(base + "/imports/preflight", files={"files": ("x.tmdata", b"native")})
    assert default_backend.status_code == 200 and default_backend.json()["backend"] == "reference"
    identity = str(uuid4())
    response = facade.client.post(
        base + "/imports", files={"files": ("x.tmdata", b"native")}, data={"operation_id": identity, "name": "fixture"}
    )
    assert response.status_code == 201 and calls[-1] == (identity, "fixture", b"native")
    response = facade.client.post(
        base + "/imports/preflight", files=[("files", ("a.tmdata", b"a")), ("files", ("b.tmdata", b"b"))]
    )
    assert response.status_code == 422


def test_host_receipt_actor_isolation(facade):
    identity = uuid4()
    reserve(facade.storage, facade.actor["id"], identity, "POST", "/api/v2/storage/migrations", {})
    with pytest.raises(NotFound):
        inspect(facade.storage, uuid4(), identity)
    with pytest.raises(StorageConflict):
        reserve(facade.storage, facade.actor["id"], identity, "POST", "/api/v2/storage/migrations", {"changed": True})


def test_real_project_api_fixed_history_plan_task_and_cancel(database, tmp_path):
    from threemind_lab import research_documents
    from threemind_lab.api import create_app
    from threemind_lab.database import LOCAL_USER

    database.blobs = BlobStore(ResearchStorage(tmp_path / "control", repository_root=tmp_path))
    project = database.create_project({"id": LOCAL_USER}, "Disposable data API test")["id"]
    document = uuid4()
    spec = {
        "kind": "report",
        "title": "Original immutable report",
        "sources": [],
        "blocks": [{"id": "comment", "type": "commentary", "markdown": "Original evidence"}],
    }
    for revision in (0, 1):
        research_documents.save(
            database,
            project,
            LOCAL_USER,
            document,
            {
                "operation_id": str(uuid4()),
                "expected_revision": revision,
                "spec": spec | {"title": f"Report edition {revision + 1}"},
            },
        )
    app = create_app(Settings(database.test_url, docs_root=tmp_path), database)
    with TestClient(app) as client:
        base = f"/api/v2/projects/{project}/data"
        response = client.get(base + "?kind=report")
        assert response.status_code == 200, response.text
        assert response.json()["rows"][0]["id"] == str(document)
        plan_id = str(uuid4())
        plan_body = {"operation_id": plan_id, "selection": {"kind": "report", "ids": [str(document)]}}
        plan = client.post(base + "/export-plans", json=plan_body)
        assert plan.status_code == 201, plan.text
        snapshot = plan.json()
        assert snapshot["objects"] and not snapshot["blockers"]
        assert client.post(base + "/export-plans", json=plan_body).json()["id"] == snapshot["id"]
        research_documents.save(
            database,
            project,
            LOCAL_USER,
            document,
            {
                "operation_id": str(uuid4()),
                "expected_revision": 2,
                "spec": spec | {"title": "Later head after fixed plan"},
            },
        )
        fixed = client.get(base + "/export-plans/" + snapshot["id"])
        assert fixed.status_code == 200 and fixed.json()["objects"] == snapshot["objects"]
        operation = str(uuid4())
        exported = client.post(base + "/exports", json={"operation_id": operation, "plan_id": snapshot["id"]})
        assert exported.status_code == 202, exported.text
        task = exported.json()
        assert task["kind"] == "data_export" and task["status"] == "pending"
        assert client.get(base + "/jobs/" + task["id"]).json()["status"] == "pending"
        cancelled = client.post(base + "/jobs/" + task["id"] + "/cancel", json={"operation_id": str(uuid4())})
        assert cancelled.status_code == 200, cancelled.text
        assert client.get(base + "/jobs/" + task["id"]).json()["status"] == "cancelled"
        invalid = client.post(base + "/imports/preflight", files={"files": ("bad.tmdata", b"not a formal archive")})
        assert invalid.status_code == 422, invalid.text
    assert research_documents.get(database, project, document, 1)["spec"]["title"] == "Report edition 1"
