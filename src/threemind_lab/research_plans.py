"""Durable, bounded research sequences, executed by one fenced worker job.

Advancing a plan calls the normal run cycle inline; it never waits for a second
worker slot. Every step has an idempotent receipt and an immutable initial plan.
"""

from contextlib import nullcontext
from uuid import UUID, uuid4, uuid5

from psycopg.types.json import Jsonb

from .database import Conflict, Forbidden, NotFound
from .inputs import digest, submit
from .permissions import execution_actor
from .research_commands import parse_protocol, required_action
from .research_lock import assert_control_available
from .research_operations import existing, record_observation, submit_advance


def current_run(db, run_id):
    row = db.execute(
        "SELECT id,status,life,revision,time_us,last_command,parent_id,origin_kind,spec->>'study_id' AS study_id "
        "FROM runs WHERE id=%s FOR UPDATE",
        (run_id,),
    ).fetchone()
    if row is None:
        raise NotFound()
    return row


def command_boundary(db, run_id):
    return db.execute("SELECT coalesce(max(id),0) AS n FROM commands WHERE run_id=%s", (run_id,)).fetchone()["n"]


def current_checkpoint(db, run_id):
    row = db.execute(
        "SELECT id,revision,time_us,state_hash,context->>'end_us' AS end_us FROM checkpoints "
        "WHERE run_id=%s ORDER BY revision DESC LIMIT 1",
        (run_id,),
    ).fetchone()
    if row is None:
        raise Conflict("请先选择有真实恢复点的暂停意识。")
    return row


def get(db, run_id, plan_id, *, lock=False):
    row = db.execute(
        "SELECT * FROM research_plans WHERE id=%s AND run_id=%s" + (" FOR UPDATE" if lock else ""),
        (plan_id, run_id),
    ).fetchone()
    if row is None:
        raise NotFound()
    return row


def actor_can_execute(db, project, actor, database=None, *, action="runs.resume", run_id=None):
    if database is not None:
        from . import permissions

        user = permissions.resolve_actor(database, actor)
        resources = [{"kind": "project", "id": str(project)}]
        if run_id is not None:
            resources.append({"kind": "run", "id": str(run_id)})
        permissions.project_access(database, user, project, write=True, action=action, resources=resources)
        return user
    if not db.execute(
        "SELECT 1 FROM members m JOIN users u ON u.id=m.user_id WHERE m.project_id=%s AND m.user_id=%s "
        "AND m.role IN ('owner','researcher') AND u.enabled",
        (project, actor),
    ).fetchone():
        raise Forbidden("计划发起者当前没有项目写权限，执行已停止。")


def create(
    database,
    project,
    run_id,
    actor,
    *,
    name,
    protocol,
    request_id,
    expected_revision,
    origin="human",
    transaction=None,
    ai_call_id=None,
    derived_from=None,
):
    protocol = parse_protocol(protocol)
    if origin not in ("human", "ai"):
        raise ValueError("未知计划来源。")
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        raise ValueError("实验名称须为 1～200 字。")
    frozen = protocol.model_dump()
    with database.tx(project) if transaction is None else nullcontext(transaction) as db:
        run = current_run(db, run_id)
        if derived_from is not None:
            parent = get(db, run_id, derived_from)
            origin, ai_call_id = parent["origin"], parent["ai_call_id"]
        identity = [str(actor), str(run_id), name, frozen, expected_revision, origin]
        if ai_call_id is not None:
            identity.append(str(ai_call_id))
        if derived_from is not None:
            identity.append(str(derived_from))
        fingerprint = digest(identity)
        old = db.execute(
            "SELECT * FROM research_plans WHERE project_id=%s AND request_id=%s", (project, request_id)
        ).fetchone()
        if old:
            if old["fingerprint"] != fingerprint:
                raise Conflict("这个编号已用于另一份计划。")
            return old
        assert_control_available(db, run_id)
        if run["study_id"] or run["status"] not in ("paused", "blocked") or run["life"] == "dead":
            raise Conflict("请从普通暂停意识设计，或先创建同源暂停沙箱。")
        if run["revision"] != expected_revision:
            raise Conflict("起点已变化，请重新查看后冻结计划。")
        if protocol.mode == "automatic" and (not run["parent_id"] or run["origin_kind"] != "fork"):
            raise ValueError("受限自动模式只对明确分叉的沙箱开放。")
        if db.execute(
            "SELECT 1 FROM jobs WHERE run_id=%s AND kind IN ('run','research_plan') AND status IN ('pending','leased')",
            (run_id,),
        ).fetchone():
            raise Conflict("请等待之前的执行任务结束。")
        cp = current_checkpoint(db, run_id)
        if cp["end_us"] is not None and int(cp["time_us"]) + protocol.totals()["wait_us"] > int(cp["end_us"]):
            raise ValueError("整份计划的推进时间超过当前运行终点；请先明确延长暂停意识的总时长。")
        result = db.execute(
            "INSERT INTO research_plans(id,project_id,run_id,actor_id,request_id,fingerprint,name,protocol,protocol_hash,"
            "origin,expected_revision,expected_command,checkpoint_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                uuid4(),
                project,
                run_id,
                actor,
                request_id,
                fingerprint,
                name,
                Jsonb(frozen),
                digest(frozen),
                origin,
                run["revision"],
                command_boundary(db, run_id),
                cp["id"],
            ),
        ).fetchone()
        if ai_call_id:
            db.execute("UPDATE research_plans SET ai_call_id=%s WHERE id=%s", (ai_call_id, result["id"]))
            result["ai_call_id"] = ai_call_id
        if derived_from:
            db.execute("UPDATE research_plans SET derived_from=%s WHERE id=%s", (derived_from, result["id"]))
            result["derived_from"] = derived_from
        return result


