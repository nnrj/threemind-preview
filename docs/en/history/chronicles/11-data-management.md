# Volume XI — Removing raw evidence from Git requires complete data management

[中文](../../../zh/history/chronicles/11-data-management.md) · [Decision source](../sources/2026-10-09-data-management.md) · [Approved plan](../../plans/data-management-and-storage-separation.md)

Recorded 2026-10-09. **The scope is approved and awaiting implementation. This turn updates plans and history only; no experiment artifacts, research data or Git history have actually been moved or cleaned.** There is no push, service operation or new experiment. Existing Core dynamics, individuals, results and criteria remain intact.

## From committed artifacts to formal data management

Earlier retention-repair and text/telemetry work committed complete checkpoints, inputs and trajectories under `lab/explorations`. The user requested preserved originals in ignored data storage, removal from Git history, and an audit for similar artifacts. They subsequently approved a combined plan for data management, external storage and a formal data bundle. Controlling repository growth and preserving reproducible experimental continuity are both requirements; cleaning Git cannot justify destroying failures, negative results or complete individual state.

Actual relocation is limited to mistakenly committed experiment artifacts. Migration support for other existing research data will be developed and tested, without a bulk migration in this phase. Git cleanup is local, with no remote push. Code, registrations, reports, small public summaries and necessary frozen regression fixtures remain in Git. Original bytes, frozen execution sources and historical hashes remain in data archives. Path changes receive a new revised report with a dated opening explanation and a link to the original. Original report bytes and links, criteria, findings and contemporary interpretation remain preserved.

## Archive, import and continuation are separate acceptance claims

The formal `data-bundle` uses typed entries and dependency manifests covering all research materials, with import/export selection by project, experiment, individual, batch/dataset and time range; stage and type may be filters. Management UI, REST, CLI and Agent share one protocol, authorization policy, destination resolver and operation receipts, rather than separate authoritative records.

Archiving and reimporting materials, restoring supported native records, and complete continuation through supported restorers are three distinct capabilities. Unknown outer bundle schemas are rejected for formal import; unsupported object schemas inside a known bundle retain their original bytes with read-only registration. Materials without required restoration dependencies or a supported restorer remain faithfully archivable, but cannot claim a complete bundle or complete continuation. Missing optional materials require explicit limitations. Complete restoration must include Core, personal peripheral weights and learning state, readout history, body/environment, mappings, RNG and associated inputs, retaining version identity and clocks. A Core-only save cannot stand for the entire individual.

Import, migration and packaging have programmatic interfaces. Human CLI deletion keeps the preview token and name confirmation. Agent may preview cleanup, while deletion retains its human boundary. Import does not authorize running unknown code, replacing old individuals or starting teaching.

## Seven supporting changes are approved for this phase

1. Verify the complete archive dependency closure, including language peripherals, with supported dedicated validators/restorers. Missing required restoration dependencies permit material archiving but forbid complete-restoration or continuation claims.
2. Add cancellation, expiry, continued upload and cleanup preview for staged experiment uploads. Originals referenced by evidence are not deleted as staging data.
3. Pin external evidence to a destination revision, object key and digest, including an S3 object version where required. Deduplication remains within each project, with immutability and reference protection.
4. Backup manifests include the database snapshot, external objects, code version and requirements for safe key custody. Restore validation uses an isolated environment.
5. Freeze task destinations and policy revisions. Stable host identity is separate from worker identity after restart, and claims use actual destination reachability.
6. Report logical bytes, physical usage, staging, cache and reclaimable capacity separately. Integrity hash scans are manually initiated.
7. Bound external I/O and local caches, avoiding long-held database transactions. Missing objects block or fail; they never become empty values, reset individuals or skipped stimuli.

These are approved implementation requirements, not verified capabilities. Delivery must separately report faithful archives, native-record restoration, complete continuation, authorization/reference protection and capacity/integrity acceptance. Deleting caches does not authorize deleting original evidence. The backlog adds [T10](../../plans/research-backlog.md), linked to T03/T05. This storage plan does not reinterpret prior `/4` retention negatives or E64/E65/E66 evidence.

## 2026-10-10 addendum: implementation authorization and preserved originals

The user subsequently requested implementation and reported a complete project backup on a removable drive, available if recovery requires it. This authorizes implementation; the October 9 pending status above preserves the planning turn rather than describing the current phase.

The reviewed selection contains 1,445 committed paths and 104,978,765 bytes. Including source/protocol/original-report context and 44 historical Git byte versions, 2,885 files and 139,226,676 bytes have been copied and individually verified. Git text-filter line-ending differences retain both working-tree originals and historical blobs. Ten initially missed nested per-condition results were added, while original selections, mappings and receipts remain archived. Embedded source_commit values are unchanged.

