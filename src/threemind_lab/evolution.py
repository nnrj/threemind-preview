"""Durable generational coordination; only child run jobs execute a brain.

The coordinator yields its lease behind the existing job barrier while children
work. A child completion wakes it in the same database transaction. No polling
job, external queue, in-memory campaign state or graph rewriting is required.
"""

from uuid import UUID, uuid4, uuid5

from psycopg.types.json import Jsonb

from . import development
from .database import Conflict, NotFound
from .evolution_protocol import EvolutionProtocol, endpoints, rank_candidates


def _campaign(db, identity, *, lock=False, summary=False):
    columns = (
        "id,project_id,name,objective,status,phase,generation,wave,revision,error,protocol_hash,created_at,updated_at,"
        "jsonb_build_object('generations',protocol->'generations','population_size',protocol->'population_size',"
        "'survivor_count',protocol->'survivor_count','criteria',protocol->'criteria') AS summary"
        if summary
        else "*"
    )
    row = db.execute(
        f"SELECT {columns} FROM evolution_campaigns WHERE id=%s" + (" FOR UPDATE" if lock else ""), (identity,)
    ).fetchone()
    if row is None:
        raise NotFound()
    return row


def _event(db, campaign, kind, payload):
    campaign["revision"] += 1
    db.execute(
        "UPDATE evolution_campaigns SET revision=%s,updated_at=clock_timestamp() WHERE id=%s",
        (campaign["revision"], campaign["id"]),
    )
    db.execute(
        "INSERT INTO evolution_events(project_id,campaign_id,revision,kind,payload) VALUES(%s,%s,%s,%s,%s)",
        (campaign["project_id"], campaign["id"], campaign["revision"], kind, Jsonb(payload)),
    )


def create(database, project, actor, request, max_seconds):
    with database.tx(project) as db:
        previous, request_hash = development._retry(db, "evolution_campaigns", project, actor, request)
        if previous:
            return previous
        declared = request.protocol
        source = development._version(db, declared.initial_version_id) if declared.initial_version_id else None
        protocol = declared.model_dump(mode="json")
        protocol["development"] = development.validate_spec(declared.development, source, max_seconds)
        protocol["evaluation"] = development.validate_spec(declared.evaluation, source, max_seconds)
        identity, job_id = uuid4(), uuid4()
        db.execute(
            "INSERT INTO jobs(id,project_id,kind,params) VALUES(%s,%s,'evolution',%s)",
            (
                job_id,
                project,
                Jsonb({"campaign_id": str(identity), "barrier_id": str(identity), "barrier_ready": True}),
            ),
        )
        row = db.execute(
            "INSERT INTO evolution_campaigns(id,project_id,actor_id,operation_id,request_hash,name,objective,protocol,protocol_hash,job_id) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                identity,
                project,
                actor,
                request.operation_id,
                request_hash,
                request.name,
                request.objective,
                Jsonb(protocol),
                development.digest(protocol),
                job_id,
            ),
        ).fetchone()
        _event(db, row, "created", {"protocol_hash": row["protocol_hash"], "selection_mode": "directed"})
        from .native_records import register_execution
        register_execution(database, db, project, {'id': actor}, 'evolution', identity, request.name, protocol,
                           executor=request.record_executor, classification=request.record_classification,
                           question=request.objective)
        return row


