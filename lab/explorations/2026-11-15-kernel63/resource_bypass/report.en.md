# R51t16: implementing and testing inhibitory resource bypass in 6.3

15 November 2026. This batch implemented the requested switch and default, assessed the cost of retaining optional independent resources, and completed 72 stages testing prefix discrimination and sustained activity. Scientific execution used the production 6.3 Rust implementation, with the Python reference implementation used for parity checks. Historical reports, originals, and implementations 6.0–6.2 were preserved.

## Conclusions

**6.3 now supports inhibitory resource bypass, enabled by default for newly created 6.3 individuals. Independent resources remain optional and default off: retaining the disabled option changed elapsed time by −0.3% to +2.5%, without substantial degradation.**

**The previously successful complete configuration recovered prefix discrimination in production 6.3: both teaching blocks passed, and the scores exactly matched R51t15. Another resource configuration retained actual activity after 300 seconds. No tested configuration passed both endpoints; actual new defaults passed 0/2 on each.**

These conclusions answer separate questions. The production implementation reproduces the earlier success. Behaviorally, prefix discrimination and sustained activity depend on different complete configurations; adding bypass alone did not give the new defaults both capabilities.

## Purpose, expectations, and design

The user requested a default-on bypass switch, a performance decision concerning optional independent resources, and checks of prefixes and 300-second activity. Before execution, we specified that a greater-than-20% elapsed-time increase for identical inputs and numerical states, confirmed by repeated measurement, would require removal of the independent-resource option. Otherwise it would remain, default off. The positive prefix reference was expected to reproduce R51t15. Other outcomes would be reported without further parameter search.

Three complete profiles were crossed with bypass on/off, yielding six conditions, each using two blocks with exchanged endings. Each prefix individual underwent continuous teaching for 212.2 internal seconds. The complete teaching parent was saved before declared AB and DB diagnostic copies were created. A or D preceded the common B by 1 second, followed by 15 seconds of observation. The correct ending's post-B activation peak had to exceed the other ending's peak by more than 1e-6. Both prefixes had to pass for a teaching block to pass.

The sustained-activity task comprised continuous 81.2-second teaching, a 300-second wait retaining the original 300 background inputs, and 15 seconds of observation. Complete state continued across stages. Every one of the 1502 observation samples had to contain a task node above 1e-6 activation. Actual activation, rather than the life-status label, determined the result. The two teaching blocks were the statistical units; copies and samples were nested observations.

Both tasks were run under each identical configuration. Passive temporal observation recorded activation, inhibition, direct activity, and associative activity; no readout was trained. Sources, configurations, inputs, and criteria were frozen and registered through the research API before scientific execution. The [protocol](protocol.en.md) and [complete configurations](configurations.json) preserve the parameters.

## Switch semantics

`inhibition_bypasses_resources` defaults to `true`. When enabled, inhibition neither releases nor consumes synaptic resources and is not multiplied by the release fraction. Excitation retains its resource rule. Inhibitory allocation, energy cost, sender and connection thresholds, and learning remain governed by their respective settings.

`separate_inhibition_resources` remains optional and defaults to `false`. Bypass takes precedence. If both options are enabled, an existing inhibitory resource state remains saved but unused. Disabling bypass restores the selected shared or independent release/recovery rule. Resource separation is chosen at birth; bypass may be changed through the existing explicit reconfiguration interface.

Python, native Rust, standalone Rust, JSON/TMIND persistence, and the configuration catalogue support the change. Earlier 6.3 snapshots lacking the field restore with `false`, retaining their original dynamics. The global creation version remains 6.1; only this birth default within 6.3 changed. Running services were not restarted.

## Prefix and sustained-activity results

P uses actual defaults: adaptive retention, arrival-window novelty, per-connection inhibition, inhibitory learning and depletion enabled, and facilitation disabled. S101 uses the earlier successful prefix profile: stability retention, immediate novelty, weight-proportional inhibition, explicit inhibitory learning disabled, depletion enabled, and facilitation disabled. S011 changes S101 by disabling depletion and setting the facilitation time constant to 1 second. Inhibition does not update last-use time in any condition; independent resources are off throughout.

| Complete profile | Inhibitory bypass | Prefix discrimination | Sustained activity after 300 s |
| --- | --- | ---: | ---: |
| P: other actual defaults | Off | 0/2 | 0/2 |
| P: actual new defaults | On | 0/2 | 0/2 |
| S101: prefix profile | Off | 0/2 | 0/2 |
| S101: prefix profile | On | **2/2** | 0/2 |
| S011: alternate resources | Off | 0/2 | **2/2** |
| S011: alternate resources | On | 0/2 | **2/2** |

With S101 and bypass on, correct-ending margins were 0.000974463734 for AB and 0.002693525721 for DB. Exchanging the endings yielded the same margins. All four exactly matched R51t15. With bypass off, the margins were 0.001123885359 and −0.001123854996: both prefixes favored the same ending. **Within this declared configuration, inhibitory bypass changed failed prefix discrimination into successful discrimination.**

