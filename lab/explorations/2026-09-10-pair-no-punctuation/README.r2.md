# 无标点配对实验 / Unpunctuated pairing study

> **修订 r2 · 2026-10-10**
> 修订原因：生成证据移出 Git 并完成校验归档；追加位置登记，保留原字节与结论。
> 原版：[README.md](README.md)；父版本 r1：[README.md](README.md)


- [中文报告](report.md) / [English report](report.en.md)
- **[完整时序窗末强度排名](/api/v2/storage/research-artifacts/research-artifact:f20fa842d9b81f7f4801c22d/content)**：180窗口、7,892节点记录；可在浏览器打开。
- [事先方案](protocol.md)、[准确课程](curriculum.json)、[默认配置及观察不干扰验证](preflight.json)
- [实现哈希](implementation.json)、[外部模板与覆盖](mapping.json)、[分析数据](/api/v2/storage/research-artifacts/research-artifact:4c4e387528bf65d35cef0e45/content)
- [逐输入、检查点、测量来源清单](evidence-index.json)、[最终验收](acceptance.json)

`platform.json`记录新项目、笔记、原生记录／报告、来源快照及导出ID。完整训练和测量证据存入该项目，较大的本地副本位于`.work/pair-no-punctuation-20260910/`；完整`node-rankings.jsonl`与`implementation-source.zip`也作为附件落库，避免将大文件反复纳入Git。

入口：`run.py prepare`固定原文、默认映射、预案及独立项目；`run.py supervise 41701`（以及41702、41703）顺序执行对应种子。每个监督器只管理自己创建的进程树。已有种子日志或结果时拒绝覆盖，复现应建立新项目／目录，不能清除旧证据后冒充同一次实验。

实际复用前轮研究脚本中的数据库输入、保存、探针及验证流程，依赖摘要已经记录；所有依赖字节仍可由Git取得。Core和平台代码未变。新增脚本仅用于本实验，不改变感官参数、主要读出分类或窗口结束策略。

`analyze.py`读取已冻结证据，保存全节点窗末排序及预先外部参照；`verify.py`核对真实数据库输入、默认感官转换、递送时间、完整状态继承和资源；`make_report.py`从结果生成图表与只读HTML查看器；`publish.py`将记录与报告接入既有平台。它们不会将分析结论写回意识。

本轮6个教学意识、15个检查点、2,400条教学输入、180个时序副本；次要固定窗口另有72个显式副本与12个原工具无输入基线。全部阶段完成。报告中的收敛并列不被当作配对成功，也不被改写为没有发生学习。


## 数据位置修订

选定的生成证据已逐字节校验归档。原报告、评判标准、结论及数据内 source_commit 均保留。以下逻辑下载需要当前主机管理员身份，数据目录未整体公开。

`data/experiments/2026-09-10-pair-no-punctuation/`

[Location and hash index / 位置及哈希登记](../../artifact-index/2026-10-09-relocations.json)

- [analysis.json](/api/v2/storage/research-artifacts/research-artifact:4c4e387528bf65d35cef0e45/content) — 3795093 B; SHA-256 `d9a4e8127b594cd399f6097ff4c4972bcaa50e673da3b3f7114432b4f5f040a1`.
- [instrumentation-source.zip](/api/v2/storage/research-artifacts/research-artifact:b4d8f1b02bcaa70dab0976c2/content) — 22059 B; SHA-256 `f217c58d8c8048bc6912b50f6a296d2066aa60ba73bb459f3d51651758f93614`.
- [rankings.html](/api/v2/storage/research-artifacts/research-artifact:f20fa842d9b81f7f4801c22d/content) — 547699 B; SHA-256 `6ab90559b66b93e744104698b2a676e0015eff522ec5112e6380e34cfc17dced`.
