# R63a: Stimulus units, connection formation and retention in 6.3

15 November 2026. This rerun retains the two encoded material blocks, two configurations and 264 conditions of E17/R51d. New subjects use current 6.3 defaults. Cue, no-cue and retention measurements use declared research copies of the teaching reference; there are two independent material blocks. Historical subjects and originals remain unchanged.

## Purpose and expectations

The study tests how stimulus grouping, repetition, intensity and order affect connections and responses, and measures whether connections formed by weak one-off and repeated experience remain after 120 seconds. Connection formation and effects of experience and order were expected to replicate. Short-term deletion is a separate target: all weak connections survived this interval in 6.1, and the same criterion is retained here.

## Results and conclusions

| Target | Result | Conclusion |
|---|---|---|
| Grouping determines connection formation | All four material/configuration combinations meet the prediction. Fresh single-channel backgrounds leave the two original connections; paired backgrounds form 96 additional connections. Complete physical inputs form 6 and 60 connections, respectively; splitting them yields zero. No cross-connections to the original task nodes occur | The grouping rule replicates in 6.3 |
| Repeated experience strengthens connections | Total weight is zero without teaching, about 0.3283 after one strong stimulus and 0.9095 after ten repetitions, projected to the respective common endpoints | Repetition leaves stronger connections; the result replicates |
| Order matters at matched dose | All eight complete-versus-shuffled comparisons have positive sums of absolute weight differences, ranging from 0.13691 to 1.99879 | Input order changes the connections formed; the result replicates |
| Delete all weak connections within 120 seconds while retaining repeated connections | All 96 weak and both repeated connections survive in every combination; none of the four combinations meets the deletion target | The short-term deletion target remains unmet, as in 6.1 |

A separate maintenance channel delivered a stimulus every 0.5 seconds throughout retention. All four conditions reached 125.8 seconds of internal time. Weak-edge survival therefore reflects continued evolution. Final weak weights range from 0.010716 to 0.012598, above the deletion threshold of 0.008; repeated weights are approximately 0.154750–0.154814. Thresholds, teaching and waiting durations were not changed to alter this outcome.

The two equal-incident-dose conditions have total weights of 0.214807 and 0.319913 at 0.1 seconds. This also replicates the contribution of both stimulus intensity and channel amplitude under the current rules. Intensity, dose, repetition and resulting weight are recorded separately.

## Timely settlement and actual activity

The 264 input schedules are identical to those in 6.1. Final lifecycle labels change from active to dead in 74 conditions. After the corresponding 6.3 death time, the maximum actual node activation in the old recorded trajectories is zero. Activation is identical at every shared sample time. These label changes remove stale activity records; this batch shows no earlier termination of real activation in those comparisons.

Other process quantities were checked separately. Maximum shared-time differences in inhibition and associative activity are 8.67×10⁻¹⁹ and 6.94×10⁻¹⁸. The direct-activation history differs by up to 0.00235747. All 318 differing direct-history samples concern nodes already removed in 6.3 but still retained in 6.1; this quantity is identical where a node exists in both versions. The four recorded processes therefore cannot all be described as numerically identical. Original processes and differences remain available; subsequent temporal-readout experiments will test their effects on task performance.

Under the original convergence rule, both versions score 48/100, with exactly the same 48 successful conditions. Four untrained cart conditions in 6.3 end early when the individual dies; they are explicitly recorded as censored, not as converged.

The readout is passive and untrained. The 100 cued conditions retain activation, inhibition, direct and associative activity. Condition-level integrals, peaks and convergence results relative to the same-parent no-cue controls are provided in analysis.json. Original sampling and scoring are retained; a final brightest node does not replace the response process.

## Integrity, cost and implications

All 528 complete initial/final states, 180 parent–copy links and input schedules passed verification. Independent arithmetic projects stored base weights to their recorded internal endpoints; maximum disagreement with the native observed total is 1.85×10⁻¹³. Verification loads no advancing subject.

Recorded condition time totals 182.33 seconds; the guarded host ran for approximately 324.58 seconds. Peak private memory was 915.17 MiB. Before analysis, originals occupied 97.60 MiB logically and 101.39 MiB physically, within the 512 MiB originals budget. Minimum free E-drive space was approximately 58.75 GiB. Historical matched condition time was 274.38 seconds; host conditions differ, so this ratio is not a controlled speedup estimate. No marked slowdown occurred in this batch.

Current 6.3 retains the basic mechanisms through which grouping, repetition and order shape connections. Timely settlement did not rapidly delete all weak one-off connections in these materials; deletion still depends on actual weights and the applicable rules. Explicit dormancy was disabled, so dormant-edge lifetime remains a separate measurement question. No campaign-wide scientific stop was triggered. The connection-blocking study follows after complete research-API evidence verification.

Evidence in the separate stimulus-63-rerun-v1 directory includes frozen.json, cases.json, analysis.json, audit.json, arithmetic-verification.json, historical-comparison.json, resource-summary.json and publication/completion.json. The protocol-date and physical-allocation corrections are documented in [analysis provenance](analysis-provenance.en.md); original frozen text, states and scoring rules are preserved.
