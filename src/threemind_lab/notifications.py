"""Project notification policy, immutable local facts and durable delivery state."""

from uuid import UUID

from psycopg.types.json import Jsonb

from .ai_providers import require_actor
from .ai_secrets import SecretBox
from .database import Conflict, NotFound
from .notification_schema import NotificationConfig

TERMINAL = ("disabled", "sent", "partial", "failed", "uncertain", "cancelled", "skipped")
PUBLIC = "project_id,revision,actor_id,config,has_api_key,has_smtp_password,updated_at"


def policy_lock(db, project):
    db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,738349221))", (str(project),))


def get_policy(db):
    row = db.execute("SELECT " + PUBLIC + " FROM notification_settings").fetchone()
    if row:
        row["config"] = NotificationConfig.model_validate(row["config"]).model_dump()
    return row or {
        "revision": 0,
        "config": NotificationConfig().model_dump(),
        "has_api_key": False,
        "has_smtp_password": False,
    }


def endpoint(config):
    host = f"[{config.smtp_host}]" if ":" in config.smtp_host else config.smtp_host
    return "api.resend.com:443" if config.transport == "resend" else f"{host}:{config.smtp_port}"


def delivery_allowed(settings, config):
    if (
        config.transport == "smtp"
        and config.smtp_security == "none"
        and (settings.mode != "workstation" or config.smtp_host not in ("127.0.0.1", "::1", "localhost"))
    ):
        return False
    return settings.mode == "workstation" or endpoint(config) in settings.notification_allowed_endpoints


def require_delivery(settings, config, secrets):
    if not config.recipients or config.transport == "smtp" and not config.smtp_host:
        raise ValueError("发送邮件需要收件人及对应的发送配置")
    if config.transport == "resend" and not secrets.get("api_key"):
        raise ValueError("请先保存 Resend API Key")
    if not delivery_allowed(settings, config):
        raise ValueError("此邮件端点未获部署许可，或 SMTP 明文模式不符合当前部署限制")


def save_policy(store, settings, project, actor, body):
    with store.tx(project) as db:
        require_actor(db, project, actor, owner=True)
        policy_lock(db, project)
        current = db.execute("SELECT * FROM notification_settings").fetchone()
        revision = current["revision"] if current else 0
        if revision != body.expected_revision:
            raise Conflict("通知设置已在其他页面修改，请重新读取后保存")
        box = SecretBox(settings.secret_keys)
        secrets = box.open(current["secrets"]) if current and current["secrets"] else {}
        previous_secrets = dict(secrets)
        for key in ("api_key", "smtp_password"):
            if getattr(body, "clear_" + key):
                secrets.pop(key, None)
            elif getattr(body, key):
                secrets[key] = getattr(body, key)
        if body.config.email_enabled:
            require_delivery(settings, body.config, secrets)
        config = body.config.model_dump()
        if (
            current
            and str(current["actor_id"]) == str(actor)
            and current["config"] == config
            and secrets == previous_secrets
        ):
            return get_policy(db)
        cipher = box.seal(secrets) if secrets else ""
        db.execute(
            "INSERT INTO notification_settings(project_id,revision,actor_id,config,secrets,has_api_key,has_smtp_password) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(project_id) DO UPDATE SET "
            "revision=EXCLUDED.revision,actor_id=EXCLUDED.actor_id,config=EXCLUDED.config,secrets=EXCLUDED.secrets,"
            "has_api_key=EXCLUDED.has_api_key,has_smtp_password=EXCLUDED.has_smtp_password,updated_at=now()",
            (
                project,
                revision + 1,
                actor,
                Jsonb(config),
                cipher,
                bool(secrets.get("api_key")),
                bool(secrets.get("smtp_password")),
            ),
        )
        db.execute(
            "INSERT INTO notification_versions(project_id,revision,actor_id,config) VALUES(%s,%s,%s,%s)",
            (project, revision + 1, actor, Jsonb(config)),
        )
        from .execution_health import configure

        configure(db, project, revision + 1, body.config)
        db.execute(
            "INSERT INTO audit(user_id,action,resource,details) VALUES(%s,'notification.settings',%s,%s)",
            (actor, str(project), Jsonb({"revision": revision + 1})),
        )
        return get_policy(db)


def request_test(store, settings, project, actor, request_id):
    with store.tx(project) as db:
        require_actor(db, project, actor, owner=True)
        policy_lock(db, project)
        policy = db.execute("SELECT * FROM notification_settings").fetchone()
        if not policy:
            raise ValueError("请先保存通知配置")
        config = NotificationConfig(**policy["config"])
        secrets = SecretBox(settings.secret_keys).open(policy["secrets"]) if policy["secrets"] else {}
        require_delivery(settings, config, secrets)
        notice_id = db.execute(
            "SELECT emit_notification(%s,NULL,%s,'test',%s,true) AS id",
            (project, f"test:{request_id}", Jsonb({"request_id": str(request_id), "actor_id": str(actor)})),
        ).fetchone()["id"]
        return db.execute("SELECT * FROM notifications WHERE id=%s", (notice_id,)).fetchone()


