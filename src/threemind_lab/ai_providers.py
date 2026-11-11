from __future__ import annotations

import hashlib
import json
from contextlib import nullcontext
from decimal import Decimal
from uuid import uuid4

from psycopg.types.json import Jsonb

from .ai_schema import ProviderConfig, ProviderEdit, origin
from .ai_secrets import SecretBox
from .database import Conflict, Forbidden, NotFound

PUBLIC = "id,project_id,original_project_id,revision,config,has_api_key,has_proxy_password,created_by,created_at,updated_at"
CALL_SUMMARY = (
    "id,ordinal,provider_id,provider_revision,purpose,run_id,status,cancel_requested,usage,reserved_usd,cost_usd,"
    "error,created_at,updated_at,sent_at,job_id,provider_config->>'name' AS provider_name,"
    "provider_config->>'model' AS model,length(response_text) AS response_chars,"
    "result->>'application_status' AS application_status"
)
TERMINAL = ("completed", "failed", "cancelled", "uncertain")


def public(row):
    return {key: value for key, value in row.items() if key != "secrets"}


def provider_lock(db, provider_id):
    db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,738349218))", (str(provider_id),))


def require_actor(db, project, actor, *, owner=False):
    """Legacy project services keep their own authenticated action, never an AI cost gate."""
    from . import permissions

    class ExistingTransaction:
        def tx(self, *args, **kwargs):
            return nullcontext(db)

    service = ExistingTransaction()
    user = permissions.resolve_actor(service, actor)
    action = user.get("_request_action") or ("research.manage" if owner else "research.write")
    if permissions.ACTION_INDEX[action]["scopes"] == ["platform"]:
        user = permissions.require(service, user, action)
        role = db.execute("SELECT role FROM members WHERE project_id=%s AND user_id=%s", (project, user["id"])).fetchone()
        if not user["superadmin"] and (not role or (owner and role["role"] != "owner")
                                      or role["role"] not in ("owner", "researcher")):
            raise Forbidden("project access denied")
    else:
        permissions.project_access(service, user, project, write=True, owner=owner, action=action)
    return user


def require_service_actor(db, project, actor, *, owner=False):
    from . import permissions

    class ExistingTransaction:
        def tx(self, *args, **kwargs):
            return nullcontext(db)

    service = ExistingTransaction()
    user = permissions.resolve_actor(service, actor)
    if owner:
        return permissions.require(service, user, "services.manage")
    if project is None:
        user = permissions.require(service, user, "services.use")
        if not permissions.allows(service, user, "services.read"):
            permissions.require(service, user, "services.manage")
        return user
    permissions.project_access(service, user, project, write=True, action="services.use")
    return user


def require_provider_grant(db, project, provider_id):
    if project is not None and not db.execute(
        "SELECT 1 FROM ai_provider_grants WHERE provider_id=%s AND project_id=%s", (provider_id, project)
    ).fetchone():
        raise Forbidden("该服务未授权给当前项目，或原授权已撤销")


def require_purpose(db, project, actor, purpose, *, run_id=None, automatic=False):
    """Paying for a service does not confer permission to read or mutate its research target."""
    if purpose == "provider_test":
        return
    from . import permissions

    class ExistingTransaction:
        def tx(self, *args, **kwargs):
            return nullcontext(db)

    service = ExistingTransaction()
    user = permissions.resolve_actor(service, actor)
    actions = {
        "environment": ["runs.stimulate"],
        "interpretation": ["runs.observe"], "analysis": ["runs.observe"],
        "record": ["reports.write"], "report": ["reports.write"],
        "world": ["worlds.write"], "ecology_observation": ["research.write"],
        "research_plan": ["research.write", "runs.read"] + (["runs.resume"] if automatic else []),
    }[purpose]
    resources = [{"kind": "project", "id": str(project)}]
    if run_id is not None:
        resources.append({"kind": "run", "id": str(run_id)})
    for action in actions:
        permissions.require(service, user, action, project=project, resources=resources)


