# E57: where does the pointing answer come from?

Registered and started on 2026-10-06. Final delivery date and measured resources appear below. [中文](report.zh.md) · [Preregistration](design.en.md) · [Dated amendments](execution-notes.md)

## What this experiment establishes

**The present shape–colour apparatus cannot be described as Core doing the recognition while the motor centre merely translates its intention.** It trains a supervised object selector, followed by a servo that moves to the selected location. With Core bypassed and the same anonymous sensory inputs supplied directly, three external training seeds each score 24/24 on the finite task.

**Core is not causally irrelevant.** Different past experiences can change answers under identical present scenes and questions. In the first source, however, the attribution tests locate an important route in residual activation of teacher-pointing receptors. Transferring the activation of just five such nodes makes all 32 fixed-reader choices identical to the opposite history's choices. Transferring visual–text connections does not change choices. This is a causal effect of actual internal state; it does not establish learned object concepts in those connections or an autonomous motor intention.

This corrects the interpretation of this apparatus. E56's 24/24 remains a system capability result, not a Core-only recognition result. Other tasks' experience and association evidence is retained; this experiment neither substitutes for nor erases it.

## 1. No hidden test answer, but the supervised objective changes the division of work

The normal E56 route is physical world/question → existing sensory coding and input bus → Core → raw activation, inhibition, direct and associative touches on the output bus → Transformer selector → one of four locations → servo.

The audited inference route does not additionally pass the raw question, correct object identity or scoring answer. The issue is that **the selector is supervised on the correct object's position**. It can learn recognition from the direct sensory responses represented inside Core. Passing through Core does not establish learning by Core. Sharing one decoder across the four known optical fields also supplies an external structural assumption; it is not an emergent Core brain region.

The bypass is an explicitly labelled experimental control, not a change to normal operation. Incoming quantities retain their channels, magnitudes and timing; undefined neural fields are zero-padded to match model capacity. They are never presented as genuine Core activity. No unprompted-reference subtraction, trial-wise amplitude rescaling or altered sensory mapping is used.

## 2. What the external selector can do alone

Reuse E56's 48 calibration and 12 practice labels, with its fixed 24 confirmation questions. Every head has 76,657 parameters and 1200 optimization steps. The three seeds change external training, not the physical dataset.

| Information read | Seed223 | Seed279 | Seed337 |
| --- | ---: | ---: | ---: |
| Eight raw activity samples from learned Core | 24/24 | 23/24 | 23/24 |
| Learning-disabled-from-birth Core, equally fitted separate head | 24/24 | 24/24 | 22/24 |
| Core bypass, eight actual incoming samples | **24/24** | **24/24** | **24/24** |
| Core bypass, all twenty incoming samples | **24/24** | **24/24** | **24/24** |

These finite colour, shape and conjunction questions therefore do not require Core to learn the concepts. Bypass success does not mean the original reader ignores Core on every trial. E56's fixed-head connection silencing changed five correct answers to errors and rescue restored them. Such sensitivity alone cannot locate the semantic decision inside Core.

## 3. Identical present information, conflicting histories

Two naming histories associate 甲乙丁戊 with four grey shapes or cyclically shift that assignment. Each name receives ten consecutive lessons followed by three interleaved review rounds, with extra waits of 0/6/18 simulated seconds before the rounds: 52 lessons over 102 simulated seconds. Each lesson lasts 1.5 seconds, so the same item's last three review onsets are actually 12 and 24 seconds apart. The added waits are not the complete per-item revisit intervals; every delivery timestamp is retained. Complete bodily/weather input, normal intensity, forgetting and inhibition remain.

One reader per source learns 32 labelled examples spanning both histories, then freezes. Testing uses held layouts/views. Each paired question has the same current scene, wording, body and environment but requires a different answer because of the past. The teacher marker is absent at test and history IDs are excluded from inference. Trials restore source snapshots; 32 questions are not 32 independent organisms.

A deterministic history-free reader cannot exceed 16/32 on these identical-input pairs. This is an incompatibility ceiling, not four-way random chance.

| Condition with identical present input | Source223, weather47 | Source279, weather103 |
| --- | ---: | ---: |
| Learned Core, one reader spanning both histories | **25/32** | **23/32** |
| Structurally nonplastic Core, equally trained shared reader | 21/32 | 31/32 |
| Current sensory input only, equally trained reader | 16/32 | 16/32 |
| Reader frozen, Core alone receives continued/reversed lessons | 22/32 | 22/32 |

Both normal sources answer both members correctly in 9/16 paired questions;
after Core-only teaching the counts are 6/16 and 8/16. Source279 does not pass
the 24/32 localization gate; 23 is not redefined as success. The nonplastic
sources have zero edges and retain history differences in activation/inhibition.
There is no consistent learned-Core advantage: plus four answers in the first
source and minus eight in the second.

