# E62: basic teaching with one continuing Core and motor peripheral

> **Revision r2 · 2026-10-10**
> Revision reason: Verified original-file relocation; append location-resolution guidance and preserve the experiment conclusions.
> Original: [report.en.md](report.en.md); parent r1: [report.en.md](report.en.md)


2026-10-07 study batch. Original E61 evidence and its correction remain. Research project: `55e5260f-a406-4aa8-8549-66c4b0aa30e9`.

## Main result

**Controller replacement is repaired, but this whole-eye continuous-teaching assembly has not learned reliable eye/hand control.** After156 lessons the primary unassisted test finishes within target in1/12 trials, entirely from an already aligned start:0/12 new entries from outside. Keeping the cue visible yields one actual new hand arrival but still1/12 completed trials. Error-contingent teaching of the same whole individual yields3/12 endpoints on retest. Assisted demonstrations are not counted as independent success.

The original working E56 assembly still passes6/6 choices and physical arrivals in a short independent recheck. New individuals inherit neither its Core nor peripheral. The assemblies differ beyond field of view; this is not evidence that whole-eye vision or ThreeMind's theory is impossible. New shape/color examinations and a valid matched preschool comparison were not reached.

**A positive causal finding remains: all three post-correction successes require existing internal connections in this fixed-reader test.** Silence changes3/12 to0/12; restoration returns3/12 and every command/body value across960 frames. Those successes were not produced by the peripheral independently of the connections. Specific memory content and local associative pathways have not been isolated.

## What was actually preserved and taught

`developmental-system/2` saves Core, delivery/readout history, body/sensors, personal Transformer, Adam, replay, RNG and curriculum cursor. Normal stages retain the same weights and optimizer, without best-head rollback. Blank Core and random personal peripheral receive156 lessons over416simulated seconds: look, point and combined actions in four directions; each first appears ten consecutive times, followed by interleaved reviews with2/6/18s gaps. There are2027teacher examples and4054optimizer steps. Assistance decreases0.8→0.2 and is zero during evaluation.

Correction continues the same taught individual:12 attempts, with11endpoint failures receiving three demonstrations at0.7/0.4/0.1 assistance and a2s physical interval. The original peripheral reaches4912updates. Shared physical retinal-cell reading does not crop named objects. The reader selects eye/hand poses; a servo executes those selected poses without consulting scoring answers. The2kg hand,5N·s/m damping,12N actuator and one-tenth original wind are a separate world version. Visible hand, eye/hand proprioception, touch, toy sounds and environmental background remain. Core dynamics/defaults and old instances are unchanged.

[Historical workflow](recovered-workflow.en.md): E54 independently calibrated a motor interface. E56 calibrated its shared reader after Core concept teaching and before evaluation; no evidence establishes inheritance of the E54 head. Here direct teaching omits unsupervised preschool, not basic motor calibration.

## Unassisted behavior

Twelve trials per condition, four each for look/point/both,4s per trial. Registered tolerances remain0.075rad and0.20m. Single-effector tasks score the requested effector; the other remains recorded, so scores do not alone establish independent control. Primary cue duration is0.75s; the supplementary visible-cue condition uses4s. Eye measurements are pre-action observations and hand endpoints follow that50ms action; preserve that original scoring convention rather than claim exact simultaneity.

| Condition | Endpoint | Ever entered | Entry from outside | Mean eye endpoint error/rad | Mean hand endpoint error/m |
| --- | --- | --- | --- | --- | --- |
| After teaching, brief cue | 1/12 | 1/12 | 0/12 | 0.249 | 1.010 |
| After teaching, visible cue | 1/12 | 1/12 | 1/12 | 0.239 | 0.601 |
| After correction, brief cue | 3/12 | 3/12 | 3/12 | 0.230 | 0.759 |
| After correction, existing edges silenced | 0/12 | 0/12 | 0/12 | 0.214 | 0.950 |
| After correction, restored edges | 3/12 | 3/12 | 3/12 | 0.230 | 0.759 |

The primary test's single endpoint success starts already aligned. Continued cue visibility reduces mean hand error1.010→0.601m but does not make control reliable; eye error changes0.249→0.239rad. This motivates separating visible-target control from post-cue retention, without identifying a specific Core defect.

Read-only inspection of256 retained supervised examples gives pose MSE0.0430, median hand-target error0.168m and median eye error approximately0.050rad. Neither Core simulation nor fitting occurred. These are training-cache scores, not held-out behavior or intent truth. Independent closed-loop performance is substantially worse.

