# Existing data migration and research file roots

[中文](../zh/storage-migration.md) · [Approved plan](plans/existing-data-migration.md) · [Phase handoff and cleanup inventory](plans/existing-data-migration-stage.md)

October 10, 2026: the approved existing-data selection has actually moved and `E:\ThreeMindData` is active with real schema 65. The current joint backup was restored in isolation; sources and older complete backups remain. Do not repeat the migration: query, verify or conditionally roll back the original task. [Actual delivery](plans/existing-data-migration-delivery.md)

## Storage boundaries

`THREEMIND_DATA_ROOT` defaults to the project's `data`; the approved destination is `E:\ThreeMindData`. It controls research files, not PostgreSQL's physical database directory. Report/note bodies, inputs, metrics, recovery cursors and node/edge queries remain relational.

New study scripts can resolve `ResearchStorage(...).workspace_path("study-name")` under the registered root's `experiments/study-name`, then pass it to maintained `StudyConfig.work` and the recorder. Resolution creates no directory/subject and resets no individual. Legacy `.work` paths and frozen scripts remain; maintained entry points accept external roots and continue registering formal originals.

The fixed control area remains `data/storage-control`, or explicit `THREEMIND_STORAGE_CONTROL`. Host identity, keys, locks, receipts and member maps stay there. Physical placements are versioned independently of scientific locators and hashes. Reads verify the current location and report corruption without falling back to retained sources.

Running checkpoints default to `database`. Explicit host setting `THREEMIND_CHECKPOINT_BACKEND=filesystem` or the management UI selects file storage; registered host settings override the environment default. This is not kernel configuration and does not change individual identity. File bytes are persisted and verified before transactional publication of checkpoint/input/observation references. Failure cannot acknowledge a save. Complete host context is preserved; a Core file alone does not establish whole-system recovery.

## Shared management surfaces

The updated Data Management → Storage page provides root preview, confirmed execution, status, resume, cancel, verify, rollback, manifest download and checkpoint backend selection. Insufficient space disables execution. The program copies, verifies and switches locations; users need not move each file. Closing a page does not cancel work; inspect and resume its existing task ID after interruption.

UI, CLI, REST and the existing Agent operation catalog share `RootChanges`, per-resource migration and payload services. Host operations require an administrator, with additional project-write/private-attachment checks. REST uses `/api/v2/storage/root-changes`, `/preview`, `/{id}`, `/{id}/manifest` and `/{id}/{action}`; checkpoint settings use `/api/v2/storage/checkpoint-backend`. Project payload migration/sealing use `/api/v2/projects/{project}/storage/payload-migrations` and `/seals/{run}`.

Preview selects scientific references and exact archived files, excluding Git source, reports, protocols and frozen fixtures. The October 10 selection contains 43 resources, 32,984 files and 4,242 database payloads. The other 114 resources are classified as 68 source/report/fixture resources and 46 expanded published-package workspaces, retained in place. Expanded members were not individually proved equivalent and cannot be automatically deleted. Payloads include media, note images and research/model/export packages. Unsealed checkpoints are not selected.

## CLI workflow

These are general operational instructions. This task is complete; do not repeat the backup/new-migration commands for everyday use. Query this task with its original ID from the delivery. Use the project's everyday Python; no paid service is needed.

```powershell
$env:PYTHONPATH = "$PWD\src"
$tmPython = "$PWD\.work\kernel-venv\Scripts\python.exe"
& $tmPython -m threemind_lab.cli storage root-preview --local --destination E:\ThreeMindData
```

`--local` uses the application database in `.env` and the local administrator context without an HTTP server. It does not replace the backup account. Only `root-*`, `checkpoint-backend`, `payload-migrate` and `seal` support it; other host commands retain their HTTP interface.

Backup reads `THREEMIND_BACKUP_DATABASE_URL` from local `.env`. Use a new destination with sufficient space. Keep URLs/passwords/key values out of command arguments, receipts and bundles. Replace the illustrative drive below with the actual destination:

`create --compression zstd:3` explicitly selects a faster backup encoding. `zstd:1`, `gzip:1` and `gzip:6` are also supported; omission preserves PostgreSQL's default. The manifest records the selection without changing original bytes/scientific hashes. Installed PostgreSQL utilities must support it. A new destination/full recovery validation remain required; compression does not guarantee space.

```powershell
& $tmPython -m threemind_lab.cli storage backup --pg-bin 'D:\Program Files\PostgreSQL\17\bin' create 'X:\ThreeMindBackups\storage-20261010'
& $tmPython -m threemind_lab.cli storage backup inspect 'X:\ThreeMindBackups\storage-20261010'
& $tmPython -m threemind_lab.cli storage backup --pg-bin 'D:\Program Files\PostgreSQL\17\bin' restore 'X:\ThreeMindBackups\storage-20261010' --new-database threemind_storage_verify --external-root 'X:\ThreeMindRestore\storage-20261010'
```

