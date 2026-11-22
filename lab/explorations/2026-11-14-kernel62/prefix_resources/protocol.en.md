# R51t9: Synaptic resources, emission thresholds, and prefix discrimination

Preregistered on 15 November 2026. The author asks whether lower thresholds or more available synaptic resources can restore prefix discrimination while retaining resource release before the signal-amount check. A subsequent comment adds node emission thresholds and weak-activity tails. Production 6.2, defaults, historical originals, manuscripts, and the paused replication program remain unchanged.

## Questions and completion criteria

Prefix discrimination means that the same B cue favors different taught endings depending on whether A or D preceded it. Block 0 teaches A→B→C and D→B→E; block 1 exchanges C/E. Both prefixes must favor their correct endings. Amplifying one ending for both prefixes does not meet this target.

1. Can reducing the post-release connection threshold, accelerating resource recovery, or combining them restore both prefixes in both blocks without a pre-release screen? A successful configuration establishes this possibility. If all specified conditions fail, the claim that these changes suffice within this tested range is rejected.
2. Do node excitation/inhibition emission thresholds independently affect recovery and cost? Node thresholds schedule emissions; connection thresholds reject signal amounts after resource release. They are separate factors.
3. Does the outcome apply under stability retention with immediate novelty, used in R51t7/R51t8, and under the current 6.2 defaults of inverse-logarithmic decay and arrival-window novelty? Report the two configurations separately.
4. After teaching, what activity and computational cost remain during a 300-second period without further stimuli? Activity at the end of this finite window does not establish indefinite persistence.

A competing explanation concerns the distribution of inhibition among connections. If every current-route configuration fails, run the three specified isolated historical-inhibition controls. This is a bounded conditional comparison, not an open parameter search.

## Subjects, materials, and branches

Reuse the two exchanged-curriculum blocks, anonymous codes, intensities, timing, background, and 212.2-second continuous teaching schedule verified in R51t7. Each configuration starts as a new complete individual. Preserve full initial/final states, inputs, clock, queues, random state, nodes, and connections. The apparatus consists of the Core, declared stimulus replay, and passive process measurement; it has no learned reader, body, or actuator. Adding adapter fitting or corrective teaching would change this mechanism question and is not part of this batch.

Preserve the complete trained parent at 212.2 seconds and create separate declared AB and DB diagnostic copies. Each waits one second, receives its first cue, receives B one second later, and is observed for 15 seconds. Local learning remains enabled as in the reference protocol. Internal time is continuous within each copy. Additional tail copies receive no further input and retain all internal state. These are declared causal diagnostic branches, not ordinary exams reset per question or additional independent samples.

The two blocks are developmental diagnostic materials. Configurations, prompts, and saved states do not increase independent N. Do not call this independent confirmation with new materials. Copy and hash-check four archived reference conditions without rerunning or modifying originals.

## Frozen conditions

The complete configuration table in `study_resources.py` is frozen with the protocol. Every new condition has pre-release screening disabled and retains fixed-function addressing, inhibition, and weight reinforcement by both successfully transmitted signal types.

| Factor | Conditions |
| --- | --- |
| Retention and novelty | Stability retention with immediate novelty; default inverse-logarithmic decay with arrival-window novelty |
| Connection signal threshold | 0.0004, 0.00004, or 0, shared by excitation and inhibition; individual overrides remain unset |
| Resource availability | Recovery time constant 0.8 s, accelerated recovery at 0.08 s, or depletion disabled as a continuously replenished upper-bound control |
| Node emission thresholds | Default excitation 0.004 and inhibition 0.002; specified single-threshold and paired zero-threshold controls |

For each retention configuration, run the 3×3 connection-threshold/resource matrix. Of 18 configurations, two archived baselines are reused, leaving 16 new configurations. Under stability retention, additionally set both node thresholds to zero at connection thresholds 0.0004/0 and recovery constants 0.8/0.08 s: four configurations. Under default retention, do so at connection threshold 0 and recovery constants 0.8/0.08 s: two configurations. Under stability retention, connection threshold 0 and recovery 0.8 s, separately zero only the excitatory or inhibitory node threshold: two configurations. Total: 24 new configurations and 144 stages.

