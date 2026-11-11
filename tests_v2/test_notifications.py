import json
import smtplib
import ssl
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from lease_helpers import claim_as
from psycopg.types.json import Jsonb

from threemind_lab import auth, notifications
from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER
from threemind_lab.notification_delivery import send_smtp
from threemind_lab.notification_schema import NotificationConfig, NotificationEdit
from threemind_lab.notification_worker import NotificationWorker
from threemind_lab.worker import Worker


def client_for(db):
    return TestClient(create_app(Settings(database_url=db.test_url, secret_keys=(Fernet.generate_key().decode(),)), db))


def configured(database, client, **changes):
    project = client.post("/api/v2/projects", json={"name": "通知验收"}).json()["id"]
    config = NotificationConfig(**({"enabled": True, "cooldown_s": 0} | changes))
    body = {"config": config.model_dump(), "api_key": "test-not-a-live-resend-key"}
    response = client.put(f"/api/v2/projects/{project}/notifications/settings", json=body)
    assert response.status_code == 200, response.text
    return project, response.json(), config


def emit(database, project, source, kind="run_completed", *, force=False):
    with database.tx(project) as db:
        return db.execute(
            "SELECT emit_notification(%s,NULL,%s,%s,%s,%s) AS id",
            (project, source, kind, Jsonb({"source": source}), force),
        ).fetchone()["id"]


def notice(database, project, notice_id):
    with database.tx(project) as db:
        return db.execute("SELECT * FROM notifications WHERE id=%s", (notice_id,)).fetchone()


def test_notification_policy_real_run_exports_atomic_facts_and_no_core_change(database):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "通知不改变模型"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        spec = {
            "environment": "replay",
            "clock": "unbounded",
            "duration_s": 0.01,
            "replay": [{"time_us": "0", "channels": [[1, 0.5], [2, 0.3]]}],
        }
        first = client.post(root + "/runs", json={"name": "基线", "spec": spec}).json()
        assert Worker(database).once()
        baseline = client.get(root + "/runs/" + first["id"]).json()
        assert client.get(root + "/notifications").json()["items"] == []
        config = NotificationConfig(enabled=True)
        config.events.export_ready = True
        saved = client.put(root + "/notifications/settings", json={"config": config.model_dump()})
        assert saved.status_code == 200, saved.text
        second = client.post(root + "/runs", json={"name": "开启本地通知", "spec": spec}).json()
        assert Worker(database).once()
        assert client.get(root + "/runs/" + second["id"]).json()["state_hash"] == baseline["state_hash"]
        item = client.get(root + "/notifications").json()["items"][0]
        assert item["kind"] == "run_completed" and item["facts"]["time_us"] == "10000"
        assert item["email_status"] == "disabled"
        task = client.post(root + "/runs/" + second["id"] + "/exports", json={"format": "tmind"}).json()
        assert Worker(database).once()
        exported = client.get(root + "/notifications").json()["items"][0]
        assert exported["kind"] == "export_ready" and exported["facts"]["job_id"] == task["id"]
        assert exported["facts"]["state_hash"] == baseline["state_hash"]
        assert client.get(root + "/notifications/unread").json()["unread"] == 2
        assert client.post(root + "/notifications/read", json={"ids": [exported["id"]]}).status_code == 200
        assert client.get(root + "/notifications?unread=true").json()["items"][0]["id"] == item["id"]
        assert client.get(root + "/notifications?limit=1").json()["next"] is not None
        # A rolled-back source transaction cannot leak an inbox event or email.
        with pytest.raises(RuntimeError), database.tx(project) as db:
            db.execute("SELECT emit_notification(%s,NULL,'rollback','run_failed','{}')", (project,))
            raise RuntimeError("rollback source")
        assert len(client.get(root + "/notifications").json()["items"]) == 2
        # Query export uses the actual registered worker kind, data_export.
        selected = client.post(
            root + "/runs/" + second["id"] + "/data-exports", json={"table": "edges", "format": "csv"}
        )
        assert selected.status_code == 202, selected.text
        assert Worker(database).once()
        query_notice = client.get(root + "/notifications").json()["items"][0]
        assert query_notice["facts"]["job_id"] == selected.json()["id"]
        assert query_notice["kind"] == "export_ready" and query_notice["facts"]["job_kind"] == "data_export"
        assert query_notice["facts"]["artifact_id"]


