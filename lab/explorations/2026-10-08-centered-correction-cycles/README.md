# E66 空白起点多轮纠错 / Blank-start correction cycles

2026-10-08。按用户要求从新的完整空白个体开始，固定眼手、物体居中，教师纠正实际错题，加入类似题和旧正确例，复习后续校、再测，最多三轮。原 E64/E65 个体与证据原位保留。

- [中文登记](design.zh.md) · [English registration](design.en.md)
- [中文报告](report.zh.md) · [English report](report.en.md) · [验证](verification.md) · [交接](HANDOFF.md)
- [当前训练规约 v2.1](../../../docs/zh/training-protocol.md)；本批执行的 v2 原文另行冻结
- 直接方法参照：[E64](../2026-10-08-centered-restart/report.zh.md)；上一批结果：[E65](../2026-10-08-centered-learning/report.zh.md)

工作目录 `.work/centered-correction-cycles-20261008`；完整身份 `e66-blank-223`；本地研究项目 `2bece525-31f1-4df8-93cf-cb3bd8dc9132`。`experiment.py` 的登记在刺激前冻结；只读审计、分章回放、交付工具分别为 `analyze.py`、`replay.py`、`publish.py`。查看结果不需要重新运行教学。

开发检查每次 72 题（两个位置各 36）；最后另外两个位置确认。全部 16 彩色搭配分别问形状、颜色，两题都对才计组合成功；四灰形状另计。最终位置从未用于当次教学或校准，前轮正式题若被用于纠错，须先明确转为开发材料。灰色不是八词头输出类别，灰物体只问形状。

复习采用一般先密后疏；精确曲线排程对照尚待单独设计。这个批次没有眼动学习、Core 改动或连接归因干预。

09:48 后补登记：[旧确认错题保持复查](retention-check.zh.md)（[English](retention-check.en.md)）。主循环结束后执行 `retention.py`，再做最终审计和回放；补查单列开发证据，不参与选头或改变原停止条件。`diagnose.py` 可复核已保存的第一轮形状输入/活动差异，不运行模拟。

结项：三轮固定开发题均72/72，起点53/72；最终新位置70/72，形状38/40、颜色32/32。原位置旧确认错题只改正2/7，易混对照7/7，尚未稳定全对。三轮上限后停止，进一步校准或曲线对照没有执行。

结项后按用户追加要求完成[固化机制核查](consolidation-audit.zh.md)（[English](consolidation-audit.en.md)）：机制存在且开启；稳定度仍会消退，长期时间尺度是否充分待讨论。没有修改Core或追加模拟。
