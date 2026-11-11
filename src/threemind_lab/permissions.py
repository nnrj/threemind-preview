"""Fresh platform authorization. Each operation and resource scope form one grant."""
from __future__ import annotations

import re
from contextlib import nullcontext
from contextvars import ContextVar
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from .database import Conflict, Forbidden, NotFound

LOCAL_USER = UUID("00000000-0000-4000-8000-000000000001")
actor_context: ContextVar[dict | None] = ContextVar("threemind_platform_actor", default=None)
SCOPES = ("platform", "all_projects", "member_projects", "own")

def _action(key, title, scopes):
    return {"id": key, "title": title, "category": key.split(".")[0], "scopes": list(scopes)}

ACTIONS = [
    _action(key, title, ("platform",)) for key, title in (
        ("system.read", "查看平台配置"), ("system.write", "修改平台配置"),
        ("execution.read", "查看宿主执行队列和调度回执"),
        ("accounts.read", "查看账号"), ("accounts.manage", "管理账号"),
        ("roles.read", "查看角色"), ("roles.manage", "管理角色"),
        ("services.manage", "管理服务"),
        ("projects.create", "创建项目"),
    )
] + [
    _action(key, title, ("all_projects", "member_projects")) for key, title in (
        ("projects.read", "查看项目"), ("projects.manage", "管理项目"),
        ("research.read", "查看研究资料"), ("research.write", "登记研究资料"),
        ("research.manage", "管理研究资料"), ("runs.read", "查看意识"),
        ("runs.create", "创建意识"), ("runs.control", "旧运行控制入口"),
        ("runs.configure", "配置意识"), ("runs.pause", "暂停意识"),
        ("runs.resume", "继续意识"), ("runs.stimulate", "递送刺激"),
        ("runs.intervene", "显式干预"), ("runs.checkpoint", "保存恢复点"),
        ("runs.restore", "恢复意识"), ("runs.export", "导出意识"),
        ("runs.observe", "观察意识"), ("experiments.read", "查看实验"),
        ("experiments.create", "创建实验"), ("experiments.control", "执行实验"),
        ("worlds.read", "查看世界与身体"), ("worlds.write", "编辑世界与身体"),
        ("worlds.use", "使用世界与身体"), ("reports.read", "查看记录和报告"),
        ("reports.write", "编写记录和报告"), ("reports.export", "导出报告"),
        ("reports.share", "分享报告"),
    )
] + [
    _action("services.read", "查看服务目录", ("platform", "all_projects", "member_projects")),
    _action("services.use", "调用服务", ("platform", "all_projects", "member_projects")),
    _action("tools.read", "查看工具", ("platform", "all_projects", "member_projects")),
    _action("tools.use", "执行工具", ("platform", "all_projects", "member_projects")),
] + [
    _action(key, title, ("platform", "all_projects", "member_projects", "own") if key.startswith("data.") else ("all_projects", "member_projects", "own")) for key, title in (
        ("data.read", "查看原件"), ("data.export", "导出数据"),
        ("data.import", "导入数据"), ("data.delete", "删除数据"),
        ("data.manage", "迁移和管理数据"), ("notes.read", "查看笔记"),
        ("notes.write", "编写笔记"), ("notes.delete", "删除笔记"),
    )
] + [
    _action("menu." + name, "菜单：" + name, ("platform",)) for name in (
        "workbench", "projects", "overview", "kernels", "experiments", "worlds", "conversation", "comparisons",
        "query", "models", "notes", "reports", "data", "settings", "docs", "accounts",
    )
]
ACTION_INDEX = {item["id"]: item for item in ACTIONS}
DELEGATION_FORBIDDEN = {"accounts", "roles", "system", "menu"}
RESOURCE_KINDS = ("project", "run", "experiment", "service")

def current_actor():
    return actor_context.get()

def catalogue():
    return {"actions": ACTIONS, "scopes": [
        {"id": "platform", "title": "平台"}, {"id": "all_projects", "title": "所有项目"},
        {"id": "member_projects", "title": "已加入项目"}, {"id": "own", "title": "本人资料"},
    ]}

