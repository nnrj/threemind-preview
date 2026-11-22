# Kernel 6.1 replication of synaptic resources, facilitation and connection strengthening

14 November 2026, R51t. Original-scale E12 comparisons under comprehensive revalidation plan v2.

**The following primary targets were not met: Sustained activity and resource control; Prefix effects with a shared middle stimulus. The preregistered scientific stopping rule was triggered. After evidence delivery, subsequent revalidation pauses for review.**

| Target | Outcome |
|---|---|
| Retention of repeated pairings | Met |
| Expression with test-time strengthening disabled | Met |
| Sustained activity and resource control | Not met |
| Prefix effects with a shared middle stimulus | Not met |

## Purpose and methods

The study tests whether repeated experience leaves cue-retrievable associations and how connection strengthening, synaptic-resource depletion and short-term facilitation contribute to retention and expression. D, F and L denote depletion, facilitation and positive strengthening of existing connections; one means enabled and zero disabled. Enabled F uses a one-second time constant. L controls the corresponding existing-connection weight updates, while initial edge creation and other local mechanisms follow their declared settings.

Two material blocks exchange the C/E target assignments. Each tests all eight D/F/L combinations. Paired and balanced teaching use equal stimulus doses and the original three-stage repetitions and spacing. Retention is tested 1, 30 and 300 seconds after teaching. Additional comparisons use two sequences sharing middle stimulus B, disable L only before testing, and apply five interventions to sustained activity under 011. Genuine kernel 6.1 retains transmission threshold 0.0004, deletion threshold 0.008, inverse-logarithmic decay and disabled retention-scale growth.

There are 34 continuous teaching references, 48 subsequent waiting or common-reference stages, and 510 diagnostics: 592 stages in total. Diagnostics include 58 uncued and 452 cued cases. Copies remain nested within the two material blocks. Ordinary teaching preserves complete state; causal copies and retention cohorts are registered separately. The 41,248 inputs replay original API records, including background intensity 0.2; current host load is not introduced as new input. Each diagnostic records activation, inhibition, direct and associative activity every 10 ms for 15 internal seconds.

The primary target margin subtracts the other target's activation peak from the taught target's peak. Subtracting the corresponding balanced-teaching margin gives the pairing effect. Values above 1e-6 are positive. A retention condition requires both target and pairing advantages for both cues in both material blocks. The original temporal readout is evaluated separately with threshold 0.055 and its original classification rules.

## Retention of repeated experience

Default 101 retained the taught target and a positive pairing effect in all four comparisons at both 30 and 300 seconds. The repeated-teaching retention target was reproduced. At 300 s the mean pairing effect was 0.033404676, compared with 0.00891491371 in the original kernel-/2 batch, a ratio of 3.75. Retention of repeated pairings improved in this apparatus.

Each cell summarizes two blocks and two cues. Historical effects are recalculated from the original peaks under the same input conditions. All block-level values and complete trajectories remain available.

| D/F/L | Wait (s) | 6.1 pairing effect | Historical effect | Positive comparisons | Full condition |
|---|---|---|---|---|---|
| 000 | 1 | 0.00172967123 | 0 | 4/4 | Not met |
| 000 | 30 | 0.00272740691 | 0 | 4/4 | Met |
| 000 | 300 | 0.00193297339 | 0 | 4/4 | Met |
| 001 | 1 | 0.0543646058 | 0.058222558 | 2/4 | Not met |
| 001 | 30 | 0.073417771 | 0.0845911488 | 4/4 | Met |
| 001 | 300 | 0.0520994115 | 0.0180599687 | 4/4 | Met |
| 010 | 1 | 0.00312330189 | 0 | 2/4 | Not met |
| 010 | 30 | 0.00275562496 | 0 | 4/4 | Met |
| 010 | 300 | 0.00195201988 | 0 | 4/4 | Met |
| 011 | 1 | 0.112535491 | 0.111067042 | 2/4 | Not met |
| 011 | 30 | 0.13641335 | 0.176366356 | 4/4 | Met |
| 011 | 300 | 0.0924454132 | 0.178001149 | 4/4 | Met |
| 100 | 1 | 0.000360768927 | 0 | 4/4 | Not met |
| 100 | 30 | 0.00272283901 | 0 | 4/4 | Met |
| 100 | 300 | 0.00192992326 | 0 | 4/4 | Met |
| 101 | 1 | 0.0267670736 | 0.0206380855 | 4/4 | Met |
| 101 | 30 | 0.0470393515 | 0.0461802355 | 4/4 | Met |
| 101 | 300 | 0.033404676 | 0.00891491371 | 4/4 | Met |
| 110 | 1 | 0.000387785991 | 0 | 4/4 | Not met |
| 110 | 30 | 0.00272246539 | 0 | 4/4 | Met |
| 110 | 300 | 0.00192966154 | 0 | 4/4 | Met |
| 111 | 1 | 0.0316147932 | 0.022379534 | 4/4 | Met |
| 111 | 30 | 0.0540383351 | 0.0530568884 | 4/4 | Met |
| 111 | 300 | 0.0383954513 | 0.0109864256 | 4/4 | Met |

