# Performance and locality audit of /2, /3.1 and /4

October 13, 2026. The user requested a multi-cause explanation of the newer kernels' slowdown, particularly whether local processing had been implemented contrary to the intended model. This audit did not change production Core, install a native extension, restore E67/E68 individuals or restart experiments. E67, /4 and the E68 automatic continuation remain stopped.

[简体中文](../../zh/plans/kernel-performance-audit-20261013.md) · [E68 continuous experiment](../../../lab/explorations/2026-10-13-continuous-shape-color/report.en.md) · [E67 termination record](../../../lab/explorations/2026-10-11-shape-color-kernels/stop-20261012.en.md)

## Conclusions

**The slowdown does not show that local mechanisms are inherently ineffective, and retaining more connections is not a sufficient explanation. The implementation contains both avoidable duplicate work and changes to learning rules beyond an equivalent execution refactor.**

1. `/3.1` combines the earlier solver framework with local retention and reclamation. Whole-node relaxation, batch propagation and whole-edge eligibility/stability processing remain. New retention settlement and expiry scheduling run on top of those paths. It has not replaced all whole-graph work with local events.
2. No per-step whole-graph refresh or complete index rebuild was found in `/4`'s default advancement path. However, all effective recipients of each internal signal packet undergo pairwise association learning, unlike the default rules in `/2` and `/3.1`. At high connectivity, this work can grow cubically with node count.
3. `/4` makes each local visit expensive through repeated settlement at the same instant, object cloning, JSON round trips, string timestamps and repeated deadline-index updates. Its stability option still applies discrete updates to every edge every 100 ms, distributed across many local expiry events.
4. Earlier locality acceptance established that adding unrelated isolated nodes did not increase visits for a local event. It did not cover the combinatorial amplification caused by large local neighborhoods and many simultaneously active nodes. That was a gap in the performance validation.

## 1. Performance evidence with identical actual inputs

The first corrective teaching round was reread for all four E67 arms: 165 lessons, 188 clips and 5850 frames. Each spans internal time 180–472.5 seconds, advances 292.5 simulated seconds and makes 23,400 native advancement calls. The canonical SHA-256 of the frame-by-frame stimuli is identical across all four arms:

`1019290be1eb88aa52ae8b05dc16eecbd38445c8bff30f41c6145aa653ca3f51`

| Measurement | /2 | /3.1 | /4 half-life | /4 stability |
|---|---:|---:|---:|---:|
| Native advancement, seconds | 649.719 | 1190.025 | 6171.915 | 7405.446 |
| Relative to /2 | 1.00 | 1.83 | 9.50 | 11.40 |
| Relative to /3.1 | 0.55 | 1.00 | 5.19 | 6.22 |
| Whole-system saving, seconds | 46.796 | 56.946 | 69.337 | 68.879 |
| Observation, seconds | 37.738 | 36.508 | 68.807 | 71.460 |
| Final nodes for this stage | 400 | 398 | 398 | 398 |
| Final edges for this stage | 144774 | 143996 | 140062 | 141978 |

`/4` is much slower in this course segment despite having fewer edges at its end. Saving, observation, database work and video production cannot explain the separately measured native advancement gap. The complete graph-development trajectories still differ. This table is not a dedicated-hardware microbenchmark, and native-call wall time includes boundary and return encoding costs.

This is the cost of a continuous teaching segment, independent of E67's per-question-restoration scores. The correction that E67 does not establish continuous-examination performance remains valid. Separately, the new continuous E68 experiment measured `/3.1` native advancement at 1.896 times the `/2` cost, with final scores of 71/72 versus 66/72. Slower execution does not invalidate those scores.

Originals: `E:\ThreeMindData\experiments\2026-10-11-shape-color-kernels\arms\<arm>\correction-1\result.json`, `clips/*.json.gz` and complete states. [Read-only evidence tool](../../../tools/audit_kernel_stage_costs.py).

## 2. Why /3.1 is slower than /2

### 2.1 Only part of the whole-graph work was replaced

`ContinuousEngine::new_retention31` still constructs the earlier continuous engine and then adds the retention operator. Execution retains:

- `restoration.rs::relax`: traversal of all nodes at the established event/solver times to decay activation, traces and inhibition.
- `lib.rs::advance_impl`: construction of a whole-node activation baseline and generation of inhibition.
- `continuous.rs::emit_continuous`: sorting all node IDs, copying nodes and adjacency, updating eligibility and stability across all edges after propagation, and clearing direct/associative readout fields on all nodes.

