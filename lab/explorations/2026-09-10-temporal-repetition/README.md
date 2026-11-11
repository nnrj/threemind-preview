# 时序收敛复验 / Temporal convergence replication

- [中文完整报告](report.md) / [English report](report.en.md)
- [训练前冻结的设计](protocol.md)、[原文课程](curriculum.json)、[默认参数与观察一致性检查](preflight.json)
- [补充连续观察设计](diagnostic-plan.md)、[观察摘要](diagnostic-summary.json)
- [逐帧验收](acceptance.json)、[检查点、实验来源与完整证据下载索引](evidence-index.json)
- [分析结果](analysis.json)、[完整节点排序](node-rankings.jsonl)

本地平台项目：**时序收敛复验：逐句20次与未见家系（2026-09-10）**。
先在项目切换器选择该项目，再打开“实验笔记”查看设计与总结，或“记录与报告”查看配对、家系、读出核对三个记录及综合报告。记录附带原生时序证据来源，可以继续选择图表与导出。项目、记录、笔记和下载ID保存在 platform.json / evidence-index.json。

主排序已由用户确认：**收敛窗口结束时的节点激活强度**。峰值和原有综合排名仅用于辅助核对。非收敛窗口、全部节点、并列、覆盖不足、零强度对照均保留。`series.total` 是合格超基线响应之和，不是全部内部激活。

## 命令与复现

本次复用了已实现的 Runtime 时序命令行/ReadoutSession 和 Lab 校准服务；没有新增或替换Core、感官或读出算法。研究脚本提供同一服务的批量执行与完整节点排序。

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe lab/explorations/2026-09-10-temporal-repetition/verify.py
```

以上是核查现有证据的命令。重新训练应**使用新的研究目录、WORK目录和独立数据库项目**，不能直接重跑本轮已经完成的种子或覆盖 platform.json。复现顺序为：

1. 保持原文课程、Core、TextSensor与TemporalReadoutConfig不变，给新研究设置独立HERE/WORK/META/WORKER。
2. `run.py preflight` → `run.py init`，创建新的参数/源码摘要和实验笔记。
3. `run.py seed --seed 41701`，依次41702、41703、41704。预算限制仍生效。
4. 可选 `diagnostic.py`，执行另行预先声明的4个12秒连续观察。
5. `analyze.py` → `verify.py` → `make_report.py` → `publish.py` → `verify.py`。

`run.py`拒绝覆盖已存在的种子结果；`analyze.py`只重新派生分析文件，不推进模型、不改原始实验；`publish.py`使用项目范围内自己创建的任务，并保留出版日志以便重试，不启动全局worker。

实施源码及依赖摘要见implementation.json；源码归档存入实验附件。大量窗口/逐节点证据存放在本地文件与数据库附件，模型本体存于数据库检查点及探针ZIP，均未放入Git。具体来源可通过evidence-index.json中的校验摘要与下载路径核对。

## 指标及文件边界

- `run.py`：原文教学、连续状态分支、既有时序/固定窗口服务、资源限制。
- `analyze.py`：窗口结束强度排序；全模板和预定独有通道投影，保持缺失与并列；完整原始节点另存。
- `diagnostic.py`：原读出结束后继续被动观察，20毫秒采样；不是重新分类。
- `verify.py`：逐条核对存储原文、默认编码帧、时刻、重复量、来源摘要、旧数据不变和出版结果。
- `make_report.py` / `publish.py`：描述性图表、说明、平台记录与报告、Markdown/HTML导出。

单位是编码种子；同一种子中多个问题、零刺激副本或时序采样点不能当作更多独立样本。本轮没有依据结果改变训练、感官映射或主排序。
