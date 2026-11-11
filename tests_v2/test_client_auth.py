"""Isolated client acceptance: no Lab database, live service or scientific run."""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from threemind_lab import auth_cli, data_cli, input_client, operations_cli, records_cli
from threemind_lab.client_auth import AuthenticationRequired, CredentialStore
from threemind_lab.operations_client import OperationsClient
from threemind_lab.research_recorder import ResearchRecorder


def expires(seconds=3600):
    return (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat()


@pytest.fixture(autouse=True)
def isolated_credentials(monkeypatch, tmp_path):
    for key in ("THREEMIND_API_USERNAME", "THREEMIND_API_PASSWORD", "THREEMIND_API_TOKEN",
                "THREEMIND_AUTH_PROFILE", "THREEMIND_EXECUTION_SOURCE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("THREEMIND_AUTH_DIR", str(tmp_path / "auth"))


def session(store, *, kind="session", remaining=3600):
    value = {"access_token": "secret-never-in-output", "kind": kind, "username": "researcher",
             "source": "script", "expires_at": expires(remaining), "user": {"id": "original-user"}}
    store.save(value)
    return value


def test_protected_session_survives_another_process_without_platform_dependency(tmp_path):
    store = CredentialStore("http://127.0.0.1:8877")
    expected = session(store)
    assert store.load() == expected
    assert expected["access_token"] not in store.path.read_text()
    if os.name != "nt":
        assert store.path.stat().st_mode & 0o077 == 0
        assert store.directory.stat().st_mode & 0o077 == 0
    script = ("from threemind_lab.client_auth import CredentialStore; "
              "v=CredentialStore('http://127.0.0.1:8877').load(); print(v['username'])")
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "researcher"
    assert expected["access_token"] not in result.stdout + result.stderr
    assert CredentialStore("http://localhost:8877").load() is None
    assert CredentialStore("http://127.0.0.1:8877", profile="separate").load() is None


def test_missing_credentials_and_username_without_password_never_prompt(monkeypatch):
    import getpass

    monkeypatch.setattr(getpass, "getpass", lambda *_: pytest.fail("unexpected password prompt"))
    transport = httpx.MockTransport(lambda request: pytest.fail("unauthenticated network call"))
    with pytest.raises(AuthenticationRequired, match="auth login"):
        OperationsClient.from_environment(transport=transport)
    monkeypatch.setenv("THREEMIND_API_USERNAME", "researcher")
    with pytest.raises(AuthenticationRequired, match="auth login"):
        OperationsClient.from_environment(transport=transport)


def test_env_login_persists_and_close_does_not_revoke(monkeypatch):
    monkeypatch.setenv("THREEMIND_API_USERNAME", "researcher")
    monkeypatch.setenv("THREEMIND_API_PASSWORD", "host-only-password")
    paths = []

    def respond(request):
        paths.append(request.url.path)
        if request.url.path == "/api/v2/auth/token":
            body = json.loads(request.content)
            assert body["source"] == "ai"
            return httpx.Response(200, json={"access_token": "session-token", "expires_at": expires(),
                                             "user": {"id": "original-user"}})
        assert request.headers["Authorization"] == "Bearer session-token"
        return httpx.Response(200, json={"user": {"id": "original-user"}})

    for _ in range(2):
        with OperationsClient.from_environment(source="ai", transport=httpx.MockTransport(respond)) as client:
            client.request("GET", "/api/v2/me")
    assert paths == ["/api/v2/auth/token", "/api/v2/me", "/api/v2/me"]
    assert CredentialStore("http://127.0.0.1:8877").load()["source"] == "ai"


def test_near_expiry_renews_once_and_all_clients_use_rotated_session():
    store = CredentialStore("http://127.0.0.1:8877")
    session(store, remaining=60)
    calls = []

    def respond(request):
        calls.append(request.url.path)
        if request.url.path == "/api/v2/auth/refresh":
            return httpx.Response(200, json={"access_token": "rotated-token", "expires_at": expires(),
                                             "user": {"id": "original-user"}})
        assert request.headers["Authorization"] == "Bearer rotated-token"
        return httpx.Response(200, json={"accepted": True})

    left = OperationsClient.from_environment(transport=httpx.MockTransport(respond))
    right = OperationsClient.from_environment(transport=httpx.MockTransport(respond))
    with left, right:
        left.request("GET", "/api/v2/me")
        right.request("GET", "/api/v2/me")
    assert calls == ["/api/v2/auth/refresh", "/api/v2/me", "/api/v2/me"]


def test_live_profile_replacement_cannot_change_actor_or_delegation():
    store = CredentialStore("http://127.0.0.1:8877")
    value = session(store, kind="delegation")
    value.update(username=None, user=None, delegation={"user_id": "original-user", "id": "original-grant"})
    store.save(value)
    with OperationsClient.from_environment(transport=httpx.MockTransport(lambda _: pytest.fail("identity changed"))) as client:
        store.save(value | {"delegation": {"user_id": "different-user", "id": "different-grant"}})
        with pytest.raises(AuthenticationRequired, match="changed identity"):
            client.request("POST", "/api/v2/projects/anything/runs", body={})
        store.save(value | {"delegation": {"user_id": "original-user", "id": "new-grant"}})
        with pytest.raises(AuthenticationRequired, match="changed identity"):
            client.request("POST", "/api/v2/projects/anything/runs", body={})


@pytest.mark.parametrize("kind", ["session", "delegation"])
def test_expired_credentials_fail_before_business_request(kind):
    store = CredentialStore("http://127.0.0.1:8877")
    session(store, kind=kind, remaining=-1)
    with (
        OperationsClient.from_environment(transport=httpx.MockTransport(lambda _: pytest.fail("expired call"))) as client,
        pytest.raises(AuthenticationRequired, match="expired"),
    ):
        client.request("POST", "/api/v2/projects/anything/runs", body={})


def test_rejected_or_revoked_credential_does_not_login_retry_or_submit_again(monkeypatch):
    session(CredentialStore("http://127.0.0.1:8877"), kind="delegation", remaining=30)
    monkeypatch.setenv("THREEMIND_API_USERNAME", "researcher")
    monkeypatch.setenv("THREEMIND_API_PASSWORD", "host-only-password")
    calls = []

    def respond(request):
        calls.append(request.url.path)
        return httpx.Response(401, json={"detail": "delegation revoked"})

    with (
        OperationsClient.from_environment(transport=httpx.MockTransport(respond)) as client,
        pytest.raises(AuthenticationRequired, match="No operation was automatically retried"),
    ):
        client.request("POST", "/api/v2/projects/anything/runs", body={})
    assert calls == ["/api/v2/projects/anything/runs"]


def test_explicit_logout_revokes_session_but_closing_client_is_not_logout():
    store = CredentialStore("http://127.0.0.1:8877")
    session(store)
    calls = []

    def respond(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"ok": True})

    with OperationsClient.from_environment(transport=httpx.MockTransport(respond)) as client:
        assert client.logout()["logged_out"]
    assert calls == ["/api/v2/logout"]
    assert store.load() is None


@pytest.mark.parametrize("auth_type,expected", [("bearer", ["/api/v2/me", "/api/v2/logout"]),
                                              ("delegation", ["/api/v2/me"])])
def test_host_token_logout_distinguishes_account_from_delegation(auth_type, expected):
    paths = []

    def respond(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={"user": {"auth_type": auth_type}})

    with OperationsClient(token="host-owned-token", transport=httpx.MockTransport(respond)) as client:
        result = client.logout()
    assert result["delegation_revocation_required"] == (auth_type == "delegation")
    assert paths == expected


def test_cli_login_and_status_never_print_secret(monkeypatch, capsys):
    monkeypatch.setenv("THREEMIND_API_PASSWORD", "host-only-password")

    def respond(request):
        if request.url.path == "/api/v2/auth/token":
            return httpx.Response(200, json={"access_token": "private-session-token", "expires_at": expires(), "user": {}})
        return httpx.Response(200, json={"user": {"id": "original-user"}, "mode": "workstation"})

    monkeypatch.setattr(auth_cli, "OperationsClient", lambda *args, **kwargs:
                        OperationsClient(*args, **kwargs, transport=httpx.MockTransport(respond)))
    monkeypatch.setattr(auth_cli, "client_from_arguments", lambda args:
                        OperationsClient.from_environment(args.url, transport=httpx.MockTransport(respond)))
    auth_cli.main(["login", "--username", "researcher", "--non-interactive"])
    auth_cli.main(["status"])
    output = capsys.readouterr().out
    assert "private-session-token" not in output
    assert "host-only-password" not in output
    assert "authenticated" in output


def test_delegation_saved_separately_without_secret_output_or_self_renewal(monkeypatch, capsys, tmp_path):
    session(CredentialStore("http://127.0.0.1:8877"))
    identity, project = str(uuid4()), str(uuid4())
    definition = {"name": "one research project", "source": "ai", "expires_at": expires(),
                  "actions": [{"action": "experiment.control", "scope": "project"}],
                  "resources": [{"kind": "project", "id": project}]}
    path = tmp_path / "delegation.json"
    path.write_text(json.dumps(definition), encoding="utf-8")
    calls = []

    def respond(request):
        calls.append((request.method, request.url.path))
        assert request.headers["Authorization"] == "Bearer secret-never-in-output"
        if request.method == "POST":
            assert json.loads(request.content) == definition
            return httpx.Response(201, json={"delegation": {"id": identity, **definition},
                                             "access_token": "private-delegation-token"})
        return httpx.Response(200, json={"revoked": True})

    monkeypatch.setattr(auth_cli, "client_from_arguments", lambda args:
                        OperationsClient.from_environment(args.url, transport=httpx.MockTransport(respond)))
    auth_cli.main(["delegate", "--json", str(path), "--delegate-profile", "research-ai"])
    assert "private-delegation-token" not in capsys.readouterr().out
    store = CredentialStore("http://127.0.0.1:8877", profile="research-ai")
    assert store.load()["access_token"] == "private-delegation-token"
    with (
        OperationsClient.from_environment(profile="research-ai", transport=httpx.MockTransport(respond)) as client,
        pytest.raises(AuthenticationRequired, match="delegated credentials"),
    ):
        client.refresh()
    auth_cli.main(["revoke", "--id", identity])
    assert calls == [("POST", "/api/v2/account/delegations"),
                     ("DELETE", f"/api/v2/account/delegations/{identity}")]


def test_session_refresh_rejection_never_submits_the_business_mutation():
    session(CredentialStore("http://127.0.0.1:8877"), remaining=60)
    calls = []

    def respond(request):
        calls.append(request.url.path)
        return httpx.Response(401, json={"detail": "account deactivated"})

    with (
        OperationsClient.from_environment(transport=httpx.MockTransport(respond)) as client,
        pytest.raises(AuthenticationRequired, match="account deactivated"),
    ):
        client.request("POST", "/api/v2/projects/anything/runs", body={})
    assert calls == ["/api/v2/auth/refresh"]


def test_shared_cli_channels_are_noninteractive(monkeypatch, capsys, tmp_path):
    import getpass

    monkeypatch.setattr(getpass, "getpass", lambda *_: pytest.fail("ordinary command requested password"))
    with pytest.raises(SystemExit) as error:
        operations_cli.main(["list", "--non-interactive"])
    assert error.value.code == 1
    with pytest.raises(SystemExit) as error:
        records_cli.main(["list", "--non-interactive"])
    assert error.value.code == 2
    with pytest.raises(SystemExit) as error:
        data_cli.main(["list", "--project", str(uuid4()), "--non-interactive"])
    assert error.value.code == 1
    carrier = tmp_path / "stimulus.txt"
    carrier.write_text("重复的文字刺激", encoding="utf-8")
    with pytest.raises(AuthenticationRequired):
        input_client.submit_text(SimpleNamespace(url="http://127.0.0.1:8877", username=None,
                                                project=uuid4(), run=uuid4(), file=carrier), uuid4())
    assert "auth login" in capsys.readouterr().err


def test_recorder_recovers_lost_response_under_reusable_identity(monkeypatch, tmp_path):
    from threemind_lab.operation_catalog import ALIASES, VERSION
    from threemind_lab.record_schema import AppendRecord, RegisterRecord
    from threemind_lab.research_records import digest

    session(CredentialStore("http://127.0.0.1:8877"))
    receipts, accepted, lose_next = {}, [], [True]
    experiment = str(uuid4())
    catalogue = {"schema": VERSION, "components": {}, "operations": []}
    for (method, path), identity in ALIASES.items():
        if identity not in ("records.register", "records.append", "records.receipt"):
            continue
        catalogue["operations"].append({"id": identity, "method": method, "path": path,
            "parameters": [{"name": name, "in": "path", "required": True, "schema": {"type": "string"}}
                           for name in ("project", "experiment", "request_id") if "{" + name + "}" in path],
            "request_receipt": method == "POST",
            "request_body": {"application/json": {"schema": {"type": "object"}}} if method == "POST" else {}})

    def respond(request):
        assert request.headers["Authorization"] == "Bearer secret-never-in-output"
        if request.url.path.endswith("/operations/catalog"):
            return httpx.Response(200, json=catalogue)
        if "/records/receipts/" in request.url.path:
            return httpx.Response(200, json=receipts[request.url.path.rsplit("/", 1)[-1]])
        body = json.loads(request.content)
        action = "append" if request.url.path.endswith("/entries") else "register"
        model = AppendRecord if action == "append" else RegisterRecord
        content = model.model_validate(body).model_dump(mode="json")
        if action == "append":
            content = {"id": experiment, **content}
        result = {"id": experiment if action == "register" else str(uuid4())}
        receipts[body["request_id"]] = {"fingerprint": digest({"action": action, "value": content}), "result": result}
        accepted.append(action)
        if action == "append" and lose_next[0]:
            lose_next[0] = False
            raise httpx.ReadError("response lost after durable commit")
        return httpx.Response(200, json=result)

    factory = OperationsClient.from_environment
    monkeypatch.setattr(OperationsClient, "from_environment", lambda *args, **kwargs:
                        factory(*args, **kwargs, transport=httpx.MockTransport(respond)))
    project = uuid4()
    with ResearchRecorder.from_environment(tmp_path / "experiment", project, source="ai") as recorder:
        recorder.register({"source_key": "mock-client-acceptance", "title": "Engineering acceptance", "executor": "ai"})
        assert recorder.synchronize(strict=True)["pending"] == 0
        # The recorder's identity is deterministic; this mock receipt uses that same identity.
        experiment = recorder.experiment
        recorder.append("stage", "repeated-stimulus", {"repetitions": 3})
        assert recorder.synchronize(strict=True)["pending"] == 0
        original = recorder.save_original("observation.jsonl", b'{"observed":true}\n')
        assert original["byte_count"] > 0
    with ResearchRecorder.from_environment(tmp_path / "experiment", project, source="ai") as resumed:
        assert resumed.resume_recording() == experiment
        assert resumed.synchronize(strict=True)["synced"] == 0
    assert accepted == ["register", "append"]
    assert "secret-never-in-output" not in "".join(path.read_text() for path in (tmp_path / "experiment").rglob("*.json"))


def test_independent_runtime_import_and_help_have_no_lab_login(monkeypatch):
    code = ("import sys; from threemind_runtime import create_engine; "
            "assert not any(m.startswith('threemind_lab') for m in sys.modules); print(create_engine().time_us)")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0"
    help_result = subprocess.run([sys.executable, "-m", "threemind_runtime.cli", "--help"],
                                 capture_output=True, text=True, timeout=20, check=False)
    assert help_result.returncode == 0, help_result.stderr
    assert "auth login" not in help_result.stdout + help_result.stderr
