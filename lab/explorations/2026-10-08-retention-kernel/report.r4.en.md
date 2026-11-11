# continuous-memory/3: implementing automatic retention and reclamation — r4

> **Revision r4 · 2026-10-16**
> Revision reason: Add purpose, existing expectations, interpretation and explicit scientific conclusions; preserve criteria, results and historical editions.
> Original: [report.en.md](report.en.md); parent r3: [report.r3.en.md](report.r3.en.md)


Editorial synthesis dated 16 October 2026. Experiment dates, measurements, thresholds and version identities are unchanged. Purpose and meaning are reconstructed from the original protocol and report; judgments not prospectively quantified are not relabeled as preregistered passes. No subject was rerun and no large raw trajectory was recomputed.

[Parent report](report.r3.en.md) · [中文](report.r4.zh.md) · [Historical audit](../../../docs/en/plans/report-conclusion-audit-20261016.md). Parent bytes read for this review, SHA256: `abac06f56549f3b8471337e8dc57720cb8dde51c89340a62f2f14c036d46f549`.

## Goal, expectation and historical identity

This batch tested the initial continuous-memory/3 implementation for automatic retention, finite decay, reclamation, configuration isolation and backend agreement. Structural probes without a learned peripheral compared repeated with single stimulation. The expectation was that local use could extend retention while idle structure could still decay and be reclaimed. Better shape/color answering was never its registered primary goal.

This report concerns the initial implementation and probes explicitly disabling propagation and inhibition. Later dose repairs and /3.1 or /5.1 are different implementations; the historical default statements below are not declarations of today's defaults. This editorial revision changes no default or kernel.

## Explicit conclusion and analysis

**Engineering acceptance passed. In the initial isolated probe, repetition greatly extended structural retention while single exposures did not become permanent.** After 120 seconds of repeated teaching, /3 retained mean weight 0.97256 at 1,800 seconds whereas /2 had no edges. Both ordinary and strong single-exposure /3 edges were absent at the 300-second observation. Different histories produced different retention, supporting a use-dependent structural effect in this initial local retention rule.

Idle reclamation also occurred: all listed nodes, active edges and dormant records disappeared 300 seconds after fixed and expanding background stopped. Automatic retention therefore did not imply permanent accumulation in these tests. Revival produced actual transmission through a 0.04 weak edge only in a fixture with artificial historical initial values. The natural-background conditions had no revival events; fixture success is not naturally acquired recall.

The 187 passing Python checks, three skips and five passing Rust checks support configuration, state and implementation contracts. They are not 187 independent behavioral experiments. Structural values establish implementation behavior, not naming or choice accuracy.

## Meaning for ThreeMind and relation to later evidence

This is **favorable engineering and controlled structural-retention evidence**: local experience can alter retention scale while finite reclamation remains possible. It supplies an implementation basis for subsequent behavioral retention studies.

The later [retention-repair report](../2026-10-08-retention-repair/report.r3.en.md) used actual transmitted doses and found that default gain 0.2 did not retain edges to its 300-second observation. These conclusions concern different implementations and input paths. The initial isolated structural effect holds; the repaired default's actual path failed its intended retention benefit. Evaluate that default using the later evidence rather than overriding its negative result with 0.97256 here or erasing this batch retrospectively.

## Preserved original evidence

> **Revision r3 · 2026-10-10**
> Revision reason: Verified original-file relocation; append location-resolution guidance and preserve the experiment conclusions.
> Original: [report.en.md](report.en.md); parent r2: [report.r2.en.md](report.r2.en.md)


> **Revision r2 · 2026-10-10**
> Revision reason: Relocate generated evidence out of Git; preserve original bytes and conclusions.
> Original: [report.en.md](report.en.md); parent r1: [report.en.md](report.en.md)


[中文](report.zh.md) · [Preregistered scope](protocol.md) · [Results](results.json) · [Equations and plan](../../../docs/en/plans/memory-retention-v3.md)

October 8, 2026. This batch checks kernel engineering and structural mechanisms. It contains no learned peripheral or shape/color answers and does not continue the E66 subject. Every probe begins with a separate empty kernel; historical subjects, evidence and running services are unchanged.

### Delivered behavior

