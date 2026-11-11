# Context judgments, evidence revision and active observation: exploratory protocol v1

9 November 2026. The author explicitly approved the proposed experiments, with compliance with training protocol v3 and prior consultation for any substantive conflict. This is a prospective protocol, not a result.

## Questions and predictions

Can experience in genuine continuous-memory/5.1 organize consistent predictions of two subsequent environmental events and an action under the same current cue? Can new discriminating evidence revise those responses? Can the system request an observation under an ambiguous cue and use the resulting information to choose an exit? A context judgment here means the joint outputs of sound-prediction, visual-prediction and action interfaces in a two-context discrete simulated world. No context semantics are supplied to Core.

We predict selective experience-dependent responses, revision by discriminating cues and an action-dependent benefit of observation. Capability and connection attribution are separate targets. Previous M1/M2/M3/M5 scores and conclusions are preserved.

## Complete subjects and implementation

Eight independent birth origins, seeds 26110900–26110907; separately recorded apparatus attempts use the disjoint 26110800–26110899 range and are excluded. Each origin develops its own complete output-interface reference before two registered opposite-history branches. Branches, questions and frames do not increase independent N. Ordinary teaching, calibration sampling, questions, correction, review and each examination sequence preserve the complete current state. There is no per-question reset.

Use genuine /5.1 native execution. Only seed and energy_seed differ from the default birth configuration. All defaults and implementation hashes are saved; no change to production dynamics, half-life, learning, forgetting, inhibition or short-term mechanisms. A separate K event of amplitude .2 every .5 internal seconds is explicitly declared fixed background input. The body is a discrete observation/exit device, not a physical robot.

The complete state includes Core, pending inputs, internal clock, three personal adapters, weights, AdamW and learning RNG, accumulated calibration samples, mappings, world and actuator state, recent complete observation windows, curriculum position and the input hash chain. Old subjects, evidence, paused studies and automations are untouched.

## Temporal output adapters

Three personal E56/E64-style Transformers use a 48-dimensional projection, one temporal layer, four heads, feed-forward width 96 and zero dropout. Each reads only its declared sound, vision or action output ports, using raw activation, inhibition, direct and associative fields. A question spans one internal second: 20 frames at 50 ms, with eight uniformly spaced frames selected. No per-example rescaling or baseline subtraction. Outputs are two sound classes, two visual classes and exit-0/exit-1/observe. Interface meanings are learned individually. Inference receives no question identity, history label, world truth, raw sensory input or file information.

First teach old relations and sample actual answer windows without displaying the answer. Fit each adapter with AdamW (.002 learning rate, .0001 weight decay, batch at most 32, clipping 1), 1,200 updates per round, at most three rounds. Keep all earlier samples and continue the same weights, optimizer and RNG. Retain the final state, never an earlier minimum-loss state. Supervision trains the external adapter; gradients do not enter Core.

Then freeze the three adapters before teaching new context relations to Core. This is the author's approved fixed-interface attribution design. Corrections still teach Core through ordinary external demonstrations, but new labels never update the adapters. The control path remains the same. This declared causal design complies with protocol sections 3, 9 and 14.

## Curriculum and materials

Randomly permute anonymous channels per origin. Old Z0/Z2 cues correspond to class 0; Z1/Z3 to class 1; W to observe. X0/X1 have opposite correspondences in the two histories. Environmental D0/D1 identify actual context 0/1. A demonstration presents sensory and output-port signals together as a declared external event. Test inputs never include output ports.

Initial teaching uses eight dense cycles and three review cycles after additional gaps of 2, 6 and 18 internal seconds. A lesson lasts 1.5 seconds and contains five events 250 ms apart in its first second; each presented channel has value .4 and global intensity 1. Log every event, dose, time and actual interval, including interleaving and background. Mixed Z0+Z1 and X0+X1 cues receive a teacher demonstration of observation, followed by the actual D cue and the demonstrated exit. No special ambiguity flag enters the network.

Development uses .72/.88 cue doses. Up to two correction rounds retain the original errors, ask them again before feedback, give ordinary demonstrations and a neighbouring .36-amplitude demonstration, review old correct cases, and use two dense cycles followed by 2/6/18-second gaps. Continue current state through development and further teaching. Stop at all-correct development or the registered limit. Interface calibration follows the same bounded correction structure. Final materials use .76/.84 plus predefined N distractors; their scores never guide fitting or curriculum.