def validate_grants(values):
    if not isinstance(values, list) or len(values) > 512:
        raise ValueError("权限必须为最多512项的操作与范围列表")
    result, seen = [], set()
    for value in values:
        if not isinstance(value, dict) or set(value) != {"action", "scope"}:
            raise ValueError("每项权限必须明确指定action及scope")
        action, scope = value["action"], value["scope"]
        if action not in ACTION_INDEX or scope not in ACTION_INDEX[action]["scopes"]:
            raise ValueError("未知操作或不适用的权限范围")
        if (action, scope) not in seen:
            result.append({"action": action, "scope": scope})
            seen.add((action, scope))
    return sorted(result, key=lambda item: (item["action"], item["scope"]))

def grant_covers(available, requested):
    if available["action"] != requested["action"]:
        return False
    scope = available["scope"]
    return scope == requested["scope"] or (
        scope == "all_projects" and requested["scope"] in ("member_projects", "own")
    ) or (scope == "member_projects" and requested["scope"] == "own")

def check_grantable(actor, grants):
    if actor.get("delegation_id"):
        raise Forbidden("委托凭据不能管理角色或签发进一步权限")
    if actor.get("superadmin"):
        return
    if any(not any(grant_covers(existing, grant) for existing in actor["permissions"]) for grant in grants):
        raise Forbidden("不能分配超出本人有效权限的操作或范围")

def enrich(database, user):
    """Caller flags never confer authority; roles and delegations are read fresh."""
    with database.tx() as db:
        account = db.execute("SELECT id,username,admin,enabled,created_at FROM users WHERE id=%s", (user["id"],)).fetchone()
        if not account or not account["enabled"]:
            raise Forbidden("账号不存在或已停用")
        roles = db.execute(
            "SELECT r.id,r.key,r.name,r.builtin,r.revision,r.permissions FROM platform_roles r "
            "JOIN platform_user_roles u ON u.role_id=r.id WHERE u.user_id=%s ORDER BY r.key", (account["id"],)
        ).fetchall()
        delegated = None
        if user.get("delegation_id"):
            delegated = db.execute("SELECT * FROM platform_delegations WHERE id=%s AND user_id=%s "
                                   "AND revoked_at IS NULL AND expires_at>now()",
                                   (user["delegation_id"], account["id"])).fetchone()
            if not delegated:
                raise Forbidden("委托凭据已失效或被撤销")
    grants = [{"action": a, "scope": s} for a, s in sorted({(p["action"], p["scope"]) for role in roles for p in role["permissions"]})]
    root = any(role["key"] == "superadmin" for role in roles)
    fresh = account | {
        "admin": any(role["key"] in ("superadmin", "admin") for role in roles),
        "superadmin": root,
        "roles": [{key: role[key] for key in ("id", "key", "name", "builtin", "revision")} for role in roles],
        "permissions": grants,
    }
    for key in ("csrf", "auth_type", "expires_at", "remembered", "source", "_request_resources", "_request_action"):
        if key in user:
            fresh[key] = user[key]
    if delegated:
        # Intersect each complete action/scope pair; never combine roles' scopes.
        narrowed = []
        for allowed in delegated["actions"]:
            for held in grants:
                if held["action"] != allowed["action"]:
                    continue
                if grant_covers(held, allowed):
                    narrowed.append(allowed)
                elif grant_covers(allowed, held):
                    narrowed.append(held)
            if root:
                narrowed.append(allowed)
        fresh.update(superadmin=False, admin=False, delegation_id=delegated["id"],
                     permissions=validate_grants(narrowed), resources=delegated["resources"],
                     source=delegated["source"], auth_type="delegation", expires_at=delegated["expires_at"])
    return fresh

