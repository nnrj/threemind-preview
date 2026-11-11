> **修订 r2 · 2026-10-10**
> 修订原因：生成证据移出 Git 并完成校验归档；追加位置登记，保留原字节与结论。
> 原版：[report-resources.md](report-resources.md)；父版本 r1：[report-resources.md](report-resources.md)

## 资源与证据核对

- 累计实验进程时间：1206.24秒（20.10分钟）；包含训练、测量及其数据库操作，不含写报告时间。
- 10个数据库意识，44个阶段恢复点，132次测量任务，588个探针/无提示副本。
- 采样到的单进程RSS最高196.49 MiB；不是整机或数据库服务内存峰值。
- 发布前数据库增长383.51 MiB，本地证据9.33 MiB；最终值另见`acceptance.json`。
- 预算4 GiB、累计计算30分钟；Codex基线65%，83%停止新实验、为20个百分点上限留余量。最终账户级观测见`quota-monitor.json`。
- 数据库逐一核对8,820个训练帧：原文、全角标点、次数、发送顺序、编码后的通道、计划及实际递送时间全部一致，均已递送。
- 44个恢复点摘要、132个测量来源摘要核对通过；4个固定代表ZIP中的28个最终模型和全部零/非零采样结构核对通过。
- 此前三个实验项目共1902个意识及其文档/笔记头摘要保持不变。没有清理旧数据，没有修改Core。

完整数据在ThreeMind本实验项目的恢复点与实验记录/报告中；`evidence-index.json`提供探针ZIP和结果的下载路径。`curriculum.json`保存完整发送清单，`measurements.json`包括早期窗口、晚期窗口、无提示基线和全部候选；不能只用表中的排名代替原始活动。


## 数据位置修订

选定的生成证据已逐字节校验归档。原报告、评判标准、结论及数据内 source_commit 均保留。以下逻辑下载需要当前主机管理员身份，数据目录未整体公开。

`data/experiments/2026-09-09-blocked-sentence-teaching/`

[Location and hash index / 位置及哈希登记](../../artifact-index/2026-10-09-relocations.json)

- [measurements.json](/api/v2/storage/research-artifacts/research-artifact:da8236a1ffa136cdac713ca9/content) — 681889 B; SHA-256 `9e0669dc685d327ade76dc05ee7c8969f4c9970de34b1dfa35c737a157fb7b72`.
- [raw-activity-differences.json](/api/v2/storage/research-artifacts/research-artifact:b167a48cd4c0bd2e798155f2/content) — 170406 B; SHA-256 `e4007d0b85bd2c71b34f0e5201476e5c01acf12c2bb8b4527e1e1ee83fbcf48e`.
- [time-courses.json](/api/v2/storage/research-artifacts/research-artifact:52e07c0b2217879a3eca28b7/content) — 973789 B; SHA-256 `d6be83c4ab1768aa5e9b772cb337fa39c034446bd0b3e786c6064afc3c7749f8`.
- [training-traces.json](/api/v2/storage/research-artifacts/research-artifact:5024d015e4fa46a1821c1f0d/content) — 1987149 B; SHA-256 `753b6709e0c6b12cbe7c1faa584cbf5293bac928c0830d81734eb7441b706aff`.
