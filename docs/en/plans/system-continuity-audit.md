# Continuity of Core and peripherals: audit and rerun plan

2026-10-07. R40. **Audit and E61 closeout belong to this phase; integrated reruns are approved for the next phase.** The user allowed closeout before rerunning. No new long simulation is added now.

[中文](../../zh/plans/system-continuity-audit.md) · [Backlog](research-backlog.md) · [Dialogue](../history/sources/2026-10-07-system-continuity.md)

## Finding

E61 used fixed anonymous motor wiring in preschool, teacher-applied forces in lessons, and a newly trained Transformer for assessment. **It was not the same continuously developing Core-plus-Transformer system requested by the user. Withdraw its interpretation as evidence that preschool provides no consistent benefit to that system.** Measurements describe the executed segmented pipeline, not the intended experiment.

Earlier work also contains new readers after lessons or correction. Distinguish instrument calibration, explicit frozen/retrained comparisons, and fixed-reader interventions from an unapproved replacement within ordinary development. Neither discard every prior observation nor defend the mismatched subject.

**Continuity is per individual, not sameness across groups.** Each Core and its own peripheral develops and resumes together; control groups may have different declared architectures or training rules. Applying one individual's learned mapping to another is a transfer experiment, not presumed compatibility. [E46](native-expression.md) already raised individual expression; the [central-adapter definition](../reference/central-adapters.md) already required binding identity and calibration history. This corrects execution drift, not the research goal. Earlier evidence that shared readers can work under particular conditions does not establish universal interchangeability.

Ordinary experiments must preserve the applicable dynamics, hypotheses and established system consistency. Authorized ablation/transplant/disconnection occurs on separate intervention copies with an intact reference, not as a mismatched baseline used to deny capability.

## Scope and evidence

Reviewed committed execution code through `be0855e`, shared fitting/save/restore paths, reports and small E61 result records. Main coverage: E54–E61; traced language peripherals in E42–E52; inspected ocean restore/control paths used by E34, E35–E36 and E53. No old large-data scan, wholesale checksum pass or rerun was performed. This is not a guarantee about every historical branch. Source lines below refer to the audited version. Code establishes resets, not how much those resets changed performance.

| Study | Actual lifecycle | Retained scope | Rerun decision |
| --- | --- | --- | --- |
| **E61 preschool** | `ExploratoryMotor`, teacher-driven body, then new `ContinuousMotor`; `classroom` resets external body/world | Contacts, feedback, commands and scores under that pipeline; same-head interventions | **P0 required:** same full system throughout exploration, teaching, breaks, correction and assessment |
| **E61 caregiver** | Continuous 120+60 s uses fixed wiring; early W reseeding also changed wiring, W2 preserves it | W2 comparisons under fixed wiring; not Transformer joint growth | Keep W as corrected historical evidence. Integrate caregiver transfer after the P0 foundation, without expanding all branches |
| **E60 eye–hand learning** | Teacher acts first, head fitted offline; correction adds data but `fit` constructs another head | Same saved-head silence/rescue changed/restored all 12 trajectories, within that assembly | **P0, combined rerun:** learning/correction in one system, not every nose/architecture branch |
| **E59 active gaze** | Scripted scans in teaching/collection; learned branch installs fitted gaze/hand selectors | Measured foveated-input cost reduction and fixed-head action effects | **P0, combined rerun:** scan-to-controller switch cannot establish failure to learn fixation |
| **E54–E56 pointing/correction** | Teacher/servo actions precede separately fitted heads; E54 expression correction and E56 correction can initialize new readers | Actual 21/24, 23/24, 24/24 performances of those assemblies; conditional same-head ablations | **P1 selective:** retest central shape/color and correction claims after reliable control, not all optical conditions |
| **E57 attribution** | Reader fitted then fixed for history/intervention comparisons; incoming-only reader separately declared | Dependence on Core history under identical current input; peripheral-alone recognition | No wholesale rerun due to E61; repeat key attribution in the future integrated system |
| **E58 memory/feedback** | Frozen and newly fitted readers; 4/16-example feedback conditions independently restore the same baseline weights | Offline readability, fixed-head history effects and limited weight adaptation | Keep original scopes. Independent doses are not a cumulative developmental trajectory |
| **E42–E45 language/senses** | Pretrained or separately calibrated mappings/readers; E44 fits output separately, weak-activity variant can continue weights | Responses, connections and interventions using specified tools | No identical replacement of an already jointly grown Transformer established here; also not proof of joint growth. Do not rerun everything |
| **E46–E51 expression** | Offline individual/shared calibration and frozen transfer; E46 developmental, E49 continued and E50 continue-from paths retain weights, cold starts separate | Calibration, failure of a particular frozen model, limited continued-fit gains | Frozen failure does not refute a plastic integrated system; future joint language study, not blanket withdrawal |
| **E52 adaptive expression** | Restores prior Core, weights and teacher replay; `adapt(initial=...)` retains weights; actual self-hearing. Adam restarts each update, disclosed in manifest | **Real weight continuity**, not random reinitialization each stage; existing tests remain | Not invalidated by the E61 mechanism. Future complete-state continuation includes optimizer/RNG |
| **Inspected ocean paths** | Full-world restore in E34; controller swaps are explicit user-requested variables in E35–E36; E53 uses versioned worlds | No undeclared preschool-to-Transformer substitution in these inspected paths | No ocean rerun for this reason; not every historical branch was audited |