Frozen-record cross-reading identifies an adapter issue: continued fitting to new examples degrades translation of earlier examples. With pre-correction weights, MSE is0.0430 on the old cache and0.3752 on the correction cache. Post-correction weights yield0.1365 and0.00553 respectively. The old inputs are literally unchanged, so the old-cache degradation belongs to the adapter update, not a changed Core rerun. New-cache fitting improves, but neither cache is a held-out behavioral test. The current FIFO retains256 recent examples. Better cross-stage retention within the same personal peripheral merits testing, without yet claiming this buffer policy is the sole cause or changing this batch's model.

## Contribution of internal connections

From identical complete starting states, keep the personal reader fixed and compare intact existing edges, temporary silence of those edges and unsilencing before testing. Environmental starting conditions/rules and requests match; sensory feedback can naturally diverge after different actions. New connections may still form; this is not removal of Core or permanent prevention of all future transmission. The original recent activity window is retained.

- silence: commands differ in 958/960 frames and body state in 958/960; maximum command difference 1.7962, comparison tolerance 1e-7.
- rescue: commands differ in 0/960 frames and body state in 0/960; maximum command difference 0, comparison tolerance 1e-7.

Changed commands establish an internal causal influence; task benefit must be judged separately from the table. Low intact performance cannot establish accurate intention translation. No local transplantation was performed. [The user's motor-center proposal](control-boundary.en.md) remains the target: internal choice, peripheral translation, physical execution. Raw-Core-only inference is implemented, but direct sensory activity may still permit recognition by the adapter.

## Failures and delivery

An initial pilot paired new teacher targets with preceding pre-prompt activity. It was disclosed, stopped and retained; [timing correction](timing-correction.en.md) defines the new supervision point. A corrected exploration run stopped under external compression-induced memory pressure. Per the user's instruction, new simulation waited until compression finished. Its incomplete teaching cannot evaluate preschool benefit. The visible-cue evaluation completed all twelve trials but encountered a final directory-rename permission error. Its complete snapshot and scores were recovered from original files without rerunning; the original failure remains. See [resource interruption](resource-interruption.md) and [save recovery](save-recovery.md).

This report covers9completed stages,16creations/restores and91.20compute minutes, including failed attempts and counting the recovered case once. One simulation worker, actual CUDA Transformer computation and native CPU Core; memory/disk/account guards remain under the [registration](design.en.md). Storage/publication figures are in `delivery.json`. Historical data are preserved.

The last preregistered rescue began before the90-minute expansion boundary and completed at91.20minutes; no further simulation started. Account usage moved14%→18%, conservatively including shared consumption, reaching the+4point expansion boundary. The150-minute/+6point/4GiB hard limits remain; their remaining room is not used to expand this batch.

Reusable tools provide full-system/curriculum continuation, ongoing personal motor learning, physical servos, read-only calibration and complete recorded replay. All formal teaching, corrections and successful/failed tests are included with assistance provenance and existing PNG/WebM capture controls. Browser visual acceptance and a rendered recording are not claimed. [Engineering verification](verification.md).

## Remaining work

Prioritize reliable visible-target gaze/holding, then cue removal, retargeting and joint movement, always preserving each individual's own peripheral. Compare supervised, independently encountered and post-correction activity to localize translation error, forgetting or closed-loop distribution change; none is isolated yet. Only then expand shape/color, centered objects and deformed shapes. Matched preschool controls, the second source and localized transplantation remain unperformed. Keep E56's working result and its adapter-contribution qualification. Repairing continuity does not by itself guarantee learning, and this new failure does not erase earlier abilities.


## Same-day follow-up: rehearse old and new demonstrations

The user proposed strengthening earlier correct translations alongside corrections. Accepted as next-batch R41: compare recent-only and historical mixed rehearsal within the same peripheral, matching update counts and capacity. Exclude held-out answers; no head reset or Core-forgetting change. No additional training was added beyond this batch's expansion boundary. Coordinate with centered-object diagnosis. [Plan](../../../docs/en/plans/motor-rehearsal.md).


> **Storage-location revision · 2026-10-10**
> This edition adds the verified move of the selected originals to `E:\ThreeMindData`. Stable scientific identities and hashes, experiment dates, measurements and conclusions remain unchanged. Paths in the preserved body describe historical sources; use the registered evidence resolver for current locations. Repository documents and frozen fixtures remain in place, and source copies are retained. Structured query data and running checkpoints remain in the database. This annotation does not assert that missing historical evidence was recovered.
