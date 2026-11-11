"""Independent birth batches and read-only, checkpoint-bound endpoint evaluation."""

from collections import Counter
from uuid import uuid4, uuid5

from psycopg.types.json import Jsonb

from . import development
from .ai_evidence import wire
from .assessment_protocol import AssessmentProtocol, summarize
from .database import Conflict, NotFound
from .evolution_protocol import SELECTION_METRICS
from .measurements import ENERGY_METRICS, energy_endpoints

UNITS = {key: value[1] for key, value in SELECTION_METRICS.items()}


def batch(db, identity, *, lock=False):
    row = db.execute(
        "SELECT * FROM assessment_batches WHERE id=%s" + (" FOR UPDATE" if lock else ""), (identity,)
    ).fetchone()
    if row is None:
        raise NotFound()
    return row


def validate(db, protocol, maximum):
    source = development._version(db, protocol.source_version_id)
    spec = development.validate_spec(protocol.evaluation, source, maximum)
    # UNION, rather than UNION ALL, also bounds malformed cyclic ancestry. Only
    # return overlaps with the <=32 requested seeds, not every historical trial.
    overlaps = db.execute(
        "WITH RECURSIVE lineage AS (SELECT id,parent_version_id,protocol FROM innate_versions WHERE id=%s "
        "UNION SELECT v.id,v.parent_version_id,v.protocol FROM innate_versions v JOIN lineage l ON v.id=l.parent_version_id), "
        "known AS (SELECT (protocol->>'environment_seed')::bigint AS seed FROM lineage "
        "UNION SELECT m.environment_seed FROM evolution_members m JOIN lineage l ON m.candidate_version_id=l.id "
        "WHERE m.stage IN ('evaluation','verification')) SELECT seed FROM known WHERE seed=ANY(%s) ORDER BY seed",
        (source["id"], protocol.environment_seeds),
    ).fetchall()
    if overlaps:
        raise ValueError("评估种子与已有谱系中的发育或选择记录重叠：" + ", ".join(str(r["seed"]) for r in overlaps))
    return protocol.model_dump(mode="json") | {"evaluation": spec}


def create(database, project, actor, request, maximum):
    with database.tx(project) as db:
        previous, request_hash = development._retry(db, "assessment_batches", project, actor, request)
        if previous:
            return previous
        protocol = validate(db, request.protocol, maximum)
        identity = uuid4()
        row = db.execute(
            "INSERT INTO assessment_batches(id,project_id,actor_id,operation_id,request_hash,name,objective,source_version_id,protocol,protocol_hash) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                identity,
                project,
                actor,
                request.operation_id,
                request_hash,
                request.name,
                request.objective,
                request.protocol.source_version_id,
                Jsonb(protocol),
                development.digest(protocol),
            ),
        ).fetchone()
        for block, seed in enumerate(request.protocol.environment_seeds):
            session = development.create_in(
                db,
                project,
                actor,
                development.DevelopmentRequest(
                    operation_id=uuid5(identity, str(block)),
                    name=f"{request.name[:95]} · {block + 1}",
                    objective=request.objective,
                    source_version_id=request.protocol.source_version_id,
                    spec=request.protocol.evaluation.model_copy(update={"environment_seed": seed}),
                ),
                maximum,
            )
            db.execute(
                "INSERT INTO assessment_members(project_id,batch_id,block_index,environment_seed,run_id) VALUES(%s,%s,%s,%s,%s)",
                (project, identity, block, seed, session["run_id"]),
            )
            # Refresh capability requirements after atomic membership insertion.
            db.execute(
                "UPDATE jobs SET params=params||%s WHERE run_id=%s AND kind='run' AND status='pending'",
                (Jsonb({"assessment_id": str(identity)}), session["run_id"]),
            )
        from .native_records import register_execution
        register_execution(database, db, project, {'id': actor}, 'assessment', identity, request.name, protocol,
                           executor=request.record_executor, classification=request.record_classification,
                           question=request.objective)
        return row


def members(db, identity):
    return db.execute(
        "SELECT m.*,r.name,r.status,r.life,r.time_us::text,r.revision,r.state_hash,r.metrics,r.error,"
        "c.id AS checkpoint_id,c.context->'implementation' AS implementation,"
        "EXISTS(SELECT 1 FROM jobs j WHERE j.run_id=r.id AND j.kind='run' AND j.status IN ('pending','leased')) AS working "
        "FROM assessment_members m JOIN runs r ON r.id=m.run_id "
        "LEFT JOIN checkpoints c ON c.run_id=r.id AND c.revision=r.revision AND c.state_hash=r.state_hash "
        "WHERE m.batch_id=%s ORDER BY m.block_index",
        (identity,),
    ).fetchall()


def endpoint(member):
    metrics = member["metrics"] or {}
    complete = member["status"] in ("completed", "dead") and member["checkpoint_id"] is not None
    values = dict.fromkeys(UNITS)
    missing = {}
    sampled_at = metrics.get("time_us")
    if complete:
        values["observed_lifetime_s"] = int(member["time_us"]) / 1e6
        values["not_dead_at_end"] = int(member["life"] != "dead")
        for metric in set(UNITS) - {"observed_lifetime_s", "not_dead_at_end", *ENERGY_METRICS}:
            if sampled_at is not None and int(sampled_at) == int(member["time_us"]):
                values[metric] = metrics.get(metric)
            else:
                missing[metric] = "no_sample_at_checkpoint"
        values.update(energy_endpoints(metrics))
    else:
        missing = dict.fromkeys(UNITS, "trial_not_complete")
    from .report_sources import scalar

    values = {key: scalar(value) for key, value in values.items()}
    for key, value in values.items():
        if value is None:
            missing.setdefault(key, "measurement_unavailable")
    return wire(
        {
            "block_index": member["block_index"],
            "environment_seed": member["environment_seed"],
            "run_id": member["run_id"],
            "status": member["status"],
            "complete": complete,
            "checkpoint_id": member["checkpoint_id"],
            "checkpoint_revision": member["revision"],
            "state_hash": member["state_hash"],
            "time_us": member["time_us"],
            "sample_time_us": sampled_at,
            "life": member["life"],
            "lifetime_right_censored": member["life"] != "dead",
            "values": values,
            "missing": missing,
            "implementation": member["implementation"],
        }
    )


