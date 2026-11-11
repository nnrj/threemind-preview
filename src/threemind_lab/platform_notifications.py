"""Platform transports, project rules and an authorized personal inbox.

Legacy policy snapshots and outbox items remain authoritative for delivery;
changing a transport does not mutate or resend an already queued notification.
"""

from uuid import UUID, uuid4

from fastapi import Query, Request
from psycopg.types.json import Jsonb
from pydantic import Field

from . import auth, notifications, permissions
from .ai_secrets import SecretBox
from .database import Conflict, Forbidden, NotFound
from .notification_schema import NotificationConfig, NotificationRead
from .protocols import StrictModel

TRANSPORT = {"transport", "sender", "smtp_host", "smtp_port", "smtp_security", "smtp_username", "timeout_s"}
RULES = set(NotificationConfig.model_fields) - TRANSPORT
PUBLIC = "id,name,revision,config,has_api_key,has_smtp_password,original_project_id,created_by,created_at,updated_at"


class ServiceEdit(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    config: dict
    expected_revision: int = Field(default=0, ge=0, strict=True)
    api_key: str = Field(default="", max_length=8192)
    smtp_password: str = Field(default="", max_length=8192)
    clear_api_key: bool = Field(default=False, strict=True)
    clear_smtp_password: bool = Field(default=False, strict=True)
    project_ids: list[UUID] = Field(default_factory=list, max_length=10000)


def available(db, project):
    return db.execute(
        "SELECT "
        + ",".join("s." + k for k in PUBLIC.split(","))
        + " FROM notification_services s JOIN notification_service_grants g ON g.service_id=s.id WHERE g.project_id=%s ORDER BY s.name,s.id",
        (project,),
    ).fetchall()


def bind_policy(store, settings, project, user, body):
    """Freeze the selected service into the existing transactional outbox policy."""
    if set(body.get("config", {})) - RULES:
        raise ValueError("project notification rules cannot contain transport configuration")
    identity = UUID(str(body["service_id"])) if body.get("service_id") else None
    expected = body.get("expected_revision", 0)
    with store.tx(project) as db:
        notifications.policy_lock(db, project)
        current = db.execute("SELECT * FROM notification_settings WHERE project_id=%s", (project,)).fetchone()
        if (current["revision"] if current else 0) != expected:
            raise Conflict("notification policy changed; reload before saving")
        service = (
            db.execute("SELECT * FROM notification_services WHERE id=%s FOR SHARE", (identity,)).fetchone()
            if identity
            else None
        )
        if identity and (
            not service
            or not db.execute(
                "SELECT 1 FROM notification_service_grants WHERE service_id=%s AND project_id=%s", (identity, project)
            ).fetchone()
        ):
            raise Forbidden("mail service is not granted to this project")
        full = NotificationConfig(**((service["config"] if service else {}) | body.get("config", {})))
        if full.email_enabled and not service:
            raise ValueError("select an authorized mail service before enabling delivery")
        secrets = SecretBox(settings.secret_keys).open(service["secrets"]) if service and service["secrets"] else {}
        if full.email_enabled:
            notifications.require_delivery(settings, full, secrets)
        config = full.model_dump()
        cipher = service["secrets"] if service else ""
        revision = expected + 1
        db.execute(
            "INSERT INTO notification_settings(project_id,revision,actor_id,config,secrets,has_api_key,has_smtp_password) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(project_id) DO UPDATE SET revision=EXCLUDED.revision,actor_id=EXCLUDED.actor_id,config=EXCLUDED.config,secrets=EXCLUDED.secrets,has_api_key=EXCLUDED.has_api_key,has_smtp_password=EXCLUDED.has_smtp_password,updated_at=now()",
            (
                project,
                revision,
                user["id"],
                Jsonb(config),
                cipher,
                bool(secrets.get("api_key")),
                bool(secrets.get("smtp_password")),
            ),
        )
        db.execute(
            "INSERT INTO notification_versions(project_id,revision,actor_id,config) VALUES(%s,%s,%s,%s)",
            (project, revision, user["id"], Jsonb(config)),
        )
        db.execute(
            "INSERT INTO notification_rule_bindings(project_id,service_id,service_revision,policy_revision,updated_by) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(project_id) DO UPDATE SET service_id=EXCLUDED.service_id,service_revision=EXCLUDED.service_revision,policy_revision=EXCLUDED.policy_revision,updated_by=EXCLUDED.updated_by,updated_at=now()",
            (project, identity, service["revision"] if service else None, revision, user["id"]),
        )
        from .execution_health import configure

        configure(db, project, revision, full)
        db.execute(
            "INSERT INTO audit(user_id,action,resource,details) VALUES(%s,'notification.rules',%s,%s)",
            (
                user["id"],
                str(project),
                Jsonb({"revision": revision, "service_id": str(identity) if identity else None}),
            ),
        )
        return policy_view(db)


def policy_view(db):
    policy = notifications.get_policy(db)
    binding = db.execute(
        "SELECT service_id,service_revision FROM notification_rule_bindings WHERE project_id::text=current_setting('tm.project_id',true)"
    ).fetchone()
    return (
        policy
        | (binding or {"service_id": None, "service_revision": None})
        | {"rules": {key: value for key, value in policy["config"].items() if key in RULES}}
    )


def register(app):
    def actor(request, write=False):
        user = auth.identity(request, mutate=write)
        return permissions.require(app.state.db, user, "services.manage" if write else "services.read")

    @app.get("/api/v2/services/notifications")
    def services(request: Request):
        actor(request)
        with app.state.db.tx() as db:
            items = db.execute("SELECT " + PUBLIC + " FROM notification_services ORDER BY name,id").fetchall()
            for row in items:
                grants = db.execute(
                    "SELECT g.project_id,p.name AS project_name FROM notification_service_grants g JOIN projects p ON p.id=g.project_id WHERE g.service_id=%s ORDER BY p.name",
                    (row["id"],),
                ).fetchall()
                row.update(grants=grants, project_ids=[g["project_id"] for g in grants])
        defaults = {key: value for key, value in NotificationConfig().model_dump().items() if key in TRANSPORT}
        return {
            "items": items,
            "defaults": defaults,
            "schema": {
                key: value
                for key, value in NotificationConfig.model_json_schema()["properties"].items()
                if key in TRANSPORT
            },
        }

    def save(request, body, identity=None):
        user = actor(request, True)
        if set(body.config) - TRANSPORT:
            raise ValueError("mail transport must not contain project rules or recipients")
        if body.api_key and body.clear_api_key or body.smtp_password and body.clear_smtp_password:
            raise ValueError("cannot set and clear the same credential")
        config = {
            key: value for key, value in NotificationConfig(**body.config).model_dump().items() if key in TRANSPORT
        }
        box, identity = SecretBox(app.state.settings.secret_keys), identity or uuid4()
        with app.state.db.tx() as db:
            db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,738349269))", (str(identity),))
            current = db.execute("SELECT * FROM notification_services WHERE id=%s FOR UPDATE", (identity,)).fetchone()
            revision = current["revision"] if current else 0
            if revision != body.expected_revision:
                raise Conflict("mail service changed; reload before saving")
            secrets = box.open(current["secrets"]) if current and current["secrets"] else {}
            for key in ("api_key", "smtp_password"):
                if getattr(body, "clear_" + key):
                    secrets.pop(key, None)
                elif getattr(body, key):
                    secrets[key] = getattr(body, key)
            cipher = box.seal(secrets) if secrets else ""
            row = db.execute(
                "INSERT INTO notification_services(id,name,revision,config,secrets,has_api_key,has_smtp_password,created_by) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET name=EXCLUDED.name,revision=EXCLUDED.revision,config=EXCLUDED.config,secrets=EXCLUDED.secrets,has_api_key=EXCLUDED.has_api_key,has_smtp_password=EXCLUDED.has_smtp_password,updated_at=now() RETURNING "
                + PUBLIC,
                (
                    identity,
                    body.name,
                    revision + 1,
                    Jsonb(config),
                    cipher,
                    bool(secrets.get("api_key")),
                    bool(secrets.get("smtp_password")),
                    user["id"],
                ),
            ).fetchone()
            db.execute(
                "INSERT INTO notification_service_versions(service_id,revision,config,actor_id) VALUES(%s,%s,%s,%s)",
                (identity, revision + 1, Jsonb(config), user["id"]),
            )
            projects = list(dict.fromkeys(body.project_ids))
            if db.execute("SELECT count(*) AS n FROM projects WHERE id=ANY(%s)", (projects,)).fetchone()["n"] != len(
                projects
            ):
                raise NotFound("project grant target does not exist")
            db.execute("DELETE FROM notification_service_grants WHERE service_id=%s", (identity,))
            for project in projects:
                db.execute(
                    "INSERT INTO notification_service_grants(service_id,project_id,granted_by) VALUES(%s,%s,%s)",
                    (identity, project, user["id"]),
                )
            db.execute(
                "INSERT INTO audit(user_id,action,resource,details) VALUES(%s,'notification.service',%s,%s)",
                (
                    user["id"],
                    str(identity),
                    Jsonb({"revision": revision + 1, "project_ids": [str(p) for p in projects]}),
                ),
            )
            return row | {"project_ids": projects}

    @app.post("/api/v2/services/notifications", status_code=201)
    def create_service(body: ServiceEdit, request: Request):
        return save(request, body)

    @app.put("/api/v2/services/notifications/{identity}")
    def edit_service(identity: UUID, body: ServiceEdit, request: Request):
        return save(request, body, identity)

    def inbox(request):
        user = auth.identity(request)
        if not permissions.has_action(user, "research.read") or user.get("delegation_id"):
            raise Forbidden("personal notification inbox requires research access")
        return user

    def notices_scope(db, user):
        all_projects = user["superadmin"] or any(
            g["action"] == "research.read" and g["scope"] == "all_projects" for g in user["permissions"]
        )
        return all_projects, user["id"]

    @app.get("/api/v2/notifications")
    def notices(
        request: Request,
        before: int | None = Query(None, ge=1),
        limit: int = Query(30, ge=1, le=100),
        unread: bool = False,
    ):
        user = inbox(request)
        with app.state.db.tx() as db:
            all_projects, identity = notices_scope(db, user)
            # Explicit authorized project contexts make this independent of any
            # page-selected project and keep project-bound RLS intact.
            projects = db.execute(
                "SELECT p.id FROM projects p WHERE %s OR EXISTS(SELECT 1 FROM members m WHERE m.project_id=p.id AND m.user_id=%s)",
                (all_projects, identity),
            ).fetchall()
            rows = []
            for project in projects:
                db.execute("SELECT set_config('tm.project_id',%s,true)", (str(project["id"]),))
                rows.extend(
                    notifications.list_notices(db, identity, before=before, limit=limit, unread=unread)["items"]
                )
            rows.sort(key=lambda row: row["ordinal"], reverse=True)
            return {"items": rows[:limit], "next": rows[limit - 1]["ordinal"] if len(rows) > limit else None}

    @app.get("/api/v2/notifications/unread")
    def unread(request: Request):
        user = inbox(request)
        with app.state.db.tx() as db:
            all_projects, identity = notices_scope(db, user)
            projects = db.execute(
                "SELECT p.id FROM projects p WHERE %s OR EXISTS(SELECT 1 FROM members m WHERE m.project_id=p.id AND m.user_id=%s)",
                (all_projects, identity),
            ).fetchall()
            count = 0
            for project in projects:
                db.execute("SELECT set_config('tm.project_id',%s,true)", (str(project["id"]),))
                count += db.execute(
                    "SELECT count(*) AS n FROM notifications n WHERE NOT EXISTS(SELECT 1 FROM notification_reads r WHERE r.notification_id=n.id AND r.user_id=%s)",
                    (identity,),
                ).fetchone()["n"]
            return {"unread": count}

    @app.post("/api/v2/notifications/read")
    def read(body: NotificationRead, request: Request):
        user = auth.identity(request, mutate=True)
        if user.get("delegation_id"):
            raise Forbidden("delegations cannot mark personal notifications")
        with app.state.db.tx() as db:
            ids = list(dict.fromkeys(body.ids))
            all_projects, identity = notices_scope(db, user)
            projects = db.execute(
                "SELECT p.id FROM projects p WHERE %s OR EXISTS(SELECT 1 FROM members m WHERE m.project_id=p.id AND m.user_id=%s)",
                (all_projects, identity),
            ).fetchall()
            found = []
            for project in projects:
                db.execute("SELECT set_config('tm.project_id',%s,true)", (str(project["id"]),))
                matching = db.execute("SELECT id FROM notifications WHERE id=ANY(%s)", (ids,)).fetchall()
                subset = [r["id"] for r in matching]
                if subset:
                    notifications.mark_read(db, project["id"], identity, subset)
                found.extend(subset)
            if set(found) != set(ids):
                raise NotFound("notification absent or inaccessible")
        return {"ok": True}
