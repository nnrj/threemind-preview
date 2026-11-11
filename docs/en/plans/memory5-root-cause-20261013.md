# /5 performance root causes and isolated candidates, 2026-10-13

[简体中文](../../zh/plans/memory5-root-cause-20261013.md) · [Multi-size performance retest](memory5-performance-comparison-20261013.md)

## Findings established so far

**On dense graphs, /5's main measured hotspots are edge settlement, copying and index access, deadline maintenance, contact learning, and per-node emission—not half-life mathematics alone.** A local implementation still spends CPU time reading whole objects, updating tree indexes, packaging messages, and maintaining deadlines. Avoiding unrelated graph visits does not ensure a lower cost per relevant contact.

**The stability option has another identified problem: per-edge 100ms maintenance generates many expiry events on low-activity sparse graphs.** Default H does not poll edges at that frequency; the options must be explained separately. In the earlier 1,024-node paired-input retest, default /5 reduced advancement time by approximately 38% against /2 and /3.1. Local execution is therefore not inherently worse.

Production Core and defaults were unchanged. Measurements used isolated source copies and new engineering objects, with no research individuals accessed. Optimization should first address object and scheduling representation, without deleting required events, reducing simulation cadence, or changing learning rules to manufacture a speedup.

## Measurement and its limits

Sources were copied into ignored storage; 53 functions in the copy received call counters and nested timers. Separate baseline and instrumented release binaries cover 12 configuration/workload points: /2, /3.1, /5 H, /5 S, and fully no-H /5 on dense 64-node/2-second and paired 1,024-node/100-second workloads, plus dense /5 H with 16 and 32 nodes.

Matching inputs produced identical complete final-state hashes between baseline and instrumentation at all 12 points. Source-hash checks confirm production Core was unchanged. **This establishes no detected final-state change for those fixtures, not formal equivalence for every input and intermediate trajectory.** Instrumentation adds wall time and can change compiler optimization, but adds no simulated time or extra stimulus.

“Self time” subtracts instrumented child intervals from a function's interval; it still includes uninstrumented calls, allocation, lookup, and measurement effects. It is not pure instruction time. Inclusive parent time cannot be added to child time again. Each profile point is one paired localization run; comparative performance conclusions still rely on the earlier [seven-repeat alternating-order benchmark](memory5-performance-comparison-20261013.md).

## Dense workload: where time accumulates

/5 H, 64 nodes, 4,032 directed edges, two simulated seconds: baseline advancement 1.01352s, instrumented advancement 1.13948s. Times below are wall-clock seconds.

| Function | Calls | Self time | Inclusive time | Interpretation |
|---|---:|---:|---:|---|
| `local::settle_edge` | 399,168 | 0.28135 | 0.46291 | Lookup, same-time check, copying, and writeback entry |
| `local::edge_value` | 237,888 | 0.15434 | 0.18156 | Edge cloning, projection, and timestamp representation |
| `local::timer` | 575,832 | 0.15930 | 0.15930 | Deadline lookup and tree removal/insertion |
| `local::associate` | 40 | 0.19699 | 0.57923 | External packet pairing and ordinary reinforcement loops |
| `local::emit` | 1,280 | 0.18280 | 0.47803 | Per-node propagation and associated object handling |
| `local::discrete_edge_state` | 237,888 | 0.02070 | 0.02070 | Preserving discrete stability/eligibility semantics |
| H `grow+decay+crossing` | 491,248 | Combined 0.02360 | — | H growth, decay, and threshold-crossing calculation |

The self times of `settle_edge` and `edge_value` locate separate costs, but `settle_edge`'s 0.46291s inclusive time must not be added to the entire `edge_value` time again. The three H functions total approximately 23.6ms within this 1.139s instrumented advancement: a smaller hotspot. **This does not mean H consumes exactly 2% of production CPU, or include every object/deadline-management cost caused by H.**