def _spawn(db, campaign, protocol, stage, slots):
    """Commit an entire declared wave and its run jobs together."""
    wave = campaign["wave"] + 1
    generation = campaign["generation"]
    source_spec = protocol.development if stage == "development" else protocol.evaluation
    seeds = (
        None
        if stage == "development"
        else protocol.evaluation_seeds
        if stage == "evaluation"
        else protocol.verification_seeds
    )
    count = 0
    for slot, source_version in slots:
        slot_seeds = [protocol.development_seeds[generation][slot]] if seeds is None else seeds
        for block, seed in enumerate(slot_seeds):
            member_id = uuid5(UUID(str(campaign["id"])), f"{generation}:{stage}:{slot}:{block}")
            name = f"{campaign['name'][:70]} · {generation + 1}/{slot + 1} · {stage} {block + 1}"
            request = development.DevelopmentRequest(
                operation_id=member_id,
                name=name,
                objective=campaign["objective"],
                source_version_id=source_version,
                spec=source_spec.model_copy(update={"environment_seed": seed}),
            )
            session = development.create_in(db, campaign["project_id"], campaign["actor_id"], request, 86400)
            db.execute(
                "INSERT INTO evolution_members(id,project_id,campaign_id,generation,wave,slot,stage,block_index,"
                "environment_seed,run_id,source_version_id,candidate_version_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    member_id,
                    campaign["project_id"],
                    campaign["id"],
                    generation,
                    wave,
                    slot,
                    stage,
                    block,
                    seed,
                    session["run_id"],
                    source_version,
                    source_version if stage != "development" else None,
                ),
            )
            # The membership now exists, so every child lease includes the new
            # capability and its completion can safely wake the coordinator.
            db.execute(
                "UPDATE jobs SET params=params||%s WHERE run_id=%s AND kind='run' AND status='pending'",
                (Jsonb({"evolution_id": str(campaign["id"])}), session["run_id"]),
            )
            count += 1
    db.execute("UPDATE evolution_campaigns SET wave=%s,phase=%s WHERE id=%s", (wave, stage, campaign["id"]))
    campaign.update(wave=wave, phase=stage)
    _event(db, campaign, "wave_started", {"generation": generation, "stage": stage, "wave": wave, "individuals": count})


def _birth_generation(db, campaign, protocol):
    parents = [protocol.initial_version_id]
    if campaign["generation"]:
        parents = [
            row["candidate_version_id"]
            for row in db.execute(
                "SELECT candidate_version_id FROM evolution_selections WHERE campaign_id=%s AND generation=%s AND selected ORDER BY rank",
                (campaign["id"], campaign["generation"] - 1),
            ).fetchall()
        ]
        if len(parents) != protocol.survivor_count:
            raise ValueError("上一代父本选择记录不完整。")
    # Equal, cyclic allocation among explicitly selected parents. Rank is not
    # silently converted into a second, undocumented reproduction weighting.
    _spawn(
        db, campaign, protocol, "development", [(i, parents[i % len(parents)]) for i in range(protocol.population_size)]
    )


def _wave(db, campaign):
    return db.execute(
        "SELECT m.*,r.status AS run_status,r.metrics,r.life,r.time_us,r.revision AS run_revision,r.state_hash AS run_hash,"
        "EXISTS(SELECT 1 FROM jobs j WHERE j.run_id=m.run_id AND j.kind='run' AND j.status IN ('pending','leased')) AS working "
        "FROM evolution_members m JOIN runs r ON r.id=m.run_id WHERE m.campaign_id=%s AND m.wave=%s ORDER BY m.slot,m.block_index",
        (campaign["id"], campaign["wave"]),
    ).fetchall()


def _pin(db, campaign, member, protocol):
    cp = db.execute(
        "SELECT id,state_hash FROM checkpoints WHERE run_id=%s AND revision=%s AND state_hash=%s",
        (member["run_id"], member["run_revision"], member["run_hash"]),
    ).fetchone()
    if cp is None:
        raise ValueError("个体缺少与最终状态一致的恢复点，不能猜测或重新执行评分。")
    version_id = member["candidate_version_id"]
    if member["stage"] == "development":
        request = development.RegistrationRequest(
            operation_id=member["id"],
            name=f"{campaign['name'][:80]} · G{campaign['generation'] + 1} / {member['slot'] + 1}",
            selection_note="多代发育候选登记；是否成为父本由单独的筛选记录确定。",
            run_id=member["run_id"],
            checkpoint_id=cp["id"],
            expected_state_hash=cp["state_hash"],
        )
        version_id = development.register_in(db, campaign["project_id"], campaign["actor_id"], request)["id"]
        outcome = {"life": member["life"], "time_us": str(member["time_us"])}
    else:
        outcome = endpoints(member, protocol.criteria)
    outcome["metrics"] = member["metrics"]
    db.execute(
        "UPDATE evolution_members SET candidate_version_id=%s,checkpoint_id=%s,state_hash=%s,outcome=%s WHERE id=%s",
        (version_id, cp["id"], cp["state_hash"], Jsonb(outcome), member["id"]),
    )
    return member | {
        "candidate_version_id": version_id,
        "checkpoint_id": cp["id"],
        "state_hash": cp["state_hash"],
        "outcome": outcome,
    }