Joint backups preserve the database, registered originals, current placements, member maps, policies and host checkpoint settings. Keep encryption keys separately. Restoration only permits a new database/root and returns an unactivated registry. Verify identities, references, recovery dependencies and next-input responses; `inspect` is not restoration validation.

For isolated recovery, `--relation-root observations=D:/ThreeMindRestore/observations` routes that table to another new directory to balance disk use. Only the new restored database's physical tablespace changes; source/logical contents remain. Receipts retain tablespace names/paths. Cleanup drops the exact new database first, then its registered tablespaces/directories; never delete everyday PostgreSQL data.

### File restoration after interruption

Check processes, the original receipt and restored-database witnesses before retrying. When the database phase completed but external-file restoration failed, resume only the files:

```powershell
& $tmPython -m threemind_lab.cli storage backup restore-files 'X:\ThreeMindBackups\storage-20261010' --new-database threemind_storage_verify --external-root 'X:\ThreeMindRestore\storage-20261010'
```

This command neither connects to nor writes a database. Its receipt explicitly covers files only; verify the database separately. The root must be empty or carry the same backup/target intent. Published files are verified and reused, unpublished staging can be retried, and conflicts stop without overwriting. Historical target IDs remain unchanged; hashed directory names avoid treating valid colon-containing IDs as Windows paths.

After successful backup/recovery validation, explicitly upgrade with the existing command. The user controls pausing/restarting their services; the application does not migrate on startup.

```powershell
& $tmPython -m threemind_lab.cli migrate
```

Preview again and use its `root_before.revision`. Preserve the stable request ID on retries. The example `0` is this phase's observed revision, not a permanent constant:

```powershell
$tmChangeId = [guid]::NewGuid().ToString()
& $tmPython -m threemind_lab.cli storage root-plan --local --destination E:\ThreeMindData --expected-revision 0 --request-id $tmChangeId
& $tmPython -m threemind_lab.cli storage root-execute --local --id $tmChangeId
& $tmPython -m threemind_lab.cli storage root-status --local --id $tmChangeId
& $tmPython -m threemind_lab.cli storage root-verify --local --id $tmChangeId
```

`--output` writes the full preview/task to a new JSON file. `root-resume`, `root-cancel` and `root-rollback` use the same `--id`; cancel stops at safe file/payload boundaries and rollback requires matching revisions/write conditions. Copies remain; no automatic deletion occurs.

Execution verifies and switches individual objects before publishing the root/future policies only after all selected objects pass. Partial results show actual placements. New writes, changed sources, configuration conflicts or failed verification stop the affected batch, without skipping conflicts on resume. Durable publication intent/receipts allow recovery after a crash following root publication.

Large fixed selections are stored separately by hash; progress/cancellation journals update only changing fields rather than rereading and rewriting every selected member after each file. New resource tasks use `/2` journals; existing `/1` tasks remain readable and resumable. Full-selection reads verify identity and hashes. Bounded metadata caches invalidate on atomic replacement and contain no organism dynamics.

Editing `.env` is not migration. A requested/registered-root mismatch reports pending migration and blocks mixed writes instead of presenting a new empty database. Align environment settings after successful switching.

Complete backups can losslessly encode their research originals with `storage backup compact-research BACKUP_DIRECTORY`. The tool verifies the old backup and each decoded scientific hash and size before atomically publishing the explicit `/2` backup format. Cleanup removes only superseded representations inside this backup; research source copies, the database dump and other backups remain. Retry the same directory after interruption. The published manifest always resolves complete bytes, including during cleanup. Existing `/1` backups remain readable; old programs reject `/2` instead of interpreting encoded bytes as originals. Savings depend on content and do not replace isolated recovery verification.

## Checkpoints and rollback limits

Single-payload migration uses `storage payload-migrate --project PROJECT_UUID --kind artifact|media|note-image|checkpoint|blob --id OBJECT_UUID --target TARGET_ID --request-id REQUEST_UUID`, with `--local` for direct local invocation. The destination must be a registered filesystem target. Database source bytes and historical placements remain.

`storage seal --local --project PROJECT_UUID --id RUN_UUID` explicitly seals a completed, non-writing subject with a supported verifiable recovery boundary. Paused subjects awaiting training, coordinators, missing dependencies and active jobs cannot be sealed for relocation. No real run was automatically sealed here. Existing T12 `/4` host-save issues remain separate; engineering fixtures do not cover them.

Root rollback checks intervening writes and resource/policy revisions. New data written after switching requires a reverse migration, not a forced switch to an incomplete old root. Payload rollback verifies retained old bytes. Cancel, rollback and archive are not deletion. Source cleanup requires a separate exact preview; formal originals are not ordinary space-recovery caches.
