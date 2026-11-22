# Why persistent activity disappeared: a causal comparison of historical kernels and 6.1

2026-11-14 · R51t1 · 476 completed scientific stages; two blocks with exchanged teaching materials.

## Scientific conclusions

**The persistent activity observed in the historical experiment is reproducible, and interventions on internal mechanisms can maintain or terminate it. In 6.1, the relevant connections remain after activity stops. Disabling inhibition at the end of teaching, while activity is still present, maintains activity for 300 seconds in both material blocks and passes the subsequent complete 15-second observation.** Thus, retaining connections and sustaining activity are distinct outcomes. Inhibition contributes to the termination of activity in 6.1 under this condition.

Two historical changes were also located. Persistent activity disappears between kernels /2 and /3.1; selecting the existing legacy connection-retention mode in /3.1 or /5.1 restores it. Discrimination between sequences sharing an intermediate stimulus changes between /1 and /2. Returning /2 to the earlier timing of novelty enhancement exactly restores the /1 response differences. The same change does not restore sequence discrimination in 6.1.

**The change in inertial reversal and the loss of persistent activity do not have the same demonstrated threshold explanation.** A transmitted-signal threshold of 0.004 restored inertial reversal in R51m but restores neither persistent activity nor sequence discrimination here. Both phenomena depend on internal transmission and inhibition, but they change at different version transitions and respond to different interventions.

## Purpose, expectations and experimental organization

R51t found that 6.1 did not reproduce two historical E12 results: activity persisting for 300 seconds without new task cues, and discrimination of the endings of A—B—C and D—B—E from their different prefixes. The author requested a comparison with historical kernels and a test of the proposed connection with the loss of inertial reversal.

We used each version's genuine native implementation and replayed identical stimuli, strengths, times and ordering. The initial 384 stages compared /2, /3.1, /5.1, /5.3 and /6.1 and controls using public configuration options. After identifying a historical version-label error and locating a version transition, we registered 80 additional stages using genuine /1 and legacy retention configurations. Finally, the novelty-configuration difference motivated a registered 12-stage timing comparison. These two additions are follow-up explorations proposed after the initial observations; their protocols and registration times are retained separately.

The apparatus uses passive temporal readout and has no trainable adapter. Teaching is continuous. Diagnostic interventions use separately registered complete copies, preserving the Core, input bus, random state and readout history. The two material blocks exchange C/E, and all conditions use these materials. The number 476 counts execution stages; **the material replication remains two blocks**, not 476 independent individuals. This is targeted diagnosis using historical materials.

The persistence test uses historical condition 011: synaptic-resource depletion disabled, short-term facilitation enabled, and strengthening of existing connections enabled. Teaching lasts 81.2 internal seconds, followed by a 300-second wait with the original background stimulation but no new task cues. Activity is then recorded every 10 milliseconds for 15 seconds. A block passes only if the maximum activation among the five task nodes exceeds 1×10⁻⁶ at every sample; restoration requires both blocks to pass. Complete trajectories retain activation, inhibition, direct and associative activity. The registered persistence measure remains unchanged.

Sequence teaching lasts 212.2 seconds. After a one-second wait, separately registered diagnostic copies receive AB or DB. For 15 seconds from the second stimulus, we compare the activation peak of the taught ending with that of the alternative ending. Both differences must exceed 1×10⁻⁶ for the block to pass. This task requires discrimination despite the shared intermediate stimulus B and is scored separately from the previously successful two-event order experiments.

## 1. Historical persistence is reproduced; the first change concerns connection retention

| Genuine version or control | Blocks passing persistence | Blocks passing prefix discrimination |
| --- | ---: | ---: |
| /1 | 2/2 | 2/2 |
| /2 | 2/2 | 0/2 |
| /3.1 | 0/2 | 0/2 |
| /5.1 | 0/2 | 0/2 |
| /5.3 | 0/2 | 0/2 |
| /6.1 | 0/2 | 0/2 |
| /3.1, legacy connection retention | 2/2 | 0/2 |
| /3.1, legacy connection retention plus manual node retention | 2/2 | 0/2 |
| /5.1, legacy connection retention | 2/2 | 0/2 |

Kernels /1 and /2 retain low-amplitude persistent activity after 300 seconds. During the next 15 seconds, maximum task-node activation ranges from 0.017154 to 0.023055. In /3.1 and /5.1, the last positive sample occurs 3.6 seconds into the wait, and the task connections are absent at 300 seconds. Selecting the existing `consolidation_mode=legacy-stability` restores persistence in both versions, with amplitudes matching the historical result.