def test_notification_secrets_validation_versions_isolation_and_personal_reads(database):
    with client_for(database) as client:
        project, saved, config = configured(database, client)
        root = f"/api/v2/projects/{project}/notifications"
        assert "test-not-a-live-resend-key" not in json.dumps(saved)
        assert saved["has_api_key"]
        assert client.put(root + "/settings", json={"config": config.model_dump()}).status_code == 409
        assert (
            client.put(
                root + "/settings", json={"expected_revision": 1, "config": config.model_dump(), "smtp_password": 123}
            ).status_code
            == 422
        )
        assert (
            "do_not_echo"
            not in client.put(root + "/settings", json={"config": {}, "api_key": {"do_not_echo": "private"}}).text
        )
        malformed = config.model_dump() | {"sender": "person@example.test\nBcc: hidden@example.test"}
        assert client.put(root + "/settings", json={"expected_revision": 1, "config": malformed}).status_code == 422
        saved = client.put(root + "/settings", json={"expected_revision": 1, "config": config.model_dump()}).json()
        assert saved["has_api_key"] and saved["revision"] == 1
        cleared = client.put(
            root + "/settings", json={"expected_revision": 1, "config": config.model_dump(), "clear_api_key": True}
        ).json()
        assert not cleared["has_api_key"] and len(client.get(root + "/versions").json()["items"]) == 2
        item = emit(database, project, "private")
        other = client.post("/api/v2/projects", json={"name": "隔离"}).json()["id"]
        assert client.post(f"/api/v2/projects/{other}/notifications/read", json={"ids": [str(item)]}).status_code == 404
        viewer = auth.create_user(database, "notice-viewer", "a long test password")
        with database.tx() as db:
            db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (project, viewer["id"]))
        server = replace(client.app.state.settings, mode="server", authentication="session")
        with TestClient(create_app(server, database)) as remote:
            login = remote.post(
                "/api/v2/login", json={"username": "notice-viewer", "password": "a long test password"}
            ).json()
            remote.headers["X-CSRF-Token"] = login["csrf"]
            assert remote.get(root + "/settings").status_code == 403
            assert remote.get(root).status_code == 200
            assert remote.post(root + "/read", json={"ids": [str(item)]}).status_code == 200
            assert remote.get(root + "/unread").json()["unread"] == 0
            assert client.get(root + "/unread").json()["unread"] == 1
            assert remote.post(root + "/test", json={"request_id": str(uuid4())}).status_code == 403


