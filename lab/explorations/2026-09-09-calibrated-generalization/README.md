# 校准后配对与关系组合验证

- [完整中文报告](report.md) · [English report](report.en.md)
- [预先方案](protocol.md) · [校准决策与执行记录](execution-notes.md)
- [校准工具及只读存储检查使用说明](../../../docs/zh/v2-probe-calibration.md)
- `summary.json`、两个 cases.csv：逐案例统计和种子块分析。
- `platform.json`：新项目、笔记、实验记录、报告与导出编号。
- `evidence-index.json`：数据库中全部校准证据的来源和下载地址。

配对关联在扩大验证中复现，未见名字的祖父关系组合没有验证成功；完整负结果保留。本轮未修改 Core。

复算使用 `.venv/Scripts/python.exe lab/explorations/2026-09-09-calibrated-generalization/analyze.py`。它只读取已有结果文件并生成派生统计，不运行意识。大原始证据保存在数据库中，本地阶段结果位于忽略目录 `.work/calibrated-generalization-20260909`，也作为报告证据附件保存。

`run.py init` 只适用于没有 platform.json 的全新研究副本；已有项目禁止覆盖初始化。每阶段文件使用独占创建，失败重试必须给新的 `--attempt` 编号。不要为重跑研究删除现有项目或结果文件。
