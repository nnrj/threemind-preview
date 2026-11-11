# Data management and storage separation delivery

[简体中文](../../zh/plans/data-management-delivery.md) · [Approved plan](data-management-and-storage-separation.md) · [User guide](../data-management.md)

Date: October 10, 2026. This record separates executed local Git cleanup, isolated tool acceptance and operations still requiring explicit deployment action. Original planning and intermediate records remain dated evidence.

## Executed Git and evidence work

| Item | Measured result |
| --- | --- |
| Reviewed committed artifacts | 1,445 paths, 104,978,765 bytes; only these source duplicates were removed after individual verification |
| Originals, context and historical bytes | 2,885 files, 139,226,676 bytes, including 44 historical Git byte versions; every archive file reverified after relocation |
| Reports | 79 appended location editions and three later telemetry addenda; original reports, links, findings and criteria preserved |
| History | 229 commits independently filtered; raw Codex tree references also filtered, with old/new identity mappings |
| Active Git pack | 89,560 → 40,550 KiB, approximately 87.5 → 39.6 MiB, a 54.7% reduction; this is not total folder disk savings |
| Complete original repository | Final bundle: 91,017,091 bytes; original metadata: 94,091,893 bytes, preserved separately in ignored backups. A fresh restored mirror retained exact original refs and passed `git fsck` |
| Similar problems | Selected paths absent from all reachable commits and snapshot trees; audit found no other reachable blob reaching 1 MiB. Necessary frozen fixtures and legitimate small resources retained |

Evidence: [selection](../../../lab/artifact-index/2026-10-09-git-data-selection.json), [original-byte locations](../../../lab/artifact-index/2026-10-09-relocations.json), [cleanup receipt and identity mapping](../../../lab/artifact-index/2026-10-10-git-history-map.json). Full receipts, old blobs, original repository and earlier inventories remain under ignored `data/`.

The repository was not rebuilt into one root commit. Code history, working files and index were checked at replacement. Embedded scientific `source_commit` values were not changed to filtered identities. Where Git text filters changed line endings, original working bytes and historical blobs are separately preserved. Original report URLs still select the original edition; a revision or `latest=true` explicitly selects a later one.

The local `.githooks/pre-commit` data guard is enabled. `python scripts/check-git-data.py --all-tracked` verifies the complete index; new clones may explicitly opt in with `git config core.hooksPath .githooks`. Formal package volumes, reviewed raw artifacts and unclassified large files cannot silently return to Git.

No push or remote rewrite occurred. Stale remote-tracking refs were removed while remote configuration remains. The recorded remote tip is an earlier local observation, not a current server claim. Any later remote rewrite requires independent inspection and authorization; merging unfiltered remote history would reintroduce removed objects. Complete recovery backups still occupy local disk and were not discarded.

## Delivered capabilities

- **Three storage responsibilities:** PostgreSQL retains scientific state, permissions and causal records. Immutable media originals, note images and export bytes can use database, filesystem or S3 storage. Rebuildable caches and control records remain separate; scientific weights are not externalized merely by MIME or extension.
- **Frozen locations:** new writes pin category policy, target revision and stable host identity. Policies affect future writes only. Jobs declare source and output target capabilities; subject restoration also declares actual backend/kernel capabilities.
- **Bounded safe I/O:** external transfer precedes causal commit; short transactions recheck authorization, destination, sequence and lease generation. Missing/corrupt bytes fail explicitly. Live original, converter state, transformed frames and input still commit atomically; retries do not skip stimuli.
- **Common reads:** artifacts, media, note images, report sources/shares, experiment packages and analysis tools read their actual backend. Private notes and nested packages remain actor-private, without project-owner bypass.
- **Formal packages:** `threemind.data-bundle/1` and `.tmdata` validate manifests, volumes, byte hashes, types and dependencies. Catalog filters cover project, experiment, individual, batch/dataset and time. Relevant revisions and required sources form the default dependency closure. Unknown outer formats fail; unsupported inner types remain faithful read-only originals.
- **Native restoration and provenance:** report/note histories, images and fixed sources become new local records with original authors, timestamps, hashes and projection hashes. Historical jobs, runs and AI calls are not fabricated as local execution. Imported AI provenance receives an explicit retained-origin label without inventing an original call FK.
- **Subject restoration:** dedicated experiment/language validators require full state and configuration before creating paused copies. Without a matching restorer or required dependencies, materials remain archives rather than complete continuation. Existing species/model packages retain their dedicated adapters.
- **Offline studies:** the approved archives are registered as 29 sealed `archived-study:<directory>` resources. They support bounded catalog/download, formal directory export and read-only reimport. Directory packages neither infer outside dependencies nor fabricate projects/runs from filenames.
- **Migration:** plan, copy/resume, cancel, verify, separately activate and conditionally roll back. Sources remain by default. Unknown writers, changed sources, lock conflicts and unsafe/control paths fail. Activation is explicit; later writes preclude blind rollback.
- **Management:** UI, REST, CLI and Agent share services and an operation catalog. A host administrator can manage storage without a project. Bounded queries, details, exports, imports, restores, migration and risk previews are available. Changing restoration backend invalidates the old preview.
- **Cleanup and backup:** candidate listing reads bounded control journals rather than scanning a bucket for presumed garbage. Human deletion requires fresh reference checks, preview token and name confirmation; Agent only queries/previews. Full backup pins the database snapshot and external originals; restore requires a new database and external root and remains unactivated.

