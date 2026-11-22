# R51t13: 6.3 is implemented; usage records and inhibitory allocation did not restore prefix discrimination

15 November 2026. Research record: `fd63e416-7e13-5833-ad74-e8681525323b`.

**Conclusion: the new switch in 6.2 and 6.3 is implemented, and 6.3 removes all excitation/inhibition state-separation options. Prefix discrimination has not recovered.** Under both registered configurations, every combination of inhibitory allocation and usage updates passed 0/2 teaching blocks. Proportional allocation produced no prefix or sustained-activity benefit and was about 46% slower in the 32-node benchmark. We recommend retaining per-connection transmission as the 6.3 default and keeping proportional allocation optional.

## Implementation

The new `inhibition_updates_usage` setting defaults to false for new 6.2 individuals. Successful inhibition no longer refreshes the connection's last transmission time, `last_pass_us`; excitation still does. This does not disable inhibitory learning, inhibitory weight reinforcement or its `last_touch_us` learning record. Earlier 6.2 artifacts lacking the field restore with true, preserving their behavior.

6.3 has its own Python and Rust transition implementations and version identity, based on 6.2 before state separation was introduced. It removes separate weights, resources and learning records, together with the master separation switch, while preserving the other authorized mechanisms. Matched shared-state configurations have identical numerical states and events. Generic mathematical, resource, event and storage components remain shared.

6.3 also defaults to no inhibitory usage updates and retains per-connection transmission. Its optional proportional rule divides the source's inhibitory amount among awake, unsilenced outgoing connections according to effective weights, then applies distance, resources and thresholds. Failed shares are not redistributed. Both modes retain inhibitory learning. API/configuration fields, snapshots, inheritance and the standalone Rust command support 6.3. The global creation default remains 6.1.

## Purpose and methods

The author requested a test of whether removing inhibitory usage updates restores prefix discrimination and whether proportional allocation is a better default. Earlier R51t11 recovery (2/2) belonged to a complete combination including stability-based retention, immediate novelty, a higher activation threshold, proportional allocation, inhibition bypassing resources, disabled explicit inhibitory learning and connection threshold, and no inhibitory usage updates. This study tests the requested changes in production 6.3 with resources and learning retained. The earlier score cannot be assigned to the new defaults without measurement.

The registered expectation was that both prefixes would evoke their respective correct endings if these changes were sufficient. Profile P uses default 6.3 inverse-logarithmic decay, arrival-window novelty and a 0.0004 connection signal threshold. S uses stability-based retention, immediate novelty and a 0.004 activation connection threshold. Within each profile, compare both allocations with usage updates off/on: eight conditions.

Each condition receives two teaching blocks with exchanged endings for 212.2 continuous internal seconds. Preserve each complete trained parent and create AB/DB diagnostic copies. Observe 15 seconds at 10-ms intervals, giving 1502 points. After the common B cue, the correct ending's peak must exceed the alternative by more than 1e-6. Both cues must pass per block, and both blocks must pass for recovery. Blocks are the statistical units; stages and copies are nested observations.

A separate comparison with usage updates off uses 81.2 seconds of paired teaching, 300 seconds of frozen background replay, and 15 seconds of observation without a target cue. All new subjects use resource-101 from birth (depletion enabled, facilitation zero), matching the prefix conditions. This is explicitly different from the historical resource-011 condition that sustained activity. Observation injects no stimuli.

## Results and scientific conclusion

Here u0 means no inhibitory usage updates and u1 means updates enabled. Margins are AB/DB values for block 0; block 1 exchanges the correct endings and has the same corresponding margins.

| Profile | Allocation and usage | Blocks passed | AB margin | DB margin |
| --- | --- | ---: | ---: | ---: |
| P | per-connection-u0 | 0/2 | -0.000133286 | 0.000133321 |
| P | per-connection-u1 | 0/2 | -0.000133286 | 0.000133321 |
| P | weight-proportional-u0 | 0/2 | -0.000136852 | 0.000136902 |
| P | weight-proportional-u1 | 0/2 | -0.000136852 | 0.000136902 |
| S | per-connection-u0 | 0/2 | 0.001559534 | -0.001559515 |
| S | per-connection-u1 | 0/2 | 0.001558728 | -0.001558713 |
| S | weight-proportional-u0 | 0/2 | 0.001663111 | -0.001663101 |
| S | weight-proportional-u1 | 0/2 | 0.001915794 | -0.001915788 |

