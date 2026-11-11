"""One PostgreSQL commit owns the population, physical world and every brain."""

from uuid import UUID, uuid4, uuid5

from psycopg.types.json import Jsonb

from threemind_runtime.cold_state import FrozenCore, StateReference
from threemind_runtime.world_schema import digest

from . import development
from .database import Conflict, NotFound


def campaign(db, identity, *, lock=False):
    row = db.execute(
        "SELECT *,revision-checkpoint_revision AS control_revision FROM ecology_campaigns WHERE id=%s"
        + (" FOR UPDATE" if lock else ""),
        (identity,),
    ).fetchone()
    if row is None:
        raise NotFound()
    return row


def run_id(identity, individual):
    return uuid5(UUID(str(identity)), f"ecological-individual:{individual}")


def validate(db, protocol, maximum):
    source = development._version(db, protocol.initial_version_id) if protocol.initial_version_id else None
    return protocol.model_dump(mode="json") | {"base": development.validate_spec(protocol.base, source, maximum)}


def create(database, project, actor, request, maximum):
    with database.tx(project) as db:
        previous, request_hash = development._retry(db, "ecology_campaigns", project, actor, request)
        if previous:
            return previous
        protocol = validate(db, request.protocol, maximum)
        identity, job_id = uuid4(), uuid4()
        db.execute(
            "INSERT INTO jobs(id,project_id,kind,params) VALUES(%s,%s,'ecology',%s)",
            (job_id, project, Jsonb({"campaign_id": str(identity), "base": protocol["base"]})),
        )
        row = db.execute(
            "INSERT INTO ecology_campaigns(id,project_id,actor_id,operation_id,request_hash,name,objective,protocol,protocol_hash,initial_version_id,job_id) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                identity,
                project,
                actor,
                request.operation_id,
                request_hash,
                request.name,
                request.objective,
                Jsonb(protocol),
                digest(protocol),
                request.protocol.initial_version_id,
                job_id,
            ),
        ).fetchone()
        from .native_records import register_execution
        register_execution(database, db, project, {'id': actor}, 'ecology', identity, request.name, protocol,
                           executor=request.record_executor, classification=request.record_classification,
                           question=request.objective)
        return row


def summary(runtime):
    accounts = list(runtime.ledger.accounts.values())
    return {
        "individuals": len(accounts),
        "living_bodies": sum(a.alive for a in accounts),
        "viable_cores": sum(p.engine.life != "dead" for p in runtime.participants.values()),
        "births": len(accounts) - runtime.settings.founder_count,
        "maximum_generation": max(a.generation for a in accounts),
        "body_failures": sum(not a.alive for a in accounts),
        "model_time_us": str(runtime.time_us),
        "physical_time_us": str(runtime.world.time_us),
        "pending_delivery_us": str(runtime.pending_end_us) if runtime.pending_end_us is not None else None,
        "resource_balance": runtime.ledger.check_balance(),
        "deferred_population": runtime.ledger.deferred_population,
        "deferred_budget": runtime.ledger.deferred_budget,
    }


