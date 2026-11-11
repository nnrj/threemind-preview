# E68 delivery supplement: storage, video and verification scope

October 13, 2026; accompanies the [report](report.en.md). Measurement: `2026-10-13T02:10:12.842978+00:00`, after original-reference synchronization and before final report publication.

| Logical file lengths | /2 | /3.1 |
|---|---:|---:|
| Arm originals (GiB) | 8.883 | 9.313 |
| All complete boundaries (included) (GiB) | 7.984 | 8.398 |
| All replay files (MiB) | 233.941 | 229.731 |
| MP4 portion (included) (MiB) | 57.258 | 53.050 |
| One complete final individual (MiB) | 6.222 | 6.492 |
| Arm originals + replays (GiB) | 9.111 | 9.537 |

All experiment-root files total **20,045,095,344 bytes, or 18.668 GiB**. This includes both groups, shared courses/protocols, frozen sources, audits and local recorder receipts. It excludes this measurement receipt itself and subsequent small publication bookkeeping.

Shared analysis is 6.104 MiB, frozen sources 5.140 MiB, and recorder control/receipts 9.011 MiB. Nested rows must not be added. Binary units measure file lengths, not allocated sectors. Shared software installations, database pages, caches and host RAM are outside this per-experiment file measurement. Database entries reference originals without duplicating a full package; total PostgreSQL growth is not an attributable per-experiment cost.

The individual size denotes a complete saved final state: Core, host/body/world/mappings, personal peripheral, optimizer, RNG and recent readout history. It is neither Core-only nor a live-RSS estimate. A late host progress sample was about 1.85 GiB RSS with both groups and tooling resident; it cannot establish separate per-group peak memory.

## Video verification

Each video is 779.1 seconds, 7791 encoded frames, 17 chapters, 1280×1024, 10fps, H.264, derived from 1210 clips and 31,100 source frames. Both streams decode fully. Actual encoded frames and all four curves were visually inspected; source and final-state hashes match. All 506 frozen source files match their stored copies and current bytes.

| Video | SHA256 |
|---|---|
| /2 | `8965c0c8f771ae3fa3360c23dbf18bb23315c7982c28bf2278ea08332389a763` |
| /3.1 | `a1cd6b89dec24c8c88b358a175943846c9e73d3ed31988d6b15c9d0d8891ef2f` |

[review_results.py](review_results.py) and `analysis/review-details.json` preserve the measurement method; `analysis/verified-results.json` records the full trajectory/checkpoint audit. Rendering and review never created or advanced a subject. Final platform publication is recorded separately in delivery receipts and history addenda. Original machine-generated drafts remain at `analysis/report-draft.*.md`.
