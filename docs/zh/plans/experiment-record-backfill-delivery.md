# 实验记录补全与统一研究总览交付

[English](../../en/plans/experiment-record-backfill-delivery.md) · [批准计划](experiment-record-backfill.md) · [使用手册](../research-records.md)

交付日期: 2026-10-10.

全部已识别的 **84 项来源索引**已正式补入本地数据库：69 个探索目录、13 组早期札记和 2 个只有平台来源的历史研究项目。它们不是 84 次完成的实验。执行状态为 {'completed': 67, 'unknown': 15, 'interrupted': 1, 'planned': 1}；资料状态为 {'indexed': 51, 'partial': 33}。66 项复用原项目，18 项明确建立后来的平台登记身份。555 个原平台项目全部盘点，其中 489 个开发／界面验收项目不列入正式研究总览，原项目不删除。

优先完成 E64～E66、原 `/3`、修复 `/3`、文字遥测与完整 `/2` 对照、`/4`，随后处理全部其余来源。全局总览默认跨项目检索；“V2 功能验收”项目原本没有报告和笔记，与其他项目已有出版记录是不同事实。近期四组保持研究确有漏登记，现已补入。AI 与人工记录要求相同，原脚本科研记录继续保留。

## 保存与核验

- 第 62 版数据库迁移已显式执行；没有启动时偷偷升级。
- 完整数据库备份 47,712,433,106 字节，SHA-256 `77d9500a03be20557f3eef2984fb06f3d2177eee7d4d767b1faf085cd6ff7139`，保存在 `D:/ThreeMindBackups/research-records-20261010`。新建临时恢复库完整恢复并核验后已删除；仅新备份的 E 盘副本在 D 盘全哈希复验后移除。已有实验原件未移动。
- 写入前后原有 **20,581 运行、24,821 检查点、420 报告／记录头及 470 固定版本、521 笔记及 605 固定版本、3,615 附件**的身份、状态、版本及哈希见证一致。7,914,970 观察、1,641,459 输入封套、1,867,146 输入帧、10,944,441 边及附件分块计数一致。没有新增历史运行或复制大附件。
- 共关联 59,118 证据引用，其中原件／旧固定版本／运行引用 58,974，新增小正文引用 144；包含 19,310 原生运行身份及配置。自定义脚本的个体、条件、逐阶段过程仍在已登记的原始载体中，不伪造为平台运行表，也不将 Core 单独状态冒称整个体恢复。结构指标与旧阴性结论不重新解释。
- 所有实际文件绑定均核对固定清单的大小和 SHA-256；原生固定版本及附件复用，29 个既有存储资源登记逐项不变。结项的 `indexed` 是登记核验范围，不声称重新复算全部科研数据。已结项补录重试核对数据库完成回执，重新核验当前原件使用独立 `verify --hashes`。私人笔记按作者权限查看、打包和再导入。

数据库索引与原件引用、条目、回执等七张新表实际占用 **126,869,504 字节（120.99 MiB）**；新小正文逻辑 JSON 共 **391,480 字节**，报告／协议 30 修订、笔记 114 修订。原有原件继续占用原位置，引用字节总和包含重叠，不能当作新增空间或实际磁盘占用。新增大原件复制量为 **0**，完整备份本身另计约 44.44 GiB。

## 接口与后续入口

REST、`threemind records` CLI、现有 MCP `records.*` 目录、Python `ResearchRecorder` 和人工 UI 共用规范保存服务。人工运行、配对、发育、生态、定向选择及评估在任务可见前登记；维护中的平台研究脚本和发布器同步个体、阶段、报告、修订和证据。历史冻结脚本未改、未重跑。

稳定请求 ID、内容哈希和同事务回执保护重试。数据库中断保留本地待同步请求；原件不能可靠写入则停止宿主继续推进。登记、查询、核验没有刺激或学习接口。按实验的正式包保存报告修订、私人权限和只读运行依赖；导入、再导出及再次导入保留原始状态表成员，不伪造历史运行。

## 验收和剩余边界