def save_receipt(
    db,
    project,
    run_id,
    actor,
    request_id,
    kind,
    parameters,
    result,
    checkpoint,
    *,
    fingerprint=None,
    job=None,
    plan=None,
    step=None,
    attempt=0,
):
    return db.execute(
        "INSERT INTO research_operations(id,project_id,run_id,actor_id,request_id,fingerprint,kind,parameters,status,"
        "checkpoint_id,result_checkpoint_id,result,job_id,plan_id,plan_step,plan_attempt) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'completed',%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (
            uuid4(),
            project,
            run_id,
            actor,
            request_id,
            fingerprint or digest([str(actor), kind, parameters]),
            kind,
            Jsonb(parameters),
            checkpoint["id"],
            checkpoint["id"],
            Jsonb(
                {
                    "checkpoint_id": str(checkpoint["id"]),
                    "revision": checkpoint["revision"],
                    "time_us": str(checkpoint["time_us"]),
                    "state_hash": checkpoint["state_hash"],
                    **result,
                }
            ),
            job["id"] if job else None,
            plan,
            step,
            attempt,
        ),
    ).fetchone()


def control(
    database, project, run_id, plan_id, actor, *, action, request_id, expected_step, expected_revision, transaction=None
):
    if action not in ("start", "pause", "cancel"):
        raise ValueError("未知计划控制。")
    params = {
        "plan_id": str(plan_id),
        "action": action,
        "expected_step": expected_step,
        "expected_revision": expected_revision,
    }
    fingerprint = digest([str(actor), str(run_id), params])
    with database.tx(project) if transaction is None else nullcontext(transaction) as db:
        run = current_run(db, run_id)
        plan = get(db, run_id, plan_id, lock=True)
        old = existing(db, project, request_id, fingerprint)
        if old:
            return {"plan": plan, "control": old}
        cp = current_checkpoint(db, run_id)
        if action == "start":
            executor = actor_can_execute(db, project, actor, database, run_id=run_id)
            protocol = parse_protocol(plan["protocol"])
            for required in sorted({required_action(protocol.step_at(i).command) for i in range(protocol.step_count)}):
                actor_can_execute(db, project, executor, database, action=required, run_id=run_id)
            if plan["status"] not in ("ready", "paused"):
                raise Conflict("该计划当前不能开始，请查看已有执行结果。")
            assert_control_available(db, run_id, plan_id)
            if run["status"] not in ("paused", "blocked") or run["life"] == "dead":
                raise Conflict("计划需要已暂停且未死亡的意识。")
            if (
                expected_step != plan["next_step"]
                or expected_revision != plan["expected_revision"]
                or run["revision"] != plan["expected_revision"]
                or command_boundary(db, run_id) != plan["expected_command"]
            ):
                raise Conflict("冻结起点或暂停边界已被外部操作改变；请从当前状态重新设计独立计划。")
            if db.execute(
                "SELECT 1 FROM jobs WHERE run_id=%s AND kind IN ('run','research_plan') AND status IN ('pending','leased')",
                (run_id,),
            ).fetchone():
                raise Conflict("前一个任务尚未确认停止，请稍后重试。")
            job = db.execute(
                "INSERT INTO jobs(id,project_id,run_id,kind,params) VALUES(%s,%s,%s,'research_plan',%s) RETURNING id",
                (
                    uuid4(),
                    project,
                    run_id,
                    Jsonb({"plan_id": str(plan_id), "execution_actor": execution_actor(executor)}),
                ),
            ).fetchone()
            plan = db.execute(
                "UPDATE research_plans SET status='queued',job_id=%s,stop_requested=false,cancel_requested=false,"
                "error=NULL,updated_at=now() WHERE id=%s RETURNING *",
                (job["id"], plan_id),
            ).fetchone()
            result = {"accepted": True, "job_id": str(job["id"]), "execution": "queued"}
        elif plan["status"] in ("queued", "running"):
            db.execute(
                "UPDATE research_plans SET stop_requested=true,cancel_requested=%s,updated_at=now() WHERE id=%s",
                (action == "cancel", plan_id),
            )
            result = {"accepted": True, "execution": "stop_at_step_boundary", "action": action}
        else:
            if plan["status"] not in ("ready", "paused"):
                raise Conflict("该计划已经结束。")
            db.execute(
                "UPDATE research_plans SET status=%s,updated_at=now() WHERE id=%s",
                ("cancelled" if action == "cancel" else "paused", plan_id),
            )
            result = {"accepted": True, "execution": action}
        receipt = save_receipt(
            db,
            project,
            run_id,
            actor,
            request_id,
            "runtime.resume" if action == "start" else f"plan.{action}",
            params,
            result,
            cp,
            fingerprint=fingerprint,
            plan=plan_id,
        )
        return {"plan": get(db, run_id, plan_id), "control": receipt}


