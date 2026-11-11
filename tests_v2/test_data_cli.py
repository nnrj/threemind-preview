import json
from uuid import uuid4

import httpx

from threemind_lab import data_cli
from threemind_lab.operations_client import OperationsClient


def test_data_cli_plan_and_export_reuse_explicit_id(tmp_path, monkeypatch, capsys):
    calls = []

    def respond(request):
        calls.append((request.url.path, json.loads(request.content), request.headers.get("X-ThreeMind-Request-ID")))
        return httpx.Response(201, json={"id": "fixture", "status": "queued"})

    monkeypatch.setattr(data_cli, "connect", lambda _: OperationsClient(transport=httpx.MockTransport(respond)))
    selection = tmp_path / "selection.json"
    selection.write_text('{"run":"fixture-subject"}', encoding="utf-8")
    operation = str(uuid4())
    project = str(uuid4())
    data_cli.main(["export-plan", "--project", project, "--json", str(selection), "--request-id", operation])
    assert calls[0][1] == {"selection": {"run": "fixture-subject"}, "operation_id": operation}
    assert calls[0][2] == operation
    assert "request_id=" + operation in capsys.readouterr().err


def test_storage_cli_never_accepts_plaintext_credential_file(tmp_path, capsys):
    import pytest

    config = tmp_path / "config.json"
    config.write_text('{"credentials":{"secret_access_key":"must-not-print"}}', encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        data_cli.storage_main(["target", "--json", str(config)])
    assert error.value.code == 1
    output = capsys.readouterr()
    assert "must-not-print" not in output.err and "--s3-credentials" in output.err


def test_storage_cli_migration_does_not_implicitly_activate(monkeypatch, capsys):
    calls = []

    def respond(request):
        calls.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"state": "copied"})

    monkeypatch.setattr(data_cli, "connect", lambda _: OperationsClient(transport=httpx.MockTransport(respond)))
    operation, plan = str(uuid4()), str(uuid4())
    data_cli.storage_main(["execute", "--id", plan, "--request-id", operation])
    assert calls == [(f"/api/v2/storage/migrations/{plan}/execute", {"request_id": operation})]
    assert json.loads(capsys.readouterr().out)["state"] == "copied"


def test_cli_preflight_and_resume_use_the_same_explicit_runtime_backend(tmp_path, monkeypatch, capsys):
    calls = []

    def respond(request):
        calls.append((request.url, request.content))
        return httpx.Response(200, json={"backend": "reference", "can_resume": False})

    monkeypatch.setattr(data_cli, "connect", lambda _: OperationsClient(transport=httpx.MockTransport(respond)))
    package = tmp_path / "fixture.tmdata"
    package.write_bytes(b"disposable fixture bytes")
    project, bundle = str(uuid4()), str(uuid4())
    data_cli.main(["preflight", "--project", project, "--file", str(package), "--backend", "reference"])
    assert b'name="backend"\r\n\r\nreference' in calls[-1][1]
    data_cli.main(
        ["resume-plan", "--project", project, "--bundle", bundle, "--id", "subject-fixture", "--backend", "reference"]
    )
    assert calls[-1][0].params["backend"] == "reference"
    data_cli.main(
        ["resume", "--project", project, "--bundle", bundle, "--id", "subject-fixture", "--backend", "reference"]
    )
    assert json.loads(calls[-1][1])["backend"] == "reference"
    capsys.readouterr()


def test_root_and_checkpoint_storage_cli_share_explicit_service_routes(tmp_path, monkeypatch, capsys):
    calls = []

    def respond(request):
        calls.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"state": "planned"})

    monkeypatch.setattr(data_cli, "connect", lambda _: OperationsClient(transport=httpx.MockTransport(respond)))
    operation, plan, project, checkpoint = (str(uuid4()) for _ in range(4))
    data_cli.storage_main(
        ["root-plan", "--destination", str(tmp_path / "new"), "--expected-revision", "3", "--request-id", operation]
    )
    assert calls[-1] == (
        "POST",
        "/api/v2/storage/root-changes",
        {"destination": str(tmp_path / "new"), "expected_revision": 3, "operation_id": operation},
    )
    data_cli.storage_main(["root-resume", "--id", plan, "--request-id", operation])
    assert calls[-1][1:] == (f"/api/v2/storage/root-changes/{plan}/resume", {"operation_id": operation})
    data_cli.storage_main(["checkpoint-backend", "--backend", "filesystem", "--expected-revision", "0"])
    assert calls[-1] == ("PUT", "/api/v2/storage/checkpoint-backend", {"backend": "filesystem", "expected_revision": 0})
    data_cli.storage_main(
        [
            "payload-migrate",
            "--project",
            project,
            "--kind",
            "checkpoint",
            "--id",
            checkpoint,
            "--target",
            "originals",
            "--request-id",
            operation,
        ]
    )
    assert calls[-1][1:] == (
        f"/api/v2/projects/{project}/storage/payload-migrations",
        {"kind": "checkpoint", "object_id": checkpoint, "target_id": "originals", "operation_id": operation},
    )
    capsys.readouterr()