def _select(db, campaign, protocol, members):
    rows = []
    for slot in range(protocol.population_size):
        blocks = [member for member in members if member["slot"] == slot]
        if len(blocks) != len(protocol.evaluation_seeds) or len({str(m["source_version_id"]) for m in blocks}) != 1:
            raise ValueError("候选的筛选环境或父本身份不完整。")
        rows.append(
            {
                "slot": slot,
                "candidate_version_id": str(blocks[0]["source_version_id"]),
                "blocks": [
                    m["outcome"]
                    | {
                        "run_id": str(m["run_id"]),
                        "checkpoint_id": str(m["checkpoint_id"]),
                        "state_hash": m["state_hash"],
                        "environment_seed": m["environment_seed"],
                        "block_index": m["block_index"],
                    }
                    for m in blocks
                ],
            }
        )
    ranked = rank_candidates(rows, protocol.criteria)
    for row in ranked:
        db.execute(
            "INSERT INTO evolution_selections(project_id,campaign_id,generation,slot,candidate_version_id,rank,selected,scores,evidence) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                campaign["project_id"],
                campaign["id"],
                campaign["generation"],
                row["slot"],
                row["candidate_version_id"],
                row["rank"],
                row["rank"] <= protocol.survivor_count,
                Jsonb(row["scores"]),
                Jsonb({"blocks": row["blocks"], "tie_break": "declared-slot-ascending", "objectives": "lexicographic"}),
            ),
        )
    _event(
        db,
        campaign,
        "parents_selected",
        {
            "generation": campaign["generation"],
            "selected_slots": [r["slot"] for r in ranked[: protocol.survivor_count]],
            "selection_hash": development.digest(ranked),
            "evaluation_learning_inherited": False,
        },
    )


def _drive(db, campaign, protocol):
    if campaign["phase"] == "birth":
        _birth_generation(db, campaign, protocol)
        return
    members = _wave(db, campaign)
    expected = protocol.population_size * (
        1
        if campaign["phase"] == "development"
        else len(protocol.evaluation_seeds)
        if campaign["phase"] == "evaluation"
        else len(protocol.verification_seeds)
    )
    if len(members) != expected:
        raise ValueError("本批次个体记录不完整；协调器不会补造证据。")
    if any(m["working"] for m in members):
        return
    if any(m["run_status"] == "paused" for m in members):
        db.execute("UPDATE evolution_campaigns SET status='paused' WHERE id=%s", (campaign["id"],))
        campaign["status"] = "paused"
        _event(db, campaign, "member_paused", {"generation": campaign["generation"], "stage": campaign["phase"]})
        return
    if any(m["run_status"] not in ("completed", "dead") for m in members):
        raise ValueError("存在失败、取消或异常停止的个体；请检查来源运行，不能把失败替换为零分。")
    members = [
        _pin(db, campaign, member, protocol) if member["checkpoint_id"] is None else member for member in members
    ]
    if campaign["phase"] == "development":
        _spawn(db, campaign, protocol, "evaluation", [(m["slot"], m["candidate_version_id"]) for m in members])
    elif campaign["phase"] == "evaluation":
        _select(db, campaign, protocol, members)
        if campaign["generation"] + 1 < protocol.generations:
            campaign["generation"] += 1
            db.execute(
                "UPDATE evolution_campaigns SET generation=%s WHERE id=%s", (campaign["generation"], campaign["id"])
            )
            _birth_generation(db, campaign, protocol)
        else:
            candidates = db.execute(
                "SELECT slot,candidate_version_id FROM evolution_selections WHERE campaign_id=%s AND generation=%s ORDER BY slot",
                (campaign["id"], campaign["generation"]),
            ).fetchall()
            _spawn(db, campaign, protocol, "verification", [(m["slot"], m["candidate_version_id"]) for m in candidates])
    elif campaign["phase"] == "verification":
        db.execute("UPDATE evolution_campaigns SET status='completed',phase='complete' WHERE id=%s", (campaign["id"],))
        campaign.update(status="completed", phase="complete")
        _event(
            db,
            campaign,
            "completed",
            {
                "generations": protocol.generations,
                "verification_runs": len(members),
                "verification_used_for_selection": False,
            },
        )


