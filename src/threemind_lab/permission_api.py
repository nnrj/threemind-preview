"""Account, role and self-service APIs using the shared authorization service."""
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from . import auth, permissions


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Setup(Strict):
    password: str = Field(min_length=12, max_length=1024)
    username: str | None = Field(None, min_length=3, max_length=80)


class User(Strict):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=12, max_length=1024)
    role_ids: list[UUID] = Field(min_length=1, max_length=64)


class RoleAssignment(Strict):
    role_ids: list[UUID] = Field(min_length=1, max_length=64)


class Enabled(Strict):
    enabled: bool = Field(strict=True)


class Password(Strict):
    password: str = Field(min_length=12, max_length=1024)


class OwnPassword(Password):
    current_password: str = Field(min_length=1, max_length=1024)


class NewRole(Strict):
    key: str = Field(min_length=3, max_length=64)
    name: str = Field(min_length=1, max_length=80)
    permissions: list[dict[str, str]] = Field(max_length=512)


class RoleEdit(Strict):
    name: str = Field(min_length=1, max_length=80)
    permissions: list[dict[str, str]] = Field(max_length=512)
    expected_revision: int = Field(ge=1, strict=True)


class TokenLogin(Strict):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=1024)
    remember: bool = Field(False, strict=True)
    source: str = "script"


class Delegation(Strict):
    name: str = Field(min_length=1, max_length=80)
    source: str
    actions: list[dict[str, str]] = Field(min_length=1, max_length=512)
    resources: list[dict[str, str]] = Field(min_length=1, max_length=256)
    expires_at: datetime


def register_permission_routes(app, access=None):
    def actor(request, action=None, *, mutate=False):
        user = auth.identity(request, mutate=mutate)
        return permissions.require(app.state.db, user, action) if action else user

    def loopback(request):
        if not request.client or request.client.host not in ("127.0.0.1", "::1"):
            raise HTTPException(403, "首次设置必须在本机进行")

    @app.get("/api/v2/auth/setup/status")
    def setup_status(request: Request):
        loopback(request)
        return auth.setup_status(app.state.db)

    @app.post("/api/v2/auth/setup")
    def setup(request: Request, response: Response, body: Setup):
        loopback(request)
        token, csrf, user = auth.setup_local(app.state.db, body.password, username=body.username)
        response.set_cookie("tm_session", token, httponly=True, secure=app.state.settings.secure_cookie,
                            samesite="strict", max_age=auth.REMEMBER_SECONDS)
        return {"user": user, "csrf": csrf, "setup_complete": True}

    @app.get("/api/v2/permissions/catalog")
    def permission_catalog(request: Request):
        actor(request)
        return permissions.catalogue()

    @app.get("/api/v2/session/permissions")
    def session_permissions(request: Request):
        user = actor(request)
        return {key: user[key] for key in ("superadmin", "roles", "permissions")} | {"user_id": user["id"]}

    @app.get("/api/v2/accounts/users")
    def users(request: Request):
        actor(request, "accounts.read")
        return {"users": permissions.list_users(app.state.db)}

    @app.post("/api/v2/accounts/users", status_code=201)
    def create_user(request: Request, body: User):
        user = actor(request, "accounts.manage", mutate=True)
        permissions.check_roles_grantable(app.state.db, user, body.role_ids)
        result = auth.create_user(app.state.db, body.username, body.password, role_ids=body.role_ids, actor=user)
        with app.state.db.tx() as db:
            db.execute("INSERT INTO audit(user_id,action,resource) VALUES(%s,'account.create',%s)",
                       (user["id"], str(result["id"])))
        return result

    @app.put("/api/v2/accounts/users/{target}/roles")
    def user_roles(target: UUID, request: Request, body: RoleAssignment):
        return permissions.assign_roles(app.state.db, actor(request, mutate=True), target, body.role_ids)

    @app.put("/api/v2/accounts/users/{target}/enabled")
    def user_enabled(target: UUID, request: Request, body: Enabled):
        return permissions.set_enabled(app.state.db, actor(request, mutate=True), target, body.enabled)

    @app.post("/api/v2/accounts/users/{target}/password")
    def reset_password(target: UUID, request: Request, body: Password):
        return auth.change_password(app.state.db, actor(request, mutate=True), body.password, target=target)

    @app.post("/api/v2/account/password")
    def change_password(request: Request, body: OwnPassword):
        return auth.change_password(app.state.db, actor(request, mutate=True), body.password,
                                    current_password=body.current_password, keep_token=auth.request_token(request)[0])

    @app.get("/api/v2/accounts/roles")
    def roles(request: Request):
        actor(request, "roles.read")
        return {"roles": permissions.list_roles(app.state.db)}

    @app.post("/api/v2/accounts/roles", status_code=201)
    def create_role(request: Request, body: NewRole):
        return permissions.save_role(app.state.db, actor(request, mutate=True), key=body.key,
                                     name=body.name, grants=body.permissions)

    @app.put("/api/v2/accounts/roles/{role_id}")
    def edit_role(role_id: UUID, request: Request, body: RoleEdit):
        return permissions.save_role(app.state.db, actor(request, mutate=True), role_id=role_id,
                                     name=body.name, grants=body.permissions, expected_revision=body.expected_revision)

    @app.delete("/api/v2/accounts/roles/{role_id}")
    def delete_role(role_id: UUID, request: Request):
        return permissions.delete_role(app.state.db, actor(request, mutate=True), role_id)


    @app.get("/api/v2/me")
    def me(request: Request):
        return {"user": {key: value for key, value in actor(request).items() if not key.startswith("_")},
                "mode": app.state.settings.mode, "backend": app.state.settings.backend}

    @app.post("/api/v2/auth/token")
    def token_login(request: Request, body: TokenLogin):
        token, csrf, user = auth.login(app.state.db, body.username, body.password, remember=body.remember, source=body.source)
        return {"access_token": token, "token_type": "Bearer", "expires_at": user["expires_at"],
                "user": user | {"auth_type": "bearer"}, "csrf": csrf}

    @app.post("/api/v2/auth/refresh")
    def refresh(request: Request, response: Response):
        token, csrf, user = auth.refresh(request)
        transport = auth.request_token(request)[1]
        if transport == "cookie":
            response.set_cookie("tm_session", token, httponly=True, secure=app.state.settings.secure_cookie,
                                samesite="strict", max_age=auth.REMEMBER_SECONDS if user["remembered"] else auth.SESSION_SECONDS)
        return {"access_token": token, "token_type": "Bearer", "expires_at": user["expires_at"], "user": user, "csrf": csrf}

    @app.get("/api/v2/account/delegations")
    def delegations(request: Request):
        return {"delegations": auth.delegation_list(app.state.db, actor(request))}

    @app.post("/api/v2/account/delegations", status_code=201)
    def create_delegation(request: Request, body: Delegation):
        return auth.delegate(app.state.db, actor(request, mutate=True), **body.model_dump())

    @app.get("/api/v2/account/delegations/{delegation_id}")
    def delegation(delegation_id: UUID, request: Request):
        return auth.delegation_get(app.state.db, actor(request), delegation_id)

    @app.delete("/api/v2/account/delegations/{delegation_id}")
    def revoke_delegation(delegation_id: UUID, request: Request):
        return auth.revoke_delegation(app.state.db, actor(request, mutate=True), delegation_id)
