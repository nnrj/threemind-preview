# R51c: local deletion and emission optimization in 6.1

13 November 2026. Engineering validation, with no scientific subjects trained. Originals: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/kernel61-v1`.

## Purpose, expectation and conclusion

R51b identified the main cost in 6.0: tiny residual inhibition continued to schedule emissions whose signals were blocked at connections. Whole-graph structural scans also revisited unchanged objects. The author approved a separately identified 6.1 with local deletion by default, independent activation and inhibition sender thresholds, and less redundant computation.

The contract required backend agreement, complete restoration, preservation of historical versions, passive observation, and advancement time and allocated state storage below the campaign's twofold 5.1 stopping threshold at both tested sizes.

**6.1 meets these engineering targets.** Default advancement takes 19.27% less time than 5.1 at 1,024 nodes and 17.66% less at 4,096 nodes. Time falls by 90.81% and 90.41% relative to 6.0. Default deletion performs no whole-graph scans, while allocated final-state storage is about 1.10 times that of 5.1. The engineering performance obstacle is resolved. Under the author's latest authorization, scientific revalidation proceeds in explicitly registered 6.1 batches.

## Changes

Local deletion keeps one replaceable deadline per connection, settles and checks that object when due, and checks only its endpoints after deletion. Same-time input and emission precede deletion. Whole-graph deletion remains an explicit option.

Activation and inhibition sender thresholds are 0.004 and 0.002. When neither activity is sufficient and no incoming signal awaits processing, recurring emission stops; new input can restart it. Zero disables the respective threshold. These are authorized dynamics changes that alter weak-activity emission, resource use and opportunities for reinforcement.

Separate implementation optimizations preserve calculation rules: typed configuration caching in Rust, numeric timestamps for short-term state, fewer repeated lookups and copies, and delayed allocation of feature vectors. Historical 6.0 continues to use its original implementation. With whole-graph deletion and both new thresholds set to zero, all eight benchmark pairs reproduce complete 6.0 final states after removing only version identity and the new configuration fields.

## Measurements

Each trial advances ten internal seconds. The 1,024-node/connection conditions have five repetitions; the 4,096-node/connection conditions have three. Six conditions yield 48 trials with alternating order. Values below are median wall-clock seconds. Repeated final states agree exactly.

| Configuration | 1,024 nodes | 4,096 nodes |
|---|---:|---:|
| 5.1 defaults | 0.0533705 | 0.2342316 |
| 6.0 defaults | 0.4688398 | 2.0105267 |
| 6.1 global deletion, zero sender thresholds | 0.2271730 | 1.0819101 |
| 6.1 local deletion, zero sender thresholds | 0.1982664 | 0.9102715 |
| 6.1 global deletion, default sender thresholds | 0.0977839 | 0.4525362 |
| 6.1 defaults: local deletion and default thresholds | **0.0430845** | **0.1928696** |

Implementation optimization alone approximately halves time while preserving the 6.0 calculation sequence. Local deletion and sender thresholds remove further work. Their combined default is faster than 5.1 at both sizes and passes the predefined resumption gate.

| Allocated final-state storage | 1,024 nodes, bytes | 4,096 nodes, bytes |
|---|---:|---:|
| 5.1 | 618,496 | 2,424,832 |
| 6.0 | 692,224 | 2,723,840 |
| 6.1 defaults | 679,936 | 2,666,496 |

Windows `FileStandardInfo` supplies allocated sizes; every file has one hard link. The timing tool's original `allocated_bytes` field uses `GetCompressedFileSizeW`, which gives file length for these uncompressed files. The independent `audit.json` records actual allocation without overwriting original timing records. Default 6.1 has zero scan visits and exactly one final deletion deadline per connection, with no stale-event accumulation.

The 48 trials took 76.05 wall-clock seconds overall. Peak process private memory was approximately 716MiB. Minimum headroom was approximately 14.38GiB committed memory, 13.44GiB available RAM, 10.57GiB on C and 92.08GiB on E, above all reserves. Process memory includes the interpreter, modules and repeated-trial allocator state. Growth under prolonged novel stimulation is measured separately in subsequent stimulus experiments.

## Integrity and interpretation

The independent audit decoded 96 complete artifacts, checked 48 records and source hashes, and recalculated all medians and ratios. Dedicated tests cover four decay curves, two deletion strategies, both backends, resources and facilitation, dormancy, both in-flight delivery policies, reproduction, restoration, reconfiguration and passive observation. Engineering fixtures are counted separately from scientific origins.

An early test found isolated nodes deleted one structural grid point later under local deletion when the final connection disappeared. This was corrected before the benchmark freeze by checking endpoints in the same deletion phase, and the regression passes. Historical evidence, pause markers and version identities remain intact.

The engineering conclusion for ThreeMind is clear: fixed-function addressing and single-age decay can run efficiently with local scheduling. The severe 6.0 slowdown was not an unavoidable cost of those mechanisms. Subsequent 6.1 batches test the scientific, behavioral and ecological claims individually, retaining the scales and stopping conditions of comprehensive revalidation plan v2.

Evidence: [preregistered protocol](protocol.md), `frozen.json`, `results.json`, `summary.json`, `audit.json` and `resource-summary.json`. Delivery receipt: `publication/completion.json`. Recalculation was performed by this assistant, not by an external reproducer.

## Installed-package acceptance

The project environment now has the 6.1 native package. Final targeted regression passed 895 checks; 13 database-dependent checks were skipped. Frontend build, history-link validation and source/data separation checks passed. Eighteen bounded checks of the installed package reproduced all 36 frozen initial/final states; default time ratios to 5.1 were 0.8088/0.8047. Release and timing binary hashes are preserved separately, and the installed extension matches its wheel member byte for byte.

The module path in `packaged-verification.json` points to the Python package initializer. The additive `installed-release.json` identifies and hashes the actual native extension without overwriting that record. Overlapping test suites are not summed as independent experiments.
