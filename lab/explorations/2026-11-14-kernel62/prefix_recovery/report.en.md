# Weight-reinforcement switches and recovery of prefix discrimination in 6.2: R51t7

Initiated 14 November 2026; verification completed 15 November 2026. Research record: `9764684a-2060-5999-b604-7b6a9d6f2ca4`.

## Scientific conclusion

**Prefix discrimination was restored in a 6.2 research derivative that retains fixed-function addressing.** Stability-based retention, immediate novelty and replacement of the complete emission method with the frozen 5.1 method passed both exchanged curriculum blocks. Disabling inhibitory weight reinforcement, replacing inhibitory transmission alone, raising the excitatory signal-amount threshold alone, and combining the latter two changes all failed to restore discrimination.

Post-teaching interventions showed that successful task weights and suitable transmission during testing are both required in this comparison. Replacing the successful parent's eight task-connection weights with those from the failed parent abolished discrimination. Changing only its test-transmission configuration to the failed condition also abolished discrimination. Conversely, giving the failed parent only the successful weights or only the successful test configuration did not restore it.

This explains why the previous 6.2 implementation did not recover the function: reinforcement and retention identified in 5.1 remain important, but differences in emission must also be addressed when transferring those rules to 6.2. **Restoration does not require abandoning fixed-function addressing.** The experiment provides a reproducible recovery procedure and a concrete emission process in which to seek a smaller change.

As requested, production 6.2 received only the two new weight-reinforcement switches, both enabled by default. Emission replacements remain separately identified research derivatives. The comprehensive replication campaign remains paused; further production changes await the author's decision.

## Purpose, expectations and materials

The first question was whether inhibitory transmission reinforces weights in a way that causes the prefix failure. Subsequent comparisons examined how teaching and expression diverge between 5.1 and 6.2. The initial nine configurations comprised 54 stages. Supplements registered before their respective runs added four emission candidates, 24 stages, and 16 post-teaching diagnostic copies: 94 stages in total. The preregistered candidate and copy allowances are exhausted and this batch is complete.

The first curriculum repeatedly supplied A–B–C and D–B–E; the second exchanged C and E. Tests supplied only A–B or D–B and measured whether the earlier A or D made the shared B favor the correct ending. Each curriculum involved 212.2 internal seconds of continuous teaching. The complete teaching parent was retained, with separately declared AB and DB diagnostic copies. Each copy waited one second before the prefix; B followed one second later, with the original observation interval retained.

Activation, inhibition, direct activity and associative activity were sampled every 10 milliseconds. The primary measure remained the correct ending's activation peak after B minus the other ending's peak. Both prefix differences had to exceed 1e-6 to pass a block; both blocks had to pass for recovery. There are two material blocks. Stages, copies and samples do not increase independent N. This was a passive mechanism investigation, without a new trainable reader or changes to the scoring criterion.

The apparatus reproduced genuine 5.1's successful reference and the previous 6.2 failure. The 5.1 peak differences matched the historical record, and the 6.2 stability/immediate reference was reproduced exactly. Separate codes verified invariance to observation, complete restoration, host pauses and partitioned advancement. Each supplement was registered before its scientific run; emerging questions did not change earlier scores.

## Delivered switches

`activation_weight_reinforcement_enabled` controls base-weight increments following successful excitatory transmission; `inhibition_weight_reinforcement_enabled` controls those following inhibitory transmission. Both default to True. They leave co-stimulation reinforcement and other learning states, including fast enhancement and stability, unchanged. The older `inhibitory_learning_enabled` switch has a broader scope and was therefore tested separately. [Equations and configuration](../mechanisms.en.md)

## Initial comparisons

The table shows peak differences for the first curriculum. The exchanged curriculum gave the same verdicts. Positive values favor the correct ending. Except for explicitly labeled compatible defaults, 6.2 conditions use stability-based retention and immediate novelty.

| Condition | AB peak difference | DB peak difference | Blocks passed |
|---|---:|---:|---:|
| Genuine 5.1 successful reference | 0.000978373 | 0.002735434 | 2/2 |
| Compatible 6.2 defaults | -0.000131848 | 0.000131883 | 0/2 |
| 6.2 stability + arrival window | 0.000804292 | -0.000803564 | 0/2 |
| 6.2 stability + immediate novelty | 0.000997287 | -0.000997332 | 0/2 |
| Inhibitory weight reinforcement off | 0.000897868 | -0.000897910 | 0/2 |
| Excitatory weight reinforcement off | 0.000146420 | -0.000146432 | 0/2 |
| Both weight-reinforcement switches off | 0.000065317 | -0.000065323 | 0/2 |
| Inhibitory-learning master switch off | 0.000889083 | -0.000889132 | 0/2 |
| Compatible defaults, inhibitory weight reinforcement off | -0.000189408 | 0.000189458 | 0/2 |

**The expectation that disabling inhibitory weight reinforcement alone would restore discrimination was rejected.** The switch changed response magnitudes but did not make both prefixes favor their respective correct endings. Disabling the broader inhibitory-learning mechanism also failed, motivating the transmission comparisons.

## Which transmission change restored discrimination?