There are 79 appended location revisions, with three further text/telemetry report addenda covering the ten missed results. Original reports and criteria remain intact. Report writing, same-identity database revisions and document reading have been validated; archive/Git safeguards passed 31 isolated checks, and research-location/migration support passed 38. A complete Git bundle has been verified as recoverable. History replacement still awaits independent filtering and validation; there is no push. These are engineering checks rather than consciousness-learning experiments.

## Later October 10 addendum: history filtering and data tool delivery

Subsequent acceptance supersedes the earlier pending-switch status without erasing it: 229 commits were independently filtered, with raw Codex tree references checked separately, and local metadata switched. Active pack fell from 89,560 to 40,550 KiB, about 54.7%. The original bundle/metadata remain separately; a fresh mirror restored original refs and passed fsck. Backup occupancy is not claimed as released space. Reviewed source duplicates were removed only after verification; all 2,885 archived files were reverified. Original source_commit and reports remain, with no remote push. [Receipt](../../../../lab/artifact-index/2026-10-10-git-history-map.json)

Shared storage, formal packages, management, migration and backup passed isolated acceptance. PostgreSQL remains scientific authority; only immutable carriers are externalized. Target/policy/source capability pinning does not change Core time or dynamics. Report/note restoration creates new local identities and preserves original read-only evidence, without fabricating historical jobs/runs/AI calls. Private carriers remain actor-protected through nested repackaging; imported AI origin is explicitly retained. The 29 sealed archive directories support formal export/reimport without inventing outside dependency completeness.

Language restoration checks next-input response/state equality; experiment restoration checks the complete paused boundary. Species and every historical configuration are not claimed as fully replayed. UI/API/CLI/Agent share services; Agent cleanup previews only and human deletion requires token/name. Database plus filesystem/S3-emulated backup restoration used new isolated destinations. No real database upgrade, cloud contact, other research migration or new learning experiment occurred. Engineering delivery does not establish biology or retention gain; E64/E65/E66 and /4 negatives remain. [Delivery/acceptance scope](../../plans/data-management-delivery.md) · [Usage](../../data-management.md)

### Later October 10 correction: missed local installation and doctor cleanup

The user successfully ran migrate, then doctor failed with unknown continuous kernel identity and pool-thread shutdown waits. The everyday `.work/kernel-venv` had an old extension supporting only through /2. Prior /3 and /4 acceptance used a separate current-extension directory without installing it into the everyday environment; the assistant's prior command instructions omitted this step. This is installation inconsistency rather than SQL failure; changing individual identities cannot remedy it.

The previous package/metadata were copied and verified under ignored storage. A current-source offline release wheel was installed into the same environment. Doctor now passes current schema/native with only PYTHONPATH=src, and all seven executable kernels load. Targeted /2 and /3 frozen witnesses plus /4 backend/partition/cross-restoration checks pass. Doctor validates current schema and always closes its pool; four exit cases pass. The user's everyday local database is upgraded; other data migration remains unexecuted. No service was started, old individual opened/reset or kernel dynamics changed. Earlier undeployed statements remain contemporary evidence, with current state explicit here and in the guide.

## Later October 10: storage tools complete, real migration awaits cleanup

The approved E:\ThreeMindData destination retains relational queries/scientific bodies and database-default running checkpoints with an explicit file option. Batch roots, exact members, payload versions, file checkpoints and joint backup share UI/CLI/REST/Agent services. Sources/scientific identity remain; damaged placements cannot fall back to old copies, durable tasks recover publication and private access remains protected.

The broad 157-resource inventory includes source/expanded copies, not net migration size. Selection is 43 resources/32,984 files plus 4,242 payloads, 61.69 GiB plus 15 GiB reserve against 55.65 GiB E free. Another 114 resources await classification; no real checkpoints were automatically sealed. Initially mistaking this for planning, the user explicitly requests a suitable cleanup pause. Stop after tool acceptance before the real new backup/recovery, schema 64 or moves. Real schema remains 63, Core/old subjects unchanged.

111 regressions, 14 filesystem/S3-emulated integrations, independent context restoration and desktop/mobile checks pass. Tiny-graph file saves/restores are slower, not a large-state conclusion. Caches/stopped clusters total 6.45 GiB; preserve the earlier verified 44.44-GiB D backup on portable storage. Retain research and distinguish copying from reclaiming space. No report location revisions precede actual moves; T12's /4 host issue remains separate. [Sources](../sources/2026-10-10-storage-root.md) · [Handoff](../../plans/existing-data-migration-stage.md) · [Operations](../../storage-migration.md)

## Later October 10: interruption audit, full restore and active root

