"""Project-scoped, sampled execution warnings, outside all model dynamics."""

import math
from datetime import timedelta
from types import SimpleNamespace

import psycopg
from psycopg.types.json import Jsonb

from threemind_runtime.ecology_observer import evaluate_rules
from threemind_runtime.world_schema import digest

from .health_schema import METRICS, HealthConfig
from .notification_schema import NotificationConfig

VERSION = "threemind.execution-health/1"


def configure(db, project, revision, config):
    enabled = config.enabled and config.events.execution_health and config.execution_health.enabled
    db.execute(
        "INSERT INTO execution_health_monitors(project_id,policy_revision,enabled) VALUES(%s,%s,%s) "
        "ON CONFLICT(project_id) DO UPDATE SET policy_revision=excluded.policy_revision,enabled=excluded.enabled,"
        "next_poll_at=clock_timestamp(),state='{}',snapshot='{}',error=NULL,updated_at=clock_timestamp()",
        (project, revision, enabled),
    )


def _number(value):
    return value if type(value) in (float, int) and math.isfinite(value) and value >= 0 else None


def snapshot(db, project, *, now=None):
    now = now or db.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    time_us = str(round(now.timestamp() * 1e6))
    jobs = db.execute(
        "SELECT count(*) FILTER(WHERE status='pending' AND available_at<=%s) AS ready,"
        "count(*) FILTER(WHERE status='pending' AND available_at<=%s AND status_changed_at IS NULL) AS unknown_ready,"
        "max(extract(epoch FROM %s-greatest(created_at,available_at,status_changed_at))) FILTER(WHERE status='pending' AND available_at<=%s) AS wait_s,"
        "count(*) FILTER(WHERE status='leased' AND lease_until<=%s) AS expired "
        "FROM jobs j WHERE project_id=%s AND status IN ('pending','leased') AND kind NOT IN ('notification','ecology_observe') "
        "AND NOT (j.kind='run' AND EXISTS(SELECT 1 FROM runs r WHERE r.id=j.run_id AND r.status IN ('paused','blocked','cancelled','completed','dead','failed')))",
        (now, now, now, now, now, project),
    ).fetchone()
    frames = {
        "ready_wait_s": {
            "value": None if jobs["unknown_ready"] else max(0, float(jobs["wait_s"] or 0)),
            "applicable": True,
            "time_us": time_us,
            "ready_tasks": jobs["ready"],
            "unknown_transition_times": jobs["unknown_ready"],
        },
        "expired_leases": {"value": jobs["expired"], "applicable": True, "time_us": time_us},
    }
    boundaries = db.execute(
        "SELECT count(*) AS n,count(*) FILTER(WHERE origin IS NULL) AS missing,"
        "max(extract(epoch FROM %s-origin)) AS age FROM ("
        "SELECT greatest(coalesce(ec.created_at,rc.created_at),a.assigned_at,j.status_changed_at) AS origin "
        "FROM jobs j LEFT JOIN job_assignments a ON a.job_id=j.id AND a.generation=j.generation "
        "LEFT JOIN ecology_campaigns p ON p.job_id=j.id LEFT JOIN ecology_checkpoints ec ON ec.id=p.checkpoint_id "
        "LEFT JOIN LATERAL(SELECT created_at FROM checkpoints WHERE run_id=j.run_id ORDER BY revision DESC LIMIT 1) rc ON true "
        "WHERE j.project_id=%s AND j.status='leased' AND j.lease_until>%s AND j.kind IN ('run','ecology')) t",
        (now, project, now),
    ).fetchone()
    frames["commit_age_s"] = {
        "value": None if boundaries["missing"] else max(0, float(boundaries["age"] or 0)),
        "applicable": bool(boundaries["n"]),
        "time_us": time_us,
        "active_brain_or_population_jobs": boundaries["n"],
    }
    # A bounded set of *all* assigned nodes, or an explicit coverage failure.
    # We never present the first page as the maximum of a larger deployment.
    workers = db.execute(
        "SELECT w.id,w.health,w.health_received_at FROM workers w WHERE EXISTS "
        "(SELECT 1 FROM jobs j WHERE j.project_id=%s AND j.worker_id=w.id AND j.status='leased' AND j.lease_until>%s "
        "AND j.kind NOT IN ('notification','ecology_observe')) ORDER BY w.id LIMIT 257",
        (project, now),
    ).fetchall()
    for name, field in (
        ("worker_rss_mib", "rss_mib"),
        ("worker_cpu_percent", "cpu_percent"),
        ("host_memory_percent", "host_memory_percent"),
    ):
        valid = []
        for worker in workers[:256]:
            health, received = worker["health"], worker["health_received_at"]
            value = _number(health.get(field))
            if (
                received
                and now - timedelta(seconds=45) <= received <= now
                and health.get("coverage") == "observed"
                and value is not None
            ):
                valid.append(value)
        complete = len(workers) <= 256 and len(valid) == len(workers)
        frames[name] = {
            "value": max(valid) if complete and valid else None,
            "applicable": bool(workers),
            "time_us": time_us,
            "known_workers": len(valid),
            "worker_count_lower_bound": len(workers),
            "coverage": "complete" if complete else "stale, unavailable or more than 256 active workers",
            "sample_signature": digest([(w["id"], w["health"].get("sample_id")) for w in workers[:256]] + [complete]),
        }
    return {
        "version": VERSION,
        "clock": "database host wall clock UTC; cached resource samples deduplicated",
        "observed_at": now.isoformat(),
        "metrics": frames,
        "scope": "current project tasks and their assigned worker processes",
        "limits": [
            "Process RSS and CPU exclude child processes. Host memory includes other applications.",
            "CPU percent uses one logical CPU as 100%; the first sample is unavailable.",
            "Commit age is elapsed host time since the last committed boundary or current lease start, not a diagnosis of Core death.",
            "Historical job transition times missing before schema 46 remain unknown.",
        ],
    }