Independent kernel, state and hypothesis identities identify `threemind.continuous-memory/3`. Python reference and Rust native implementations share configuration/state contracts. Unspecified new creation selects /3; saved project defaults, old individuals, explicit historical configurations and old protocols retain their identities. Exact old behavior requires selecting the old kernel; `legacy-stability` within /3 is a formula ablation.

The user explicitly selected unified automatic support retention, now the default. Support S records a local retention reserve and H_node its activity-dependent half-life; there is no separate semantic importance score. Automatic mode reclaims only inactive, disconnected nodes with S<0.006 and ignores manual timing/threshold controls.

Manual experiments retain `prune_support` (node reclamation support threshold): positive values select the original threshold plus touch-age policy; zero selects positive `dead_node_retention_us` (isolated-node retention time), default 80 simulated seconds. Actual touch resets isolation and reconnection cancels it. `retain_nodes`, `dormant_traces_enabled` and `revival_enabled` default false. Disabling dormancy disables revival; enabling dormancy again does not restore revival automatically. UI/API/CLI share these semantics and inactive controls are disabled in the UI.

Edges and automatic node support use finite learned half-lives: initial minimum 30 seconds, maximum 30 days, passive H decrease 0.125 seconds per simulated second. Actual activity dose extends H and weight. The default has no permanent-consolidation flag or extra legacy stability reward. Strong input produces local salience and recoverable fatigue, with actual extra cost when the optional energy ledger is enabled. These are simulation times, not human-memory calibration.

### Structural results

The [fixed script](verify.py) disables propagation and inhibition in retention probes to separate passive forgetting from recurrent reinforcement. Two channels receive amplitude 0.8; repeated exposure occurs every 250 ms for 120 seconds. There are no semantic labels or answer scores.

| Condition | Mean weight at 0.1 s | 30 s | 300 s | 1,800 s |
| --- | ---: | ---: | ---: | ---: |
| /2 single ordinary | 0.08417 | 0.04462 | No edges | No edges |
| /3 single ordinary | 0.08534 | 0.05304 | No edges | No edges |
| /2 single intensity 4 | 0.17287 | 0.11420 | No edges | No edges |
| /3 single intensity 4 | 0.22050 | 0.15389 | No edges | No edges |
| /2 repeated | 1.00000 | 0.98477 | 0.21198 | No edges |
| /3 repeated | 0.99993 | 0.99948 | 0.99533 | 0.97256 |

New repeated exposure ends with edge H about 12.45 hours, reaching about 12.52 hours after residual activity settles, then decreasing. Node H reaches about 6.09 days. At 1,800 seconds the old repeated group has no edges but still has support 1; the new automatic law makes support retention finite. Single strong input has a benefit and fatigue but does not directly produce long retention here; no permanent bonus was added to force that result. Fatigue falls from 2.9406 at 0.1 seconds to 0.00744 at 30 seconds. Separate tests verify higher consumption with energy accounting enabled.

An explicitly initialized instrument fixture additionally verifies approximately 94.4% weight retention after 300 unreinforced seconds starting from H=3,600 seconds and weight 0.5. Disuse eventually returns H to 30 seconds. That fixture is equation verification, not natural learning.

### Background, revival and adaptation limits

Paired weak input (amplitude 0.3) arrives every two seconds for 120 seconds, then stops for 300 seconds. Fixed alphabet: 32 channels. Expanding alphabet: 120 total channels. Limits are 128 nodes and 512 live plus dormant edges; no capacity limit is reached in this batch.

| /3 condition | Fixed input end: nodes/live/dormant | Expanding input end: nodes/live/dormant | After 300 s without input |
| --- | --- | --- | --- |
| Automatic, no dormancy | 32 / 36 / 0 | 96 / 70 / 0 | All zero |
| Manual, no dormancy | 32 / 36 / 0 | 80 / 70 / 0 | All zero |
| Automatic, dormancy only | 32 / 36 / 28 | 96 / 70 / 26 | All zero |
| Automatic, dormancy and revival | 32 / 36 / 28 | 96 / 70 / 26 | All zero |

This background produces no revival. A historical-contact fixture separately verifies actual transmission through a revived 0.04 edge and no creation without historical contact. Relearning the same contact can replace its dormant trace at capacity. These finite schedules do not establish safe indefinite accumulation: frequent meaningless background can still be retained because local support does not know semantic importance.

