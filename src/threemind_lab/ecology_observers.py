"""Durable observers over committed population evidence; never own a brain."""

from uuid import uuid4

from psycopg.types.json import Jsonb

from threemind_runtime.ecology_observer import ObserverConfig, describe_checkpoint, describe_event, evaluate_rules
from threemind_runtime.world_schema import digest

from .database import Conflict, NotFound


def subject(db, identity):
    row = db.execute(
        "SELECT id,checkpoint_id,checkpoint_revision,status FROM ecology_campaigns WHERE id=%s", (identity,)
    ).fetchone()
    if row is None:
        raise NotFound()
    return row


def detail(db, identity):
    campaign = subject(db, identity)
    row = db.execute(
        "SELECT o.*,r.configuration,r.configuration_hash,r.first_checkpoint_revision,j.status AS job_status,j.error AS job_error "
        "FROM ecology_observers o JOIN ecology_observer_revisions r USING(campaign_id,revision) "
        "LEFT JOIN jobs j ON j.id=o.job_id WHERE o.campaign_id=%s",
        (identity,),
    ).fetchone()
    return {"observer": row, "latest_checkpoint_revision": campaign["checkpoint_revision"]}


def configure(database, project, identity, actor, config, expected_revision):
    with database.tx(project) as db:
        # Serialize the initial INSERT too, without locking the population owner.
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("ecology-observer:" + str(identity),))
        campaign = subject(db, identity)
        current = db.execute("SELECT * FROM ecology_observers WHERE campaign_id=%s FOR UPDATE", (identity,)).fetchone()
        if (current["revision"] if current else 0) != expected_revision:
            raise Conflict("observer configuration changed; reload before saving")
        if current and current["job_id"]:
            db.execute(
                "UPDATE jobs SET available_at=clock_timestamp() WHERE id=%s AND status='pending'", (current["job_id"],)
            )
        revision = expected_revision + 1
        first = 1 if config.start_from == "beginning" else max(1, campaign["checkpoint_revision"])
        raw = config.model_dump(mode="json")
        db.execute(
            "INSERT INTO ecology_observer_revisions(project_id,campaign_id,revision,configuration,configuration_hash,first_checkpoint_revision,actor_id) VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (project, identity, revision, Jsonb(raw), digest(raw), first, actor),
        )
        job_id = None
        if config.enabled:
            job_id = uuid4()
            db.execute(
                "INSERT INTO jobs(id,project_id,kind,params) VALUES(%s,%s,'ecology_observe',%s)",
                (job_id, project, Jsonb({"campaign_id": str(identity), "configuration_revision": revision})),
            )
        db.execute(
            "INSERT INTO ecology_observers(campaign_id,project_id,revision,next_checkpoint_revision,job_id) VALUES(%s,%s,%s,%s,%s) "
            "ON CONFLICT(campaign_id) DO UPDATE SET revision=excluded.revision,next_checkpoint_revision=excluded.next_checkpoint_revision,"
            "after_event_index=-1,rule_state='{}',job_id=excluded.job_id,last_checkpoint_id=NULL,updated_at=clock_timestamp()",
            (identity, project, revision, first, job_id),
        )
        db.execute(
            "INSERT INTO audit(user_id,action,resource) VALUES(%s,'ecology.observer.configure',%s)",
            (actor, str(identity)),
        )
        return detail(db, identity)


def retry(database, project, identity, expected_revision):
    with database.tx(project) as db:
        subject(db, identity)
        current = db.execute("SELECT * FROM ecology_observers WHERE campaign_id=%s FOR UPDATE", (identity,)).fetchone()
        if current is None or current["revision"] != expected_revision:
            raise Conflict("observer configuration changed")
        config = db.execute(
            "SELECT configuration FROM ecology_observer_revisions WHERE campaign_id=%s AND revision=%s",
            (identity, expected_revision),
        ).fetchone()["configuration"]
        if not config["enabled"]:
            raise Conflict("observer is disabled")
        status = db.execute("SELECT status FROM jobs WHERE id=%s", (current["job_id"],)).fetchone()
        if status and status["status"] in ("pending", "leased"):
            return detail(db, identity)
        job_id = uuid4()
        db.execute(
            "INSERT INTO jobs(id,project_id,kind,params) VALUES(%s,%s,'ecology_observe',%s)",
            (job_id, project, Jsonb({"campaign_id": str(identity), "configuration_revision": expected_revision})),
        )
        db.execute("UPDATE ecology_observers SET job_id=%s WHERE campaign_id=%s", (job_id, identity))
        return detail(db, identity)


