# R51t13: usage records, inhibitory allocation and prefix discrimination in 6.3

Registered before computation on 15 November 2026. The author authorized a usage-time switch in 6.2, a separate 6.3 without the excitation/inhibition separation options, and comparison of inhibitory allocation. Broad revalidation remains paused.

## Questions and expectations

We test whether the actual 6.3 defaults restore prefix discrimination, whether preventing inhibitory transmission from updating connection usage time is sufficient, and whether distributing a fixed inhibitory amount in proportion to connection weights offers a better default than current per-connection transmission. A beneficial result must restore both swapped teaching blocks without material losses in sustained activity, selectivity or computational cost.

The earlier R51t11 success (2/2) applied to a complete combination: stability-based retention, immediate novelty, a higher activation threshold, checking before resource release, proportional inhibition, bypassing resources for inhibition, disabling explicit inhibitory learning and its connection threshold, and no inhibitory usage-time updates. The present production 6.3 retains resources and inhibitory learning. Its performance must be measured independently.

## Conditions and stages

Profile P uses 6.3 default dynamics: single-age inverse-logarithmic decay, arrival-window novelty and activation/inhibition connection thresholds of 0.0004. Profile S uses the previously registered stability-based retention, immediate novelty and an activation connection threshold of 0.004. Both enable resource prechecking, local subthreshold expiry, depletion and weight reinforcement by both signal types; facilitation is zero. The inhibitory connection threshold remains 0.0004 and node emission thresholds remain 0.004/0.002. P versus S is a comparison of complete configurations, not a single-factor ablation.

For each profile, cross per-connection versus weight-proportional inhibition with usage updates on/off, giving eight conditions. Each receives two anonymous teaching blocks with exchanged endings, continuously for 212.2 internal seconds. Preserve each complete trained parent and create separate AB and DB diagnostic copies. Cue separation is one second; observe for 15 seconds at 10-ms intervals (1502 points), including activation, inhibition, direct and associative activity. This gives 48 stages. There are two material blocks; copies do not add independent samples.

With usage updates off, also compare the two profiles and allocations after 81.2 seconds of paired teaching, 300 seconds with frozen background replay, and a 15-second observation without a target cue: another 24 stages. Unlike the historical resource-011 material, these new subjects use resource-101 from birth (depletion enabled, facilitation zero), matching the prefix configurations. This change is explicit; it is not a direct replication of the old 011 condition. Stages retain complete state continuously.

Weight-proportional allocation divides the source's inhibitory amount among awake, unsilenced outgoing connections according to effective weights. Distance, resource release and thresholds still apply afterwards. Failed shares are not redistributed; a zero weight sum sends nothing. Source energy cost follows the allocated total; per-connection transmission retains its existing cost. Both keep successful inhibitory reinforcement. The usage switch controls only last_pass_us, not explicit learning or last_touch_us.

## Registered criteria and decisions

Keep the historical prefix criterion: after the shared B cue, the correct ending's peak activation must exceed the alternative by more than 1e-6. Both AB and DB must pass in each block, and both blocks must pass for recovery. Default recovery specifically means P, per-connection transmission and usage updates off.

If any condition passes, select by this fixed order: P before S, usage updates off before on, then per-connection before proportional allocation. Do not select by observed margin. Validate that condition and the other allocation with otherwise identical settings on two new encodings and seeds, adding 12 stages. XOR masks are 0x02000000/0x01000000; seeds are 9291251/9291252. If all conditions fail, stop without a parameter search.

For sustained activity, report the full waiting trace and whether the largest activation among target nodes stays above 1e-6 throughout the final 15 seconds. Also report the fraction of node samples at activation >=0.95. Longer activity cannot substitute for correct discrimination. Recommend changing the allocation default only if proportional allocation restores both old and new materials under P while per-connection does not, sustained-activity passes do not decrease, saturation rises by no more than five percentage points, and median scientific-stage CPU cost is at most twice the reference. Otherwise retain the current default and report gains and losses explicitly. Success under S supports that combination only. This study does not automatically change defaults.

An engineering benchmark uses identical 32-node, 60-second input, one warmup and five scored repeats per condition. Compare the previous 6.2 binary, new 6.2 with old usage behavior explicitly enabled, and matching 6.3; require identical numerical state and event counts before attributing timing changes to implementation. Report time, process memory and snapshot size. New-default and proportional dynamics are measured separately with actual event counts.

## Integrity, budget and delivery

These are passive mechanism measurements without trainable peripherals. Preserve full state, random state and event ordering; inputs contain no answer labels. Independent apparatus codes test observation, save/restore, partitioned advancement and wall-clock pauses for identical complete states. Register and freeze code, native binary, configuration, materials and tools before formal runs.

Maximum 84 stages, 512 MiB of originals and 2 GiB total including archive/readback, one scientific host and a two-hour wall limit. A stage exceeding 300 seconds requests a pause at its complete boundary. Every second, retain 5/4/5/25 GiB of commit/RAM/C/E headroom. Preserve and stop on a new incomplete state, resource breach, invalid original or observation disturbance. Do not delete originals, lower thresholds or change dynamics during the run.

Independently recompute scores and verify state chains. Deliver bilingual purpose, expectation, result, analysis, scientific conclusion and implications. Close only after full original-package readback through the research API with pending=0. Update the backlog, bilingual history and both Classical Chinese adaptations; commit locally without pushing. Historical data, criteria, versions and author manuscripts remain intact.