The 5.1 emitter first sends excitation, then distributes a node's available inhibitory amount among incident connections in proportion to their base weights. Inhibitory distribution does not use short-term resource release or reinforce connections. In 6.2, both signal types travel through directed connections using a shared transmission process, short-term resources and optional learning. The old emitter also checks excitatory amounts before releasing short-term resources; the 6.2 connection signal threshold is checked after release.

| Isolated research condition | AB peak difference | DB peak difference | Blocks passed |
|---|---:|---:|---:|
| Old inhibitory transmission only | 0.000558579 | -0.000558675 | 0/2 |
| 6.2 excitatory connection threshold raised to 0.004 | 0.000570700 | -0.000570702 | 0/2 |
| Old inhibitory transmission + excitatory threshold 0.004 | 0.000318883 | -0.000318894 | 0/2 |
| Complete emission replacement | 0.000978373 | 0.002735434 | 2/2 |

The complete replacement retains the remaining 6.2 implementation and fixed-function addressing, under research identity `threemind.research-prefix-transport62/1`. Responses in both blocks closely matched the successful 5.1 reference. **Complete emission replacement met the preregistered recovery target; the other three candidates did not.** Recovery was localized to a defined emission process rather than requiring replacement of the whole kernel.

Teaching traces further narrowed the next candidate. Comparing complete emission replacement with old inhibitory transmission plus the 0.004 excitatory threshold, the first recorded task-state difference occurred at 3.9 internal seconds in the short-term resources of A→B and B→A. The successful condition retained its resource record from 3.8 seconds; the failed condition released resources again at 3.9 seconds. Recorded node activity, base weights, stability and recent-transmission state were still equal at that time. Weight and response differences followed later.

Source inspection agrees with this order: the old method skips sufficiently weak excitation before resource release, whereas raising only the 6.2 post-release threshold can still consume resources and then discard the signal. **The handling of weak signals before resource release is therefore the most focused next single-component candidate.** This is a new explanation suggested by the batch; the direct recovery result concerns the complete emission replacement.

## Formation during teaching and expression at test

The successful complete-emission parent and failed inhibitory-only parent have the same eight directed connections among the five task nodes. Weight exchange replaced only their eight base weights at the same teaching-end time. Recipient activity, short-term states, stability, recent history, age and unrelated connections were retained. Field-level audits confirmed exactly eight weight changes. Configuration interventions changed only configuration, definition and access counters; internal time did not advance.

| Post-teaching intervention | Blocks passed | Conclusion |
|---|---:|---|
| Failed parent with successful test configuration | 0/2 | Changing transmission at test alone did not rescue the state formed during failed teaching |
| Successful parent with failed test configuration | 0/2 | The successfully learned state still required suitable test transmission |
| Failed parent with successful task weights | 0/2 | These weights were insufficient under the failed test configuration and remaining state |
| Successful parent with failed task weights | 0/2 | The learned weights of these eight connections had a causal role in successful discrimination |

**Formation and expression of the prefix relation require compatible conditions.** This extends R51t6's finding that learned weights carry response differences: transmission affects both how those weights form and how they are expressed. Disabling one class of weight increment does not substitute for testing these two stages.

## Recommendation for 6.2

The two requested switches are delivered with enabled defaults. Evidence does not support disabling inhibitory reinforcement by default or changing only the excitatory connection threshold to 0.004 as a prefix-recovery fix.

Retain complete emission replacement as the successful reference. The next focused investigation should test weak-signal handling before resource release, keeping 6.2's directed transmission and other mechanisms, to seek a smaller change than restoring the entire old emitter. Whether to implement it, make it selectable or change defaults remains the author's decision. This batch does not resume the main campaign.

## Engineering and evidence

The final delivery regression passed 319 tests. Nine additional tests require an isolated PostgreSQL test cluster, which was not started. The 319 include 6.1 compatibility, Python/Rust parity, earlier 6.2 snapshot restoration and independent Rust runtime checks; the five independent-runtime tests also passed separately. The frontend built successfully, as did Python runtime and native Rust wheels and the standalone Rust executable. The native wheel is installed in the project environment; running services were not restarted. Six historical 6.1 implementation hashes remain unchanged. [Engineering summary](engineering-summary.json)

Scientific stages took 35.25 minutes in total. Verification covered 188 execution initial/final states, 16 pre-intervention states, 68 process records and every intervention field. Independent peak and integral calculations across all four activity fields had a maximum discrepancy of 3.91×10⁻¹⁸. These are audit counts; the material-block count remains two.

The initial full-graph observation buffer reached the 1 GiB process guard. Execution paused at the first complete teaching boundary, retaining that state and its original trace. Observation was changed to streaming storage after complete-state equivalence checks on separate codes; the completed teaching was not rerun and simulated time was not rolled back. The final 16 stages recorded a peak private memory of 83.59 MiB. Before archiving, the work directory occupied approximately 264 MiB logically, within the 1 GiB originals and 3 GiB total peak budgets.

Originals are stored at `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/prefix-recovery62-v1`. `analysis.json` preserves the initial matrix; `final-analysis.json` and `final-audit.json` cover the complete batch. `publication/completion.json` is the final receipt for full API readback and pending status. This report and all supplements are included in the evidence archive. Verification is an internal read-only audit within the author's project.
