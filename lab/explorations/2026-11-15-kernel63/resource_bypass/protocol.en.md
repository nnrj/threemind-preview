# R51t16: inhibitory resource bypass, performance, and behavior

Preregistered on 15 November 2026. The user authorized an inhibitory resource-bypass option in 6.3, enabled by default, and retention of optional independent resources only if keeping the disabled option causes no substantial performance loss. This batch also tests prefix discrimination and sustained activity after 300 seconds. The broad revalidation and manuscript remain paused.

## Implementation

With `inhibition_bypasses_resources=true`, inhibitory transmission neither releases nor consumes synaptic resources and is not multiplied by the resource release fraction. Excitation retains its existing resource rules. Bypass takes precedence over `separate_inhibition_resources`; an existing independent inhibitory resource state is preserved but not used while bypass is enabled. Allocation, energy, thresholds, and learning follow their separate settings. Only the new bypass birth default changes. Other parameters in the previously successful prefix configuration are not made defaults.

Implement the option in Python, Rust, and the standalone runtime. Earlier 6.3 snapshots lacking the field restore with false. Preserve 6.1/6.2. Engineering checks cover old snapshots, single-signal resource expenditure, learning, both backends, restoration, reconfiguration, and observation invariance.

## Performance decision

Compare the current optimized Rust build with independent resources disabled against the pre-option 6.3 implementation at b7adf1b5 with the identical bypass rule added. The latter is an isolated engineering reference. Verify identical numerical states and event counts; account for configuration metadata separately.

Use fixed courses with 32 and 128 nodes, both inhibitory allocation modes, and bypass on/off. Warm up, then alternate builds for five measurements each. A median elapsed-time increase exceeding 20% triggers five further alternating measurements. A repeated increase above 20% requires removal of the independent-resource option; otherwise retain it, default off. Report CPU time, peak memory, and snapshot size. Control inputs, internal duration, and compiler optimization. Host interference calls for a corrected measurement, not a dynamics change.

## Scientific conditions

Six conditions cross bypass on/off with three complete profiles, each tested on two exchanged teaching blocks. Use the same configuration for both tasks:

| Profile | Retention, novelty, inhibitory allocation | Inhibitory learning | Resources |
| --- | --- | --- | --- |
| P | Actual 6.3 defaults: adaptive half-life, arrival-window novelty, per-connection inhibition | On | Depletion on, facilitation off |
| S101 | Stability retention, immediate novelty, weight-proportional allocation | Off | Depletion on, facilitation off |
| S011 | As S101 | Off | Depletion off, facilitation time constant 1 second |

In all conditions inhibition does not update last-use time, independent resources are off, and the pre-release check is on. Other P settings are actual defaults. S uses excitatory/inhibitory connection thresholds of 0.004/0.0004 and node sender thresholds of 0.004/0.002. S101 with bypass is the previously replicated positive prefix reference. S011 tests another resource condition. Successes from different profiles will not be combined into a claim of simultaneous success.

For prefixes, retain continuous 212.2-second teaching and save the complete parent before creating declared AB and DB diagnostic copies. Give A or D, then the common B after 1 second, and observe for 15 seconds. The second block exchanges endings. The correct ending's post-B activation peak must exceed the competing ending's peak by more than 1e-6. Both prefixes must pass within a block, and both blocks must pass to establish recovery. These are the historical criteria.

For sustained activity, retain continuous 81.2-second teaching, a continuous 300-second wait with the original 300 background inputs, then a 15-second observation. Carry all state across these stages. Record task-node activation, inhibition, direct activity, and associative activity every 10 ms, including the initial point, for 1502 samples. Each sample must contain at least one task node above 1e-6 activation. Report each block, activation range, saturation fraction, and actual transmission. The `active` label is not the endpoint. This background condition is not described as 300 seconds without external input.

Each condition has six prefix stages and six sustained-activity stages: 72 total. Teaching blocks are the statistical units; copies and samples are nested. Use passive temporal observation, without training a peripheral. Preserve teaching, repetition, spacing, background, dose, and windows. P-on measures the new default; paired off conditions measure the bypass effect; S101 tests transfer of the earlier success into the production backends; S011 tests the alternate resource condition. Report negatives without additional tuning.

## Integrity, limits, delivery

Freeze sources, binaries, configurations, and inputs before registered scientific execution. Check invariance under observation, saving/restoration, partitioned advancement, and wall-clock pauses. Preserve complete nodes, edges, resources, events, and random state. There are no learned peripherals in this batch.

Originals are capped at 512 MiB; total scientific delivery budget is 2 GiB, with a separate 3 GiB engineering-build budget. Scientific host execution is capped at two hours; stop at a complete boundary if a stage exceeds 300 seconds. Check commit headroom/RAM/C/E every second, retaining 5/4/5/25 GiB. Preserve and stop on invalid originals, observer perturbation, resource shortage, or a dead host with an in-flight marker. Do not roll back or clear that marker. Investigate an unreproduced positive reference without changing its criterion.

Independently verify state chains, configurations, inputs, scores, and hashes. Compare S101-on prefix margins with R51t15 within absolute tolerance 1e-12. Deliver bilingual reports and recomputable originals, verify complete API readback and pending=0, and update research backlog and bilingual histories, with both Classical Chinese adaptations for a major phase. Commit locally only.