def execute(database, job):
    """Consume at most 100 events and one checkpoint; cursor + facts are atomic."""
    identity, revision = job["params"]["campaign_id"], job["params"]["configuration_revision"]
    with database.tx(job["project_id"]) as db:
        observer = db.execute("SELECT * FROM ecology_observers WHERE campaign_id=%s FOR UPDATE", (identity,)).fetchone()
        # Match configure/retry's lock order: subscription first, then its lease.
        database.fence(db, job)
        if observer is None or observer["revision"] != revision or observer["job_id"] != job["id"]:
            db.execute(
                "UPDATE jobs SET status='done',lease_until=NULL,result=%s WHERE id=%s",
                (Jsonb({"status": "superseded"}), job["id"]),
            )
            return
        campaign = subject(db, identity)
        saved = db.execute(
            "SELECT * FROM ecology_observer_revisions WHERE campaign_id=%s AND revision=%s", (identity, revision)
        ).fetchone()
        config = ObserverConfig(**saved["configuration"])
        cp = db.execute(
            "SELECT id,revision,state_hash,time_us,observation,status FROM ecology_checkpoints WHERE campaign_id=%s AND revision=%s",
            (identity, observer["next_checkpoint_revision"]),
        ).fetchone()
        if cp:
            rows = (
                db.execute(
                    "SELECT id,event_index,payload FROM ecology_events WHERE campaign_id=%s AND population_checkpoint_id=%s AND event_index>%s ORDER BY event_index LIMIT 101",
                    (identity, cp["id"], observer["after_event_index"]),
                ).fetchall()
                if config.narration_enabled
                else []
            )
            source = {
                "campaign_id": str(identity),
                "checkpoint_id": str(cp["id"]),
                "checkpoint_revision": cp["revision"],
                "checkpoint_hash": cp["state_hash"],
                "configuration_revision": revision,
                "configuration_hash": saved["configuration_hash"],
            }
            entries = []
            for event in rows[:100]:
                entries.append(
                    (
                        "event:" + str(event["event_index"]),
                        describe_event(event["payload"], source | {"event_id": str(event["id"])}),
                    )
                )
                observer["after_event_index"] = event["event_index"]
            if len(rows) <= 100:
                population = cp["observation"].get("population", {})
                if config.narration_enabled:
                    entries.append(("summary", describe_checkpoint(population, cp["status"], source)))
                warnings, observer["rule_state"] = evaluate_rules(config, population, observer["rule_state"], source)
                entries.extend((f"rule:{entry['rule_id']}:{entry['code']}", entry) for entry in warnings)
                observer.update(
                    next_checkpoint_revision=cp["revision"] + 1, after_event_index=-1, last_checkpoint_id=cp["id"]
                )
            for key, entry in entries:
                db.execute(
                    "INSERT INTO ecology_observer_entries(project_id,campaign_id,configuration_revision,checkpoint_id,entry_key,kind,body) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                    (job["project_id"], identity, revision, cp["id"], key, entry["kind"], Jsonb(entry)),
                )
            db.execute(
                "UPDATE ecology_observers SET next_checkpoint_revision=%s,after_event_index=%s,rule_state=%s,last_checkpoint_id=%s,updated_at=clock_timestamp() WHERE campaign_id=%s",
                (
                    observer["next_checkpoint_revision"],
                    observer["after_event_index"],
                    Jsonb(observer["rule_state"]),
                    observer["last_checkpoint_id"],
                    identity,
                ),
            )
        # Paused/blocked campaigns may resume. The checkpoint trigger wakes a
        # caught-up subscription, without generating empty execution receipts.
        terminal = (
            campaign["status"] in ("completed", "cancelled")
            and observer["next_checkpoint_revision"] > campaign["checkpoint_revision"]
        )
        caught_up = observer["next_checkpoint_revision"] > campaign["checkpoint_revision"]
        db.execute(
            "UPDATE jobs SET status=%s,worker_id=NULL,lease_until=NULL,attempts=0,available_at="
            "CASE WHEN %s THEN '9999-12-31 00:00:00+00'::timestamptz ELSE clock_timestamp()+interval '1 second' END,result=%s WHERE id=%s",
            (
                "done" if terminal else "pending",
                caught_up,
                Jsonb(
                    {
                        "campaign_id": str(identity),
                        "configuration_revision": revision,
                        "next_checkpoint_revision": observer["next_checkpoint_revision"],
                    }
                ),
                job["id"],
            ),
        )
