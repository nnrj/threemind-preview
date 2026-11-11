# 经历保持与自主活动研究

[English](README.md) · [完整报告](report.zh.md) · [交付验证](delivery.zh.md)

2026-09-29，802 个实例完成并停止继续模拟；四项预登记操作判据全部通过。原始状态不因报告编写而更改。主观体验不是本项目可直接验证的变量。

- [基础登记：722 实例](design.zh.md)
- [追加登记：80 个 30 秒保持副本](retention-extension.zh.md)
- 平台项目：`2026-09-29 经历保持、内部通路与自主活动判据`，`92548061-22c0-4bd9-b283-c4e1e7f4360d`。
- 数据与分析：项目根目录 `.work/experience-autonomy-20260929`；完整证据包也在平台四条实验记录及报告的附件中。
- 既有 180 实例报告只追加讨论，修订到第 2 版，旧证据包保留。

## 操作命令

在项目根目录使用 `.work/kernel-venv/Scripts/python.exe`。基础登记和模拟入口分别为：

```powershell
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-experience-and-autonomy/experiment.py register
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-experience-and-autonomy/experiment.py local
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-experience-and-autonomy/experiment.py memory
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-experience-and-autonomy/experiment.py sequence
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-experience-and-autonomy/experiment.py environment
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-experience-and-autonomy/experiment.py novelty
```

以上记录执行入口，不表示应重新执行已完成的研究。登记拒绝覆盖已有项目，完整案例会读取复用；STOP 文件阻止新增模拟。独立复现请新建研究目录与 WORK 名称并重新登记，保留原研究，不删除 STOP 后原地改参数。

以下命令只分析现有数据，不运行 Core：

```powershell
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-experience-and-autonomy/analyze.py all
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-experience-and-autonomy/analyze.py audit
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-experience-and-autonomy/retention_analysis.py
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-experience-and-autonomy/diagnostics.py
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-experience-and-autonomy/secondary_analysis.py
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-experience-and-autonomy/evidence.py
```

`diagnostics.py` 检查运动公式的非线性是否能独自解释连续互动；`secondary_analysis.py` 保留无提示行为和完整节点向量分析。它们是公开标记的次要诊断，不改变预登记判据。

## 证据结构

每例包含最终状态、配置、干预事件、观测、原始输入信封与递送、时序窗口和末端激活排序；探测另有节点及身体完整轨迹。目录中的 `registration.json` 与冻结副本固定执行前依据；追加登记另存，未覆盖原登记。`criteria-decision.json` 是明确判定，`analysis.json` 与 `input-export-audit.json` 是完整性核验，`publication-verification.json` 是落库与归档回读核验。

`StateImage.digest` 是模型规范摘要，与压缩文件本身 SHA 不混用。工作目录和平台使用同一批完整状态；不从图形抽样重建证据。

本轮 Core、运行时默认值、前端和映射协议均未修改。已有公开的复制、出生、输入、推进、参数干预、边静默和模型保存接口已足以执行本轮实验。