- 新记录验收 10 项、受影响接口／报告／笔记／数据库／操作目录 28 项、既有资料包与备份 23 项、存储登记及迁移 40 项通过；适配器重试、本地回执丢失恢复、冲突拒绝及 CLI／HTTP 回执改动另复验通过。前端生产构建通过。
- 只读验收服务核对全局 84 项，E64～E66、N01 和保持对照可查，原项目空页可返回全局；原笔记、英文及 390px 窄屏通过，无浏览器运行错误。验收服务不启动 worker、不执行写请求，完成后关闭。
- 逐项核对全部 84 项的详情、数据库结项回执与一个原件预览。有原小正文时读取原文；缺原报告／笔记的旧项目读取原运行元数据，不加载模型、不把后来说明冒称原文，也不将这次抽样称为重读所有大型原件。
- 同输入的 `/4` 在四阶段穿插记录和只读核验，完整 Core 哈希始终与无记录对照相同。这是工程不干预验收，不是新学习实验。
- 50 条隔离阶段记录：持久入队 p50/p95 17.19/19.19ms；保存及回执 p50/p95 52.54/56.31ms。测量时后台正在恢复大备份，不能当作 Core 求解成本；正文共 2,790 字节，没有模型运算或大原件复制。
- 扩展宿主回归中，另有 25 项通过、6 项已有发育／选择／评估出生失败：`threemind_runtime/inheritance.py` 仍生成已废弃的 `/3` `blocked/charge/cursor` 状态。重新构建 native 扩展后仍能复现，不能称完全验收这些出生流水线。另发现 `Database.save_checkpoint` 假定全局 `state_time_us`，而 `/4` 保存局部锚点，会报缺字段。这两处旧宿主问题单列待修，本期未改 Core、出生／继承或检查点语义；正式补录不调用这些路径。
- 既有正式包容量、依赖闭包与磁盘预留仍有效；小包往返已验，不声称所有巨大历史实验都能一包无限制导出。可缩小选择或保存原完整归档。真实云端未使用。

## 全量台账与缺项

以下 N01～N13 是本次新增的检索标签，分别对应原札记 001～013，已追加说明，不是恢复的旧实验编号。E50 原项目、其后局部图表达和撤回项目分别登记。四视场草案不是已执行的 E64，编号后来用于中央重启；该草案保留 `planned`。

缺项反映现有证据范围。缺独立事前协议时不以后来笔记替代；缺原过程或检查点时不能重建旧状态；新平台身份不冒称恢复的旧身份；缺内核身份时不填当前默认。早期执行状态未知保持未知。原文件未失效不等于当时所有信息已采集。