After the user freed space, verify source witnesses and make a current full joint backup. The earlier isolated restore had failed at 16:31 without prompt handling by the assistant. Following the user stop, no copying process remained; the database phase had completed. A colon-containing historical target ID had been interpolated into a Windows path. Fix the directory mapping and add file-only resumption, reusing the same backup and restored database. All 35,375 original-file references pass size/SHA-256 checks at isolated new placements, and seven real full/delta checkpoint samples match state/context witnesses. Independent backend fixtures also validate next input; this is not rerunning every old consciousness.

Explicitly install schema 64 and correct the published-artifact placement boundary with schema 65, then complete task `35b23849-b53b-4da3-89e9-8ea9efd77b6a`: 43 resources, 32,984 files and 4,242 database payloads, 61.69 GiB. Verify new placements and activate `E:\ThreeMindData`. Scientific metadata witnesses match across the switch. Running checkpoints remain database-default without auto-sealing old subjects. All 157 resources are classified: retain 68 source/report/fixture resources and 46 expanded published-package workspaces. Expanded members lack an individual equivalence proof and are not automatic deletion candidates.

Append 70 dated experiment annotations, 129 database and 136 repository report editions with 129 fixed-version links. Original bodies, charts, AI provenance, review state and results remain. Normal payload reads and identical relational pages match their earlier witnesses. Core, subjects and simulation time are unchanged. Retain sources and current/older complete backups; remove only owned disposable restored copies and the aborted unusable temporary dump. [Actual results, occupancy and rollback](../../plans/existing-data-migration-delivery.md) · [Sources](../sources/2026-10-10-storage-root.md)

## Payload relocation: scientific content versus physical placement

After the file phase, nine published artifacts were rejected because the old immutability trigger treated `blob_id` placement as content. Other payloads continued. Preserve the earlier schema-64 receipt and explicitly add schema 65 after isolated validation, allowing only same-project placements with identical size/SHA-256 while keeping content, scientific metadata and chunks immutable. Eight distinct cases pass across publication body/bundle relocation, retries, rollback, ordinary reads and rejection of invalid content. The first guard test used an invalid payload category; its corrected rerun passes. Real scientific hashes of nine artifacts and six publications match before/after. Wait for the original process to finish and resume only the nine failed items under the original task, without recopying committed files/payloads.


## November 10, 2026: ordinary Git file sizes

After a manuscript commit was rejected, the author asked where the 1 MiB threshold came from and explicitly authorized a reasonable increase to avoid inconvenience and loss for future open-source contributors. This is the present authorization; the earlier implementation record does not establish that the author personally chose 1 MiB. Code history shows that commit `22fc53e` on October 10 replaced a 10 MiB threshold with 1 MiB and individual exceptions.

The new rule follows GitHub's ordinary file limits: above 50 MiB warns without blocking; above 100 MiB blocks. Ordinary manuscripts no longer require individual registration, and twelve obsolete manuscript exceptions were removed. Existing research-original, checkpoint, complete-trajectory and frozen-fixture boundaries remain. Failed checks explicitly state that the commit was aborted and files and staged changes are preserved. All 23 focused checks passed, including actual manuscript commits in isolated repositories and preservation after rejecting raw data; the current staged and full-index audits passed. No commit or push was performed in the working repository, and no experiments or manuscripts were changed. This dated correction supersedes the old size gate for current operations while preserving the earlier historical text. [Current rules](../../../../lab/artifact-index/README.md) · [Guide](../../data-management.md)

> **Public-edition edit (2026-11-11; source lines 81-86):** Manuscript text, writing/submission discussion or links to non-public manuscript documents are omitted. Where a paragraph mixed these with research information, the research information is retained in this public extract. The complete source remains unchanged.


## 2026-11-21 · New experiments can use multiple disks

After connecting a portable SSD, the author wanted a large experiment to make use of free space across disks. The allocator now considers directory priority, directory quotas and minimum free space. It keeps a whole experiment together by default. A study can explicitly split worlds, batches or archive volumes. This workstation uses E first and H second. An isolated acceptance check wrote two ZIP segments to E and H, recovered a 1,065,576-byte original onto H and verified its SHA-256. This was a storage-tool delivery. [Usage](../../storage-migration.md)

## 2026-11-21 · Moving completed experiments to removable storage

The author wanted to reclaim space on a run disk while keeping finished experiments accessible by name. The storage tools now provide replicas, versioned backup and restore, migration, archival and unarchival. In an isolated round trip, the host synced an experiment from E to H, reused the verified replica for archival, released the old copy and restored it to E. The checks covered contents, empty directories, and NTFS creation and modification times. [Operator guide](../../storage-migration.md)

The author clarified that archival normally frees space on the run disk. The page now suggests a directory on a different physical disk first and also permits an explicit same-disk destination.