def test_notification_durable_queue_delivery_idempotence_budget_and_lost_ack(database):
    with client_for(database) as client:
        project, _, config = configured(
            database, client, email_enabled=True, recipients=["one@example.test"], daily_email_limit=1
        )
        sent = []

        def respond(request):
            sent.append(request)
            return httpx.Response(200, json={"id": "receipt-1"})

        worker = NotificationWorker(database, client.app.state.settings, transport=httpx.MockTransport(respond))
        first = emit(database, project, "first")
        assert emit(database, project, "first") == first
        assert claim_as(database, "runtime-test", queue="runtime") is None
        assert claim_as(database, "ai-test", queue="ai") is None
        assert worker.once() and notice(database, project, first)["email_status"] == "sent"
        assert len(sent) == 1 and sent[0].headers["Idempotency-Key"] == "threemind-" + str(first)
        second = emit(database, project, "budget")
        assert worker.once() and notice(database, project, second)["email_reason"] == "rolling_24h_limit"
        assert len(sent) == 1
        # A policy change cancels queued mail instead of changing recipients silently.
        third = emit(database, project, "changed")
        config.daily_email_limit = 20
        config.language = "en"
        notifications.save_policy(
            database,
            client.app.state.settings,
            project,
            LOCAL_USER,
            NotificationEdit(config=config, expected_revision=1),
        )
        assert worker.once() and notice(database, project, third)["email_status"] == "cancelled"
        lost = emit(database, project, "lost-receipt")
        job = claim_as(database, "lost-worker", queue="notification")
        prepared = notifications.prepare_delivery(database, client.app.state.settings, job)
        assert prepared["notice"]["id"] == lost
        with database.tx() as db:
            db.execute("UPDATE jobs SET lease_until=clock_timestamp()-interval '1 second' WHERE id=%s", (job["id"],))
        assert worker.once()
        assert notice(database, project, lost)["email_status"] == "uncertain" and len(sent) == 1
        test_id = str(uuid4())
        test_root = f"/api/v2/projects/{project}/notifications/test"
        a = client.post(test_root, json={"request_id": test_id}).json()
        assert client.post(test_root, json={"request_id": test_id}).json()["id"] == a["id"]
        assert worker.once() and len(sent) == 2
        assert json.loads(sent[-1].content)["subject"] == "ThreeMind · Notification test"


def test_notification_out_of_order_commits_and_endpoint_or_actor_revocation(database):
    with client_for(database) as client:
        project, _, _ = configured(database, client, email_enabled=True, recipients=["one@example.test"])
        sent = []

        def respond(request):
            sent.append(request)
            return httpx.Response(200, json={"id": str(uuid4())})

        worker = NotificationWorker(database, client.app.state.settings, transport=httpx.MockTransport(respond))
        with database.tx(project) as older:
            first = older.execute(
                "SELECT emit_notification(%s,NULL,'slow','run_completed','{}') AS id", (project,)
            ).fetchone()["id"]
            second = emit(database, project, "committed-first")
            assert worker.once() and notice(database, project, second)["email_status"] == "sent"
        assert worker.once() and notice(database, project, first)["email_status"] == "sent"
        assert len(sent) == 2
        denied = emit(database, project, "endpoint-revoked")
        restricted = NotificationWorker(
            database, replace(client.app.state.settings, mode="server", authentication="session"), transport=httpx.MockTransport(respond)
        )
        assert restricted.once() and notice(database, project, denied)["email_reason"] == "endpoint_not_allowed"
        revoked = emit(database, project, "actor-revoked")
        with database.tx() as db:
            db.execute("UPDATE members SET role='researcher' WHERE project_id=%s AND user_id=%s", (project, LOCAL_USER))
        assert worker.once() and notice(database, project, revoked)["email_status"] == "cancelled"
        assert len(sent) == 2


def test_notification_recurrence_event_commits_and_exhausted_export_jobs(database):
    with client_for(database) as client:
        project, _, _ = configured(database, client)
        run = database.create_run(project, "读出来源", {})["id"]
        # This is a trigger fixture, not a claim of measured recurrence.
        payload = {
            "structure": {
                "recurrence_notice": True,
                "structure_id": "candidate-a",
                "state_signature": "signature",
                "occurrences": 3,
                "span_us": "2000",
            }
        }
        with database.tx(project) as db:
            db.execute(
                "INSERT INTO events(project_id,run_id,event_key,time_us,kind,payload,commit_revision) VALUES(%s,%s,'recurrence',2000,'structural_readout',%s,2)",
                (project, run, Jsonb(payload)),
            )
        root = f"/api/v2/projects/{project}/notifications"
        item = client.get(root).json()["items"][0]
        assert item["kind"] == "structure_recurrence" and item["facts"]["structure_id"] == "candidate-a"
        assert item["facts"]["revision"] == 2 and item["facts"]["span_us"] == "2000"
        job = database.enqueue(project, "export", run_id=run)
        with database.tx() as db:
            db.execute(
                "UPDATE jobs SET status='leased',attempts=5,lease_until=clock_timestamp()-interval '1 second' WHERE id=%s",
                (job["id"],),
            )
        assert claim_as(database, "recover-export") is None
        item = client.get(root).json()["items"][0]
        assert item["kind"] == "job_failed" and item["facts"]["job_id"] == str(job["id"])