def evaluate(config: HealthConfig, snapshot, previous, source):
    states, entries = {}, []
    for rule in config.rules:
        if not config.enabled or not rule.enabled:
            continue
        frame = snapshot["metrics"][rule.metric]
        old = previous.get(rule.id, {})
        if not frame["applicable"]:
            states[rule.id] = {"status": "inactive", "value": None}
            continue
        if old.get("status") == "inactive":
            old = {}
        now = frame["time_us"]
        # Cached host samples cannot accumulate hold time just by UI/SQL polling.
        signature = frame.get("sample_signature")
        if signature and signature == old.get("sample_signature") and old.get("last_us"):
            now = old["last_us"]
        if old.get("last_us") and int(now) < int(old["last_us"]):
            old = {}  # A wall-clock correction restarts the sampled duration.
        notices, result = evaluate_rules(
            SimpleNamespace(enabled=True, warnings_enabled=True, rules=[rule]),
            {rule.metric: frame["value"], "host_time_us": now},
            {rule.id: old},
            source | {"measurement": frame, "unit": METRICS[rule.metric]["unit"]},
            metrics={rule.metric: {"clock": "host"}},
        )
        states[rule.id] = result[rule.id] | {"sample_signature": signature}
        for notice in notices:
            notice["version"] = VERSION
            if notice["code"] == "triggered":
                notice["text"] = {
                    "zh": "执行条件在已采样宿主观测上达到预警阈值。",
                    "en": "The execution condition met its threshold in sampled host observations.",
                }
            notice.pop("content_hash", None)
            notice["content_hash"] = digest(notice)
            entries.append(notice)
    return entries, states


def process(store, project):
    with store.tx(project, repeatable=True) as db:
        from .notifications import policy_lock

        policy_lock(db, project)
        current = db.execute(
            "SELECT * FROM execution_health_monitors WHERE project_id=%s FOR UPDATE", (project,)
        ).fetchone()
        if current is None or not current["enabled"]:
            return
        policy = db.execute(
            "SELECT revision,config FROM notification_settings WHERE project_id=%s", (project,)
        ).fetchone()
        if policy is None or policy["revision"] != current["policy_revision"]:
            return
        config = NotificationConfig.model_validate(policy["config"])
        if not config.enabled or not config.events.execution_health or not config.execution_health.enabled:
            return
        evidence = snapshot(db, project)
        source = {"project_id": str(project), "policy_revision": policy["revision"], "snapshot_hash": digest(evidence)}
        notices, states = evaluate(config.execution_health, evidence, current["state"], source)
        for entry in notices:
            db.execute(
                "SELECT emit_notification(%s,NULL,%s,'execution_health',%s)",
                (project, "health:" + entry["content_hash"], Jsonb(entry)),
            )
        db.execute(
            "UPDATE execution_health_monitors SET state=%s,snapshot=%s,error=NULL,updated_at=clock_timestamp() WHERE project_id=%s",
            (Jsonb(states), Jsonb(evidence), project),
        )


def tick(store):
    with store.tx(ai_admin=True) as db:
        rows = db.execute(
            "WITH due AS (SELECT project_id FROM execution_health_monitors WHERE enabled AND next_poll_at<=clock_timestamp() "
            "ORDER BY next_poll_at FOR UPDATE SKIP LOCKED LIMIT 10) UPDATE execution_health_monitors m "
            "SET next_poll_at=clock_timestamp()+interval '5 seconds' FROM due WHERE m.project_id=due.project_id RETURNING m.project_id,m.policy_revision"
        ).fetchall()
    for row in rows:
        try:
            process(store, row["project_id"])
        except psycopg.Error:
            raise  # Database recovery belongs to the existing worker loop.
        except Exception as error:  # noqa: BLE001 -- isolate a failed read-only observer from mail delivery
            with store.tx(row["project_id"]) as db:
                db.execute(
                    "UPDATE execution_health_monitors SET enabled=false,error=%s,updated_at=clock_timestamp() WHERE project_id=%s AND policy_revision=%s",
                    (
                        "Observation stopped: " + type(error).__name__ + ". Save the notification policy to resume.",
                        row["project_id"],
                        row["policy_revision"],
                    ),
                )
