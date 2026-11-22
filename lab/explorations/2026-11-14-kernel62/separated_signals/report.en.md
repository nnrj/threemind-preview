# R51t12: separating excitatory and inhibitory states did not restore prefix discrimination

2026-11-15. Kernel: ThreeMind 6.2. Research record: `b6725bdc-406d-5ae8-9981-67e071bc7424`.

**Conclusion: with inhibitory learning enabled, separating base weights, synaptic resources and learning records, individually or in combination, did not restore prefix discrimination in this experiment.** All six groups under each of two configurations passed 0/2 curriculum blocks. The options have been implemented and validated, but the experiment provides no capability benefit supporting their activation. Shared state remains the default.

## Purpose and expectation

R51t11 showed that inhibitory transmission could refresh connection usage times even when explicit inhibitory learning was disabled. Those records affected retention and later co-stimulation reinforcement. Under a particular inhibitory transmission configuration, removing that update restored prefix discrimination. The author proposed another route: retain inhibitory learning while giving excitation and inhibition their own weights and resources. The author subsequently approved separate learning records and requested a performance comparison.

The registered expectation was that, if shared state sufficiently explained the lost distinction, separating the relevant state would allow both prefixes to evoke their correct endings. That expectation was not met. The tested separation settings do not restore the capability in this apparatus.

## Methods

Six groups were compared under each of two fixed configurations. P used the 6.2 default single-age inverse-logarithmic decay, arrival-window novelty and a 0.0004 connection signal threshold. S used stability-based retention, immediate novelty and a 0.004 excitatory connection threshold, as in the earlier localization work; its inhibitory connection threshold remained 0.0004. Both retained the prescribed node thresholds, inhibitory learning, both weight-reinforcement mechanisms, resource prechecks and local activity expiry.

Each group used two curriculum blocks with exchanged ending associations. Each new individual received 212.2 internal seconds of continuous teaching. Its complete state was preserved before making separate AB and DB diagnostic copies. Each diagnostic combined a different prefix with the common B cue and recorded 15 seconds of activation, inhibition, direct activation and associative activation at 10-millisecond intervals, giving 1502 observations. Teaching was continuous. The statistical units were two curriculum blocks; the 72 stages and 48 processes were nested observations.

The registered criterion required the correct ending's peak activation after B to exceed the alternative by more than 1e-6. Both AB and DB had to pass in each block, and both blocks had to pass for recovery. A fresh-encoding test was conditional on recovery. No group qualified, so computation ended without adding that batch or widening the parameter search.

Weight-only separation retained shared usage and retention records. Learning-record separation gave each signal type its own fast enhancement, eligibility, stability, retention timescale, decay age and usage records. Separate resource pools each retained the original capacity, so this condition changed both consumption isolation and total capacity. The [implementation notes](implementation.en.md) define the switches and their precedence; the [protocol](protocol.en.md) was written before execution.

## Results and interpretation

| Condition | P: default retention | S: stability retention |
| --- | ---: | ---: |
| Shared | 0/2 | 0/2 |
| Resources only | 0/2 | 0/2 |
| Weights only | 0/2 | 0/2 |
| Weights and resources | 0/2 | 0/2 |
| Weights and learning records | 0/2 | 0/2 |
| All three | 0/2 | 0/2 |

All 48 diagnostic processes were complete. No failure resulted from missing observations. Under P, every condition had a negative correct-ending margin for one cue and a positive margin for the other. S showed the opposite preference but the same failure to distinguish both prefixes. In block 0, shared P margins for AB/DB were −0.000133286 and 0.000133321; with all state separated, they were −0.000191893 and 0.000189921. Shared S margins were 0.001558728 and −0.001558713; full separation gave 0.001272596 and −0.001272573. Block 1 had the same corresponding scores.

The system therefore retained an ending preference rather than switching to the correct ending for each prefix. Separation did alter transmission and connection state. For example, under P, resource-only separation increased total inhibitory transmission across the group's six stages from 7.076 to 18.798, without passing the prefix criterion. More transmission and separate records did not automatically preserve the required relational distinction.