In the [local executor](../../../crates/threemind-core/src/local.rs), `settle_edge` returns a complete `Edge` clone even on its same-time shortcut; the other path also clones in `edge_value` and writes back to a tree. Nodes, edges, queues, and deadlines use tree structures, with timestamp string conversions. The [older executor](../../../crates/threemind-core/src/lib.rs) uses dense numeric rows and indexes. These are concrete representation differences, not unavoidable costs of locality itself.

The `associate` hotspot belongs to restored external co-packet learning; pairing cannot simply be removed for speed. A 64-channel packet yields 64×63 directed candidates. This run did not reinstate the corrected extension that paired internal receivers with one another.

## Propagation and event counts are different quantities

In the same dense fixture, /2 and /3.1 each call `continuous::emit_continuous` 20 times, while /5 calls `local::emit` 1,280 times. **The former processes a graph round; the latter processes a node. This is not evidence of 64 times as much propagation.** Some node-emission calls produce no effective signal event.

Event creation gives another measure: 80 calls to older `lib::event`, versus 1,340 to /5's `local::event`. These count all created event kinds, not signals alone; 1,280 `emit` calls must not automatically be labeled 1,280 signals. The event function's small self time is also not total event-lifecycle cost: message construction, JSON conversion, queue operations, and later reception grouping appear elsewhere.

The older [propagation path](../../../crates/threemind-core/src/continuous.rs) aggregates a round's signals, whereas the local path delivers per emitting node. Representation and implementation batching can be investigated while preserving independent node actions, established same-time ordering, and every required delivery.

## Stability mode: periodic maintenance on a sparse graph

For 1,024 nodes and 1,024 edges under rotating pair inputs over 100 simulated seconds, the same /5 counters report:

| Measure | Default H | Stability S |
|---|---:|---:|
| Baseline advancement, seconds | 0.45092 | 2.64745 |
| Instrumented advancement, seconds | 0.57221 | 3.27932 |
| Expiry checks | 3,942 | 897,382 |
| `settle_edge` calls | 156,871 | 1,050,311 |
| `timer` calls | 217,991 | 1,111,473 |
| S `expiry` self / inclusive time | — | 0.87182 / 2.43162s |
| S `timer` self time | — | 0.34273s |

In S mode, `edge_timer` schedules the next propagation period; `expiry` updates eligibility, stability, and untraversed edge weights, then schedules again. Many edges without effective transmission are consequently processed periodically. H predicts threshold crossing, so most edges do not need this class of event every 100ms. The 897,382 versus 3,942 counts use the same definition and compare maintenance frequency, but do not directly determine CPU percentages.

Fully no-H means `legacy-stability + manual node retention`. **The measured calls to `grow`, `decay`, and `crossing` were all zero in both dense and sparse no-H profiles.** S periodic maintenance remained. Earlier repeated runs found no clear dense speedup and a 5.74-fold sparse slowdown, so this is not an artifact of failing to disable H. Replacement retention/reclamation rules change as well; this is not an arithmetic-only ablation preserving the same trajectory.

## Is local architecture inferior to global architecture?

**The evidence supports expensive dense hot paths in the current /5 implementation, not inherently inferior local architecture.** Nearly all objects remain active in the dense fixture, leaving few effective edges for local scheduling to avoid while object/event-management costs remain. The large low-degree result demonstrates a locality benefit. However, cross-version comparisons share inputs and final graph sizes while /5 also includes H, automatic support, and reclamation mechanisms absent from /2. They are not a pure executor A/B with identical dynamics. Separating mechanism burden from representation cost requires another isolated implementation comparison with matched mechanisms.

## Optimization candidates and proof obligations

These are candidates, not approved production changes. Integration must disclose reasons, changes, and effects under [kernel governance](../kernel-change-governance.md).