def list_notices(db, actor, *, before=None, limit=30, unread=False):
    items = db.execute(
        "SELECT n.*,r.read_at FROM notifications n LEFT JOIN notification_reads r ON r.notification_id=n.id AND r.user_id=%s "
        "WHERE (%s::bigint IS NULL OR n.ordinal<%s) AND (NOT %s OR r.read_at IS NULL) ORDER BY n.ordinal DESC LIMIT %s",
        (actor, before, before, unread, limit + 1),
    ).fetchall()
    return {"items": items[:limit], "next": items[limit - 1]["ordinal"] if len(items) > limit else None}


def mark_read(db, project, actor, ids):
    ids = list(dict.fromkeys(UUID(str(value)) for value in ids))
    if db.execute("SELECT count(*) AS n FROM notifications WHERE id=ANY(%s)", (ids,)).fetchone()["n"] != len(ids):
        raise NotFound("通知不存在或不属于当前项目")
    db.execute(
        "INSERT INTO notification_reads(project_id,notification_id,user_id) SELECT %s,id,%s FROM notifications "
        "WHERE id=ANY(%s) ON CONFLICT(notification_id,user_id) DO NOTHING",
        (project, actor, ids),
    )


def finish_delivery(store, job, notice_id, status, *, reason=None, provider_id=None):
    with store.tx(job["project_id"]) as db:
        store.fence(db, job)
        db.execute(
            "UPDATE notifications SET email_status=%s,email_reason=%s,email_provider_id=%s,finished_at=now() "
            "WHERE id=%s AND email_job_id=%s AND email_status IN ('queued','sending')",
            (status, reason, provider_id, notice_id, job["id"]),
        )


def prepare_delivery(store, settings, job):
    with store.tx(job["project_id"]) as db:
        store.fence(db, job)
        policy_lock(db, job["project_id"])
        notice = db.execute(
            "SELECT * FROM notifications WHERE id=%s FOR UPDATE", (job["params"]["notification_id"],)
        ).fetchone()
        if notice is None or notice["email_job_id"] != job["id"]:
            raise NotFound("通知任务已失效")
        if notice["email_status"] in TERMINAL:
            return {"status": notice["email_status"]}
        reason, status = None, None
        if notice["dispatched_at"] is not None:
            status, reason = "uncertain", "worker_replaced_after_dispatch"
        policy = db.execute("SELECT * FROM notification_settings").fetchone()
        config = NotificationConfig(**policy["config"])
        if status is None:
            actor = db.execute(
                "SELECT 1 FROM members m JOIN users u ON u.id=m.user_id WHERE m.project_id=%s AND m.user_id=%s AND m.role='owner' AND u.enabled",
                (job["project_id"], policy["actor_id"]),
            ).fetchone()
            if (
                policy["revision"] != notice["policy_revision"]
                or not actor
                or (notice["kind"] != "test" and (not config.enabled or not config.email_enabled))
            ):
                status, reason = "cancelled", "policy_or_permission_changed"
            elif not delivery_allowed(settings, config):
                status, reason = "cancelled", "endpoint_not_allowed"
        if status is None:
            budget = db.execute(
                "SELECT count(*) AS n,max(dispatched_at) AS last FROM notifications WHERE dispatched_at>clock_timestamp()-interval '24 hours'"
            ).fetchone()
            recent = db.execute(
                "SELECT EXISTS(SELECT 1 FROM notifications WHERE dispatched_at>clock_timestamp()-(%s * interval '1 second')) AS value",
                (config.cooldown_s,),
            ).fetchone()["value"]
            if budget["n"] >= config.daily_email_limit:
                status, reason = "skipped", "rolling_24h_limit"
            elif recent:
                status, reason = "skipped", "cooldown"
        if status:
            db.execute(
                "UPDATE notifications SET email_status=%s,email_reason=%s,finished_at=now() WHERE id=%s",
                (status, reason, notice["id"]),
            )
            return {"status": status, "reason": reason}
        secrets = SecretBox(settings.secret_keys).open(policy["secrets"]) if policy["secrets"] else {}
        require_delivery(settings, config, secrets)
        # Persist uncertainty before crossing the external side-effect boundary.
        # A replacement worker never resends an already-dispatched notification.
        db.execute(
            "UPDATE notifications SET email_status='sending',dispatched_at=clock_timestamp() WHERE id=%s",
            (notice["id"],),
        )
        return {"notice": notice, "config": config, "secrets": secrets}
