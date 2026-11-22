# R51t11: Restoring prefix discrimination by separating inhibition transmission and connection retention

15 November 2026. Research record: `33b74b4b-d2ef-54ac-a3db-a460c960a424`. This is the first completed report for this batch. Earlier reports, originals and criteria are preserved.

## Conclusion

**A concrete solution restores prefix discrimination with 6.2 fixed-function addressing, supported by a direct causal comparison.** The reference normalizes inhibition by effective connection weights, bypasses excitatory synaptic resources, disables explicit inhibitory learning, and sets the inhibitory connection-signal threshold to zero, yet passes 0/2 blocks. Changing only whether inhibitory transmission writes the connection usage time restores both exchanged curricula. The new-code and birth-seed check passes 2/2 blocks. Node sending thresholds and inhibitory competition remain active.

The same B cue therefore elicits different learned endings according to whether A or D preceded it. Exchanging the taught endings exchanges the correct responses. This recovery uses network dynamics and experience, without a trainable readout or access to scoring answers.

The normalized-path condition restored prefix discrimination in both blocks. Its matched phase-A control differs only in inhibitory usage marking. This comparison establishes a causal contribution of that marking to the prefix outcome under the specified configuration. The identical full configuration passed persistence in 0/2 blocks and the additional recoding check in 2/2 blocks. This supplies a second, more narrowly isolated recovery result alongside phase F.

None of the four complete configurations tested with the phase-F candidate jointly passed prefix discrimination and task activity after 300 seconds. The configuration that recovered prefixes failed persistence; those that maintained task activity failed prefix discrimination. **The batch resolves prefix recovery and identifies the candidate's present configuration trade-off.** Production 6.2 and its defaults were not changed.

## Purpose, material and criteria

The author requested a solution. The registered targets were an implementable recovery, a decomposition of inhibitory propagation, and a persistence check under identical full configurations. See the [initial protocol](protocol.en.md), [shared-configuration amendment](shared-config-amendment.en.md) and [usage-record amendment](usage-amendment.en.md).

Two curriculum blocks teach A–B–C and D–B–E, with the ending assignments exchanged in the second block. Each condition develops continuously for 212.2 internal seconds. Its complete teaching state is retained; separately registered diagnostic copies receive AB or DB, with B one second after the prefix. Activation, inhibition, direct and associative activity are recorded over 15 seconds at 10-ms intervals, including same-time pre/post-stimulus observations: 1,502 points in total. Execution uses isolated derivatives of the Python reference implementation, each with its own saved identity and complete definition.

The historical criterion is unchanged: after B, peak activation of the correct ending minus that of the alternative must exceed 10⁻⁶. Both AB and DB must pass within each block, and both blocks must pass for recovery. The units are two exchanged curriculum blocks. Conditions, copies and observation points are not additional independent samples. The recoding test changes anonymous codes and birth seeds while retaining the taught relations.

Persistence uses existing material: 81.2 seconds of teaching, a 300-second wait containing 300 fixed background frames, and a 15-second observation window. At every observation, at least one task node must have activation above 10⁻⁶; both blocks must pass. Records at or above 0.95 are also counted. Actual node activity, not the life label, determines the outcome. Prefix and persistence subjects are born separately, with identical full configurations in each matched comparison.

## Recovery and controls

Phase A crossed four binary factors: inhibitory allocation, use of synaptic resources, inhibitory learning, and the inhibitory connection threshold. All sixteen combinations passed 0/2 blocks. This reference already used stability-based retention, immediate novelty and the 0.004 excitatory threshold. It represents the current sending pathway under those settings, not an individual with every production default.

The preregistered fallback compared incident versus outgoing connections and base versus effective weights within a separate inhibitory pathway. All four conditions passed:

| Routing and weight | Blocks passed | Block/cue: correct-ending peak advantage |
| --- | --- | --- |
| incident-base | 2/2 | 0/AB: 0.00097837252715; 0/DB: 0.00273543382836; 1/AB: 0.000978372527257; 1/DB: 0.00273543382825 |
| incident-effective | 2/2 | 0/AB: 0.00097836336178; 0/DB: 0.00273543350522; 1/AB: 0.000978363361994; 1/DB: 0.002735433505 |
| outgoing-base | 2/2 | 0/AB: 0.00097620054254; 0/DB: 0.002737824669; 1/AB: 0.00097620054254; 1/DB: 0.002737824669 |
| outgoing-effective | 2/2 | 0/AB: 0.000976198938564; 0/DB: 0.00273781661793; 1/AB: 0.000976198938564; 1/DB: 0.00273781661793 |

