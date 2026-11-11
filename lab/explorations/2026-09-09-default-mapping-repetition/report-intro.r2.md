# 默认映射复验：逐句20次与完整标点

> **修订 r2 · 2026-10-10**
> 修订原因：生成证据移出 Git 并完成校验归档；追加位置登记，保留原字节与结论。
> 原版：[report-intro.md](report-intro.md)；父版本 r1：[report-intro.md](report-intro.md)


2026-09-09。平台项目：默认映射复验：逐句20次与完整标点 · 2026-09-09。
项目编号：`a9bd83bb-3d57-4eab-859d-68312f6b2b17`。

本次按用户纠正重新实验：完整原句由发送层原样提交，现有默认感官继续执行NFKC。没有为标点改变映射器、感官参数或内核。上一轮关闭NFKC是执行条件错误，旧记录保留但不作为本轮条件的证据。

下面的“目标领先”是外部词模板相关活动超过其他候选，不能自动解释为意识生成了该文字答案。连续状态是主观察；结构出生副本清空活动后再激活，必须分开理解。配对/问答的平均量是目标减另一个候选；家系平均量是角色区分量，不是准确率。

## 最终观察汇总

| 教学 | 观察方式 | 项目 | 目标严格领先/可评分 | 总提示数 | 并列 | 种子平均量 |
| --- | --- | --- | --- | --- | --- | --- |
| 原对应 | 连续状态 | 配对 | 0/8 | 8 | 8 | 0 |
| 原对应 | 结构出生副本 | 配对 | 8/8 | 8 | 0 | 0.0001057436485 |
| 原对应 | 连续状态 | 问答 | 0/16 | 16 | 16 | 0 |
| 原对应 | 结构出生副本 | 问答 | 15/16 | 16 | 1 | 0.0001563656276 |
| 原对应 | 连续状态 | 未见家系 | 0/6 | 8 | 6 | 0 |
| 原对应 | 结构出生副本 | 未见家系 | 2/6 | 8 | 1 | -1.346165325e-05 |
| 家系互换 | 连续状态 | 未见家系 | 0/6 | 8 | 6 | 0 |
| 家系互换 | 结构出生副本 | 未见家系 | 1/6 | 8 | 0 | -3.29468362e-05 |
| 名词互换 | 连续状态 | 配对 | 0/4 | 4 | 4 | 0 |
| 名词互换 | 结构出生副本 | 配对 | 4/4 | 4 | 0 | 0.0001333653798 |
| 名词互换 | 连续状态 | 问答 | 0/8 | 8 | 8 | 0 |
| 名词互换 | 结构出生副本 | 问答 | 8/8 | 8 | 0 | 0.0001739960172 |

完整候选数值、阶段变化、对照及方法限制在以下记录中；无法评分不填零，并列不计为严格领先。


## 数据位置修订

选定的生成证据已逐字节校验归档。原报告、评判标准、结论及数据内 source_commit 均保留。以下逻辑下载需要当前主机管理员身份，数据目录未整体公开。

`data/experiments/2026-09-09-default-mapping-repetition/`

[Location and hash index / 位置及哈希登记](../../artifact-index/2026-10-09-relocations.json)

- [measurements.json](/api/v2/storage/research-artifacts/research-artifact:dbfff82fe099b76a2bd3de00/content) — 683222 B; SHA-256 `cf7e579516363d0af8efaa2d1050586a51078fc602dd6e0e2c87cca8b1ed568b`.
- [raw-activity-differences.json](/api/v2/storage/research-artifacts/research-artifact:ee9d13d05f5136dd41cac98d/content) — 176450 B; SHA-256 `99ce5441b9563dde3045f63f7b7eb1b65ca0eec5bfbd6692606e5d225e2f4dd2`.
- [time-courses.json](/api/v2/storage/research-artifacts/research-artifact:943f9d7ab9ccc620ab61f098/content) — 967982 B; SHA-256 `8c4d20babadaf773793c4128ebf1dc1bdf024e66b3d3446418c68e1a2b9122b1`.
- [training-traces.json](/api/v2/storage/research-artifacts/research-artifact:181fcc88fa99d7496f49f41e/content) — 1988076 B; SHA-256 `b0c110b1d394729042b1c271c5aca78dd48772dae977d521745bc3ef04babed9`.
