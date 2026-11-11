# E69 motor-training audit and conditional improvement plan

October15,2026, Beijing time. Liu Dongxu raised the question and authorized the conditional sequence below. AI checked code, historical reports and committed originals. The current E69 continues its frozen curriculum; this audit does not replace the subject, peripheral, training method or Core.

**Later same-day clarification takes precedence:** The user supports keeping target recognition out of a motor intention reader. Complete E69 normally unless a clear major training degradation is identified. If sampling has substantial impact, evaluate a current-study branch versus a later blank-subject study. A branch may combine several evidence-backed improvements to test overall benefit first; component attribution comes later. A visual center that recognizes targets, converts results into stimuli for Core, and feeds Core responses to motor control is deferred until after E69 for discussion, not execution now.

## 1. Historical capability and the intended division of work

The user intends internal Core activity to determine intention, a motor adapter to translate it, and a body driver to execute it, as recorded in the [October7 control boundary](../2026-10-07-continuous-development/control-boundary.en.md). Continue the current experiment. If coordination, especially pointing, remains poor and a training problem is established, improve hand training using the earlier four-field experience. If hand capability improves but coordination remains poor, inspect gaze training and, if necessary, start a new blank individual to compare faster/better gaze learning, followed by hand, coordination and shape/color learning.

| Reference | Actual method and result | Difference from E69 |
|---|---|---|
| E54 separate motor preparation | 32 demonstrations,864 action samples;28/32 new visible-marker targets reached | A single motor interface was tested first. Language pointing was only2/32, a different result |
| E56 four-field pointing | One shared reader scores four physical fields; a position servo executes the selected location;24/24 new-layout choices and arrivals | No separately learned gaze orMOVE/WAIT. The successful reader was separately calibrated, not inherited by E69 |
| E69 | A fresh/5.1 Core and personal peripheral;68 receptors in a moving eye; independent eye/hand locations andMOVE/WAIT, updated every0.5s, with servo execution | Adds changing coordinates, action timing and joint learning; no separate hand preparation stage or old trained motor weights |

[E54 report](../2026-10-06-shape-color-pointing/report.en.md) · [E56 report](../2026-10-06-vision-correction/report.en.md) · [E69 frozen design](design.en.md)

E56 establishes accurate system-level pointing. [E57 attribution](../2026-10-06-choice-attribution/report.en.md) also found recognition performed by the reader; historical24/24 does not establish a pure translation of an independently formed Core intention. Reuse effective engineering separation without inheriting an unproved causal interpretation or old per-question restoration/peripheral replacement practices.

E69 already has a low-level servo: `system.Executor` maps a selected receptor to an eye angle/hand target and applies physical feedback. Core is not directly learning each motor force. Diagnose target reading, timing, coordinates, execution and maintenance separately.

## 2. Read-only findings

Derived evidence: `E:\ThreeMindData\experiments\2026-10-13-eye-hand-shape-color\continuations\r1\.continuation\reviews\motor-training-20261015\audit.json`. [motor_training_audit.py](motor_training_audit.py) inspects frozen labels, saved scores and optical geometry without importing Core, loading a subject/peripheral or running the physical world. Every corpus reference in both fit plans passes its hash; counts match original fit receipts. The geometry sample was fixed in advance: trials0,5,12,23 from each of two development rounds, eight clips/960 frames, not a representative population estimate.

| Motor calibration | All samples | WAIT labels | MOVE/hand-location labels | WAIT fraction |
|---|---:|---:|---:|---:|
| Initial coordination fit | 6,516 | 6,027 | 489 | 92.50% |
| After correction1 | 8,460 | 6,757 | 1,703 | 79.87% |

All5,616 retained gaze samples areWAIT. The current sampler uniformly draws from all old/new examples; the action-classification loss is not class-balanced. Hand-location loss usesMOVE examples and is separately averaged within that subset: **20.13% of examples does not mean20.13% of loss weight**. The imbalance and minibatch coverage are established conditions, not yet a measured causal explanation for persistentWAIT.

Training labels permitMOVE only after stable fixation of the true target; before that, the hand label is-1 and contributes no position supervision. Consequently gaze difficulties also restrict unassisted hand-location examples:21/432 initial coordination windows and134/864 post-correction windows. The468 and1,080 assisted windows are allMOVE, showing a demonstration/autonomous-state distribution difference. A temporal encoder is shared across eye/hand location and action classification; interference remains a hypothesis requiring a separate test.

Autonomous coordination is0/24 initially and0/24 after correction1, with all192 new hand decisionsWAIT in each round; eye scores are6/24 and1/24. Between them,96 unassisted sampling trials produce67MOVE decisions in19 trials, but both overall successes are initially-at-target maintenance. Complete new-arrival coordination is0/94. Two eligible timing passes fail terminal hand maintenance. These are classifications of saved results, not a newly completed independent frame-level scoring replay.