def restore_scheduled_actor(db, project, actor, lineage, *, purpose, provider_id, run_id=None):
    """Restore a recorded delegation; UUID fallback is only for historical schedules."""
    from . import permissions

    class ExistingTransaction:
        def tx(self, *args, **kwargs):
            return nullcontext(db)

    resources = [{"kind": "project", "id": str(project)}, {"kind": "service", "id": str(provider_id)}]
    if run_id is not None:
        resources.append({"kind": "run", "id": str(run_id)})
    permissions.actor_context.set(None)
    user = permissions.restore_execution_actor(ExistingTransaction(),
        lineage or {"user_id": str(actor), "source": "script"}, action="services.use", project=project, resources=resources)
    require_purpose(db, project, user["id"], purpose, run_id=run_id)
    require_provider_grant(db, project, provider_id)
    return user


def network_allowed(settings, config: ProviderConfig):
    if settings.mode == "workstation":
        return True
    allowed = {origin(value) for value in settings.ai_allowed_origins}
    return origin(config.base_url) in allowed and (not config.proxy_url or origin(config.proxy_url) in allowed)


def get(db, provider_id):
    row = db.execute("SELECT * FROM ai_providers WHERE id=%s", (provider_id,)).fetchone()
    if row is None:
        raise NotFound("供应商不存在或当前范围未获授权")
    return row


def save(store, settings, project, actor, body: ProviderEdit, provider_id=None, *, platform=False):
    provider_id = provider_id or uuid4()
    with store.tx(project, ai_admin=True) as db:
        user = require_service_actor(db, project, actor, owner=True)
        actor = user["id"]
        if project is not None:
            from . import permissions

            class ExistingTransaction:
                def tx(self, *args, **kwargs):
                    return nullcontext(db)

            permissions.project_access(ExistingTransaction(), user, project, write=True, action="research.write")
        provider_lock(db, provider_id)
        row = db.execute("SELECT * FROM ai_providers WHERE id=%s", (provider_id,)).fetchone()
        if row and project is not None and str(row["original_project_id"]) != str(project):
            raise Forbidden("共享供应商只允许平台管理员在平台范围修改")
        if body.expected_revision != (row["revision"] if row else 0):
            raise Conflict("供应商已被其他页面修改，请重新读取后保存")
        box = SecretBox(settings.secret_keys)
        secrets = box.open(row["secrets"]) if row else {}
        for key in ("api_key", "proxy_password"):
            if getattr(body, "clear_" + key):
                secrets.pop(key, None)
            elif getattr(body, key):
                secrets[key] = getattr(body, key)
        cipher = box.seal(secrets)
        if row:
            row = db.execute(
                "UPDATE ai_providers SET revision=revision+1,config=%s,secrets=%s,has_api_key=%s,"
                "has_proxy_password=%s,updated_at=now() WHERE id=%s RETURNING " + PUBLIC,
                (
                    Jsonb(body.config.model_dump()),
                    cipher,
                    bool(secrets.get("api_key")),
                    bool(secrets.get("proxy_password")),
                    provider_id,
                ),
            ).fetchone()
        else:
            row = db.execute(
                "INSERT INTO ai_providers(id,project_id,original_project_id,config,secrets,has_api_key,has_proxy_password,created_by) "
                "VALUES(%s,NULL,%s,%s,%s,%s,%s,%s) RETURNING " + PUBLIC,
                (
                    provider_id,
                    project,
                    Jsonb(body.config.model_dump()),
                    cipher,
                    bool(secrets.get("api_key")),
                    bool(secrets.get("proxy_password")),
                    actor,
                ),
            ).fetchone()
            if project is not None:
                db.execute("INSERT INTO ai_provider_grants(provider_id,project_id) VALUES(%s,%s)", (provider_id, project))
        db.execute(
            "INSERT INTO ai_provider_versions(provider_id,revision,config,actor_id,created_at,source) VALUES(%s,%s,%s,%s,%s,'saved')",
            (provider_id, row["revision"], Jsonb(row["config"]), actor, row["updated_at"]),
        )
        db.execute(
            "INSERT INTO audit(user_id,action,resource,details) VALUES(%s,'ai.provider.save',%s,%s)",
            (actor, str(provider_id), Jsonb({"revision": row["revision"], "platform": True,
                                           "original_project_id": str(project) if project is not None else None})),
        )
        return row


