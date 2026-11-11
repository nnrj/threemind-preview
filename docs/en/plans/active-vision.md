# E59: visual focus, saccades and eye–hand coordination

Recorded and authorized 2026-10-07. Status: engineering and bounded controls completed; teaching repair, reliable recognition and extensions remain open. [中文](../../zh/plans/active-vision.md)

## Questions and boundaries

Retain the whole scene while reducing sensory/connection cost with a sharp center, coarse periphery and a genuinely moving eye. Do not crop known objects or program the eye to follow the correct hand target. The user's prediction that associative touches rise during scanning is a hypothesis to test, not an existing result.

E58 continued external learning and whole-scene shape failure are separate experiments. Supervised reader updates helped new mappings while sacrificing some old examples; shape failure in both Core and direct-input groups has not been attributed to one attention mechanism. The old four fields arrived together, rather than through four real saccades. Preserve E58 data and criteria.

Separate optical sampling, bodily eye movement and internal competition. Keep the old amplitude-TopK gate disabled by default. Preserve continuous local competition, inhibition, forgetting, facilitation settings and timing. No new global Core attention or semantic connection deletion in this phase.

## Authorized sequence

1. Build a versioned foveated sensor retaining the complete scene, visible self, physical teacher marker and ongoing physical background. Reuse fixed retinal port identities across eye movements and supply measured angle/velocity feedback. Audit repeated delivery, identity growth, co-observation association, nonzero background surfaces and display cost. Unchanged ongoing stimuli must not disappear under the guise of compression.
2. Compare fixed gaze, answer-independent scanning and Core-output-controlled gaze. Record optical angles, actuator limits and sampling clocks. Teacher targets are training/scoring data only; inference receives no object IDs, correct coordinates or answer count. Eye and hand outputs remain independent, including staying still.
3. Use short lessons, at least ten initial repetitions and later increasingly spaced reviews with ongoing background. Test color, shape and combinations in held-out layouts with frozen readers; distinguish closest-object choice from physical arrival. Direct-input, absent-output, connection-silencing and rescue controls separate external recognition, execution and Core contribution.
4. Record eye/hand trajectories, inputs, direct/associative touches, inhibition and local activity together. Investigate timing and then targeted causal interventions when behavior warrants them. New visual input can itself increase activity; a rise alone does not demonstrate internal deliberation.
5. After regular shapes work, test unseen deformations with varied positions/colors/scales. Separate single choice, plural positive and plural negative questions. Test spontaneous transfer before correction, then teacher feedback and fresh examples. Score omissions, false/repeated points and stopping without giving the controller the number of correct answers. If prerequisites fail, report the obstacle instead of expanding blindly.

## Tooling and compute

Reuse buses, MuJoCo, raw activity streams and individual external motor readers. Expose sensing, control, restoration/replay, growth diagnostics, joint traces, deformation scenes and multiple-choice scoring through Python/CLI. Use GPU batches where beneficial, including transfer cost; keep Core equations/precision/scheduling unchanged. No claim that the production world editor already supports the new laboratory apparatus.

One worker, 180 cumulative compute minutes, at most512new instances/branches,4GiB process RAM;6GiB combined evidence/database growth stops simulations,8GiB hard ceiling. Reserve2GiB available RAM,C:5GiB,E:15GiB. Shared usage begins80%; stop expansion85%,new simulation88%,refresh at least every30minutes. Any resource amendment is recorded before exceeding the original bound. No old-data cleanup or overwrite; staged local commits,no push.

Detailed registration: [E59 design](../../../lab/explorations/2026-10-07-active-vision/design.en.md). Sources: [dialogue](../history/sources/2026-10-07-active-vision.md),[E58](../../../lab/explorations/2026-10-07-embodied-memory/report.en.md),[Transformer](https://arxiv.org/abs/1706.03762),[recurrent visual attention](https://arxiv.org/abs/1406.6247). These papers motivate candidates, not proof of ThreeMind gains. Lower sampling may still accumulate dense connections over time; new association rules require separate discussion/versioning. A successful eye is not automatic authorization for global Core attention.

## 2026-10-07 · Measured update

E59 engineering and bounded controls completed: after ten simulated seconds, uniform whole vision used 1,080,548 edges/100.5 seconds, the new scanning eye 87,888/11.5, approaching old four-field cost. Core, defaults and evidence remain unchanged. Central shapes are optically distinguishable, but targets spend only about 14% of scanning time in the sharp center; fixed/scanning Core readers score 8/24 and 5/24 nearest, below the expansion gate. Reading all sixty samples does not improve fresh holdout performance. Closed-loop normal/silenced/empty-command scores are 4/12, 5/12 and 4/12 with zero arrivals. Silencing changes all twelve endpoints and four choices; rescue restores endpoints. Internal influence exists without an established correctness benefit. Each group receives 104 lessons. Teachers were not omitted, but increasing round delays does not ensure expanding per-concept review, and error-specific correction is still missing. Next priorities are per-concept review, demonstrated fixation and teacher correction before deformation/plural/negative pointing. Reusable tools, CUDA fitting and complete teaching/control replay are delivered; production editor controls and global Core attention are not implemented.

[Report](../../../lab/explorations/2026-10-07-active-vision/report.en.md)