def _resource_allowed(user, resources=None):
    if not user.get("delegation_id"):
        return True
    requested = resources if resources is not None else user.get("_request_resources", [])
    allowed = {(r["kind"], str(r["id"])) for r in user["resources"]}
    # A project-wide delegation authorizes children, but a child delegation
    # never authorizes project-wide listings or aggregate metadata.
    return any((r["kind"], str(r["id"])) in allowed for r in requested)

def _scope_allowed(user, action, *, project=None, owner_id=None, member=False, resources=None):
    if not _resource_allowed(user, resources):
        return False
    if user.get("superadmin"):
        return True
    for grant in user.get("permissions", []):
        if grant["action"] != action:
            continue
        scope = grant["scope"]
        if scope == "platform" and project is None and owner_id is None:
            return True
        if scope == "all_projects" and project is not None:
            return True
        if scope == "member_projects" and project is not None and member:
            return True
        if scope == "own" and owner_id is not None and str(owner_id) == str(user["id"]) and (project is None or member):
            return True
    return False

def has_action(user, action):
    """Navigation/aggregate filter only; concrete objects still need require."""
    return bool(user.get("superadmin") or any(g["action"] == action for g in user.get("permissions", [])))

def allows(database, user, action, *, project=None, owner_id=None, resources=None):
    fresh = enrich(database, user)
    member = False
    if project is not None:
        with database.tx() as db:
            member = db.execute("SELECT 1 FROM members WHERE project_id=%s AND user_id=%s", (project, fresh["id"])).fetchone() is not None
    return _scope_allowed(fresh, action, project=project, owner_id=owner_id, member=member, resources=resources)

def require(database, user, action, *, project=None, owner_id=None, resources=None):
    if action not in ACTION_INDEX:
        raise ValueError("unknown platform permission action")
    fresh = enrich(database, user)
    member = False
    if project is not None:
        with database.tx() as db:
            member = db.execute("SELECT 1 FROM members WHERE project_id=%s AND user_id=%s", (project, fresh["id"])).fetchone() is not None
    if not _scope_allowed(fresh, action, project=project, owner_id=owner_id, member=member, resources=resources):
        raise Forbidden("当前账号没有此操作及资料范围的权限")
    return fresh

def resolve_actor(database, actor):
    """UUID-only legacy services retain a matching authenticated delegation."""
    if isinstance(actor, dict):
        return enrich(database, actor)
    current = current_actor()
    return enrich(database, current if current and str(current["id"]) == str(actor) else {"id": actor})


def connection_access(conn, actor, project, *, action, write=False, owner=False):
    """Fresh checks inside an existing transaction; no second pool is opened."""
    class Bound:
        def tx(self, *args, **kwargs):
            return nullcontext(conn)
    database = Bound()
    principal = resolve_actor(database, actor)
    result = project_access(database, principal, project, action=action, write=write, owner=owner)
    set_context(conn, principal, project, action=action)
    return result


def _connection_database(conn):
    """Bind identity checks to an already locked account transaction."""
    class Bound:
        def tx(self, *args, **kwargs):
            return nullcontext(conn)
    return Bound()

def project_access(database, user, project, *, write=False, owner=False, action=None, resources=None):
    fresh = enrich(database, user)
    action = action or fresh.get("_request_action") or ("research.manage" if owner else "research.write" if write else "research.read")
    if resources is None:
        resources = fresh.get("_request_resources") or [{"kind": "project", "id": str(project)}]
    with database.tx() as db:
        row = db.execute("SELECT p.name,m.role FROM projects p LEFT JOIN members m ON m.project_id=p.id "
                         "AND m.user_id=%s WHERE p.id=%s", (fresh["id"], project)).fetchone()
    if not row:
        raise NotFound("project not found")
    member = row["role"] is not None
    if not _scope_allowed(fresh, action, project=project, owner_id=fresh["id"], member=member, resources=resources):
        raise Forbidden("project access denied")
    global_access = fresh["superadmin"] or any(g["action"] == action and g["scope"] == "all_projects" for g in fresh["permissions"])
    if not global_access and (owner and row["role"] != "owner" or write and row["role"] not in ("owner", "researcher")):
        raise Forbidden("project access denied")
    return row | {"role": ("owner" if fresh["superadmin"] or owner else "researcher" if write else "viewer") if global_access else row["role"]}

