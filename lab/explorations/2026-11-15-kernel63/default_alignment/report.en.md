# Aligning 6.3 defaults with 6.1 and verifying compatibility

2026-11-15. This report documents an authorized change to defaults and its engineering verification. **6.3 now uses the 6.1 resource-release order, inhibitory transmission-time updates, and shared-resource behavior, while retaining local expiry of subthreshold activation.** Python, native Rust, the standalone Rust runtime, and the API configuration catalogue have been synchronized.

## Purpose, author decisions, and delivered settings

The author requested fewer differences between the 6.3 and 6.1 defaults, making the resource-precheck decision conditional on performance. The initial request disabled local subthreshold expiry. After learning that 6.1 already zeros activation below `activation_floor`, the author explicitly chose to keep expiry enabled. The final settings are:

| Setting | 6.3 default before this task | Delivered default | Effect |
| --- | --- | --- | --- |
| Resource precheck | On | **Off** | Use the 6.1 order: release synaptic resources, then check the transmitted amount |
| Local subthreshold expiry | On | **On** | Schedule local settlement of positive activation below the existing zeroing floor, updating the active set and the start of quiescence |
| Inhibition updates last transmission time | Off | **On** | Successful inhibitory transmission updates `last_pass_us`, as in 6.1 |
| Inhibition bypasses resource limits | On | **Off** | Inhibition uses synaptic resources, as in 6.1 |
| Independent excitatory/inhibitory resources | Off | **Off** | Shared resources remain the default; independent resources remain optional |

The corresponding fields are `resource_precheck_enabled=False`, `subthreshold_expiry_enabled=True`, `inhibition_updates_usage=True`, `inhibition_bypasses_resources=False`, and `separate_inhibition_resources=False`. All existing switches remain. Node emission thresholds also remain: 0.004 for activation and 0.002 for inhibition. These act at a different stage from the connection resource precheck.

This task changes three defaults and their interface descriptions. It does not rewrite transmission, decay, learning, or death formulas. The application's default kernel remains 6.1. Saved 6.3 individuals restore their own configuration; compatibility rules for missing historical fields are unchanged.

## Why the resource precheck is disabled by default

The preregistered decision required at least a 20% reduction in the geometric mean of execution times across four materials, with no material slowing by more than 20%, followed by independent confirmation. Materials used 32 or 128 nodes, sparse or dense initial connections, fixed inputs, and 60 internal seconds. Each condition had one warmup and five alternating measurements. Advancement, serialization, memory, and file size were recorded separately.

The first comparison disabled expiry for compatibility with 6.1. Prechecking reduced the geometric mean of advancement time by 7.63%. After the author chose to retain expiry, the same comparison was repeated under the final expiry setting. The second comparison gave these medians:

| Initial material | 6.1 advancement, seconds | Final 6.3 defaults, seconds | 6.3 with precheck, seconds | Time reduction from precheck |
| --- | ---: | ---: | ---: | ---: |
| 32 nodes, sparse | 0.042787 | 0.044502 | 0.041667 | 6.37% |
| 32 nodes, dense | 0.171519 | 0.178620 | 0.159637 | 10.63% |
| 128 nodes, sparse | 0.045456 | 0.044646 | 0.041607 | 6.81% |
| 128 nodes, dense | 0.916164 | 0.981186 | 0.885917 | 9.71% |

**Under the final expiry setting, prechecking reduced the geometric mean of time by 8.40%, below the 20% decision threshold. It is therefore disabled by default and remains available as an option.** This measures the operating cost of two resource rules. Those rules affect release and subsequent events, so the entire difference cannot be attributed to implementation optimization.

Final 6.3 defaults changed execution time relative to 6.1 by −1.78% to +7.10%, peak commit by 0 to +0.84%, and snapshot size by −0.02% to +0.64%. Serialization times are listed separately in the [summary](summary.json). No large slowdown occurred in these materials. With expiry disabled, all 24 paired 6.1/6.3 final numerical states were identical; advancement time changed by −0.32% to +1.91%, and snapshots consistently added 1059 bytes of version and configuration metadata.