Outgoing connections with effective weights were selected by the registered preference, preserving the current direction and weight representation. AB and DB advantages were approximately 0.000976199 and 0.002737817. The recoding test produced the same advantages, above the 10⁻⁶ criterion. Recovery therefore does not require incident-edge routing or a return to base-weight readout.

The selected phase-F procedure is explicit:

1. Process excitation using 6.2 node rules, pre-release checking, synaptic resources and learning; use an excitatory connection-signal threshold of 0.004.
2. After excitatory processing, calculate the node's inhibitory output budget and retain the node-level inhibitory output threshold of 0.002.
3. Allocate that budget proportionately over available outgoing effective weights: `inhibition delivered to a target = node inhibitory output × connection effective weight / total available outgoing effective weight`.
4. Inhibition continues to affect competing target nodes. It does not use excitatory synaptic resources, directly reinforce connections or update their usage time. The ordering of excitatory processing and inhibitory allocation is part of the tested procedure.

This is a validated combination. Phase A shows that its success cannot simply be assigned to a single switch such as less inhibition or disabled inhibitory learning. Complete configurations, distinct research identities and source copies are frozen in the phase-F and phase-D selection artifacts.

## Inhibitory usage records and retention

Source inspection found that the current sending pathway updates `last_pass_us` after inhibitory-only transmission even with `inhibitory_learning_enabled=False`. Under stability-based retention, this can exempt the connection from weight decay at the same time and affects the coefficient used for a later co-stimulation update. It is a dynamics-relevant field.

This observation became a prospectively registered phase-E hypothesis. Two completed A conditions serve as intact controls. E changes only whether inhibitory-only transmission writes the usage record; excitation continues to write it. The current-path condition keeps existing allocation and resources. The normalized-path condition already normalizes inhibition, bypasses its synaptic resources, and disables explicit inhibitory learning and its connection threshold.

| Condition | Blocks passed | Block/cue: correct-ending peak advantage |
| --- | --- | --- |
| current-path | 0/2 | 0/AB: 0.00126677808512; 0/DB: -0.00126673399811; 1/AB: 0.00126677808512; 1/DB: -0.00126673399811 |
| normalized-path | 2/2 | 0/AB: 0.000974492791518; 0/DB: 0.00269342308005; 1/AB: 0.000974492791518; 1/DB: 0.00269342308005 |

In both blocks, retaining the usage record in the normalized control gives a correct-ending advantage of approximately 0.001050893 for AB but −0.001051378 for DB. Removing the record gives 0.000974493 and 0.002693423, respectively. A preference for one ending becomes the appropriate response to each prefix.

The normalized-path condition restored prefix discrimination in both blocks. Its matched phase-A control differs only in inhibitory usage marking. This comparison establishes a causal contribution of that marking to the prefix outcome under the specified configuration. The identical full configuration passed persistence in 0/2 blocks and the additional recoding check in 2/2 blocks. This supplies a second, more narrowly isolated recovery result alongside phase F.

### Recommended configuration

The phase-E solution retains the current emission order. Its full settings are stability-based retention, immediate novelty, a 0.004 excitatory connection-signal threshold, pre-release checking and activity expiry; inhibitory output normalized by outgoing effective weights and distance factors; no inhibitory release or consumption of excitatory synaptic resources; explicit inhibitory learning disabled; inhibitory connection-signal threshold zero; and no inhibitory-only update of connection usage time. Node sending thresholds remain. Depletion is enabled, facilitation disabled, and the inhibition decay constant remains 0.2321354823 seconds.

The causal result concerns a specific connection-usage record. Even with explicit inhibitory learning disabled, inhibition previously influenced decay and later reinforcement through that record. Separating this effect from competition restored the correct prefix relations. The intervention acts on the record and both of its downstream uses; attribution is to that measured mechanism unit. The research implementation is complete. Production Python/Rust and defaults have not been changed.


## Prefix discrimination and persistence under the same configuration