Demand-driven weight retention, expiry-based reclamation, edge removal and affected-index updates have been localized. The earlier whole-graph prune and retention-state synchronization paths are no longer used. The accurate description is partial localization: neither no implementation nor complete replacement.

### 2.2 Edge use triggers multiple expiry reservations

When an edge actually transmits, H is updated and expiry is scheduled. Ordinary weight strengthening immediately schedules it again. No expiry event executes between these steps; the second reservation immediately supersedes the first.

Even when the new deadline is identical to the old one, `retention.rs::timer` removes entries from its BTreeMap/BTreeSet and reinserts them. Every ordinary strengthening of an established edge also makes `edge_changed` repeat isolation-marker and node-timer cleanup for both endpoints.

The final E68 `/3.1` original contains these execution counters:

- **3,357,181,044 actual edge-retention settlements**.
- 13,586,125 node-retention settlements and 564,604 expiry checks.
- **2,445,808,123 total touches on surviving edges**. Both learning paths that increment touches subsequently call `edge_changed`. Those surviving edges alone therefore establish at least that many corresponding expiry-scheduling calls, excluding removed edges and the additional reservation during emission.

This measures implementation work associated with learning experiences, not additional memory benefit. `/2` has more touches on surviving edges—2,607,331,469—so more ordinary learning operations in `/3.1` cannot simply explain the difference.

### 2.3 Repeated data-structure and formula work

Retention state resides in a BTreeMap side table while the actual edges reside in a Vec/HashMap. An operation repeatedly crosses several indexes. Even after settlement at the current time, expiry scheduling computes another retention projection with dt=0. H growth repeatedly computes the logarithm of a configuration constant.

There is also a definite redundant lookup: the whole-edge trailing loop first executes `traversed.contains`, then checks whether legacy stability-controlled forgetting is enabled. Under the default half-life mode, the latter condition is always false, making the preceding tree lookup irrelevant. Testing the mode first can skip it without changing a formula.

H growth, forgetting and threshold timing use the agreed exponential/logarithmic formulas and an analytical inverse. **There is no binary search for the threshold.** The formulas are not themselves unsupported errors; the problem is repeated evaluation and object-management cost.

## 3. Why /4 is slower still, and where the implementation differs from the intent

### 3.1 One transmission becomes pairwise learning among its recipients

The source path is: `local.rs::emit` packages one source's outgoing neighbors; `receive` groups effective recipients by packet identity; `associate` runs a double loop over those recipients.

For example, A sends signals to B, C and D. In addition to each recipient processing its own signal, the implementation produces candidates for strengthening or creating B↔C, B↔D and C↔D connections. Default unified reception admits internal signals to this path. Default `co-stimulus` internal signals in `/2` and `/3.1` do not invoke associate in this way.

Thus consistent external/internal reception does more than unify a node's response here: it expands association-learning opportunities. This behavior is present in `/4`'s implementation/contract, but cannot be described as an execution-only change preserving the learning process. The change and its complexity should previously have been explained and validated separately.

A packet with k effective recipients causes k² loop iterations, including rejected self-pairs. Across packets, the work is `Σ k_packet²`. With many nodes each sending to a dense neighborhood, the worst case is O(N³), whereas one traversal of existing connections is O(E). Actual gates reduce recipient sets; this worst-case bound is not a count measured in the formal experiment.

This meets a broad criterion of visiting only objects associated with a packet. **It is not equivalent to each node responding only to signals it actually receives and affecting others through actual contacts.** This is the mechanism choice most in need of explicit reconsideration.

### 3.2 Simultaneous arrivals are projected repeatedly

Inhibitory packets are separated by source. Every inhibitory message calls `settle_node`, even if that recipient was already settled at the same instant. The call still clones the node, parses its timestamp, evaluates decay expressions and writes it back. Context processing settles before reception, and touch settles again. Outgoing and incident adjacency processing can also settle the same edge repeatedly.

Existing counter increments over the first corrective round:

| Counter | /3.1 | /4 half-life | /4 stability |
|---|---:|---:|---:|
| Node settlements/visits | 2545524 | 403280120 | 411292996 |
| Edge settlements/visits | 658869134 | 2185434581 | 2694290996 |
| Expiry checks | 150094 | 756504 | 419381205 |

Counter definitions differ across these versions, so their ratios are not CPU-time shares. They nevertheless establish that actual work reaches hundreds of millions to billions of operations.

### 3.3 Local timers do not remove stability's periodic work