def set_context(conn, user, project=None, *, action="research.read"):
    """Transaction-local flags, set only from authenticated host context."""
    user = user or {}
    action = user.get("_request_action") or action
    all_projects = any(g["action"] == action and g["scope"] == "all_projects" for g in user.get("permissions", []))
    scoped_projects = [str(r["id"]) for r in user.get("resources", []) if r["kind"] == "project"]
    # Explicit resource methods still check child IDs. Narrow delegates do not
    # acquire the global browsing RLS route used by an unrestricted role.
    if user.get("delegation_id") and not scoped_projects:
        all_projects = False
    for key, value in (
        ("tm.platform_superadmin", "true" if user.get("superadmin") else "false"),
        ("tm.permission_all_projects", "true" if all_projects else "false"),
        ("tm.permission_actor_id", str(user.get("id", ""))),
        ("tm.permission_domain", action.split(".")[0]),
        ("tm.permission_projects", ",".join(scoped_projects)),
        ("tm.permission_private_notes", "true" if any(g["action"] == action and action.startswith("notes.") and g["scope"] in ("member_projects", "all_projects") for g in user.get("permissions", [])) else "false"),
        ("tm.permission_mutation", "false" if action.endswith((".read", ".observe")) else "true"),
        ("tm.permission_metadata_only", "false"),
        ("tm.permission_metadata_tables", ""),
    ):
        conn.execute("SELECT set_config(%s,%s,true)", (key, value))

def request_resources(request):
    """Trusted route/query identities, never user-supplied authority flags."""
    parts = request.url.path.strip("/").split("/")
    names = {"projects": "project", "runs": "run", "experiments": "experiment", "providers": "service"}
    resources = []
    for i, part in enumerate(parts[:-1]):
        if part in names:
            try:
                resources.append({"kind": names[part], "id": str(UUID(parts[i + 1]))})
            except ValueError:
                pass
    project = request.query_params.get("project")
    if project:
        try:
            resources.append({"kind": "project", "id": str(UUID(project))})
        except ValueError:
            pass
    return resources

def command_action(kind):
    return {
        "pause": "runs.pause", "cancel": "runs.pause", "resume": "runs.resume",
        "advance": "runs.resume", "stimulus": "runs.stimulate", "input": "runs.stimulate",
        "intervene": "runs.intervene", "intervention": "runs.intervene", "robot_control": "runs.intervene",
        "checkpoint": "runs.checkpoint", "readout_observe": "runs.observe",
        "restore": "runs.restore", "configure": "runs.configure", "close_inputs": "runs.configure",
    }.get(kind, "runs.control")