Core-only teaching does change some answers, but both scores remain 22/32.
Final teacher pointing also changes with history, so this result still admits
the recent sensory-residue route rather than establishing newly learned concepts.

Reading history is still weaker than learning a new mapping: the head has been supervised on both assignments. It could identify the history from a residual signal and select an answer rule stored in its own weights. We therefore locate the history signal rather than treating accuracy alone as concept learning.

## 4. Residual demonstration activity versus learned connections

Source223 passed the preregistered 24/32 localization gate. Masks use physical visual/text channel inventories, not test answers. Silence those existing edges, silence the same count of other edges, release the target mask, and transfer the opposite history's selected edges with their short-term operator state.

| First source, fixed reader | Correct for own history | Choices changed from normal |
| --- | ---: | ---: |
| Normal | 25/32 | 0 |
| Visual–text existing-edge silence | 25/32 | 0 |
| Same-count other-edge silence | 24/32 | 1 |
| Target-edge rescue | 25/32 | 0 |
| Opposite-history target-edge/state transfer | 25/32 | 0 |
| Opposite-history other-edge transfer | 25/32 | 0 |

This does not establish that all connections are irrelevant: only selected pre-existing edges were treated, without preventing new edges or recalling already emitted signals. Other-edge controls match count, but mean absolute weight mismatch is about 0.275 and topology is unmatched. Do not describe them as strictly equivalent lesions. Nevertheless, target-edge silencing and transfer do not explain the measured history choices.

An offline reader-field diagnostic was followed by an intervention in **actual copied Core states**, avoiding the mistake of treating altered decoder arrays as original neural evidence. Change only selected receptor activations; preserve all other node fields, connections, operator states, energy, clocks and pending signals. Then deliver the ordinary environment/question, run Core and read genuine bus output. Originals remain intact.

| Intervention in actual Core copy | Own-history correct | Opposite-history correct | Observation |
| --- | ---: | ---: | --- |
| Normal | 25/32 | 3/32 | Baseline |
| Clear five teacher-marker receptor activations | **16/32** | 16/32 | Both histories now make identical choices |
| Transfer only those five activations from opposite history | **3/32** | **25/32** | All32choices equal the donor-history baseline |
| Transfer five own-pointer receptor activations | **25/32** | 3/32 | Choices unchanged |

The teacher marker was genuine past sensory input, not an injected history label or current-answer leak. Its residue is **real short-term Core state**, and its causal influence is established. But the external reader can use that small residue to choose an already supervised answer rule. That is a more direct explanation than transferable object concepts learned inside Core. Other unread memories are not ruled out.

Intervention magnitude is an important limitation. Both swaps select five nodes,
with three activation values actually differing. Summed absolute changes are
about 1.668 for marker receptors but only 0.000426 for own-pointer receptors.
The latter is **count-matched, not amplitude-matched**. Its unchanged choices do
not show that equally large perturbations elsewhere would have no effect. The
strong evidence is that this restricted marker-state exchange reproduces every
donor choice, not that all alternative pathways have been exhaustively excluded.

Offline diagnostics cover all predetermined vision, text, marker, body/environment and four activity-field groups. Every result is retained. Source279 scores 23/32 normally and 15/32 when teacher-marker fields are zeroed offline; swapping those fields gives 5/32 for the recipient history and 23/32 for the donor. This also implicates that information route. Altered offline arrays can be unnatural combinations and are not equivalent to actual Core interventions. Actual activation interventions were performed only in the first source; do not imply full causal replication in both.

## 5. Why movement occurs without consciousness activity

Freeze the original E56 reader, create no Core, and retain all 24 physical scenes, wind and body. With all-zero eight-frame input, the shared field decoders face identical inputs; selection still forces an argmax, taking the first entry on a tie. It selects slot 0 on all 24 trials, coincidentally correct on 6. The downstream servo issues 960 nonzero commands, with maximum displacement 1.443 m.

A separate control delivers no frame, makes no decoder call and issues no motor command. It produces zero commands; passive wind drift reaches about0.070m. **Zero-valued input differs from no input/no selection**, and commands must be distinguished from passive motion.

The present selector has no abstention/no-intention result. Its mechanical selection is neither a Core intention nor evidence of an acquired conditioned response. This is a controller-definition issue; the experiment does not silently add a production intent gate or modify dynamics. The earlier Core-absent interval-circling control remains in [E56](../2026-10-06-vision-correction/report.en.md).

## 6. Does less external practice increase Core's contribution?

The user proposed a useful learned fast-response interpretation and accepts joint decisions, while retaining the attribution requirement. Hold the same60supervised examples and all Core experiences fixed; vary external optimization over100/300/1200steps. This does not reduce Core lesson repetitions and is not a biological demonstration of a conditioned reflex.

