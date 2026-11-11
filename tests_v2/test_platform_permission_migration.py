"""Upgrade a populated disposable schema, without using the research database."""

from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from psycopg.types.json import Jsonb

from threemind_lab import permissions
from threemind_lab.ai_secrets import SecretBox
from threemind_lab.database import LOCAL_USER


@pytest.fixture
def schema65(monkeypatch, request):
    from threemind_lab import database as module

    complete = module.MIGRATIONS
    assert len(complete) == 67
    monkeypatch.setattr(module, "MIGRATIONS", complete[:65])
    database = request.getfixturevalue("database")
    return database, complete


def test_populated_schema65_to67_preserves_authorship_credentials_and_frozen_sources(schema65, monkeypatch):
    from threemind_lab import database as module

    database, complete = schema65
    assert "tm2_test_db_" in database.test_url
    permissions.actor_context.set(None)
    author, admin, project, other = (uuid4() for _ in range(4))
    provider, shared_provider, note = (uuid4() for _ in range(3))
    call, job, notice, delivery = (uuid4() for _ in range(4))
    box = SecretBox((Fernet.generate_key().decode(),))
    provider_secret = box.seal({"api_key": "isolated-fixture-secret", "proxy_password": "fixture-proxy"})
    notification_secret = box.seal({"smtp_password": "isolated-fixture-mail"})
    current_config = {"name": "Current private service", "model": "fixture-model-v4", "base_url": "https://example.invalid"}
    call_config = current_config | {"name": "Historical private service", "model": "fixture-model-v2"}
    notice_config = {"enabled": True, "email_enabled": True, "transport": "smtp", "smtp_host": "example.invalid",
                     "recipients": ["engineering@example.invalid"], "events": {"run_completed": True}, "cooldown_s": 12}

    with database.tx(project, ai_admin=True) as db:
        assert [r["version"] for r in db.execute("SELECT version FROM schema_version ORDER BY version")] == list(range(1, 66))
        for identity, name, administrator in ((LOCAL_USER, "legacy-local", True), (author, "legacy-author", False),
                                                (admin, "legacy-admin", True)):
            db.execute("INSERT INTO users(id,username,password_hash,admin) VALUES(%s,%s,%s,%s) "
                       "ON CONFLICT(id) DO UPDATE SET username=EXCLUDED.username,password_hash=EXCLUDED.password_hash,admin=EXCLUDED.admin",
                       (identity, name, "legacy-preserved-password-hash", administrator))
        db.execute("INSERT INTO projects(id,name,owner_id) VALUES(%s,'Original private project',%s),(%s,'Existing shared grant',%s)",
                   (project, author, other, admin))
        for p, identity, role in ((project, author, "owner"), (project, admin, "viewer"), (other, admin, "owner")):
            db.execute("INSERT INTO members VALUES(%s,%s,%s)", (p, identity, role))
        db.execute("INSERT INTO ai_providers(id,project_id,revision,config,secrets,has_api_key,has_proxy_password,created_by) "
                   "VALUES(%s,%s,4,%s,%s,true,true,%s),(%s,NULL,1,%s,%s,true,false,%s)",
                   (provider, project, Jsonb(current_config), provider_secret, author,
                    shared_provider, Jsonb(current_config | {"name": "Already shared"}), provider_secret, admin))
        db.execute("INSERT INTO ai_provider_grants VALUES(%s,%s)", (shared_provider, other))
        db.execute("INSERT INTO jobs(id,project_id,kind,status,params) VALUES(%s,%s,'ai','done','{}')", (job, project))
        db.execute("INSERT INTO ai_calls(id,project_id,actor_id,provider_id,provider_revision,provider_config,request_id,"
                   "fingerprint,purpose,prompt,response_text,response_meta,result,status,job_id,usage,reserved_usd,cost_usd) "
                   "VALUES(%s,%s,%s,%s,2,%s,%s,%s,'provider_test',%s,'recorded fixture response',%s,%s,'completed',%s,%s,0.02,0.01)",
                   (call, project, author, provider, Jsonb(call_config), uuid4(), "1" * 64,
                    Jsonb({"messages": [{"role": "user", "content": "historical prompt"}]}),
                    Jsonb({"provider": "fixture"}), Jsonb({"original": True}), job,
                    Jsonb({"input_tokens": 4, "output_tokens": 5})))
        db.execute("INSERT INTO notification_settings(project_id,revision,actor_id,config,secrets,has_smtp_password) "
                   "VALUES(%s,3,%s,%s,%s,true)", (project, author, Jsonb(notice_config), notification_secret))
        for revision in (1, 2, 3):
            db.execute("INSERT INTO notification_versions(project_id,revision,actor_id,config) VALUES(%s,%s,%s,%s)",
                       (project, revision, author, Jsonb(notice_config | {"cooldown_s": revision * 4})))
        db.execute("INSERT INTO jobs(id,project_id,kind,params) VALUES(%s,%s,'notification',%s)",
                   (delivery, project, Jsonb({"notification_id": str(notice)})))
        db.execute("INSERT INTO notifications(id,project_id,source_key,kind,facts,policy_revision,email_status,email_job_id) "
                   "VALUES(%s,%s,'original-notice','run_completed',%s,2,'queued',%s)",
                   (notice, project, Jsonb({"preserved": "original facts"}), delivery))
        db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(author),))
        db.execute("INSERT INTO notes(id,project_id,owner_id,title,kind,revision,search_text) "
                   "VALUES(%s,%s,%s,'Original author-private note','draft',1,'private original')", (note, project, author))
        db.execute("INSERT INTO note_versions(project_id,owner_id,note_id,revision,operation_id,request_hash,metadata,body,content_hash) "
                   "VALUES(%s,%s,%s,1,%s,%s,%s,%s,%s)",
                   (project, author, note, uuid4(), "2" * 64, Jsonb({"title": "Original author-private note"}),
                    Jsonb({"format": "markdown", "text": "private original"}), "3" * 64))
        users_before = db.execute("SELECT * FROM users ORDER BY id").fetchall()
        members_before = db.execute("SELECT * FROM members ORDER BY project_id,user_id").fetchall()
        provider_before = db.execute("SELECT * FROM ai_providers WHERE id=%s", (provider,)).fetchone()
        call_before = db.execute("SELECT * FROM ai_calls WHERE id=%s", (call,)).fetchone()
        policy_before = db.execute("SELECT * FROM notification_settings WHERE project_id=%s", (project,)).fetchone()
        versions_before = db.execute("SELECT * FROM notification_versions ORDER BY revision").fetchall()
        notice_before = db.execute("SELECT * FROM notifications WHERE id=%s", (notice,)).fetchone()
        note_before = db.execute("SELECT * FROM note_versions WHERE note_id=%s", (note,)).fetchone()

    monkeypatch.setattr(module, "MIGRATIONS", complete)
    module.migrate(database.test_migration_url)
    permissions.actor_context.set(permissions.enrich(database, {"id": LOCAL_USER}))
    with database.tx(project, ai_admin=True) as db:
        assert db.execute("SELECT * FROM users ORDER BY id").fetchall() == users_before
        assert db.execute("SELECT * FROM members ORDER BY project_id,user_id").fetchall() == members_before
        migrated = db.execute("SELECT * FROM ai_providers WHERE id=%s", (provider,)).fetchone()
        assert migrated["project_id"] is None and migrated["original_project_id"] == project
        assert {k: migrated[k] for k in provider_before if k != "project_id"} == {k: v for k, v in provider_before.items() if k != "project_id"}
        assert migrated["secrets"] == provider_secret
        assert box.open(migrated["secrets"])["api_key"] == "isolated-fixture-secret"
        assert db.execute("SELECT * FROM ai_calls WHERE id=%s", (call,)).fetchone() == call_before
        snapshots = db.execute("SELECT revision,config,source FROM ai_provider_versions WHERE provider_id=%s ORDER BY revision", (provider,)).fetchall()
        assert snapshots == [{"revision": 2, "config": call_config, "source": "call_snapshot"},
                             {"revision": 4, "config": current_config, "source": "current_import"}]
        assert {row["project_id"] for row in db.execute("SELECT project_id FROM ai_provider_grants WHERE provider_id=%s", (provider,))} == {project}
        assert {row["project_id"] for row in db.execute("SELECT project_id FROM ai_provider_grants WHERE provider_id=%s", (shared_provider,))} == {other}
        assert db.execute("SELECT * FROM notification_settings WHERE project_id=%s", (project,)).fetchone() == policy_before
        assert db.execute("SELECT * FROM notification_versions ORDER BY revision").fetchall() == versions_before
        assert db.execute("SELECT * FROM notifications WHERE id=%s", (notice,)).fetchone() == notice_before
        service = db.execute("SELECT * FROM notification_services WHERE original_project_id=%s", (project,)).fetchone()
        assert service["secrets"] == notification_secret and service["created_by"] == author
        assert service["config"] == {key: value for key, value in notice_config.items()
                                      if key not in ("enabled", "email_enabled", "recipients", "events", "cooldown_s")}
        assert box.open(service["secrets"])["smtp_password"] == "isolated-fixture-mail"
        assert db.execute("SELECT project_id FROM notification_service_grants WHERE service_id=%s", (service["id"],)).fetchone()["project_id"] == project
        assert db.execute("SELECT policy_revision,service_revision FROM notification_rule_bindings WHERE project_id=%s", (project,)).fetchone() == {"policy_revision": 3, "service_revision": 1}
        assert db.execute("SELECT * FROM note_versions WHERE note_id=%s", (note,)).fetchone() == note_before
        assert db.execute("SELECT status FROM jobs WHERE id=%s", (delivery,)).fetchone()["status"] == "pending"
    for identity, expected in ((LOCAL_USER, "superadmin"), (author, "user"), (admin, "admin")):
        principal = permissions.enrich(database, {"id": identity})
        assert [role["key"] for role in principal["roles"]] == [expected]
        assert principal["superadmin"] == (identity == LOCAL_USER)
    # Explicit migration remains repeatable, without duplicating imported services.
    module.migrate(database.test_migration_url)
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM notification_services").fetchone()["n"] == 1
        assert db.execute("SELECT count(*) AS n FROM ai_provider_versions WHERE provider_id=%s", (provider,)).fetchone()["n"] == 2