**Scientific conclusion: this experiment rejects the hypothesis that the tested state separations alone restore prefix discrimination under either configuration.** The successful R51t11 research configuration used different inhibitory transmission and usage-record handling, and its evidence remains intact. The present result distinguishes separate storage and updating from that successful combination and narrows the next mechanism question.

## Performance and storage

The engineering benchmark used identical 32-node inputs and 60 internal seconds, a fresh process per condition, one warmup and five timed runs. The table reports medians; ranges, CPU time and working-set measurements are in the [numerical summary](summary.json). Timings include injection and advancement; snapshots were measured afterward. Conditions processed 1770–1772 internal events.

| Implementation or separation | Wall time, ms | Microseconds/event | Peak process commit, MiB | Snapshot, KiB |
| --- | ---: | ---: | ---: | ---: |
| Previous 6.2 binary | 159.22 | 89.90 | 29.25 | 603.58 |
| Shared | 166.48 | 94.00 | 29.68 | 603.86 |
| Resources only | 166.12 | 93.75 | 30.73 | 725.02 |
| Weights only | 187.21 | 105.77 | 29.68 | 642.98 |
| Weights and resources | 190.69 | 107.67 | 30.66 | 764.37 |
| Weights and learning records | 252.74 | 142.79 | 33.11 | 887.94 |
| All three | 248.62 | 140.38 | 34.73 | 1008.99 |

With all state shared, the new implementation was about 4.6% slower than the previous binary, with identical numerical state and 1771 events. Its snapshot added only 278 bytes of configuration. This measures the implementation overhead with separation disabled. Relative to the new shared condition, full separation was about 49.3% slower, also about 49.3% more expensive per event, with 67.1% larger snapshots and 17.0% higher peak process commit. Weight-only separation was about 12.4% slower; separate weights and learning records were about 51.8% slower. These measurements point to independent learning and decay updates as a higher-priority optimization target than switch checks alone.

Advancement and recording across the 72 scientific stages totaled 163.51 seconds. Total host time was 215.89 seconds, with 99.69 MiB peak private commit. The largest complete states under full separation were approximately 1.16 MiB in P and 0.91 MiB in S, compared with 0.79 MiB and 0.62 MiB when shared. No resource stop was triggered. The measurements cover these materials and the 32-node benchmark; large embodied networks require costs measured against their own activity.

**Recommendation for 6.3: do not enable separation by default on the expectation of prefix recovery.** Retain these options for specific further comparisons. If a later experiment demonstrates a benefit from a particular separation, prioritize redundant state projection, storage of separate records and removal of unnecessary configuration combinations. This batch changed no defaults and did not begin 6.3 optimization.

## Verification and evidence

Read-only verification covered 144 complete initial/final states, 48 processes and all parent-copy relations. Independent scoring had zero discrepancy. Before execution, all 12 configurations produced identical complete states under plain advancement, observation, restoration, partitioned advancement and host pauses. Two frozen shared-mode witnesses exactly matched the previous implementation; historical 6.1 implementation files were unchanged. Engineering validation passed 706 tests, including 17 standalone runtime checks; 11 isolated database integration checks were skipped because their test service was not configured.

Originals: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/separated-signals62-v1`. `analysis-final.json` contains detailed analysis; `audit-final.json` records verification; `frozen-source/` preserves execution-time sources. A subsequent standalone tmind interoperability test found missing optional fields in its decoder whitelist. That format-only issue was corrected and tested separately; the scientific native run and JSON states did not use that path. Frozen sources were retained and the repair separately recorded. Final engineering, build and installation information is in `engineering.json`; the complete research-API readback receipt is in `delivery.json`.

Protocols, conclusions and originals remain distinct. Historical experiments, reference subjects and manuscripts are unchanged; the main revalidation campaign remains paused. Verification and recomputation were performed within this task, not described as external replication.
