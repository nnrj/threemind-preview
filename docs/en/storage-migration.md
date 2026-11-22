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

## Store a new experiment across data directories

With no directory pool configured, experiments use the existing data root's `experiments` directory. Open **Data management → Storage locations → Experiment directories and disk placement** to register absolute paths on the host. Smaller priority numbers come first. A directory limit includes existing files at their allocated sizes. Directories on the same volume share the available space and the largest configured free-space floor.

Budget for the peak simultaneous use of raw records, checkpoint files, scratch files, archives and readback copies. By default the allocator looks for one directory that can hold the whole experiment. If none fits, the preview shows the shortfall. To split a study, give each independently writable world, batch or volume a name and explicitly enable splitting. Files and individual parts always stay on one disk. Removing a disk stops access to its assigned parts. Reconnect the same disk and reopen the placement by name. On Windows it can be found under a different drive letter by its volume and directory identity.

The web interface, REST API and CLI share host placement records. Use these commands at the host, or omit `--local` to use the authenticated server.

```powershell
threemind storage pool status --local
threemind storage pool configure --local --json directories.json
threemind storage pool preview --local --json budget.json
threemind storage pool reserve --local --json budget.json
threemind storage pool path --local --name aquatic --part world-a
```

Example host configuration, with E first and H second. Set `limit_bytes` to cap a directory. Supply the current revision from `status` when editing.

```json
{"expected_revision":0,"directories":[
  {"id":"primary","path":"E:/ThreeMindData","priority":10,"reserve_bytes":26843545600,"limit_bytes":null},
  {"id":"portable","path":"H:/ThreeMindData","priority":20,"reserve_bytes":5368709120,"limit_bytes":null}
]}
```

Example budget with one world, two archive volumes and space to read back a file. Size these parts for the actual experiment.

```json
{"name":"aquatic","allow_split":true,"parts":[
  {"name":"world-a","kind":"data","bytes":4294967296},
  {"name":"vol-1","kind":"archive","bytes":2147483648},
  {"name":"vol-2","kind":"archive","bytes":2147483648},
  {"name":"check","kind":"readback","bytes":1073741824}
]}
```

Study authors can use `StudyConfig.for_experiment(...)` for automatic placement using the study's hard budget. For a multipart reservation, pass `part="world-a"` to open that workspace. Other scripts can call `ResearchStorage.workspace_path(name, part=...)`. Scripts that hard-code a physical location continue to use it. Existing experiments and the database retain their own storage settings.

After finishing writes, `archive` streams a standard ZIP directly into the reserved volumes. It publishes the ordered manifest after verifying segment sizes and SHA-256 hashes. Use `verify` to check the archive again, or `extract` to restore one file into its reserved readback part without joining the volumes. These operations are also available in the web interface. Recipients can concatenate the raw volumes in manifest order to obtain an ordinary ZIP.

```powershell
threemind storage pool archive --local --name aquatic
threemind storage pool verify --local --name aquatic
threemind storage pool extract --local --name aquatic --part check --member world-a/trajectory.json
threemind storage pool finish --local --name aquatic
```

The REST entry point is `/api/v2/storage/experiment-pool`, with `/preview`, `/reserve` and `/studies/{name}/manifest`. An authenticated client can download and verify a segment with `threemind storage pool download --name aquatic --part vol-1 --output volume-1.bin`. Completion releases unused budget and retains the placement. Only unused reservations can be cancelled. Joint backups preserve the source host's placement records and published volume manifests. Register experiment originals under the existing backup procedure or back them up separately.

After completing a study, restore an individual file with `threemind storage pool extract --local --name aquatic --member world-a/trajectory.json --output trajectory.json`, or select **Download file from archive** in the web interface.

## Sync, back up, move and archive whole experiments

Choose directory roles under **Data management → Storage locations → Experiment directories and disk placement**. To reclaim space on the run disk, archive to another physical disk. For example, an experiment on E can use H:\ThreeMindArchive on a removable disk. The page suggests an online archive directory on another physical disk first. A directory on the same disk can also be selected for organizing files. Only run directories receive new experiments. Directories on the same volume share its available space and reserve. On Windows the host queries disk extents to distinguish separate physical disks from partitions of the same disk. [Windows volume disk extents](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-ioctl_volume_get_volume_disk_extents)

Open **Experiment sync, migration and archival**, select the experiment and destination, and preview the transfer. Use **Register a completed historical experiment** for a finished, inactive workspace directly below the experiments folder of a configured run directory. A registered experiment with several named parts can be transferred as a unit.

| Operation | Destination and effect |
| --- | --- |
| Sync | Updates the replica under replicas. Identical files are reused, target-only files stay in place, and conflicting edits are reported. The experiment keeps its original location. |
| Backup | Adds a version under backups with its inventory, hashes and receipt. Restore any version to a run directory under a new experiment name. |
| Migrate | Switches the experiment to another run directory. |
| Archive | Switches the experiment to an archive directory. An exact, verified replica at that destination can be used directly. The catalog remains visible while the disk is disconnected. |
| Unarchive | Returns the experiment to the selected run directory under its existing name and completed status. |

This workstation uses `primary` for `E:\ThreeMindData` and `portable-archive` for `H:\ThreeMindArchive`. `H:\ThreeMindData` remains the fallback run directory. The following commands use these IDs and an example study named `aquatic`.

~~~powershell
threemind storage transfer discover --local --directory primary
threemind storage transfer adopt --local --directory primary --name aquatic
threemind storage transfer preview --local --operation archive --name aquatic --to portable-archive
threemind storage transfer sync --local --name aquatic --to portable-archive
threemind storage transfer archive --local --name aquatic --to portable-archive
threemind storage transfer list --local
threemind storage transfer release --local --job <archive-job-id>
threemind storage transfer unarchive --local --name aquatic --to primary
threemind storage transfer backup --local --name aquatic --to portable-archive
threemind storage transfer restore --local --name aquatic --backup <backup-id> --to primary --as aquatic-restored
~~~

Migration, archival and unarchival retain the old copy until **Release old copy** or release verifies both locations again. Verification covers sizes, SHA-256, empty directories, file and directory modification times, and NTFS creation times. Consolidating parts from multiple volumes creates a common parent for them. Access times may change on reads. Shared hard links prevent source release. Symbolic links, reparse points and named NTFS streams require separate handling. Registered evidence follows its storage locator. External scripts that embed absolute paths must use the experiment name or locator to follow a move.

After a disconnect, resume the same job to reuse verified files. The tool reports changes to a source during an interruption. On a fresh host, register the backup disk and use import-backup --directory <id> --name <study> --backup <version> before restore. The host backup command covers database records and separately registered external evidence. The existing pool archive command creates split ZIP files.

The authenticated HTTP entry point is /api/v2/storage/experiment-pool/transfers. Inspection and preview use data.read, and changes use data.manage. Omit --local in the CLI to use the HTTP interface. Starting an HTTP transfer returns a job ID for progress and error reporting.