def request_action(request):
    path, method = request.url.path, request.method
    write = method not in ("GET", "HEAD", "OPTIONS")
    if "/accounts/users" in path or "/admin/users" in path:
        return "accounts.manage" if write else "accounts.read"
    if "/accounts/roles" in path:
        return "roles.manage" if write else "roles.read"
    if "/auth/" in path or path.endswith(("/session", "/me", "/login", "/logout")) or "/account/" in path:
        return None
    if path.endswith("/configuration-template") and "/runs/" in path:
        # Copying saved configuration never configures or pauses the individual.
        # The handler separately requires platform system.write for the template.
        return "runs.read"
    project_path = re.fullmatch(r"/api/v2/projects/[^/]+(?:/(members|configuration/defaults|notifications/settings|notifications/versions))?", path)
    if project_path:
        return "projects.manage" if write else "projects.read"
    if "/runs/" in path and write:
        if any(word in path for word in ("/inputs", "/media", "/uploads", "/stimuli", "/live-capture")):
            return "runs.stimulate"
        if "/organs" in path:
            return "runs.configure"
    if "/ai-tools" in path:
        if not write:
            return "runs.read"
        return "services.use" if "/requests" in path else "runs.configure"
    if "/configuration/validate" in path:
        return "tools.read"
    if "/ai/" in path or "/providers" in path or "/services/notifications" in path or "/admin/ai" in path:
        if path.endswith(("/test", "/diagnose", "/chat", "/generate")) and write:
            return "services.use"
        if "/services/notifications" in path:
            return "services.manage" if write else "services.read"
        return "services.use" if write and not any(s in path for s in ("/providers", "/grants", "/credentials")) else "services.manage" if write else "services.read"
    if "/configuration/defaults" in path or "/configuration/templates" in path:
        return "system.write" if write else "tools.read"
    if path == "/api/v2/admin/execution" or path.startswith("/api/v2/admin/execution/"):
        # Inspecting host queues is distinct from reading public system defaults.
        # Pure limit validation is read-only; saving limits remains system.write.
        return "system.write" if write and path != "/api/v2/admin/execution/validate" else "execution.read"
    if "/settings" in path or "/admin" in path or "/system/" in path:
        return "system.write" if write else "system.read"
    if "/notes" in path or "/notebooks" in path or "/note-assets" in path or "/note-collections" in path:
        return "notes.delete" if method == "DELETE" else "notes.write" if write else "notes.read"
    if "/data" in path or "/artifacts" in path or "/media" in path or "/bundles" in path:
        if any(word in path for word in ("/exports", "/export")):
            return "data.export"
        if "/imports" in path or "/import" in path or "/restore" in path:
            return "data.import"
        return "data.delete" if method == "DELETE" else "data.manage" if write else "data.read"
    if "/world" in path or "/robot" in path or "/bodies" in path:
        return "worlds.write" if write else "worlds.read"
    if "/research-generation" in path:
        return "services.use" if write else "reports.read"
    if "/reports" in path or "/documents" in path or "/research-documents" in path or "/studies" in path or "/report-" in path:
        if "/exports" in path and write:
            return "reports.export"
        return "reports.share" if "/shares" in path and write else "reports.write" if write else "reports.read"
    if "/experiments" in path or "/evolution" in path or "/ecology" in path or "/assessments" in path:
        if write and path.endswith("/experiments"):
            return "experiments.create"
        return "experiments.control" if write else "experiments.read"
    if "/runs" in path:
        if path.endswith("/forks") and write:
            return "runs.create"
        if "/exports" in path:
            return "runs.export"
        if "/restore" in path:
            return "runs.restore"
        if "/checkpoints" in path and write:
            return "runs.checkpoint"
        if path.endswith("/runs") and write:
            return "runs.create"
        if any(word in path for word in ("/configuration", "/config", "/body", "/peripherals", "/resources", "/energy", "/spatial")) and write:
            return "runs.configure"
        return "runs.control" if write else "runs.read"
    if path.endswith("/projects"):
        return "projects.create" if write else "projects.read"
    if "/projects/" in path:
        return "research.write" if write else "research.read"
    return "tools.use" if write else "tools.read"

def execution_actor(user=None):
    """Persist original principal and delegation; never save a flattened root."""
    user = user or current_actor()
    if not user:
        return None
    result = {"user_id": str(user["id"]), "source": user.get("source", "human")}
    if user.get("delegation_id"):
        result["delegation_id"] = str(user["delegation_id"])
    return result

def restore_execution_actor(database, lineage, *, action=None, project=None, resources=None):
    if not lineage or not lineage.get("user_id"):
        raise Forbidden("后台任务缺少可核验执行主体")
    user = {"id": lineage["user_id"], "source": lineage.get("source", "script")}
    if lineage.get("delegation_id"):
        user["delegation_id"] = lineage["delegation_id"]
    user = enrich(database, user)
    if resources is not None:
        user["_request_resources"] = resources
    if action:
        user = require(database, user, action, project=project, resources=resources)
        user["_request_action"] = action
    actor_context.set(user)
    return user

def list_roles(database):
    with database.tx() as db:
        return db.execute("SELECT * FROM platform_roles ORDER BY builtin DESC,key").fetchall()