### Source pointers

- [E61](../../../lab/explorations/2026-10-07-body-exploration/experiment.py): `explore/classroom/teach/fit/evaluate`; [W correction](../../../lab/explorations/2026-10-07-body-exploration/withdrawal-correction.md).
- [E60](../../../lab/explorations/2026-10-07-eye-hand-learning/experiment.py): 142–181, 235–258, `correct` at 311. [E59](../../../lab/explorations/2026-10-07-active-vision/experiment.py): `teach` 98, `collect` 142, `fit` 170, `closed` 199.
- [E54](../../../lab/explorations/2026-10-06-shape-color-pointing/experiment.py): 108 and 336–366; [E55](../../../lab/explorations/2026-10-06-grounded-reviews/experiment.py): 137, 228; [E56](../../../lab/explorations/2026-10-06-vision-correction/experiment.py): 155–215 and [shared reader](../../../lab/explorations/2026-10-06-vision-correction/shared.py).
- [E57](../../../lab/explorations/2026-10-06-choice-attribution/experiment.py): 199–223; [E58](../../../lab/explorations/2026-10-07-embodied-memory/experiment.py): 392–415, 449–478.
- [E44](../../../lab/explorations/2026-10-04-language-development/experiment.py): 323; [E46](../../../lab/explorations/2026-10-05-native-language/expression.py): `initial=previous`; [E49](../../../lab/explorations/2026-10-05-bus-expression/joint.py): `continued`; [E50](../../../lab/explorations/2026-10-05-graph-expression/multiview.py): `continue_from`; [E52](../../../lab/explorations/2026-10-05-coadaptive-language/experiment.py): 179–233 and [AdaptiveExpression](../../../src/threemind_transformer/adaptive_expression.py).
- [Ocean restore](../../../lab/tools/ocean_community.py): 28–61; [group copy](../../../lab/tools/ocean_groups.py): 116–130; [explicit controls](../../../lab/explorations/2026-10-04-ocean-groups/experiment.py).

## Missing continuity support

`ContinuousMotor.fit` creates AdamW and restarts sampling RNG each call. Its saved artifact contains model weights/metadata, not optimizer or sampling position. `SensorimotorSession.snapshot` contains Core, reader, world and dt, **not current raw output or recent history**; those are empty after restore. Keeping a deque in memory does not save it.

Task/classroom setup also resets posture, velocity or world. Independent assessment copies can legitimately do that when specified, but ordinary growth cannot silently do it. Offline best-model selection is not a license to roll back only Transformer while leaving a developing Core/body at a later time; any historical assessment must restore the matching whole system.

These findings do not quantify the cause of low scores. They establish that the intended subject was not maintained. Fix tools before interpreting capability or tuning Core.

## Retain the working multi-field reference

The user requires building on the functioning combination. Register **E56 `r4-exposure` plus `r4-exposure-shared-fit`** as the functional reference, indexed in [baseline-reference.json](../../../lab/explorations/2026-10-07-body-exploration/baseline-reference.json). Checked small results, state identity and model metadata; no full rerun.

