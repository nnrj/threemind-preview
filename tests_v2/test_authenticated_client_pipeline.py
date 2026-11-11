"""Engineering acceptance: CLI, MCP and Python share one authenticated research service.

The in-process HTTP bridge exercises real routes without listening on a port.
The subject and all originals exist only in the isolated test database/directory.
"""

import asyncio
import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from threemind_lab import auth, auth_cli, cli, permissions
from threemind_lab.api import create_app
from threemind_lab.client_auth import CredentialStore
from threemind_lab.config import Settings
from threemind_lab.mcp_server import build_server
from threemind_lab.operations_client import OperationsClient
from threemind_lab.research_recorder import ResearchRecorder
from threemind_lab.worker import Worker

pytestmark = pytest.mark.session_auth


class LabBridge(httpx.BaseTransport):
    def __init__(self, client):
        self.client = client
        self.logins = 0

    def handle_request(self, request):
        if request.url.path == "/api/v2/auth/token":
            self.logins += 1
        response = self.client.request(request.method, request.url.path,
            params=request.url.query.decode(), content=request.read(), headers=dict(request.headers))
        headers = {k: v for k, v in response.headers.items() if k.lower() not in ("content-encoding", "content-length")}
        return httpx.Response(response.status_code, headers=headers, content=response.content, request=request)


