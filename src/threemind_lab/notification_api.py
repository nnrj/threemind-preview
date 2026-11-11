from uuid import UUID

from fastapi import Query, Request

from . import notifications
from .notification_schema import NotificationConfig, NotificationEdit, NotificationRead, NotificationTest
from .platform_notifications import available, bind_policy, policy_view


def register_notification_routes(app, access):
    prefix = "/api/v2/projects/{project}/notifications"

    @app.get(prefix + "/execution-health")
    def health(project: UUID, request: Request):
        from .health_schema import METRICS, HealthConfig

        access(request, project)
        with app.state.db.tx(project) as db:
            current = db.execute("SELECT * FROM execution_health_monitors WHERE project_id=%s", (project,)).fetchone()
        return {"monitor": current, "metrics": METRICS, "defaults": HealthConfig().model_dump(mode="json")}

    @app.get(prefix + "/settings")
    def settings(project: UUID, request: Request):
        access(request, project, owner=True)
        with app.state.db.tx(project) as db:
            result = policy_view(db)
        return result | {"defaults": NotificationConfig().model_dump()}

    @app.put(prefix + "/settings")
    def save(project: UUID, request: Request, body: dict):
        actor = access(request, project, owner=True)
        if "service_id" in body:
            return bind_policy(app.state.db, app.state.settings, project, actor, body)
        # Compatibility entry: changing transport/credentials is a platform
        # service-management operation, not a project owner privilege.
        from . import permissions

        edit = NotificationEdit.model_validate(body)
        with app.state.db.tx(project) as db:
            current = notifications.get_policy(db)
        from .platform_notifications import TRANSPORT

        transport_changed = any(edit.config.model_dump()[k] != current["config"][k] for k in TRANSPORT) or any(
            (edit.api_key, edit.smtp_password, edit.clear_api_key, edit.clear_smtp_password)
        )
        if transport_changed:
            permissions.require(app.state.db, actor, "services.manage")
        result = notifications.save_policy(app.state.db, app.state.settings, project, actor["id"], edit)
        if transport_changed:
            # An old API writes an explicit legacy snapshot. Never claim that
            # its newly supplied transport came from an unchanged catalogue ID.
            with app.state.db.tx(project) as db:
                db.execute(
                    "UPDATE notification_rule_bindings SET service_id=NULL,service_revision=NULL,policy_revision=%s,updated_by=%s,updated_at=now() WHERE project_id=%s",
                    (result["revision"], actor["id"], project),
                )
        return result

    @app.get(prefix + "/services")
    def services(project: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            return {"items": available(db, project)}

    @app.post(prefix + "/validate")
    def validate(project: UUID, request: Request, body: NotificationConfig):
        access(request, project, owner=True)
        return {"config": body.model_dump()}

    @app.post(prefix + "/test", status_code=202)
    def test(project: UUID, request: Request, body: NotificationTest):
        actor = access(request, project, owner=True)
        return notifications.request_test(app.state.db, app.state.settings, project, actor["id"], body.request_id)

    @app.get(prefix)
    def notices(
        project: UUID,
        request: Request,
        before: int | None = Query(None, ge=1),
        limit: int = Query(30, ge=1, le=100),
        unread: bool = False,
    ):
        actor = access(request, project)
        with app.state.db.tx(project) as db:
            return notifications.list_notices(db, actor["id"], before=before, limit=limit, unread=unread)

    @app.get(prefix + "/unread")
    def unread_count(project: UUID, request: Request):
        actor = access(request, project)
        with app.state.db.tx(project) as db:
            return db.execute(
                "SELECT count(*) AS unread FROM notifications n WHERE NOT EXISTS(SELECT 1 FROM notification_reads r WHERE r.notification_id=n.id AND r.user_id=%s)",
                (actor["id"],),
            ).fetchone()

    @app.post(prefix + "/read")
    def read(project: UUID, request: Request, body: NotificationRead):
        # Viewing members may mark their own inbox without project write access.
        from .auth import identity

        actor = identity(request, mutate=True)
        app.state.db.authorize(actor, project)
        with app.state.db.tx(project) as db:
            notifications.mark_read(db, project, actor["id"], body.ids)
        return {"ok": True}

    @app.get(prefix + "/versions")
    def versions(
        project: UUID, request: Request, before: int | None = Query(None, ge=1), limit: int = Query(20, ge=1, le=100)
    ):
        access(request, project, owner=True)
        with app.state.db.tx(project) as db:
            rows = db.execute(
                "SELECT revision,config,actor_id,created_at FROM notification_versions WHERE (%s::bigint IS NULL OR revision<%s) ORDER BY revision DESC LIMIT %s",
                (before, before, limit + 1),
            ).fetchall()
        return {"items": rows[:limit], "next": rows[limit - 1]["revision"] if len(rows) > limit else None}