def snapshot(db, identity):
    value = batch(db, identity)
    rows = members(db, identity)
    protocol = AssessmentProtocol(**value["protocol"])
    if (
        len(rows) != len(protocol.environment_seeds)
        or [r["environment_seed"] for r in rows] != protocol.environment_seeds
    ):
        raise Conflict("评估成员与冻结种子表不一致；不能省略或补造试验。")
    trials = [endpoint(row) for row in rows]
    source = development._version(db, value["source_version_id"])
    return wire(
        {
            "batch_id": identity,
            "batch_name": value["name"],
            "objective": value["objective"],
            "control_revision": value["revision"],
            "control_state": value["control_state"],
            "protocol": value["protocol"],
            "protocol_hash": value["protocol_hash"],
            "source_version_id": source["id"],
            "source_state_hash": source["state_hash"],
            "trials": trials,
            "criteria": summarize(trials, protocol.criteria),
            "all_trials_complete": all(row["complete"] for row in trials),
            "row_unit": "one independent birth in one declared environment seed",
            "inference_boundary": "finite declared test set; no claim about intelligence, intent, consciousness or unseen environments",
            "seed_boundary": "known lineage development/selection seeds and explicit exclusions checked; unknown external history cannot be verified",
        }
    )


def listing(database, project, query="", offset=0):
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    with database.tx(project) as db:
        rows = db.execute(
            "SELECT id,name,objective,revision,control_state,source_version_id,protocol_hash,created_at,"
            "jsonb_array_length(protocol->'environment_seeds') AS trial_count FROM assessment_batches "
            "WHERE name ILIKE %s ORDER BY created_at DESC,id DESC LIMIT 31 OFFSET %s",
            (f"%{escaped}%", offset),
        ).fetchall()
    return {"rows": rows[:30], "more": len(rows) > 30}


def detail(database, project, identity):
    with database.tx(project, repeatable=True) as db:
        value = snapshot(db, identity)
        value["statuses"] = dict(Counter(row["status"] for row in value["trials"]))
        value["captures"] = db.execute(
            "SELECT r.id,r.created_at,j.status,j.error,s.content_hash FROM report_source_requests r "
            "JOIN jobs j ON j.id=r.job_id LEFT JOIN report_sources s ON s.id=r.id "
            "WHERE r.assessment_id=%s ORDER BY r.created_at DESC,r.id DESC LIMIT 30",
            (identity,),
        ).fetchall()
        return value


def control(database, project, actor, identity, request):
    with database.tx(project) as db:
        previous, request_hash = development._retry(db, "assessment_actions", project, actor, request)
        if previous:
            if str(previous["batch_id"]) != str(identity):
                raise Conflict("控制操作编号已用于另一项评估。")
            return previous
        value = batch(db, identity, lock=True)
        if value["revision"] != request.expected_revision or value["control_state"] == "cancelled":
            raise Conflict("评估控制状态已改变或已经取消，请刷新。")
        rows = db.execute(
            "SELECT r.id,r.status FROM runs r JOIN assessment_members m ON m.run_id=r.id "
            "WHERE m.batch_id=%s ORDER BY r.id FOR UPDATE OF r",
            (identity,),
        ).fetchall()
        changed = 0
        for row in rows:
            action = request.action
            if action in ("resume", "retry"):
                if row["status"] not in ("paused", "blocked", "failed"):
                    continue
                if row["status"] in ("failed", "blocked") and action != "retry":
                    raise Conflict("存在失败或阻塞试验，请检查原因并明确重试。")
                if row["status"] == "failed":
                    db.execute("UPDATE runs SET status='blocked' WHERE id=%s", (row["id"],))
                action = "resume"
            elif action == "pause" and row["status"] not in ("queued", "running"):
                continue
            elif action == "cancel":
                if row["status"] in ("completed", "dead", "cancelled"):
                    continue
                if row["status"] == "failed":
                    db.execute("UPDATE runs SET status='blocked' WHERE id=%s", (row["id"],))
            database.command(
                project,
                row["id"],
                action,
                {"assessment_id": str(identity), "actor_id": str(actor)},
                assessment_id=identity,
                transaction=db,
            )
            changed += 1
        if not changed:
            raise Conflict("当前没有适用该控制的试验；运行中的暂停请求需要等待提交。")
        state = "paused" if request.action == "pause" else "cancelled" if request.action == "cancel" else "active"
        db.execute("UPDATE assessment_batches SET revision=revision+1,control_state=%s WHERE id=%s", (state, identity))
        return db.execute(
            "INSERT INTO assessment_actions(id,project_id,batch_id,actor_id,operation_id,request_hash,action,revision) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                uuid4(),
                project,
                identity,
                actor,
                request.operation_id,
                request_hash,
                request.action,
                value["revision"] + 1,
            ),
        ).fetchone()