Thus, **the change from legacy connection retention to adaptive retention is a reversible cause of this historical difference in persistence**. This configuration affects both weight strengthening and forgetting and is interpreted as a combined retention-mode intervention. The result is not assigned to a decay equation alone. The structural endpoint at 300 seconds also does not establish that connections had already been deleted at 3.6 seconds.

## 2. Connections remain in 6.1, and an inhibition intervention maintains activity

Default 6.1 still has a positive activation sample at 28.2 seconds, but activation is zero at 30, 60 and 300 seconds. The complete graph at 300 seconds retains four task connections with weights of 0.632698–0.654313. Deletion of the task connections therefore does not explain activity termination in this 6.1 condition.

Disabling inhibition either from birth or only after unchanged teaching maintains activity through 300 seconds in both blocks. During the subsequent 15 seconds, maximum task-node activation ranges from 0.744045 to 1, passing at every sample. The post-teaching intervention starts from the same complete taught state, so it does not require changing the preceding teaching history.

Activity is still present when inhibition is disabled. This intervention **maintains existing activity** rather than restarting a network that has already become inactive. The public operation also clears existing inhibition and pending inhibitory events and settles state at the same internal time. All actual field changes are retained in each stage's `intervention.json`; the operation is not described as changing one scalar while leaving every other field untouched.

We then created diagnostic copies from the complete state at 300 seconds and changed resource depletion, short-term facilitation and strengthening of existing connections to test what maintains the activity.

| Intervention at 300 seconds | First zero-activation sample in /1 | First zero-activation sample in 6.1 with inhibition disabled after teaching |
| --- | ---: | ---: |
| None | Persists throughout 15 seconds | Persists throughout 15 seconds |
| Enable resource depletion | 0.65 seconds | 2.06 seconds |
| Disable short-term facilitation | 0.55 seconds | 4.09 seconds |
| Both changes | 0.55 seconds | 2.01 seconds |
| Disable strengthening of existing connections | Persists throughout 15 seconds | Persists throughout 15 seconds |

Both blocks give the same results. The sampling resolution is 10 milliseconds; times identify the first zero-valued sample. Short-term facilitation means that recent transmission increases the fraction of synaptic resources released. It is configured separately from the short-term enhancement that increases effective connection weight.

**These interventions show that established local connections and recurrent propagation can maintain activity, that short-term facilitation contributes to its maintenance, and that depletion can terminate it. Continued strengthening is not necessary for persistence within the tested 15-second interval.** Activity without inhibition in 6.1 is much stronger than historical activity and reaches the activation ceiling. This provides causal evidence; the report does not recommend this configuration as the production default.

## 3. Relationship to inertial reversal

In R51m, inertial reversal changes between 5.1 and 5.3. Persistence in the present experiment has already changed between /2 and /3.1. Raising the 6.1 transmitted-signal threshold from 0.0004 to 0.004 restored inertial reversal in all four R51m material blocks. Applying the same threshold here, either from birth or after teaching, yields 0/2 for both targets.

This rejects the expectation that transferring the threshold intervention that restored inertial reversal would also restore persistence. Inhibition remains relevant to both studies: disabling inhibition in a historical R51m control changed the reversed response, whereas disabling it here maintains activity. Future changes to inhibition should therefore evaluate response direction and persistence separately.

## 4. The early change in prefix discrimination follows novelty timing

Kernel /1 distinguishes AB and DB in both material blocks. The two peak differences are 0.0009778696465850764 and 0.00273563307296195. All four replayed values exactly match the historical originals. With /2's default arrival-window novelty calculation, the two prefixes favor the same ending, and neither block passes.

Changing only /2's `novelty_mode` to `immediate`, the earlier immediate novelty-enhancement rule, restores both blocks. All four values again exactly match /1. **This rule change is sufficient to explain the /1-to-/2 difference in prefix discrimination on these materials.**

The same change in 6.1 still yields 0/2. The AB and DB peak differences are +0.0000361310 and −0.0000361394, respectively. The preference changes, but the system does not recover the correct ending for both sequences. **The early version difference has been located; restoration of this shared-intermediate-stimulus task in 6.1 was not achieved.** Legacy retention, disabling inhibition and the other tested candidates also fail to restore that target. Further work requires a separate specific hypothesis rather than an open-ended parameter search.

## Scores for all remaining configurations

The table completes the initial controls not listed individually above. Conditions use 6.1 unless otherwise stated; each denominator is two material blocks.