def list_users(database):
    with database.tx() as db:
        rows = db.execute("SELECT id,username,admin,enabled,created_at FROM users ORDER BY created_at,id").fetchall()
    result = []
    for row in rows:
        with database.tx() as db:
            roles = db.execute("SELECT r.id,r.key,r.name,r.builtin,r.revision FROM platform_roles r JOIN "
                               "platform_user_roles u ON u.role_id=r.id WHERE u.user_id=%s ORDER BY r.key", (row["id"],)).fetchall()
        result.append(row | {"roles": roles, "superadmin": any(r["key"] == "superadmin" for r in roles)})
    return result

def _accounts_lock(db):
    db.execute("SELECT pg_advisory_xact_lock(738349230)")

def _roles(db, ids):
    ids = list(dict.fromkeys(UUID(str(value)) for value in ids))
    if not ids or len(ids) > 64:
        raise ValueError("账号必须具有1至64个角色")
    rows = db.execute("SELECT * FROM platform_roles WHERE id=ANY(%s) ORDER BY key FOR SHARE", (ids,)).fetchall()
    if len(rows) != len(ids):
        raise NotFound("role not found")
    return ids, rows

def _guard_last_superadmin(db, target, removing):
    if removing and not db.execute(
        "SELECT 1 FROM platform_user_roles ur JOIN platform_roles r ON r.id=ur.role_id JOIN users u ON u.id=ur.user_id "
        "WHERE r.key='superadmin' AND u.enabled AND u.password_hash IS NOT NULL AND u.id<>%s LIMIT 1", (target,)
    ).fetchone():
        raise Conflict("不能停用或移除最后一个可登录的超级管理员")

def check_roles_grantable(database, actor, ids):
    actor = enrich(database, actor)
    with database.tx() as db:
        _, roles = _roles(db, ids)
    if any(r["key"] == "superadmin" for r in roles) and not actor["superadmin"]:
        raise Forbidden("只有超级管理员可以分配超级管理员")
    check_grantable(actor, [g for r in roles for g in r["permissions"]])

def assign_roles(database, actor, target, ids):
    actor = require(database, actor, "accounts.manage")
    check_roles_grantable(database, actor, ids)
    with database.tx() as db:
        _accounts_lock(db)
        actor = require(_connection_database(db), actor, "accounts.manage")
        account = db.execute("SELECT * FROM users WHERE id=%s FOR UPDATE", (target,)).fetchone()
        if not account:
            raise NotFound("account not found")
        ids, roles = _roles(db, ids)
        check_grantable(actor, [grant for role in roles for grant in role["permissions"]])
        old_super = db.execute("SELECT 1 FROM platform_user_roles ur JOIN platform_roles r ON r.id=ur.role_id "
                               "WHERE ur.user_id=%s AND r.key='superadmin'", (target,)).fetchone()
        new_super = any(r["key"] == "superadmin" for r in roles)
        if (old_super or new_super) and not actor["superadmin"]:
            raise Forbidden("只有超级管理员可以调整超级管理员账号")
        _guard_last_superadmin(db, target, bool(old_super and not new_super))
        db.execute("DELETE FROM platform_user_roles WHERE user_id=%s", (target,))
        for role in ids:
            db.execute("INSERT INTO platform_user_roles VALUES(%s,%s)", (target, role))
        db.execute("UPDATE users SET admin=%s WHERE id=%s", (any(r["key"] in ("admin", "superadmin") for r in roles), target))
        db.execute("DELETE FROM sessions WHERE user_id=%s", (target,))
        db.execute("INSERT INTO audit(user_id,action,resource,details) VALUES(%s,'account.roles',%s,%s)",
                   (actor["id"], str(target), Jsonb({"role_ids": [str(v) for v in ids]})))
    return {"ok": True}

