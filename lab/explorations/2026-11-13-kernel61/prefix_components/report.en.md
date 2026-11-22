# Prefix discrimination depends on transmission learning, stability and learned weights

2026-11-14 · R51t6 · Two exchanged curriculum blocks and 70 scientific stages.

**Two effects were necessary for recovered prefix discrimination: reinforcement of base weights by actual associative transmission, and stability-dependent protection against weight forgetting. Removing either abolished two-way discrimination. Exchanging only the learned weights transferred success and failure in both directions.**

The novelty result revises the explanation of recovery. **Additional immediate-novelty enhancement was unnecessary: disabling it preserved the complete scientific states and recorded activity processes. Arrival-window novelty instead produced weight differences that biased responses toward one ending.** The immediate configuration's advantage here comes from avoiding that adverse change, not from a stronger enhancement.

## Purpose, expectations and design

R51t5 recovered both prefix relations with legacy retention and immediate novelty in genuine versions 3.1 and 5.1. This study separated novelty's weight and stability increments, local retention effects, and the contribution of learned weights. Its preregistered expectations were that removing at least one component would abolish recovery and that weight exchange would transfer performance. Both targets were achieved.

The isolated research implementation, `threemind.research-prefix-components/1`, derives from frozen 5.1 rules. It is not a production 5.1, 6.1 or 6.2 kernel. Nine birth configurations each received two curricula, with one teaching stage and two diagnostic copies per curriculum: 54 stages. Sixteen preregistered post-teaching interventions followed. Only three copied local methods—connection formation, emission and edge updates—contain the declared component switches. Source inspection verified those differences, and complete-state calibration compared the reference with genuine native 5.1.

One curriculum taught A-B-C and D-B-E; the other exchanged C and E. Teaching lasted 212.2 internal seconds. Diagnostic copies inherited the complete teaching endpoint, waited one second, received A or D, then B one second later, and were observed for 15 seconds. The fixed process record includes activation, inhibition, direct and associative activity. No trainable readout was added.

The unchanged primary criterion requires the taught ending's activation peak to exceed the alternative's peak by more than 1×10⁻⁶. Both prefix directions must pass within a block. The two blocks are exchanged materials, not 70 independent individuals. All conditions and criteria were registered before execution and remained fixed.

## Contributions of the components

| Condition | Passing curriculum blocks | Finding |
| --- | ---: | --- |
| Legacy retention plus immediate novelty | 2/2 | Reproduced recovery |
| Arrival-window novelty | 0/2 | Recovery was lost |
| All immediate-novelty increments disabled | 2/2 | Extra enhancement was unnecessary |
| Immediate novelty adds weight only | 2/2 | Same performance as the reference |
| Immediate novelty adds stability only | 2/2 | Same performance as the reference |
| Remove the decay exemption during use | 2/2 | Not necessary in this task |
| Remove stability's protection against weight forgetting | **0/2** | **Necessary in the successful combination** |
| Remove recent-trace protection against stability decline | 2/2 | Not necessary in this task |
| Remove weight reinforcement by actual transmission | **0/2** | **Necessary in the successful combination** |

Legacy stability is an edge state between zero and one. Co-stimulation and actual transmission increase it, and it declines with disuse. Higher stability slows weight forgetting. A separate recent-transmission trace, stored as `eligibility`, can temporarily slow stability's decline.

Under the default legacy rule, an edge that did not transmit during a 100-ms period multiplies its weight by `1−0.0023×(1−stability)`. Actual use exempts that period from weight decay. Removing stability's protection retains the other processes but makes the multiplier independent of stability. The correct-direction margins then become −0.008243803 for AB and +0.008242222 for DB: activity remains, but it favors the same ending. Removing transmission-based weight reinforcement yields +0.000005919 and −0.000005919, again failing two-way discrimination.

Reference margins are 0.000978373 and 0.002735434. Removing the exemption during use gives 0.000793306 and 0.002890887; removing the recent trace's protection gives 0.000970360 and 0.002742758. These are separate ablations. Simultaneously removing both has not been tested.

## What learned weights carry

The post-teaching exchanges replaced only base weights. Recipient activity, inhibition, short-term resources, stability, recent traces, queues and observer history remained intact. Directed topology, channel identity and weight timestamps matched.

