# R51b: locating the cost of advancing version 6.0

13 November 2026. Engineering diagnosis; formal revalidation remains paused. [Preregistered protocol](protocol.md).

## Purpose and conclusion

This study asked why 6.0 took approximately eight times as long as 5.1 on the same-sized fixture, and which part should be optimized first. The intended deliverable was an explanation supported by timing and complete-state checks, followed by an optimization order.

**Repeated emission dominates the cost: weak activity keeps nodes attempting to send, while connections block the resulting tiny signals.** Emission accounted for 76.66% of coarse-profile time and structural checks for 17.67%. Of 102,400 connection transmission attempts, 97,280 transmitted neither excitation nor inhibition. During internal seconds 1–10, all 92,160 attempts transmitted nothing; that interval accounted for 87.15% of total elapsed time.

This revises the initial priority after R51a, which identified structural scanning as the first path to investigate. Scanning contributes, but emission is the principal cost. Reducing scan frequency alone does not close the performance gap. Diagnosis is complete; production implementation and formal subjects are unchanged.

## Measurement and validity

The fixture contains 512 independent reciprocal pairs: 1024 nodes and 1024 directed connections. Each node receives a stimulus of strength 0.8 at internal time zero, followed by ten internal seconds of advancement. Node identifiers and stimulus codes are 0–1023 in both versions. Each version uses its genuine defaults, with the same extension of the quiescence death delay. Only advancement is timed; saving, analysis and research API readback are outside the timing interval.

Each production condition was repeated five times with alternating order. The 4096-node comparison used three repetitions per version. A separate source copy added coarse timers for major processes and detailed timers for settlement, decay and scheduling. Each timer level was repeated three times; disabled timers and segmented advancement were also checked.

There were 31 production-module and 21 instrumented-copy trials. All 104 complete initial and final files were decoded and checked. Every instrumented final state exactly matched its production reference, including segmented versus uninterrupted advancement. Hashes of 68 production source and build-definition files remained unchanged, and the installed native module was not replaced. These are 52 engineering repetitions, with zero scientific independent origins.

Instrumentation has measurable overhead. Median 6.0 advancement took 0.45066 seconds in production, 0.46820 seconds with the temporary module's timers disabled, 0.48931 seconds with coarse timers, and 0.66233 seconds with detailed timers: increases of 3.89%, 8.58% and 46.97%, respectively. Major shares below use coarse timing; detailed timing identifies calls rather than estimating production performance directly.

## Total cost and bounded controls

Values are median wall-clock seconds for ten internal seconds. Each row has five repetitions unless stated otherwise.

| Condition | Median time | Reduction from default 6.0 |
| --- | ---: | ---: |
| Default 5.1, 1024 nodes | 0.05259 s | — |
| Default 6.0, 1024 nodes | 0.45066 s | — |
| 6.0 structural-check interval increased from 0.1 to 1 s | 0.38729 s | 14.06% |
| 6.0 exponential decay replacing inverse-logarithmic decay only | 0.41194 s | 8.59% |
| 6.0 with both diagnostic changes | 0.34915 s | 22.52% |
| Default 5.1, 4096 nodes, three repetitions | 0.23350 s | — |
| Default 6.0, 4096 nodes, three repetitions | 1.97298 s | — |

The 6.0/5.1 ratio was 8.57 at 1024 nodes and 8.45 at 4096 nodes. Quadrupling the node count left the ratio similar. At 1024 nodes, default elapsed times ranged from 0.05192–0.05403 seconds for 5.1 and 0.44970–0.47163 seconds for 6.0. CPU time showed the same gap. The obstacle is CPU cost during advancement.

Changed check intervals and decay curves were confined to separate engineering subjects. Their complete final states differ from the default; they diagnose cost and were not adopted as formal configurations. Exponential decay reduced total cost by about 9% here, so the inverse-logarithmic formula does not explain the approximately 8.6-fold gap.

## Where the time goes

The following values are medians of three coarse profiles. Shares are medians of individual shares, so dividing the median times need not reproduce them exactly.

