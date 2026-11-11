# Experiment record backfill and unified research overview

[中文](../../zh/plans/experiment-record-backfill.md)

Approved 2026-10-10. The user's implementation request supersedes the earlier planning-only boundary. No historical experiments are rerun; Core, existing individuals, protocols and original conclusions remain unchanged. No Git push.

## 1. Objective and principles

Cover all historical formal research experiments and unify future AI and human recording. The database and UI provide a global index, reports, notes and evidence links. Complete originals remain accessible by reference without duplicating large files.

The approved design is **unified records plus original references**, preserving additional scientific data from existing AI experiments. Historical detail need not be forced into runtime tables. No new internal-kernel event tracing is introduced.

## 2. Inventory and backfill

- Reconcile the database, exploration directories, early laboratory notes, historical sources, publication receipts and relocation manifests. The 69 discovered exploration directories are inventory candidates, not 69 confirmed completed experiments.
- Preserve experiment numbers and project ownership; reuse published records. Distinguish unstarted proposals, failed/interrupted trials, negative results, calibration and controls. A directory name does not prove execution.
- Record question, protocol/version, executor, experiment date, kernel/configuration, conditions, subject/branch relationships, actual stages, conclusions, reports, notes and evidence. Unknown information remains explicit.
- Register logical resources, format, size, hashes, experiment/stage, dependencies and viewing capabilities. Reuse existing database artifacts and archive locations. Do not move/delete originals or upload another complete copy.
- Store small report/protocol/scientific-note bodies in the database. Preserve originals and revision chains. Separate experiment dates from ingestion dates and label newly written retrospective notes.
- Unknown formats keep exact bytes and an index; missing files, checkpoints, identity or time become specific gaps. Backfill neither reruns science nor fabricates uncaptured data.

First complete E64–E66 links and original /3, repaired /3, text/telemetry and /2 controls, and /4. Then process earlier work chronologically; the scope remains all history.

## 3. Database and UI

Add a research experiment index linked to existing scientific facts, without replacing runtime execution.

- Add experiment, subject/condition/stage associations, evidence references and backfill batches. Index identity is distinct from original identity. Continuation, restoration, independent controls and copies follow evidence.
- Separate execution state and documentation coverage; registered files alone never imply full scientific completeness.
- Add a global experiment overview for all authorized formal experiments, searchable by project, number, date, kernel, executor, execution and coverage. Temporary development tests are excluded by default.
- Details collect protocol, stages, results, report revisions, notes, checkpoints and originals. Reuse replays; paginate supported process data and provide manifests/downloads for other formats.
- Keep project-specific document and notebook pages, adding clear scope and a global-overview link.
- Reuse shared storage/data services and experiment-scoped exports. Enforce project and private-note permissions, protect referenced evidence, and report unavailable originals rather than empty success.

## 4. Shared recording tools

One service supports UI, CLI, MCP/Agent and Python scripts.

| Interface | Capabilities |
| --- | --- |
| REST | Global/project queries, registration, stage/entry append, evidence attachment, report/note writing, verification and backfill preview/application |
| `threemind records` | list, register, append, attach, finalize, verify, backfill-plan, backfill-apply, receipt |
| MCP/Agent | The same installed operation catalog, schemas, prerequisites and receipts |
| Python recorder | Registration, stage recording, original references, synchronization and completion checks; no UI emulation |

AI and human executions share requirements and validation. Keep scientific extensions and original formats. Stable request IDs and hashes provide replay and reject conflicts. Register before formal execution, preserve process originals, synchronize at stage boundaries and verify completion. Human entrypoints register automatically.

Persist an unsynchronized journal when the database is unavailable. If originals cannot be durably recorded, stop host advancement and report failure without resetting a subject or skipping input. Recording does not stimulate, learn, restore or rerun. Credentials, unrelated logs, temporary engineering tests and Agent private reasoning are not automatically ingested. Frozen historical scripts stay unchanged; backfill uses external adapters and maintained future scripts use the shared recorder.

## 5. Delivery and acceptance

1. Inventory/protection: frozen source inventory, gaps and preview; backup the local database before writes and verify recovery.
2. Implementation/isolation: index, API, CLI, MCP, recorder and UI; explicit migrations.
3. Application: fixed-source batches with receipts and visibility checks; retries cannot duplicate or overwrite published evidence.
4. Integration/delivery: complete ledger, results, remaining gaps, manual, storage increments, research progress and required histories.

Acceptance covers all identified experiments and unstarted/failed work; global visibility; unchanged revisions/hashes/identities; shared-interface recording and interrupted/idempotent retries; missing/unsupported/forbidden states; no simulation or subject mutation; formal bundle round trips; and separate index/body/original/recording-cost measurements.

Report unrecoverable data with exact gaps, consequences and possible sources. Ask for a user backup only when a concrete missing source needs it. **A completed index is not a claim that uncaptured scientific data was recovered.**

## Implementation log

- 2026-10-10: approved plan saved; inventory and engineering begin. No passing implementation or completed live backfill is claimed yet.

- 2026-10-10: complete backup/recovery and explicit schema 62 migration accepted. All 84 source indices are live with 59,118 references. Original identities, state, revisions and storage mappings remain unchanged. Engineering, full UI and formal bundle round trips pass; gaps and older host mismatches remain explicit. See [delivery](experiment-record-backfill-delivery.md).