In the illustrative geometry sample, a correct receptor-center ray can miss the requested tabletop point by up to0.487m when the target remains peripheral, exceeding the0.15m scoring radius. At some saved poses no receptor center represents an endpoint inside that radius. All140 sampled frames with the target inside the central region avoid this excess. This separates poor fixation from coarse endpoint representation; it neither explains allWAIT nor equates static ray error with actual movement error. Existing preflight primarily checks16 ideally centered geometries, not every moving-eye pose or complete hand-arrival trajectory.

## 3. Authorized sequence and current checkpoint

1. **Continue current E69.** Preserve the individual and all experience, personal weights, Adam/RNG, body and executor. Review after the frozen coordination stage's maximum three correction rounds and full retest; absent a clear major method obstacle, continue through shape/color and final tests. Pause or branch at a complete boundary only when an important training/apparatus problem is established and an independent comparison is ready. Low scores alone do not authorize rebirth, rollback or in-place curriculum edits.
2. **Separate hand execution from selection.** Independent apparatus calibration should cover eye poses, chosen rays/targets, hand starting states, inertia and wind. Calibration truth must never reach formal inference/servo as the correct answer. Measure selected location, commanded endpoint and actual arrival separately; preserve body dynamics andCore.
3. **If performance remains poor and a training obstacle is established, register a separate improvement branch.** Preserve a complete reference and branch only from the then-latest complete state. Candidate improvements include stratified/balanced sampling, hand-only demonstrations and answer-free requests, old-example rehearsal, and separating hand-target learning from timing practice. The later clarification permits bundling evidence-backed improvements into one bounded branch, testing aggregate benefit before separate attribution experiments. Keep old samples and personal weights/optimizer; disclose each change and rationale, without attributing a bundle benefit to one component. Any necessary new adapter architecture must have an explicit version and initialization, never silently replace the baseline.
4. **Validate hand capability before coordination.** Improvement must include entering from outside and stable arrival, followed by held-out layouts; lower fitting loss, maintenance or a transient crossing do not substitute. Eye and hand remain independently controlled: no answer-dependent release gate and no automatic copying of the eye choice to the hand. Distinguish intention reading, actuator calibration, hand capability and eye-before-hand behavior.
5. **Only if the hand improves but coordination remains poor, conduct the conditional blank-subject gaze comparison.** Check whether gaze training also confounds intention reading and execution calibration. If so, start a new explicitly identified blank/5.1 individual with its own peripherals; never import an old grown Core or another individual's learned mapping. Generic apparatus calibration may be reused with disclosure. Compare internal seconds, teacher lessons, calibration updates and wall time to reach20/24 development gaze, scores at equal teaching dose, retention and held-out layouts. Original E69 reaches20/24 at4662 internal seconds; this is a study reference, not a universal success threshold.
6. **If the new gaze method is faster and better, continue that same new individual through hand, coordination and shape/color learning.** Authorization is not a result. Preserve negative outcomes rather than unlimited teaching or Core changes. Disclose actual branch/new-birth scope before execution and results afterward; existing authorization need not be repeatedly requested. Additional rollback, Core edits and architecture changes beyond this scope still require consultation.

This is an authorized conditional route; no new training branch has been started. Sample/label differences are established, but their causal performance cost is not yet quantified, so they do not currently trigger a mandatory stop or fork. Frozen live source, curriculum, modules, Core and guard limits remain unchanged. Monitoring retains the method checkpoint, stays quiet without material changes, and completes original E69 normally in the absence of a clear major obstacle.

A later visual-center candidate may perform partial/full recognition, convert its outputs into declared sensory stimuli for Core, then pass Core responses to motor control. Other comparisons can be discussed. This records a research idea only: it does not install a semantic path, silently replace a motor translator with a classifier, or claim that Core thereby determines behavior.

## 4. Evidence locations

- Labeling/loss: `classroom.py:trial`, `lab/tools/continuous_foveal_motor.py:_loss/continue_calibration`.
- Execution: `system.py:Executor`, `lab/tools/active_eye.py:selected_ray`; preflight scope in`preflight.py`.
- Frozen originals: r1`stages/coordination-fit-{0,1}/motor-plan.json`, `motor-023.json`, and`coordination-dev-{0,1}`/`coordination-cal-1/result.json`.
- [Stage results](progress-20261015.en.md) · [Handoff](HANDOFF.md) · [Source/history](../../../docs/en/history/sources/2026-10-13-eye-hand-shape-color.md).
