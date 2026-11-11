from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException, Request
from psycopg.types.json import Jsonb

from . import permissions
from .database import LOCAL_USER, Conflict, Forbidden, NotFound

PASSWORDS = PasswordHasher()
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(24))
SESSION_SECONDS = 12 * 60 * 60
REMEMBER_SECONDS = 30 * 24 * 60 * 60
DELEGATION_SECONDS = REMEMBER_SECONDS

def password_valid(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 1024:
        raise ValueError("password requires 12–1024 characters")

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def request_token(request):
    header = request.headers.get("Authorization", "")
    if header:
        kind, _, token = header.partition(" ")
        if kind.lower() != "bearer" or not token or " " in token:
            raise HTTPException(401, "invalid bearer credential")
        return token, "bearer"
    return request.cookies.get("tm_session", ""), "cookie"

def _source(request, default="human"):
    source = request.headers.get("X-ThreeMind-Execution-Source", default)
    if source not in ("human", "ai", "script"):
        raise HTTPException(422, "unknown execution source")
    return source

def identity(request: Request, *, mutate=False):
    permissions.actor_context.set(None)
    settings, db = request.app.state.settings, request.app.state.db
    peer = request.client.host if request.client else ""
    if settings.mode == "workstation" and peer not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Workstation access requires loopback")
    token, transport = request_token(request)
    if token.startswith("tm_delegate_"):
        if transport != "bearer":
            raise HTTPException(401, "delegations require bearer transport")
        with db.tx() as conn:
            row = conn.execute("SELECT id,user_id FROM platform_delegations WHERE token_hash=%s "
                               "AND expires_at>now() AND revoked_at IS NULL", (digest(token),)).fetchone()
        if not row:
            raise HTTPException(401, "delegation expired or revoked")
        fresh = permissions.enrich(db, {"id": row["user_id"], "delegation_id": row["id"]})
    else:
        with db.tx() as conn:
            user = conn.execute(
                "SELECT u.id,u.username,u.admin,u.enabled,s.csrf,s.expires_at,s.remembered,s.source "
                "FROM sessions s JOIN users u ON u.id=s.user_id "
                "WHERE s.token_hash=%s AND s.expires_at>now() AND u.enabled", (digest(token),)
            ).fetchone()
        if not user:
            raise HTTPException(401, "login required")
        if mutate and transport == "cookie" and not hmac.compare_digest(
            request.headers.get("X-CSRF-Token", ""), user["csrf"]
        ):
            raise HTTPException(403, "invalid CSRF token")
        fresh = permissions.enrich(db, user) | {
            "csrf": user["csrf"], "auth_type": transport, "expires_at": user["expires_at"],
            "remembered": user["remembered"], "source": _source(request, user["source"]),
        }
    fresh["_request_resources"] = permissions.request_resources(request)
    fresh["_request_action"] = permissions.request_action(request)
    permissions.actor_context.set(fresh)
    return fresh

def _insert_session(conn, user_id, *, remember=False, source="human"):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
    expires = datetime.now(UTC) + timedelta(seconds=REMEMBER_SECONDS if remember else SESSION_SECONDS)
    conn.execute("INSERT INTO sessions(token_hash,user_id,csrf,expires_at,remembered,source) VALUES(%s,%s,%s,%s,%s,%s)",
                 (digest(token), user_id, csrf, expires, remember, source))
    return token, csrf, expires

def login(db, username, password, *, remember=False, source="human"):
    permissions.actor_context.set(None)
    if source not in ("human", "ai", "script"):
        raise ValueError("unknown execution source")
    with db.tx() as conn:
        attempts = conn.execute("SELECT count(*) AS n FROM login_attempts WHERE username=%s "
                                "AND occurred_at>now()-interval '10 minutes'", (username,)).fetchone()["n"]
        if attempts >= 10:
            raise HTTPException(429, "Too many login attempts; try later")
        conn.execute("INSERT INTO login_attempts(username) VALUES(%s)", (username,))
        user = conn.execute("SELECT * FROM users WHERE username=%s", (username,)).fetchone()
    try:
        PASSWORDS.verify(user["password_hash"] if user and user["password_hash"] else DUMMY_HASH, password)
        valid = bool(user and user["enabled"] and user["password_hash"])
    except (VerifyMismatchError, InvalidHashError, VerificationError, TypeError):
        valid = False
    if not valid:
        raise HTTPException(401, "invalid username or password")
    with db.tx() as conn:
        conn.execute("DELETE FROM login_attempts WHERE username=%s", (username,))
        conn.execute("DELETE FROM sessions WHERE expires_at<now()")
        token, csrf, expires = _insert_session(conn, user["id"], remember=remember, source=source)
    fresh = permissions.enrich(db, user) | {"csrf": csrf, "remembered": remember, "source": source,
                                          "expires_at": expires, "auth_type": "cookie"}
    permissions.actor_context.set(fresh)
    return token, csrf, fresh

def refresh(request):
    user = identity(request, mutate=True)
    if user.get("delegation_id"):
        raise Forbidden("委托凭据不能续期平台会话")
    old, _ = request_token(request)
    db = request.app.state.db
    with db.tx() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE token_hash=%s AND expires_at>now() FOR UPDATE", (digest(old),)).fetchone()
        if not row:
            raise HTTPException(401, "session no longer available")
        conn.execute("DELETE FROM sessions WHERE token_hash=%s", (digest(old),))
        token, csrf, expires = _insert_session(conn, user["id"], remember=row["remembered"], source=row["source"])
    fresh = permissions.enrich(db, user) | {"csrf": csrf, "expires_at": expires}
    permissions.actor_context.set(fresh)
    return token, csrf, fresh

def logout(request):
    user = identity(request, mutate=True)
    token, _ = request_token(request)
    with request.app.state.db.tx() as conn:
        if user.get("delegation_id"):
            conn.execute("UPDATE platform_delegations SET revoked_at=now() WHERE id=%s", (user["delegation_id"],))
        else:
            conn.execute("DELETE FROM sessions WHERE token_hash=%s", (digest(token),))
    permissions.actor_context.set(None)
    return {"ok": True}

def create_user(db, username, password, *, admin=False, role_ids=None, actor=None):
    if not isinstance(username, str) or not 3 <= len(username) <= 80:
        raise ValueError("username requires 3–80 characters")
    password_valid(password)
    identity_id = uuid4()
    with db.tx() as conn:
        permissions._accounts_lock(conn)
        if actor is not None:
            actor = permissions.require(permissions._connection_database(conn), actor, "accounts.manage")
        if role_ids is None:
            role_ids = [conn.execute("SELECT id FROM platform_roles WHERE key=%s", ("admin" if admin else "user",)).fetchone()["id"]]
        roles, rows = permissions._roles(conn, role_ids)
        if actor is not None:
            permissions.check_grantable(actor, [grant for row in rows for grant in row["permissions"]])
        if any(r["key"] == "superadmin" for r in rows):
            raise Forbidden("新建账号不能直接取得超级管理员；请由超级管理员显式分配角色")
        account = conn.execute("INSERT INTO users(id,username,password_hash,admin) VALUES(%s,%s,%s,%s) "
                               "RETURNING id,username,admin,enabled",
                               (identity_id, username, PASSWORDS.hash(password), any(r["key"] == "admin" for r in rows))).fetchone()
        for role in roles:
            conn.execute("INSERT INTO platform_user_roles VALUES(%s,%s)", (identity_id, role))
    return permissions.enrich(db, account)

def setup_status(db):
    with db.tx() as conn:
        user = conn.execute("SELECT id,username,password_hash,enabled FROM users WHERE id=%s", (LOCAL_USER,)).fetchone()
    return {"required": bool(user and not user["password_hash"]), "username": user["username"] if user else "local",
            "user_id": LOCAL_USER}

def setup_local(db, password, *, username=None):
    password_valid(password)
    if username is not None and not 3 <= len(username) <= 80:
        raise ValueError("username requires 3–80 characters")
    encoded = PASSWORDS.hash(password)
    with db.tx() as conn:
        permissions._accounts_lock(conn)
        row = conn.execute("SELECT * FROM users WHERE id=%s FOR UPDATE", (LOCAL_USER,)).fetchone()
        if not row:
            raise NotFound("local account not initialized; run explicit schema migration")
        if row["password_hash"]:
            raise Conflict("首次设置已经完成，请正常登录")
        if not row["enabled"]:
            raise Forbidden("local administrator is disabled")
        name = username or row["username"]
        if conn.execute("SELECT id FROM users WHERE username=%s AND id<>%s", (name, LOCAL_USER)).fetchone():
            raise Conflict("username already exists")
        conn.execute("UPDATE users SET username=%s,password_hash=%s WHERE id=%s", (name, encoded, LOCAL_USER))
        conn.execute("DELETE FROM sessions WHERE user_id=%s", (LOCAL_USER,))
        conn.execute("INSERT INTO audit(user_id,action,resource) VALUES(%s,'account.initial-password',%s)", (LOCAL_USER, str(LOCAL_USER)))
    return login(db, name, password, remember=True)

def change_password(database, actor, password, *, current_password=None, target=None, keep_token=None):
    actor = permissions.enrich(database, actor)
    if actor.get("delegation_id"):
        raise Forbidden("委托凭据不能更改账号密码")
    password_valid(password)
    target = target or actor["id"]
    own = str(target) == str(actor["id"])
    if not own:
        actor = permissions.require(database, actor, "accounts.manage")
    with database.tx() as conn:
        permissions._accounts_lock(conn)
        actor = permissions.enrich(permissions._connection_database(conn), actor)
        if not own:
            actor = permissions.require(permissions._connection_database(conn), actor, "accounts.manage")
        row = conn.execute("SELECT * FROM users WHERE id=%s FOR UPDATE", (target,)).fetchone()
        if not row:
            raise NotFound("account not found")
        target_super = bool(conn.execute("SELECT 1 FROM platform_user_roles ur JOIN platform_roles r ON r.id=ur.role_id "
                                        "WHERE ur.user_id=%s AND r.key='superadmin'", (target,)).fetchone())
        if not own and target_super and not actor.get("superadmin"):
            raise Forbidden("只有超级管理员可以重设超级管理员密码")
        if own:
            try:
                PASSWORDS.verify(row["password_hash"] or DUMMY_HASH, current_password or "")
            except (VerifyMismatchError, InvalidHashError, VerificationError):
                raise Forbidden("当前密码错误") from None
        conn.execute("UPDATE users SET password_hash=%s WHERE id=%s", (PASSWORDS.hash(password), target))
        if own and keep_token:
            conn.execute("DELETE FROM sessions WHERE user_id=%s AND token_hash<>%s", (target, digest(keep_token)))
        else:
            conn.execute("DELETE FROM sessions WHERE user_id=%s", (target,))
        conn.execute("UPDATE platform_delegations SET revoked_at=now() WHERE user_id=%s AND revoked_at IS NULL", (target,))
        conn.execute("INSERT INTO audit(user_id,action,resource) VALUES(%s,'account.password',%s)", (actor["id"], str(target)))
    return {"ok": True}

def _delegation_metadata(row):
    return {key: value for key, value in row.items() if key != "token_hash"}

def delegation_list(database, actor):
    actor = permissions.enrich(database, actor)
    if actor.get("delegation_id"):
        raise Forbidden("委托凭据不能管理其他凭据")
    with database.tx() as db:
        return [_delegation_metadata(r) for r in db.execute(
            "SELECT * FROM platform_delegations WHERE user_id=%s ORDER BY created_at DESC", (actor["id"],)
        ).fetchall()]

def delegation_get(database, actor, delegation_id):
    actor = permissions.enrich(database, actor)
    if actor.get("delegation_id"):
        raise Forbidden("委托凭据不能管理其他凭据")
    with database.tx() as db:
        row = db.execute("SELECT * FROM platform_delegations WHERE id=%s", (delegation_id,)).fetchone()
    if not row or str(row["user_id"]) != str(actor["id"]) and not actor["superadmin"]:
        raise NotFound("delegation not found")
    return _delegation_metadata(row)

def delegate(database, actor, *, name, source, actions, resources, expires_at):
    actor = permissions.enrich(database, actor)
    if actor.get("delegation_id"):
        raise Forbidden("委托凭据不能签发进一步委托")
    actions = permissions.validate_grants(actions)
    if not actions or any(p["action"].split(".")[0] in permissions.DELEGATION_FORBIDDEN for p in actions):
        raise ValueError("委托只允许明确的业务操作，不允许账号、角色或平台管理")
    permissions.check_grantable(actor, actions)
    if source not in ("ai", "script") or not 1 <= len(name.strip()) <= 80:
        raise ValueError("invalid delegation source or name")
    if expires_at.tzinfo is None:
        raise ValueError("expires_at requires an explicit timezone")
    now = datetime.now(UTC)
    if not now < expires_at <= now + timedelta(seconds=DELEGATION_SECONDS):
        raise ValueError("委托有效期必须为未来时间且不超过30天")
    if not resources or len(resources) > 256:
        raise ValueError("委托必须限定1至256个资源")
    normalized = []
    for r in resources:
        if set(r) != {"kind", "id"} or r["kind"] not in permissions.RESOURCE_KINDS:
            raise ValueError("未知委托资源类型")
        rid = str(UUID(str(r["id"])))
        item = {"kind": r["kind"], "id": rid}
        if item not in normalized:
            normalized.append(item)
        with database.tx(ai_admin=r["kind"] == "service") as db:
            db.execute("SELECT set_config('tm.browse_user_id',%s,true)", (str(actor["id"]),))
            db.execute("SELECT set_config('tm.record_user_id',%s,true)", (str(actor["id"]),))
            table = {"project": "projects", "run": "runs", "experiment": "research_experiments", "service": "ai_providers"}[r["kind"]]
            row = db.execute("SELECT " + ("id AS project_id" if r["kind"] == "project" else "project_id") +
                             " FROM " + table + " WHERE id=%s", (rid,)).fetchone()
        if not row:
            raise NotFound("delegation resource is unavailable")
        project = row["project_id"]
        if not any(permissions.allows(database, actor, a["action"], project=project,
                                      owner_id=actor["id"] if a["scope"] == "own" else None) for a in actions):
            raise Forbidden("签发人不能访问委托所选资源")
    token = "tm_delegate_" + secrets.token_urlsafe(40)
    with database.tx() as db:
        row = db.execute("INSERT INTO platform_delegations(id,user_id,token_hash,name,source,actions,resources,expires_at) "
                         "VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                         (uuid4(), actor["id"], digest(token), name.strip(), source, Jsonb(actions),
                          Jsonb(normalized), expires_at)).fetchone()
        db.execute("INSERT INTO audit(user_id,action,resource,details) VALUES(%s,'account.delegate',%s,%s)",
                   (actor["id"], str(row["id"]), Jsonb({"source": source, "actions": actions, "resources": normalized})))
    return {"delegation": _delegation_metadata(row), "access_token": token, "token_type": "Bearer"}

def revoke_delegation(database, actor, delegation_id):
    delegation_get(database, actor, delegation_id)
    with database.tx() as db:
        db.execute("UPDATE platform_delegations SET revoked_at=coalesce(revoked_at,now()) WHERE id=%s", (delegation_id,))
        db.execute("INSERT INTO audit(user_id,action,resource) VALUES(%s,'account.revoke-delegation',%s)", (actor["id"], str(delegation_id)))
    return {"ok": True}