def checkpoint_boundary(db, run_id, plan_id, *, status, next_step, attempt=0, wait_target=None, error=None):
    run = current_run(db, run_id)
    return db.execute(
        "UPDATE research_plans SET status=%s,next_step=%s,step_attempt=%s,wait_target_us=%s,expected_revision=%s,"
        "expected_command=%s,error=%s,updated_at=now() WHERE id=%s RETURNING *",
        (status, next_step, attempt, wait_target, run["revision"], command_boundary(db, run_id), error, plan_id),
    ).fetchone()


def execute(worker, job):
    try:
        return execute_steps(worker, job)
    except Conflict as exc:
        # Only an invalid lease belongs to Worker's stale-worker branch. A real
        # admission refusal must finish this plan as failed, not lease-loop it.
        with worker.db.tx(job["project_id"]) as db:
            worker.db.fence(db, job)
        raise ValueError(f"计划步骤被拒绝：{exc}") from exc


def execute_steps(worker, job):
    database, project, run_id = worker.db, job["project_id"], job["run_id"]
    plan_id = job["params"]["plan_id"]
    protocol, frozen_hash = None, None
    from . import permissions

    lineage = job["params"].get("execution_actor")
    executor = permissions.current_actor()
    if lineage and executor is None:
        executor = permissions.restore_execution_actor(database, lineage, project=project)
    while True:
        with database.tx(project) as db:
            database.fence(db, job)
            run = current_run(db, run_id)
            plan = get(db, run_id, plan_id, lock=True)
            if str(plan["job_id"]) != str(job["id"]):
                return {"superseded": True}
            if plan["status"] not in ("queued", "running"):
                return {"status": plan["status"], "next_step": plan["next_step"]}
            if protocol is None:
                protocol = parse_protocol(plan["protocol"])
                frozen_hash = digest(protocol.model_dump())
            if frozen_hash != plan["protocol_hash"]:
                raise ValueError("计划哈希不匹配，拒绝执行。")
            index, attempt = plan["next_step"], plan["step_attempt"]
            step = protocol.step_at(index)
            executor = actor_can_execute(
                db, project, executor or plan["actor_id"], database, action=required_action(step.command), run_id=run_id
            )
            executor["_request_action"] = required_action(step.command)
            permissions.actor_context.set(executor)
            # On a process retry, finish the already admitted step before honoring
            # a boundary pause; the ordinary run cycle handles its exact target.
            request_id = uuid5(UUID(str(plan_id)), f"step:{index}:{attempt}")
            prior = db.execute(
                "SELECT * FROM research_operations WHERE project_id=%s AND request_id=%s", (project, request_id)
            ).fetchone()
            if (plan["stop_requested"] or worker.stopping) and prior is None:
                paused = checkpoint_boundary(
                    db,
                    run_id,
                    plan_id,
                    status="cancelled" if plan["cancel_requested"] else "paused",
                    next_step=index,
                    attempt=attempt,
                    wait_target=plan["wait_target_us"],
                )
                return {"status": paused["status"], "next_step": index}
            db.execute("UPDATE research_plans SET status='running',updated_at=now() WHERE id=%s", (plan_id,))
            if step.command == "runtime.wait" and plan["wait_target_us"] is None:
                plan["wait_target_us"] = str(int(run["time_us"]) + step.parameters["duration_us"])
                db.execute("UPDATE research_plans SET wait_target_us=%s WHERE id=%s", (plan["wait_target_us"], plan_id))
        common = {"job": job, "plan_id": plan_id, "plan_step": index, "plan_attempt": attempt}
        if step.command == "runtime.wait":
            operation = prior or submit_advance(
                database,
                project,
                run_id,
                executor["id"],
                request_id=request_id,
                expected_revision=run["revision"],
                duration_us=int(plan["wait_target_us"]) - int(run["time_us"]),
                **common,
            )
            result = worker.run(
                job
                | {
                    "params": {
                        "research_operation_id": str(operation["id"]),
                        "stop_at_us": operation["parameters"]["target_us"],
                    }
                }
            )
            completed = bool(result["target_reached"])
        elif prior is not None:
            completed = prior["status"] == "completed"
        elif step.command in ("stimulus.send", "stimulus.frames", "runtime.pause"):
            with database.tx(project) as db:
                database.fence(db, job)
                current_run(db, run_id)
                cp = current_checkpoint(db, run_id)
                if step.command in ("stimulus.send", "stimulus.frames"):
                    envelope = submit(
                        database,
                        project,
                        run_id,
                        executor,
                        adapter_id="text-sensor" if step.command == "stimulus.send" else "anonymous-frames",
                        payload=step.parameters,
                        request_id=request_id,
                        transaction=db,
                        source_id=("ai-debug" if plan["origin"] == "ai" else "ui-text")
                        if step.command == "stimulus.send"
                        else None,
                        research_plan_id=plan_id,
                    )
                    result = {
                        "envelope_id": str(envelope["id"]),
                        "admission_status": envelope["status"],
                        "meaning": "carrier accepted; delivery is recorded separately by InputBus",
                    }
                else:
                    result = {"execution": "pause_at_step_boundary"}
                save_receipt(
                    db,
                    project,
                    run_id,
                    executor["id"],
                    request_id,
                    step.command,
                    step.parameters,
                    result,
                    cp,
                    job=job,
                    plan=plan_id,
                    step=index,
                    attempt=attempt,
                )
            completed = True
        else:
            record_observation(
                database,
                project,
                run_id,
                executor["id"],
                request_id=request_id,
                kind=step.command,
                **step.parameters,
                **common,
            )
            completed = True
        with database.tx(project) as db:
            database.fence(db, job)
            run = current_run(db, run_id)
            fresh = get(db, run_id, plan_id, lock=True)
            if completed:
                index += 1
                status = (
                    "completed"
                    if index == protocol.step_count
                    else "cancelled"
                    if fresh["cancel_requested"]
                    else (
                        "paused"
                        if fresh["stop_requested"]
                        or worker.stopping
                        or protocol.mode == "manual"
                        or step.command == "runtime.pause"
                        else "running"
                    )
                )
                checkpoint_boundary(db, run_id, plan_id, status=status, next_step=index)
            else:
                # A graceful host stop or an explicit model interrupt may cut a
                # wait short. Keep its ORIGINAL absolute target for the next attempt.
                status = "paused" if run["status"] in ("paused", "blocked") and run["life"] != "dead" else "failed"
                if fresh["cancel_requested"]:
                    status = "cancelled"
                checkpoint_boundary(
                    db,
                    run_id,
                    plan_id,
                    status=status,
                    next_step=index,
                    attempt=attempt + 1,
                    wait_target=fresh["wait_target_us"],
                    error=None if status == "paused" else "意识未达到本步目标。",
                )
            if status != "running":
                return {"status": status, "next_step": index}