The stability option still requires each edge's original discrete update on a 100 ms lattice. There is no whole-edge for loop, but each edge's deadline is popped, processed and reinserted. At high connectivity, work formerly performed in a sequential traversal becomes E ordered-queue operations, with worse cache behavior and constant overhead. The stage's 419 million expiry checks are consistent with this path.

Switching from H to stability therefore does not solve the slowdown. Shared pairing and object-management costs remain, and stability adds another periodic event class.

### 3.4 Heavy local objects and unnecessary adjacency visits

- Internal events are encoded as JSON Value, then cloned and decoded upon arrival. External persistence requirements do not require this overhead for internal dispatch.
- Nodes/edges are cloned and cloned again on write-back; string timestamps are repeatedly parsed and constructed.
- `timer` rearranges both indexes even when the deadline is unchanged.
- Each touch scans incident edges for novelty windows, although most edges have long passed that window.
- Emit gathers inhibitory weights across all incident edges before checking whether transmission is needed. The same source features are generated repeatedly for outgoing edges.
- Having each node/edge calculate its own decay requires more numerical evaluations than the old engine's shared per-step factor. Pure-function caching can reduce this cost without silently changing the decay law.

### 3.5 Causes not found

The default `/4` advance path obtains its next instant from event/deadline queues. No whole-graph snapshot or complete index rebuild was found on this hot path. Whole-graph projections mainly occur in observation, graph display, statistics and saving. Those costs can still be improved, but do not sufficiently explain the main native-advancement gap.

`scan_visits=0` only means that the explicit scan-control branch did not scan. It does not establish a low total visit count. In `/4`, `pending_events` includes deadlines: the H arm's 141099 items comprise 363 messages and 140736 deadlines. Dividing that figure directly by the older kernel's two queued transmission events is misleading.

All four arms use the same release native binary, SHA-256 `baa17c4f150ada52b5b504286e801fe472f1695a3ff12b32be95b24c7cba9379`. `/4` is not using a Debug build, and Python is not running alongside Rust to synchronize dynamics. Energy, dormancy/awakening and global homeostasis are disabled in this batch and cannot be named as its main causes. Full internal-event tracing is also disabled.

## 4. Short engineering profiling in this audit

An ignored directory, `.work/kernel-performance-20261013`, holds a copy of the Rust source and a separately compiled release driver. The production extension is not replaced. Fresh synthetic Core instances with 16/32/64 channels each receive 40 frames at 50 ms intervals over two simulated seconds. They have no image semantics, reader, database, saving or restoration of research individuals.

[Preparation/runner](../../../tools/profile_kernel_locality.py) · [Driver template](../../../tools/kernel_locality_driver.rs) · [Observation-probe template](../../../tools/kernel_locality_probe.rs). Probes only record function calls and timings; no probes were added to production source.

| Channels | /2 native seconds | /3.1 native seconds | /4 H native seconds | /4 stability native seconds | /4 H pair-loop iterations |
|---|---:|---:|---:|---:|---:|
| 32 | 0.0819 | 0.1525 | 0.8982 | 0.9339 | 307291 |
| 64 | 0.3447 | 0.6601 | 7.1779 | 7.5024 | 2390245 |

Times are from the first uninstrumented run. Separate instrumented runs locate calls and loop counts; their timings do not replace production-speed measurements. Final graphs contain 992/4032 edges. Doubling nodes roughly quadruples edges and the older kernels' runtime, while `/4` runtime and pairing counts increase about eightfold. This matches the source-level complexity prediction rather than relying solely on formal-experiment end states.

At 64 channels, `/3.1` already makes 817568 timer calls in two simulated seconds, versus 7348970 for `/4 H` and 7672421 for stability. The heaviest instrumented `/4` call subtree is associate and its edge settlement/scheduling work. Optimizing only graph display or JSON export would miss that finding.

Uninstrumented and instrumented final complete-state hashes match for all four conditions at all three sizes. This proves only that the observation probes did not alter the final states of these fixtures; it is not a complete formal-trajectory validation. Instrumented exclusive time includes some child-probe bookkeeping cost and is not published as an exact CPU share of the formal course. Short fixtures use record=false, which differs in scope from the formal inputs-only recording path.

### Two equivalent candidates tested in an isolated copy

A third, separate executable adds only unchanged-deadline early returns and a mode check before the traversed lookup. Pairing rules, inputs, formulas, propagation intervals and thresholds remain unchanged. The 64-channel fixture runs in three paired repetitions, including both execution orders, after compilation and original-file decoding have finished:

| Condition | Original median seconds | Candidate median seconds | Range of paired time reductions |
|---|---:|---:|---|
| /2 control | 0.2896 | 0.3010 | -42.0% to 5.0%; no consistent improvement |
| /3.1 | 0.5991 | 0.5457 | 3.3% to 23.4%; substantial short-run variability |
| /4 H | 6.2283 | 6.1045 | -1.2% to 4.2%; no consistent improvement |
| /4 stability | 6.2402 | 5.3660 | 11.9% to 18.2%; improved in all three pairs |

Every pair has the same final complete-state hash. This is engineering feasibility evidence, not production integration acceptance. In particular, the lack of consistent benefit for `/4 H` **rules out the optimistic claim that fixing deadline indexing alone solves the overall slowdown**. Do not extrapolate these two candidates to every proposed remedy or promise a formal-course speedup. Short timings on a shared workstation vary; all three original values are preserved.

Raw engineering outputs, state digests and build provenance are in `.work/kernel-performance-20261013`: `formal-evidence.json`, `engineering-summary.json`, individual JSON measurements and three executables. The summary records compiler, configuration, source-manifest, probe and executable hashes. These engineering originals stay outside Git. The tool sequence prepare→build (without/with probes)→run→candidate→build --candidate→run --candidate→summarize can be repeated in a fresh `.work` subdirectory; existing outputs are not overwritten. Production source and the installed binary were not replaced.

## 5. Actionable remedy order and boundaries

| Priority | Work | Mechanism implications |
|---|---|---|
| P0 | Skip unchanged-deadline rearrangement; test mode before irrelevant lookups; reserve expiry once after an emission's final updates | Can be an equivalent implementation optimization; verify complete state and ordering |
| P1 | Typed internal messages, integer timestamps, fewer clones, in-place updates, cached constants/source features | Can be an equivalent implementation optimization while preserving persistence compatibility |
| P1 | Reuse same-instant settled values; maintain only adjacency with pending novelty settlement; gate inhibition earlier | Preserve all thresholds/clamps, accumulation order, audit semantics and expiry times; do not arbitrarily omit state write-back |
| P2 | Specify which learning/birth opportunities internal signals should create; remove unwanted recipient cross-pairing | Substantive learning-rule change; confirm first and introduce an identity such as /4.1, retaining /4 |
| P2 | Determine whether discrete stability updates can be solved/combined exactly, or whether a new forgetting formula is acceptable | Retain the version only for exact equivalence; otherwise use another version. Do not merely increase internal time steps |

Reducing inputs, skipping signals, imposing edge limits, disabling learning, diluting teaching, rolling back or adding global quotas is not an acceptable substitute for optimization. Ordinary host throttling also does not reduce the total work required for the same simulated experience.

If association is redesigned around actual contact or signals received by an edge, the first contact between previously unconnected objects still needs an explicit rule. Performance is not permission to silently add global candidate selection, semantic rewards or connections inferred from display positions. Low-level batching that preserves message order does not require a global observer allocating learning opportunities. Model-local rules and executor data layout are distinct concerns.

Acceptance should cover large unrelated isolated graphs, varying connectivity at fixed node count, many simultaneous sources and continuous dense sensory input. Record candidate pairings, effective learning, repeated same-instant settlement, unchanged-deadline rearrangement and separate advancement/observation/saving costs. Verify inputs, event ordering, deletion times, complete state, restoration and Python/Rust agreement. A zero scan counter alone is no longer sufficient acceptance evidence.

## 6. Evidence limits and next status

This report combines read-only evidence collection, code inspection and engineering diagnosis on fresh synthetic fixtures. It is not another shape/color performance-score experiment. Formal `/4` research remains at 472.5 seconds without a complete final comparison. The October 12 early performance report's statement that the stability arm was not yet born describes that earlier snapshot; the subsequent termination record updates it. Preserve the original report.

There is another timing-scope issue: `/4 H initial-teaching` Core timing inherits cumulative work from before restoration, whereas wall time covers only the current launch. The Core/wall ratio cannot be interpreted as a time share. This report uses the complete matched correction-1 segment and retains that limitation.

Current evidence points to implementation choices and gaps in performance validation. It does not support a claim that someone deliberately sabotaged the experiments. This audit does not infer motives from the user's suspicion or send accusations to third parties.

Production repairs have not been implemented. These recommendations do not automatically authorize dynamics changes, rerunning old experiments or deleting originals. E68, prior negative results, stopped experiments and the author's manuscript remain intact.
