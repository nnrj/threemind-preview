# 耗竭、易化与连接巩固：执行与结果

[English](README.md)

2026-09-29：已完成 598 个整网实例，以及三因素独立控制、旧结果复现、八组短时和保持对照、有限扩展与检查点核查。

- [中文报告与图表](report.zh.md)
- [英文报告](report.en.md)
- [能量用词、持续内部活动与研究者原话](discussion.zh.md)：实验后的讨论补记，已追加报告；不修改原始结果。
- [下一轮自主活动实验讨论稿](../../../docs/zh/plans/autonomous-activity.md)：尚未执行。

讨论补记已经通过 `publish_discussion.py --apply` 发布为两篇报告的第 2 版，原第 1 版保留；同一笔记本新增中英文讨论笔记和待讨论方案。发布回读见 `.work/memory-timescales-20260929/discussion-publication.json`：实验实例仍为 598，未运行新实验，原证据附件的身份和摘要未变。本次未重新读取整包；完整字节校验仍见第一次交付。讨论与新方案不属于此前冻结的证据包。

- [交付记录、平台报告 ID 与最终资源账目](delivery.zh.md)
- [冻结的原设计](design.zh.md)：文中的“未实施”为登记时状态，不是当前状态。
- [前轮报告、讨论与七篇原始文献](../2026-09-29-continuous-mechanisms/report.zh.md)

项目 ID：`cbde2d48-284d-4294-9184-89f439923547`，项目列表中的名称保留为 **2026-09-29 耗竭、易化与连接巩固（实验设计）**。设计笔记、执行笔记和后续结果均归于该项目。初始中文设计笔记 `302a6256-61b1-51f2-aab1-01400009af1c`、英文设计笔记 `2117594c-6df7-5116-8ed6-1001fa1eadd4` 保留。

本轮实际命令顺序如下，已登记的 prepare/register 不应重复。命令只操作本研究命名空间；新研究须使用新的项目和工作目录，不能覆盖现有 ID。

```powershell
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-memory-timescales/run.py prepare
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-memory-timescales/run.py validate
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-memory-timescales/run.py short
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-memory-timescales/run.py retention
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-memory-timescales/extend.py register
# 三份扩展登记分别记录准入时间与范围；之后执行 history/readout/diagnostic/residual/sustain。
```

只读复核及重新生成派生分析：

```powershell
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-memory-timescales/analyze.py
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-memory-timescales/audit.py
```

前一条重建派生分析及图，不修改原始观测；后一条通过公开 Lab 接口解码全部本轮检查点，核对原始哈希和资源。设计、扩展登记、实验数据位于 `.work/memory-timescales-20260929`；不提交大数据到 Git。

新研究内核 `continuous-memory/1` 接入统一内核目录、参数 UI、Runtime CLI、定义协议和 Python/Rust 后端。保留原连续版及旧基线。测试见 `tests_v2/test_memory_candidate.py`。

`run.py` 的采样范围修订仅影响证据体积：第一阶段保存所有节点 10 ms 轨迹，保持及扩展阶段保存所有任务节点 10 ms 轨迹、全网络摘要和完整首尾状态。时序读出始终完整。原第一阶段脚本副本、核心源码和所有登记哈希均随证据保存。

报告通过 `publish.py` 使用 Lab 服务写入实验报告、实验笔记及八组实验记录；完整 ZIP 在内存生成，逐成员验签后流入数据库，不在磁盘额外保留大包。`publication.json` 记录平台 ID，交付文档记录最终空间和额度。
