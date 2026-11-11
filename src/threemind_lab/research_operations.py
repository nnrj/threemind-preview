"""Manual research actions refer to actual checkpoints, never fabricated states."""

from uuid import uuid4

from psycopg.types.json import Jsonb

from .database import Conflict, NotFound
from .inputs import digest


def existing(db, project, request_id, fingerprint):
    row = db.execute(
        "SELECT * FROM research_operations WHERE project_id=%s AND request_id=%s",
        (project, request_id),
    ).fetchone()
    if row is not None and row["fingerprint"] != fingerprint:
        raise Conflict("这个请求编号已用于另一项操作，请保留原请求重试或创建新编号。")
    return row


def submit_advance(
    database,
    project,
    run_id,
    actor,
    *,
    request_id,
    expected_revision,
    duration_us,
    job=None,
    plan_id=None,
    plan_step=None,
    plan_attempt=0,
):
    """Freeze the absolute stop time before a worker sees this job.

    Retrying a leased job must resume toward this same target, not add the duration
    to its most recent checkpoint a second time.
    """
    if type(duration_us) is not int or not 1 <= duration_us <= 86_400_000_000:
        raise ValueError("推进时长须为 1～86,400,000,000 微秒的整数。")
    if type(expected_revision) is not int or expected_revision < 1:
        raise ValueError("请指定已有恢复点的科学修订号。")
    parameters = {"duration_us": str(duration_us), "expected_revision": expected_revision}
    fingerprint = digest({"run_id": str(run_id), "actor_id": str(actor), "kind": "runtime.advance", **parameters})
    with database.tx(project) as db:
        database.fence(db, job)
        run = db.execute(
            "SELECT id,status,revision,time_us,life,spec->>'study_id' AS study_id,"
            "spec->>'duration_s' AS duration_s FROM runs WHERE id=%s FOR UPDATE",
            (run_id,),
        ).fetchone()
        if run is None:
            raise NotFound()
        old = existing(db, project, request_id, fingerprint)
        if old is not None:
            return old
        from .research_lock import assert_control_available

        assert_control_available(db, run_id, plan_id)
        if run["study_id"]:
            raise Conflict("配对实验的时间协议已冻结；请分叉到独立实验沙箱再逐步操作。")
        if run["status"] not in ("paused", "blocked") or run["life"] == "dead":
            raise Conflict("逐步推进需要已暂停且未死亡的意识。")
        if run["revision"] != expected_revision:
            raise Conflict("科学修订号已变化，请查看新恢复点后重新操作。")
        if db.execute(
            "SELECT 1 FROM jobs WHERE run_id=%s AND kind='run' AND status IN ('pending','leased')", (run_id,)
        ).fetchone():
            raise Conflict("工作进程仍在提交停止状态，请稍后重试。")
        if db.execute("SELECT 1 FROM research_operations WHERE run_id=%s AND status='pending'", (run_id,)).fetchone():
            raise Conflict("已有研究操作尚未结束。")
        cp = db.execute(
            "SELECT id,time_us,context->>'end_us' AS end_us,context->>'start_us' AS start_us "
            "FROM checkpoints WHERE run_id=%s AND revision=%s",
            (run_id, expected_revision),
        ).fetchone()
        if cp is None:
            raise NotFound("没有可用的恢复点。")
        now = int(cp["time_us"])
        end = int(cp["end_us"]) if cp["end_us"] is not None else None
        if end is None and run["duration_s"] is not None:
            end = int(cp["start_us"] or 0) + round(float(run["duration_s"]) * 1e6)
        target = now + duration_us
        if end is not None and target > end:
            raise ValueError("推进目标超出当前运行终点；请先在暂停参数中明确延长总时长。")
        operation_id, job_id = uuid4(), job["id"] if job else uuid4()
        if job is None:
            db.execute(
                "INSERT INTO jobs(id,project_id,run_id,kind,params) VALUES(%s,%s,%s,'run',%s)",
                (
                    job_id,
                    project,
                    run_id,
                    Jsonb({"research_operation_id": str(operation_id), "stop_at_us": str(target)}),
                ),
            )
        db.execute("UPDATE runs SET status='queued',error=NULL WHERE id=%s", (run_id,))
        return db.execute(
            "INSERT INTO research_operations(id,project_id,run_id,actor_id,request_id,fingerprint,kind,parameters,"
            "status,checkpoint_id,job_id,plan_id,plan_step,plan_attempt) VALUES(%s,%s,%s,%s,%s,%s,'runtime.advance',%s,'pending',%s,%s,%s,%s,%s) RETURNING *",
            (
                operation_id,
                project,
                run_id,
                actor,
                request_id,
                fingerprint,
                Jsonb(parameters | {"start_us": str(now), "target_us": str(target)}),
                cp["id"],
                job_id,
                plan_id,
                plan_step,
                plan_attempt,
            ),
        ).fetchone()


def finish_at_checkpoint(db, project, run_id, operation_id, checkpoint, result):
    """Called in the same fenced transaction as the final causal state."""
    row = db.execute(
        "UPDATE research_operations SET status=%s,result=%s,result_checkpoint_id=%s,updated_at=now() "
        "WHERE project_id=%s AND run_id=%s AND id=%s AND status='pending' RETURNING id",
        (
            "completed" if result["target_reached"] else "interrupted",
            Jsonb(result),
            checkpoint,
            project,
            run_id,
            operation_id,
        ),
    ).fetchone()
    if row is None:
        raise Conflict("研究操作不再等待这个检查点提交。")


