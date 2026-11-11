# Implementation plan for data management, storage separation and formal data bundles

[中文](../../zh/plans/data-management-and-storage-separation.md)

**October 10, 2026 implementation status: P1–P5 local cleanup, development and isolated acceptance complete.** Revision 1 and intermediate pending statements below remain contemporary records. See [delivery](data-management-delivery.md) and [guide](../data-management.md) for current facts. Only reviewed artifacts were relocated; other migration, real database deployment and remote rewriting were not executed.

Date: 2026-10-09. Revision 1 combines this conversation's earlier Git cleanup plan, seven storage safeguards, and recommendations for formal data bundles and centralized management. The user approved these recommendations and requested a plan update. The earlier complete draft existed only in the conversation; this is the first complete plan saved in the repository. It does not rewrite earlier plans or experiment reports.

**Status: approved, awaiting implementation. This update records plans and decisions only; no artifacts have been moved, Git history rewritten, data migrated, cloud services called, or running services changed.** The interfaces and acceptance criteria in this document are implementation targets, not capabilities already delivered.

## 1. Goals, authorization and implementation boundaries

- First clean up mistakenly committed artifacts and similar cases, then deliver unified data management, configurable data locations, formal bundle import/export and migration tools. Data management is included in this phase; do not create another independent store of authoritative facts.
- Actual relocation in this phase is limited to mistakenly committed experiment artifacts approved in the inventory. Their destination is the ignored `data/experiments/<original-experiment-directory>/<original-relative-path>`. Migration of other existing data is implemented and verified with temporary fixtures only, pending a separate explicit operation.
- Preserve the complete bytes of original evidence, earlier reports and fixed criteria, original version/implementation identities, and all established older kernels. Do not rerun experiments or change Core dynamics, individuals, peripherals, observation or simulation timing.
- Do not automatically perform real cloud transfers, permanent deletion or upgrades to the existing database. Validate schema upgrade scripts in an isolated database; deployment operations are performed separately. Do not take over user services or push.
- New functionality must not migrate data on startup or move existing resources when settings change. Do not automatically classify historical data as disposable based on failure status, zero results, filenames or having been exported.
- This phase introduces no second authoritative database, independent MQ, database sharding, global deduplication across projects, multiple writers through cloud synchronization, or arbitrary version conversion. Without measurements from the actual deployment, do not present architectural risks as measured bottlenecks.

## 2. Current facts and gaps to address

These conclusions come from source/Git review on 2026-10-09 and do not constitute acceptance testing of the actual deployment:

| Current fact | Work in this phase |
| --- | --- |
| PostgreSQL is Lab's authoritative store; Core does not query a database; checkpoints already have full anchors and bounded delta chains | Preserve this boundary, the checkpoint causal representation and earlier hashes |
| Experiment storage inspection, model archives, experiment bundle pages and API/CLI/MCP already exist | Integrate them into one data management entry point with shared permission, reference and task services |
| Generic experiment bundles start from one run/latest checkpoint, with attachments explicitly selected; import registers a read-only archive before continuation creates a new paused identity | Add formal data bundles and typed restorers; do not claim that current bundles already support round trips for all data |
| Language and population have dedicated bundles; the generic bundle does not automatically include all dependencies such as language peripherals | Add dependency checks and dedicated validators; disable continuation when dependencies or a coordinator are missing |
| Database reports already support multiple immutable revisions; repository Markdown lacks version associations, and the generic publication tool creates only the first revision | Reuse database revisions and add repository version registration and revision publication |
| Database artifacts for public reports are protected by immutability triggers | Extend reference/retention constraints to externally stored bytes; protecting the database index alone is insufficient |
| Experiment bundle upload budgets sum declared upload bytes; canceling a task does not release interrupted upload chunks | Add staging lifecycle management, cancellation/expiration/recovery and cleanup previews; referenced originals are not disposable cache |
| Storage inspection explicitly omits some media, WAL and index costs and does not expand free-text references | Separate logical size, physical size, staging, cache and reclaimable space; conservatively protect unknown references |

