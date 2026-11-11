# Existing-data migration delivery

[中文](../../zh/plans/existing-data-migration-delivery.md) · [Approved plan](existing-data-migration.md) · [Operations and rollback](../storage-migration.md)

Recorded October 10, 2026. The approved selection has actually moved and `E:\ThreeMindData` is active. Real schema 65 was explicitly installed. Relational queries, report/note bodies and running checkpoints remain in PostgreSQL. Source copies and older backups remain; Core, old subjects, outcomes and simulation time are unchanged. Local commits only, no push.

## Scope and placement

| Category | Verified selection |
| --- | ---: |
| Exact resources | 43 |
| Original files | 32,984; 24,475,865,828 bytes |
| Database payloads | 4,242; 41,759,339,574 bytes |
| Logical selected total | 66,235,205,402 bytes; 61.69 GiB |
| Sealed checkpoints externalized | 0; historical subjects were not auto-sealed |
| Strict placement checks | 4,285; no old-source fallback |

Payloads comprise 3,615 packages, 475 media originals and 152 note images with unchanged scientific identities, sizes and hashes. Files use `originals` and future experiment workspaces use `experiments`; registered locators resolve their locations. Host control remains in project `data/storage-control`, retaining host identity and keys. Checkpoints default to `database`; explicit `filesystem` is available as host storage, outside kernel configuration.

All 157 resources are classified: 43 exact selections, 68 repository documents/source/frozen fixtures retained, and 46 published-package expanded workspaces retained while their canonical packages move. Their expanded members were not proved individually equivalent to the packages, so they are not auto-deletion candidates. Known historical gaps remain; relocation invents no evidence.

## Interruption, backup and recovery

The previous recovery log failed at 16:31 after 3,146.27 seconds because a colon-containing target ID was treated as a path component. The assistant failed to handle/report this promptly. Following the user's stop, no copy/migration process remained; real schema was 63 with no active jobs or root switch. The owned isolated cluster completed crash recovery and matched the backup's scientific witness exactly. Only its file phase resumed; database copying was not repeated.

Schema 64 was installed first. The first real copy completed all file resources and 4,233 database payloads; nine published artifacts failed because the previous trigger also forbade physical-pointer changes. Schema 65 permits only a same-project, same-size, same-hash placement while preserving content, metadata and publication protection. Scientific witnesses for nine published artifacts and six publications remained identical. After confirming that the first process exited, the same task retried only these nine items without recopying committed items. Eight distinct relevant cases ultimately passed; one test-setup error was corrected and rerun. Business-content immutability does not prohibit development, schema upgrades or verified relocation.

Current joint backup: `E:\ThreeMindBackups\storage-20261010-r2`, ID `37f19cc0-c29d-4577-a479-6a9ff0b5adf6`. Its database dump is 41,994,013,594 bytes with `zstd:3`; backup content reuse preserves original bytes. All 35,375 research references pass size/SHA-256 checks in isolated new placements, and 7 actual historical full/delta checkpoint samples match state/context witnesses. Isolated fixtures separately cover independent Python/Rust recovery and next input, filesystem/S3 emulation, faults and reference protection. This does not rerun every old consciousness. T12's host-inheritance and `/4` save-field issues remain separate.

The older complete `D:\ThreeMindBackups\research-records-20261010` backup remains. After validation, only this task's disposable restored database/tablespace/files and its aborted unusable temporary dump were removed. Research sources and complete backups remain. Copying/switching did not reclaim source or database-original space.

## Research revisions and reads

Append 70 dated experiment annotations, new versions of 129 database reports with 129 fixed-version evidence links, and 136 repository report editions. Original report versions, charts, sources, review state and AI provenance remain; measurements/conclusions are unchanged.

| Paginated query | Before median ms | After median ms | Rows |
| --- | ---: | ---: | ---: |
| edges | 1.478 | 1.024 | 50 |
| nodes | 2.323 | 2.091 | 50 |
| observations | 8.778 | 8.513 | 50 |