@pytest.mark.parametrize(
    "response,status,reason",
    [(400, "failed", "resend_http_400"), (503, "uncertain", "resend_http_503"), (302, "failed", "resend_http_302")],
)
def test_notification_http_failure_is_sanitized_and_does_not_follow_redirects(database, response, status, reason):
    with client_for(database) as client:
        project, _, _ = configured(database, client, email_enabled=True, recipients=["one@example.test"])
        item = emit(database, project, "failure")
        sent = []

        def respond(request):
            sent.append(request)
            return httpx.Response(
                response, text="private-token-in-provider-error", headers={"Location": "https://not-authorized.invalid"}
            )

        assert NotificationWorker(database, client.app.state.settings, transport=httpx.MockTransport(respond)).once()
        result = notice(database, project, item)
        assert result["email_status"] == status and result["email_reason"] == reason and len(sent) == 1
        assert "private-token" not in json.dumps(result, default=str)


def test_notification_smtp_tls_partial_and_quit_failure_keep_known_receipt(monkeypatch):
    calls = []

    class SMTP:
        def __init__(self, host, port, **options):
            calls.append((host, port, options))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            # DATA already received a successful response; QUIT is not delivery.
            raise smtplib.SMTPServerDisconnected("QUIT connection dropped")

        def ehlo(self):
            calls.append("ehlo")

        def starttls(self, context):
            assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
            calls.append("starttls")

        def login(self, user, password):
            assert user == "sender" and password == "test-password"
            calls.append("login")

        def send_message(self, message, *, from_addr, to_addrs):
            assert from_addr == "sender@example.test" and len(to_addrs) == 2
            assert message["Date"] and message["Subject"] == "ThreeMind · 通知测试"
            assert message.get_body().get_content_type() == "text/plain"
            calls.append("data")
            return {to_addrs[-1]: (550, b"rejected")}

    monkeypatch.setattr("threemind_lab.notification_delivery.smtplib.SMTP", SMTP)
    config = NotificationConfig(
        transport="smtp",
        smtp_host="smtp.example.test",
        sender="ThreeMind <sender@example.test>",
        smtp_username="sender",
        recipients=["one@example.test", "two@example.test"],
    )
    result = send_smtp(
        config, {"smtp_password": "test-password"}, {"id": uuid4(), "project_id": uuid4(), "kind": "test", "facts": {}}
    )
    assert result == {"status": "partial", "reason": "smtp_partial_recipient_refusal"}
    assert calls[1:] == ["ehlo", "starttls", "ehlo", "login", "data"]
    settings = Settings(
        database_url="postgresql://unused", mode="server", notification_allowed_endpoints=("smtp.example.test:587",)
    )
    assert notifications.delivery_allowed(settings, config)
    assert not notifications.delivery_allowed(settings, config.model_copy(update={"smtp_security": "none"}))


def test_notification_cooldown_preserves_inbox_and_transition_retries_are_distinct(database):
    with client_for(database) as client:
        project, _, _ = configured(database, client, email_enabled=True, recipients=["one@example.test"], cooldown_s=60)
        worker = NotificationWorker(
            database,
            client.app.state.settings,
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"id": "receipt"})),
        )
        first = emit(database, project, "first")
        assert worker.once() and notice(database, project, first)["email_status"] == "sent"
        second = emit(database, project, "cooling")
        assert worker.once() and notice(database, project, second)["email_reason"] == "cooldown"
        run = database.create_run(project, "需要重试", {})["id"]
        for _attempt in range(2):
            with database.tx(project) as db:
                db.execute("UPDATE runs SET status='running' WHERE id=%s", (run,))
                db.execute("UPDATE runs SET status='blocked' WHERE id=%s", (run,))
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM notifications WHERE run_id=%s", (run,)).fetchone()["n"] == 2