| 来源 | 执行状态 | 资料状态 | 原件／旧版／运行引用 | 原生运行身份 | 缺项 |
| --- | --- | --- | ---: | ---: | --- |
| `historical-project:3df399e5-649b-4040-b151-67a6bf278ec6` | unknown | partial | 4 | 0 | G01, G08 |
| `historical-project:532e9e84-9454-46ef-bcb5-b5d80ca8916f` | unknown | partial | 36 | 32 | G02, G05, G01, G07, G08 |
| [N01](../../../lab/zh/001_2026-07-25_2015_最小躯体三角结构.md) | unknown | partial | 2 | 0 | G03, G02, G04, G01, G07, G08 |
| [N02](../../../lab/zh/002_2026-07-27_0000_感官约束与全局饱和.md) | unknown | partial | 2 | 0 | G03, G02, G04, G01, G07, G08 |
| [N03](../../../lab/zh/003_2026-07-28_0000_V3重复激活签名与可读输出.md) | unknown | partial | 2 | 0 | G03, G02, G04, G01, G07, G08 |
| [N04](../../../lab/zh/004_2026-07-28_0000_长文本刺激的时间分帧.md) | unknown | partial | 2 | 0 | G03, G02, G04, G01, G07, G08 |
| [N05](../../../lab/zh/005_2026-08-01_0000_V3探针刺激收敛映射.md) | unknown | partial | 2 | 0 | G03, G02, G04, G01, G07, G08 |
| [N06](../../../lab/zh/006_2026-08-01_0055_关系探针复现与过度联想.md) | unknown | partial | 2 | 0 | G03, G02, G04, G01, G07, G08 |
| [N07](../../../lab/zh/007_2026-08-02_1246_从截面读出到时间区间证据.md) | unknown | partial | 2 | 0 | G03, G02, G04, G01, G07, G08 |
| [N08](../../../lab/zh/008_2026-08-03_2152_V3时序读出候选语序收敛.md) | unknown | partial | 2 | 0 | G03, G02, G04, G01, G07, G08 |
| [N09](../../../lab/zh/009_2026-08-03_2202_快慢时间尺度与证据链.md) | unknown | partial | 2 | 0 | G03, G02, G04, G01, G07, G08 |
| [N10](../../../lab/zh/010_2026-08-03_2239_连续长文本流下的迁移激活.md) | unknown | partial | 2 | 0 | G03, G02, G04, G01, G07, G08 |
| [N11](../../../lab/zh/011_2026-08-03_2327_关系端点再激活与响应簇.md) | unknown | partial | 2 | 0 | G03, G02, G04, G01, G07, G08 |
| [N12](../../../lab/zh/012_2026-08-04_0014_多关系局部结构共存.md) | unknown | partial | 2 | 0 | G03, G02, G04, G01, G07, G08 |
| [N13](../../../lab/zh/013_2026-08-04_0041_传递关系未涌现与类比触达.md) | unknown | partial | 2 | 0 | G03, G02, G04, G01, G07, G08 |
| [E04](../../../lab/explorations/2026-09-09-blocked-sentence-teaching/report.md) | completed | indexed | 394 | 10 | — |
| [E02](../../../lab/explorations/2026-09-09-calibrated-generalization/report.md) | completed | indexed | 3004 | 977 | — |
| [E05](../../../lab/explorations/2026-09-09-default-mapping-repetition/report.md) | completed | indexed | 400 | 10 | — |
| [E03](../../../lab/explorations/2026-09-09-language-scaffold-relations/report.md) | completed | indexed | 258 | 25 | — |
| [E01](../../../lab/explorations/2026-09-09-memory-relations/report.md) | completed | indexed | 946 | 900 | — |
| [E09](../../../lab/explorations/2026-09-10-host-background-pair/report.md) | completed | partial | 168 | 4 | G01 |
| [E08](../../../lab/explorations/2026-09-10-pair-no-punctuation/report.md) | completed | indexed | 204 | 6 | — |
| [E06](../../../lab/explorations/2026-09-10-temporal-repetition/report.md) | completed | indexed | 217 | 10 | — |
| [E07](../../../lab/explorations/2026-09-10-time-comparison/report.md) | interrupted | indexed | 54 | 0 | — |
| [E10](../../../lab/explorations/2026-09-29-candidates/report.zh.md) | completed | indexed | 3273 | 3229 | — |
| [E11](../../../lab/explorations/2026-09-29-continuous-mechanisms/report.zh.md) | completed | indexed | 378 | 341 | — |
| [E15](../../../lab/explorations/2026-09-29-experience-and-autonomy/report.zh.md) | completed | indexed | 842 | 802 | — |
| [E13](../../../lab/explorations/2026-09-29-input-rate-and-autonomy/report.zh.md) | completed | indexed | 511 | 448 | — |
| [E14](../../../lab/explorations/2026-09-29-internal-activity/report.zh.md) | completed | indexed | 217 | 180 | — |
| [E16](../../../lab/explorations/2026-09-29-mechanism-calibration/report.zh.md) | completed | indexed | 825 | 787 | — |
| [E12](../../../lab/explorations/2026-09-29-memory-timescales/report.zh.md) | completed | indexed | 640 | 598 | — |
| [E19](../../../lab/explorations/2026-09-30-intensity-mechanisms/report.zh.md) | completed | indexed | 1285 | 1246 | — |
| [E18](../../../lab/explorations/2026-09-30-memory-transfer/report.zh.md) | completed | indexed | 1580 | 1536 | — |
| [E17](../../../lab/explorations/2026-09-30-stimulus-spacetime/report.zh.md) | completed | indexed | 328 | 295 | — |
| [E23](../../../lab/explorations/2026-10-01-observation-background/report.zh.md) | completed | indexed | 541 | 502 | — |
| [E21](../../../lab/explorations/2026-10-01-order-mechanisms/report.zh.md) | completed | indexed | 2941 | 2880 | — |
| [E20](../../../lab/explorations/2026-10-01-priority-memory/report.zh.md) | completed | indexed | 2910 | 2808 | — |
| [E22](../../../lab/explorations/2026-10-01-recovery-reference/report.zh.md) | completed | indexed | 1590 | 1520 | — |
| [E25](../../../lab/explorations/2026-10-02-response-readout/report.zh.md) | completed | partial | 21 | 0 | G01 |
| [E26](../../../lab/explorations/2026-10-02-robot-language/report.zh.md) | completed | indexed | 19 | 0 | — |
| [E27](../../../lab/explorations/2026-10-02-survival-transfer/report.zh.md) | completed | indexed | 36 | 0 | — |
| [E24](../../../lab/explorations/2026-10-02-target-background/report.zh.md) | completed | indexed | 215 | 160 | — |
| [E31](../../../lab/explorations/2026-10-03-ocean-behavior/report.zh.md) | completed | indexed | 9665 | 0 | — |
| [E30](../../../lab/explorations/2026-10-03-ocean-causality/report.zh.md) | completed | indexed | 46 | 0 | — |
| [E32](../../../lab/explorations/2026-10-03-ocean-community/report.zh.md) | completed | indexed | 2984 | 0 | — |
| [E29](../../../lab/explorations/2026-10-03-ocean-evolution/report.zh.md) | completed | indexed | 52 | 0 | — |
| [E34](../../../lab/explorations/2026-10-03-ocean-hunting/report.zh.md) | completed | partial | 5135 | 0 | G01 |
| [E33](../../../lab/explorations/2026-10-03-ocean-no-predation/report.zh.md) | completed | partial | 853 | 0 | G01 |
| [E28](../../../lab/explorations/2026-10-03-primitive-ocean/report.zh.md) | completed | indexed | 26 | 0 | — |
| [E42](../../../lab/explorations/2026-10-04-language-centre/report.zh.md) | completed | indexed | 58 | 4 | — |
| [E44](../../../lab/explorations/2026-10-04-language-development/report.zh.md) | completed | indexed | 98 | 0 | — |
| [E43](../../../lab/explorations/2026-10-04-language-spaced/report.zh.md) | completed | indexed | 50 | 0 | — |
| [E39–E40](../../../lab/explorations/2026-10-04-ocean-culture/report.zh.md) | completed | partial | 2334 | 0 | G01 |
| [E37](../../../lab/explorations/2026-10-04-ocean-enclosure/report.zh.md) | completed | indexed | 1869 | 0 | — |
| [E35–E36](../../../lab/explorations/2026-10-04-ocean-groups/report.zh.md) | completed | partial | 2548 | 0 | G01 |
| [E38](../../../lab/explorations/2026-10-04-ocean-species/report.zh.md) | completed | partial | 1934 | 0 | G01 |
| [E41](../../../lab/explorations/2026-10-04-ocean-split/report.zh.md) | completed | partial | 2054 | 0 | G01 |
| [E49](../../../lab/explorations/2026-10-05-bus-expression/report.zh.md) | completed | indexed | 61 | 0 | — |
| [E51](../../../lab/explorations/2026-10-05-clock-recollection/report.zh.md) | completed | partial | 22 | 0 | G01 |
| [E52](../../../lab/explorations/2026-10-05-coadaptive-language/report.zh.md) | completed | indexed | 82 | 0 | — |
| [E47](../../../lab/explorations/2026-10-05-expression-alignment/report.zh.md) | completed | indexed | 97 | 0 | — |
| [E50](../../../lab/explorations/2026-10-05-graph-expression/report.zh.md) | completed | partial | 87 | 0 | G01 |
| [E45](../../../lab/explorations/2026-10-05-language-calibration/report.zh.md) | completed | indexed | 145 | 0 | — |
| [E46](../../../lab/explorations/2026-10-05-native-language/report.zh.md) | completed | indexed | 90 | 0 | — |
| [E48](../../../lab/explorations/2026-10-05-temporal-state-expression/report.zh.md) | completed | partial | 142 | 0 | G01 |
| [E57](../../../lab/explorations/2026-10-06-choice-attribution/report.zh.md) | completed | partial | 31 | 0 | G01 |
| [E55](../../../lab/explorations/2026-10-06-grounded-reviews/report.zh.md) | completed | indexed | 52 | 0 | — |
| [E53](../../../lab/explorations/2026-10-06-ocean-communication/report.zh.md) | completed | indexed | 46 | 0 | — |
| [E54](../../../lab/explorations/2026-10-06-shape-color-pointing/report.zh.md) | completed | partial | 28 | 0 | G01 |
| [E56](../../../lab/explorations/2026-10-06-vision-correction/report.zh.md) | completed | indexed | 55 | 0 | — |
| [E59](../../../lab/explorations/2026-10-07-active-vision/report.zh.md) | completed | indexed | 34 | 0 | — |
| [E61](../../../lab/explorations/2026-10-07-body-exploration/report.zh.md) | completed | indexed | 158 | 0 | — |
| [E62](../../../lab/explorations/2026-10-07-continuous-development/report.zh.md) | completed | indexed | 49 | 0 | — |
| [E58](../../../lab/explorations/2026-10-07-embodied-memory/report.zh.md) | completed | indexed | 29 | 0 | — |
| [E60](../../../lab/explorations/2026-10-07-eye-hand-learning/report.zh.md) | completed | indexed | 89 | 0 | — |
| [E63](../../../lab/explorations/2026-10-07-rehearsal-centered/report.zh.md) | completed | indexed | 37 | 0 | — |
| [E66](../../../lab/explorations/2026-10-08-centered-correction-cycles/report.zh.md) | completed | indexed | 55 | 0 | — |
| [E65](../../../lab/explorations/2026-10-08-centered-learning/report.zh.md) | completed | indexed | 28 | 0 | — |
| [E64](../../../lab/explorations/2026-10-08-centered-restart/report.zh.md) | completed | indexed | 31 | 0 | — |
| [E64：从空白重现四视场成功流程](../../../lab/explorations/2026-10-08-four-field-reproduction/design.zh.md) | planned | partial | 3 | 0 | G06, G08 |
| [continuous-memory/3：自动保持与回收的实现验证](../../../lab/explorations/2026-10-08-retention-kernel/report.zh.md) | completed | partial | 1036 | 0 | G03 |
| [continuous-memory/3 局部保持修复：工程通过，默认保持增益仍不足](../../../lab/explorations/2026-10-08-retention-repair/report.zh.md) | completed | partial | 485 | 0 | G03, G05 |
| [物理遥测背景下，文字连接的重复、保持与消退](../../../lab/explorations/2026-10-08-retention-telemetry-text/report.zh.md) | completed | partial | 2325 | 0 | G03 |
| [/4 局部事件交付与保持校准](../../../lab/explorations/2026-10-09-local-events-v4/report.zh.md) | completed | partial | 108 | 0 | G03, G05 |