def reserve_cost(config, prompt):
    if config.input_usd_per_million is None or config.output_usd_per_million is None:
        return None
    # Bytes + generous framing allowance are a reservation, not measured tokens.
    bound = len(json.dumps(prompt, ensure_ascii=False).encode()) + 1024
    return (
        Decimal(str(config.input_usd_per_million)) * bound
        + Decimal(str(config.output_usd_per_million)) * config.max_output_tokens
    ) / 1000000


def enqueue(
    store,
    settings,
    project,
    actor,
    provider_id,
    *,
    request_id,
    purpose,
    prompt,
    evidence=None,
    run_id=None,
    transaction=None,
):
    if purpose not in (
        "provider_test",
        "environment",
        "interpretation",
        "research_plan",
        "analysis",
        "record",
        "report",
        "world",
        "ecology_observation",
    ):
        raise ValueError("unknown AI tool")
    if project is None and (purpose != "provider_test" or run_id is not None or evidence):
        raise ValueError("无项目调用只允许供应商诊断；正式研究调用必须保留实际项目与证据归属")
    if set(prompt) != {"system", "user"} or any(not isinstance(v, str) for v in prompt.values()):
        raise ValueError("AI prompt must contain system and user text")
    if len(json.dumps(prompt, ensure_ascii=False).encode()) > 200000 or not prompt["user"].strip():
        raise ValueError("AI 请求文本为空或超过 200 KB；请缩小证据范围")
    actor = actor["id"] if isinstance(actor, dict) else actor
    frozen = {
        "provider_id": str(provider_id),
        "purpose": purpose,
        "actor_id": str(actor),
        "prompt": prompt,
        "evidence": evidence or {},
        "run_id": str(run_id) if run_id else None,
    }
    fingerprint = hashlib.sha256(json.dumps(frozen, sort_keys=True, allow_nan=False).encode()).hexdigest()
    with store.tx(project, ai_admin=project is None) if transaction is None else nullcontext(transaction) as db:
        user = require_service_actor(db, project, actor)
        require_purpose(db, project, actor, purpose, run_id=run_id,
                        automatic=(evidence or {}).get("request", {}).get("mode") == "automatic")
        request_scope = str(project) if project is not None else "actor:" + str(actor)
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,738349228))",
                   ("ai-request:" + request_scope + ":" + str(request_id),))
        provider_lock(db, provider_id)
        previous = db.execute(
            "SELECT * FROM ai_calls WHERE request_id=%s AND project_id IS NOT DISTINCT FROM %s "
            + ("AND actor_id=%s" if project is None else ""),
            (request_id, project) + ((actor,) if project is None else ()),
        ).fetchone()
        if previous:
            if previous["fingerprint"] != fingerprint:
                raise Conflict("同一请求 ID 已用于不同的 AI 请求")
            return previous
        row = get(db, provider_id)
        require_provider_grant(db, project, provider_id)
        config = ProviderConfig.model_validate(row["config"])
        if not config.enabled:
            raise Conflict("供应商尚未启用")
        if not network_allowed(settings, config):
            raise Forbidden("服务器尚未允许该供应商或代理地址；请由部署管理员配置 THREEMIND_AI_ALLOWED_ORIGINS")
        if not settings.secret_keys:
            raise ValueError("尚未配置供应商凭据加密钥")
        if run_id and not db.execute("SELECT id FROM runs WHERE id=%s", (run_id,)).fetchone():
            raise NotFound()
        budget = db.execute(
            "SELECT count(*) FILTER(WHERE active) AS active,"
            "count(*) FILTER(WHERE created_at >= date_trunc('day',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC') AS today,"
            "coalesce(sum(coalesce(cost_usd,reserved_usd)) FILTER(WHERE created_at >= "
            "date_trunc('month',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'),0) AS month "
            "FROM ai_reservations WHERE provider_id=%s",
            (provider_id,),
        ).fetchone()
        cost = reserve_cost(config, prompt)
        if budget["active"] >= config.max_pending:
            raise Conflict("供应商待处理请求已达上限，请等待或取消已有请求")
        if budget["today"] >= config.daily_request_limit:
            raise Conflict("供应商今日请求数量已达上限（UTC）")
        if (
            cost is not None
            and config.monthly_budget_usd is not None
            and (Decimal(budget["month"]) + cost > Decimal(str(config.monthly_budget_usd)))
        ):
            raise Conflict("本次请求的费用预留将超过供应商月预算（UTC）")
        call_id, job_id = uuid4(), uuid4()
        from .permissions import execution_actor

        db.execute(
            "INSERT INTO jobs(id,project_id,run_id,kind,params) VALUES(%s,%s,%s,'ai',%s)",
            (job_id, project, run_id, Jsonb({"call_id": str(call_id), "purpose": purpose,
                                           "execution_actor": execution_actor(user)})),
        )
        call = db.execute(
            "INSERT INTO ai_calls(id,project_id,actor_id,provider_id,provider_revision,provider_config,"
            "request_id,fingerprint,purpose,run_id,evidence,prompt,job_id,reserved_usd) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                call_id,
                project,
                actor,
                provider_id,
                row["revision"],
                Jsonb(row["config"]),
                request_id,
                fingerprint,
                purpose,
                run_id,
                Jsonb(evidence or {}),
                Jsonb(prompt),
                job_id,
                cost,
            ),
        ).fetchone()
        db.execute(
            "INSERT INTO ai_reservations(call_id,provider_id,reserved_usd) VALUES(%s,%s,%s)",
            (call_id, provider_id, cost),
        )
        for ref in (evidence or {}).get("checkpoint_refs", []):
            db.execute(
                "INSERT INTO ai_call_checkpoints(project_id,call_id,run_id,checkpoint_id) VALUES(%s,%s,%s,%s)",
                (project, call_id, ref["run_id"], ref["checkpoint_id"]),
            )
        return call