Changed pairing first exposes 1+2 for twenty seconds, then 1+3 for twenty seconds. New-kernel weights end near 0.90319/0.97620 and reach 0.23625/0.25831 after 300 seconds. A new relation can form while the old remains; this is not behavioral reversal or absence of interference.

Single-run wall times on this host were about 0.044 seconds for /2 fixed background versus 0.395 for /3 automatic, and 0.090 versus 0.622 for expanding background. Small samples and uncontrolled host load prevent extrapolating a speed ratio, but the additional state and interval calculations cost time. Large graphs, sustained background and learned-peripheral loads need subsequent profiling. Geometric root-like branching is deferred, not implemented.

### Historical-mechanism audit

| Earlier evidence | Previous implementation/default | /3 decision |
| --- | --- | --- |
| E49 depletion/recovery, context and fast traces | Already integrated; recovery 0.8 s | Preserved; local resources also constrain learning dose |
| Delayed-arrival novelty, gain 0.018/reference 0.2 | Arrival-window is /2 default | Preserve eligibility; route earned gain into local learning dose |
| Conditional one-second facilitation; no general E45 F1 advantage | Ordinary default zero; research preset one second | Keep the conditional preset, without a universal default claim |
| E49 doubled learning/faster recovery/stronger inhibition lack general superiority | Not promoted universally | Keep conditions explicit; separately verify the new learning law |
| E20 delayed nonresponse is not complete structural loss | Historical evidence preserved | Separate structure, activity and future behavioral retention |
| Balanced calibration, process readout, correction and expanding review | Existing peripheral/tools/protocol | Preserve them without mislabeling them as Core learning |

Sources: [E49](../2026-10-05-bus-expression/report.en.md), [E20](../2026-10-01-priority-memory/report.en.md), [training protocol](../../../docs/en/training-protocol.md). No universally supported omitted Core mechanism or superior default was found. This is not a claim that every historical task has been rerun with /3.

### Validation and remaining work

Tests cover automatic/manual retention, half-life/legacy formulas, Python/Rust agreement, complete cross-restoration, observation/batching invariance, atomic configuration rejection, resource budgets, dormant capacity/toggle dependency, actual revival transmission, reclamation and strong-input recovery. Preserved /2 is compared with a witness generated by the installed pre-change native module, without assuming its binary build commit. Historical causal/9 and continuous/memory/novelty suites also run.

Initial combined validation: 187 passed, 3 skipped; Rust workspace: 5 passed; TypeScript and production UI build passed. See [final verification](verification.md) for post-default-switch checks. Windows sandbox temp-directory/process restrictions initially blocked pytest/Vite; authorized local execution resolved them without changing product behavior to hide errors. Review fixed stable budget ordering, dormant-capacity double counting, state mutation before configuration rejection, and English documentation misclassification through incidental history links.

The result table, fixed script and eighteen final checkpoints are retained (checkpoints/, about 32 KB compressed total). Checkpoints include complete configuration, identity, pending state and digests. No seed search or extended schedule was used to obtain success.

Next phase: a new complete blank individual with its own peripherals, shape/color teaching, correction/similar-example reinforcement/retesting, exact old-error conditions and /3 versus /2 comparisons under the training protocol. Ebbinghaus scheduling, realistic sustained noise, second independent training source, behavioral reversal and dormant/revival benefit remain unverified. Structural retention does not establish the cause of E66 errors.


### Data location revision

Selected generated evidence has been archived and verified byte for byte. Original reports, criteria, conclusions and embedded source_commit values are preserved. The logical downloads below require the current host administrator. The data directory is not public.

`data/experiments/2026-10-08-retention-kernel/`

[Location and hash index / 位置及哈希登记](../../artifact-index/2026-10-09-relocations.json)



> **Storage-location revision · 2026-10-10**
> This edition adds the verified move of the selected originals to `E:\ThreeMindData`. Stable scientific identities and hashes, experiment dates, measurements and conclusions remain unchanged. Paths in the preserved body describe historical sources; use the registered evidence resolver for current locations. Repository documents and frozen fixtures remain in place, and source copies are retained. Structured query data and running checkpoints remain in the database. This annotation does not assert that missing historical evidence was recovered.

## Revised conclusion

Initial /3 engineering acceptance, isolated structural retention and idle reclamation are supported. Natural revival and behavioral retention were not successful measured endpoints of this batch. The later actual-dose repair negative remains separate, with each implementation judged by its own evidence.