Main code entry points: `src/threemind_lab/{database,media_store,experiment_archive,experiment_bundles,bundle_api,model_library,storage_audit,research_documents,report_shares}.py`; first report publication uses `lab/tools/study_publication.py`. Existing descriptions: [storage (Chinese)](../../zh/v2-storage.md), [model archives (Chinese)](../../zh/v2-model-library.md), [backup and cleanup](backup-and-cleanup.md), and the [original research tooling implementation record](research-tooling-and-candidate-experiments.md). A4/A5 completion in that record refers only to the scope delivered then, not the additional capabilities in this plan.

## 3. Git history cleanup and evidence revisions

### 3.1 Inventory, archiving and history rewriting

1. Build an exact file inventory without bulk-reading unrelated historical data: original and historical paths, experiment identity, relevant commits, bytes, SHA-256, destination and classification rationale.
2. Start with generated artifacts in `2026-10-08-retention-telemetry-text` and `2026-10-08-retention-repair`, then address other raw trajectories, large per-item results, pages embedding complete data, and compressed evidence/implementation snapshots found by the audit. Keep compact summaries, source code, protocols, necessary frozen fixtures and documentation; do not remove every JSON/GZ file by suffix.
3. The two batches previously totaled about 64.8 MiB of added files, with other similar artifacts also present. This is logical file size, not the eventual Git space saving. Before execution, recheck the current branch, worktree, all references and object sizes.
4. Place a complete backup of the old Git repository in the ignored `data/git-backups/<batch>`, independent of the active object store, and verify that it can be restored. The backup still occupies local space; report active repository and evidence backup sizes separately.
5. Copy artifacts into the data area and verify every file. Preserve original manifests, source, inputs, results, fingerprints and failure evidence; do not change internal `source_commit` values. Location registration links original paths, logical resources and checksums.
6. After adding the minimal location resolution and report revision support, use `git-filter-repo` with the explicit inventory in a fresh isolated clone with no alternates or shared object store to remove all relevant historical paths. Preserve code history and produce an old/new commit map. Do not rebuild the repository as a single root commit.
7. Replace local Git metadata only after confirming that the worktree, index and original HEAD have not changed. Remove backup references, remote-tracking references and reflogs that still retain old objects in the active store, then repack using the tool's safe procedure. Stop on concurrent changes; do not overwrite others' work.
8. Retain the old Git backup, original experiment bytes and commit map. Never rewrite commit values to make original fingerprints appear to match a new implementation. Actual restoration remains subject to original implementation validation.

This phase cleans local history only and does not force-push. Preserve remote configuration and expected old reference values, and provide later remote synchronization steps. A smaller local repository does not mean server history has been cleaned; do not directly merge with the unrevised remote.

### 3.2 Preventing recurrence and revising reports

- Improve exact generated-path ignore rules and `scripts/check-git-data.py`. Block recognized raw artifacts regardless of size; require classification review for files reaching 1 MiB unless explicitly allowed. Explicitly allow necessary frozen fixtures, summaries and derived documentation examples; do not relax a global limit to allow whole data batches.
- Replace large documentation resources with small derived examples while retaining evidence references to the originals. Maintained shared writers use location resolution; do not bulk-edit frozen historical script sources. Execute those scripts in isolated reproduction directories.
- Add `report-revisions.json` beside repository reports to register series, language, revision, parent revision, date, reason, relative path and content hash. Revision files use the original name plus an identifier such as `.r2`; preserve original file contents and links.
- A revised report opens with the reason for relocation/correction and links to the original. Change location references and current status only; do not silently alter conclusions, criteria or missing evidence. Write “relocated” only after actual relocation succeeds.
- Use a shared revision writer and `Publication.revise_document()` with parent checks, expected revision, idempotent operations and atomic registration. Database reports append the next revision under the same identity; old exports and shares remain bound to their original revision.
- Readers offer the original, a specified revision and the latest revision. Evidence links resolve through registered logical locations and existing permissions, without exposing an entire external file root.