| 6.0 process | Time | Share of total | Calls |
| --- | ---: | ---: | ---: |
| Emission, including its internal settlement | 375.09 ms | 76.66% | 102,400 |
| Structural checks, including their node checks | 86.43 ms | 17.67% | 100 |
| Reception | 9.69 ms | 1.96% | 106 |
| Whole advancement | 489.28 ms | 100% | 1 |

The remaining approximately 3.7% is mainly outer scheduling. Structural checks invoke node expiry checks; most expiry time is already included in 86.43 ms and must not be added again. In every trial, the sum of times excluding nested calls equalled the whole measured advancement.

Version 5.1 made 17,408 emission calls; 6.0 made 102,400, or 5.88 times as many. Emission performs node and connection settlement, short-term state updates, resource release, signal calculation, threshold checks, accounting and scheduling.

Detailed profiling counted 204,800 connection settlements, 210,944 decay evaluations, 421,888 log-remaining evaluations and 313,444 timer operations. These occur in both emission and structural checks and are nested. They explain work inside the processes and must not be added directly to coarse-profile times.

## Why calculation continues without transmission

The 6.0 `pulse` function schedules another emission when node activation is positive, inhibition is positive, or inhibition remains pending. The default interval is 0.1 internal seconds. In 5.1, residual inhibition must reach `inhibition_propagation_min` to continue scheduling emission through that condition.

Default 6.0 disables the separate inhibitory sender gate but enables a common connection signal threshold of 0.0004. The source therefore continues offering signals. After updating connection state and calculating transmission, the connection sets an amount below the threshold to zero. Weak inhibition can repeatedly trigger this sequence.

Saved states support this explanation. At ten seconds, every 6.0 node has zero activation but inhibition of approximately `1.23714e-38`; emission timers remain. The corresponding 5.1 fixture retains inhibition of approximately 0.001917, below its 0.002 gate, which no longer schedules emission on that basis.

**Zero transmission still involves internal changes.** The current implementation releases synaptic resources before applying the connection's signal threshold. It also drains source inhibition and updates state times and accounting. Finite-energy configurations additionally involve emission energy. Simply deleting these attempts would change dynamics. Any future batching must establish equivalence for resources, energy, inhibition, time and event ordering, then pass complete-state comparisons.

Relevant code is in `crates/threemind-core/src/local60_transitions.rs`: `pulse`, `emit`, `settle_edge` and `expiry`. The 5.1 counterpart is `local_shared.rs`. These descriptions refer to frozen source `b26b6012`.

## Recommended order and implications for ThreeMind

**Optimize emission implementation first while retaining the current signal rules.** Source inspection identifies repeated construction of fallback short-term states, copying of states with string timestamps, time parsing and formatting, configuration dictionary lookups, and repeated connection-container lookups and writes. These are the first candidates to reduce. Existing short-term state should not require eager construction of an unused fallback; fixed settings can be parsed at creation; unchanged state can avoid copying. Their actual benefit requires measurement after implementation; no speedup is claimed in advance.

Second, reduce repeated settlement and scheduling within structural checks. Changing check frequency affects the timing of deletion and other events, so it is not automatically an equivalent optimization. Third, assess whether exact formulas can combine successive updates with zero output. Such work must account for synaptic resources and energy, rather than relying on zero output alone.

This study explains the performance obstacle before revalidation: current 6.0 pays the full computational cost for many emission attempts that transmit nothing, with structural maintenance adding further work. R51a found similar costs in 5.3 and 6.0, placing the main change before fixed-function addressing. The next implementation work now has a clear target while preserving the model's rules. Changes to weak-signal handling or other dynamics remain separate author decisions. Formal scientific revalidation stays paused.

## Originals and verification

Originals: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/cost-profile-v1/`. `stock/results.json` contains production comparisons, `instrument/results.json` timing and counters, `summary.json` medians, and `profile-analysis.json` an independent file-based recalculation of states, counters and nested timing. The isolated sources and native module accompany the archive for engineering reproduction.

The one-second host guard checked commit headroom, physical RAM and C/E space. Both batches remained above the 5/4/5/25 GiB reserves, with no resource pause or incomplete unit. The same assistant performed independent arithmetic from saved files; this is not registered as external replication. The research record is R51b. Delivery completion is determined by `publication/completion.json` in the data directory.