- Core/world: `.work/vision-correction-20261006/cases/r4-exposure/checkpoint.json.gz`, `continuous-memory/2`, 354 simulation seconds, `grounded-classroom/2`.
- Peripheral: that study's `r4-exposure-shared-fit/controller`, `spatial-choice-reader/1`, shared reading of four physical 4×4 fields using raw activity.
- Action chain: select a position, then a physical servo executes it. **This differs from later continuous-force prediction.** Changing both visual sampling and the output task cannot isolate a visual cause of degradation.
- Held-out layouts: color/shape/combinations each 8/8; actual arrival 24/24. Same-head existing-edge silence 19/24; rescue 24/24. Preserve the attribution limits too.
- Saved artifacts restore that assessment assembly, **not its full historical optimizer/recent-window training state**. Do not invent missing state or claim birth-to-test joint learning. Next phase first makes a small functional check, then uses a new complete-state version.

Keep the multi-field reference intact. A whole-eye group may have its own adapter, retaining useful shared local reading and selection/physical-execution design while developing with its own Core. Do not attach the old multi-field model to incompatible input without adaptation. Isolate visual sampling/spatial mapping, then gaze and feedback; any output/control architecture change is separately disclosed. Existing success is the starting point.

## Next phase

1. **Whole-system checkpoint and body calibration.** New version, old protocols intact. Save Core/queues/clocks, body/world, Transformer weights/buffers/optimizer/step, teacher replay, RNG, recent raw outputs and sensory/actuator identities. Record parent snapshots and change types. A short uninterrupted-versus-restored action/update check is sufficient; no repeated large-file hashing. Calibrate hand mass, support/damping and mild wind before fixing common conditions.
2. **One center from birth.** Initialize once and retain it throughout. If target-free motor variation is needed, record it separately, balance it across applicable controls and do not call it intention. If preschool has no adapter learning signal, say the adapter is not updating then; discuss any proposed self-supervised objective before adding it. Never substitute anonymous wiring to hide the gap.
3. **Explore, demonstrate, try, correct, review.** Preserve body and readout windows between ordinary stages. Teacher moves toys, demonstrates and speaks through normal senses. Record assistance and student proposals separately, fade assistance, continue the same weights and learning state. Inference reads Core activity, not target coordinates, question categories or grading answers. Retain physical background, visible hand, eye/hand proprioception, contact, toy sound and self-hearing. Validation selection cannot replace actual lessons or dense-to-spaced review.
4. **Minimal comparison.** Two sources, each split from a complete initial system into exploration and matched environment arms; same subsequent teaching while preserving each system. Measure independent eye movement/fixation/retargeting, hand and joint control, and correction gains. Do not start nose, NPC, reward and innate-selection branches simultaneously.
5. **Core attribution.** Complete post-teaching copies: normal, selected-edge silence, matched intervention and rescue with the same peripheral. History transplant is an explicit intervention. Record full trajectories and transient responses. Assessment copies do not write back into the developmental line.
6. **Shape/color and centered-object fallback.** Recheck central recognition, correction and answer ownership after basic control improves. If coordination still blocks testing, use the independently approved single centered object diagnostic; it does not replace continuous-system testing.

Proposed next-phase budget: one worker, first source then second; 90 minutes stops expansion, 150 minutes stops new simulations; at most 96 complete-system creations/restores, new evidence 3 GiB soft/4 GiB hard, process 4 GiB, reserves RAM 2 GiB/C 5 GiB/E 15 GiB. Refresh account baseline at launch, +4 percentage points stops expansion/+6 stops new simulations, including shared usage. This is a proposal, not an executed run. Amend before execution if pilot timing warrants it.

## Communication and status

The user requires advance explanation/agreement for replacing or resetting components or control paths, not a late limitation. This is now in project `AGENTS.md`; already approved ablation/transplant/cold-start controls remain authorized.

Confirmed: controller changes, some correction refits from new heads, missing training/history state. Completed now: correction, source audit and rerun priorities, with E61 evidence retained and replay/report warnings. **Not completed: whole-system tooling, integrated rerun or its capability verdict.**


## 2026-10-07 update: repair and bounded retry completed

The earlier unfinished status describes E61 closure. E62 now delivers complete-system tools, nine focused tests and one-source direct teaching/correction; successes3/12 fall to0/12 with existing-edge silence and return to3/12 on restoration. Exploration was interrupted by memory pressure. Reliable control, shape/color and matched preschool remain incomplete; engineering repair is not capability completion. [E62 final report](../../../lab/explorations/2026-10-07-continuous-development/report.en.md).