def record_observation(
    database,
    project,
    run_id,
    actor,
    *,
    request_id,
    kind,
    checkpoint_id=None,
    text="",
    label="",
    limit=20,
    job=None,
    plan_id=None,
    plan_step=None,
    plan_attempt=0,
):
    if kind not in (
        "observe.summary",
        "observe.graph",
        "observe.output",
        "experiment.note",
        "snapshot.capture",
        "history.tail",
    ):
        raise ValueError("未注册的观察命令。")
    if kind == "experiment.note":
        if not isinstance(text, str) or not text.strip() or len(text) > 20000:
            raise ValueError("注记须为 1～20,000 字的文本。")
    elif text:
        raise ValueError("观察命令不接受额外文本。")
    parameters = {"checkpoint_id": str(checkpoint_id) if checkpoint_id else None}
    if kind == "experiment.note":
        parameters["text"] = text
    elif kind == "snapshot.capture":
        if not isinstance(label, str) or not label.strip() or len(label) > 200:
            raise ValueError("状态名称须为 1～200 字。")
        parameters["label"] = label
    elif kind == "history.tail":
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("历史条数须为 1～100。")
        parameters["limit"] = limit
    fingerprint = digest({"run_id": str(run_id), "actor_id": str(actor), "kind": kind, **parameters})
    with database.tx(project) as db:
        database.fence(db, job)
        old = existing(db, project, request_id, fingerprint)
        if old is not None:
            return old
        cp = db.execute(
            "SELECT id,revision,time_us,state_hash FROM checkpoints WHERE run_id=%s"
            + (" AND id=%s" if checkpoint_id else "")
            + " ORDER BY revision DESC LIMIT 1",
            (run_id, checkpoint_id) if checkpoint_id else (run_id,),
        ).fetchone()
        if cp is None:
            raise NotFound("没有可观察的恢复点。")
    # Annotation and pointer actions never expand the neural state. A summary
    # uses this exact immutable checkpoint, even if execution has since advanced.
    result = {
        "checkpoint_id": str(cp["id"]),
        "revision": cp["revision"],
        "time_us": str(cp["time_us"]),
        "state_hash": cp["state_hash"],
        "basis": "committed_checkpoint",
        "observer": "registered_plan_tool" if plan_id else "human_research_tool",
    }
    if kind == "observe.summary":
        from threemind_runtime import create_engine

        _, image = database.load_checkpoint(project, run_id, cp["id"])
        engine = create_engine(state=image)
        result["metrics"] = engine.metrics()
        if engine.capture_state().digest != image.digest:
            raise ValueError("被动观察意外改变了模型状态，结果未保存。")
    elif kind == "observe.graph":
        result["queries"] = {"tables": ["nodes", "edges"], "checkpoint_id": str(cp["id"])}
    elif kind == "observe.output":
        # Freeze output event references, not an invented semantic interpretation.
        rows = []
        with database.tx(project) as db:
            for channel, event_kind in (
                ("structure", "structural_readout"),
                ("temporal", "temporal_readout"),
                ("voices", "organ_output"),
                ("image", "organ_output"),
            ):
                row = db.execute(
                    "SELECT id::text AS event_id,kind,time_us FROM events WHERE run_id=%s AND kind=%s "
                    "AND time_us<=%s AND commit_revision<=%s "
                    + ("AND payload ? %s " if event_kind == "organ_output" else "")
                    + "ORDER BY time_us DESC,id DESC LIMIT 1",
                    (run_id, event_kind, cp["time_us"], cp["revision"])
                    + ((channel,) if event_kind == "organ_output" else ()),
                ).fetchone()
                if row is not None:
                    rows.append(row | {"channel": channel})
        result["events"] = rows
        result["coverage"] = "latest_committed_output_at_or_before_checkpoint; absent kinds were not recorded"
    elif kind == "history.tail":
        with database.tx(project) as db:
            result["operations"] = db.execute(
                "SELECT o.id,o.kind,o.status,o.checkpoint_id,o.result_checkpoint_id FROM research_operations o "
                "JOIN checkpoints c ON c.id=o.checkpoint_id WHERE o.run_id=%s AND c.revision<=%s "
                "ORDER BY o.ordinal DESC LIMIT %s",
                (run_id, cp["revision"], limit),
            ).fetchall()
            result["operations"] = [
                {key: str(value) if value is not None else None for key, value in row.items()}
                for row in result["operations"]
            ]
    elif kind == "snapshot.capture":
        result["label"] = label
    with database.tx(project) as db:
        database.fence(db, job)
        # Serialize idempotent retries with other commands and whole-run cleanup.
        if db.execute("SELECT id FROM runs WHERE id=%s FOR UPDATE", (run_id,)).fetchone() is None:
            raise NotFound()
        old = existing(db, project, request_id, fingerprint)
        if old is not None:
            return old
        return db.execute(
            "INSERT INTO research_operations(id,project_id,run_id,actor_id,request_id,fingerprint,kind,parameters,"
            "status,checkpoint_id,result_checkpoint_id,result,job_id,plan_id,plan_step,plan_attempt) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'completed',%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                uuid4(),
                project,
                run_id,
                actor,
                request_id,
                fingerprint,
                kind,
                Jsonb(parameters),
                cp["id"],
                cp["id"],
                Jsonb(result),
                job["id"] if job else None,
                plan_id,
                plan_step,
                plan_attempt,
            ),
        ).fetchone()