The two serial benchmark runs used 144 worker executions, including warmups. Minimum available commit, physical RAM, C-drive space, and E-drive space were 14.00, 12.69, 9.34, and 58.86 GiB, satisfying the registered reserves. These measurements characterize small engineering materials; larger tasks still require their own budgets.

## What still differs from 6.1

All 128 configuration fields shared with 6.1 have identical default values. Additional 6.3 options remain available: stability-based retention and its controls, separate connection thresholds for the two signals, separate weight-reinforcement controls, resource prechecking, inhibitory usage records, independent resources, inhibitory resource bypass, and weight-proportional inhibition. This task removes none of them.

**One behavioral difference remains in the actual defaults: local settlement of subthreshold activation.** The 6.1 projection rule already zeros activation below `activation_floor=0.004`. Some weak inputs, however, schedule no subsequent settlement, leaving the active set and `life` marker stale. With expiry enabled, 6.3 settles such activity at the next internal microsecond and then applies the original one-second quiet period.

A single-node engineering input of 0.0001 demonstrates the difference. Observed activation becomes zero in both versions. At 300 seconds, 6.1 still reports `active`; 6.3 becomes `dead` at 1.000001 internal seconds under the original quiet-period rule. The `life` field describes the whole individual; node deletion follows separate structural rules. A control with activation decay disabled and activity above the existing floor remains active at 300 seconds, confirming that this activity is not forcibly expired.

The final defaults therefore should not be described as state-for-state identical to 6.1. The fix can affect death time and whether later inputs are accepted. Explicitly setting `subthreshold_expiry_enabled=False`, with all other delivered defaults retained, selects the 6.1-compatible configuration. Four input materials—grouped, weak, simultaneous accumulation, and ordered—passed all 72 complete numerical comparisons across two backends and nine internal-time boundaries. Event queues, activity, and counters were included. Observation leaves state unchanged, and restoration at every boundary preserves subsequent evolution.

## Historical versions, saved individuals, and delivery

Before changing defaults, five old 6.3 configurations were captured before and after advancement, giving ten complete engineering witnesses. Both backends restore the initial states and reproduce their subsequent states. The standalone Rust runtime additionally verifies JSON and TMIND restoration. Hashes of 19 implementation files for 6.0, 6.1, and 6.2 are unchanged.

Cross-backend floating-point comparisons retain the existing tolerances: relative 3×10⁻¹² and absolute 3×10⁻¹⁴. Structures, markers, ordering, and integer counters must match exactly. The 24 native benchmark pairs instead compare SHA256 hashes of normalized states and require exact equality.

The first regression run passed 591 tests and skipped five because a standalone runtime had not been specified. The post-build run passed 65, including those five and the new standalone checks. Across both runs, 654 distinct tests passed. Two database integration checks were skipped because the isolated test database was not running; no service was started for them. The rebuilt native module is installed in the project environment, and the standalone runtime has been built. Existing services were not restarted.

The engineering objective is complete: restore the three authorized defaults, retain the author's final expiry decision, verify historical restoration and performance, and identify the remaining difference. Historical prefix and sustained-activity experiments, criteria, and results remain intact. This task runs no new cognitive experiment or replacement scoring. Broad revalidation remain paused under the previous decision. [Public edition: manuscript editing or private locator omitted.]

Evidence: [protocol](protocol.en.md), [benchmark](benchmark.py), [independent arithmetic check](summarize.py), [small summary](summary.json), and [regression checks](../../../../tests_v2/test_local63_default_alignment.py). Complete engineering originals and test XML remain in ignored `.work/kernel63-default-alignment/`; the summary records their hashes and delivered binary hashes. Complete states are excluded from Git. This is engineering verification and has no new scientific API experiment record.