def execute(worker, job):
    """Own finalization too, so an acknowledged pause cannot race a later finish."""
    with worker.db.tx(job["project_id"]) as db:
        worker.db.fence(db, job)
        campaign = _campaign(db, job["params"]["campaign_id"], lock=True)
        if campaign["status"] == "active":
            try:
                with db.transaction():
                    _drive(db, campaign, EvolutionProtocol(**campaign["protocol"]))
            except (ValueError, OverflowError) as exc:
                # Roll back the whole wave, including any child created before
                # the validation failure; persist only a diagnosable stop.
                campaign = _campaign(db, campaign["id"], lock=True)
                error = str(exc)[:2000]
                db.execute(
                    "UPDATE evolution_campaigns SET status='blocked',error=%s WHERE id=%s", (error, campaign["id"])
                )
                campaign.update(status="blocked", error=error)
                _event(db, campaign, "blocked", {"reason": error})
        terminal = campaign["status"] in ("completed", "cancelled")
        db.execute(
            "UPDATE jobs SET status=%s,worker_id=NULL,lease_until=NULL,attempts=0,"
            "params=jsonb_set(params,'{barrier_ready}','false'),result=%s WHERE id=%s",
            (
                "done" if terminal else "pending",
                Jsonb({"campaign_id": str(campaign["id"]), "status": campaign["status"]}),
                job["id"],
            ),
        )


def child_finished(db, job):
    """Called inside the ordinary child completion transaction, after its status."""
    if job["kind"] != "run":
        return
    row = db.execute(
        "SELECT c.id,c.job_id,c.wave FROM evolution_members m JOIN evolution_campaigns c ON c.id=m.campaign_id "
        "WHERE m.run_id=%s AND m.wave=c.wave",
        (job["run_id"],),
    ).fetchone()
    if row is None:
        return
    # Serialize the final-completion check. Otherwise two completing workers
    # can each see the other's uncommitted lease and both omit the wakeup.
    db.execute("SELECT id FROM jobs WHERE id=%s FOR UPDATE", (row["job_id"],))
    current = db.execute("SELECT status,wave FROM evolution_campaigns WHERE id=%s", (row["id"],)).fetchone()
    if current["status"] == "cancelled":
        _settle_cancel(db, row["id"], job["run_id"])
        return
    if current["status"] != "active" or current["wave"] != row["wave"]:
        return
    if not db.execute(
        "SELECT 1 FROM evolution_members m JOIN jobs j ON j.run_id=m.run_id AND j.kind='run' "
        "WHERE m.campaign_id=%s AND m.wave=%s AND j.status IN ('pending','leased') LIMIT 1",
        (row["id"], row["wave"]),
    ).fetchone():
        db.execute(
            "UPDATE jobs SET params=jsonb_set(params,'{barrier_ready}','true') WHERE id=%s AND status='pending'",
            (row["job_id"],),
        )