Historical prefix material enabled depletion and disabled facilitation; historical persistence material disabled depletion and used a one-second facilitation time constant. A prospective amendment crossed both resource settings with both inhibition time constants in both tasks. Code 101 denotes depletion on and facilitation off; 011 denotes depletion off and a one-second facilitation time constant. Connection consolidation is enabled in both. The original inhibition decay constant is 0.2321354823 seconds; its quarter value is 0.05803387058 seconds.

| Complete configuration | Prefix discrimination | Task activity after 300 seconds |
| --- | --- | --- |
| resource-101-original-tau | 2/2 | 0/2 |
| resource-101-quarter-tau | 0/2 | 0/2 |
| resource-011-original-tau | 0/2 | 2/2 |
| resource-011-quarter-tau | 0/2 | 2/2 |

With resource setting 011, pointwise maximum task activation was 0.0171540–0.0230551 at the original time constant and 0.0554378–0.0745087 at the quarter value. Neither reached 0.95. With setting 101, task activation after 300 seconds was zero at both time constants.

Within these comparisons, stronger persistence coexists with failed prefix discrimination, and successful prefix discrimination coexists with failed 300-second persistence. Activity duration is therefore not a substitute for relational performance. The results support measuring activity maintenance and discrimination separately when choosing a configuration.

## Target closure and implications

| Target | Result and judgment | Scientific conclusion |
| --- | --- | --- |
| Implementable prefix recovery | Four F conditions each 2/2; passed | Correct prefix relations can be recovered with 6.2 fixed-function addressing |
| Check changed anonymous codes | D: 2/2; passed | Recovery is preserved under the tested recoding |
| Recover through the original four-factor decomposition | Sixteen A conditions all 0/2; failed | Those factors did not capture all consequential differences in the successful pathway |
| Joint prefix and 300-second persistence with the F candidate | No joint pass among four complete configurations; failed | The measured trade-off argues against selecting a global default from one task alone |
| Recover by removing inhibitory usage marking alone | current-path 0/2, normalized-path 2/2 | Passed under normalized inhibition; the usage record has a causal contribution |
| Recoding of the final E candidate | H: 2/2; passed | Recovery is reproduced with new codes and birth seeds |
| Same-configuration persistence of the final E candidate | G: 0/2; failed | This prefix configuration does not maintain task activity after 300 seconds |

Prefix recovery is a favorable result for ThreeMind: it supplies a rule-level solution without changing answers, fitting a peripheral or reverting stimulus addressing. The negative controls constrain its explanation and prevent an existing switch from being mistaken for a complete mechanism. The crossed-task results argue against choosing defaults solely for longer activity.

The supported inhibitory pathway is a candidate optional 6.2 mechanism, with the current pathway and historical saved identities retained. Default selection should reflect the actual prefix and persistence requirements. This recommendation has not been applied to production. Comprehensive replication remain paused. [Public edition: manuscript editing or private locator omitted.]

## Evidence, integrity and cost

The batch completed 192 teaching, waiting or diagnostic stages. Independent verification covered 576 complete states and 118 processes; maximum scoring discrepancy was 0. Apparatus checks preserved identical full states under observation, save/restore, partitioned advancement and host pauses. The original 168-stage analysis and audit remain intact; additions appear in `analysis-final.json` and `audit-final.json`.

Scientific stages took 93.99 wall-clock minutes; phase hosts including management took 96.45 minutes. Peak private memory was 115.99 MiB. Files occupied 158.94 MiB at final audit, before archive and readback copies. This is a file-byte total, not NTFS allocation or a controlled performance benchmark. Minimum observed commit/RAM/C/E availability was 13.61/11.87/9.44/60.61 GiB; reserve thresholds remained 5/4/5/25 GiB. No resource stop or new incomplete stage occurred.

The separate inhibitory research pathway does not increment the general inhibitory-transmission counter. Conclusions use saved node inhibition processes and controlled outcomes. A zero value of that counter is not interpreted as absent inhibition or used to compare total inhibitory transmission.

Originals: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/prefix-solution62-v1`. The [delivery receipt](delivery.json) records completion of scientific-API registration, full archive readback and pending=0. Production kernel sources, defaults, historical originals and manuscripts are unchanged.
