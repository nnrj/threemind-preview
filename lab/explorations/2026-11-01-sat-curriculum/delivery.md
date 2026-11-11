# SAT v2交付核验 / Delivery verification

2026-11-01。本批已完成 / Completed.

- Project: `7137e322-c160-424e-8832-55b29111fd31`
- Record: `9219955f-127c-5196-95db-fa62081ca9b8`
- API: **completed / verified / pending=0**
- Original resource: `sat-curriculum-20261101-v2`
- Directory: `E:/ThreeMindData/experiments/2026-11-01-sat-curriculum/v2`
- First archive for study v2: `originals-v1.zip`, 93,480,050 bytes; SHA256 `cbc38f7f964b9238ca5fd978da0d87d610a3e0fce1b58846f874614a09196313`.
- 2169 original members plus embedded manifest verified byte-for-byte; the entire archive was downloaded again through the local API. Four protocol/report documents also match their full source text. / 原包全部成员及四份双语协议、报告均完整读回。

## 训练与结果 / Training and findings

8 paired origins, 16 students; genuine /5.1, unchanged defaults and half-life. Every student: 112 demonstrations, dense-to-sparse 2/6/18-second added review gaps, 192 unassisted calibration questions, 4800 continuous personal Transformer updates, initial teaching plus three review/retest cycles. Each question spans 1 second, 20 raw frames, 8 selected frames. All final local decisions are correct: 27312/27312 in each learned arm. No actual local mistakes required correction in the formal cohort; that code path was tested in isolated apparatus.

Normal 162/192; shuffled 162/192; random 103/192; matched-information zero-break rule 162/192; WalkSAT 168/192. G1 passes (+30.73 percentage points versus random, 97.5% interval 21.35–39.06), G2 fails (normal minus shuffled 0), G3 passes (all witnesses valid). Normal and shuffled each match the rule baseline's 208 full action trajectories. [中文结论](report.zh.md) / [English conclusions](report.en.md).

## 存储实测 / Measured storage

Win32 FileStandardInfo measurements, unique volume/file identity deduplication; no multiple-hardlink paths were observed. Directory/NTFS metadata overhead is excluded. / 区分逻辑长度与实际分配，不用路径长度之和冒充磁盘占用。

|Category / 类别|Logical bytes / 逻辑字节|Unique allocated bytes / 去重实际分配|
|---|---:|---:|
|originals_and_metadata|100,445,342|104,311,408|
|archive|93,480,050|93,483,008|
|api_readback|93,480,050|93,483,008|
|Total / 合计|287,405,442|291,277,424|

Total allocated: 277.78 MiB, including originals, archive and independent API readback. / 合计包括原件、归档及独立读回副本。

For each of 16 final students, the complete resumable dependency closure has 8 files: checkpoint, current reader weights/Adam-RNG/manifest, and four persistent calibration datasets. Checkpoint bytes: 21,164–21,234; decoded state JSON: 86,932–87,408; **whole-student logical bytes: 617,387–632,422**, actual allocation: 627,112–643,496. / 单一检查点文件不冒称完整个体；完整个体计入其全部个人外设与学习数据依赖。[Detailed snapshot / 明细](storage-summary.json).

## Continuity and review / 连续性与审阅

1040 final trajectories, 480 whole-state/input transitions, 54624 final temporal predictions and 1792 demonstrations were audited. Saved-reader replay reproduces every final output exactly. Scientific runtime 20.02 minutes, peak process private memory 1.662 GiB. The initial complete-birth pause and exact STOP were archived; the separately hashed 2 GiB host allowance retains 5/4/5/25 GiB system reserves. No lost internal time, ordinary rollback, Core change or half-life change.

Review was performed by the assistant, including independent arithmetic and full bilingual text review; it is not labeled human or external replication. Old v1 received dated bilingual corrections with its completed status and archive hash preserved. E69/E67/E68/M4/M6/M7, automations and author manuscripts remain untouched. No follow-up batch starts automatically.

[Protocol](protocol.en.md) · [Whole audit summary](summary.json) · [Host amendment](host-budget-note.zh.md) · [v1 correction](v1-procedure-correction.zh.md).