def _settle_cancel(db, campaign_id, run_id):
    run = db.execute("SELECT status,last_command FROM runs WHERE id=%s FOR UPDATE", (run_id,)).fetchone()
    if run["status"] not in ("paused", "blocked", "failed"):
        return
    command = db.execute(
        "SELECT id,payload FROM commands WHERE run_id=%s AND kind='cancel' AND payload->>'evolution_id'=%s ORDER BY id DESC LIMIT 1",
        (run_id, str(campaign_id)),
    ).fetchone()
    if command is None:
        return
    db.execute(
        "UPDATE runs SET status='cancelled',last_command=%s,updated_at=clock_timestamp() WHERE id=%s",
        (command["id"], run_id),
    )
    db.execute(
        "INSERT INTO events(project_id,run_id,event_key,time_us,kind,payload) SELECT project_id,id,%s,time_us,'cancel',%s FROM runs WHERE id=%s "
        "ON CONFLICT(run_id,event_key) DO NOTHING",
        (f"command:{command['id']}", Jsonb(command["payload"]), run_id),
    )


def job_failed(db, job, error):
    if job["kind"] != "evolution":
        return
    campaign = db.execute("SELECT * FROM evolution_campaigns WHERE job_id=%s FOR UPDATE", (job["id"],)).fetchone()
    if campaign and campaign["status"] == "active":
        db.execute("UPDATE evolution_campaigns SET status='blocked',error=%s WHERE id=%s", (error, campaign["id"]))
        _event(db, campaign, "coordinator_failed", {"reason": error})


def control(database, project, identity, actor, action, expected_revision):
    with database.tx(project) as db:
        campaign = _campaign(db, identity)
        # Same order as execute: coordinator lease row, then campaign row.
        db.execute("SELECT id FROM jobs WHERE id=%s FOR UPDATE", (campaign["job_id"],))
        campaign = _campaign(db, identity, lock=True)
        if campaign["revision"] != expected_revision:
            raise Conflict("演化状态已更新，请刷新后重新操作。")
        if campaign["status"] in ("completed", "cancelled"):
            raise Conflict("该多代实验已经结束；请从明确的先天版本创建新实验。")
        members = _wave(db, campaign) if campaign["wave"] else []
        if action in ("pause", "cancel"):
            status = "paused" if action == "pause" else "cancelled"
            for member in members:
                if (
                    member["run_status"] in ("queued", "running")
                    or action == "cancel"
                    and member["run_status"] in ("paused", "blocked", "failed")
                ):
                    db.execute(
                        "INSERT INTO commands(project_id,run_id,kind,payload) VALUES(%s,%s,%s,%s)",
                        (
                            project,
                            member["run_id"],
                            action,
                            Jsonb({"evolution_id": str(identity), "actor_id": str(actor)}),
                        ),
                    )
                    if action == "cancel" and not member["working"]:
                        _settle_cancel(db, identity, member["run_id"])
            db.execute("UPDATE evolution_campaigns SET status=%s,error=NULL WHERE id=%s", (status, identity))
            db.execute(
                "UPDATE jobs SET status=%s,worker_id=NULL,lease_until=NULL,params=jsonb_set(params,'{barrier_ready}','false') WHERE id=%s",
                ("done" if action == "cancel" else "pending", campaign["job_id"]),
            )
        elif action in ("resume", "retry"):
            if campaign["status"] not in ("paused", "blocked"):
                raise Conflict("只能继续已暂停或明确重试已阻塞的实验。")
            if any(m["working"] for m in members):
                raise Conflict("个体任务仍在提交停止状态，请稍后再继续。")
            if any(m["run_status"] == "cancelled" for m in members):
                raise Conflict("个体已经取消，不能当作可精确继续的样本；请创建新实验。")
            for member in members:
                if member["run_status"] in ("paused", "blocked", "failed"):
                    if member["run_status"] != "paused" and action != "retry":
                        raise Conflict("存在失败个体，需要明确选择重试，并检查错误原因。")
                    db.execute("UPDATE runs SET status='queued',error=NULL WHERE id=%s", (member["run_id"],))
                    db.execute(
                        "INSERT INTO jobs(id,project_id,run_id,kind) VALUES(%s,%s,%s,'run')",
                        (uuid4(), project, member["run_id"]),
                    )
            db.execute("UPDATE evolution_campaigns SET status='active',error=NULL WHERE id=%s", (identity,))
            db.execute(
                "UPDATE jobs SET status='pending',worker_id=NULL,lease_until=NULL,attempts=0,error=NULL,"
                "params=jsonb_set(params,'{barrier_ready}','true') WHERE id=%s",
                (campaign["job_id"],),
            )
        else:
            raise ValueError("unknown evolution control")
        _event(
            db,
            campaign,
            action,
            {"actor_id": str(actor), "generation": campaign["generation"], "stage": campaign["phase"]},
        )
        return _campaign(db, identity)


