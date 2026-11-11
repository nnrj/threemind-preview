# October 10, 2026: storage relocation and cleanup boundaries

[中文](../../../zh/history/sources/2026-10-10-storage-root.md) · [Volume XI](../chronicles/11-data-management.md)

Recorded October 10, 2026 from visible messages. Earlier undated messages are not assigned invented event times. Quotation, translation, approval and engineering evidence are distinct; no credentials/private attachments are included.

## Original quotations and translations

> 默认数据目录仍是项目下的 `data`；本次迁移目标为 `E:\ThreeMindData`。

Translation: default project data; this migration targets E:\ThreeMindData.

> **默认保留源副本。** 源副本清理另出精确预览，不混入位置切换，也不将复制成功宣称为已经释放磁盘空间。

Translation: retain sources; separate exact cleanup from switching and do not call copying reclaimed space.

> 你可正常规划，我在实施计划前，会完成清理使得空间够用。此前的重构和迁移中，是不是有啥备份留着没删除，可以告诉我，我来手动删除或者进入UI界面进行清理。我记得以前有90多GB空闲？

Translation: the user will clear space and requests retained-backup identification for manual/UI cleanup, recalling over 90 GB free.

> 我刚刚当成了规划阶段，你可在适当的阶段停下来，告诉我哪些数据可以删除，我来操作后，有了足够空闲空间后再继续。

Translation: stop at a suitable phase, identify removable data, then continue after user cleanup.

> 已通过迁移其他文件，给E盘腾出了138GB左右空闲空间，未删除或移动threeemind相关文件。你可继续进行

Translation: the user moved unrelated files, freed about 138 GB on E without deleting or moving ThreeMind files, and authorizes continuation.

Implementation resumes with source witnesses and all 35,374 original references verified, followed by the current joint backup and isolated recovery. Continuation authorizes the approved sequence, not deletion of research source copies or older backups. Actual results require a later entry.

## Approved scope and evidence

“PLEASE IMPLEMENT THIS PLAN” authorizes relational records/queries plus managed originals, database-default running checkpoints with file option, and full backup/recovery before real migration. Historical identities/evidence remain. The final message requests a cleanup pause, not autonomous deletion.

Tools pass isolated acceptance; real schema remains 63 with zero moves. Selection totals 61.69 GiB plus 15 GiB reserve against 55.65 GiB E free. Another 114 resources await classification. Caches/stopped test clusters total 6.45 GiB; preserve the earlier verified 44.44-GiB D backup on portable storage. No historical free-space time series proves why space changed.

111 regressions, 14 filesystem/S3-emulated integrations, independent Python/Rust context restoration and desktop/mobile checks are engineering evidence, not learning results or full recovery of every historical subject. T12 remains separate. Stop before this phase's real new backup, schema 64 and moves; source cleanup remains separate.

## Sources

- [Approved plan](../../plans/existing-data-migration.md)
- [Handoff, space and cleanup](../../plans/existing-data-migration-stage.md)
- [Common interfaces/operations](../../storage-migration.md)
- Implementation includes storage_root.py, storage_payloads.py, 064_storage_locations.sql and isolated tests. Originals/exact manifests remain in managed storage, not this history.

## User interruption request and actual relocation

The user explicitly asked to check surviving background tasks to avoid duplicate migration, and identify interrupted files/operations. The reported three-hour apparent stall is a user observation, not proof of an infinite loop. Logs show an earlier restore error and delayed assistant handling. The database copy had completed; only external files resumed. Full isolated verification preceded actual relocation and report editions. [Delivery](../../plans/existing-data-migration-delivery.md) records scope and retained items. Earlier unmoved statements remain as phase evidence, superseded for current status.

## Authorization to clean failed products

The user authorizes removing previous failed products, or placing them in a clearly removable area, after final correct migration, and asks to avoid excessive backups. After migration/read/report acceptance, remove owned failed metadata, isolated locks and empty staging directories without another full backup. Scientific source copies and verified complete backups are not failed products. Exact removals are recorded in fixed-control `failed-leftovers-cleanup-receipt.json`.

## Immutability and development boundary

The user asks why business immutability affects development and says this is a question, not an instruction to change the approach. This is not authorization to rewrite publications. Development and byte-preserving relocation are allowed; content and fixed hashes remain protected. Schema 65 corrects the technical-pointer boundary, with before/after real witnesses and the original schema-64 receipt preserved.