These local measurements use the same real run/pagination with 12 repetitions excluding two warmups. Result hashes match; queries still access PostgreSQL without per-query file scans. Normal reading services return identical bytes for 9 real package/media/note-image samples. Placement independence does not imply faster saves/restores: isolated 32-node Python file save/restore medians were about 144/32 ms versus database 40/22 ms; Rust about 132/31 versus 40/21 ms. Do not extrapolate to large graphs.

## Receipt and rollback

Stable task ID: `35b23849-b53b-4da3-89e9-8ea9efd77b6a`. Do not execute another migration; query or reverify:

```powershell
$env:PYTHONPATH = "$PWD\src"
$tmPython = "$PWD\.work\kernel-venv\Scripts\python.exe"
$tmChangeId = '35b23849-b53b-4da3-89e9-8ea9efd77b6a'
& $tmPython -m threemind_lab.cli storage root-status --local --id $tmChangeId
& $tmPython -m threemind_lab.cli storage root-verify --local --id $tmChangeId
```

`root-rollback` uses this ID and fences subsequent writes and placement/policy versions. New data at the active root requires a reviewed reverse migration rather than forcing an incomplete old root. Rollback, cancellation and deletion are separate; source cleanup needs an exact preview.

Detailed receipts remain in `data/storage-control/migration-20261010`: root receipt/verification, unchanged scientific witness, position-edition receipt, classification and recovery/read witnesses. Exact lists live in fixed-control selections. Large manifests/logs/originals stay outside Git; the backup retains recovery witnesses. Completion covers the approved selection; expanded workspaces and unsealed checkpoints remain under the agreed rules.

## Final occupancy and measured cost

| Item | GiB | Meaning |
| --- | ---: | --- |
| PostgreSQL before | 64.958 | `pg_database_size` |
| PostgreSQL after closure | 64.970 | Placement metadata/report editions; original payload bytes retained |
| Database net growth | 0.012 | No duplicate database copy |
| New research root | 61.678 | 41,378 files, summed logical sizes |
| Retained selected file sources | 22.795 | Fixed file selection, excluding database payloads |
| Current complete joint backup | 59.090 | `E:\ThreeMindBackups\storage-20261010-r2` |
| Older complete backup | 44.436 | `D:\ThreeMindBackups\research-records-20261010` |
| Fixed control area | 0.085 | Registry, fixed lists and receipts, outside consciousness state |
| E free | 43.612 | Closure snapshot, includes other disk usage |
| D free | 55.237 | Closure snapshot |

File totals are logical sizes, not measured NTFS allocation. The 4,242 payload references reuse 4,197 same-project, same-hash files plus 4,197 one-byte object locks. Together with 32,984 originals, this is exactly 41,378 files and 66,226,007,553 bytes, matching the per-object calculation. Reference deduplication is not missing data. Source database payloads already belong to PostgreSQL's size and must not be counted again. The copy and resumed operation took 10599.57 seconds in total (about 2.94 hours), including hashing, placement commits and final verification; per-stage logs remain. Small-file verification/registration costs are not sequential I/O bandwidth. No source-copy or original database-byte cleanup occurred. See `final-capacity.json` for the detailed capacity witness.

Under the user's later authorization, clean 45 confirmed failed leftovers/empty staging items after final acceptance; exact paths and failed-manifest hashes remain in `failed-leftovers-cleanup-receipt.json`. The aborted 5.89-GiB temporary dump was already removed. No additional full backup was made and no research sources/complete backups were deleted. Earlier manifest-retained receipts remain as contemporary evidence.

Git contains only code, bilingual delivery/history and report revision chains; originals, backups, receipts and execution logs remain ignored. `.report-revisions.lock` files coordinate processes: add an ignore rule and remove 28 previously tracked locks from the index while retaining local files. Report bodies/manifests remain tracked. All 136 new reports and their preserved parent versions verify, and the complete index passes the source/data boundary check. Closure auditing finds no remaining migration or isolated-recovery tasks.
