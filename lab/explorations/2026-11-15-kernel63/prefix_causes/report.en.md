# R51t15: Reproducing prefix discrimination on 6.3 and identifying its causes

15 November 2026. All 132 stages are complete. The study used two material blocks with exchanged endings, followed by two newly encoded blocks for a selected successful/failing contrast. It used an isolated 6.3-derived research implementation; production kernels and defaults are unchanged.

## Conclusions

**The earlier 6.2 recovery is reproducible. Reconstructing its complete conditions on a 6.3 base again passes both material blocks, with prefix scores exactly matching the archived originals. The recent unsuccessful conditions used different resource and learning settings.**

The study answers four questions:

1. **Separate synaptic resources together with disabled inhibitory transmission-time updates did not restore discrimination.** Independent resources still passed 0/2 after explicit inhibitory learning was disabled and the inhibitory connection threshold was set to zero. Independent resources retain depletion and recovery; inhibition bypassed those constraints in the historical successful condition.
2. **Inhibitory learning has effects beyond transmission-time updates.** With those time updates still disabled, restoring the remaining explicit learning contributions changed 2/2 to 0/2. Restoring shared base weight, connection stability, touch count and latest touch time individually was sufficient to disrupt the successful condition.
3. **A zero inhibitory connection threshold was unnecessary for recovery.** The successful combination passed 2/2 at both 0 and 0.0004. Across all 12 conditions, these two thresholds did not change the corresponding pass/fail result.
4. **The selected contrast reproduced with new codes.** With threshold 0.0004, inhibitory resource bypass and disabled explicit inhibitory learning, both new blocks passed. Restoring only explicit inhibitory learning again produced 0/2.

| Scientific target | Registered criterion | Result and conclusion |
| --- | --- | --- |
| Reproduce the historical positive | Correct AB and DB in both blocks; check originals | Both emitters passed 2/2 with zero score discrepancy; the earlier recovery reproduced |
| Explain failure with independent resources and no time updates | Matched resource, learning and threshold comparisons | Independent groups passed 0/2; bypass with learning disabled passed 2/2; resource separation and bypass have different consequences |
| Locate explicit learning effects | Restore one inhibitory contribution to the working condition | Weight, stability and touch records each reduced the result to 0/2; effects extend beyond the transmission-time field |
| Replicate the selected contrast | Test fixed successful/failing conditions with new codes | Again 2/2 and 0/2; the original contrast replicated |

## Purpose, expectation and design

The user asked why separate resources and disabled inhibitory transmission-time updates had not reproduced the earlier recovery. We first reconstructed the complete positive condition, then tested the differences in matched comparisons. Full reproduction was expected; individual effects were determined experimentally. The user did not claim that shared resources were the sole cause. That attribution has been corrected in a separate [addendum](../resources/correction-20261115.en.md), also read back through the original research record. Historical text and scores remain intact.

All conditions used stability-based retention, immediate novelty, weight-proportional inhibition and prerelease checking. The excitatory connection threshold was 0.004; excitatory/inhibitory node sending thresholds were 0.004/0.002. Inhibition did not update the most recent transmission time except in the designated A control. These common settings came from the historical positive condition. Full parameters and stopping rules are in the [preregistered protocol](protocol.en.md).

Each new individual received 212.2 internal seconds of continuous teaching. Its complete final state was preserved before creating separate AB and DB diagnostic copies. AB should favor C and DB should favor E; the second material block exchanged the endings. A or D preceded B by one second. The full 15-second response was sampled every 10 ms, retaining activation, inhibition, direct and associative activity: 1,502 samples including the pre-cue point. Readout was passive, with no additional trainable reader.

The historical criterion was retained: after B, the correct ending's peak activation must exceed the other ending's by more than 1e-6. Both prefixes must be correct for a material block to pass, and both blocks must pass for recovery. Diagnostic copies and samples do not increase the number of independent material blocks. The new-encoding results are reported separately.

A comprised 18 stages for reproduction and the transmission-time control. B added 66 stages, completing 12 resource × learning × threshold conditions with the reused identical A reference. C used 36 stages to restore learning contributions individually. D used 12 stages for the selected contrast with new encodings. All 132 stages followed the registered design.

## Historical reproduction and factorial results

Both the historical emitter and the 6.3 emitter passed 2/2 under the complete positive conditions. In the first block, the correct-ending margins were 0.000974492792 for AB and 0.002693423080 for DB. The exchanged-ending block had the same answer-adjusted margins, exactly matching R51t11. Restoring inhibitory transmission-time updates alone kept AB correct but made DB favor C, failing both blocks. This reproduces the previously identified causal effect of that time record.

The following conditions all disable inhibitory transmission-time updates. Explicit inhibitory learning covers updates of connection weight, short-term enhancement, eligibility, stability, retention timescale and touch records after successful inhibitory transmission. It is distinct from the transmission-time control. Disabling this learning leaves inhibitory transmission and its effect on target nodes intact, as well as learning driven by excitation. See the [field descriptions](learning-fields.en.md).

