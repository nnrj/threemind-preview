"""Named capture requests resolve inside the actual checkpoint transaction."""

from datetime import UTC
from typing import Literal
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb
from pydantic import Field, field_validator

from .database import Conflict, NotFound
from .inputs import digest
from .protocols import StrictModel


class CaptureRequest(StrictModel):
    request_id: UUID
    label: str = Field("", max_length=120, strict=True)
    auto_name: Literal["revision", "timestamp"] = "timestamp"
    pinned: bool = Field(False, strict=True)

    @field_validator("label")
    @classmethod
    def name(cls, value):
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("恢复点名称不能含换行或控制字符。")
        return value.strip()


def submit(store, project, run_id, actor, body):
    params = body.model_dump(mode="json", exclude={"request_id"})
    fingerprint = digest({"run_id": str(run_id), "actor_id": str(actor), **params})
    with store.tx(project) as db:
        run = db.execute("SELECT id,status FROM runs WHERE id=%s FOR UPDATE", (run_id,)).fetchone()
        if run is None:
            raise NotFound()
        old = db.execute(
            "SELECT * FROM state_captures WHERE project_id=%s AND request_id=%s", (project, body.request_id)
        ).fetchone()
        if old:
            if old["fingerprint"] != fingerprint:
                raise Conflict("此请求编号已用于另一份捕获；请重试原请求或重新创建。")
            return old
        from .research_lock import assert_control_available

        assert_control_available(db, run_id, population_checkpoint=True)
        if run["status"] not in ("queued", "running"):
            raise Conflict("捕获新状态需要正在执行的意识；已停止时可直接编辑已有恢复点名称。")
        job = db.execute(
            "SELECT id FROM jobs WHERE run_id=%s AND kind='run' AND status IN ('pending','leased')", (run_id,)
        ).fetchone()
        if job is None:
            raise Conflict("没有执行中的运行任务，无法确认新的状态边界。")
        if db.execute("SELECT 1 FROM state_captures WHERE run_id=%s AND status='pending'", (run_id,)).fetchone():
            raise Conflict("已有状态捕获等待提交，请等待回执后再捕获。")
        capture_id = uuid4()
        command = db.execute(
            "INSERT INTO commands(project_id,run_id,kind,payload) VALUES(%s,%s,'checkpoint',%s) RETURNING id",
            (project, run_id, Jsonb({"capture_id": str(capture_id)})),
        ).fetchone()
        return db.execute(
            "INSERT INTO state_captures(id,project_id,run_id,actor_id,request_id,fingerprint,parameters,command_id,job_id) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (capture_id, project, run_id, actor, body.request_id, fingerprint, Jsonb(params), command["id"], job["id"]),
        ).fetchone()


def finish_failed(db, run_id, reason, *, job_id=None):
    db.execute(
        "UPDATE state_captures SET status='failed',error=%s,finished_at=clock_timestamp() WHERE run_id=%s AND status='pending' "
        "AND (%s::uuid IS NULL OR job_id=%s)",
        (reason, run_id, job_id, job_id),
    )


def resolve(db, project, run, checkpoint, last_command, terminal):
    capture = db.execute(
        "SELECT * FROM state_captures WHERE run_id=%s AND status='pending' FOR UPDATE", (run["id"],)
    ).fetchone()
    if capture is None:
        return
    if capture["command_id"] > (last_command or 0):
        if terminal:
            finish_failed(db, run["id"], "运行在处理捕获请求前结束；可查看最后已提交恢复点。")
        return
    permitted = db.execute(
        "SELECT 1 FROM members m JOIN users u ON u.id=m.user_id WHERE m.project_id=%s AND m.user_id=%s "
        "AND m.role IN ('owner','researcher') AND u.enabled",
        (project, capture["actor_id"]),
    ).fetchone()
    if not permitted:
        finish_failed(db, run["id"], "发起者已失去项目编辑权限，命名未应用。")
        return
    params = capture["parameters"]
    label = params["label"]
    if not label:
        suffix = f" · r{checkpoint['revision']}"
        if params["auto_name"] == "timestamp":
            suffix += " · " + checkpoint["created_at"].astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        # Limit only the name prefix, retaining the actual revision and UTC stamp.
        label = run["name"][: 120 - len(suffix)] + suffix
    from .model_library import update_metadata

    updated = update_metadata(
        db, project, checkpoint, {"label": label, "pinned": params["pinned"]}, capture["actor_id"], checkpoint=True
    )
    result = {
        "label": label,
        "revision": checkpoint["revision"],
        "time_us": str(checkpoint["time_us"]),
        "state_hash": checkpoint["state_hash"],
    }
    db.execute(
        "UPDATE state_captures SET status='completed',checkpoint_id=%s,result=%s,finished_at=clock_timestamp() WHERE id=%s",
        (checkpoint["id"], Jsonb(result), capture["id"]),
    )
    return updated


def history(store, project, run_id, *, before=None, limit=10):
    store.get_run(project, run_id)
    with store.tx(project) as db:
        rows = db.execute(
            "SELECT * FROM state_captures WHERE run_id=%s AND (%s::bigint IS NULL OR ordinal<%s) ORDER BY ordinal DESC LIMIT %s",
            (run_id, before, before, limit + 1),
        ).fetchall()
    return {"rows": rows[:limit], "next": rows[limit - 1]["ordinal"] if len(rows) > limit else None}
