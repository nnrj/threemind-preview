# Data management and storage locations

Date: 2026-10-10. This guide follows the approved [implementation plan](plans/data-management-and-storage-separation.md). Generic separation, packaging and migration tools were implemented without migrating real experiments, upgrading the user's database or taking over running services. Only the explicitly approved repository artifact archival was performed. Migrations 060/061 and round trips were tested in isolated PostgreSQL and temporary directories. Git history cleanup was local; nothing was pushed remotely.

**Later October 10 correction:** the user subsequently migrated the everyday local database. The missed native-extension installation is repaired, and schema/native `doctor` checks now pass on this host. This project currently has only a local environment; earlier “real deployment” distinguished the everyday local database from isolated acceptance databases rather than claiming an online service. Other study-data migration remains unexecuted. See “Local database and native-extension updates” below.

## November 10, 2026: file sizes in everyday commits

The author requested a less restrictive local rule for open-source contributors. Ordinary files up to 50 MiB pass; files above 50 MiB and up to 100 MiB produce a warning but still pass; files above 100 MiB are rejected. These match [GitHub's ordinary Git file limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github), not a Git default. Manuscripts, PDFs and ordinary documentation no longer need individual exceptions at 1 MiB.

Research originals, checkpoints, complete trajectories and formal data bundles remain excluded by their existing classification rules. Necessary frozen fixtures and templates retain their bounded exceptions. Checks read staged objects and never delete, move or unstage files. Run `python scripts/check-git-data.py` for staged changes, or add `--all-tracked` for the whole index; fix and restage any rejected content before committing again. See the [current policy](../../lab/artifact-index/README.md). The earlier delivery statements below retain their historical scope.

## Access and interface

Open **Data and writing → Data management**. Project members can query visible resources. Export plans, import and native restoration require a researcher or project owner. Private notes and bundles containing private data remain owner-visible; project ownership does not bypass another person's private-note access. Candidate inventory and cleanup preview require project ownership. Host targets, write policies, offline resources, migrations and repository research originals require a host administrator.

Server mode uses authenticated sessions and mutation CSRF checks. Workstation local identity is restricted to loopback. CLI uses `--url` and `--username`, prompting locally for the password or reading `THREEMIND_API_PASSWORD`. Remote login requires HTTPS; never embed credentials in a URL.

The inventory supports project, experiment, individual, population, batch, dataset, tag and time selection. Preview selected resources or the complete current range before export. Details show versions, origin and restoration boundaries. Large original contents require an explicit source-object read or bundle download.

## Formal data bundles

`.tmdata` uses `threemind.data-bundle/1`; multiple volumes have a `.tmdata.json` total manifest. Project-resource exports include required dependencies and saved history. Missing required volumes or objects and hash mismatches block registration or restoration. A volume is limited to 8 GiB compressed; expanded size, object count and total budgets are also bounded. Upload is additionally limited by the deployment's explicit staging budget. The CLI defaults to an 8 GiB transfer total; `--maximum-bytes` can raise that total explicitly, but cannot bypass the per-volume limit.

SHA-256 verification establishes agreement with the supplied manifest, not author identity or original signature validity. Historical sharing, permission and signature semantics remain tied to their original format; import does not grant access or reactivate old shares.

Create `selection.json`, for example `{"filters":{"experiment":"EXPERIMENT_UUID"}}`, `{"run":"RUN_UUID"}`, or `{"resources":[{"kind":"document","id":"DOCUMENT_UUID"},{"kind":"note","id":"NOTE_UUID"}]}`.

```powershell
threemind data list --project PROJECT_UUID
threemind data detail --project PROJECT_UUID --kind document --id DOCUMENT_UUID
threemind data export-plan --project PROJECT_UUID --json selection.json --request-id REQUEST_UUID
threemind data export --project PROJECT_UUID --plan PLAN_UUID --request-id EXPORT_REQUEST_UUID
threemind data job-status --project PROJECT_UUID --id JOB_UUID
threemind data bundles --project PROJECT_UUID
threemind data bundle --project PROJECT_UUID --bundle BUNDLE_UUID
threemind data download --project PROJECT_UUID --bundle BUNDLE_UUID --volume 0 --output records.tmdata
threemind data manifest --project PROJECT_UUID --bundle BUNDLE_UUID --output records.tmdata.json
```

Download each volume separately, with zero-based `--volume`. Downloads preserve identifiable `.partial` files and never overwrite existing evidence. Completed volume downloads verify their registered byte count and SHA-256.

```powershell
threemind data preflight --project TARGET_PROJECT_UUID --file records.tmdata
threemind data import --project TARGET_PROJECT_UUID --file records.tmdata --request-id IMPORT_REQUEST_UUID
threemind data preflight --project TARGET_PROJECT_UUID --manifest-file set.tmdata.json --file part1.tmdata --file part2.tmdata --maximum-bytes 17179869184
threemind data restore-records --project TARGET_PROJECT_UUID --bundle IMPORTED_BUNDLE_UUID --request-id RESTORE_REQUEST_UUID
threemind data object --project TARGET_PROJECT_UUID --bundle IMPORTED_BUNDLE_UUID --id document:SOURCE_DOCUMENT_UUID
```

Import first registers read-only origin data. Native restoration of reports and the caller's notes is separate. It creates new local IDs while preserving source versions, authors, dates, original hashes and projection hashes, and mapping fixed references and formal attachment links. Original bundle bytes and origin records remain unchanged. Previous share metadata is evidence only: old URLs, credentials and permissions are not reactivated. Unknown objects within a known outer schema remain read-only; unknown outer formats are rejected.

Subject restoration uses `resume-plan` and `resume` with an explicit source object ID. Only the corresponding validated adapter can create a paused copy. Generic run/coordinator facts cannot become runnable subjects, and a Core-only state cannot represent the complete subject. Existing experiment, language, population and species formats retain their dedicated interfaces and evidence boundaries. A historical report share ZIP does not acquire native restoration semantics automatically. `threemind data cancel --project PROJECT_UUID --id JOB_UUID --request-id REQUEST_UUID` stops uncommitted work; already committed bundles and records remain.

Preflight and subject restoration must use the same runtime backend. The UI selects `native` or `reference` and invalidates previous previews when that choice changes. Supply the same CLI `--backend` to `preflight`, `resume-plan` and `resume`; omitted REST/CLI values use the deployment's configured backend. Preflight reports the effective `backend`.

## Targets and explicit migration

October 10 update: batch research-root changes, database-payload relocation and optional file checkpoints are described in the [migration guide](storage-migration.md). The three-category scope below is the original delivery statement; the new `checkpoint` category requires explicit configuration and running checkpoints still default to database. The real database remains schema 63; schema 64 and actual migration await user disk cleanup. [Phase handoff](plans/existing-data-migration-stage.md)

PostgreSQL retains authoritative scientific state. Only `media-original`, `note-image` and `export` carrier categories may be externalized; offline research files use separate host registrations. Filesystem, S3-compatible and database targets have stable IDs and versioned configurations. Policies affect future writes, freezing the target version at submission; changing a setting does not rewrite historical locators. Filesystem or cloud-synced directories must satisfy normal-directory/file constraints. Symbolic links, Windows reparse points, control-area overlap and private repository metadata are rejected.

The control area defaults to `data/storage-control`; `THREEMIND_STORAGE_CONTROL` can explicitly select it. It holds registrations, locks, candidates and operation receipts. Encryption must use the application's `THREEMIND_SECRET_KEYS`; public target responses expose only `has_secret`. Enter S3 credentials using the UI password fields or `threemind storage target --json target.json --s3-credentials`. Do not store plaintext credentials in ordinary JSON, command arguments, reports or data bundles.

`threemind storage inspect` displays host configuration. A filesystem target request is `{"kind":"filesystem","name":"Research originals","path":"E:/ThreeMindData","expected_revision":0}`.

```powershell
threemind storage target --json target.json --request-id REQUEST_UUID
threemind storage policy --category note-image --json policy.json --request-id POLICY_REQUEST_UUID
threemind storage resource-register --json resource.json --request-id RESOURCE_REQUEST_UUID
threemind storage resource --id RESOURCE_ID
threemind storage plan --json migration.json --request-id PLAN_REQUEST_UUID
threemind storage execute --id PLAN_UUID --request-id COPY_REQUEST_UUID
threemind storage status --id PLAN_UUID
threemind storage verify --id PLAN_UUID --request-id VERIFY_REQUEST_UUID
threemind storage activate --id PLAN_UUID --expected-revision RESOURCE_REVISION --request-id ACTIVATE_REQUEST_UUID
```

`policy.json` contains `target_id` and the current policy's `expected_revision`. A resource request contains `resource_id`, `target_id`, `relative_path`, `writer_mode` and `expected_revision`, optionally explicit `legacy_paths`. A migration request contains the resource, destination target/path and current resource revision; the CLI can provide its stable `request_id`.

Unknown writers permit inspection only. `sealed` means writing has actually stopped; `cooperative` requires the program to implement the storage lock and writer protocol. A declaration cannot make an old script safe automatically.

The sequence is **plan → copy → verify → separately activate**. Copy leaves the source mapping unchanged; activation retains original files. `resume` continues from verified file boundaries; `cancel` stops copying. `rollback --expected-revision ...` is conditional mapping rollback: later writes or registration changes can require a reverse migration plan. Inspect uncertain outcomes before retrying, and reuse the original request ID. `threemind storage receipt --id REQUEST_UUID` reads the host journal.

The host UI also lists archived repository originals from exact verified manifests. `threemind storage artifacts --json filters.json` supports, for example, `{"q":"E63","offset":0,"limit":50}`. `threemind storage artifact --id research-artifact:RESOURCE_HASH --output original.json.gz` downloads only a registered original, with server-side raw-byte verification. No arbitrary archive directory is scanned.

Host administrators may inspect and package an explicitly registered offline directory whose writer is sealed or implements the cooperative protocol. Host storage tools are available even without a research project. The archive preserves every regular scientific file within the selected resource and its raw-byte hash. It does not infer outside dependencies or invent a project, execution history or complete-subject recovery. Project import registers it as read-only origin data, separately from native report/note restoration and dedicated subject resumption.

The approved repository archive is registered as 29 sealed `archived-study:<original-directory-name>` resources; benchmark document data uses `archived-study:docs`. These can be selected directly. Other real experiment directories were not automatically registered or migrated.

```powershell
threemind storage resource --id RESOURCE_ID
threemind storage export --id RESOURCE_ID --expected-revision RESOURCE_REVISION --request-id EXPORT_UUID
threemind storage export-status --id EXPORT_UUID
threemind storage export-manifest --id EXPORT_UUID --output offline.tmdata.json
threemind storage export-download --id EXPORT_UUID --volume 0 --output offline.v001.tmdata
threemind data preflight --project PROJECT_UUID --manifest-file offline.tmdata.json --file offline.v001.tmdata
threemind data import --project PROJECT_UUID --manifest-file offline.tmdata.json --file offline.v001.tmdata --request-id IMPORT_UUID
```

Download and supply every volume for a multivolume archive. Exports use the fixed host control directory `data-transfers/host-EXPORT_UUID`; REST accepts no arbitrary output directory. Reading the export receipt or downloading requires host administration. Each manifest and volume is checked against its registered byte count and SHA-256. Export neither modifies source files nor activates a location change.

## Integrity, cleanup and backup

Integrity distinguishes logical object bytes from database indexes/WAL and physical backend allocation. `threemind data integrity --project PROJECT_UUID --verify --maximum-bytes 1073741824` verifies a bounded set of caller-visible originals. The UI also retains the existing experiment storage audit and model-library archive/cleanup tools.

`threemind data candidates --project PROJECT_UUID --limit 200` inspects unregistered upload candidates using bounded control logs, without scanning a bucket or arbitrary directory. Unknown, unfinished and recent candidates require diagnosis, not automatic deletion. `cleanup-preview --id CANDIDATE_UUID` returns current references, blockers and a token. Human execution additionally requires `cleanup --id ... --token ... --confirm-name ...` with the exact object name. Registered or referenced immutable originals are protected. Agent/MCP cleanup access is query/preview only. Archival, task cancellation and permanent deletion are distinct operations.

Administrators perform backups manually on the host. The administration connection comes only from `THREEMIND_BACKUP_DATABASE_URL`:

```powershell
threemind storage backup --pg-bin C:/PostgreSQL/bin create E:/Backups/ThreeMind-2026-10-10
threemind storage backup inspect E:/Backups/ThreeMind-2026-10-10
threemind storage backup --pg-bin C:/PostgreSQL/bin restore E:/Backups/ThreeMind-2026-10-10 --new-database restored_threemind --external-root E:/RestoredThreeMind
```

Backups include PostgreSQL, explicitly registered external originals, location metadata and verification manifests. Preserve actual encryption keys separately; `--key-id` records identifiers only. Restoration requires a new database and new external directory, returning an unactivated result. It cannot overwrite production or replace a running subject. Administrators must deploy migrations 060/061 explicitly following [operations](operations.md), then verify their deployment; isolated acceptance does not mean the real environment has been upgraded.

## REST, agents and report editions

Project routes are rooted at `/api/v2/projects/{project}/data`: inventory, details, export plans/tasks, task status/cancel, import preflight/registration, bundles, native restoration, origin objects, resume planning, integrity and cleanup preview. Host routes are rooted at `/api/v2/storage`. The common operation catalog exposes project/host scope, permissions, durable receipts, human confirmation and actual rollback limits to UI, CLI and MCP. A transport does not bypass canonical service checks.

Original repository report URLs still return their original edition. `/api/v2/documents/versions?path=...` lists related editions; `content?path=...&revision=2` selects an edition and `latest=true` explicitly selects the latest, mutually exclusively. `threemind report-revisions versions --path lab/EXPERIMENT/report.en.md` lists editions. `revise` requires a body file, reason, date, stable operation UUID, expected parent edition and its original hash. A revision must describe completed work, never claim that an unperformed migration has happened.

Report `sha256` preserves publication-time bytes. New registries also record `canonical_sha256` and `canonicalization=utf8-crlf-to-lf/1`, permitting only Git checkout CRLF/LF differences. Reads expose actual `read_sha256`, `byte_identity_matches` and `integrity`, distinguishing raw originals from Git text identity. Older registries without these fields remain strictly byte-verified. Experimental originals, media, packages and export bytes retain strict raw-byte validation.

## Local database and native-extension updates

This workstation uses `.work/kernel-venv`. SQL migration and Rust installation are separate operations: `migrate` applies unapplied SQL in order but does not compile/install the native module. `PYTHONPATH=src` does not update an installed `.pyd`. Pause tasks, normally exit the workstation and independent workers, and keep PostgreSQL running.

```powershell
Set-Location E:\WORKSPACE\AgentWork\threemind
$env:PYTHONPATH = "$PWD\src"
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli migrate
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli doctor
```

Migration reads `THREEMIND_MIGRATION_DATABASE_URL` from project `.env` and reports `Schema is up to date.`. Doctor verifies current schema, connection and actual native kernel loading, not complete scientific-data roundtrips. Missing configuration requires the appropriate connection variable, not reinitialization through `setup-local`.

After source updates, `unknown continuous kernel identity` or missing `NativeLocal` means the current Rust extension must be installed into the same interpreter environment. Do not change old individuals or choose another default kernel to hide the mismatch. Explicit wheel construction/installation is available; `--offline` requires cached Rust dependencies:

```powershell
.\.work\kernel-venv\Scripts\python.exe -m maturin build --release --offline --manifest-path crates/threemind-native/Cargo.toml --out .work/native-update/wheels
.\.work\kernel-venv\Scripts\python.exe -m pip install --no-index --no-deps --force-reinstall .\.work\native-update\wheels\threemind_native-2.0.0-cp311-abi3-win_amd64.whl
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli doctor
```

Use the actual output wheel name when package versions change. Installation already completed on this host on October 10: all seven implemented kernels load natively, so no reinstall is required. Normal startup uses `scripts/start-lab.ps1 -Python .work/kernel-venv/Scripts/python.exe`. Doctor now closes its pool on failure as well as success. No workstation startup or historical-individual change occurred.