def call_by_id(db, call_id):
    row = db.execute("SELECT * FROM ai_calls WHERE id=%s", (call_id,)).fetchone()
    if row is None:
        raise NotFound()
    return row


def finish_call(store, job, call_id, status, *, text="", meta=None, usage=None, error=None):
    if status not in TERMINAL:
        raise ValueError("invalid AI completion status")
    with store.tx(job["project_id"], ai_admin=job["project_id"] is None) as db:
        store.fence(db, job)
        call = call_by_id(db, call_id)
        if status == "completed" and call["cancel_requested"]:
            status, error = "cancelled", "完成保存前收到取消请求；结果不会用于工具执行"
        config = ProviderConfig.model_validate(call["provider_config"])
        cost = None
        if usage and config.input_usd_per_million is not None and config.output_usd_per_million is not None:
            cost = (
                Decimal(str(config.input_usd_per_million)) * usage["input_tokens"]
                + Decimal(str(config.output_usd_per_million)) * usage["output_tokens"]
            ) / 1000000
        elif call["sent_at"] is None:
            cost = Decimal(0)
        db.execute(
            "UPDATE ai_calls SET status=%s,response_text=%s,response_meta=%s,usage=%s,cost_usd=%s,error=%s,"
            "updated_at=now() WHERE id=%s",
            (status, text, Jsonb(meta or {}), Jsonb(usage) if usage else None, cost, error, call_id),
        )
        db.execute("UPDATE ai_reservations SET active=false,cost_usd=%s WHERE call_id=%s", (cost, call_id))
    return {"call_id": str(call_id), "status": status}
