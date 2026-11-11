# Migration handoff: tools complete, awaiting disk cleanup

**Current state, October 10, 2026: the approved selection has moved and `E:\ThreeMindData` is active with real schema 65. All 43 resources, 32,984 files and 4,242 database payloads pass copying, hash and new-placement checks. Running checkpoints still default to database. The joint backup was restored in isolation; sources and older complete backups remain. Earlier phase records below are preserved. See the [actual delivery](existing-data-migration-delivery.md).**

[中文](../../zh/plans/existing-data-migration-stage.md) · [Approved plan](existing-data-migration.md) · [Operations](../storage-migration.md)

Recorded October 10, 2026. At the user's request, finish tools/isolated validation and stop for user-operated cleanup before a new real full backup, schema 64 or actual relocation. No originals, caches or backups were deleted; user PostgreSQL/Lab services were not taken over and Git was not pushed.

## Delivery and real state

Implemented research-root configuration, durable batch tasks, exact member placement maps, database-payload location versions, optional file checkpoints and joint backup. UI/REST/CLI/Agent share copy, verify, switch, resume, cancel and conditional rollback services. Running checkpoints default to database; no historical subjects were automatically sealed. Scientific identity/hash/source and source copies remain.

The real database remains schema 63: 20,581 runs, 24,821 checkpoints, 84 research indices, 59,118 references, 442 research documents, 635 notes/719 versions, 3,615 packages, 475 media, 152 note images, zero stored blobs/active jobs. Registry SHA-256 is `ab2c7d4083a3635d10409d4a94224fea7f5668ca23c18da2e67d952c0b36ca90`; host identity is unchanged. Witnesses do not replace a current full backup.

No Core/default/individual/input changes occurred. T12's existing `/4` host-save mismatch remains separate. Supported `causal/9` fixtures do not establish recovery of all historical subjects.

## Capacity

| Item | Measurement |
| --- | ---: |
| Physical PostgreSQL | 69,748,250,291 bytes, about 64.96 GiB |
| Broad directory inventory | 157 resources, 234,354 files, about 96.22 GiB; includes source, expanded copies and tools, not net migration size |
| Exact selected files | 43 resources, 32,984 files, about 22.79 GiB |
| Eligible database payloads | 4,242, about 38.89 GiB; 3,615 packages + 475 media + 152 note images |
| Selected total | 66,235,205,402 bytes, about 61.69 GiB |
| Additional reserve | 15 GiB |
| E free | About 55.65 GiB; insufficient |
| Selected checkpoints | Zero; unsealed checkpoints remain in database |
| Other registered resources | 114 retained for classification |

This batch needs about **76.69 GiB** free on E; prepare **80 GiB or more**. The caches below alone are insufficient. A fresh joint backup and isolated restoration need separate capacity, so 80 GiB is not the whole plan's requirement. Recalculate per-drive needs after cleanup. Backup preflight conservatively counts physical database, originals and reserve, without assuming compression.

Sources, including original database bytes, remain: relocated bytes are not automatically reclaimed bytes. Other resources include source/reports and expanded workspaces whose packages already have references; batch completion is not all-history relocation.

## User cleanup candidates

Paths are relative to `E:\WORKSPACE\AgentWork\threemind`, confirmed as reproducible caches. Later builds/tests may need their dependencies reinstalled. The everyday native module is installed in `.work\kernel-venv`, not run from `target`.

| Removable directory | GiB | Purpose/impact |
| --- | ---: | --- |
| `target` | 3.370 | Rust build cache |
| `.work\report-render-tools` | 1.487 | Report-render dependencies |
| `threemind-ui\node_modules` | 0.439 | Frontend dependencies |
| `.work\local-v4-testdeps` | 0.395 | Specialized test dependencies |
| `.work\kernel-build-cache` | 0.347 | Native build cache |
| `.work\retention-plot-deps` | 0.117 | Retention plotting dependencies |
| `.work\retention-test-deps` | 0.087 | Retention test dependencies |

Two isolated PostgreSQL **test clusters have no running server**; their directories are removable and are not the everyday database:

| Test cluster | Size | Verification |
| --- | ---: | --- |
| `.work\pgtest` | 145,567,094 bytes, about 138.82 MiB | `pg_ctl status`: no server running |
| `.work\data-management-pg-20261010` | 75,579,691 bytes, about 72.08 MiB | Port-55439 cluster stopped and status rechecked |