| Candidate | Work to reduce | Required preservation and evidence |
|---|---|---|
| Typed internal messages | Repeated runtime JSON construction/parsing | Input validation, event order, saved format, and restored identity |
| Compact slots with stable IDs | Tree lookups, allocation, poor cache locality | IDs cannot silently become other scientific identities; deletion, checkpoints, and ordering remain valid |
| Avoid whole-Edge clones for current read-only weights | Whole-object copying in inhibition/read-only paths | Direct access only when both time and discrete-period settlement are current; otherwise settle normally |
| Cache configuration-only constants | Rebuilding parameters and recalculating fixed terms | Correct invalidation on configuration changes; verify floating-point order/results |
| Exact lazy settlement for stability | Per-edge 100ms maintenance | Prove eligibility, clamps, traversed-edge exemptions, thresholds, and deletion times; do not merely delete periodic events |

Validate local read-only access and constant caching first, then consider larger layout changes. Exact lazy stability settlement may offer substantial gains, but has a higher proof burden and must not silently change forgetting. Disabling learning, reducing inputs, freezing objects, or skipping internal time is not an implementation optimization.

## Isolated A/B candidates: initial validation complete, no production integration

Three uninstrumented binaries were built from the temporary copy: baseline, A, and A+B. A caches the configuration-only single-period eligibility-retention coefficient instead of recomputing its exponential. B reads three scalar values at one inhibition weight-access site when both timestamp and discrete-period settlement are current, avoiding a full Edge clone while preserving the audit count. B was tested on top of A; **its standalone benefit was not measured**.

Each main workload uses one warmup and seven measured repetitions, alternating the three-program order. Six additional single-run controls cover /2, /3.1, /4 H, /4 S, /5 S, and no-H: 66 raw results in total. Complete final-state hashes match within every case. The six single-run controls establish final-state witnesses, not version-performance rankings.

| Default H workload | Baseline median seconds | A cache | A+B | Time reduction, A / A+B |
|---|---:|---:|---:|---:|
| Dense 64 nodes, 2 simulated seconds | 1.00172 | 0.98462 | 0.94626 | 1.71% / 5.54% |
| Paired 1,024 nodes, 100 simulated seconds | 0.46832 | 0.45761 | 0.41877 | 2.29% / 10.58% |

Dense baseline samples range from 0.91445 to 1.10643s, versus 0.89486–1.19988s for A+B. A+B is slower than its same-round baseline in three of seven rounds. The overlapping ranges support reporting a median trend, not a stable speedup. All seven sparse A+B samples, 0.41398–0.43373s, are below the fastest baseline sample, 0.44620s, providing clearer improvement in this batch. These remain shared-workstation samples without confidence intervals or formal-course acceleration evidence.

Some representation overhead can therefore be reduced while preserving measured final states, but this does not resolve the earlier dense comparison's greater-than-threefold time gap. Intermediate trajectories, complete save/restore, configuration-change invalidation, and wider conditions still need verification. **Matching 66 final states does not prove complete equivalence.** Candidate binaries were not installed; production Core, defaults, and formal individuals remain unchanged. Integration requires further checks and applicable authorization.

## Evidence and reproduction entry points

Large originals remain in ignored `.work/memory5-root-cause-20261013/`, outside Git:

- `profile-validation.json`: 12 paired baseline/instrumented cases, full final-state hashes, 53-function statistics, H call counts, compiler and binary hashes.
- `*-baseline.exe.json` and `*-profile.exe.json`: raw metrics and timings for each fixed workload.
- `source-hashes.json`: source-protection evidence; `crates/` contains the temporary copy and `baseline.exe` / `profile.exe` its binaries.
- `candidates-r1/summary.json` and 66 per-run files: uninstrumented candidate comparisons with configuration, binary, and patch-manifest hashes; `cache.exe` and `weight-view.exe` are isolated candidates.
- [Isolated profiling tool](../../../tools/profile_kernel_locality.py), [candidate tool](../../../tools/memory5_perf_candidates.py), and [repeated candidate benchmark](../../../tools/benchmark_memory5_candidates.py): explicit engineering tools requiring neither a Lab service nor a research database. The benchmark consumes preserved isolated executables and requires a new output directory under `.work`.

Conclusions apply to the measured fixtures. Independent repeated timing, historical-version witnesses, save/restore checks, and matched-input result verification are needed before selecting candidates for proposed production integration.