The following prespecified factorial differences quantify D, F, L and their interactions. Positive and negative values respectively increase and reduce the mean pairing effect. All combinations use the same formula; none was selected after observing the result.

| Effect | 1 s | 30 s | 300 s |
|---|---|---|---|
| D | -0.0281556619 | -0.0271977905 | -0.0181925265 |
| F | 0.016109813 | 0.0175056018 | 0.0113388905 |
| L | 0.0549201088 | 0.0749951178 | 0.0521500935 |
| DF | -0.0273448894 | -0.0280125936 | -0.0176872673 |
| DL | -0.0522069056 | -0.0543578535 | -0.0363596444 |
| FL | 0.0307989783 | 0.0349833591 | 0.0226589961 |
| DFL | -0.0519565516 | -0.0559680038 | -0.0353359182 |

## Established connections and test-time strengthening

Disabling L immediately before the cue preserved the default-101 effect at both delays. Established experience can therefore be expressed without further connection strengthening during the test. Across these eight comparisons, 99.9710%–99.9712% of the L-on target margin remained. Prior teaching can be expressed without further increases to existing connections' base weights during the test.

| Teaching D/F/L | Wait (s) | Target margin, L on | Target margin, L off | Pairing effect, L off | Outcome |
|---|---|---|---|---|---|
| 001 | 30 | 0.0732753135 | 0.0732215065 | 0.0733638601 | Met |
| 001 | 300 | 0.0519271841 | 0.0518889535 | 0.0520610542 | Met |
| 011 | 30 | 0.136358087 | 0.136096293 | 0.136151499 | Met |
| 011 | 300 | 0.0924123945 | 0.0922863789 | 0.0923193529 | Met |
| 101 | 30 | 0.0463691649 | 0.0463558028 | 0.0470257961 | Met |
| 101 | 300 | 0.0328434462 | 0.0328339301 | 0.0333949974 | Met |
| 111 | 30 | 0.053896569 | 0.0538769624 | 0.0540186768 | Met |
| 111 | 300 | 0.0382034679 | 0.0381895036 | 0.038381417 | Met |

These comparisons branch from the same complete reference and change L through the public configuration interface immediately before the cue. Field-by-field receipts include any settling of current state caused by that call. The comparison distinguishes established teaching effects from continued test-time weight changes.

## Maintaining and terminating activity

In both material blocks, maximum task-node activation was 0.318379507 at the one-second checkpoint and zero at 30 and 300 seconds. Activity had already ceased before intervention. Every sample in all five subsequent 15-second conditions was also zero. Kernel 6.1 therefore failed to reproduce persistence to 300 seconds under the historical 011 condition. Zero endpoints after enabling depletion or disabling facilitation are not counted as causal termination: all branches started with zero task activity.

Activity is the maximum activation among task nodes. Time starts at intervention after the 300-second wait. The following 15 seconds contain no new task stimulus; recorded background input continues. Last positive times use the 10-ms sampling interval.

| Material block | Condition | Initial activity | Activity at 15 s | Last positive activity (s after intervention) |
|---|---|---|---|---|
| 0 | Both changes | 0 | 0 | — |
| 0 | Disable L only | 0 | 0 | — |
| 0 | Enable depletion | 0 | 0 | — |
| 0 | Disable facilitation | 0 | 0 | — |
| 0 | Unchanged | 0 | 0 | — |
| 1 | Both changes | 0 | 0 | — |
| 1 | Disable L only | 0 | 0 | — |
| 1 | Enable depletion | 0 | 0 | — |
| 1 | Disable facilitation | 0 | 0 | — |
| 1 | Unchanged | 0 | 0 | — |

## Prefix effects on a common middle stimulus

Default 101 did not distinguish both prefixes in both blocks at any of 1, 3 or 20 seconds. The short-term input-interaction target was not met. At the one-second wait, both historical default-condition blocks distinguished the endings associated with AB and DB; kernel 6.1 passed jointly in 0/2 blocks. In the new results, both prefixes favored the D-sequence ending at one and three seconds, and the A-sequence ending at 20 seconds. Waiting changed the dominant ending without restoring prefix-specific discrimination.

Both taught sequences share B. A→B and D→B test whether each prefix retrieves its corresponding ending. Each block's two margins below follow that order. Single-cue, uncued and 0.1-, 1- and 3-second inter-cue comparisons remain in the complete analysis.

