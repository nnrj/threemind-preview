# E55 操作 / operations

计划与实测分开保存。`experiment.py` 是本轮入口，使用现有数据库配置；独立项目登记后可运行指定条件。三组都持续接收物理背景。不会启动Docker或接管用户worker。

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
& $py lab/explorations/2026-10-06-grounded-reviews/experiment.py prepare
& $py lab/explorations/2026-10-06-grounded-reviews/experiment.py suite --condition spaced --seed 223
& $py lab/explorations/2026-10-06-grounded-reviews/experiment.py suite --condition frozen --seed 223
& $py lab/explorations/2026-10-06-grounded-reviews/experiment.py suite --condition uniform --seed 223
```

本轮已登记的执行次序补充见`execution-notes.md`：等间隔组和第二来源后置，优先实际指向，不能将上方命令的存在当成该组已运行。

```powershell
& $py lab/explorations/2026-10-06-grounded-reviews/experiment.py extra --condition spaced --split permutations
& $py lab/explorations/2026-10-06-grounded-reviews/motor.py suite
```

运动CLI也支持`teach`、`fit --scope episode|recent`、`test --scope episode --mode normal|changed-request|silence|zero|rescue`。默认完整流程会跳过完成阶段，不覆盖半途失败；过程窗只选取实际帧，不改变刺激或活动值。教师坐标只供示范与评分，不能交给测试控制器。`analyze.py`从已有评分逐题配对，区分净得分与答案改变，不启动新实验。

`validate_motor.py`使用完整最后一轮示范作为验证集，训练另一候选头；`validate_motor.py --test-if-qualified`仅在事前误差门槛、账户和剩余计算预算均通过时启动32题闭环复测。验证集标签不会作为梯度训练目标；旧`ActivityController.fit`不传验证集时行为不变。

2026-10-06结项：主头到达0/32、短窗1/32。候选验证未通过0.05门槛，另以`--exploratory-task-test`执行了唯一一套后验实际任务检验，结果1/32；未改写失败标记。该选项只记录本次明确说明的执行偏离，不代表放开预算或验证已通过。后三组大批运动消融/改请求及恢复、等间隔组和第二来源未执行；本轮不再启动。完整结论见[中文](report.zh.md)、[English](report.en.md)。

`prepare`只能运行一次。已完成阶段被跳过；不完整阶段不自动覆盖。`collect --split train|familiar|held`、`fit`可以分别调用。账户读数须由当前实测写入`.work/grounded-reviews-20261006/usage.json`，过期30分钟自动停止。不要伪造余额或为绕过守卫刷新旧值。

Reuse tools: `lab.tools.grounded_classroom.GroundedClassroom` provides real simulated measurements and restorable state; `lab.tools.classroom_reviews.classroom_reviews` exports exact per-item timing. No answer label is consumed by Core or the expression head at inference. Training targets are external teacher supervision. The old classroom and old evidence remain unchanged.

`summarize.py` aggregates completed stages only; `replay.py` renders fixed-index teaching/probe records and bodily measurements without generating new answers. Final report and evidence are published through existing ThreeMind research services.