## 4. Storage architecture, configuration and lifecycle

### 4.1 Three responsibilities and default policies

PostgreSQL remains the authoritative record layer. A unified interface accesses immutable resources in the database/files/S3; rebuildable caches are managed separately. New registrations and tasks belong to the host and do not participate in Core, propagation, learning, forgetting or simulation scheduling.

| Data | Supported locations | Default/constraint |
| --- | --- | --- |
| Runs, checkpoints, converted frames, causal input/output records, individual scientific learning state, permissions and report versions | PostgreSQL | Preserve the existing authoritative store; binary MIME does not make these ordinary files eligible for external storage |
| Active offline experiment directories | Registered local/shared file roots | Existing individuals keep their current locations; new maintained entry points default the research root to `data/experiments/` |
| Images, original audio/video and export bundles | PostgreSQL/file directory/S3 | Preserve each category's current default; existing media/artifacts remain in the database, and existing file export defaults do not change |
| Sealed research directories | File directory; S3 after packaging | Do not present object storage as an appendable directory |
| Caches, download staging, builds and dependencies | Local host directory | Bounded; do not move all of `.work`, and preserve existing specialized overrides |

- `ResearchStorage` handles research directory resolution, registration, sealing and migration; `BlobStore` handles immutable bytes. Share validation and receipts without creating a second set of run facts.
- Classification configuration is limited to the image/audio/video/export semantics above; suffix or MIME alone is insufficient. Database, file and S3 settings affect new writes only.
- Each resource binds its actual backend, `target_id/config_revision`, relative object key, size, content hash and any required S3 object version. Old records default to the database. Referenced configuration versions cannot be overwritten, deleted or changed to another bucket in a way that disconnects existing resources.
- Register file roots under stable deployment/host identities, separate from worker session identities. Pin the target and policy revision when creating a job; only workers with the actual required read/write access may claim it.
- Host control configuration, registrations, migration logs and key identifiers live in a control area excluded from migration, defaulting to `data/storage-control/`. Run management records remain in the database, without a second copy of scientific state. Continue using existing pause/checkpoint/configuration-change procedures.
- Treat cloud synchronization directories as ordinary file roots; cloud drive software performs synchronization. Support only the declared local single-writer/sealed-archive use, without promising locks across hosts. Active PostgreSQL/SQLite databases do not enter synchronization directories.
- S3 is an optional dependency, configured with endpoint, bucket, prefix and encrypted credential references. Reuse the existing `SecretBox`; returned configuration shows only whether secrets are set. Saving configuration or displaying capabilities does not automatically contact the cloud; display “configured, not yet verified.”

### 4.2 Transactions, reads and retention

- Stage/multipart-upload and verify external bytes first. Then use a short database transaction to recheck permissions, request identity, target version and lease generation before committing complete references. Database failure leaves only registered unreferenced candidates, not a partial stimulus or visible partial evidence.
- Continuous capture still commits frozen configuration, sequence numbers, encoder state, original-byte references and converted frames together. Move network upload outside the transaction holding the run lock, then revalidate before committing. Retries use the same identity, without skipping chunks, resetting sensory state or changing simulation steps.
- Ordinary downloads, media, note images, report sources/shares, analysis tools, experiment packaging and restoration all use the unified read interface. Existing scientific weights may remain in the database. Do not change UI downloads alone while missing bundle export/restoration.
- Local storage uses relative keys constrained to a registered root, staged files, checksums and atomic publication. S3 uses immutable keys, bounded concurrency/retries/timeouts, multipart-upload cancellation and SHA-256 verification; ETag does not replace full integrity checks.
- Caches have capacity limits. Missing/corrupt/unavailable content explicitly blocks an operation or returns an error, never empty evidence. Slow external reads must not hold database transactions or connections for long periods; preserve existing fencing of expired workers.
- Extend immutability/reference protection for original reports, note revisions, sources, shares, lineage, frozen studies and restoration chains to objects. Deduplication is within a project only; private notes remain readable under author permissions.
- Register and commit reference deletion and external deletion requests before rechecking references and reclaiming objects. Do not delete external originals first inside a transaction that may roll back. Process registered candidates only; do not classify everything under a bucket prefix as disposable.
- Staging records distinguish receiving, processing, completed-and-referenced, canceled, expired and pending-cleanup states. Only expired, unreferenced records without active leases can enter cleanup plans. Original uploaded bytes of formal bundles remain evidence and are not deleted as staging. This phase does not use these rules to clean real historical data.