Resource capacity is normalized to one in this implementation. Increasing availability therefore means faster replenishment, without inventing a larger pool parameter. Disabling depletion retains utilization 0.5 and a released fraction of 0.5; it does not disable the entire synaptic-resource operator or retain ordinary depletion. The 0.08-s value is a bounded tenfold exploratory change, not a proposed biological optimum.

The node activation zero-clamp `activation_floor=0.004` remains unchanged, as does `propagation_activation_min=0`; the historical inhibitory offered-amount gate remains disabled. Zero node emission thresholds therefore do not remove every weak-activity cutoff. The connection-weight gate remains disabled. Full configurations are saved in all states.

If no modern-route condition restores discrimination, add three isolated historical-inhibition conditions: connection threshold 0 with recovery 0.8 s; threshold 0.0004 with recovery 0.08 s; threshold 0 with recovery 0.08 s. Excitation retains release before checking. Historical inhibition distributes signals by adjacent weights, does not use these connection resources, and retains its own threshold rather than inheriting the common connection threshold. Explicitly report this difference. Reuse its archived low-threshold baseline. Maximum: 18 additional stages.

Tail observations use a fixed selection independent of scores: both retention configurations, each at its original baseline and at connection threshold 0, both node thresholds 0, recovery 0.08 s; two blocks each, eight copies. Observe at 0, 1, 5, 10, 30, 60, 120, and 300 s. Native death under the existing rule is a recorded terminal outcome.

## Measurements and interpretation

Keep the original primary criterion: after B arrives, correct-ending activation peak minus other-ending peak must exceed 10⁻⁶. Both AB and DB must pass in each block, and both blocks must pass for recovery. Do not change windows, materials, or denominators after seeing results.

Record activation, inhibition, direct activation, and associative activation every 10 ms; report peak, integral, and final values separately. During teaching, record task nodes, connection weights, resources, fast states, and cumulative transmission every 100 ms. Also report maximum activation, ending selectivity, threshold-rejected and transmitted amounts, elapsed time, peak private memory, and evidence size. Overall signal amplification is distinct from discrimination.

Project cached resource states to a common internal time before comparing availability. Report each block's factorial differences without treating two materials as a population significance test. Resource interventions change propagation, inhibition, and subsequent learning together; causal claims apply to the declared intervention. The more specific claim that weight gains are canceled by resource depletion remains to be tested.

Validate Python/Rust agreement on separate-code five-second apparatus materials. Observation, save/restore, host pause, and alternative advancement partitions must preserve full state. Use installed native 6.2 for formal stages and the existing isolated research implementation only for conditional historical inhibition. Independently recalculate scores and verify full states and branch ancestry without advancing scientific subjects.

## Resources, stops, and delivery

Initial free commit/RAM/C/E was approximately 14.75/12.92/8.82/61.89 GiB and must be read live before execution. Freeze an original-evidence cap of 1 GiB and total added peak of 4 GiB including archive and complete API readback. Reserve commit/RAM/C/E at 5/4/5/25 GiB. Check every second and pause only at complete stages. Limit a host to two hours, a stage to 300 s, and private memory to 1 GiB. Do not rerun complete stages, remove orphaned in-flight markers, or lower safeguards.

Pause for invalid apparatus, leakage, failed file verification, or undeclared state changes. Valid negative outcomes close normally. Prefix recovery and tail costs have separate conclusions; new tail concerns do not retroactively veto the prefix criterion. Deliver bilingual reports, complete API archive readback with zero pending requests, synchronized backlog/history, and a local Git commit only.

## Biological motivation

Tsodyks and Markram identified release utilization and resource recovery as determinants of short-term depression, motivating their separation as experimental factors here. [PNAS 1997](https://pmc.ncbi.nlm.nih.gov/articles/PMC19580/). Their study does not establish a biological implementation of ThreeMind's node threshold, connection hard cutoff, or pre-release check. This batch first tests their measurable computational effects.