def listing(database, project, query="", offset=0):
    with database.tx(project) as db:
        rows = db.execute(
            "SELECT id,name,objective,status,phase,generation,wave,revision,error,protocol_hash,created_at,updated_at,"
            "jsonb_build_object('generations',protocol->'generations','population_size',protocol->'population_size',"
            "'survivor_count',protocol->'survivor_count') AS summary FROM evolution_campaigns "
            "WHERE name ILIKE %s ORDER BY created_at DESC,id DESC LIMIT 31 OFFSET %s",
            (f"%{query}%", offset),
        ).fetchall()
        return {"rows": rows[:30], "more": len(rows) > 30, "offset": offset}


def detail(database, project, identity, generation=None, offset=0, stage=None):
    with database.tx(project) as db:
        campaign = _campaign(db, identity, summary=True)
        generation = campaign["generation"] if generation is None else generation
        members = db.execute(
            "SELECT m.*,r.name,r.status AS run_status,r.life,r.time_us FROM evolution_members m JOIN runs r ON r.id=m.run_id "
            "WHERE m.campaign_id=%s AND m.generation=%s AND (%s::text IS NULL OR m.stage=%s) "
            "ORDER BY m.stage,m.slot,m.block_index LIMIT 61 OFFSET %s",
            (identity, generation, stage, stage, offset),
        ).fetchall()
        selections = db.execute(
            "SELECT generation,slot,candidate_version_id,rank,selected,scores FROM evolution_selections "
            "WHERE campaign_id=%s AND generation=%s ORDER BY rank",
            (identity, generation),
        ).fetchall()
        counts = db.execute(
            "SELECT m.stage,r.status,count(*) AS count FROM evolution_members m JOIN runs r ON r.id=m.run_id "
            "WHERE m.campaign_id=%s AND m.generation=%s GROUP BY m.stage,r.status",
            (identity, generation),
        ).fetchall()
        events = db.execute(
            "SELECT revision,kind,payload,created_at FROM evolution_events WHERE campaign_id=%s ORDER BY revision DESC LIMIT 30",
            (identity,),
        ).fetchall()
        progress = db.execute(
            "SELECT generation,s.key AS metric,min(s.value::double precision) AS minimum,"
            "max(s.value::double precision) AS maximum,avg(s.value::double precision) AS mean,"
            "avg(s.value::double precision) FILTER(WHERE selected) AS parent_mean,count(*) AS candidates "
            "FROM evolution_selections CROSS JOIN LATERAL jsonb_each_text(scores) s "
            "WHERE campaign_id=%s AND generation BETWEEN %s AND %s GROUP BY generation,s.key ORDER BY generation,s.key",
            (identity, max(0, generation - 99), generation),
        ).fetchall()
        return campaign | {
            "view_generation": generation,
            "members": members[:60],
            "members_more": len(members) > 60,
            "offset": offset,
            "selections": selections,
            "counts": counts,
            "events": events,
            "progress": progress,
            "progress_range": [max(0, generation - 99), generation],
        }
