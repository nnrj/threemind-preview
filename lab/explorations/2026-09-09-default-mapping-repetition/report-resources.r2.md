> **修订 r2 · 2026-10-10**
> 修订原因：生成证据移出 Git 并完成校验归档；追加位置登记，保留原字节与结论。
> 原版：[report-resources.md](report-resources.md)；父版本 r1：[report-resources.md](report-resources.md)

## 资源与验收

- 固定预算：新增4 GiB、累计实验计算30分钟，达到3 GiB先停止计算并留发布余量；账户66%起始、84%停止。
- 本轮实验进程计时 **20.72分钟**，包含训练、测量和相关数据库操作，不含报告编写。
- 进程采样最大RSS **194.74 MiB**；这不是整机内存峰值或未采样瞬间的保证。
- 发布前数据库增长 **365.67 MiB**，本地证据 **9.28 MiB**；发布后的最终数值见`acceptance.json`。
- 10条教学意识、8820次实际教学输入、44个恢复点、132个测量任务、588个提示/无提示副本。
- 最近额度观测66%，起始66%；账户级读数可能滞后且包含其他任务。最终记录见`quota-monitor.json`。
- 1912条既有实验意识及其所在项目笔记/记录/报告头摘要未改变；未清理旧数据。产品源码和原生二进制摘要一致，感官与内核完整默认配置一致。
- 逐条输入、所有恢复点与测量来源摘要已校验；固定首种子的正常/交叉家系、连续/出生共4个原始ZIP及其中所有最终模型和完整活动采样已抽检。其余ZIP保留可审计，但不声称逐个解压检查过。
- 仅运行本轮自有任务，不启动通用worker领取其他任务。不声称做过本轮未执行的浏览器交互验收。

平台内保存方案笔记、3份实验记录、关联报告、结果笔记以及Markdown/HTML导出；`evidence-index.json`连接原始ZIP、恢复点和输入核验，`implementation.json`固定实际实现身份。


## 数据位置修订

选定的生成证据已逐字节校验归档。原报告、评判标准、结论及数据内 source_commit 均保留。以下逻辑下载需要当前主机管理员身份，数据目录未整体公开。

`data/experiments/2026-09-09-default-mapping-repetition/`

[Location and hash index / 位置及哈希登记](../../artifact-index/2026-10-09-relocations.json)

- [measurements.json](/api/v2/storage/research-artifacts/research-artifact:dbfff82fe099b76a2bd3de00/content) — 683222 B; SHA-256 `cf7e579516363d0af8efaa2d1050586a51078fc602dd6e0e2c87cca8b1ed568b`.
- [raw-activity-differences.json](/api/v2/storage/research-artifacts/research-artifact:ee9d13d05f5136dd41cac98d/content) — 176450 B; SHA-256 `99ce5441b9563dde3045f63f7b7eb1b65ca0eec5bfbd6692606e5d225e2f4dd2`.
- [time-courses.json](/api/v2/storage/research-artifacts/research-artifact:943f9d7ab9ccc620ab61f098/content) — 967982 B; SHA-256 `8c4d20babadaf773793c4128ebf1dc1bdf024e66b3d3446418c68e1a2b9122b1`.
- [training-traces.json](/api/v2/storage/research-artifacts/research-artifact:181fcc88fa99d7496f49f41e/content) — 1988076 B; SHA-256 `b0c110b1d394729042b1c271c5aca78dd48772dae977d521745bc3ef04babed9`.