| D/F/L | Post-teaching wait (s) | Blocks passing both prefixes | AB/DB target margins in blocks 0 and 1 |
|---|---|---|---|
| 001 | 1 | 0/2 | -0.000648743856/0.000645936192; -0.000648743856/0.000645936192 |
| 001 | 3 | 0/2 | -0.000533719928/0.000531229905; -0.000533719928/0.000531229905 |
| 001 | 20 | 0/2 | 0.000322925388/-0.000321537043; 0.000322925388/-0.000321537043 |
| 101 | 1 | 0/2 | -0.000131848083/0.000131882899; -0.000131848083/0.000131882899 |
| 101 | 3 | 0/2 | -0.000108825352/0.000108856135; -0.000108825352/0.000108856135 |
| 101 | 20 | 0/2 | 6.59196957e-05/-6.59300899e-05; 6.59196957e-05/-6.59300899e-05 |

## Original temporal readout

Of 452 cued diagnostics, 0 were classified as converged by the original temporal readout. Among the 404 A, D, AB and DB cues with a specified ending, 0 produced qualified windows and 0 had a taught-target margin above 1e-6. The remaining 48 B-only cues control for the shared middle stimulus; their windows and both ending responses are reported without assigning a unique correct ending. The historical batch had zero converged windows among its 452 cued tests. This target is scored independently with the same rule.

| Temporal classification | Count |
|---|---|
| no_window | 58 |
| residual_decay | 452 |

Activation peaks measure a mechanism effect, while temporal classification tests whether the original readout forms a qualified window. Their scores and denominators remain separate. Pre-cue structure, uncued activity and 64 residual-activity subtractions are included in analysis.json for condition-level recalculation.

## Scientific conclusions and meaning for ThreeMind

This batch establishes that kernel 6.1 retains and strengthens repeated-pairing retention in this apparatus, and expresses prior teaching when test-time connection strengthening is disabled. It fails to reproduce two historical properties: persistent activity under 011 and prefix-specific endings when sequences share a middle stimulus. These are two explicit adverse dynamical differences and trigger the comprehensive plan's preregistered pause.

The next step is a same-material comparison of historical kernels and 6.1 to locate the responsible update rules before deciding how to resume comprehensive revalidation. Connection-causality, transplantation and four-criterion findings from other batches retain their recorded outcomes. This batch changes no default parameter or production Core.

The controlled comparisons distinguish the connection effects left by experience from their expression under current resource conditions. Each of the four targets receives its own conclusion under the original rules. Temporal-readout scores do not replace mechanism results, and one configuration does not stand for all configurations. The following primary targets were not met: Sustained activity and resource control; Prefix effects with a shared middle stimulus. The preregistered scientific stopping rule was triggered. After evidence delivery, subsequent revalidation pauses for review.

## Verification, cost and evidence

Read-only analysis verified 592 stages, 4,746 complete states, 41,248 inputs, 192 pre-cue structural records and four observation controls, creating and advancing no Core. Independent high-precision integration differed by at most 2.77556e-17. Normal and lower-frequency observation, restoration and host pauses preserved identical complete final states in apparatus qualification.

Formal execution took 114.29 minutes; peak private memory was 872.29 MiB. Comparable stage allocation ranged from 0.564 to 1.916 times the historical counterpart. Before report generation, originals occupied 1307.73 MiB logically and 1327.05 MiB of actual allocation, including apparatus and retained writer-qualification evidence.

The original apparatus and streaming writer v2 reached the one-GiB private-memory limit and stopped at complete boundaries. Version v3 losslessly compressed cached projections. Six calibration stages had identical complete states, observer states, trajectories and decoded projection bytes, with a 756.20-MiB private-memory peak. The formal batch then started once. Originals, archive and readback each have an eight-GiB budget; system reserves remain 5/4/5/25 GiB. This storage amendment changed no Core, curriculum or score.

The read-only audit corrected two tool errors: the bus interface requires an empty pending mapping, and the four observation controls must be compared at their frozen task-node scope. All 592 final buses contained no pending inputs; all 6,008 shared task samples and eight shared complete snapshots agreed exactly. The original auditor, v2 and both failure records are retained; v3 completed the full audit. Scientific measurements and thresholds remained unchanged, and no student was rerun. Evidence is in audit-amendment-v2/proof.json and audit-amendment-v3/proof.json.

Workspace: E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/memory-timescales61-v1. Research record: c4dda7ad-66fc-51de-8ad8-d1a31fe8d61c. Bilingual reports, protocols, tools, inputs, complete states and analysis are delivered under that record. The archive API-readback receipt is at publication/completion.json. Historical reports and the author's manuscript are preserved. Independent arithmetic here means tool verification; external researcher replication is recorded separately.
