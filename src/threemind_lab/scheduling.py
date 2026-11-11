"""Worker capability matching and read-only explanations; no model reconstruction."""

from .database import Conflict, NotFound


def available_features(report, queue):
    if not isinstance(report, dict) or report.get("queue", "runtime") != queue:
        return []
    return sorted(
        key
        for key, value in report.get("features", {}).items()
        if isinstance(value, dict)
        and (
            value.get("state") == "available" or key.startswith("worker.telemetry_") and value.get("state") == "partial"
        )
    )


def public_assignment(report):
    # Preserve the actual small probe report, never environment variables or DB credentials.
    return {
        key: report[key]
        for key in ("schema", "scope", "queue", "checked_at", "platform", "python", "backend", "features", "task_family")
        if key in report
    }


def jobs(database, project, *, history=False, run_id=None, before_time=None, before_id=None):
    """Bounded project metadata. Explanations are observations, not reservations."""
    from .execution_limits import counts

    if (before_time is None) != (before_id is None):
        raise ValueError("both cursor timestamp and job ID are required")
    if before_time is not None and before_time.tzinfo is None:
        raise ValueError("cursor timestamp must include a time zone")
    with database.tx(project, repeatable=True) as db:
        if not db.execute("SELECT 1 FROM projects WHERE id=%s", (project,)).fetchone():
            raise NotFound()
        global_row = db.execute("SELECT limits FROM execution_limits WHERE singleton").fetchone()
        if not global_row:
            raise Conflict("execution limits have not been initialized")
        global_limits = global_row["limits"]
        project_row = db.execute(
            "SELECT limits FROM project_execution_limits WHERE project_id=%s", (project,)
        ).fetchone()
        project_limits = project_row["limits"] if project_row else {}
        now = db.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        global_usage, project_usage = counts(db), counts(db, project)
        reports = db.execute(
            "SELECT capabilities FROM workers WHERE enabled AND heartbeat>%s-interval '90 seconds'", (now,)
        ).fetchall()
        availability = {
            queue: [(set(available_features(row["capabilities"], queue)), row["capabilities"].get("task_family")) for row in reports] for queue in global_limits
        }
        rows = db.execute(
            "SELECT j.id,j.run_id,j.kind,j.status,j.attempts,j.generation,j.worker_id,j.created_at,j.lease_until,"
            "j.required_features,j.available_at,CASE WHEN j.kind IN ('ai','notification') THEN j.kind ELSE 'runtime' END AS queue,"
            "(j.params ? 'barrier_id' AND (j.params->>'barrier_ready')::boolean IS DISTINCT FROM TRUE) AS barrier,"
            "a.capabilities->>'backend' AS backend,a.assigned_at "
            "FROM jobs j LEFT JOIN job_assignments a ON a.job_id=j.id AND a.generation=j.generation "
            "WHERE j.project_id=%s AND (%s OR j.status IN ('pending','leased')) "
            "AND (%s::uuid IS NULL OR j.run_id=%s) "
            "AND (%s::timestamptz IS NULL OR (j.created_at,j.id)<(%s,%s::uuid)) "
            "ORDER BY j.created_at DESC,j.id DESC LIMIT 51",
            (project, history, run_id, run_id, before_time, before_time, before_id),
        ).fetchall()
        eligible = {}
        for row in rows[:50]:
            queue = row["queue"]
            features = tuple(row["required_features"])
            key = (queue, features)
            if key not in eligible:
                eligible[key] = sum(bool(report) and set(features) <= report
                                    and (family != "playground" or any(f.startswith("worker.playground_") for f in features))
                                    for report, family in availability[queue])
            row["eligible_workers"] = eligible[key]
            project_limit = project_limits.get(queue)
            if row["status"] == "leased":
                reason = "running" if row["lease_until"] and row["lease_until"] > now else "awaiting_recovery"
            elif row["status"] != "pending":
                reason = "finished"
            elif row["barrier"]:
                reason = "waiting_checkpoint"
            elif row["available_at"] > now:
                reason = "waiting_evidence" if row["available_at"].year == 9999 else "waiting_schedule"
            elif global_limits[queue] == 0 or project_limit == 0:
                reason = "admission_paused"
            elif not row["eligible_workers"]:
                reason = "no_eligible_worker"
            elif global_usage[queue]["active"] >= global_limits[queue] or (
                project_limit is not None and project_usage[queue]["active"] >= project_limit
            ):
                reason = "capacity"
            else:
                reason = "waiting_turn"
            row["reason"] = reason
            del row["barrier"]
        return {
            "rows": rows[:50],
            "observed_at": now,
            "next": {"before_time": rows[49]["created_at"], "before_id": rows[49]["id"]} if len(rows) > 50 else None,
        }


def assignments(database, project, job):
    with database.tx(project, repeatable=True) as db:
        if not db.execute("SELECT 1 FROM jobs WHERE project_id=%s AND id=%s", (project, job)).fetchone():
            raise NotFound()
        return db.execute(
            "SELECT generation,worker_id,required_features,capabilities,assigned_at FROM job_assignments "
            "WHERE job_id=%s ORDER BY generation DESC LIMIT 5",
            (job,),
        ).fetchall()