Adding bypass to P produced margins of 0.001093660107 and −0.001093331820, still favoring the same ending for both prefixes. P retains inhibitory learning and other defaults that differ from S101. Its negative result and S101's replicated positive result answer the two separately registered questions.

For S011 with bypass on, the maximum task-node activation remained between 0.017154 and 0.023055 throughout the 15-second window after the 300-second wait. With bypass off it ranged from 0.019880 to 0.026719. Both blocks passed, with no node sample reaching 0.95 activation in that window. The waiting course also retained samples every 100 ms: all 3001 samples per block and condition contained task activity above 1e-6. This post-run descriptive calculation is preserved in `descriptive-analysis.json` and did not alter registered scoring. Task activity in P and S101 reached zero about 1.7–1.8 seconds into the wait.

**The batch establishes a specific configuration tradeoff: the original prefix profile discriminated both relations; disabling depletion and enabling facilitation sustained activity to 300 seconds while both prefixes again favored one ending.** Those two resource settings changed together, so the observed contrast belongs to that combined change. This measured difference provides a concrete basis for studying coexistence of discrimination and sustained activity. The registered batch ended without further tuning or resumption of broad revalidation.

## Performance decision for independent resources

The reference build used 6.3 at b7adf1b5, before independent resources were added, with the same new bypass rule. It was built in isolation and did not replace the production implementation. Both builds used the same Rust release optimizations. Courses with 32 and 128 nodes crossed the two allocation modes with bypass on/off. After warmup, builds alternated for five measurements each; comparisons use medians.

| Nodes | Inhibitory allocation | Bypass | Elapsed-time change from retaining the disabled independent-resource option |
| ---: | --- | --- | ---: |
| 32 | Per connection | On | +2.52% |
| 32 | Per connection | Off | +2.43% |
| 32 | Weight proportional | On | +1.27% |
| 32 | Weight proportional | Off | +1.51% |
| 128 | Per connection | On | +0.30% |
| 128 | Per connection | Off | +2.10% |
| 128 | Weight proportional | On | −0.33% |
| 128 | Weight proportional | Off | +0.11% |

All matched builds produced identical numerical states and event counts. Peak process commit differed by at most about 1.2%. Snapshots grew by 76 bytes from storing the explicit option in both configuration and definition. No condition reached the preregistered 20% repeat threshold. **Retain independent resources, default off.** This measures keeping the disabled option; enabling independent resources adds actual resource state, whose earlier cost is reported in R51t14.

Bypass itself changes dynamics, so its execution cost is reported separately. At 32 nodes, enabling it increased per-connection/proportional times by about 27%/36%. At 128 nodes, proportional allocation increased about 0.9%, whereas per-connection execution increased from 0.898 to 12.126 seconds, about 13.50-fold. The 128-node course initially creates 16,256 directed connections and is a dense-network benchmark. These are measured costs of different transmission rules under identical input, rather than the overhead of retaining the independent-resource option. Bypass remains default on as authorized; subsequent large-task budgets should account for this cost instead of extrapolating from the small prefix task.

## Verification, delivery, and significance

All 263 engineering checks passed, covering Python/Rust parity, resource use by each signal type, learning, reconfiguration, earlier snapshots, complete restoration, and the standalone runtime. Hashes of 19 implementation files for 6.0–6.2 remained unchanged. All six configurations passed observation, save/restore, partitioned-advance, and wall-clock-pause invariance checks. The native wheel was installed in the project environment. Temporary-directory permission failures occurred before scientific execution and required no subject modification or repeated teaching.

All 72 stages completed. Verification covered 144 complete states, 36 processes, and parent–copy relationships. Independent score recomputation had zero maximum discrepancy. Recorded stage execution totaled 188.59 seconds; host time including saving and boundary handling was 239.84 seconds. Peak scientific-host private memory was 98.55 MiB. Originals occupied about 64.84 MiB logically at audit time. No resource stop occurred. Engineering-build costs and scientific execution are recorded separately.

This batch brings the experimentally validated inhibitory bypass into production 6.3 and exactly reproduces the earlier prefix success. It identifies the differences among actual defaults, the prefix profile, and the sustained-activity profile, providing concrete evidence for subsequent configuration choices. Retaining optional independent resources is inexpensive, so performance does not require deleting it. Completed stages will not be rerun; broad revalidation remain paused. [Public edition: manuscript editing or private locator omitted.]

Research record: `8f0bca42-147f-54d5-a0fe-0fc9299ce0c0`. Originals: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/resource-bypass63-v1`. See [summary.json](summary.json), [scores.csv](scores.csv), [performance summary](performance-summary.json), and the complete readback/closure receipt [delivery.json](delivery.json). Verification was performed on the author's side and is not labeled external reproduction.
