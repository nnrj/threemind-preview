# Time-comparison evidence / 时间对照证据

> **修订 r2 · 2026-10-10**
> 修订原因：生成证据移出 Git 并完成校验归档；追加位置登记，保留原字节与结论。
> 原版：[README.md](README.md)；父版本 r1：[README.md](README.md)


**Status: partially completed, stopped at the registered per-process deadline. No further experiment is authorized by this README.**

- [中文报告](report.md) / [English report](report.en.md)
- [计算前方案](protocol.md)、[输入原文与逐帧脉冲](/api/v2/storage/research-artifacts/research-artifact:decf38ee925df7c7ffafb3dc/content)、[实现与参数](implementation.json)
- [时间与调用控制](diagnostics.json)、[已完成组的全部排名](analysis.json)
- [中止清单](stop.json)、[中止文件的明确标记与可读前缀](/api/v2/storage/research-artifacts/research-artifact:8daec7ca0262c495edf5d5f9/content)
- [前后验证](verification-prepublish.json)；归档后的验证见`verification.json`。
- `platform.json`标明项目、笔记、记录、报告、附件及导出ID。旧源码、全节点轨迹、完整检查点均在数据库证据包中，本地位于`.work/time-comparison-20260910/`，不扫描`data/`。

源码依据为Git97d8592的四个旧模块原始字节，另保存旧manager作核对；当前实现身份为causal/9、state/6。没有对旧存档作新版转换，也没有更新旧研究项目。固定课程与run.py的字节摘要在platform.json中。

`run.py prepare`创建独立项目并写入事先笔记，已有项目时拒绝覆盖。`run.py diagnostic`执行小型时间控制，`run.py train GROUP SEED VERSION`执行一个注册组。未来若用户授权恢复，应使用`supervise.py`管理自己的Windows进程树、保持资源上限；它是在发现Windows虚拟环境启动器可能再派生Python进程后补充的保护器，不改变原实验run.py，也没有被用来重跑此次中止组。

本轮实际调用：`run.py launch diagnostic`、`run.py launch train pair 41701 legacy`、`run.py launch train pair 41701 current`、`run.py launch train dialogue 41701 legacy`。最后一项180秒超时。旧进程已经退出。训练检查点完整，但无输入观察gzip文件不完整，不能把文件存在视为完成。

`analyze.py`、`finalize.py`只读已有数据，分别计算指标和整理中止证据／图表；不执行任何模型。`publish.py`只对本项目自己创建的发布作业写入证据和文档，不启动通用worker。导出、gzip/ZIP检查与源文件哈希见验证记录。

如需重新完整复现，应创建新的研究目录／项目，保留本轮原始证据，不删除输出后就地重跑。若只继续第一阶段，优先复用已保存的旧对话训练状态，另建有界观察作业；需要先获得用户对资源中止后的继续决定。


## 数据位置修订

选定的生成证据已逐字节校验归档。原报告、评判标准、结论及数据内 source_commit 均保留。以下逻辑下载需要当前主机管理员身份，数据目录未整体公开。

`data/experiments/2026-09-10-time-comparison/`

[Location and hash index / 位置及哈希登记](../../artifact-index/2026-10-09-relocations.json)

- [inputs.json](/api/v2/storage/research-artifacts/research-artifact:decf38ee925df7c7ffafb3dc/content) — 1098730 B; SHA-256 `b3830d63232dd7919e64bb9e88d13add43b752c461b620f2ce6ae3d544ce32aa`.
- [partial-prefix.json](/api/v2/storage/research-artifacts/research-artifact:8daec7ca0262c495edf5d5f9/content) — 553539 B; SHA-256 `ed2eaa057d5aab138fb28b13e56435f6deb68b4e7d88c64fcdca5ab6046d7043`.