缺项定义（保持核验器的原始描述）：

- **G01**: {"kind": "declared-gap", "message": "Kernel identity is not established in the index; original configurations are preserved and no current default is substituted."}
- **G02**: {"kind": "declared-gap", "message": "No independently preserved preregistered protocol identified; later notebooks/reports are not substituted for it."}
- **G03**: {"kind": "declared-gap", "message": "No original platform project identity identified; this is a later platform registration. Original case/checkpoint identities remain in their carriers."}
- **G04**: {"kind": "declared-gap", "message": "No original process/checkpoint carrier identified; descriptions cannot reconstruct missing model states."}
- **G05**: {"kind": "declared-gap", "message": "No original scientific notebook identified."}
- **G06**: {"kind": "declared-gap", "message": "Unstarted conditional draft; no execution data should exist. E64 was reassigned to centered restart."}
- **G07**: {"kind": "missing-role", "role": "protocol"}
- **G08**: {"kind": "missing-role", "role": "report"}

固定盘点 SHA-256: `9ba6effd505461fba7e89150c008461c7020ecc2fa8ac51865bba1027f2f1f74`. [机器可读台账](../../../lab/artifact-index/2026-10-10-research-record-backfill.json)。完整固定预览、每批回执、缺项和写库前后见证在 `data/records-backfill-20261010/`；不提交大原件。恢复见证与原存储登记备份随 D 盘备份保存。