class PopulationWriter:
    def __init__(self, database, project, row, *, job=None, implementation=None):
        self.database, self.project, self.row, self.job = database, project, row, job
        self.implementation = implementation or {}
        self.previous = {}
        self.events, self.member_events, self.observations = [], {}, {}
        self.spike_bytes = 0

    def record(self, event):
        self.events.append(event)

    def member_record(self, identity, event):
        if event["kind"] == "spikes":
            self.spike_bytes += 200 + 12 * len(event["payload"]["nodes"])
            if self.spike_bytes > 64 * 1024**2:
                raise ValueError("单个种群推进片段的脉冲记录超过 64 MiB；请减少规模或显式关闭脉冲记录。")
        if event["kind"] == "metric_sample":
            self.observations.setdefault(identity, []).append(event["payload"])
        else:
            self.member_events.setdefault(identity, []).append(event)

    def load(self):
        if self.row["checkpoint_id"] is None:
            return None
        with self.database.tx(self.project, repeatable=True) as db:
            cp = db.execute(
                "SELECT * FROM ecology_checkpoints WHERE id=%s AND campaign_id=%s",
                (self.row["checkpoint_id"], self.row["id"]),
            ).fetchone()
            if cp is None:
                raise ValueError("population manifest is missing")
            members = db.execute(
                "SELECT * FROM ecology_checkpoint_members WHERE population_checkpoint_id=%s ORDER BY individual",
                (cp["id"],),
            ).fetchall()
        images = {}
        for member in members:
            if member["outcome"]["core_life"] == "dead" and not member["outcome"]["alive"]:
                with self.database.tx(self.project) as db:
                    brain_cp = db.execute(
                        "SELECT * FROM checkpoints WHERE id=%s AND run_id=%s",
                        (member["checkpoint_id"], member["run_id"]),
                    ).fetchone()
                if brain_cp is None or brain_cp["state_hash"] != member["state_hash"]:
                    raise ValueError("archived population member checkpoint mismatch")
                images[member["individual"]] = self.state_reference(member["run_id"], brain_cp)
                self.previous[member["individual"]] = (brain_cp, None)
                continue
            brain_cp, image = self.database.load_checkpoint(self.project, member["run_id"], member["checkpoint_id"])
            if image.digest != member["state_hash"]:
                raise ValueError("population manifest brain checksum mismatch")
            images[member["individual"]] = image
            self.previous[member["individual"]] = (brain_cp, image.to_dict())
        if cp["context"].get("checkpoint_hash") != cp["state_hash"]:
            raise ValueError("population manifest checksum mismatch")
        return cp["context"], images

    def state_reference(self, subject, checkpoint):
        database, project, identity = self.database, self.project, checkpoint["id"]
        return StateReference(checkpoint["state_hash"], lambda: database.load_checkpoint(project, subject, identity)[1])

    def commit(self, runtime, *, status="active", operation_id=None, finish=False):
        """Synchronous backpressure; buffers clear only after the outer commit succeeds."""
        operation_id = operation_id or uuid4()
        saved, identity = {}, uuid4()
        with self.database.tx(self.project) as db:
            self.database.fence(db, self.job)
            row = campaign(db, self.row["id"], lock=True)
            if finish:
                # Control acceptance and final readout closure share the same
                # lock. An acknowledged pause cannot lose a race to completion.
                status = (
                    "cancelled"
                    if row["requested_action"] == "cancel"
                    else "paused"
                    if row["requested_action"] == "pause"
                    else status
                )
                for agent in runtime.participants.values():
                    agent.inputs.interrupt_capture(status)
                    if status != "paused":
                        agent.readouts.observe(agent.engine, force=True)
                        agent.readouts.close(
                            agent.engine.time_us, "cancelled" if status == "cancelled" else "run_ended"
                        )
                    agent.organs.observe(agent.engine, final=status != "paused")
            metadata, images = runtime.checkpoint()
            observation = runtime.world.observation()
            observed = summary(runtime)
            observation["population"] = observed
            changes = {key: agent.inputs.changes for key, agent in runtime.participants.items()}
            fingerprint = digest(
                {
                    "metadata": metadata,
                    "status": status,
                    "events": self.events,
                    "member_events": self.member_events,
                    "observations": self.observations,
                    "inputs": changes,
                }
            )
            retry = db.execute(
                "SELECT * FROM ecology_checkpoints WHERE campaign_id=%s AND operation_id=%s", (row["id"], operation_id)
            ).fetchone()
            if retry:
                if retry["fingerprint"] != fingerprint or row["checkpoint_id"] != retry["id"]:
                    raise Conflict("population checkpoint retry differs from its committed operation")
                committed = row
                for key in images:
                    saved[key] = db.execute(
                        "SELECT c.* FROM checkpoints c JOIN ecology_checkpoint_members m ON m.checkpoint_id=c.id WHERE m.population_checkpoint_id=%s AND m.individual=%s",
                        (retry["id"], key),
                    ).fetchone()
            else:
                if (
                    row["checkpoint_id"] != self.row["checkpoint_id"]
                    or row["checkpoint_revision"] != self.row["checkpoint_revision"]
                ):
                    raise Conflict("population checkpoint changed; restore the complete group")
                if row["status"] != "active":
                    raise Conflict("ecological campaign is no longer active")
                db.execute(
                    "INSERT INTO ecology_checkpoints(id,project_id,campaign_id,revision,previous_id,operation_id,fingerprint,state_hash,time_us,context,observation,status) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        identity,
                        self.project,
                        row["id"],
                        row["checkpoint_revision"] + 1,
                        row["checkpoint_id"],
                        operation_id,
                        fingerprint,
                        metadata["checkpoint_hash"],
                        runtime.time_us,
                        Jsonb(metadata),
                        Jsonb(observation),
                        status,
                    ),
                )
                source = development._version(db, row["initial_version_id"]) if row["initial_version_id"] else None
                born = {
                    event["individual"]: event
                    for event in self.events
                    if event["kind"] in ("founder_born", "individual_born")
                }
                for key in sorted(images, key=lambda k: int(k[1:])):
                    agent, account, image = runtime.participants[key], runtime.ledger.accounts[key], images[key]
                    subject = run_id(row["id"], key)
                    previous = self.previous.get(key)
                    if previous is None:
                        birth = born.get(key)
                        if birth is None or birth["state_hash"] != image.digest or agent.engine.time_us != 0:
                            raise ValueError("each birth must be committed before the newborn receives experience")
                        parent_cp = saved[account.parent_id] if account.parent_id else None
                        if parent_cp and parent_cp["state_hash"] != birth["source_state_hash"]:
                            raise ValueError("parent checkpoint must be the actual inherited state")
                        origin = parent_cp["id"] if parent_cp else source["checkpoint_id"] if source else None
                        parent_run = (
                            run_id(row["id"], account.parent_id)
                            if account.parent_id
                            else source["run_id"]
                            if source
                            else None
                        )
                        db.execute(
                            "INSERT INTO runs(id,project_id,name,spec,parent_id,origin_hash,origin_checkpoint_id,origin_kind) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                            (
                                subject,
                                self.project,
                                f"{row['name'][:90]} · {key}",
                                Jsonb(row["protocol"]["base"]),
                                parent_run,
                                birth["source_state_hash"],
                                origin,
                                "inherited" if parent_run else "created",
                            ),
                        )
                        db.execute(
                            "INSERT INTO ecology_members(project_id,campaign_id,individual,run_id,parent,generation,birth_us,birth_hash,source_hash,source_checkpoint_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                            (
                                self.project,
                                row["id"],
                                key,
                                subject,
                                account.parent_id,
                                account.generation,
                                account.birth_us,
                                birth["state_hash"],
                                birth["source_state_hash"],
                                origin,
                            ),
                        )
                    member_status = (
                        "dead" if agent.engine.life == "dead" else "running" if status == "active" else status
                    )
                    context = {
                        "protocol": row["protocol"]["base"],
                        "ecological_campaign_id": str(row["id"]),
                        "population_checkpoint_id": str(identity),
                        "birth_us": str(account.birth_us),
                        "individual": key,
                        "participant": metadata["members"][key]["context"],
                        "implementation": self.implementation,
                        "backend": self.implementation.get("backend"),
                    }
                    measured = list(self.observations.get(key, []))
                    metric = agent.metrics()
                    if measured and measured[-1]["time_us"] == metric["time_us"]:
                        measured[-1] = metric
                    else:
                        measured.append(metric)
                    unchanged_archive = (
                        isinstance(agent.engine, FrozenCore)
                        and previous is not None
                        and previous[0]["state_hash"] == image.digest
                        and previous[0]["context"].get("participant") == context["participant"]
                        and not self.member_events.get(key)
                        and not self.observations.get(key)
                        and not any(changes[key].values())
                    )
                    if unchanged_archive:
                        saved[key] = previous[0]
                    else:
                        # A late final readout may update evidence without changing
                        # the dead brain. Materialize at most this member's baseline.
                        if previous is not None and previous[1] is None:
                            previous = (previous[0], image.to_dict())
                        saved[key] = self.database.save_checkpoint(
                            self.project,
                            subject,
                            image,
                            expected_revision=previous[0]["revision"] if previous else 0,
                            previous=previous,
                            context=context,
                            status=member_status,
                            job=None,  # The owner row remains locked by the outer fence.
                            transaction=db,
                            observations=measured,
                            events=self.member_events.get(key, []),
                            input_changes=changes[key],
                            last_command=agent.last_command,
                        )
                    db.execute(
                        "INSERT INTO ecology_checkpoint_members(project_id,campaign_id,population_checkpoint_id,individual,run_id,checkpoint_id,state_hash,outcome) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            self.project,
                            row["id"],
                            identity,
                            key,
                            subject,
                            saved[key]["id"],
                            image.digest,
                            Jsonb(
                                account.model_dump(mode="json")
                                | {
                                    "metrics": metric,
                                    "core_life": agent.engine.life,
                                    "core_time_us": str(agent.engine.time_us),
                                    "observed_age_us": str(runtime.time_us - account.birth_us),
                                }
                            ),
                        ),
                    )
                for index, event in enumerate(self.events):
                    db.execute(
                        "INSERT INTO ecology_events(project_id,campaign_id,population_checkpoint_id,event_index,time_us,individual,kind,payload) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            self.project,
                            row["id"],
                            identity,
                            index,
                            event["time_us"],
                            event.get("individual"),
                            event["kind"],
                            Jsonb(event),
                        ),
                    )
                committed = db.execute(
                    "UPDATE ecology_campaigns SET checkpoint_id=%s,checkpoint_revision=checkpoint_revision+1,revision=revision+1,time_us=%s,summary=%s,status=%s,error=NULL,requested_action=CASE WHEN %s='active' THEN requested_action ELSE NULL END,updated_at=clock_timestamp() WHERE id=%s RETURNING *",
                    (identity, runtime.time_us, Jsonb(observed), status, status, row["id"]),
                ).fetchone()
                db.execute("SELECT pg_notify('threemind_changes',%s)", (str(self.project),))
            if self.job is not None:
                # The outer job lock prevents takeover while multiple models
                # are copied. Refresh before releasing that ownership lock.
                db.execute(
                    "UPDATE jobs SET lease_until=clock_timestamp()+interval '60 seconds' WHERE id=%s", (self.job["id"],)
                )
        self.row = committed
        next_previous = {}
        for key, agent in runtime.participants.items():
            if not agent.body_enabled and agent.engine.life == "dead" and agent.dead_recorded:
                agent.archive_engine(self.state_reference(run_id(self.row["id"], key), saved[key]))
                next_previous[key] = (saved[key], None)
            else:
                next_previous[key] = (saved[key], images[key].to_dict())
        self.previous = next_previous
        self.events, self.member_events, self.observations = [], {}, {}
        self.spike_bytes = 0
        for agent in runtime.participants.values():
            agent.inputs.take_changes()
            agent.force_checkpoint = False
            agent.readouts.bytes = 0
        return committed


