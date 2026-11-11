"""Called while holding the subject row lock, before accepting scientific edits."""

from .database import Conflict


def assert_control_available(db, run_id, plan_id=None, *, population_input=False, population_checkpoint=False):
    if db.execute("SELECT 1 FROM language_sessions WHERE run_id=%s", (run_id,)).fetchone():
        raise Conflict("语言实验意识按轮推进；请在对话实验中操作，或从检查点分叉以进行其他研究。")
    if db.execute("SELECT 1 FROM assessment_members WHERE run_id=%s", (run_id,)).fetchone():
        raise Conflict("独立评估的环境、输入和参数已经冻结；请在评估页面控制，或先分叉进行另外的实验。")
    ecological = db.execute(
        "SELECT c.protocol->>'external_inputs' AS external_inputs FROM ecology_members m JOIN ecology_campaigns c ON c.id=m.campaign_id WHERE m.run_id=%s",
        (run_id,),
    ).fetchone()
    if ecological and not (population_checkpoint or population_input and ecological["external_inputs"] == "true"):
        raise Conflict(
            "该个体由生态训练统一管理。请在训练器控制种群；外部输入需要在创建时显式开启，参数或独立控制实验请使用继承副本。"
        )
    member = db.execute("SELECT campaign_id FROM evolution_members WHERE run_id=%s", (run_id,)).fetchone()
    if member:
        raise Conflict(
            "该个体属于冻结的多代实验协议。请在训练器中暂停、继续或重试；独立输入或参数实验请先分叉，避免污染评估与遗传来源。"
        )
    active = db.execute(
        "SELECT id FROM research_plans WHERE run_id=%s AND status IN ('queued','running')", (run_id,)
    ).fetchone()
    if active and str(active["id"]) != str(plan_id):
        raise Conflict("受控实验计划正在执行；请先暂停计划再添加计划外输入、命令或修改参数。")
