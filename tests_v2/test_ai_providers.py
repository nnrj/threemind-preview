import asyncio
import json
import threading
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from lease_helpers import claim_as

from threemind_lab import ai_providers as providers
from threemind_lab.ai_http import SSE, Completion, ProviderFailure, request_body
from threemind_lab.ai_schema import ProviderConfig, ProviderEdit
from threemind_lab.ai_secrets import SecretBox
from threemind_lab.ai_worker import AIWorker
from threemind_lab.api import create_app
from threemind_lab.auth import create_user
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Conflict


def setup(database):
    settings = Settings(database_url=database.test_url, secret_keys=(Fernet.generate_key().decode(),))
    project = database.create_project({"id": LOCAL_USER}, "AI tools")["id"]
    return settings, project


def create(database, settings, project, **overrides):
    config = {"name": "Local test", "base_url": "http://127.0.0.1:12345/v1", "model": "fixture-model", "enabled": True}
    config.update(overrides)
    return providers.save(
        database, settings, project, LOCAL_USER, ProviderEdit(config=ProviderConfig(**config), api_key="fixture-secret")
    )


def enqueue(database, settings, project, provider, request_id=None, **kwargs):
    return providers.enqueue(
        database,
        settings,
        project,
        LOCAL_USER,
        provider["id"],
        request_id=request_id or uuid4(),
        purpose="provider_test",
        prompt={"system": "Test", "user": "Connection"},
        **kwargs,
    )


def get_call(database, project, call):
    with database.tx(project) as db:
        return providers.call_by_id(db, call["id"])


class Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk


def chat_response(text="连接成功", finish="stop", usage=True):
    events = [
        {"id": "fixture-response", "model": "reported-fixture", "choices": [{"index": 0, "delta": {"content": text}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": finish}]},
    ]
    if usage:
        events.append({"choices": [], "usage": {"prompt_tokens": 11, "completion_tokens": 3}})
    raw = "".join("data: " + json.dumps(v, ensure_ascii=False) + "\n\n" for v in events).encode() + b"data: [DONE]\n\n"
    # Split inside Chinese UTF-8 characters and SSE delimiters.
    return httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        stream=Chunks([raw[i : i + 7] for i in range(0, len(raw), 7)]),
    )


def test_protocol_parsing_bounds_and_secret_rotation():
    a, b = (Fernet.generate_key().decode() for _ in range(2))
    cipher = SecretBox((a,)).seal({"api_key": "local-secret"})
    assert SecretBox((b, a)).open(cipher)["api_key"] == "local-secret"
    with pytest.raises(ValueError, match="无法解密"):
        SecretBox((b,)).open(cipher)
    for base in ("file:///private", "http://name:password@localhost", "https://x/?key=secret", "http://x/#fragment"):
        with pytest.raises(ValueError):
            ProviderConfig(name="x", model="x", base_url=base)
    with pytest.raises(ValueError):
        ProviderConfig(name="x", model="x", base_url="http://localhost", enabled="false")
    c = ProviderConfig(name="x", model="chosen", base_url="https://example.com/v1", protocol="responses")
    body = request_body(c, {"system": "s", "user": "u"})
    assert body["store"] is False and body["model"] == "chosen" and "temperature" not in body
    for raw in (b"data: {broken}\n\n", b'data: {"choices":[]}\n', b"data: [DONE]\n\ndata: {}\n\n"):
        with pytest.raises(ValueError):
            sse = SSE(Completion(), "chat")
            sse.feed(raw)
            sse.feed(b"", final=True)
    complete = Completion()
    with pytest.raises(ProviderFailure):
        complete.event({"choices": [{"delta": {"content": "partial"}, "finish_reason": "length"}]}, "chat")
    assert complete.text == "partial" and not complete.complete


def test_encrypted_provider_crud_validation_quotas_and_independent_queue(database):
    settings, project = setup(database)
    with TestClient(create_app(settings, database)) as client:
        base = f"/api/v2/projects/{project}/ai"
        bad = client.post(
            base + "/providers",
            json={
                "config": {"name": "", "model": "x", "base_url": "http://x"},
                "api_key": "must-not-echo",
                "clear_api_key": True,
            },
        )
        assert bad.status_code == 422 and "must-not-echo" not in bad.text
        provider = create(
            database,
            settings,
            project,
            max_pending=1,
            daily_request_limit=2,
            input_usd_per_million=1.0,
            output_usd_per_million=2.0,
        )
        listed = client.get(base + "/providers")
        assert "fixture-secret" not in listed.text and '"secrets"' not in listed.text
        with database.tx(project) as db:
            stored = providers.get(db, provider["id"])
        assert "fixture-secret" not in stored["secrets"]
        edited = client.put(
            base + f"/providers/{provider['id']}", json={"config": provider["config"], "expected_revision": 1}
        )
        assert edited.status_code == 200 and edited.json()["has_api_key"]
        provider = edited.json()
        call = enqueue(database, settings, project, provider)
        assert enqueue(database, settings, project, provider, call["request_id"])["id"] == call["id"]
        with pytest.raises(Conflict, match="待处理"):
            enqueue(database, settings, project, provider)
        runtime = database.enqueue(project, "analysis")
        runtime_job = claim_as(database, "runtime-fixture", max_active=1)
        assert runtime_job["id"] == runtime["id"]
        requests = []

        def handler(request):
            requests.append(request)
            body = json.loads(request.content)
            assert request.headers["authorization"] == "Bearer fixture-secret"
            assert body["model"] == "fixture-model" and "max_completion_tokens" in body
            return chat_response()

        worker = AIWorker(database, settings, transport=httpx.MockTransport(handler))
        assert worker.once()  # Runtime claim capacity is full; AI still executes.
        done = get_call(database, project, call)
        assert done["status"] == "completed", done["error"]
        assert done["response_text"] == "连接成功" and done["usage"]["total_tokens"] == 14
        assert done["provider_revision"] == 2 and float(done["cost_usd"]) == 0.000017
        assert len(requests) == 1
        # Job-ack crash AFTER durable response must not resend.
        with database.tx() as db:
            db.execute("UPDATE jobs SET status='pending' WHERE id=%s", (done["job_id"],))
        assert worker.once() and len(requests) == 1
        exported = client.get(base + f"/calls/{call['id']}/export")
        assert exported.status_code == 200 and "fixture-secret" not in exported.text
        second = enqueue(database, settings, project, provider)
        client.post(base + f"/calls/{second['id']}/cancel")
        assert worker.once()
        assert get_call(database, project, second)["status"] == "cancelled" and len(requests) == 1
        with pytest.raises(Conflict, match="今日"):
            enqueue(database, settings, project, provider)
        history = client.get(base + "/calls?limit=1").json()
        assert history["next"] and "response_text" not in history["items"][0]


def test_incomplete_timeout_cancellation_and_uncertain_never_resend(database):
    settings, project = setup(database)
    provider = create(database, settings, project, timeout_s=1)
    partial = enqueue(database, settings, project, provider)
    worker = AIWorker(database, settings, transport=httpx.MockTransport(lambda r: chat_response(finish="length")))
    assert worker.once()
    assert get_call(database, project, partial)["status"] == "failed"
    uncertain = enqueue(database, settings, project, provider)
    with database.tx(project) as db:
        db.execute("UPDATE ai_calls SET sent_at=now(),status='sending' WHERE id=%s", (uncertain["id"],))
    calls = []

    async def stalled(request):
        calls.append(request)
        await asyncio.sleep(30)
        return chat_response()

    worker.transport = httpx.MockTransport(stalled)
    assert worker.once() and not calls
    assert get_call(database, project, uncertain)["status"] == "uncertain"
    timed = enqueue(database, settings, project, provider)
    assert worker.once()
    assert "超时" in get_call(database, project, timed)["error"]
    cancelled = enqueue(database, settings, project, provider)
    entered = threading.Event()

    async def blocked(request):
        entered.set()
        await asyncio.sleep(30)
        return chat_response()

    worker.transport = httpx.MockTransport(blocked)
    thread = threading.Thread(target=worker.once)
    thread.start()
    assert entered.wait(5)
    with database.tx(project) as db:
        db.execute("UPDATE ai_calls SET cancel_requested=true WHERE id=%s", (cancelled["id"],))
    thread.join(5)
    assert not thread.is_alive() and get_call(database, project, cancelled)["status"] == "cancelled"


def test_shared_grants_rls_revoke_and_no_admin_project_bypass(database):
    settings, project = setup(database)
    other = database.create_project({"id": LOCAL_USER}, "Other")["id"]
    with TestClient(create_app(settings, database)) as client:
        provider = client.post(
            "/api/v2/admin/ai/providers",
            json={
                "config": {"name": "Shared", "base_url": "http://127.0.0.1/v1", "model": "test", "enabled": True},
                "api_key": "shared-secret",
            },
        ).json()
        assert provider["id"], provider
        assert not client.get(f"/api/v2/projects/{project}/ai/providers").json()["providers"]
        assert (
            client.put(
                f"/api/v2/admin/ai/providers/{provider['id']}/grants", json={"projects": [str(project)]}
            ).status_code
            == 200
        )
        assert len(client.get(f"/api/v2/projects/{project}/ai/providers").json()["providers"]) == 1
        with database.tx(other) as db:
            assert not db.execute("SELECT * FROM ai_providers").fetchall()
        forbidden = client.put(
            f"/api/v2/projects/{project}/ai/providers/{provider['id']}",
            json={
                "config": provider["config"],
                "expected_revision": 1,
            },
        )
        assert forbidden.status_code == 403
        call = enqueue(database, settings, project, provider)
        client.put(f"/api/v2/admin/ai/providers/{provider['id']}/grants", json={"projects": []})

        def never(request):
            raise AssertionError("revoked provider must not be sent")

        assert AIWorker(database, settings, transport=httpx.MockTransport(never)).once()
        assert get_call(database, project, call)["status"] == "failed"
    outsider = create_user(database, "outsider-admin", "test-only long secret", admin=True)
    with TestClient(create_app(replace(settings, mode="server", authentication="session"), database)) as client:
        login = client.post(
            "/api/v2/login", json={"username": outsider["username"], "password": "test-only long secret"}
        ).json()
        assert client.get(f"/api/v2/projects/{project}/ai/calls").status_code == 403
        assert client.get("/api/v2/admin/ai/providers").status_code == 200
        client.headers["X-CSRF-Token"] = login["csrf"]
        assert (
            client.post(f"/api/v2/projects/{project}/ai/providers", json={"config": provider["config"]}).status_code
            == 403
        )


def test_responses_final_evidence_allowlist_and_pending_config_changes(database):
    settings, project = setup(database)
    provider = create(database, settings, project, protocol="responses", stream=False)
    server = replace(settings, mode="server", authentication="session")
    with pytest.raises(Exception, match="尚未允许"):
        enqueue(database, server, project, provider)
    server = replace(server, ai_allowed_origins=("http://127.0.0.1:12345",))
    call = enqueue(database, server, project, provider)

    def response(request):
        body = json.loads(request.content)
        assert body["store"] is False and "max_output_tokens" in body
        assert request.url.path == "/v1/responses"
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "model": "fixture-model",
                "id": "test",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "result"}]}],
            },
        )

    worker = AIWorker(database, server, transport=httpx.MockTransport(response))
    assert worker.once()
    done = get_call(database, project, call)
    assert done["status"] == "completed" and done["usage"] is None and done["cost_usd"] is None
    pending = enqueue(database, server, project, provider)
    providers.save(
        database,
        server,
        project,
        LOCAL_USER,
        ProviderEdit(config=ProviderConfig(**provider["config"]), expected_revision=1, clear_api_key=True),
        provider["id"],
    )
    assert worker.once()
    assert get_call(database, project, pending)["status"] == "failed"
    assert get_call(database, project, pending)["sent_at"] is None