def control(database, project, identity, actor, action, expected_revision):
    with database.tx(project) as db:
        preview = campaign(db, identity)
        job = db.execute("SELECT * FROM jobs WHERE id=%s FOR UPDATE", (preview["job_id"],)).fetchone()
        row = campaign(db, identity, lock=True)
        if row["control_revision"] != expected_revision:
            raise Conflict("生态训练已更新，请刷新后再操作。")
        leased = job["status"] == "leased"
        if action in ("pause", "cancel"):
            if row["status"] not in ("active", "paused", "blocked") or row["status"] != "active" and action == "pause":
                raise Conflict("当前生态训练不能执行该控制。")
            status = row["status"] if leased else "paused" if action == "pause" else "cancelled"
            if not leased:
                db.execute("UPDATE jobs SET status='done',lease_until=NULL WHERE id=%s", (job["id"],))
                db.execute(
                    "UPDATE runs SET status=%s,updated_at=clock_timestamp() WHERE id IN (SELECT run_id FROM ecology_members WHERE campaign_id=%s) AND life<>'dead'",
                    (status, identity),
                )
            result = db.execute(
                "UPDATE ecology_campaigns SET requested_action=%s,status=%s,revision=revision+1,updated_at=clock_timestamp() WHERE id=%s RETURNING *",
                (action if leased else None, status, identity),
            ).fetchone()
        elif action in ("resume", "retry"):
            required = "paused" if action == "resume" else "blocked"
            if row["status"] != required or job["status"] in ("pending", "leased"):
                raise Conflict("请等待种群完成暂停；只有暂停可继续，失败阻塞可重试。")
            db.execute(
                "UPDATE jobs SET status='pending',attempts=0,error=NULL,result=NULL,lease_until=NULL,params=params||%s WHERE id=%s",
                (Jsonb({"campaign_id": str(identity)}), job["id"]),
            )
            result = db.execute(
                "UPDATE ecology_campaigns SET status='active',requested_action=NULL,error=NULL,revision=revision+1,updated_at=clock_timestamp() WHERE id=%s RETURNING *",
                (identity,),
            ).fetchone()
        else:
            raise ValueError("unknown ecological control")
        db.execute(
            "INSERT INTO audit(user_id,action,resource) VALUES(%s,%s,%s)", (actor, f"ecology.{action}", str(identity))
        )
        return result


def job_failed(db, job, error):
    if job["kind"] != "ecology":
        return
    row = db.execute(
        "UPDATE ecology_campaigns SET status='blocked',requested_action=NULL,error=%s,revision=revision+1,updated_at=clock_timestamp() WHERE job_id=%s AND status='active' RETURNING id",
        (error, job["id"]),
    ).fetchone()
    if row:
        db.execute(
            "UPDATE runs SET status='blocked',error=%s WHERE id IN (SELECT run_id FROM ecology_members WHERE campaign_id=%s) AND life<>'dead'",
            (error, row["id"]),
        )
