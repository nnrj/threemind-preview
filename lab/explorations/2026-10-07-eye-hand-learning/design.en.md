# E60: learning eye movements, fixation and eye–hand coordination

Registered 2026-10-07, before execution. Results will be reported separately. [Discussion](../../../docs/en/history/sources/2026-10-07-eye-hand-learning.md).

E59 reduced visual cost but did not establish reliable fixation. Receptor selection, fixed/scanning teaching and learned control are different tasks. This study prioritizes a shared continuous motor adapter, with independent adapters as a comparison. Physical actuator addresses remain distinct; no Core regions or hidden eye/hand intention tags are assigned.

Preserve continuous-memory/2, defaults, text normalization, anonymous mapping and old evidence. Keep the complete four-object scene, visible self, simulated wind, temperature, humidity, gravity support, inertia/contact, eye angle/velocity/power. No CPU telemetry, semantic gate, baseline subtraction or per-example rescaling. Do not re-investigate the already clarified preset-scan video.

Adapters consume only ordered raw activation/inhibition/direct/associative output fields. Task type, target coordinates and answers are used only by the external teacher, supervision and scoring. Ordinary teacher words enter Core through its text sensor. Missing-output interventions are recorded; zero motor command does not erase inertia.

## Sequence

1. Mechanical turn, stop, hold and retarget calibration. Add an optional head-fixed nose in a /5 world; ordinary ray intersections encode its RGB/range. Preserve /4 restoration. The nose is peripheral at forward gaze, not a screen crosshair; eye rotation changes its retinal projection.
2. Reusable joint/separate continuous motor readers, per-skill spaced teaching and process metrics/CLI. One temporal representation emits four components in the shared case; two representations emit two each in the independent case. Report parameter counts instead of pretending capacity is exactly identical. Permit zero action; no forced argmax or hard fixation timer.
3. Four skills: look only, point only, both, hold. Ten consecutive three-second lessons per initial skill; subsequent onset intervals are 6, 12 and 24 seconds for that skill. Keep the world/background throughout gaps. Vary direction/layout. Assisted bodily demonstration is explicitly teacher-driven. Preserve the complete instance after 52 lessons.
4. Fit both adapters on the same demonstrations, CUDA with CPU fallback. Separate demonstration validation selects adapter checkpoints, never a substitute for Core teaching or test-based instance selection. Sixteen fresh, balanced closed-loop trials include a target change.
5. On separate practice cases, let the pupil try and then provide corrective teaching. At most two rounds of sixteen cases. Cross old/new adapters with before/after Core snapshots to distinguish experience from external recalibration. Final holdouts never enter correction or selection.
6. Freeze adapters for output interruption and existing-edge silencing/rescue. If needed fit an explicitly labeled direct-input bypass on the same labels. Expand successful basic control to longer fixation, cue removal, small nose comparisons and a second environmental source; otherwise retain a bounded nose diagnostic or state that it was not executed. Do not expand without limit.

Eyes and hands may move separately, together or remain still. During assisted demonstrations the inactive organ is held at its starting pose, but no task-specific gating exists at test time. Record action provenance for each frame; replay clearly identifies teacher assistance, Core-driven control, bypass, interruption or preset control.

## Measures and interpretation

Measure target occupancy in the physical sharp field (half-width .075), angular error/velocity, entry latency, continuous residence, retargeting and unintended effector motion. Also report occupancy with speed below .08 rad/s. This is a motor measurement, not a Core convergence rule or an 800ms requirement. Report hand distance, occupancy within .20m and drift during hold tasks. Keep every trial, failure, activity sample and intervention, not only final nearest-object scores.

Separate turning, stabilizing and choosing. Constant central output is not successful fixation. Visible cue tracking is not color/shape understanding; retention after cue removal and language-only selection are separate findings. Activity alone is not labeled intention. Frozen-reader intervention/rescue locates its causal control contribution, while teaching-specific changes are needed to attribute learned task relations. Existing consciousness criteria are unchanged.

## Budgets

One worker; at most256 creations/restores;150 compute minutes including failures; process4GiB, GPU60%; reserve RAM2GiB/C5GiB/E15GiB. New local plus database evidence:6GiB expansion stop,8GiB hard limit including archive reserve. Account baseline0%,+5pp stops expansion,+8pp stops new computation, shared usage conservatively included. Persist each stage; never overwrite failures. No Docker or service restarts; no repeated large-data hashing.

Register any bounded correction or reader amendment before its next stage. If basic control remains unsuccessful, locate the bottleneck and defer shape reasoning, negative/plural pointing and global attention.

References: [shared and effector-specific planning](https://pmc.ncbi.nlm.nih.gov/articles/PMC6623835/), [eye proprioception](https://pmc.ncbi.nlm.nih.gov/articles/PMC6620976/), [preregistered virtual-nose experiment](https://pmc.ncbi.nlm.nih.gov/articles/PMC11522211/). These motivate controls, not claims that this implementation already works.