def test_concurrent_quota_reservations_and_exhausted_ai_lease_do_not_block_core(database):
    from concurrent.futures import ThreadPoolExecutor

    settings, project = setup(database)
    provider = create(database, settings, project, max_pending=1)
    gate = threading.Barrier(2)

    def submit_one():
        gate.wait(5)
        try:
            return enqueue(database, settings, project, provider)
        except Conflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit_one(), range(2)))
    assert sum(row is not None for row in results) == 1
    call = next(row for row in results if row is not None)
    run = database.create_run(project, "Independent paused model", {})
    with database.tx(project) as db:
        db.execute("UPDATE runs SET status='paused' WHERE id=%s", (run["id"],))
        db.execute("UPDATE ai_calls SET run_id=%s,sent_at=now(),status='sending' WHERE id=%s", (run["id"], call["id"]))
        db.execute(
            "UPDATE jobs SET run_id=%s,status='leased',attempts=5,lease_until=now()-interval '1 second' WHERE id=%s",
            (run["id"], call["job_id"]),
        )
    assert not claim_as(database, "expiration-sweeper", queue="ai")
    assert get_call(database, project, call)["status"] == "uncertain"
    assert database.get_run(project, run["id"])["status"] == "paused"
    assert enqueue(database, settings, project, provider)["status"] == "queued"


def test_archive_cleanup_removes_ai_content_but_retains_budget_receipt(database):
    from test_model_library import annotate, fixture

    settings, _ = setup(database)
    with TestClient(create_app(settings, database)) as client:
        project, run_id, url, _cp, _image = fixture(client, database)
        provider = create(database, settings, project)
        call = enqueue(database, settings, project, provider, run_id=run_id)
        worker = AIWorker(database, settings, transport=httpx.MockTransport(lambda r: chat_response()))
        progressed = worker.once()
        with database.tx(project) as db:
            queue = db.execute("SELECT kind,status,required_features FROM jobs WHERE id=%s", (call["job_id"],)).fetchone()
        assert progressed, queue
        assert annotate(client, url, archived=True).status_code == 200
        preview = client.get(url + "/cleanup-preview").json()
        assert preview["allowed"] and preview["counts"]["ai_calls"] == 1
        from threemind_lab.model_library import cleanup

        cleanup(database, project, run_id, {"id": LOCAL_USER}, preview["token"], preview["name"])
        with database.tx(project) as db:
            assert not db.execute("SELECT * FROM ai_calls WHERE id=%s", (call["id"],)).fetchone()
            receipt = db.execute("SELECT * FROM ai_reservations WHERE call_id=%s", (call["id"],)).fetchone()
            assert receipt and receipt["active"] is False
