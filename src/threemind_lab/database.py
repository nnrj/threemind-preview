from __future__ import annotations

import hashlib
import json
import math
from contextlib import contextmanager, nullcontext
from dataclasses import fields
from decimal import Decimal
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from threemind_core import StateImage
from threemind_core.engine import Edge, Node
from threemind_runtime.codec import ArtifactCodec

from . import checkpoints as checkpoint_codec
from .config import ROOT

LOCAL_USER = UUID("00000000-0000-4000-8000-000000000001")
CHUNK_BYTES = 4 * 1024 * 1024
MIGRATIONS = (
    "001_lab.sql",
    "002_checkpoint_deltas.sql",
    "003_configuration.sql",
    "004_sensory_inputs.sql",
    "005_media_carriers.sql",
    "006_telemetry.sql",
    "007_readouts.sql",
    "008_live_capture.sql",
    "009_energy_supply.sql",
    "010_input_selection.sql",
    "011_devices.sql",
    "012_media_uploads.sql",
    "013_conversation.sql",
    "014_source_policies.sql",
    "015_model_library.sql",
    "016_research_operations.sql",
    "017_research_plans.sql",
    "018_ai_tools.sql",
    "019_ai_runtime_tools.sql",
    "020_graph_observation.sql",
    "021_notifications.sql",
    "022_named_captures.sql",
    "023_execution_limits.sql",
    "024_worker_matching.sql",
    "025_personal_notebooks.sql",
    "026_research_documents.sql",
    "027_report_exports.sql",
    "028_research_generation.sql",
    "029_research_events.sql",
    "030_research_shares.sql",
    "031_development.sql",
    "032_environment_seed.sql",
    "033_raw_readouts.sql",
    "034_evolution.sql",
    "035_evolution_exports.sql",
    "036_evolution_publication.sql",
    "037_worlds.sql",
    "038_world_authoring.sql",
    "039_ecology.sql",
    "040_ecology_reports.sql",
    "041_device_wiring.sql",
    "042_ecology_observer.sql",
    "043_assessments.sql",
    "044_observer_ai.sql",
    "045_observer_ai_scope.sql",
    "046_execution_health.sql",
    "047_v3_restoration.sql",
    "048_chat_interpretations.sql",
    "049_probe_calibration.sql",
    "050_temporal_research.sql",
    "051_transformer_tools.sql",
    "052_operation_receipts.sql",
    "053_experiment_bundles.sql",
    "054_activity_process.sql",
    "055_robot_tasks.sql",
    "056_language_adapters.sql",
    "057_playground_tasks.sql",
    "058_species_library.sql",
    "059_language_observation.sql",
    "060_external_blobs.sql",
    "061_data_management.sql",
    "062_research_records.sql",
    "063_global_browsing.sql",
    "064_storage_locations.sql",
    "065_shared_artifact_placement.sql",
    "066_platform_permissions.sql",
    "067_platform_configuration.sql",
    "068_kernel_creation_hierarchy.sql",
)


def wire_rows(cursor):
    factory = dict_row(cursor)

    def row(values):
        result = factory(values)
        return {key: str(value) if isinstance(value, Decimal) else value for key, value in result.items()}

    return row


class Conflict(Exception):
    pass


class NotFound(Exception):
    pass


class Forbidden(Exception):
    pass


def migrate(url: str) -> None:
    """Install versioned SQL under an exclusive migration lock; never scan old data."""
    with psycopg.connect(url, autocommit=False) as db:
        db.execute("SELECT pg_advisory_xact_lock(738349201)")
        exists = db.execute("SELECT to_regclass('tm2.schema_version')").fetchone()[0]
        if exists is None:
            db.execute((ROOT / "migrations" / MIGRATIONS[0]).read_text(encoding="utf-8"))
        versions = db.execute("SELECT version FROM tm2.schema_version ORDER BY version").fetchall()
        if versions != [(i,) for i in range(1, len(versions) + 1)] or not 1 <= len(versions) <= len(MIGRATIONS):
            raise ValueError("unsupported database schema version")
        for filename in MIGRATIONS[len(versions) :]:
            db.execute((ROOT / "migrations" / filename).read_text(encoding="utf-8"))
        if db.execute("SELECT version FROM tm2.schema_version ORDER BY version").fetchall() != [
            (i,) for i in range(1, len(MIGRATIONS) + 1)
        ]:
            raise ValueError("migration did not produce the declared schema history")
        db.execute(
            "INSERT INTO tm2.users(id,username,admin) VALUES(%s,'local',true) ON CONFLICT(id) DO NOTHING", (LOCAL_USER,)
        )


