# Centered-object recognition and body calibration

2026-10-07, R39. User-approved direction after E61; **not yet executed**, and not an established improvement.

## A body that mild wind does not easily move

The user requested a heavier arm or a gentler breeze. Freeze the next batch's physical parameters before teaching. Record mass, driving force, damping, the wind-force model and units; do not rename a dimensionless gain as mass.

Measure zero-command drift, arrival and holding with the existing controller, and responses under different wind forces. Seek a configuration where the breeze remains perceptible without dominating arm movement. Preserve increased inertia and movement cost; do not silently compensate with stronger actions. Determine ranges through a dimensional audit and small calibration, and register the choice before teaching.

The current `advance_physics` uses a unit-mass carriage: velocity changes include `4×action − 3×velocity + 0.15×(wind−velocity)`, with no independent arm-mass parameter. Increasing mass alone mainly changes transients; it need not reduce terminal drift when sustained force balances viscous drag. Audit mass, damping and wind together. Toys already have separate masses, which are not arm mass.

Wind components are bounded by 0.8 and 0.5 metres per second, giving a speed upper bound of approximately 0.94 m/s. The environment does not simulate a gale. Audit the simplified carriage's mechanical response and accumulated drift rather than inferring excessive wind speed from motion alone. Static friction or a more realistic supporting structure are next-batch physical candidates, not immediate changes to the old world.

E61's quiet condition retained wind and therefore passive movement and contact. It was not a no-experience condition. Do not alter its registered gravity, mass, wind or sensory mapping mid-study. Version and save future physical changes so old worlds retain their original restoration behavior.

## Isolate recognition from eye–hand coordination

If coordination remains poor, present **one centered object** during both lessons and questions. Teach colors, shapes, combinations and question forms such as “What is this?” with dense-to-spaced review and corrective demonstrations. Keep physical and proprioceptive background. This branch does not require learned scanning or pointing.

Compare the same reader across untaught, reversed-correspondence, Core-connection intervention and restoration conditions. Normal inference must not receive teacher answers or object classes. Retain raw activity-pattern evidence to separate recognition from expression failure. Decode actual activity without subtracting an uncued clone or filtering for expected answers.

Better performance with one object would implicate selection, gaze or coordination as bottlenecks, without proving they are the only causes. Continued failure calls for separating teaching, internal patterns and expression, not immediately rejecting Core recognition.

## Sequence and boundaries

1. Finish E61 comparisons, attribution and reporting; do not add an unbounded grid.
2. Calibrate body physics; freeze the next configuration, budget and inputs.
3. Test centered-object recognition and answers, including answer attribution.
4. Return to multi-object coordination if supported. Irregular shapes, full embodiment, NPCs, innate selection and energy rewards remain separate registrations.

When returning to body learning, compare one motor center calibrated throughout preschool and teaching against E61's fixed preschool wiring followed by a newly trained Transformer. The latter is an implementation fact and a possible transfer limitation, not a causally established explanation. Retain the old pipeline as a control. Also retain the previously useful shared visual-reading approach for appropriate comparisons, without preselecting objects for Core.

Register sample sizes and thresholds when launching. This plan does not claim unrun candidates are validated.

[E61](body-exploration.md) · [Sources](../history/sources/2026-10-07-body-exploration.md) · [中文](../../zh/plans/centered-object-and-body-calibration.md)

2026-10-07 correction: R40 supersedes treating continuity as merely an optional limitation. Complete-system continuity and body calibration come first, retaining E56. Centered-object diagnostics remain approved, not a required detour inferred from the mismatched E61 primary test.

[R40](system-continuity-audit.md)

## 2026-10-07 follow-up: the next centered-object diagnostic

E62 has calibrated the separate body's mass, damping, breeze and servos; corrective eye/hand confirmation is still running. The user again proposed presenting one centered object during both teaching and questions if gaze remains unreliable: shapes/colors, then combinations and answers, before returning to multi-object pointing. Finish the registered E62 correction/attribution first; do not silently add this task to its curriculum.

The old successful assembly and new whole-eye system differ beyond field of view: object-specific fields and offline shared-reader calibration versus new retinal sampling, temporal architecture, online learning and active eye control. The gap cannot all be assigned to scanning. Centering removes active search, but answer attribution still needs untaught/reversed teaching and fixed-personal-reader connection intervention/restoration.

Register a separate experiment starting blank with its own peripheral, physical background, dense-to-spaced review and error correction. Physical eye fixation/centering must be an explicit apparatus condition, never answer-driven focus or claimed learned fixation. This records an approved direction, not an executed result.