All 32 prefix records were complete. Every condition retained a preference for one ending instead of selecting the correct ending for each prefix. The usage switch did not change this metric under P. Under S it changed margins, but not pass counts. Proportional allocation also changed response values without recovering discrimination.

Each of the four sustained-activity conditions passed 0/2: target-node activation was zero throughout the 15-second observation after the 300-second wait. This describes the target nodes under resource-101; background channels still received input, so it is not a finding of whole-system death. Saturation was zero in all 40 diagnostic processes. All 72 stages completed without a resource stop or incomplete state. No condition qualified for the preregistered fresh-encoding follow-up.

**The experiment rejects the expectation that, under these configurations, removing inhibitory usage updates alone or combining it with proportional allocation is sufficient to restore prefix discrimination.** Missing measurements do not explain the result: complete processes and states were verified. For ThreeMind, the required prefix ability remains an unresolved weakness of the current defaults. The switch provides a controlled comparison, not a solution by itself. The earlier successful combination remains informative because it supplies an achieved configuration to investigate. No extra condition was added to overturn that success, and the parameter search was not expanded.

## Performance and default recommendation

The benchmark uses identical 32-node input for 60 internal seconds, a fresh process per condition, one warmup and five scored repetitions. The first three rows have identical numerical states and 1771 events after excluding version identity, definitions and equivalent configuration fields. They therefore measure implementation costs. The last two rows apply the new defaults or allocation dynamics; their actual events and states are reported separately. Memory is peak commit for the whole measurement process.

| Implementation | Median wall ms | μs/event | Peak commit MiB | Snapshot KiB | Events |
| --- | ---: | ---: | ---: | ---: | ---: |
| Previous 6.2, shared | 164.57 | 92.93 | 30.18 | 603.85 | 1771 |
| New 6.2, old usage behavior | 165.32 | 93.35 | 30.36 | 603.91 | 1771 |
| 6.3, matched configuration | 156.43 | 88.33 | 29.74 | 603.73 | 1771 |
| 6.3 defaults | 156.60 | 88.42 | 29.59 | 603.73 | 1771 |
| 6.3, proportional allocation | 228.70 | 129.28 | 30.14 | 603.72 | 1769 |

Removing the separation implementation made matched 6.3 about 5.4% faster than new 6.2 and 5.0% faster than the previous 6.2 binary. This supports the simplification, with a modest measured gain. Shared mode already omitted separate inhibitory state, so snapshots shrink by only 186 configuration bytes rather than a large fraction of network storage.

Proportional allocation was about 46.0% slower than default 6.3, with 1769 rather than 1771 events and a correspondingly higher per-event cost. It adds a pass to sum eligible effective weights before transmission. Recording occupied more of the smaller scientific workloads, whose median stage CPU times did not show the same increase; detailed measurements are retained. These workloads must not be combined into a single performance ratio.

**Recommendation: retain per-connection transmission as the default.** This batch found no capability benefit from proportional allocation, while measuring added cost. Keep it optional for a specific further comparison. The author's requested default of no inhibitory usage updates is implemented; this negative result was not used to silently revert it or disable inhibitory learning.

## Verification and delivery

All eight conditions produced identical complete states under direct advancement, observation, save/restore, partitioned advancement and wall-clock pauses on independent apparatus codes. Read-only verification covered 144 formal initial/final states, parent-copy relationships and 40 processes, with zero independent scoring discrepancy. Engineering checks passed 631 cases with seven conditional skips; preliminary subset reruns are not counted again. They cover Python/Rust parity, historical artifacts, independent runtime interoperability for both allocations, version routing and configuration fields. The native wheel is installed in the project environment; existing services were not restarted. Thirteen checked historical 6.0/6.1 implementation files have unchanged hashes.

Scientific advancement and recording totaled 170.54 seconds; total host time was 219.41 seconds, with peak private commit of 98.51 MiB. Originals occupied about 61.68 MiB at audit, within the 512-MiB original and 2-GiB total budgets. Originals are at `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/inhibition63-v1`; execution-time sources are preserved in `frozen-source/`. Protocols, analyses and reports remain separate. Historical evidence and author manuscripts are unchanged, and broad revalidation remains paused.

[Preregistered protocol](protocol.en.md) · [Numerical summary](summary.json) · [Performance measurements](performance.json) · [Engineering checks](engineering.json) · [Research API receipt](delivery.json)