## 5. Formal data bundles, export and import

### 5.1 Contract and selection dimensions

Add the `threemind.data-bundle/1` contract and `.tmdata` entry point, reusing streaming chunks, path/member/budget checks and hash utilities. Existing `.tmexperiment`, report evidence ZIPs, and language/population bundles retain their original protocols and capabilities; a type registry dispatches validators without silently upgrading old bundles. Add the new extension and volumes to Git data protection.

| Bundle/export purpose | Commitment |
| --- | --- |
| Analytical subsets such as CSV, charts and JSONL | Readable/analyzable; not represented as complete restorable experiments |
| Formal research archive bundle | Complete registration of original material, versions and relationships; can be reimported for querying; implemented types can restore native records |
| Complete bundle validated by its corresponding restorer | Restores the complete subject/system under matching versions, dependencies and external conditions; paused by default |

- Export selection supports experiments, individuals/populations, batches/datasets, projects, tags and time ranges. Combine filters for data type, backend and archive status. A time subset does not automatically qualify for continuation.
- An export plan freezes scope and a consistent commit boundary, automatically collecting required dependencies and historical revisions. Include the selected objects' complete history by default; for subsets, explicitly state included/excluded coverage and lost restoration capabilities.
- The closure covers Core, peripheral weights and learning state, mappings, body, random state, readouts, inputs, checkpoint anchor/delta dependencies, coordinators, fixed report sources and artifacts, note collections/revisions/attachments, and the originals actually used.
- Private notes include only content the caller may view. Other authors' private records, user accounts/credentials, device authorization and running service processes are excluded from default research bundles. Project export does not grant broader access.
- If a generic bundle cannot restore a coordinator or unknown object type, preserve its originals and description completely and label it read-only material. Do not fill gaps with blank peripherals/coordinators. Orphaned historical files may be material attachments; list missing metadata explicitly rather than inventing it.
- Include logical object/version identity, provenance, original hashes, dependencies, commit boundaries, bundle/object schemas, kernel/implementation identities, restorers and three independent capabilities: viewing, record restoration and continuation. SHA-256 provides integrity checks; it is not a digital signature.
- Carry every byte required for restoration inside the bundle. Local paths, S3 URLs or references inaccessible to the target machine cannot substitute for those bytes. List optional missing material as limitations; required missing members prevent complete validation.
- Large bundles use a master manifest and hashes for each volume, reusing bounded sub-bundles. By default, retain existing limits of 8 GiB compressed/20 GiB expanded per volume. Publish the complete bundle only after all volumes are present and verified. Total budgets can be explicitly configured; do not silently trim content to satisfy them.

### 5.2 Import and restoration

The flow is preflight → read-only registration of the original bundle → native-record restoration/restoration plan → explicit commit. Import and starting execution are separate operations.