Together about **6.45 GiB**. Delete exact paths in the file manager; the current data UI does not manage arbitrary build caches/test clusters. Scripts/screenshots/handoff evidence are retained separately.

### Preserve or relocate backups and research

- `D:\ThreeMindBackups\research-records-20261010`: dump 47,712,433,106 bytes, **44.44 GiB**, plus manifest/source/recovery witnesses/registry. Earlier isolated recovery passed; this phase checked files/size only. Move the **whole folder to portable storage and preserve it**, verify before clearing the D copy. Do not permanently delete the known verified backup before a replacement passes recovery. It occupies D and cannot explain/free E.
- `data\git-backups`: **263.29 MiB**, recoverable original Git history; preserve or relocate the complete folder.
- `data\backups` is empty; `.work\records-backup-restored-20261010` is only 360 bytes and its restored database was already removed, not a hidden 65-GiB copy.
- **Keep** `.work\kernel-venv`, entire `data`/`.work`, the real PostgreSQL directory and research workspaces. Expanded ocean-evolution, temporal-state, body-exploration and eye-hand-learning files/packages require hashes, references and recovery-dependency checks before duplicate cleanup. A ZIP alone is insufficient.
- Existing witnesses cannot reconstruct every change from remembered "over 90 GB" free space; current sizes do not prove a particular refactor caused it.

## Engineering acceptance and costs

Combined root/backup/byte-backend/package/reference/checkpoint/temporal-report/API/CLI regression: **111 passed**. Filesystem/local Moto S3 media/images/reports/packages/permissions/restoration: **14 passed**, not real-cloud validation. Python and Rust independently pass file/delta checkpoints, complete host context, relational queries and next-input equality: two cases. Final changes rechecked backup safety, joint recovery and interrupted root publication.

Coverage includes insufficient space, changed sources, active writers, cancel/resume, missing/corrupt bytes, transaction failure, idempotency/conflict, private payloads, seal eligibility, revisions after rollback and publication-intent recovery. Old-source fallback is prohibited in corruption tests. TypeScript/Vite build and installed Edge desktop 1440/mobile 390 checks pass, including layout, insufficient-space disablement and checkpoint-setting submission; no overflow/JS errors. Isolated UI interfaces leave user port 8877 untouched.

Warm synthetic `causal/9`: 32 nodes, 14,010-byte payload, not formal learning/production evidence. Milliseconds below; Core/first prepare one sample, encoding/read/restore five, queries eight, saves four. Saves include SQL projection/publication.

| Operation | Python | Rust |
| --- | ---: | ---: |
| Core advance | 2.93 | 1.02 |
| Encoding | 4.05 | 4.29 |
| First file persistence | 171.75 | 159.70 |
| Verified file read | 9.57 | 9.45 |
| DB / file save | 40.00 / 143.89 | 39.61 / 132.30 |
| Relational query in DB / file mode | 2.26 / 1.69 | 1.36 / 1.57 |
| DB / file restore | 21.82 / 31.97 | 21.06 / 31.09 |

Small file saves/restores are slower; queries remain relational. This supports the database default, without establishing large-state benefits. Exact preview measured 10.65 seconds last and 132.98 earlier after reducing repeated metadata/project scans; differing cache conditions preclude a fixed speedup claim.

## Resume sequence

1. Recheck space, writers and witnesses after cleanup; destination stays `E:\ThreeMindData`.
2. Create a current joint database/original/control backup and verify new-database/new-root recovery; preserve the old backup.
3. Explicitly install schema 64, migrate approved exact selections under stable task IDs, verify new-location permissions/replay/packages/restoration. Paused/incomplete subjects remain in database.
4. Classify remaining workspaces/source/duplicates rather than equating this batch with complete history. Append location revisions after actual moves, preserving originals.
5. Publish root/policies and actual receipts/unmoved list; source cleanup has a separate preview.

Local evidence under `data/storage-control/migration-20261010`: `inventory.json`, `pre-migration-witness.json`, `formal-preview.json`, `formal-preview-r2.json`, `cache-candidates.json`, `engineering-performance.json`. Old previews remain. Machine-path manifests are ignored by Git; this document retains aggregates rather than replacing exact evidence.