| Resource handling | Explicit inhibitory learning | Inhibitory connection threshold 0 | Threshold 0.0004 |
| --- | --- | ---: | ---: |
| Shared resources | Off | 0/2 | 0/2 |
| Shared resources | On | 0/2 | 0/2 |
| Independent resources | Off | 0/2 | 0/2 |
| Independent resources | On | 0/2 | 0/2 |
| Inhibition bypasses resources | Off | 2/2 | 2/2 |
| Inhibition bypasses resources | On | 0/2 | 0/2 |

The independent pools were active. For the first block's DB diagnostic with inhibitory learning disabled and threshold zero, inhibitory amounts transmitted through connections were approximately 0.52705, 0.53033 and 3.35999 for shared, independent and bypassed resources. Independent pools remove sharing but retain inhibition's own release and recovery constraints. Resource bypass removes attenuation by the resource-release fraction. Corresponding excitatory amounts were approximately 0.63559, 0.72454 and 0.71110. These totals help interpret the matched outcomes; they do not replace the registered prefix score.

The successful nonzero-threshold condition had margins 0.000974463734 for AB and 0.002693525721 for DB. Both directions remained correct, establishing that lowering this threshold to zero was unnecessary in this comparison.

## Individual inhibitory learning effects

Starting from the recovered combination, each condition restored one inhibitory learning contribution while keeping all excitatory learning. Margins are the correct ending's peak minus the competing ending's peak. The two exchanged-ending blocks had identical answer-adjusted values.

| Individually restored inhibitory contribution | AB margin | DB margin | Blocks passed |
| --- | ---: | ---: | ---: |
| Shared base weight | +0.005640712 | -0.005638356 | 0/2 |
| Short-term enhancement | +0.000973876 | +0.002699569 | 2/2 |
| Eligibility | +0.000991682 | +0.002676600 | 2/2 |
| Connection stability | +0.001694651 | -0.001692954 | 0/2 |
| Retention-timescale growth (disabled in the base configuration) | +0.000974493 | +0.002693423 | 2/2 |
| Touch count and latest touch time | +0.000878090 | -0.000877071 | 0/2 |

Restoring shared base weight, connection stability, touch count and latest touch time individually made both prefixes favor the same ending. Restoring short-term enhancement, eligibility individually retained the correct response to each prefix. Retention-timescale growth was disabled in the base configuration; that row checks consistency with the unchanged configuration.

These results explain why the overall learning switch matters. Excitation and inhibition currently share base weights: inhibitory reinforcement also increases a connection's ability to transmit later excitation. Increasing stability reduces the decay of that shared connection's weight. Touch counts also participate in subsequent co-stimulation-driven stability growth. Restoring these updates individually reproduced the loss of discrimination. Disabling transmission-time updates leaves these reinforcement and retention paths available. The earlier explanation assigning all effects of explicit inhibitory learning to the time record was therefore incomplete.

Each comparison asks whether adding one update back to a working combination disrupts discrimination. The results identify three disruptive contributions. Decisions about their use in production should follow the actual interventions tested here.

## New encodings and implications for ThreeMind

The preregistered selection favored the successful condition with the nonzero threshold and its matched control restoring only explicit inhibitory learning. With new anonymous codes and birth seeds, the successful condition again passed both blocks while the control remained at 0/2. These results were not used to select new settings or revise the criterion.

**Prefix discrimination is reproducible on a 6.3 base. The relevant differences concern actual inhibitory transmission and how inhibition reinforces and maintains connections shared with excitation.** Resource separation, transmission-time updates and explicit learning are distinct interventions. Combining the first two did not reproduce the historical positive dynamics. This study identifies their actual consequences, preserves the earlier success and explains the recent failures. Any subsequent choice of production defaults can use these complete comparisons; production was unchanged here.

## Verification and delivery

All 264 complete states and 88 processes passed lineage, configuration, input and hash checks. Independent score recalculation had maximum discrepancy 0. Twelve historical positive boundaries and twelve recent unsuccessful reference boundaries were checked. Historical diagnostic setup settled short-term traces, whereas the new copies preserve their lazy representation. Projecting both to the same saved internal time left a maximum absolute state difference of 5.69e-14; prefix scores matched exactly.

Twenty-one configurations passed complete-state checks for observation, save/restore, partitioned advancement and host pauses. Shared and independent resource controls matched production 6.3 reference execution. Seven field-isolation and seven excitatory-update-equivalence formula checks passed. The historical emission-function body matched R51t11 exactly. Production sources, Rust, historical originals and manuscripts are unchanged.

Scientific computation totaled about 67.39 minutes; stage-host time including saving was about 69.15 minutes. Peak private memory was about 108.30 MiB. Original files had a combined logical size of about 112.94 MiB at audit. No resource stop was triggered. This mechanism study used the Python reference implementation; these timings document its execution cost.

A duplicate audit write was rejected because a list of changed field names had a different ordering. The original audit was preserved, its equivalent content was checked, and the unchanged B plan was registered. No teaching was repeated, rolled back or rescored.

Originals: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/prefix-causes63-v1`. Research record: `f5f5c28c-bcbd-590b-8a4a-8be49e30e6b7`. See [scores.csv](scores.csv), [summary.json](summary.json) and the [delivery receipt](delivery.json) for complete API readback and pending requests. Verification was performed by author-side tools and the assistant; the original package supports independent recalculation by external researchers.