- Preflight revalidates the manifest, all members, versions, resource budgets, complete dependencies, restorer capability and target permissions. Merely having `manifest.json` does not authorize execution. Do not import arbitrary SQL/executable serialization or automatically execute source code in the bundle.
- Reject unknown outer bundle schemas for formal import. Unsupported object schemas inside a known `data-bundle/1` may retain their original bytes and be registered read-only, without native restoration or continuation. A bundle missing dependencies required for restoration cannot claim complete restoration capability; if only optional material is missing, preserve explicit limitations.
- First retain original bundle bytes, IDs, authors, timestamps and hashes as provenance evidence. The target uses new identities/namespaces and explicit mappings, without overwriting equal UUIDs or merging different experiments because names or hashes match.
- Reports and the caller's own notes support native-record restoration: preserve all historical revisions, parent/reference/attachment relationships, and original author/time provenance. New objects follow current permissions. Record original and imported-projection hashes separately; do not pretend remapped objects are still the originals.
- Restore fixed report captures and their source evidence/attachment dependencies with the bundle. Resolve old project/artifact/note-image/source links in bodies and metadata through registered identity mappings in the imported projection, while retaining original text separately and unchanged. Sources that cannot be represented natively attach as read-only origin material; do not fabricate runs, AI calls or execution records to satisfy foreign keys.
- Original source research records may be queried as read-only research datasets; supported restorers restore complete executable objects. Content without a validator remains read-only rather than being forced into active tables. Project import is not a full database backup or role restoration.
- Fixed share metadata and original exports may be retained as evidence. Original public URLs, credentials and authorizations do not become active automatically; republication follows the current owner's existing workflow.
- Ordinary models/existing dedicated bundles continue through their existing importers. The unified entry point can invoke them after registered type validation, without weakening compatibility checks. Do not reset or automatically upgrade kernels, scientific clocks, input cursors, random state or learning state.
- Requests are idempotent and concurrent operations check conflicts; inactive staging is not visible. Publish database restoration only after the entire transaction succeeds. Recover failed external object operations through staging/receipts, without leaving a usable partial subject.
- Restoration is paused by default. Explain changes in external telemetry, device reconnection and target execution conditions separately; successful import does not prove identical live inputs. Automatic merging across experiments, arbitrary version conversion and whole-study continuation with unknown coordinators are deferred.

## 6. Unified data management and migration interfaces

### 6.1 Management entry point and operation boundaries

Add a “Data management” UI menu that integrates storage inspection, model archives, bundle management and revision viewing; retain compatible navigation from existing entry points. Provide resource lists/details, import/export, storage targets/migration and task receipt pages usable on desktop and narrow screens.

- Queries support project, experiment, individual, batch, type, backend, tag, time and archive status. Details show size, provenance, revisions, references, location, restoration capabilities and verification status, without expanding large bodies by default.
- Project operations use `/api/v2/projects/{project}/data`; host target and migration management uses `/api/v2/storage`. The service layer reuses existing facts, permissions and task services; endpoints permit neither arbitrary SQL nor arbitrary host directory scans.
- CLI provides `threemind data` for queries, inspection, export planning/execution, import preflight/restoration and `cleanup preview/execute`; `threemind storage` handles targets, inspection, migration and status. Cleanup execution requires a preview token and object name, with references checked again. Keep existing bundle upload/download commands compatible.
- API/UI/CLI/Agent use the same operation catalog and services. Add host scope, durable receipts and accurate rollback descriptions; do not label file migration as undoable through a checkpoint fork. Agents accept only registered target/resource/plan IDs.
- Administrators configure roots/secrets. Project resource operations continue under roles and private-note permissions; administrators do not automatically bypass project boundaries. Provide programmatic interfaces and request identities for migration, packaging and import.
- Permanent cleanup retains the human workflow: UI/CLI must obtain a preview token and confirm the object name; the backend rechecks references and scope before committing. Agents provide queries/previews only, without a universal delete operation bypassing the existing human-controlled `cleanup` constraints.
- Distinguish archiving, redundant-copy removal, staging reclamation and permanent cleanup. Active runs and report/lineage/restoration/frozen-experiment references continue to block deletion. Do not bypass immutability triggers to delete report or note history. Successful export does not automatically authorize deletion.
- Risk previews show the actual scope, blockers, space requirements, whether pausing is needed, whether sources are retained and whether rollback is possible, rather than a generic warning. Confirmation does not waive reference constraints.

### 6.2 Migration service

One service provides `inspect / plan / execute / status / resume / cancel / verify / activate / rollback`. Project resource tasks reuse existing job leases/generations and capability matching. Offline directories across projects use an independent host task journal and OS locks, without creating a fictitious project.

