# 校准后配对与关系组合验证

> **修订 r2 · 2026-10-10**
> 修订原因：生成证据移出 Git 并完成校验归档；追加位置登记，保留原字节与结论。
> 原版：[README.md](README.md)；父版本 r1：[README.md](README.md)


- [完整中文报告](report.md) · [English report](report.en.md)
- [预先方案](protocol.md) · [校准决策与执行记录](execution-notes.md)
- [校准工具及只读存储检查使用说明](../../../docs/zh/v2-probe-calibration.md)
- `summary.json`、两个 cases.csv：逐案例统计和种子块分析。
- `platform.json`：新项目、笔记、实验记录、报告与导出编号。
- `evidence-index.json`：数据库中全部校准证据的来源和下载地址。

配对关联在扩大验证中复现，未见名字的祖父关系组合没有验证成功；完整负结果保留。本轮未修改 Core。

复算使用 `.venv/Scripts/python.exe lab/explorations/2026-09-09-calibrated-generalization/analyze.py`。它只读取已有结果文件并生成派生统计，不运行意识。大原始证据保存在数据库中，本地阶段结果位于忽略目录 `.work/calibrated-generalization-20260909`，也作为报告证据附件保存。

`run.py init` 只适用于没有 platform.json 的全新研究副本；已有项目禁止覆盖初始化。每阶段文件使用独占创建，失败重试必须给新的 `--attempt` 编号。不要为重跑研究删除现有项目或结果文件。


## 数据位置修订

选定的生成证据已逐字节校验归档。原报告、评判标准、结论及数据内 source_commit 均保留。以下逻辑下载需要当前主机管理员身份，数据目录未整体公开。

`data/experiments/2026-09-09-calibrated-generalization/`

[Location and hash index / 位置及哈希登记](../../artifact-index/2026-10-09-relocations.json)

- [evidence-index.json](/api/v2/storage/research-artifacts/research-artifact:a7d58c69bb50d0a0ea94263a/content) — 1907032 B; SHA-256 `7f78fba5b192449f07803b542ef51b74a7c920919781e75ff5c70740461ebe5b`.
- [implementation-source.zip](/api/v2/storage/research-artifacts/research-artifact:0a07a4565eb15bbe5a09c629/content) — 614159 B; SHA-256 `b49bbbcc014adae8b97cc754a8e25bd8140b1a58bdc242d6ec686558f640fe2e`.
- [memory-cases.csv](/api/v2/storage/research-artifacts/research-artifact:781b21047f7ca3b6f91834ff/content) — 168372 B; SHA-256 `b8df0f42e6edd22729eb0ad500e8cabad4777c5315e53ade76dee433bf8680fc`.
- [relations-cases.csv](/api/v2/storage/research-artifacts/research-artifact:933e43f64d199036293addf0/content) — 35564 B; SHA-256 `b2beca67815b255e3e8b9d2319d640e09ce989464762729e03b94e9ef592e202`.
