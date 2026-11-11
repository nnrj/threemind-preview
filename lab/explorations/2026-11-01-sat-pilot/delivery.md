# 3-SAT交付核验 / Delivery verification

2026-11-01。本批计算、独立复算及本机科研记录均已完成 / Computation, independent arithmetic and local research registration are complete.

- Project: `7e0dbe00-99e4-4b28-afae-dd3e3cdac4d6`
- Record: `2c6ef182-21d2-5049-8678-236191df04b8`
- Resource: `sat-pilot-20261101-v1`
- Status: **completed / verified / pending=0**
- 原件 / Originals: `E:/ThreeMindData/experiments/2026-11-01-sat-pilot/v1`
- 完整包 / Archive: `originals-v1.zip`, **21,347,277 bytes**, SHA256 `d657cf7c8155a9fff54e77f95b85ce6e72d7e4f2d892fed27988ec0b5448b46f`.
- 包含3,232份原件，另加内嵌清单，共3,233个ZIP成员 / 3,232 original files plus the embedded manifest.
- 原包经本机科研API完整下载至`readback/originals-v1.zip`，全部字节及成员哈希一致 / Full loopback API download, byte hash and all member hashes verified.
- 中英文协议、报告共4份实际读回，文本完全一致 / All four protocol/report documents read back exactly.
- `publication/final-verification.json`、`publication/document-readback.json`、`publication/completion.json`保留回执 / Receipts retained.

## 资源 / Resources

| 项目 / Item | 逻辑字节 / Logical bytes | 分配字节 / Allocated bytes |
| --- | ---: | ---: |
| 原件及元数据 / Originals and metadata | 22,723,931 | 29,144,672 |
| 归档包 / Archive | 21,347,277 | 21,348,352 |
| API完整读回副本 / Full API readback | 21,347,277 | 21,348,352 |
| 合计 / Total | 65,418,485 | 71,841,376 |

使用Win32 FileStandardInfo测量，按卷/文件标识去除硬链接重复；本次共3254文件，无多硬链接、压缩或稀疏文件。分配量约68.51MiB，不包括目录及NTFS元数据开销。此为交付后存储快照，测量工具和汇总属于另附的派生元数据，没有修改已冻结的资料包。

Measured with Win32 FileStandardInfo, deduplicating volume/file IDs. There are 3,254 files, with no multiple hardlinks, compressed files or sparse files. Allocated storage is 68.51 MiB, excluding directory and NTFS metadata overhead. This post-delivery storage measurement supplements the frozen archive without changing it.

48份最终完整分支状态每份压缩后10492—10552字节，解压JSON为26390—26490字节，每份分配12288字节；包含Core、个人映射、固定读出定义、随机状态、背景游标、最近读出和问题环境状态。这是本批13节点小装置的完整状态，不能套作ThreeMind任意规模个体的内存需求。

The 48 final complete branch snapshots occupy 10,492–10,552 compressed bytes each, 26,390–26,490 decoded JSON bytes and 12,288 allocated bytes. They include Core, personal mapping, fixed readout, random state, background cursor, recent readouts and task environment. These sizes describe this small apparatus, not arbitrary ThreeMind individuals.

## 研究结果 / Scientific result

G1 FAIL：正常和打乱教学均98/192；G2 FAIL：目标静默使零破坏选择率降低0.829个百分点，低于预设20点；匹配变化0，恢复精确。WalkSAT 172/192，在八来源中全部胜出。该阴性应用结果与微小连接作用均保留，不追加训练、不改旧成绩。

G1 fails with 98/192 under both histories. G2 fails: target silencing reduces zero-break choice by 0.829 points, below 20; the matched change is zero and restoration exact. WalkSAT solves 172/192 and wins in every source. Both the negative application result and the small connection contribution are retained.

本次为执行助手的复算和审阅，不是作者人工复核或外部研究者复现。所有API操作仅在本机`127.0.0.1:8877`、本机数据库与E盘资源之间进行；原包没有发送到外部服务器。Core、旧原件、暂停的实验和自动接续、作者论文均未改。

Review and recalculation are by the executing assistant, not human-author or external replication. API operations remain on loopback, the local database and the E-drive resource; the archive was not sent to an external server. Core, historical evidence, paused studies/automations and the author's manuscript remain unchanged.

[中文报告](report.zh.md) · [English report](report.en.md) · [派生存储汇总 / storage summary](storage-summary.json)

[2026-11-01 G3比较范围补注 / Comparison-scope addendum](scope-note.md) — 原评分与首版报告不变 / Scores and first edition unchanged.

比较范围补注已另存本机科研记录并逐字读回；记录仍为completed/verified/pending=0，原归档不变。回执：`publication/scope-note-verification.json`。

The comparison-scope note was separately registered and read back exactly. The record remains completed/verified/pending=0; the original archive is unchanged. Receipt: `publication/scope-note-verification.json`.