Entry points: [BlobStore](../../../src/threemind_lab/blob_store.py), [research locations](../../../src/threemind_lab/research_storage.py), [formal packages](../../../src/threemind_lab/data_bundles.py), [directory packages](../../../src/threemind_lab/research_data_bundles.py), [backup](../../../src/threemind_lab/storage_backup.py), [API](../../../src/threemind_lab/data_api.py). These are Lab/host tools. Core/kernel source, historical individuals and experimental input were not changed.

## Acceptance and limits

Checks used a task-owned PostgreSQL 17, temporary projects/roles/directories, a local S3 emulator and UI mocks. No real cloud or user database upgrade occurred. Groups overlap and are not summed into a fictitious total.

| Group | Completed checks |
| --- | --- |
| Archive/Git/report revisions/location migration foundations | 86 passes covering original bytes/reports, version reads, paths, migration, retries and risk boundaries |
| BlobStore, external backup and directory packages | 15 passes, including filesystem/S3 backup restoration, volumes, read-only reimport, private originals, failed upload retry, legacy table-export policy freezing and integrity |
| Existing media/tools/job compatibility | 53 affected old cases pass. One OCI temporary-directory case hit Windows sandbox ACL restrictions and passed in an isolated retry |
| Original readers/legacy packages/shares | Batches of 13 external source/capability, nine legacy package/share and 11 final export/share cases pass. Final actor upload status/retry and imported-AI edit provenance each pass targeted verification |
| Formal packages | 20 passes: report/note histories, images, fixed sources, volumes, unknown types, cancellation/leases, cross-project restore, full experiment/language paused copies; same-SHA original missing/corrupt, nested privacy, AI provenance and probe closure cases |
| API/CLI/actual job chain | Final 18 passes; earlier report-inclusive group 31 passes, including isolated Worker package roundtrips and host directory read-only import |
| UI | Six browser cases pass: desktop, 390px, projectless host administration, risk UI and backend-preview invalidation; production build passes |
| Static checks | Affected Python Ruff, Git data guard, history/bilingual link validation and whitespace checks pass |

Complete continuation acceptance applies only to covered configurations/adapters: language checks the next input response/state; experiment checks the complete paused boundary without a subsequent actual-input case in that group; species branches remain implemented without an independent end-to-end fixture here. It does not cover every historical folder/version/environment. Storage does not alter simulation time or observation. No training, retention-gain experiment or Core performance improvement is claimed.

## Operations still requiring explicit action

1. **Database deployment:** migrations `060_external_blobs.sql` and `061_data_management.sql` were exercised in isolated databases. Real deployment requires the documented explicit migration and renewed acceptance; startup cannot secretly upgrade old databases.
2. **Other research data:** migration programs, interfaces, commands and risk prompts are implemented. No other existing study migration, cleanup or category-policy switch was executed.
3. **Actual S3/shared folders:** local emulation does not validate a live cloud or shared multi-host filesystem. S3 uses the `storage` extra and explicit encrypted credentials. Cloud-sync folders only support declared single-writer/sealed use.
4. **Capacity:** logical references, candidates and actual registered-object integrity are observable. Total bucket use, database/WAL and physically reclaimable bytes are not inferred from logical totals; unknowns remain unknown.
5. **Offline dependency completeness:** all selected directory files can be faithfully packaged/reimported, but without outside dependency declarations and a dedicated restorer they remain read-only, not a restored organism.
6. **Keys and identity:** control registrations and actual keys need separate safe backups. Public packages contain no plaintext credentials, and host configuration is not guessed from Git on startup.

[T03/T05/T10](research-backlog.md) records current scope. Negative-zero byte semantics, large-ecology retention policies and kernel memory findings remain separate open questions.

### Later October 10 correction: missed local installation and doctor cleanup

The user successfully ran migrate, then doctor failed with unknown continuous kernel identity and pool-thread shutdown waits. The everyday `.work/kernel-venv` had an old extension supporting only through /2. Prior /3 and /4 acceptance used a separate current-extension directory without installing it into the everyday environment; the assistant's prior command instructions omitted this step. This is installation inconsistency rather than SQL failure; changing individual identities cannot remedy it.

The previous package/metadata were copied and verified under ignored storage. A current-source offline release wheel was installed into the same environment. Doctor now passes current schema/native with only PYTHONPATH=src, and all seven executable kernels load. Targeted /2 and /3 frozen witnesses plus /4 backend/partition/cross-restoration checks pass. Doctor validates current schema and always closes its pool; four exit cases pass. The user's everyday local database is upgraded; other data migration remains unexecuted. No service was started, old individual opened/reset or kernel dynamics changed. Earlier undeployed statements remain contemporary evidence, with current state explicit here and in the guide.
