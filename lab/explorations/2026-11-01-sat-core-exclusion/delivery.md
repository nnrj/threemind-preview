# SAT v3: verified delivery / 已核验交付

2026-11-01. **Completed, verified, pending=0.** [中文报告](report.zh.md) · [English report](report.en.md) · [Frozen Chinese protocol](protocol.zh.md) · [Frozen English protocol](protocol.en.md).

## What was completed / 完成范围

Eight independently developed v2 parent origins; 64 registered research branches and 24 algorithm baseline conditions. All 88 conditions completed. All six registered Q1–Q4 verdicts pass. Intact Core, untrained Core, no-Core relay/template, fresh no-Core readers and the direct zero-break rule each solve 161/192 and reproduce all 208 full intact trajectories. Both constant-input controls solve 103/192. Complete data and the adverse attribution result for Core-specific SAT learning are retained.

Independent arithmetic code verified 2288 trajectories, 1728 complete-state transitions, 258748 probe/final predictions and 1024 calibration-stage development predictions, with maximum reproduced-logit error 0.0. Ten isolated apparatus checks and four arithmetic checks passed. This is assistant execution and verification through separate code paths, not external-researcher replication.

## Originals, lineage and API readback / 原件与回读

- Data resource: `sat-core-exclusion-20261101-v1`.
- Work: `E:/ThreeMindData/experiments/2026-11-01-sat-core-exclusion/v1`.
- Project: `114851bb-fed4-4508-9b8e-898a8e0098a4`; record: `fd28c3a2-6ba3-5541-b49b-7551b3a5e4da`.
- Archive: `originals-v1.zip`, **136,542,318 bytes**, 5066 original members plus its embedded manifest.
- SHA256: `45c1d58687199d561fdb18527d023f520253e3c326908dae0c813529e04b547b`.
- An independent full download at `readback/originals-v1.zip` matches that SHA256; every archived member's size and SHA256 were checked. The two protocols and two reports were also read back with exact text equality.
- Receipts: `publication/completion.json`, `final-verification.json`, `download-receipt.json`, `document-readback.json`.
- Reviewed code/report hashes: [publication-review.json](publication-review.json). Scientific runner and original source hashes: data `runner-manifest.json` and `frozen/`; postprocessing dependencies are retained under `postprocessing/repo/` with their repository-relative paths.
- Old parent state and dependency files are preserved and hashed in `parents-manifest.json`. Old v1/v2 archives remain unchanged. The separate `postprocessing/parent-boundary-review.json` verifies all 16 final teaching/test boundary edge counts (zero) without advancing any subject.

The scientific `status.json` intentionally retains its historical `awaiting-analysis` snapshot. The later publication completion receipt is authoritative for delivery. **Do not run a completed scientific batch again.** This archive includes all positive and negative arms; it does not overwrite the earlier SAT reports.

## Resources / 时间、内存及存储

Scientific host elapsed time: **64.95 minutes**, including training, trajectories and complete-state recording; this excludes later analysis and publication. Peak host private memory: **1.720 GiB**. The lowest observed available commit / RAM / C: / E: values were **7.62 / 10.11 / 9.51 / 102.55 GiB**. The 5 / 4 / 5 / 25 GiB reserves were unchanged; there was no resource STOP or orphaned in-flight state.

Final storage snapshot, 2026-11-01T13:19:01.305018+08:00:

|Storage group|Files|Logical bytes|Unique allocated bytes|
|---|---:|---:|---:|
|originals_and_metadata|5087|157,623,510|168,012,824|
|archive|1|136,542,318|136,544,256|
|api_readback|1|136,542,318|136,544,256|
|Total|5089|430,708,146|441,101,336|

Total: **410.76 MiB logical / 420.67 MiB allocated**. NTFS allocation was measured with Win32 FileStandardInfo and volume/file-identity deduplication. No multiply linked paths were present. Directory and filesystem metadata are excluded, as is the measurement file written after its own snapshot. [Compact storage summary](storage-summary.json); full 64-branch detail is in `publication/storage-after.json`.

A complete final branch closure occupies **294,828–625,962 logical bytes** (**299,424–639,400 allocated bytes**), including the saved state and its reader weights, optimizer/RNG, retained samples and required templates. Shared dependencies overlap between branches; closure sizes must not be added as independent allocated storage. Frozen source is recorded separately. Checkpoint-file size alone is not the complete subject size.

## Cleanup and continuation / 收尾与后续

The scientific host exited normally. After verified delivery, only this task's API-only service and launcher were closed after PID, creation-time and exact-command checks; `publication/service-cleanup.json` records this. The user's existing PostgreSQL process remained alive and untouched. Current available E: space at the final snapshot was 102.29 GiB.

R42, bilingual chronology/theme/source records and both Classical Chinese adaptations carry the explicit result. Old experiments and automations remain unchanged; no next experiment is started. Production Core, half-life settings, earlier subjects and author manuscripts are unchanged. Follow-up on history-dependent SAT design or retention requires its own stated question and protocol.
