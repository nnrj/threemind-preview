# R51a: 6.0 reproduction implemented; revalidation paused at the performance gate

13 November 2026. This report covers engineering preparation and the early cost gate of revalidation plan v2.

**Conclusion: 6.0 reproduction is implemented. Offspring inherit persistent connection state and decay age by default; resetting age is an explicit control. Python, the native binding and the standalone Rust executable can restore and continue offspring. The subsequent performance gate failed: with matched identifiers, size and input in a 1024-node fixture, 6.0 advancement took 8.51 times as long as 5.1. Formal mechanism, visual and aquatic revalidation is therefore paused under the author's registered rule.**

## Purpose and expectations

Aquatic experiments require a traceable birth rule. Offspring should inherit persistent structure, begin their own internal clock at zero and receive new experience. Preserve decay age by default and provide a reset-age control. Exact continuation remains a separate full-state operation. Engineering targets also include unchanged historical birth behavior, backend agreement, ecological energy accounting and complete multigeneration recovery.

The approved campaign requires pausing when comparable 6.0 execution reaches twice the 5.1 cost after checking host interference. Engineering fixtures establish implementation and cost; no new autonomy, retention, visual or aquatic scientific study began in this batch.

## Implementation and verification

The rule is `threemind.birth/2`. Default `preserve` retains persistent weights, node support, stability, local plasticity, use counts, retention scales, energy regions, dormancy and accumulated decay age at the saved observation time. `reset` changes only inherited decay age. Fast activity, synaptic resource-use state, pending events, parental intervention masks and internal time are initialized anew; virtual node addresses remain unchanged.

Birth interfaces, ecological protocols and events, developmental records and inherited branches record the actual rule. Python and Rust allow inherited age to exceed the newborn's own lifetime while retaining finite, nonnegative validation. No decay formula or other dynamics changed. The global creation default remains 5.3; the 6.0 deletion threshold remains 0.008.

Checks cover four curves, two in-flight policies, two inheritance-age policies and both backends. Ecological fixtures reach a second generation, recover exactly at complete and partially delivered physical-sampling boundaries, and satisfy energy accounting. Fourteen birth comparisons across seven historical kernels and two backends produced the same hashes as the birth function at commit `a84bafda`, without changing parents. Eight offspring fixtures continued consistently through the standalone Rust executable.

Some old tests implicitly selected today's global default, 5.3, whose birth remains undefined. The pre-change function rejects the same request. These historical tests now explicitly select their original kernel; production defaults and historical rejection behavior remain unchanged. Relevant regressions passed 416 checks, with 15 skipped because the isolated PostgreSQL test service was unavailable. Four additional mid-delivery recovery cases were then added, and all 49 reproduction checks passed. The latter suite overlaps the earlier regression and is not added to it as an independent count. Full test records accompany the evidence.

## Cost method, instrument correction and results

The fixture comprises 512 disjoint reciprocal pairs: 1024 nodes and 1024 directed connections. Each pair receives strength 0.8 at internal time zero, followed by ten internal seconds. Both use their genuine defaults except for a common quiescence-death wait long enough to cover the window. Initial and final graph sizes match. Each version is warmed up, then measured five times in alternating order. Crossing the gate triggers five additional engineering comparisons. Construction, advancement, capture and serialization are timed separately, with complete initial and final states retained.

The first protocol incorrectly assumed historical node IDs began at one. Artifact inspection showed they began at zero, so that attempt failed the stated identifier-matching condition. Its protocol, results and failed check are preserved. The corrected version uses codes 0–1023 and verifies `id=channel` before timing. The following conclusions use its confirmation results.

| Median measurement | 5.1 | 6.0 | 6.0 / 5.1 |
| --- | ---: | ---: | ---: |
| Wall time for ten internal seconds | 0.0525683 s | 0.4474190 s | 8.51 |
| Advancement process CPU time | 0.046875 s | 0.453125 s | 9.67 |
| Complete-state capture | 0.0169578 s | 0.0175056 s | 1.03 |
| Complete-state serialization | 0.1102112 s | 0.1186814 s | 1.08 |
| Final-file allocated storage | Reference | 1.1222 times reference | 1.12 |

5.1 clearly wins this advancement-cost comparison. CPU and wall time increase together, and both alternating measurement rounds agree. Memory and disk reserves remain ample, so host waiting and archive size do not explain the main difference. Minimum reserves were approximately 15.07 GiB commit, 14.45 GiB physical RAM, 11.69 GiB C and 92.57 GiB E; peak private process memory was about 0.582 GiB.

The first confirmed slow condition triggers the preregistered stop. The 8192-node and silenced conditions were not run and are not counted as completed.

## Diagnosis and implications

A separately frozen, bounded five-repeat comparison of 5.3 and 6.0 used the corrected, identifier-matched fixture. Median advancement was 0.4555816 and 0.4528874 seconds respectively; median CPU time was 0.453125 seconds for both. Scan and visit counts were identical. Fixed addressing added no material cost in this fixture. The benchmark does not call birth, so the new reproductive operation cannot explain its slowdown.

Both 5.3 and 6.0 perform a structural check every 0.1 internal seconds, scanning 204800 node/connection entries in ten seconds and recording 219136 node visits. 5.1 performs no such periodic full scan here and records 35840 node visits. The corresponding source path visits connections, settles weights, compares deletion thresholds and then checks all nodes. This is a concrete cost source to profile first. Other rules also differ; visit counts are not a breakdown of CPU-time contributions.

**The practical conclusion is that 6.0 reproduction is ready at the engineering level; execution cost currently blocks the scientific campaign, and the major performance issue predates fixed addressing.** Retain 6.0 and first profile structural maintenance. Subject to authorization, reduce repeated lookup, copying and calculation while preserving check times, numerical results and event order; then apply the same cost and complete-state gates before resuming. No such optimization was implemented in this batch.

No old data were migrated,[Public edition: manuscript editing or private locator omitted.] Originals are in `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/`, including both benchmark editions, diagnosis and standalone restoration. `audit-v2.json` independently recomputes 32 valid engineering trials, 64 complete benchmark states and the stopping decision. This is an assistant arithmetic audit, not external replication. Archive and API-readback receipts are stored separately under `publication/`.

Sources: [plan v2](../../../docs/en/plans/kernel60-revalidation-v2.md), [corrected preregistered engineering protocol](foundation-protocol-v2.en.md), [bounded diagnosis protocol](diagnostic-protocol-v2.md), [6.0 implementation](../../../docs/en/v2-kernel60.md).

## 13 November 2026 correction: file length and allocated storage

The first storage instrument used `GetCompressedFileSizeW`. For these ordinary files it returned file length without allocation-unit rounding. The table's 1.1222-fold figure therefore describes file length. A separate `GetFileInformationByHandleEx / FileStandardInfo` audit measured median final allocations of 618496 bytes for 5.1 and 692224 for 6.0, a ratio of **1.1192**. Neither measure crosses the twofold storage threshold; the 8.51-fold advancement result and pause decision are unchanged.

The directory snapshot after archive and API readback contained 749 files without duplicate hard links: 125712937 logical bytes and 127258896 allocated bytes. It includes originals, source, the archive and API readback, but excludes this subsequently generated storage audit and correction receipts. Evidence is saved separately as `storage-allocation-audit.json`. The original archive, table and published edition are preserved; the platform receives an explicitly revised report and another readback check.
