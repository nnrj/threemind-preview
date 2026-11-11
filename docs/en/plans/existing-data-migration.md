# Existing-data migration and unified storage

**Current state, October 10, 2026: the approved selection has moved and `E:\ThreeMindData` is active with real schema 65. All 43 resources, 32,984 files and 4,242 database payloads pass copying, hash and new-placement checks. Running checkpoints still default to database. The joint backup was restored in isolation; sources and older complete backups remain. Earlier phase records below are preserved. See the [actual delivery](existing-data-migration-delivery.md).**

[中文](../../zh/plans/existing-data-migration.md) · Implementation approved 2026-10-10

## Scope

The database retains research records and frequently queried data; a unified original-object service manages immutable payloads without requiring a separate file server. The universal default remains the repository `data` directory. This migration selects `E:\ThreeMindData`. `THREEMIND_DATA_ROOT` does not relocate PostgreSQL's physical database. Core dynamics, identities, kernels, results, simulation time, and the independent Runtime's optional SQLite remain unchanged.

Lifecycle and location are independent. Report/note bodies and revisions, ordered inputs, metrics, recovery cursors and graph projections remain relational. Media, acquisition files, formal packages and confirmed historical originals use unified file storage. Running checkpoints default to `database`; add the explicit host option `filesystem`. Only completed, sealed checkpoints with complete verified dependencies may be archived externally. A whole subject includes Core, peripheral learning state, body, mappings, randomness and readout history.

## Sequence

1. Save this bilingual plan; classify registered resources, database payloads and historical references as formal originals, source documents, frozen fixtures, temporary data or gaps. The initial 157 resources are not an experiment count.
2. Implement batch root changes, versioned locations, database-payload migration, optional file checkpoints and joint backup through one service shared by UI, REST, CLI and Agent. Validate in isolation before modifying the real database.
3. Use the configured local backup administrator to back up the current database, registered originals and fixed control metadata; verify an isolated restore. Retain previous backups; no paid backup service.
4. Prioritize E64–E66, retention comparisons and /4, then all confirmed formal evidence. Do not move entire `.work` or `lab` trees. Git source, protocols, reports and frozen fixtures stay in place.
5. Copy, verify and transactionally activate media, note images, packages and eligible sealed checkpoints in batches. Paused/developing subjects, incomplete dependencies and failed restores keep their database path.
6. Verify reads, recovery, import/export and backup at the new location, then activate the root and future write policies. Existing objects resolve their registered locations. Failures retain the source and are reported as partial or blocked.

Root changes support preview, execution, status, resume, cancel, verification and rollback. Raw configuration changes cannot silently migrate or hide previously registered data. Host control metadata and keys remain fixed. Locations may change, scientific hashes and provenance may not. File checkpoints are durable and verified before transactional publication with input, observation and recovery references. Failure never acknowledges a save, skips an input or clears a subject. Source copies remain; cleanup requires a separate exact preview. Respect cooperative writer locks or confirmed pauses; do not take over user services.

## Acceptance and delivery

Verify relational query paths, identical trajectories, whole-system/delta-chain recovery, independent SQLite, failures/retries, permissions, exact bytes and references. New-location verification must not fall back to retained sources. Measure database, originals, copies and backup separately, as well as queries, encoding, saves, I/O and recovery. Detailed manifests/receipts belong in managed storage; public reports contain aggregate results.

Synchronize T10/T11, bilingual guidance and modern histories, and both Classical Chinese adaptations. Preserve original reports and append location revisions explaining the migration. Commit local phases; do not push.

## Status

2026-10-10: implementation started. Saving this plan is not evidence of completed backup, migration or acceptance. Dated delivery receipts and measured results will be recorded separately.

Later October 10: tools and isolated acceptance complete; pause for user-operated disk cleanup. The real database remains schema 63, with no current joint backup, schema 64 installation or actual relocation. Exact preview requires 61.69 GiB plus 15 GiB reserve; E has about 55.65 GiB free. Another 114 registered resources await classification; no checkpoints were automatically sealed. [Handoff, cleanup and measurements](existing-data-migration-stage.md) · [Guide](../storage-migration.md)

October 10 resumption: after moving unrelated files, the user has about 138 GiB free on E; ThreeMind originals remain. Real schema is 63 with matching witnesses and no active writers. All 35,374 file references pass size/SHA-256 checks. Explicit isolated tablespace routing and reduced repeated metadata checks support safe execution across drives; Core/old subjects remain. Begin the current joint backup/recovery, with results appended later rather than predeclaring relocation.

October 10 interruption audit: after stopping the previous turn, the user requests a background-process check to avoid duplicate execution. The recovery log failed after 3,146.27 seconds because a historical colon-containing target ID was rejected as a filesystem path. Database copying had finished; external files had not been published. The current complete backup remains; real schema is 63 with no active jobs or root-switch receipt. The owned isolated cluster restarted with crash recovery, and its scientific metadata matches the backup-source witness exactly. Portable target-directory mapping, file-only restoration, matching intents, member reuse and conflict rejection pass seven focused tests and five joint-restore integrations. Continue the same backup/database's file phase; actual migration still waits for complete recovery validation.

## October 10, 2026 actual completion

**Current state, October 10, 2026: the approved selection has moved and `E:\ThreeMindData` is active with real schema 65. All 43 resources, 32,984 files and 4,242 database payloads pass copying, hash and new-placement checks. Running checkpoints still default to database. The joint backup was restored in isolation; sources and older complete backups remain. Earlier phase records below are preserved. See the [actual delivery](existing-data-migration-delivery.md).**
