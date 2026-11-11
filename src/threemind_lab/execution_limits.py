"""Lab execution admission budgets, separate from model physics and display limits."""

from typing import Annotated

from psycopg.types.json import Jsonb
from pydantic import Field

from .database import Conflict, NotFound
from .protocols import StrictModel

QUEUES = ("runtime", "ai", "notification")
LOCK = 738349202  # Shared with job claims: changes and admissions serialize.
Limit = Annotated[int, Field(strict=True, ge=0, le=1024)]


class GlobalLimits(StrictModel):
    runtime: Limit
    ai: Limit
    notification: Limit


class ProjectLimits(StrictModel):
    runtime: Limit | None = None
    ai: Limit | None = None
    notification: Limit | None = None


def initialize(database, settings):
    """Use deployment environment only once; later starts never overwrite UI policy."""
    limits = GlobalLimits(
        runtime=settings.max_active_jobs,
        ai=settings.max_ai_jobs,
        notification=settings.max_notification_jobs,
    ).model_dump()
    with database.tx() as db:
        db.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK,))
        row = db.execute(
            "INSERT INTO execution_limits(singleton,limits) VALUES(true,%s) ON CONFLICT DO NOTHING RETURNING revision",
            (Jsonb(limits),),
        ).fetchone()
        if row:
            db.execute(
                "INSERT INTO execution_limit_history(revision,limits) VALUES(%s,%s)",
                (row["revision"], Jsonb(limits)),
            )


def counts(db, project=None):
    # Expired leases are recoverable work, not running capacity or successful results.
    rows = db.execute(
        "SELECT CASE WHEN kind IN ('ai','notification') THEN kind ELSE 'runtime' END AS queue,"
        "count(*) FILTER(WHERE status='pending') AS pending,"
        "count(*) FILTER(WHERE status='leased' AND lease_until>clock_timestamp()) AS active,"
        "count(*) FILTER(WHERE status='leased' AND lease_until<=clock_timestamp()) AS expired "
        "FROM jobs WHERE status IN ('pending','leased') AND (%s::uuid IS NULL OR project_id=%s) GROUP BY 1",
        (project, project),
    ).fetchall()
    by_queue = {row["queue"]: row for row in rows}
    return {queue: by_queue.get(queue, {"queue": queue, "pending": 0, "active": 0, "expired": 0}) for queue in QUEUES}


def snapshot(database, project=None):
    with database.tx(project, repeatable=True) as db:
        global_policy = db.execute("SELECT revision,limits,updated_at FROM execution_limits WHERE singleton").fetchone()
        if global_policy is None:
            raise Conflict("execution limits have not been initialized by this deployment")
        result = {"global": global_policy}
        if project is None:
            result["usage"] = counts(db)
            result["history"] = db.execute(
                "SELECT h.*,u.username AS actor FROM execution_limit_history h LEFT JOIN users u ON u.id=h.actor_id "
                "ORDER BY h.id DESC LIMIT 50"
            ).fetchall()
        else:
            selected = db.execute("SELECT name FROM projects WHERE id=%s", (project,)).fetchone()
            if not selected:
                raise NotFound()
            result["project_name"] = selected["name"]
            policy = db.execute(
                "SELECT revision,limits,updated_at FROM project_execution_limits WHERE project_id=%s", (project,)
            ).fetchone() or {"revision": 0, "limits": ProjectLimits().model_dump()}
            result["project"] = policy
            result["usage"] = counts(db, project)
            result["effective"] = {
                queue: min(global_policy["limits"][queue], policy["limits"].get(queue))
                if policy["limits"].get(queue) is not None
                else global_policy["limits"][queue]
                for queue in QUEUES
            }
        return result


def project_choices(database, query="", offset=0):
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    with database.tx() as db:
        rows = db.execute(
            "SELECT id,name FROM projects WHERE name ILIKE %s ORDER BY name,id LIMIT 51 OFFSET %s",
            (f"%{escaped}%", offset),
        ).fetchall()
        return {"rows": rows[:50], "more": len(rows) > 50}


def save(database, actor, limits, expected_revision, project=None):
    limits = (ProjectLimits if project else GlobalLimits).model_validate(limits).model_dump()
    with database.tx(project) as db:
        db.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK,))
        if project:
            if not db.execute("SELECT 1 FROM projects WHERE id=%s", (project,)).fetchone():
                raise NotFound()
            row = db.execute("SELECT revision FROM project_execution_limits WHERE project_id=%s", (project,)).fetchone()
        else:
            row = db.execute("SELECT revision FROM execution_limits WHERE singleton").fetchone()
            if row is None:
                raise Conflict("execution limits have not been initialized")
        revision = row["revision"] if row else 0
        if revision != expected_revision:
            raise Conflict("execution limits changed; reload the policy before saving")
        revision += 1
        if project:
            db.execute(
                "INSERT INTO project_execution_limits(project_id,revision,limits) VALUES(%s,%s,%s) "
                "ON CONFLICT(project_id) DO UPDATE SET revision=EXCLUDED.revision,limits=EXCLUDED.limits,updated_at=now()",
                (project, revision, Jsonb(limits)),
            )
        else:
            db.execute(
                "UPDATE execution_limits SET revision=%s,limits=%s,updated_at=now() WHERE singleton",
                (revision, Jsonb(limits)),
            )
        db.execute(
            "INSERT INTO execution_limit_history(project_id,revision,limits,actor_id) VALUES(%s,%s,%s,%s)",
            (project, revision, Jsonb(limits), actor),
        )
        db.execute(
            "INSERT INTO audit(user_id,action,resource) VALUES(%s,'execution.limits',%s)",
            (actor, str(project) if project else "deployment"),
        )
        return {"revision": revision, "limits": limits}