| External steps | Normal Core, individual seed scores | Same frozen heads reading existing-edge-silenced activity | Direct sensory bypass |
| --- | --- | --- | --- |
| 100 | 16,16,22 /24 | 12,11,21 /24 | 23,24,23 /24 |
| 300 | 24,22,23 /24 | 19,18,20 /24 | 24,24,24 /24 |
| 1200 | 24,23,23 /24 | 19,18,20 /24 | 24,24,24 /24 |

Across the three fits, silencing loses14,12,13previously correct answers respectively; the100step condition also gains4. Rescue restores all original choices. There is no consistent trend that less external training makes Core more decisive; normal fitting mainly deteriorates. Summed72evaluations repeatedly use the same24questions and are not72independent tests. Optimization count does not change inference architecture; no faster-inference claim is made.

## 7. Judgment and next steps

1. **Finite system-level pointing works; Core-originating conceptual recognition is unestablished.** There is a sufficient external recognition route. The strong description of a motor centre merely translating Core intent is not supported by this implementation and experiment.
2. **Core short-term history influences answers, with a concrete mechanism located.** Five residual teacher-marker receptor activations control first-source history selection. This does not establish logic, object concepts or autonomous pointing intent.
3. **Less external optimization is not an immediate remedy.** Learned external responses can be useful and joint control is acceptable, but total accuracy cannot stand in for new Core capability.
4. **This does not decide that ThreeMind as a whole is useless.** The present task admits a Core-free solution; its task design and division of labour therefore do not establish a need for Core. Evaluate E50 and ocean interventions on their own evidence, neither erasing them nor borrowing them as proof for this task.

Retain the shared selector as an explicitly named external-recognition baseline. A next task should hold current input and reader fixed, teach only Core a new association, and balance the final demonstrations and their residual activity. Avoid supervising both complete answer tables and then allowing a residual history cue to select between them. Test retention, correction, relevant-pathway silencing/rescue and transfer against direct-input and simple short-term-memory controls. If this still fails, locate the learning or reading limitation before altering Core.

Separate object selection from action execution. Validate absent-intention handling and real continuous closed-loop control separately. **No intent gate or Core modification was introduced to manufacture success.** Visible self-limb, genuine Core-controlled circling, energy-based motivation, long retention and unseen relational transfer remain open; they were neither forgotten nor claimed complete.

## 8. Reproduction, resources and delivery

Closed on 2026-10-07: 113 completed stages, 588 new source/fork creations,
**71.69 minutes** of registered computation, and no incomplete cases. This remains
below the 600-creation/90-minute bounds. Pre-archive working evidence occupies
about **0.755 GiB**; final archive/database totals are recorded in delivery and
remain subject to the 4 GiB hard bound. Shared account usage moved from 74% to
76%, including other tasks, below the registered extension/computation limits.

Six targeted tests pass: raw sensory controls exclude answer metadata,
conflicting-history scoring, channel-aligned transfer with source preservation,
shared-field permutation and reader validation boundaries. New scripts compile.
A single complete input audit checks 26 paired conditions and 8,320 paired
stimulus frames. Six actual-state intervention snapshots preserve every saved
field except the registered activations. No repeated whole-evidence hashing is
used in place of scientific analysis.

The new project is **E57 指认答案的内核与外设归属**, ID
`e7606f95-62ea-4645-badd-46bdcf54ec47`. Bilingual designs/reports, execution notes
and complete evidence are saved separately. The archive includes the specific
historical E56 reader, state and features actually used, without changing their
originals. The bilingual backlog and histories, including both Classical Chinese
adaptations, are updated. No new film or UI change is included; lab checks are
not claimed as acceptance of a new UI.

Original registration remains intact. C/D/E/F additions and the source279environment correction were recorded before execution. Merely changing the Core seed was found inadequate: under this configuration it only affects an unused optional spatial substrate. Before source279was run, its weather seed changed47→103while mapping, curriculum and within-source pairing stayed fixed. Source223was untouched; there was no post-result weather selection. Two environmental sources are not two independent populations.

Only experimental and reusable lab tools were added. Core dynamics, defaults, old instances and old experiments were not changed. Teaching, actual input, activity, snapshots, intervention receipts, weights and every prediction are retained. Complete input equality is checked once where causal attribution requires it, without repeated scans or redundant hashing of old evidence.

[Commands](README.md) · [All results](results.json) · [Input equality audit](input-audit.json) · [Research plan](../../../docs/en/plans/choice-attribution.md) · [Backlog](../../../docs/en/plans/research-backlog.md)

## 2026-10-07: system-continuity scope note

This study fits then freezes one head for Core-history, silence and transfer comparisons; separately fitted sensory readers are explicit controls. These conditional causal results remain and do not require a blanket rerun because of E61. Offline fitting and frozen evaluation are not co-development from birth; repeat key attribution controls in the integrated successor.

[Continuity audit / 连续性核查](../../../docs/en/plans/system-continuity-audit.md)