def test_all_clients_continue_one_recorded_repeated_text_subject(database, tmp_path, monkeypatch, capsys):
    password = "isolated shared client account password"
    actor = auth.create_user(database, "shared-client-ai", password)
    settings = Settings(database_url=database.test_url, authentication="session", backend="reference")
    monkeypatch.setenv("THREEMIND_API_URL", "http://127.0.0.1:8877")
    monkeypatch.setenv("THREEMIND_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.setenv("THREEMIND_AUTH_PROFILE", "engineering")
    monkeypatch.setenv("THREEMIND_EXECUTION_SOURCE", "ai")
    monkeypatch.setenv("THREEMIND_API_PASSWORD", password)
    monkeypatch.delenv("THREEMIND_API_TOKEN", raising=False)
    monkeypatch.delenv("THREEMIND_API_USERNAME", raising=False)
    original_factory = OperationsClient.from_environment

    with TestClient(create_app(settings, database)) as http:
        bridge = LabBridge(http)
        monkeypatch.setattr(auth_cli, "OperationsClient", lambda *args, **kwargs:
                            OperationsClient(*args, transport=bridge, **kwargs))
        def factory(cls, *args, **kwargs):
            return original_factory(*args, transport=bridge, **kwargs)
        monkeypatch.setattr(OperationsClient, "from_environment", classmethod(factory))

        def command(arguments):
            capsys.readouterr()
            monkeypatch.setattr("sys.argv", ["threemind", *arguments])
            cli.main()
            output = capsys.readouterr()
            assert password not in output.out + output.err
            value = json.loads(output.out)
            assert "access_token" not in output.out
            return value

        login = command(["auth", "login", "--username", actor["username"], "--remember"])
        assert not login["user"]["superadmin"]
        monkeypatch.delenv("THREEMIND_API_PASSWORD")
        with OperationsClient.from_environment() as client:
            project = client.request("POST", "/api/v2/projects", body={"name": "Isolated cross-channel acceptance"})["id"]
        registration = {"request_id": str(uuid4()), "spec": {
            "source_key": "isolated-shared-client-pipeline", "title": "Cross-channel engineering acceptance",
            "classification": "development", "executor": "ai", "execution_status": "planned",
            "metadata": {"engineering_only": True, "accuracy_assessment": False},
        }}
        body_file = tmp_path / "request.json"
        body_file.write_text(json.dumps(registration), encoding="utf-8")
        registered = command(["records", "register", "--project", project, "--json", str(body_file)])
        experiment = registered["id"]

        def operation(name, value, request_id=None):
            body_file.write_text(json.dumps(value), encoding="utf-8")
            arguments = ["ops", "call", name, "--arguments", str(body_file)]
            if request_id:
                arguments += ["--request-id", str(request_id)]
            return command(arguments)

        with OperationsClient.from_environment() as client:
            spec = client.call("configuration.defaults", {})["spec"]
        spec.update(environment="manual", clock="unbounded", duration_s=0.5, sample_us=50000, checkpoint_us=100000)
        for key in ("host_telemetry", "process_telemetry", "runtime_telemetry"):
            spec[key]["enabled"] = False
        spec["text_sensor"]["enabled"] = True
        prepared = operation("consciousness.create", {"path": {"project": project}, "body": {
            "name": "Shared recorded subject", "spec": spec, "start_immediately": False,
            "record_executor": "ai", "record_classification": "development",
        }}, uuid4())
        run = prepared["id"]
        path = {"project": project, "run_id": run}
        operation("consciousness.command", {"path": path, "body": {"kind": "resume"}}, uuid4())
        inputs = []
        for when in (0, 100000, 200000):
            identity = uuid4()
            accepted = operation("stimulus.submit", {"path": path, "body": {
                "adapter_id": "text-sensor", "source_id": "cli-text", "request_id": str(identity),
                "payload": {"text": "红色圆形", "intensity": 1.0}, "requested_time_us": str(when),
            }}, identity)
            assert accepted["id"] == str(identity)
            inputs.append(str(identity))

        with ResearchRecorder.from_environment(tmp_path / "originals", project, source="ai") as recorder:
            assert recorder.register(registration["spec"], request_id=registration["request_id"]) == experiment
            recorder.append("stage", "inputs-accepted", {"run_id": run, "input_ids": inputs})
            assert recorder.synchronize(strict=True)["pending"] == 0
        permissions.actor_context.set(None)
        assert Worker(database, backend="reference").once()

        server = build_server()
        def mcp(name, arguments, request_id=None):
            output = asyncio.run(server.call_tool("operation_call", {
                "operation": name, "arguments": arguments,
                **({"request_id": str(request_id)} if request_id else {}),
            }))
            assert not output.is_error, output
            value = output.structured_content or json.loads(output.content[0].text)
            return value["result"]
        observed = mcp("consciousness.inspect", {"path": path})
        assert observed["status"] == "completed" and observed["revision"] > 0
        checkpoints = mcp("checkpoint.list", {"path": path})
        checkpoint = checkpoints[0]
        record_path = {"project": project, "experiment": experiment}
        for kind in ("protocol", "report", "note"):
            mcp("records.text", {"path": record_path, "body": {
                "request_id": str(uuid4()), "identity": str(uuid4()), "kind": kind,
                "title": "Engineering " + kind,
                "markdown": "Engineering acceptance: authenticated clients preserve the same three input receipts. No cognition claim.",
            }}, uuid4())
        with OperationsClient.from_environment() as client:
            envelopes = client.request("GET", f"/api/v2/projects/{project}/runs/{run}/inputs")["rows"]
            assert {row["id"] for row in envelopes} == set(inputs)
            assert all(row["delivered_count"] == row["frame_count"] > 0 for row in envelopes)
            delivered_times = []
            for identity in inputs:
                carrier = client.request("GET", f"/api/v2/projects/{project}/runs/{run}/inputs/{identity}")
                assert carrier["envelope"]["actor_id"] == str(actor["id"])
                delivered_times.append(int(carrier["frames"][0]["delivered_time_us"]))
            assert delivered_times == [0, 100000, 200000]
        with ResearchRecorder.from_environment(tmp_path / "originals", project, source="ai") as recorder:
            assert recorder.resume_recording() == experiment
            original = recorder.save_original("delivery-summary.json", json.dumps({"input_ids": inputs}).encode())
            for kind, identity in (("run", run), ("checkpoint", checkpoint["id"])):
                recorder.attach({"logical_id": kind + ":" + identity, "role": "subject" if kind == "run" else "checkpoint",
                    "label": "Actual " + kind, "format": "threemind." + kind, "locator": {"kind": kind, "id": identity}})
            recorder.append("result", "actual-client-delivery", {"run_id": run, "summary_original": original})
            assert recorder.synchronize(strict=True)["pending"] == 0
            recorder.finalize("completed")
            assert recorder.synchronize(strict=True)["pending"] == 0
        verified = command(["records", "verify", "--project", project, "--experiment", experiment, "--hashes"])
        assert verified["coverage"] == "verified"
        assert bridge.logins == 1  # Repeated CLI, MCP and Python calls reuse one account session.
        assert CredentialStore("http://127.0.0.1:8877", profile="engineering").load()["user"]["id"] == str(actor["id"])
        assert command(["auth", "status"])["identity"]["user"]["id"] == str(actor["id"])
        command(["auth", "logout"])
        assert CredentialStore("http://127.0.0.1:8877", profile="engineering").load() is None