## Trials and environmental consequences

Each history completes the same 24 prospective trials: four old, eight single-cue (including four conflicting-evidence trials), and 12 mixed-cue trials. Source-specific order is frozen and matched between arms. Opposite histories receive the same current single cue. Each trial comprises two complete one-second windows and one second of background, with all resulting state changes retained.

The first window produces two predictions and an action. Single-cue evidence trials receive D0/D1 at the declared second-window onset. Mixed-cue trials receive D only when the selected action is observe; otherwise only background arrives. The second window determines final predictions and exit. Observation spends the single available viewing opportunity and does not select the correct exit. The feedback function uses world state and actual action, never the scoring answer or response correctness. Forced viewing is a separate apparatus ceiling control, not autonomous success.

## Causal branches and matching

Keep the latest complete trained parent of each history unchanged. Each branch runs all 24 questions continuously from that parent. Arms: intact, sham, target-edge silence, matched-edge silence, immediate restoration, view feedback blocked, forced view. Announce parent times and intervention scope before execution, and actual lineage and recovery afterward.

Target edges run from X0/X1/D0/D1 to the declared output ports; matched edges run from Z0/Z1/Z2/Z3 to the same ports. Selection uses declared interfaces and teaching only. Require equal counts and endpoint degree distributions, contemporaneous mean effective-weight difference at most .05, and teaching-period mean source-activity difference at most .05. Publish residuals. Silence changes only silenced_edges; restoration must exactly recover state. Failed matching makes the attribution measurement invalid while preserving capability results. No result-based edge selection.

## Registered goals

Every source must satisfy the requirements in both histories. Errors, absent responses and failed observations remain in the relevant denominator.

|Goal|Per-source requirement|Batch rule|
|---|---|---|
|G1 Experience organizes a joint judgment|At least 75% first-window joint sound/vision/exit accuracy on new single cues; opposite histories change at least 50% of the matched joint responses|At least 6/8 origins|
|G2 Evidence revises the judgment|At least 75% joint second-window accuracy on conflicting evidence; at least 50 percentage points improvement over first-window agreement with the actual context|At least 6/8 origins|
|G3 Active observation helps|At least 75% observe choices on mixed cues, at most 25% on clear cues, at least 75% final mixed-cue exit accuracy, and at least 20 percentage points benefit over blocked viewing|At least 6/8 origins|
|G4 Local connections carry the history effect|Target silence reduces G1 joint accuracy by at least 30 percentage points; matched reduction at most 10; target loss on old cases at most 10; sham/restoration raw windows exactly match; matching valid|At least 6/8 origins|

Report complete denominators, source/history/condition/time breakdowns, intervals and source-level paired differences. Eight origins are exploratory. Any 48-origin confirmation needs a separately frozen resource and power plan. Each target closes as supported, expectation not met or invalid measurement. Interface development below 90% is recorded as insufficient expression apparatus; its subsequent poor performance is not assigned to Core mechanisms. Training loss is never a substitute for behavior.

## Instrument validation, budgets and delivery

Before scientific registration validate complete-state restoration and the next optimizer update; observation-frequency invariance; no simulated advance during wall-clock pauses; complete windows; label isolation; action-dependent feedback; material separation; intervention fields and restoration; independent arithmetic from originals. Instrument and scientific samples are distinct.

Serial scientific host. System reserves commit/RAM/C/E = 5/4/5/25 GiB, sampled every second, pausing only at complete unit boundaries. Startup commit allowance is at least 8 GiB. Originals at most 2 GiB, with another 4 GiB allocated for archive/readback, private host memory at most 3 GiB and cumulative scientific wall time at most four hours. Preserve and report failed saves, death or orphaned in-flight units; no blind replay. Complete pauses resume only a verified latest complete state.

Deliver raw stimuli, activity windows, actions and feedback, complete lineage and adapters, reproducible analysis and explicit bilingual scientific conclusions. Register and read back the full original package through the unified local research API, with pending=0 before finalization. Synchronize the bilingual backlog/history and the two Classical Chinese histories for major phases. Do not edit the author's paper or push Git.

References: Ernst & Banks (2002), doi:10.1038/415429a; Powers et al. (2017), doi:10.1126/science.aan3458. Reliability learning, body-feedback conflicts and sleep-like recombination remain subsequent independent protocols; this study adds no Core mechanism.
