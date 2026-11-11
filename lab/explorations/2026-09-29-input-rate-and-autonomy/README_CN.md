# 刺激间隔、环境选择与自主活动

[English](README.md) · [中文结果](report.zh.md) · [英文结果](report.en.md)

2026-09-29。448 个实例已完成，停止新增实验。使用新项目，不覆盖旧数据。Core 源码和默认参数未改。

打开平台项目 **2026-09-29 刺激间隔、自主活动与环境选择**（`59aee7a1-5248-417f-a03b-b56f858a04d9`）。实验笔记中有原始登记、各阶段安排及中英文结果；记录与报告中有 4 篇主题记录、2 篇报告和原始证据下载入口。意识列表保留配置、父本关系、全模型检查点和实际递送输入。未新增环形世界实时控制面板，本轮通过公开 Python 服务执行，平台查阅同一数据库证据。

## 命令

从项目根目录使用 `.work/kernel-venv/Scripts/python.exe`。数据库 URL 取自本地 `.env`，不打印密码，不操作原有进程。

实际执行顺序为 `calibrate.py register` → `validate` → `screen` → `analyze`；没有间隔通过规则，因此未执行 `holdout`。之后为 `activity.py`、`world.py preflight`、`selection.py`、`recovery.py`、`attribution.py`。这些都是创建实验的命令，**本轮已完成，不应原地再跑**。

读取／派生已有证据：

```powershell
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-input-rate-and-autonomy/analyze.py
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-input-rate-and-autonomy/figures.py
```

`read_world.py` 用既有读出器分析保存的世界样本，独立登记背景触发；`publish.py` 使用 Lab 笔记、报告、附件服务发布；`verify_publication.py` 从数据库读回核对。发布后修订应另开报告版本，不重写登记和证据。

各阶段原执行源码、配置和哈希位于 `.work/input-rate-autonomy-20260929/frozen-tools/` 及证据包；后来仅作格式整理的文件不冒充原执行哈希。独立重复应另建项目、证据目录和登记，保留本次结果只读。没有声称新增通用分布式调度或世界 UI。

## 证据

- `cases/**/result.json`：模型身份、配置、时长、父本和指标；`parent-state.json.gz`：全状态。
- `trajectory.jsonl.gz`：提示期间完整节点和 LIF 物理状态；原始脉冲在 `events.jsonl.gz`。
- `activity.jsonl.gz`：停止输入后的全节点活动。
- `world.json.gz`：身体、实际感官、节点活动、提出与执行的动作、供能器状态。
- `recovery.jsonl.gz`：局部恢复、活动与能量；`derived-readouts/`：单列的事后时序窗口及末端激活排序。
- 选择决定保存候选、分数和亲本编号；评估学习不回写父本。

模型使用规范化状态哈希；附件使用逐字节 SHA-256，JSON 文本数字写法不同不等于模型不同。3 GiB 总预算包含新增数据库和附件；账户用量起点 44%，47% 停扩展、48% 封存。`STOP` 文件已阻止新增模拟，但不阻碍核查发布。旧数据不扫描、不清理。
