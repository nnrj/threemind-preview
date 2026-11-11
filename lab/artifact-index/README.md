# Research artifact locations

This directory contains source-controlled metadata, never the raw experiment data.

- `2026-10-09-git-data-selection.json` freezes the reviewed removal scope, original repository snapshot, selection rules, exact leaf paths, group counts and path digests. Revision 2 includes ten nested per-condition results that were already preserved as companion evidence in revision 1.
- `2026-10-09-relocations.json` maps stable `resource_id` values and repository-relative `legacy_path` values to byte-verified `archive_path` values under ignored `data/experiments/`. Its `snapshot_commit` identifies the repository checkout captured for relocation; it does not replace any scientific payload's internal `source_commit`.
- `git-data-policy.json` lists explicit small templates and necessary frozen regression fixtures. It does not exempt an entire experiment or data directory.

Full inventories, related original Git commits, old blob versions, location-index revisions and receipts live under ignored `data/storage-control/research-artifact-archive/<batch>/`. Original working-tree bytes and historical Git blob bytes are retained separately when Git text filters changed line endings. Version `change_commits` records include the reviewed snapshot for current blobs in addition to history change records; they do not assert that every listed commit contains every version.

The archive tool is deliberately separate from Git history rewriting:

```text
python scripts/research_artifact_archive.py inventory
python scripts/research_artifact_archive.py archive
python scripts/research_artifact_archive.py verify --sources
python scripts/research_artifact_archive.py manifest
python scripts/research_artifact_archive.py paths
python scripts/research_artifact_archive.py resolve <original-repository-relative-path>
```

`inventory` and `archive` require the reviewed original HEAD and refs. Repeated copying reuses identical destinations and rejects differing bytes. The tool never deletes sources or changes Git refs/index, original reports, embedded hashes, or experimental payloads. A location-index revision requires the exact prior hash with `--replace-expected-sha256`, retains prior bytes, and publishes atomically. After local Git cleanup, `verify` still verifies the archive without requiring the old HEAD; omit `--sources` once original duplicates have been removed by a separate authorized operation.

`python scripts/check-git-data.py` checks staged objects rather than working-tree sizes. `--all-tracked` checks the complete index. Under the user-authorized November 10, 2026 revision, ordinary files follow [GitHub's file limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github):

| Staged file size | Result |
| --- | --- |
| Up to 50 MiB | Passes the size check |
| Above 50 MiB and up to 100 MiB | Warning only; the check still succeeds |
| Above 100 MiB | Rejected; use Git LFS or external storage for eligible assets |

Ordinary manuscripts, PDFs and documentation no longer need individual size exceptions. The former 1 MiB gate and its twelve manuscript exceptions have been removed. Size limits are defined in `scripts/check-git-data.py`; the policy JSON contains only the remaining reviewed classification exceptions. Each such fixture or template must remain within its recorded allowance, and no exception bypasses the 100 MiB file limit.

Reviewed research originals, runtime storage, checkpoints, complete trajectories and portable `.tmdata` packages remain blocked regardless of size, apart from the existing bounded fixture/template exceptions. Git LFS does not automatically authorize research data in the source repository. Ignore rules prevent ordinary re-addition, while the checker catches forced staging. A failed pre-commit check explicitly reports that the commit was aborted; the checker never deletes, moves or unstages files.

The compact engineering resource `docs/benchmarks/kernel-candidates-2026-09-28.summary.json` retains declared protocol/configuration and aggregate metrics with the original evidence identity and hash. It contains neither raw observations nor restorable final states; the full original remains a registered archived resource.

## 2026-10-10 verified local cleanup

[Cleanup receipt and commit mapping](2026-10-10-git-history-map.json) records 229 old/new commit entries and the filtered Codex snapshot trees. The filtered tip is `22fc53ec94a7eecd522c0a941de37cdff68ac678`; future tooling commits extend this history normally. All 1,445 reviewed paths are absent from reachable commits and snapshot trees. The 2,885 archived files (139,226,676 bytes) were reverified after removal of the exact source duplicates. Original scientific `source_commit` values, code, frozen fixtures and report editions remain intact.

Git pack size changed from 89,560 to 40,550 KiB. This measures the active Git object store, not total disk savings: complete Git bundles and original metadata remain separately in ignored `data/git-backups/`. A fresh mirror restored the complete original refs and evidence from the final bundle and passed `git fsck`.

The 29 P1 archive groups are registered as sealed `archived-study:<original-directory>` resources on this host, including `archived-study:docs` for the benchmark originals. They can be queried, exported into a formal read-only `.tmdata` archive and explicitly migrated through the common host service. Registration changed no scientific bytes or existing individual. Host configuration is ignored and must accompany an explicitly managed storage/backup transfer; it is not reconstructed from Git on startup.

The tracked pre-commit guard is enabled locally with `core.hooksPath=.githooks`. New clones can opt in with `git config core.hooksPath .githooks`; the standalone checker works without installation. No push or remote history update occurred. Do not merge or fetch the unfiltered remote into this cleaned repository. If remote rewriting is later authorized, inspect its current branch in a separate checkout and use an exact `--force-with-lease` against the verified remote value. The pre-cleanup local remote reference is evidence of a past observation, not a claim about the remote's current state.
