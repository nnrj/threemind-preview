"""Shared admission rules for explicit scientific resource/control ports."""

from contextlib import nullcontext

from psycopg.types.json import Jsonb

from threemind_kernels.registry import resolve_kernel

from .database import Conflict, NotFound


def submit(database, project, run_id, actor_id, *, kind, request_id, payload, required_flag=None, transaction=None):
    if kind not in ("energy_supply", "input_modulation"):
        raise ValueError("unsupported scientific input port")
    payload = payload | {"request_id": str(request_id), "actor_id": str(actor_id)}
    with database.tx(project) if transaction is None else nullcontext(transaction) as db:
        run = db.execute("SELECT * FROM runs WHERE id=%s FOR UPDATE", (run_id,)).fetchone()
        if run is None:
            raise NotFound("run")
        previous = db.execute(
            "SELECT * FROM commands WHERE run_id=%s AND kind=%s AND payload->>'request_id'=%s",
            (run_id, kind, str(request_id)),
        ).fetchone()
        if previous:
            if previous["payload"] != payload:
                raise Conflict("相同请求编号已用于不同的端口请求；未重复执行。")
            return previous
        from .research_lock import assert_control_available

        assert_control_available(db, run_id, population_input=True)
        if run["status"] not in ("queued", "running", "paused", "blocked") or run["life"] == "dead":
            raise Conflict("此实例已结束，不能通过外部端口恢复生命；请显式继承为新实例。")
        if run["spec"].get("study_id"):
            raise Conflict("实验协议已冻结；请声明新的实验条件或分叉为独立运行。")
        capability = "causal_energy" if kind == "energy_supply" else "causal_attention"
        if capability not in resolve_kernel(run["spec"].get("kernel_id")).capabilities:
            raise Conflict("此意识选择的内核不支持该控制端口；不能把不同物理量或机制当作同一能力。")
        if required_flag and not getattr(
            resolve_kernel(run["spec"].get("kernel_id")).configuration(run["spec"].get("config", {})), required_flag
        ):
            raise Conflict("请先在意识参数中启用能量记账。")
        cp = db.execute(
            "SELECT context FROM checkpoints WHERE run_id=%s ORDER BY revision DESC LIMIT 1", (run_id,)
        ).fetchone()
        if (cp and cp["context"].get("source_enabled") is False) or db.execute(
            "SELECT 1 FROM commands WHERE run_id=%s AND kind='close_inputs' AND id>%s", (run_id, run["last_command"])
        ).fetchone():
            raise Conflict("该实例已关闭外部输入与控制端口。")
        result = db.execute(
            "INSERT INTO commands(project_id,run_id,kind,payload) VALUES(%s,%s,%s,%s) RETURNING *",
            (project, run_id, kind, Jsonb(payload)),
        ).fetchone()
        action = "energy.supply" if kind == "energy_supply" else "input.modulate"
        db.execute("INSERT INTO audit(user_id,action,resource) VALUES(%s,%s,%s)", (actor_id, action, str(run_id)))
        return result
