from __future__ import annotations

import asyncio
import socket
import threading
import time
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import psycopg

from . import ai_providers as providers
from .ai_http import Completion, ProviderFailure, complete
from .ai_schema import ProviderConfig
from .ai_secrets import SecretBox
from .database import Conflict, Forbidden, NotFound


class CallCancelled(Exception):
    pass


class AIWorker:
    """Independent PostgreSQL queue: an active runtime never occupies AI capacity."""

    def __init__(self, database, settings, *, name=None, transport=None):
        self.db, self.settings = database, settings
        self.name = name or f"{socket.gethostname()}-ai-{uuid4().hex[:8]}"
        self.transport = transport  # In-process test seam; never exposed over HTTP.
        self.stopping = False
        self.announced_at = None
        self.capabilities = None

    def serve(self):
        while not self.stopping:
            try:
                if not self.once():
                    time.sleep(0.25)
            except psycopg.OperationalError:
                time.sleep(1)

    def once(self):
        from .ai_scheduler import tick

        tick(self.db, self.settings)
        from .ecology_ai import tick as tick_ecology

        tick_ecology(self.db, self.settings)
        if self.announced_at is None or time.monotonic() - self.announced_at >= 30:
            self.capabilities = {
                "queue": "ai",
                "checked_at": datetime.now(UTC).isoformat(),
                "features": {
                    "worker.evolution_v1": {"state": "available"},
                    "worker.ecology_evidence_v1": {"state": "available"},
                    "worker.assessment_v1": {"state": "available", "name": "独立评估"},
                    "worker.ecology_ai_v1": {"state": "available", "name": "AI 观察解释"},
                    "worker.world_authoring_v1": self.world_authoring_capability(),
                    "worker.research_events_v1": {"state": "available"},
                    "worker.research_ai_v1": {
                        "name": "固定证据文档草案",
                        "state": "available",
                        "reason": "校验引用范围并保存独立的待审核修订。",
                    },
                    "worker.ai": {
                        "name": "AI 文本请求",
                        "state": "available",
                        "protocols": ["chat", "responses"],
                        "reason": "独立 HTTP 请求队列；具体调用仍需有效供应商配置、授权和凭据。",
                    },
                },
            }
            self.db.announce_worker(self.name, self.capabilities)
            self.announced_at = time.monotonic()
        job = self.db.claim(self.name, queue="ai", max_active=self.settings.max_ai_jobs, capabilities=self.capabilities)
        if not job:
            return False
        stop = threading.Event()

        def heartbeat():
            while not stop.wait(15):
                try:
                    self.db.renew(job)
                except Conflict:
                    return
                except psycopg.OperationalError:
                    continue

        thread = threading.Thread(target=heartbeat, daemon=True, name="ai-lease")
        thread.start()
        try:
            result = self.run(job, apply=True)
            self.db.finish(job, result=result)
        except Conflict:
            pass  # Only the current lease holder may finalize anything.
        except Exception as exc:  # noqa: BLE001 -- sanitize errors at the durable job boundary
            # Do not place raw httpx / credential / proxy exceptions in job logs.
            try:
                with self.db.tx(job["project_id"], ai_admin=job["project_id"] is None) as db:
                    call = providers.call_by_id(db, job["params"]["call_id"])
                if call["status"] not in providers.TERMINAL:
                    providers.finish_call(
                        self.db,
                        job,
                        call["id"],
                        "uncertain" if call["sent_at"] else "failed",
                        text=call["response_text"],
                        error="AI worker 异常终止；未自动重发请求",
                    )
                self.db.finish(job, error=f"AI worker failed ({type(exc).__name__}); see call status")
            except Conflict:
                pass
        finally:
            stop.set()
            thread.join(timeout=1)
        return True

    @staticmethod
    def world_authoring_capability():
        try:
            from threemind_runtime.world_schema import default_world

            from .worlds import validate

            validate(default_world().model_dump(mode="json"))
            return {"state": "available", "name": "世界与躯体草案"}
        except Exception as exc:  # noqa: BLE001 -- report an optional authoring capability, never fake validation
            return {"state": "unavailable", "name": "世界与躯体草案", "reason": type(exc).__name__}

    def run(self, job, *, apply=False):
        from .permissions import actor_context, restore_execution_actor

        # A reused worker thread must not inherit another task's identity.
        token = actor_context.set(None)
        try:
            with self.db.tx(job["project_id"], ai_admin=job["project_id"] is None) as db:
                self.db.fence(db, job)
                call = providers.call_by_id(db, job["params"]["call_id"])
            if call["status"] in providers.TERMINAL and (
                not apply or call["status"] != "completed" or job["params"].get("purpose") == "provider_test" or call["result"]
            ):
                # A reclaimed acknowledgement must not rewrite an already saved response,
                # even if the original account or delegation has since been revoked.
                return {"call_id": str(call["id"]), "status": call["status"]}
            lineage = job["params"].get("execution_actor") or {"user_id": str(call["actor_id"]), "source": "script"}
            try:
                restore_execution_actor(self.db, lineage, action="services.use", project=job["project_id"],
                                        resources=[{"kind": "service", "id": str(call["provider_id"])}]
                                        + ([{"kind": "project", "id": str(job["project_id"])}]
                                           if job["project_id"] is not None else []))
            except Forbidden:
                if call["status"] == "completed":
                    # Keep the measured remote response; only its deferred application is denied.
                    from psycopg.types.json import Jsonb

                    result = {"application_status": "rejected", "error": "原执行权限已被撤销"}
                    with self.db.tx(job["project_id"]) as db:
                        self.db.fence(db, job)
                        db.execute("UPDATE ai_calls SET result=%s,updated_at=now() WHERE id=%s AND result='{}'::jsonb",
                                   (Jsonb(result), call["id"]))
                    return {"call_id": str(call["id"]), "status": "completed", "tool_result": result}
                return providers.finish_call(self.db, job, call["id"], "uncertain" if call["sent_at"] else "failed",
                    text=call["response_text"], meta=call["response_meta"], usage=call["usage"],
                    error=("请求已发出且原执行权限已撤销；远端结果不确定，未自动重发" if call["sent_at"] else
                           "操作者或原委托的服务调用权限已被撤销；未发送请求"))
            result = self._run(job)
            if apply and result["status"] == "completed" and job["params"].get("purpose") != "provider_test":
                from .ai_tools import apply_completed

                result["tool_result"] = apply_completed(self.db, job)
            return result
        finally:
            actor_context.reset(token)

    def _run(self, job):
        call_id = job["params"]["call_id"]
        with self.db.tx(job["project_id"], ai_admin=job["project_id"] is None) as db:
            self.db.fence(db, job)
            call = providers.call_by_id(db, call_id)
        if call["status"] in providers.TERMINAL:
            return {"call_id": str(call_id), "status": call["status"]}
        if call["sent_at"]:
            return providers.finish_call(
                self.db,
                job,
                call_id,
                "uncertain",
                text=call["response_text"],
                meta=call["response_meta"],
                usage=call["usage"],
                error="请求发送后 worker 中断，远端结果不确定；未自动重发",
            )
        result = Completion()
        try:
            with self.db.tx(job["project_id"], ai_admin=job["project_id"] is None) as db:
                self.db.fence(db, job)
                call = providers.call_by_id(db, call_id)
                providers.require_service_actor(db, job["project_id"], call["actor_id"])
                providers.require_purpose(db, job["project_id"], call["actor_id"], call["purpose"],
                    run_id=call["run_id"], automatic=call["evidence"].get("request", {}).get("mode") == "automatic")
                provider = providers.get(db, call["provider_id"])
                providers.require_provider_grant(db, job["project_id"], call["provider_id"])
                config = ProviderConfig.model_validate(provider["config"])
                if provider["revision"] != call["provider_revision"] or not config.enabled:
                    raise ProviderFailure("供应商配置已改变或停用，请检查后重新提交请求")
                if not providers.network_allowed(self.settings, config):
                    raise ProviderFailure("部署已撤销对供应商或代理地址的访问许可")
                secrets = SecretBox(self.settings.secret_keys).open(provider["secrets"])
                if self.stopping or call["cancel_requested"]:
                    raise CallCancelled()
                # Commit BEFORE any HTTP send. A crash here can conservatively
                # classify an unsent request as uncertain, but never resends one.
                db.execute(
                    "UPDATE ai_calls SET status='sending',sent_at=now(),updated_at=now() WHERE id=%s", (call_id,)
                )
            asyncio.run(self.request(job, call, config, secrets, result))
            return providers.finish_call(
                self.db, job, call_id, "completed", text=result.text, meta=result.meta, usage=result.usage
            )
        except CallCancelled:
            return providers.finish_call(
                self.db,
                job,
                call_id,
                "cancelled",
                text=result.text,
                meta=result.meta,
                usage=result.usage,
                error="请求已取消；已发送请求的远端计费可能仍然发生",
            )
        except (TimeoutError, httpx.TimeoutException):
            return providers.finish_call(
                self.db,
                job,
                call_id,
                "failed",
                text=result.text,
                meta=result.meta,
                usage=result.usage,
                error="供应商请求超时；未自动重试，部分内容未用于执行",
            )
        except (Forbidden, NotFound):
            return providers.finish_call(
                self.db, job, call_id, "failed", text=result.text, error="操作者权限或共享供应商授权已被撤销"
            )
        except ProviderFailure as exc:
            return providers.finish_call(
                self.db, job, call_id, "failed", text=result.text, meta=result.meta, usage=result.usage, error=str(exc)
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return providers.finish_call(
                self.db,
                job,
                call_id,
                "failed",
                text=result.text,
                meta=result.meta,
                usage=result.usage,
                error="供应商连接、凭据解密或响应格式错误；请检查配置，未自动重试",
            )

    async def request(self, job, call, config, secrets, result):
        last_write = 0.0

        async def progress(value):
            nonlocal last_write
            now = time.monotonic()
            if now - last_write >= 0.5:
                with self.db.tx(job["project_id"], ai_admin=job["project_id"] is None) as db:
                    self.db.fence(db, job)
                    db.execute(
                        "UPDATE ai_calls SET response_text=%s,updated_at=now() WHERE id=%s", (value.text, call["id"])
                    )
                last_write = now

        def check():
            with self.db.tx(job["project_id"], ai_admin=job["project_id"] is None) as db:
                self.db.fence(db, job)
                providers.require_service_actor(db, job["project_id"], call["actor_id"])
                provider = providers.get(db, call["provider_id"])
                providers.require_provider_grant(db, job["project_id"], call["provider_id"])
                current = db.execute("SELECT cancel_requested FROM ai_calls WHERE id=%s", (call["id"],)).fetchone()
                if self.stopping or current["cancel_requested"]:
                    raise CallCancelled()
                if provider["revision"] != call["provider_revision"] or not provider["config"]["enabled"]:
                    raise ProviderFailure("供应商配置在调用过程中改变或停用；请求已中止")

        async def watch():
            while True:
                await asyncio.to_thread(check)
                await asyncio.sleep(0.25)

        network = asyncio.create_task(
            complete(config, secrets, call["prompt"], result, progress, transport=self.transport)
        )
        cancel = asyncio.create_task(watch())
        try:
            done, _ = await asyncio.wait(
                (network, cancel), timeout=config.timeout_s, return_when=asyncio.FIRST_COMPLETED
            )
            if not done:
                raise TimeoutError()
            # Recheck even if network completed simultaneously with revocation.
            await asyncio.to_thread(check)
            if cancel in done:
                cancel.result()
            await network
        finally:
            for task in (network, cancel):
                if not task.done():
                    task.cancel()
            await asyncio.gather(network, cancel, return_exceptions=True)