def set_enabled(database, actor, target, enabled):
    actor = require(database, actor, "accounts.manage")
    with database.tx() as db:
        _accounts_lock(db)
        actor = require(_connection_database(db), actor, "accounts.manage")
        if not db.execute("SELECT id FROM users WHERE id=%s FOR UPDATE", (target,)).fetchone():
            raise NotFound("account not found")
        superadmin = bool(db.execute("SELECT 1 FROM platform_user_roles ur JOIN platform_roles r ON r.id=ur.role_id "
                                    "WHERE ur.user_id=%s AND r.key='superadmin'", (target,)).fetchone())
        if superadmin and not actor["superadmin"]:
            raise Forbidden("只有超级管理员可以调整超级管理员账号")
        _guard_last_superadmin(db, target, superadmin and not enabled)
        db.execute("UPDATE users SET enabled=%s WHERE id=%s", (enabled, target))
        db.execute("DELETE FROM sessions WHERE user_id=%s", (target,))
        db.execute("UPDATE platform_delegations SET revoked_at=now() WHERE user_id=%s AND revoked_at IS NULL", (target,))
        db.execute("INSERT INTO audit(user_id,action,resource) VALUES(%s,'account.enabled',%s)", (actor["id"], str(target)))
    return {"ok": True}

def save_role(database, actor, *, key=None, name, grants, role_id=None, expected_revision=0):
    actor = require(database, actor, "roles.manage")
    grants = validate_grants(grants)
    check_grantable(actor, grants)
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise ValueError("角色名称长度必须为1至80")
    with database.tx() as db:
        _accounts_lock(db)
        actor = require(_connection_database(db), actor, "roles.manage")
        check_grantable(actor, grants)
        row = db.execute("SELECT * FROM platform_roles WHERE id=%s FOR UPDATE", (role_id,)).fetchone() if role_id else None
        if role_id and not row:
            raise NotFound("role not found")
        if row and row["key"] == "superadmin":
            raise Forbidden("内置超级管理员角色不可修改")
        # An ordinary administrator cannot remove or alter a role whose
        # existing authority exceeds their own, even by first narrowing it.
        if row:
            check_grantable(actor, row["permissions"])
        if (row["revision"] if row else 0) != expected_revision:
            raise Conflict("角色已更新，请重新载入")
        if row:
            result = db.execute("UPDATE platform_roles SET name=%s,permissions=%s,revision=revision+1,updated_at=now() "
                                "WHERE id=%s RETURNING *", (name.strip(), Jsonb(grants), role_id)).fetchone()
        else:
            if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{2,63}", key) or key in ("superadmin", "admin", "user"):
                raise ValueError("请使用3至64位非内置英文角色标识")
            role_id = uuid4()
            result = db.execute("INSERT INTO platform_roles(id,key,name,permissions) VALUES(%s,%s,%s,%s) RETURNING *",
                                (role_id, key, name.strip(), Jsonb(grants))).fetchone()
        db.execute("INSERT INTO audit(user_id,action,resource,details) VALUES(%s,'role.save',%s,%s)",
                   (actor["id"], str(role_id), Jsonb({"revision": result["revision"]})))
    return result

def delete_role(database, actor, role_id):
    actor = require(database, actor, "roles.manage")
    with database.tx() as db:
        _accounts_lock(db)
        actor = require(_connection_database(db), actor, "roles.manage")
        role = db.execute("SELECT * FROM platform_roles WHERE id=%s FOR UPDATE", (role_id,)).fetchone()
        if not role:
            raise NotFound("role not found")
        if role["builtin"]:
            raise Conflict("内置角色不可删除")
        check_grantable(actor, role["permissions"])
        if db.execute("SELECT 1 FROM platform_user_roles WHERE role_id=%s LIMIT 1", (role_id,)).fetchone():
            raise Conflict("角色仍已分配，请先调整相关账号")
        db.execute("DELETE FROM platform_roles WHERE id=%s", (role_id,))
        db.execute("INSERT INTO audit(user_id,action,resource) VALUES(%s,'role.delete',%s)", (actor["id"], str(role_id)))
    return {"ok": True}