- A plan pins the resource inventory, source/destination, configuration revisions, sizes/hashes and request identity. Execution accepts a saved plan ID only and rechecks paths, space, unchanged sources and absence of active writers.
- The flow is staged copy → verification → complete publication → separate activation of the location mapping. Retain sources by default; do not automatically dual-write, delete sources or start migration jobs on boot.
- Save progress across interruptions. Retrying the same identity returns the original task; cancellation retains old sources and inactive targets. Explicitly reject existing targets with different content, out-of-bounds paths, symlink/junction escapes, migrations nested into the control area, insufficient space and changed sources.
- The operator must pause/stop writes to active research first and acquire the actual lock. An idle new lock is not evidence that historical scripts have stopped writing. Reject historical writers whose safety cannot be established.
- Map physical locations through registration while preserving original scientific registration paths/parameters/seeds/implementation fingerprints as evidence. Relocation does not relax restoration checks. Do not claim transparent compatibility for isolated historical scripts.
- Activation switches locations using a registration revision comparison. If new writes occur afterward, rollback requires a reverse plan rather than blindly switching to the old source. Source deletion and cleanup of canceled fragments are separate explicit operations.
- In this phase, execute migrations only in temporary directories/databases and against a local S3 test service. Archiving mistakenly committed artifacts is the sole authorized exception for actual file relocation.

## 7. Capacity, integrity and backups across backends

- The capacity page distinguishes logical reference bytes, actual object bytes, database/index/WAL costs, staging, rebuildable cache and explicitly reclaimable space. Mark unknown quantities as unknown; estimates are not releasable space. Count a shared object's physical size once.
- Read metadata with bounded pagination by default. Complete hash scans are explicitly triggered, cancelable and budgeted; do not scan all files or the entire bucket every time a page opens.
- Audits show missing/corrupt objects, unreachable backends, unreferenced candidates, stale uploads and reference blockers. Statistics, migration and cleanup previews share the registration interface. A conservative audit failing to find a reference does not prove there is none.
- Backup tools produce a master manifest of a consistent database snapshot, its referenced immutable external objects and hashes, implementation version, target configuration and key identifiers. Keep actual keys separately and securely, outside public bundles/Git.
- Pin retention leases for objects needed by the snapshot during backup to prevent concurrent reclamation. Full database backup uses a sufficiently privileged backup account; separately register roles/privileges rather than treating the application's RLS view as a whole-database backup.
- Restore into isolated locations/a new database and check complete members/dependencies, versions/permissions and consistent whole-subject continuation. Opening a ZIP is not restoration acceptance. A research bundle does not replace database and key backups.
- This phase implements manually triggered backup/inspection entry points and restoration drills. It creates no scheduled tasks and does not back up, restore or clean real user data.

## 8. Implementation phases and acceptance

| Phase | Deliverables and passing conditions |
| --- | --- |
| P0 Record the plan | Bilingual plan, original decisions/review evidence, synchronized backlog and modern/Classical Chinese histories; status states approved, awaiting implementation only |
| P1 Complete Git cleanup first | Exact inventory, verified original-byte copies, minimal location/report revision support, protection checks, old repository backup, isolated filtering/verification, local switch and commit map; no push |
| P2 Storage separation | ResearchStorage/BlobStore, constrained category configuration, identities/target capabilities, all related read/write paths and staging lifecycle; existing defaults and reads unchanged |
| P3 Formal bundle round trips | Type registration, selection dimensions and dependency closure, volumes, read-only registration, native report/note restoration and existing restorers; unknown types stay read-only |
| P4 Management and migration | Unified UI/REST/CLI/Agent resource operations, risk previews, receipts, migration recovery/activation, capacity/integrity and backup tools |
| P5 Acceptance and delivery | Isolated fault/round-trip/restoration and UI acceptance, usage documentation, actual limitations and repository size report; no start of real data migration |