| Post-teaching intervention | Passing blocks | Correct-direction AB / DB margins |
| --- | ---: | --- |
| Successful parent receives window-parent weights | **0/2** | +0.000996508 / −0.000996605 |
| Window parent receives successful-parent weights | **2/2** | +0.000978396 / +0.002735439 |
| Disable existing-edge strengthening during successful-parent probes | 2/2 | +0.000978193 / +0.002734240 |
| Disable weight forgetting during successful-parent probes | 2/2 | +0.000993013 / +0.002721190 |

**Bidirectional exchange establishes that learned weight differences are sufficient to change prefix performance in these materials.** Successful expression persists without further existing-edge strengthening during testing; the relations need not be learned anew while answering. Current prefix activity enters the network, and the stored weights determine how it affects responses after the shared B stimulus.

Failure was not simply weaker connectivity. In the first curriculum, B→C increased from reference weight0.594162 to0.603411 under the window rule; B→E increased from0.576705 to0.585630. Larger weights did not improve relational discrimination. The exchanges provide causal evidence beyond these descriptive differences.

## Interpreting novelty

For novelty-off, weight-only and stability-only immediate configurations, comparison with the reference covered teaching and both probes in each block. All 18 scientific endpoint states and all 18 recorded node processes were exactly identical. Identity, configuration and execution counters were separated; other state was compared field by field.

**Success in this curriculum does not depend on the immediate bonus, whereas the learned weight differences introduced by the arrival-window rule disrupt it.** This rejects the explanation that additional immediate enhancement is required for recovery. The historical calibration and current result concern different outcomes: arrival-window novelty improved transient responses in other materials, without establishing universal task superiority. The [authorization audit](novelty-authorization.en.md) records the proposal, prospective approval and contemporary evidence.

This study did not separately remove the arrival-window rule's own weight and stability increments. It therefore does not independently attribute the adverse outcome to its initial weight bonus, subsequent retention or learning feedback. The completed localization is that its learned weights transfer failure, while stability-dependent retention and actual-transmission learning are individually necessary for the successful combination. Any further decomposition receives a new design without changing this study's targets.

## Meaning for ThreeMind and 6.2

The findings identify a concrete mechanism: actual transmission reinforces connections, stability makes forgetting depend on experience, and the resulting weight relationships support prefix-dependent responses. Additional enhancement can disrupt those relationships. Restoring useful behavior should target these identified effects rather than maximizing persistence or activation alone.

Retain both existing novelty modes and prioritize immediate novelty as a default candidate for 6.2. Legacy retention is valuable as an optional reference, particularly its experience-dependent modulation of forgetting. The present study leaves 6.1 addressing, transmission and single-age decay unchanged. A 6.2 default must be evaluated in its actual configuration using the recovered prefix task and affected established capabilities.

Legacy stability growth and decline differ from growth and relaxation of the current time scale H. Legacy weight decay does not use H. Enabling H flags does not automatically implement a defined legacy rule. Preserve the legacy mechanism's own growth and decline with explicit controls rather than silently adding another H rule. The [6.2 assessment](evaluation.en.md) states the recommendations and inertial-sensing preset separately.

## Verification and delivery

All 70 stages completed. Audits verified 332 complete states, 8,462 inputs and arithmetic, with a maximum discrepancy of 3.47×10⁻¹⁸. Separate-encoding calibration matched the research reference to genuine native 5.1 scientific state within 1×10⁻¹². Observation on/off, complete restoration and a host pause produced identical research endpoint hashes and observer histories. Read-only auditing did not advance the model.

Science execution took21.38 minutes; peak private memory was approximately112.96MiB. The research implementation runs in Python, so this elapsed time is not a production-kernel performance ranking. Commit memory, RAM, C and E remained above5/4/5/25GiB reserves. The initial storage-calibration failure, pre-run restoration-default correction and read-only settlement-audit correction are preserved separately. No formal subject was rerun or rolled back.

Data: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/prefix-components61-v2`. Project `d0a04159-ee0f-4200-ada9-13d5ce7197b7`; record `118a926b-c65d-5834-a0d6-b8fd8e67f73a`. Closure requires full original-package readback through the research API and pending=0, recorded in `publication/completion.json`. Project-assistant analysis is distinguished from independent external replication. The comprehensive campaign remains paused; production kernels, defaults and the author's manuscript remain unchanged.
