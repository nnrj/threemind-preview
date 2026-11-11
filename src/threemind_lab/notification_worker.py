"""Independent delivery queue; no email failure or latency occupies a Core worker."""

import socket
import threading
import time
from datetime import UTC, datetime
from uuid import uuid4

import psycopg

from . import notifications
from .database import Conflict
from .notification_delivery import deliver


class NotificationWorker:
    def __init__(self, database, settings, *, name=None, transport=None):
        self.db, self.settings = database, settings
        self.name = name or f"{socket.gethostname()}-notifications-{uuid4().hex[:8]}"
        self.transport = transport  # In-process test injection; never an API URL override.
        self.stopping = False
        self.announced_at = None
        self.capabilities = None

    def serve(self):
        while not self.stopping:
            try:
                if not self.once():
                    time.sleep(0.5)
            except psycopg.OperationalError:
                time.sleep(1)

    def once(self):
        from .execution_health import tick

        tick(self.db)
        if self.announced_at is None or time.monotonic() - self.announced_at > 30:
            self.capabilities = {
                "queue": "notification",
                "checked_at": datetime.now(UTC).isoformat(),
                "features": {
                    "worker.execution_health_v1": {
                        "name": "执行资源与进度预警",
                        "state": "available",
                        "reason": "Sampled host observations; no Core inputs or commands.",
                    },
                    "worker.notifications": {
                        "name": "邮件通知",
                        "state": "available",
                        "protocols": ["resend", "smtp"],
                    },
                },
            }
            self.db.announce_worker(self.name, self.capabilities)
            self.announced_at = time.monotonic()
        job = self.db.claim(
            self.name,
            queue="notification",
            max_active=self.settings.max_notification_jobs,
            capabilities=self.capabilities,
        )
        if job is None:
            return False
        stopped = threading.Event()

        def heartbeat():
            while not stopped.wait(15):
                try:
                    self.db.renew(job)
                except Conflict:
                    return
                except psycopg.OperationalError:
                    continue

        thread = threading.Thread(target=heartbeat, daemon=True, name="notification-lease")
        thread.start()
        try:
            prepared = notifications.prepare_delivery(self.db, self.settings, job)
            if "notice" in prepared:
                result = deliver(prepared["config"], prepared["secrets"], prepared["notice"], transport=self.transport)
                notifications.finish_delivery(self.db, job, prepared["notice"]["id"], **result)
            else:
                result = prepared
            self.db.finish(job, result=result)
        except Conflict:
            pass
        except Exception:  # noqa: BLE001 -- durable, redacted external-delivery boundary
            try:
                with self.db.tx(job["project_id"]) as db:
                    notice = db.execute(
                        "SELECT dispatched_at FROM notifications WHERE id=%s", (job["params"]["notification_id"],)
                    ).fetchone()
                state = "uncertain" if notice and notice["dispatched_at"] else "failed"
                notifications.finish_delivery(
                    self.db, job, job["params"]["notification_id"], state, reason="worker_failure"
                )
                self.db.finish(job, error="通知 worker 未完成；敏感连接信息未写入错误记录")
            except (Conflict, psycopg.OperationalError):
                pass
        finally:
            stopped.set()
            thread.join(timeout=3)
        return True