class Database:
    @property
    def checkpoint_backend(self):
        path = self.blobs.storage.control_dir / "checkpoint-settings.json"
        return self.blobs.storage.checkpoint_settings()["backend"] if path.exists() else self._checkpoint_backend

    @checkpoint_backend.setter
    def checkpoint_backend(self, value):
        if value not in ("database", "filesystem"):
            raise ValueError("checkpoint backend must be database or filesystem")
        self._checkpoint_backend = value

    def __init__(self, url: str, *, allow_owner: bool = False, checkpoint_backend=None):
        import os

        from .ai_secrets import SecretBox
        from .blob_store import BlobStore

        self.blobs = BlobStore(
            secret_box=SecretBox(tuple(k for k in os.getenv("THREEMIND_SECRET_KEYS", "").split(",") if k)),
            restore_projection=os.getenv("THREEMIND_STORAGE_RESTORE") or None,
        )
        self.checkpoint_backend = checkpoint_backend or os.getenv("THREEMIND_CHECKPOINT_BACKEND", "database")
        self.pool = ConnectionPool(
            url,
            min_size=1,
            max_size=8,
            timeout=10,
            kwargs={"row_factory": wire_rows, "application_name": "threemind-lab"},
            open=True,
        )
        self.pool.wait(timeout=10)
        with self.tx() as db:
            row = db.execute(
                "SELECT r.rolsuper,r.rolbypassrls,c.relowner=r.oid AS owner FROM pg_roles r CROSS JOIN pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE r.rolname=current_user AND c.relname='runs' AND n.nspname='tm2'"
            ).fetchone()
            if row is None:
                raise ValueError("database migration is required")
            if not allow_owner and any(row.values()):
                self.pool.close()
                raise ValueError("application database role must not own tables, bypass RLS, or be a superuser")
        from .storage_payloads import PayloadStorage

        self.payloads = PayloadStorage(self)
        self.blobs.location_resolver = self.payloads.location

    def close(self):
        self.pool.close()

    @contextmanager
    def tx(
        self,
        project: str | UUID | None = None,
        *,
        repeatable: bool = False,
        ai_admin: bool = False,
        read_only: bool = False,
    ):
        with self.pool.connection() as db, db.transaction():
            if repeatable:
                db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            if read_only:
                db.execute("SET TRANSACTION READ ONLY")
            db.execute("SELECT set_config('search_path','tm2,pg_catalog',true)")
            db.execute("SELECT set_config('tm.project_id',%s,true)", (str(project) if project else "",))
            db.execute("SELECT set_config('tm.ai_admin',%s,true)", ("true" if ai_admin else "false",))
            from .permissions import current_actor, set_context
            set_context(db, current_actor(), project)
            yield db

    def authorize(self, user: dict, project: str | UUID, *, write: bool = False, owner: bool = False):
        from .permissions import project_access
        return project_access(self, user, project, write=write, owner=owner)

    def projects(self, user: dict):
        from .permissions import _resource_allowed, enrich, has_action
        user = enrich(self, user)
        if not has_action(user, "projects.read") or not _resource_allowed(user):
            raise Forbidden("project listing access denied")
        all_projects = user["superadmin"] or any(g["action"] == "projects.read" and g["scope"] == "all_projects" for g in user["permissions"])
        with self.tx() as db:
            return db.execute(
                "SELECT p.*,coalesce(m.role,'viewer') AS role FROM projects p LEFT JOIN members m ON m.project_id=p.id AND m.user_id=%s WHERE %s OR m.user_id IS NOT NULL ORDER BY p.created_at",
                (user["id"], all_projects),
            ).fetchall()

    def create_project(self, user: dict, name: str):
        project = uuid4()
        with self.tx(project) as db:
            row = db.execute(
                "INSERT INTO projects(id,name,owner_id) VALUES(%s,%s,%s) RETURNING *", (project, name, user["id"])
            ).fetchone()
            db.execute("INSERT INTO members VALUES(%s,%s,'owner')", (project, user["id"]))
            db.execute(
                "INSERT INTO audit(user_id,action,resource) VALUES(%s,'project.create',%s)", (user["id"], str(project))
            )
        return row

    def create_run(
        self,
        project,
        name,
        spec,
        *,
        parent_id=None,
        origin_hash=None,
        run_id=None,
        origin_checkpoint_id=None,
        origin_kind=None,
        transaction=None,
        execution=None,
    ):
        run = run_id or uuid4()
        if origin_kind is None and parent_id is None and origin_hash is None:
            origin_kind = "created"
        with self.tx(project) if transaction is None else nullcontext(transaction) as db:
            if run_id:
                existing = db.execute("SELECT * FROM runs WHERE id=%s", (run,)).fetchone()
                if existing:
                    return existing
            if parent_id and not db.execute("SELECT 1 FROM runs WHERE id=%s", (parent_id,)).fetchone():
                raise NotFound()
            row = db.execute(
                "INSERT INTO runs(id,project_id,name,spec,parent_id,origin_hash,origin_checkpoint_id,origin_kind,execution) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (run, project, name, Jsonb(spec), parent_id, origin_hash, origin_checkpoint_id, origin_kind,
                 Jsonb(execution or {})),
            ).fetchone()
        return row

    def enqueue(self, project, kind, params=None, run_id=None, *, transaction=None):
        params = dict(params or {})
        from .permissions import execution_actor
        actor = execution_actor()
        if actor:
            params["execution_actor"] = actor
            from .permissions import current_actor
            current = current_actor()
            params['authorization'] = {'action':current.get('_request_action'), 'resources':current.get('_request_resources', [])}
        if kind in ("report_export", "experiment_bundle_export", "bundle_export", "data_export"):
            params["storage_policy"] = self.blobs.freeze("export")
        job = uuid4()
        with self.tx(project) if transaction is None else nullcontext(transaction) as db:
            if run_id and not db.execute("SELECT 1 FROM runs WHERE id=%s", (run_id,)).fetchone():
                raise NotFound()
            return db.execute(
                "INSERT INTO jobs(id,project_id,run_id,kind,params) VALUES(%s,%s,%s,%s,%s) RETURNING *",
                (job, project, run_id, kind, Jsonb(params)),
            ).fetchone()

    def get_run(self, project, run_id):
        with self.tx(project) as db:
            row = db.execute(
                "SELECT r.*,CASE WHEN e.id IS NULL THEN NULL ELSE jsonb_build_object("
                "'campaign_id',e.id,'name',e.name,'individual',m.individual,'status',e.status,"
                "'external_inputs',e.protocol->'external_inputs') END AS ecology, "
                "(SELECT jsonb_build_object('id',a.batch_id,'name',b.name) FROM assessment_members a "
                "JOIN assessment_batches b ON b.id=a.batch_id WHERE a.run_id=r.id) AS assessment "
                "FROM runs r LEFT JOIN ecology_members m ON m.run_id=r.id "
                "LEFT JOIN ecology_campaigns e ON e.id=m.campaign_id WHERE r.id=%s",
                (run_id,),
            ).fetchone()
            if row is None:
                raise NotFound()
            return row

    def require_current_schema(self):
        with self.tx() as db:
            exists = db.execute("SELECT to_regclass('tm2.schema_version') AS relation").fetchone()["relation"]
            versions = (
                [r["version"] for r in db.execute("SELECT version FROM schema_version ORDER BY version").fetchall()]
                if exists
                else []
            )
        if versions != list(range(1, len(MIGRATIONS) + 1)):
            raise ValueError(
                f"Database schema does not match this application (requires {len(MIGRATIONS)}). "
                "Stop the application and run: python -m threemind_lab.cli migrate. "
                "Use application code matching the database if it was upgraded by a newer release."
            )

    def list_runs(self, project, *, study_id=None, limit=200, offset=0, include_archived=False, summary=False):
        projection = (
            "id,project_id,name,status,revision,time_us,life,metrics,state_hash,parent_id,origin_hash,"
            "metadata_revision,archived_at,created_at,updated_at,"
            "jsonb_build_object('environment',spec->'environment','seed',spec->'seed',"
            "'clock',spec->'clock','duration_s',spec->'duration_s','study_id',spec->'study_id',"
            "'condition',spec->'condition','block_seed',spec->'block_seed') AS spec"
            if summary
            else "*"
        )
        with self.tx(project) as db:
            return db.execute(
                "SELECT "
                + projection
                + " FROM runs"
                + (
                    " WHERE spec->>'study_id'=%s"
                    if study_id
                    else ""
                    if include_archived
                    else " WHERE archived_at IS NULL"
                )
                + " ORDER BY created_at DESC,id LIMIT %s OFFSET %s",
                ((str(study_id),) if study_id else ()) + (limit, offset),
            ).fetchall()

    def command(self, project, run_id, kind, payload, *, assessment_id=None, transaction=None):
        with self.tx(project) if transaction is None else nullcontext(transaction) as db:
            row = db.execute("SELECT status FROM runs WHERE id=%s FOR UPDATE", (run_id,)).fetchone()
            if row is None:
                raise NotFound()
            from .research_lock import assert_control_available

            assessment = db.execute("SELECT batch_id FROM assessment_members WHERE run_id=%s", (run_id,)).fetchone()
            managed_assessment = (
                assessment
                and str(assessment["batch_id"]) == str(assessment_id)
                and kind in ("pause", "cancel", "resume")
            )
            if assessment and not managed_assessment:
                raise Conflict("该试验由独立评估管理，请使用评估页面的控制；参数或输入实验请先分叉。")

            if not managed_assessment:
                assert_control_available(
                    db, run_id, population_checkpoint=kind == "checkpoint", population_input=kind == "stimulus"
                )
            if row["status"] not in ("queued", "running", "paused", "blocked"):
                raise Conflict("run is not accepting commands")
            if kind == "resume":
                if row["status"] not in ("paused", "blocked"):
                    raise Conflict("only paused or blocked runs can resume")
                if db.execute(
                    "SELECT id FROM jobs WHERE run_id=%s AND kind='run' AND status IN ('pending','leased')", (run_id,)
                ).fetchone():
                    raise Conflict("worker is still completing the pause; retry shortly")
                db.execute("UPDATE runs SET status='queued',error=NULL WHERE id=%s", (run_id,))
                from .permissions import execution_actor
                return db.execute(
                    "INSERT INTO jobs(id,project_id,run_id,kind,params) VALUES(%s,%s,%s,'run',%s) RETURNING *",
                    (uuid4(), project, run_id, Jsonb({"execution_actor": execution_actor()})),
                ).fetchone()
            cmd = db.execute(
                "INSERT INTO commands(project_id,run_id,kind,payload) VALUES(%s,%s,%s,%s) RETURNING *",
                (project, run_id, kind, Jsonb(payload)),
            ).fetchone()
            if kind == "cancel" and row["status"] in ("paused", "blocked"):
                db.execute(
                    "UPDATE runs SET status='cancelled',last_command=%s,updated_at=now() WHERE id=%s",
                    (cmd["id"], run_id),
                )
                db.execute(
                    "INSERT INTO events(project_id,run_id,event_key,time_us,kind,payload) SELECT project_id,id,%s,time_us,'cancel','{}' FROM runs WHERE id=%s",
                    (f"command:{cmd['id']}", run_id),
                )
            return cmd

    def announce_worker(self, worker, capabilities):
        from .worker_health import sample

        health = sample()
        with self.tx() as db:
            db.execute(
                "INSERT INTO workers(id,name,heartbeat,capabilities,health,health_received_at) VALUES(%s,%s,now(),%s,%s,clock_timestamp()) "
                "ON CONFLICT(id) DO UPDATE SET heartbeat=now(),capabilities=EXCLUDED.capabilities,health=EXCLUDED.health,"
                "health_received_at=CASE WHEN workers.health->>'sample_id' IS DISTINCT FROM EXCLUDED.health->>'sample_id' THEN clock_timestamp() ELSE workers.health_received_at END",
                (worker, worker, Jsonb(capabilities), Jsonb(health)),
            )

    def claim(self, worker: str, *, max_active: int = 2, queue: str = "runtime", capabilities: dict | None = None):
        if queue not in ("runtime", "ai", "notification"):
            raise ValueError("unknown worker queue")
        with self.tx(ai_admin=queue == "ai") as db:
            enabled = db.execute("SELECT enabled FROM workers WHERE id=%s", (worker,)).fetchone()
            if enabled and not enabled["enabled"]:
                return None
            db.execute(
                "INSERT INTO workers(id,name,heartbeat) VALUES(%s,%s,clock_timestamp()) ON CONFLICT(id) DO UPDATE SET heartbeat=clock_timestamp()",
                (worker, worker),
            )
            # The upsert holds this worker row lock until commit. Recheck after
            # acquiring it so an acknowledged drain cannot race an earlier read.
            if not db.execute("SELECT enabled FROM workers WHERE id=%s", (worker,)).fetchone()["enabled"]:
                return None
            db.execute("SELECT pg_advisory_xact_lock(738349202)")
            policy = db.execute("SELECT limits FROM execution_limits WHERE singleton").fetchone()
            if policy is not None:
                max_active = policy["limits"][queue]
            expired = db.execute(
                "SELECT id,project_id,run_id,kind FROM jobs WHERE status='leased' AND lease_until<clock_timestamp() AND attempts>=5 FOR UPDATE SKIP LOCKED"
            ).fetchall()
            for failed in expired:
                db.execute("SELECT set_config('tm.project_id',%s,true)", (str(failed["project_id"]) if failed["project_id"] else "",))
                db.execute(
                    "UPDATE jobs SET status='failed',error='worker recovery attempts exhausted',lease_until=NULL WHERE id=%s",
                    (failed["id"],),
                )
                if failed["kind"] == "notification":
                    db.execute("SELECT set_config('tm.project_id',%s,true)", (str(failed["project_id"]) if failed["project_id"] else "",))
                    db.execute(
                        "UPDATE notifications SET email_status=CASE WHEN dispatched_at IS NULL THEN 'failed' ELSE 'uncertain' END,"
                        "email_reason='worker_recovery_exhausted',finished_at=clock_timestamp() WHERE email_job_id=%s AND email_status IN ('queued','sending')",
                        (failed["id"],),
                    )
                if failed["kind"] == "ai":
                    db.execute("SELECT set_config('tm.project_id',%s,true)", (str(failed["project_id"]) if failed["project_id"] else "",))
                    calls = db.execute(
                        "UPDATE ai_calls SET status=CASE WHEN sent_at IS NULL THEN 'failed' ELSE 'uncertain' END,"
                        "error='worker recovery attempts exhausted; request was not resent',updated_at=clock_timestamp() "
                        "WHERE job_id=%s AND status IN ('queued','sending') RETURNING id",
                        (failed["id"],),
                    ).fetchall()
                    for call in calls:
                        db.execute("UPDATE ai_reservations SET active=false WHERE call_id=%s", (call["id"],))
                if failed["run_id"] and failed["kind"] in ("run", "research_plan"):
                    db.execute("SELECT set_config('tm.project_id',%s,true)", (str(failed["project_id"]),))
                    db.execute("SELECT id FROM runs WHERE id=%s FOR UPDATE", (failed["run_id"],))
                    from .state_captures import finish_failed

                    finish_failed(db, failed["run_id"], "运行任务恢复次数耗尽，捕获未完成。", job_id=failed["id"])
                    db.execute(
                        "UPDATE research_plans SET status='failed',error='worker recovery attempts exhausted',updated_at=clock_timestamp() "
                        "WHERE job_id=%s AND status IN ('queued','running')",
                        (failed["id"],),
                    )
                    db.execute(
                        "UPDATE research_operations SET status='failed',error='worker recovery attempts exhausted',updated_at=clock_timestamp() WHERE job_id=%s AND status='pending'",
                        (failed["id"],),
                    )
                    db.execute(
                        "UPDATE runs SET status='blocked',error='worker recovery attempts exhausted' WHERE id=%s",
                        (failed["run_id"],),
                    )
                from .evolution import child_finished, job_failed

                job_failed(db, failed, "worker recovery attempts exhausted")
                child_finished(db, failed)
                from .ecology_store import job_failed as ecology_failed

                ecology_failed(db, failed, "worker recovery attempts exhausted")
            db.execute("SELECT set_config('tm.project_id','',true)")
            count = db.execute(
                "SELECT count(*) AS n FROM jobs WHERE status='leased' AND lease_until>clock_timestamp() AND (CASE WHEN kind IN ('ai','notification') THEN kind ELSE 'runtime' END)=%s",
                (queue,),
            ).fetchone()["n"]
            if count >= max_active:
                return None
            from .scheduling import available_features, public_assignment

            record = db.execute("SELECT capabilities FROM workers WHERE id=%s", (worker,)).fetchone()
            report = capabilities if capabilities is not None else record["capabilities"] if record else {}
            features = available_features(report, queue)
            if not features:
                return None
            row = db.execute(
                """WITH project_usage AS MATERIALIZED (
                SELECT project_id,count(*) AS active FROM jobs WHERE status='leased' AND lease_until>clock_timestamp()
                AND (CASE WHEN kind IN ('ai','notification') THEN kind ELSE 'runtime' END)=%s GROUP BY project_id),
                candidate AS (
                SELECT candidate_job.id FROM jobs candidate_job
                LEFT JOIN project_usage u ON u.project_id=candidate_job.project_id
                LEFT JOIN project_execution_limits p ON p.project_id=candidate_job.project_id
                WHERE (status='pending' OR (status='leased' AND lease_until<clock_timestamp())) AND attempts<5
                AND candidate_job.available_at<=clock_timestamp()
                AND (CASE WHEN kind IN ('ai','notification') THEN kind ELSE 'runtime' END)=%s
                AND (NOT params ? 'barrier_id' OR (params->>'barrier_ready')::boolean IS TRUE)
                AND candidate_job.required_features <@ %s::text[]
                AND (NOT %s OR EXISTS (SELECT 1 FROM unnest(candidate_job.required_features) f WHERE starts_with(f,'worker.playground_')))
                AND (NOT %s OR 'worker.backend:reference'=ANY(candidate_job.required_features))
                AND coalesce(u.active,0) < coalesce((p.limits->>%s)::integer,%s)
                ORDER BY candidate_job.created_at,candidate_job.id FOR UPDATE OF candidate_job SKIP LOCKED LIMIT 1)
                UPDATE jobs j SET status='leased',worker_id=%s,generation=generation+1,attempts=attempts+1,
                    lease_until=clock_timestamp()+interval '60 seconds'
                FROM candidate WHERE j.id=candidate.id RETURNING j.*""",
                (queue, queue, features, report.get("task_family") == "playground",
                 report.get("task_family") == "kernel-reference", queue, max_active, worker),
            ).fetchone()
            if row:
                db.execute("SELECT set_config('tm.project_id',%s,true)", (str(row["project_id"]) if row["project_id"] else "",))
                db.execute(
                    "INSERT INTO job_assignments(project_id,job_id,generation,worker_id,required_features,capabilities) VALUES(%s,%s,%s,%s,%s,%s)",
                    (
                        row["project_id"],
                        row["id"],
                        row["generation"],
                        worker,
                        row["required_features"],
                        Jsonb(public_assignment(report)),
                    ),
                )
            if row and row["kind"] in ("run", "research_plan") and row["attempts"] > 1:
                db.execute("SELECT set_config('tm.project_id',%s,true)", (str(row["project_id"]),))
                db.execute("SELECT id FROM runs WHERE id=%s FOR UPDATE", (row["run_id"],))
                for table, condition in (("capture_sessions", ""), ("device_sessions", " AND clock_mode='device'")):
                    # Only fixed internal identifiers are interpolated.
                    db.execute(
                        f"UPDATE {table} SET status='interrupted',reason='worker_replaced',updated_at=clock_timestamp() WHERE run_id=%s AND status='active'{condition}",
                        (row["run_id"],),
                    )
            return row

    def renew(self, job):
        from .worker_health import sample

        health = sample()
        with self.tx() as db:
            row = db.execute(
                "UPDATE jobs SET lease_until=clock_timestamp()+interval '60 seconds' WHERE id=%s AND worker_id=%s AND generation=%s AND status='leased' AND lease_until>clock_timestamp() RETURNING id",
                (job["id"], job["worker_id"], job["generation"]),
            ).fetchone()
            if row is None:
                raise Conflict("worker lease expired or replaced")
            db.execute(
                "UPDATE workers SET heartbeat=now(),health=%s,health_received_at=CASE WHEN health->>'sample_id' IS DISTINCT FROM %s THEN clock_timestamp() ELSE health_received_at END WHERE id=%s",
                (Jsonb(health), health["sample_id"], job["worker_id"]),
            )

    @staticmethod
    def fence(db, job):
        if job is None:
            return
        row = db.execute(
            "SELECT id FROM jobs WHERE id=%s AND worker_id=%s AND generation=%s AND status='leased' AND lease_until>clock_timestamp() FOR UPDATE",
            (job["id"], job["worker_id"], job["generation"]),
        ).fetchone()
        if row is None:
            raise Conflict("stale worker cannot commit")

    def finish(self, job, *, result=None, error=None, cancelled=False):
        with self.tx(job["project_id"]) as db:
            self.fence(db, job)
            db.execute(
                "UPDATE jobs SET status=%s,result=%s,error=%s,lease_until=NULL WHERE id=%s",
                ("cancelled" if cancelled else "failed" if error else "done", Jsonb(result or {}), error, job["id"]),
            )
            if error and job["run_id"] and job["kind"] in ("run", "research_plan"):
                db.execute("SELECT id FROM runs WHERE id=%s FOR UPDATE", (job["run_id"],))
                from .state_captures import finish_failed

                finish_failed(db, job["run_id"], "运行任务失败，捕获未完成。", job_id=job["id"])
                if job["kind"] == "research_plan":
                    db.execute(
                        "UPDATE research_plans SET status='failed',error=%s,updated_at=now() WHERE job_id=%s "
                        "AND status IN ('queued','running')",
                        (error, job["id"]),
                    )
                db.execute(
                    "UPDATE research_operations SET status='failed',error=%s,updated_at=now() WHERE job_id=%s AND status='pending'",
                    (error, job["id"]),
                )
                if job["kind"] == "run":
                    db.execute(
                        "UPDATE runs SET status='failed',error=%s,updated_at=now() WHERE id=%s", (error, job["run_id"])
                    )
                else:
                    db.execute(
                        "UPDATE runs SET status='blocked',error=%s,updated_at=now() WHERE id=%s AND status IN ('running','queued')",
                        (error, job["run_id"]),
                    )
                db.execute(
                    "UPDATE capture_sessions SET status='interrupted',reason='worker_failed',updated_at=now() "
                    "WHERE run_id=%s AND status='active'",
                    (job["run_id"],),
                )
                db.execute(
                    "UPDATE device_sessions SET status='interrupted',reason='worker_failed',updated_at=now() WHERE run_id=%s AND clock_mode='device' AND status='active'",
                    (job["run_id"],),
                )
            from .evolution import child_finished, job_failed

            if error:
                job_failed(db, job, error)
                from .ecology_store import job_failed as ecology_failed

                ecology_failed(db, job, error)
            child_finished(db, job)
            from .native_records import execution_finished

            execution_finished(self, db, job, error=error, cancelled=cancelled)

    def save_checkpoint(
        self,
        project,
        run_id,
        image: StateImage,
        *,
        context=None,
        expected_revision: int,
        status="running",
        job=None,
        observations=(),
        events=(),
        last_command=None,
        previous=None,
        captured=None,
        configuration_change=None,
        live_protocol_change=None,
        input_changes=None,
        research_completion=None,
        transaction=None,
    ):
        # A population owner must commit every brain and the physical manifest
        # together. Reject an unscoped/autocommit connection before any writes.
        if transaction is not None:
            if transaction.info.transaction_status != psycopg.pq.TransactionStatus.INTRANS:
                raise ValueError("checkpoint requires an active owning transaction")
            scope = transaction.execute("SELECT current_setting('tm.project_id',true) AS project").fetchone()
            if scope["project"] != str(project):
                raise ValueError("checkpoint transaction has a different project scope")
        commit_context = {**(context or {}), "last_command": last_command}
        if configuration_change is not None:
            commit_context["configuration_change"] = configuration_change
        if live_protocol_change is not None:
            from .organ_controls import validate_change

            validate_change(live_protocol_change)
            commit_context["organ_controls"] = live_protocol_change
        if input_changes:
            from .inputs import digest

            commit_context["input_audit_hash"] = digest(input_changes)
        if research_completion is not None:
            commit_context["research_completion"] = research_completion
        commit_context["commit_fingerprint"] = hashlib.sha256(
            json.dumps(
                {"context": commit_context, "status": status, "observations": observations, "events": events},
                sort_keys=True,
                default=str,
            ).encode()
        ).hexdigest()
        state = captured if captured is not None else image.to_dict()
        raw, storage_format, depth, patch = checkpoint_codec.encode(state, image.digest, previous)
        commit_context["persistence"] = {
            "format": storage_format,
            "bytes": len(raw),
            "delta_depth": depth,
            "projection_upserts": {t: len(patch[t]["upsert"]) if patch else len(state[t]) for t in ("nodes", "edges")},
        }
        checkpoint = uuid4()
        # Host storage only: publication precedes the scientific transaction.
        # A failed transaction leaves an explicit unattached candidate, never a
        # visible partial checkpoint. This also applies to population transactions.
        prepared_blob = (
            self.payloads.prepare_checkpoint(project, raw) if self.checkpoint_backend == "filesystem" else None
        )
        with self.tx(project) if transaction is None else nullcontext(transaction) as db:
            self.fence(db, job)
            # Revision fencing still serializes checkpoint/configuration writers.
            # Compatible KEY SHARE admissions may retain new physical packets while
            # the graph projection is written; no primary/foreign key is changed.
            current = db.execute("SELECT * FROM runs WHERE id=%s FOR NO KEY UPDATE", (run_id,)).fetchone()
            if current is None:
                raise NotFound()
            if configuration_change is not None:
                from .research_lock import assert_control_available

                assert_control_available(db, run_id)
                if (
                    current["status"] not in ("paused", "blocked")
                    or db.execute(
                        "SELECT 1 FROM jobs WHERE run_id=%s AND kind='run' AND status IN ('pending','leased')",
                        (run_id,),
                    ).fetchone()
                ):
                    raise Conflict("请暂停运行，并等待工作进程完成检查点后再保存配置。")
                from .inputs import pending_budget

                pending = pending_budget(db, run_id)
                limits = configuration_change["after"]["input_bus"]
                if (
                    int(pending["frames"]) > limits["max_pending_frames"]
                    or int(pending["channels"]) > limits["max_pending_channels"]
                ):
                    raise Conflict("新预算小于已接收载体的待递送量；请等待递送或提高输入总线预算。")
                if current["spec"] != configuration_change["before"]:
                    raise Conflict("配置已被其他操作更新，请重新载入后编辑。")
                if current["metadata_revision"] != configuration_change.get(
                    "expected_metadata_revision", current["metadata_revision"]
                ):
                    raise Conflict("名称或档案信息已更新，请重新载入后保存配置。")
            if current["revision"] != expected_revision:
                # The exact same retry is acknowledged; a different state is never overwritten.
                existing = db.execute(
                    "SELECT * FROM checkpoints WHERE run_id=%s AND revision=%s AND state_hash=%s",
                    (run_id, expected_revision + 1, image.digest),
                ).fetchone()
                if (
                    existing
                    and existing["context"].get("commit_fingerprint") == commit_context["commit_fingerprint"]
                    and current["revision"] == expected_revision + 1
                ):
                    return existing
                raise Conflict("checkpoint revision changed")
            if live_protocol_change is not None:
                from .protocols import RunSpec

                if RunSpec(**current["spec"]).model_dump() != live_protocol_change["before"]:
                    raise Conflict("器官设置生效前配置已改变；请重新读取。")
            revision = expected_revision + 1
            if previous and (
                str(previous[0]["run_id"]) != str(run_id)
                or str(previous[0]["project_id"]) != str(project)
                or previous[0]["revision"] != expected_revision
                or previous[0]["state_hash"] != current["state_hash"]
            ):
                raise Conflict("checkpoint delta base differs from current revision")
            row = db.execute(
                "INSERT INTO checkpoints(id,project_id,run_id,revision,time_us,sequence,state_hash,context,byte_count,storage_format,base_checkpoint_id,delta_depth,blob_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (
                    checkpoint,
                    project,
                    run_id,
                    revision,
                    state["time_us"],
                    state["sequence"],
                    image.digest,
                    Jsonb(commit_context),
                    len(raw),
                    storage_format,
                    previous[0]["id"] if depth else None,
                    depth,
                    self.blobs.attach(db, prepared_blob),
                ),
            ).fetchone()
            with db.cursor() as cp:
                for i in range(0, 0 if prepared_blob else len(raw), CHUNK_BYTES):
                    block = raw[i : i + CHUNK_BYTES]
                    cp.execute(
                        "INSERT INTO state_chunks VALUES(%s,%s,%s,%s,%s)",
                        (project, checkpoint, i // CHUNK_BYTES, block, hashlib.sha256(block).hexdigest()),
                    )
            # COPY to transaction-local staging, then reconcile the current projection.
            # No ORM object per numerical value and no growing per-run JSON replacement.
            if state["dynamics"] == "unified-associative":
                from .legacy_graph import save as save_legacy_graph

                save_legacy_graph(db, project, run_id, state)
            for name, kind, keys in (("nodes", Node, ("id",)), ("edges", Edge, ("source", "target"))):
                if state["dynamics"] == "unified-associative":
                    break
                columns = [f.name for f in fields(kind)]
                temp = "stage_" + name
                db.execute(
                    sql.SQL("CREATE TEMP TABLE {} (LIKE {} INCLUDING DEFAULTS) ON COMMIT DROP").format(
                        sql.Identifier(temp), sql.Identifier(name)
                    )
                )
                names = ["project_id", "run_id", *columns]
                with db.cursor().copy(
                    sql.SQL("COPY {} ({}) FROM STDIN").format(
                        sql.Identifier(temp), sql.SQL(",").join(map(sql.Identifier, names))
                    )
                ) as cp:
                    for item in patch[name]["upsert"] if patch is not None else state[name]:
                        cp.write_row(
                            (
                                project,
                                run_id,
                                *(
                                    item.get(k)
                                    if k
                                    in ("birth_us", "local_plasticity", "pending_inhibition", "generated_inhibition")
                                    else item[k]
                                    for k in columns
                                ),
                            )
                        )
                equality = sql.SQL(" AND ").join(sql.SQL("s.{0}=t.{0}").format(sql.Identifier(k)) for k in keys)
                if patch is not None:
                    removed = patch[name]["delete"]
                    if removed:
                        deleted = "deleted_" + name
                        db.execute(
                            sql.SQL("CREATE TEMP TABLE {} AS SELECT {} FROM {} WITH NO DATA").format(
                                sql.Identifier(deleted),
                                sql.SQL(",").join(map(sql.Identifier, keys)),
                                sql.Identifier(name),
                            )
                        )
                        with db.cursor().copy(sql.SQL("COPY {} FROM STDIN").format(sql.Identifier(deleted))) as cp:
                            for row_key in removed:
                                cp.write_row(row_key)
                        db.execute(
                            sql.SQL("DELETE FROM {} t USING {} s WHERE t.run_id=%s AND {}").format(
                                sql.Identifier(name), sql.Identifier(deleted), equality
                            ),
                            (run_id,),
                        )
                        db.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier(deleted)))
                else:
                    db.execute(
                        sql.SQL("DELETE FROM {} t WHERE run_id=%s AND NOT EXISTS(SELECT 1 FROM {} s WHERE {})").format(
                            sql.Identifier(name), sql.Identifier(temp), equality
                        ),
                        (run_id,),
                    )
                update = sql.SQL(",").join(
                    sql.SQL("{0}=EXCLUDED.{0}").format(sql.Identifier(k)) for k in columns if k not in keys
                )
                before = sql.SQL(",").join(
                    sql.SQL("current_row.{}").format(sql.Identifier(k)) for k in columns if k not in keys
                )
                after = sql.SQL(",").join(
                    sql.SQL("EXCLUDED.{}").format(sql.Identifier(k)) for k in columns if k not in keys
                )
                db.execute(
                    sql.SQL(
                        "INSERT INTO {} AS current_row SELECT * FROM {} ON CONFLICT ({}) DO UPDATE SET {} WHERE ({}) IS DISTINCT FROM ({})"
                    ).format(
                        sql.Identifier(name),
                        sql.Identifier(temp),
                        sql.SQL(",").join(map(sql.Identifier, ("run_id", *keys))),
                        update,
                        before,
                        after,
                    )
                )
                db.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier(temp)))
            for event in events:
                db.execute(
                    "INSERT INTO events(project_id,run_id,event_key,time_us,kind,payload,commit_revision,provenance) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(run_id,event_key) DO NOTHING",
                    (
                        project,
                        run_id,
                        event["key"],
                        event["time_us"],
                        event["kind"],
                        Jsonb(event["payload"]),
                        revision,
                        Jsonb(event.get("provenance")),
                    ),
                )
            for observation in observations:
                db.execute(
                    "INSERT INTO observations(project_id,run_id,time_us,sequence,metrics,commit_revision) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(run_id,time_us) DO NOTHING",
                    (project, run_id, observation["time_us"], observation["sequence"], Jsonb(observation), revision),
                )
            if input_changes:
                from .inputs import commit_inputs

                commit_inputs(db, project, run_id, revision, input_changes)
            metrics = (
                observations[-1]
                if observations
                else {
                    "nodes": len(state["nodes"]),
                    "edges": len(state["edges"]),
                    "life": state["life"],
                    "time_us": state["time_us"],
                }
            )
            if "resources" in state:
                from threemind_core.spec import BUDGET_DEFAULTS

                # Latest accounting is the actual checkpoint boundary, even when
                # the last scientific observation was earlier or absent.
                metrics = metrics | {
                    "resources": state["resources"]
                    | {
                        "limits": {key: state["config"].get(key) for key in BUDGET_DEFAULTS},
                        "step_us": state["config"]["step_us"],
                    }
                }
            if "energy" in state:
                from threemind_core.energy import observation as energy_observation

                reserve = None
                if (
                    state["dynamics"] in (
                        "threemind.continuous-memory/4", "threemind.continuous-memory/5", "threemind.continuous-memory/5.1",
                        "threemind.continuous-memory/5.2", "threemind.continuous-memory/5.3", "threemind.continuous-memory/6.0", "threemind.continuous-memory/6.1", "threemind.continuous-memory/6.2", "threemind.continuous-memory/6.3"
                    )
                    and state["config"]["energy_model"] == "local-field"
                ):
                    # This is a read-only aggregate of the checkpoint's local
                    # pools and reserves, not the retired global reservoir.
                    reserve = math.fsum(
                        [amount for _, amount in state["pools"]]
                        + [node["reserve"] for node in state["nodes"]]
                    )

                metrics = metrics | {
                    "energy": energy_observation(
                        state["energy"],
                        state["config"],
                        state.get("state_time_us", state["time_us"]),
                        reserve=reserve,
                    )
                }
            if "attention" in state:
                from threemind_core import Config
                from threemind_core.attention import Attention
                from threemind_core.spec import ATTENTION_DEFAULTS
                from threemind_kernels.registry import kernel_catalog, resolve_kernel

                configuration = (
                    resolve_kernel(state["dynamics"]).configuration(state["config"])
                    if state["dynamics"] in {k["kernel_id"] for k in kernel_catalog()}
                    else Config(**state["config"])
                )

                metrics = metrics | {
                    "attention": state["attention"]
                    | {
                        "parameters": {
                            key: state["config"].get(key, default) for key, default in ATTENTION_DEFAULTS.items()
                        },
                        "effective": Attention.restore(state["attention"], int(state["time_us"])).effective(
                            int(state["time_us"]), configuration
                        ),
                    }
                }
            if state["dynamics"] == "threemind.causal/6":
                from threemind_core import Config
                from threemind_core.spatial import Spatial

                spatial_config = Config(**state["config"])
                metrics = metrics | {
                    "spatial": Spatial().summary(
                        spatial_config,
                        {n["id"]: n for n in state["nodes"]} if spatial_config.spatial_embedding else {},
                        {(e["source"], e["target"]): e for e in state["edges"]}
                        if spatial_config.spatial_embedding
                        else {},
                    )
                }
            db.execute(
                "UPDATE runs SET revision=%s,time_us=%s,sequence=%s,state_hash=%s,status=%s,life=%s,metrics=%s,last_command=%s,updated_at=now() WHERE id=%s",
                (
                    revision,
                    state["time_us"],
                    state["sequence"],
                    image.digest,
                    status,
                    state["life"],
                    Jsonb(metrics),
                    last_command if last_command is not None else current["last_command"],
                    run_id,
                ),
            )
            db.execute(
                "INSERT INTO outbox(project_id,topic,payload) VALUES(%s,'checkpoint',%s)",
                (project, Jsonb({"run_id": str(run_id), "revision": revision})),
            )
            if configuration_change is not None:
                from .model_library import update_metadata

                update_metadata(
                    db, project, current, {"name": configuration_change["name"]}, configuration_change["user_id"]
                )
                db.execute(
                    "UPDATE runs SET spec=%s WHERE id=%s",
                    (Jsonb(configuration_change["after"]), run_id),
                )
                db.execute(
                    "INSERT INTO audit(user_id,action,resource) VALUES(%s,'run.configure',%s)",
                    (configuration_change["user_id"], str(run_id)),
                )
            if live_protocol_change is not None:
                db.execute("UPDATE runs SET spec=%s WHERE id=%s", (Jsonb(live_protocol_change["after"]), run_id))
                for operation in live_protocol_change["operations"]:
                    db.execute(
                        "INSERT INTO audit(user_id,action,resource,details) VALUES(%s,'run.organ-switch',%s,%s)",
                        (operation["actor_id"], str(run_id), Jsonb(operation | {"applied_at_us": state["time_us"]})),
                    )
            if research_completion is not None:
                from .research_operations import finish_at_checkpoint

                finish_at_checkpoint(
                    db,
                    project,
                    run_id,
                    research_completion["operation_id"],
                    checkpoint,
                    research_completion["result"] | {"revision": revision, "state_hash": image.digest},
                )
            if (last_command or 0) > current["last_command"] or status != "running":
                from .state_captures import resolve

                row |= resolve(db, project, current, row, last_command, status != "running") or {}
            db.execute("SELECT pg_notify('threemind_changes',%s)", (str(project),))
            # Resolve export requests to this first acknowledged, immutable boundary.
            db.execute(
                "UPDATE jobs SET params=params || jsonb_build_object('barrier_ready',true,'checkpoint_id',%s::text) WHERE run_id=%s AND status='pending' AND params ? 'barrier_id' AND NOT coalesce((params->>'barrier_ready')::boolean,false) AND ((params->>'barrier_id')::bigint<=%s OR %s)",
                (
                    str(checkpoint),
                    run_id,
                    last_command or 0,
                    status in ("paused", "completed", "dead", "cancelled", "failed", "blocked"),
                ),
            )
            return row

    def checkpoint_identity(self, project, run_id, checkpoint_id=None):
        """Small, project-scoped selection without decoding any model chunks."""
        with self.tx(project) as db:
            row = db.execute(
                "SELECT id,revision,time_us,sequence,state_hash FROM checkpoints WHERE run_id=%s"
                + (" AND id=%s" if checkpoint_id else "")
                + " ORDER BY revision DESC LIMIT 1",
                (run_id, checkpoint_id) if checkpoint_id else (run_id,),
            ).fetchone()
            if row is None:
                raise NotFound("no checkpoint")
            return row

    def load_checkpoint(self, project, run_id, checkpoint_id=None):
        with self.tx(project, repeatable=True) as db:
            row = db.execute(
                "SELECT * FROM checkpoints WHERE run_id=%s"
                + (" AND id=%s" if checkpoint_id else "")
                + " ORDER BY revision DESC LIMIT 1",
                (run_id, checkpoint_id) if checkpoint_id else (run_id,),
            ).fetchone()
            if row is None:
                raise NotFound("no checkpoint")
            chain, cursor = [], row
            while True:
                if len(chain) > checkpoint_codec.MAX_DEPTH:
                    raise ValueError("checkpoint delta chain exceeds recovery budget")
                blob = (
                    db.execute("SELECT * FROM stored_blobs WHERE id=%s", (cursor["blob_id"],)).fetchone()
                    if cursor.get("blob_id")
                    else None
                )
                if cursor.get("blob_id") and (not blob or blob["bytes"] != cursor["byte_count"]):
                    raise ValueError("checkpoint external payload is inconsistent")
                if blob:
                    blob = self.payloads.location(blob, transaction=db)
                chunks = (
                    []
                    if blob
                    else db.execute(
                        "SELECT * FROM state_chunks WHERE checkpoint_id=%s ORDER BY ordinal", (cursor["id"],)
                    ).fetchall()
                )
                if any(
                    c["ordinal"] != i or hashlib.sha256(c["body"]).hexdigest() != c["sha256"]
                    for i, c in enumerate(chunks)
                ):
                    raise ValueError("checkpoint chunk checksum failed")
                raw = b"".join(c["body"] for c in chunks)
                if not blob and len(raw) != cursor["byte_count"]:
                    raise ValueError("incomplete checkpoint")
                chain.append((cursor, raw, blob))
                if cursor["storage_format"] == "tmind/2":
                    break
                base = db.execute(
                    "SELECT * FROM checkpoints WHERE run_id=%s AND id=%s", (run_id, cursor["base_checkpoint_id"])
                ).fetchone()
                if (
                    base is None
                    or base["revision"] != cursor["revision"] - 1
                    or base["delta_depth"] != cursor["delta_depth"] - 1
                ):
                    raise ValueError("invalid checkpoint delta lineage")
                cursor = base
        image = None
        for cp, raw, blob in reversed(chain):
            if blob:
                raw = b"".join(self.blobs.read(blob, resolve=False))
            image = ArtifactCodec.decode(raw) if image is None else checkpoint_codec.apply_delta(raw, image)
            if image.digest != cp["state_hash"]:
                raise ValueError("checkpoint state checksum failed")
        return row, image

    def query_graph(
        self, project, run_id, *, table="nodes", after=None, limit=200, minimum=0.0, revision=None, source=None, node_id=None
    ):
        if table not in ("nodes", "edges"):
            raise ValueError("unknown graph table")
        with self.tx(project, repeatable=True) as db:
            run = db.execute("SELECT revision,time_us,sequence,metrics,spec->>'kernel_id' AS kernel_id FROM runs WHERE id=%s", (run_id,)).fetchone()
            if run is None:
                raise NotFound()
            if revision is not None and run["revision"] != revision:
                raise Conflict("state changed; restart pagination at its new revision")
            legacy = run["kernel_id"] == "unified-associative"
            after = after if after is not None else (-1 if table == "nodes" and not legacy else 0)
            if node_id is not None:
                if table != "nodes":
                    raise ValueError("node_id is only accepted for node queries")
                rows = ([row["payload"] for row in db.execute(
                    "SELECT payload FROM legacy_graph_rows WHERE run_id=%s AND kind='nodes' AND identity=%s",
                    (run_id, str(node_id)),
                ).fetchall()] if legacy else db.execute("SELECT * FROM nodes WHERE run_id=%s AND id=%s",
                                                        (run_id, int(node_id))).fetchall())
            elif legacy:
                from .legacy_graph import rows as legacy_rows

                rows = legacy_rows(db, run_id, table, after=after, limit=limit + 1, minimum=minimum,
                                   source=str(source) if source is not None else None)
            elif table == "nodes":
                rows = db.execute(
                    "SELECT * FROM nodes WHERE run_id=%s AND id>%s AND activation>=%s ORDER BY id LIMIT %s",
                    (run_id, after, minimum, limit + 1),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM edges WHERE run_id=%s AND weight>=%s AND (%s::bigint IS NULL OR source=%s) ORDER BY source,target OFFSET %s LIMIT %s",
                    (run_id, minimum, source, source, after, limit + 1),
                ).fetchall()
            more = len(rows) > limit
            rows = rows[:limit]
            for row in rows:
                row.pop("project_id", None)
                row.pop("run_id", None)
                for key in ("last_touch_us", "birth_us"):
                    if key in row:
                        row[key] = str(row[key])
            return {
                **run,
                "time_us": str(run["time_us"]),
                "rows": rows,
                "more": more,
                "next": (rows[-1]["id"] if table == "nodes" and not legacy else after + len(rows)) if rows else after,
            }

    def put_artifact(self, job, name: str, media_type: str, raw: bytes, metadata=None):
        return self._put_artifact_chunks(
            job, name, media_type, (raw[i : i + CHUNK_BYTES] for i in range(0, len(raw), CHUNK_BYTES)), metadata
        )

    def put_artifact_stream(self, job, name: str, media_type: str, stream, metadata=None):
        return self._put_artifact_chunks(job, name, media_type, iter(lambda: stream.read(CHUNK_BYTES), b""), metadata)

    def _put_artifact_chunks(self, job, name, media_type, chunks, metadata):
        artifact = uuid4()
        # Only explicit export tasks may externalize. Scientific weights/state
        # and ordinary analysis records keep their original database semantics.
        frozen = job.get("params", {}).get("storage_policy", {"kind": "db", "category": "export", "policy_revision": 0})
        prepared = (
            self.blobs.prepare(job["project_id"], "export", chunks, frozen=frozen) if frozen["kind"] != "db" else None
        )
        with self.tx(job["project_id"]) as db:
            if job.get("params", {}).get("actor_id"):
                db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(job["params"]["actor_id"]),))
            # Do not hold the job's UPDATE lock throughout a long upload: it
            # would block the background lease heartbeat. Check the generation
            # initially and fence under a row lock again before commit.
            if not db.execute(
                "SELECT id FROM jobs WHERE id=%s AND worker_id=%s AND generation=%s AND status='leased' AND lease_until>clock_timestamp()",
                (job["id"], job["worker_id"], job["generation"]),
            ).fetchone():
                raise Conflict("stale worker cannot write artifact")
            db.execute(
                "INSERT INTO artifacts(id,project_id,job_id,name,media_type,bytes,sha256,metadata) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    artifact,
                    job["project_id"],
                    job["id"],
                    name,
                    media_type,
                    0,
                    "",
                    Jsonb(metadata or {}),
                ),
            )
            if prepared:
                blob_id = self.blobs.attach(db, prepared)
                self.fence(db, job)
                return db.execute(
                    "UPDATE artifacts SET bytes=%s,sha256=%s,blob_id=%s WHERE id=%s RETURNING *",
                    (prepared["bytes"], prepared["sha256"], blob_id, artifact),
                ).fetchone()
            digest, size = hashlib.sha256(), 0
            with db.cursor() as cp:
                for ordinal, chunk in enumerate(chunks):
                    if not isinstance(chunk, bytes) or not 0 < len(chunk) <= CHUNK_BYTES:
                        raise ValueError("artifact chunks must be nonempty bounded bytes")
                    cp.execute(
                        "INSERT INTO artifact_chunks VALUES(%s,%s,%s,%s)",
                        (job["project_id"], artifact, ordinal, chunk),
                    )
                    digest.update(chunk)
                    size += len(chunk)
            self.fence(db, job)
            return db.execute(
                "UPDATE artifacts SET bytes=%s,sha256=%s WHERE id=%s RETURNING *", (size, digest.hexdigest(), artifact)
            ).fetchone()