Each phase may be committed locally, without pushing. P1 first implements only the minimal report/location support required for cleanup; later phases complete the generic capabilities. Do not delete originals merely because complete data management has not yet been delivered.

Required verification:

1. **Evidence and Git:** original bytes/earlier reports/frozen fixtures stay unchanged; active history contains none of the inventoried artifacts; the old backup restores; checks block regenerated artifacts; report repository packs, worktree data and backup sizes separately.
2. **Backends and permissions:** policy changes affect new writes only; old targets remain readable; downloads, shares, analysis, packaging and restoration behave consistently on all three backends; project/author permissions, path boundaries, target capabilities and pinned configuration are correct.
3. **Faults and lifecycle:** upload success followed by database commit failure, expired leases, process exit, cancellation, missing/corrupt objects, target changes and insufficient budgets create no partial stimuli or executable partial subjects; evidence references prevent erroneous staging deletion.
4. **Formal bundle round trips:** object counts, historical revision counts, original-byte hashes and original references are traceable for every supported type; images, artifacts and fixed sources for every historical revision remain readable in the new project; equal names/UUIDs do not overwrite; missing volumes/unknown outer protocols reject formal import, unknown objects remain read-only, and missing dependencies/forged claims reject complete restoration; shares do not become public automatically.
5. **Whole subjects and compatibility:** identical simulation inputs preserve Core, peripherals/optimizers, body, mappings, readouts, random state, inputs/queues and time phase; old bundles/kernels are not upgraded; unknown types cannot continue; restoration is paused by default.
6. **Migration:** temporary complete subjects and material exercise planning, concurrency, interruption recovery, idempotence, cancellation, verification, activation and controlled rollback; active writers, changed sources, junction escapes and control-area boundary violations are rejected; actual relocation is limited to the P1 inventory.
7. **Backups and costs:** an isolated database plus external objects restores completely; missing objects/keys are clearly diagnosable; measure Core, storage, compression, export and query costs separately, without claiming that reduced duplicate data storage improves dynamics performance.
8. **Documentation and UI:** bilingual content, report versions, data operations and task receipts work; narrow screens do not hide risk scope; history catalog/link validation passes.

Continue maintaining the [research backlog](research-backlog.md), bilingual modern histories and both Classical Chinese adaptations throughout delivery. Distinguish approval, implementation, measured results and unverified claims. Preserve original E64/E65/E66 evidence, original `/2`/`/3`/`/4` evidence and their contemporary conclusions; location revisions do not change what that evidence establishes.

## 9. Revision record for this turn

- 2026-10-09, r1: saved the conversational plan, combining seven storage safeguards, configurable database/file/S3 categories, formal data bundle round trips by experiment and other dimensions, centralized data management and risk previews. Actual relocation in this phase concerns mistakenly committed artifacts only; other migration, cleanup and cloud operations are development/isolated-validation scope only. This records an approved plan, not a completion report.

- 2026-10-10: The user explicitly authorized implementation. P1 original-byte copying/verification and appended report-location editions are complete; independent Git filtering/replacement remains pending. P2–P4 are under development. General migration uses isolated validation without changing the real database.

- October 10, 2026 delivery: 229 commits and raw Codex snapshot trees independently filtered and switched locally; source duplicates of 1,445 paths removed only after verification. Full original-repository restoration passed. P2–P4 provide storage, formal packages, native restoration, specialized paused copies, UI/API/CLI/Agent, migration and backup. P5 completes isolated acceptance/documentation. The 29 sealed P1 directories are registered host resources, with read-only formal-package reimport rather than inferred external dependencies or full-subject eligibility. Private carrier ACLs and source target capabilities are enforced; imported provenance does not fabricate original runs/jobs/AI calls. See [delivery](data-management-delivery.md). No other actual migration, real database upgrade, cloud access or push.

- Later October 10: the user migrated the everyday local DB; the missed native installation supporting only through /2 is repaired and current schema/native doctor passes. Earlier undeployed statements describe the original delivery, not an online environment. Other actual migration remains unexecuted. See delivery addendum and guide.