| Condition | Persistence | Prefix discrimination |
| --- | ---: | ---: |
| /3.1, strong-stimulus fatigue disabled | 0/2 | 0/2 |
| Transmitted-signal threshold 0.004 | 0/2 | 0/2 |
| Transmitted-signal threshold disabled | 0/2 | 0/2 |
| Activation and inhibition sending thresholds both zero | 0/2 | 0/2 |
| Strong-stimulus fatigue disabled | 0/2 | 0/2 |
| Inhibition disabled | 2/2 | 0/2 |
| Inhibitory transmission excluded from connection strengthening | 0/2 | 0/2 |
| Short-term enhancement disabled | 0/2 | 0/2 |
| Exponential decay | 0/2 | 0/2 |
| Context mixing in reception matching disabled | 0/2 | 0/2 |
| Threshold 0.004 plus strong-stimulus fatigue disabled | 0/2 | 0/2 |
| Threshold changed to 0.004 after teaching | 0/2 | 0/2 |
| Strong-stimulus fatigue disabled after teaching | 0/2 | 0/2 |
| Inhibition disabled after teaching | 2/2 | 0/2 |
| Short-term enhancement disabled after teaching | 0/2 | 0/2 |
| /2, immediate novelty enhancement | Not tested | 2/2 |
| /6.1, immediate novelty enhancement | Not tested | 0/2 |

Figure files are stored under `figures/activity-causes.svg`, `.png` and `.pdf` in the batch data directory. Panels A–C show the waiting and observation trajectories of block 0; identical curves overlap. Panel D shows all peak differences for both blocks and both prefixes. The dashed line is the registered 1×10⁻⁶ criterion. Axes retain zero and negative values. Plotting neither advances nor reruns an individual.

## Verification, costs and version correction

The complete audit passes for 476 stages, 2248 complete states and 44652 inputs. None of the 48 waiting stages contains a task cue. Twenty default-6.1 final-state digests exactly match their R51t counterparts. Independent arithmetic on the original trajectories differs by at most 3.47×10⁻¹⁸. This arithmetic check is part of the same research workflow, not reproduction by external researchers.

The three scientific hosts take 58.57 minutes in total, excluding apparatus checks, audit and postprocessing. Peak private memory is 747.67 MiB. Minimum available commit, physical RAM, C-drive space and E-drive space are 13.73, 12.09, 7.34 and 67.92 GiB, respectively, all above the reserves. Recorded time for the same 20 stages gives a 6.1-to-5.1 ratio of 1.31. This includes observation and saving and is not a pure Core benchmark. Before archiving, the directory contains approximately 1.095 GiB of logical content and 1.108 GiB of allocated storage across 6778 files, with no duplicate hard links. This includes field-by-field intervention audit records and excludes the subsequent archive and readback copies.

All 592 historical E12 result files identify `threemind.continuous-memory/1`. R51t mistakenly labeled that historical comparator /2. A [separate erratum](../memory_timescales/errata-20261114.en.md) and appended notes in the original research record correct the label; the original reports, values, artifacts and genuine /2 runs remain intact. A registration event category and an auditor's incorrect receipt-field assumption were also corrected; see the [audit note](audit-correction.en.md) and `registration-corrections/` in the data. These corrections changed no scientific inputs or scoring and reran no completed individual.

The final audit entry points are `analyze_v3.py` and `analyze_novelty_v2.py`. Earlier auditors remain as process records. Originals, configurations, frozen-source records, both follow-up protocols, complete states, deliveries, figures and reports are delivered through the existing research API. Closure requires complete-package download verification and zero pending requests; the receipt is stored in `publication/completion.json`.

## Meaning for ThreeMind and the next decision

The comparison advances the historical observation of persistence into a more specific mechanism account: **connections retain propagation paths; continued activity also depends on short-term facilitation, resource depletion and inhibition.** The historical phenomenon is reproducible and can be maintained or terminated by interventions, giving a concrete experimental result to preserve and explain. A further finding is that the timing of novelty enhancement is sufficient to change discrimination between two similar sequences.

This diagnostic batch is complete. Production Core implementations, defaults and manuscripts are unchanged. The comprehensive replication campaign remains paused under R51t's adverse-mechanism rule. We recommend a bounded comparison of propagation balance while retaining inhibition, with separate tests of persistence, inertial response direction and shared-intermediate-stimulus discrimination. Specific changes and new experiments require the author's decision. Disabling inhibition is not adopted as a default, and restored persistence does not replace the still-unsuccessful prefix-discrimination target.
