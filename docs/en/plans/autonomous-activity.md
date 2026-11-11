# Autonomous activity: from persistent circulation to environmental adaptation

Execution addendum, 2026-09-29: [448-instance results](../../../lab/explorations/2026-09-29-input-rate-and-autonomy/report.en.md). The original discussion remains below; actual scope and budgets follow the [execution registration](../../../lab/explorations/2026-09-29-input-rate-and-autonomy/design.en.md) and stage records. Core unchanged. Inherited region preferences appeared without requiring inter-node communication; sustained autonomous circulation was not observed.

[中文](../../zh/plans/autonomous-activity.md) · [Plan index](index.md) · [Previous results](../../../lab/explorations/2026-09-29-memory-timescales/report.en.md)

2026-09-29. **Discussion draft; not executed.** This turn adds documentation and experimental design only. It does not run training, change kernels or sensory mappings, or modify existing evidence. Discussion does not require switching the application's planning mode. Freeze the accepted protocol, configurations, seeds and budgets before execution.

## Question

Training has already produced networks that remain active after task input stops. The next useful question is: **can this activity retain experience, incorporate new experience, switch patterns, and help the model change its surroundings?**

These observable properties are closer to the researcher's intended autonomous consciousness-like activity than persistence alone. They do not directly establish subjective experience. The study will not invent a single consciousness score or require human language.

| Capability | Concrete test | What it establishes by itself |
| --- | --- | --- |
| Maintaining activity | Internal transmission continues after all sensory input stops | Self-maintenance; not yet flexible activity rather than a fixed oscillator |
| History affects the present | Identical current input produces different activity after different histories | Experience contributes to current processing |
| Changing and switching | A weak cue alters a pattern beyond the cue's duration | More than replaying an unchangeable pattern |
| Using action | Activity changes the environment through actions and outperforms disconnected feedback | Internal activity contributes to interaction with surroundings |
| Environment shapes tendencies | Opposite selection conditions produce opposite tendencies that can change after reversal | Tendencies depend on experience and environmental conditions |

Report each capability separately. A stable loop remains an informative finding. Switching and active adaptation would be further substantive progress.

## Supply conditions and preserved mechanisms

- The researcher's clarification is controlling: **unlimited external supply still requires local consumption, recovery and refractoriness**. The earlier unexecuted draft's D=0 main condition has been corrected. Instantaneous refill remains a separate control.
- Keep the continuous-memory kernel at `depletion_enabled=true`, `stp_enabled=true`, `stp_facilitation_tau_s=1.0`, `edge_consolidation_enabled=true` (111). Preserve existing self-inhibition; LIF retains its distinct explicit refractory interval and adaptation current. Do not rewrite or equate their formulas.
- **Input-spacing calibration** preserves prior energy settings within each kernel: local consumption/recovery remain enabled; continuous whole-model `energy_simulation_enabled=false` stays as before and LIF has no such account. This excludes extra whole-model starvation, not a claim that a complete feeding/metabolism process was tested.
- **Later environment experiments**, when explicitly measuring energy, should reuse the continuous kernel's account and external supplier: `total_supply_limit=null`, finite supply rate/capacity and nonzero transmission costs. Freeze a supply sufficient for the registered small-model load and audit consumption, supply and unmet demand. Never clamp each local fraction to one. Whole-model reserve and local recovery are presently independent, so more external reserve does not accelerate local recovery. Adding the same account to LIF would be a separate proposed mechanism, not an existing feature.
- Keep inhibition, self-inhibition, forgetting, activation decay, fast traces, context, thresholds and the existing propagation cadence. Learning continues, but evaluation learning never writes back to the parent. Do not disable unrelated mechanisms.
- Do not assign meanings to nodes, add good/bad or liking variables, prewrite connections or correct actions, or have AI make decisions in the output adapter. Labels are observational only.
- Unlimited supply does not create activation. If all activation ceases after input withdrawal, preserve the existing death rule; no hidden life-support stimulation or revival to complete tests.
- External shortage or a finite total supply can be explicit comparisons. Do not mislabel the previous depletion-removal result as sufficient external supply. No project-wide defaults or hypothesis versions change.

## Preliminary stage: independently test millisecond input spacing

This user-requested check comes before persistence and environmental selection. **Change the input schedule alone, not propagation speed, numerical step, thresholds or refractoriness at the same time.**

### Verified time scales

| Quantity | Current value | Meaning |
| --- | --- | --- |
| Previous external frame interval | 1000 ms | Experimental input spacing, not the entire kernel update rate |
| Continuous numerical step / propagation interval / transmission delay | 10 / 100 / 10 ms | Separate parameters; initially unchanged |
| LIF grid / transmission delay / explicit refractory interval | 0.25 / 1 / 2 ms | Internal timing is already millisecond-scale |
| LIF membrane / current / learning-trace constants | 20 / 5 / 20 ms | A transient can largely disappear before a one-second follow-up |

Thus input arriving too late to interact is a concrete hypothesis grounded in code, not yet an established explanation of previous failures. Input interval, spike duration and propagation delay differ; biology has no single universal frame rate. See [integrate-and-fire time scales](https://neuronaldynamics.epfl.ch/online/Ch1.S3.html).

### Bounded comparison

Within continuous-memory and LIF separately, compare **1000, 100, 20, 5 and 1 ms** intervals. Use the same anonymous co-frame pair curriculum, 20/10/10 repetition blocks, frame order, frame count, intensity and mapping. Retain LIF's existing facilitation and other settings rather than changing them to match the continuous kernel. Their response units differ and must not be pooled into one numerical ranking.

Two fixed seeds give 2 kernels × 5 intervals × 2 seeds = 20 training instances. Each gets matched A-cue, D-cue and no-cue copies at an identical post-training delay, giving 60 probes and 80 instances total. Freeze cue timing/intensity before execution; test timing must not track training frequency. Preserve actual delivery timestamps.

Reserve at most 16 instances for an independent third seed: for each kernel compare the one-second baseline with one candidate interval, each with a training instance and three probes. If no improvement appears, do not exhaust the budget merely to continue. Prefer the **lower frequency** that consistently improves preregistered endpoints in both screening seeds rather than assuming faster is better. If the held-out seed fails to support it, keep the prior main setting.

Required measurements:

- LIF spikes, membrane/current, refractory state and connection-weight changes; continuous activation, inhibition, local energy consumption/recovery and weight changes.
- Matched-target response relative to the alternative target, pre/post-cue change and no-cue activity. Global brightening alone is not improved pairing.
- Complete temporal readouts/end rankings, with absent qualifying windows reported. Preserve spike events; a default 100-ms display sample cannot establish absence of millisecond spikes.
- Frame count and cumulative input dose remain equal, while dose per second rises and training duration falls. Align tests by time since final input. A claim that improvement specifically reflects temporal interaction rather than reduced forgetting needs a separately registered matched-age or equal-duration/equal-dose burst-versus-uniform comparison.

Continuous inhibition/propagation still follow the existing 10/100-ms schedule. If apparent gain comes only from pre-update accumulation, saturation, merged frames or dropped frames, report that limitation rather than greater biological fidelity. A needed change in internal propagation interval or numerical step requires a separate factor test, not a hidden part of faster input.

Use a validated interval in subsequent experiments for that kernel; otherwise retain one second. Kernels need not share an optimal interval. Co-frame connection formation does not by itself solve association between separate frames.

## Stage one: can experience change the loop?

Run this stage after input-spacing calibration, without a new world, robot, GPU or Transformer. Local consumption is retained, so reproduction of the old D=0 persistent regime is not assumed. Preserve and report a failure to sustain activity.

### Training and sample allocation

Fix six independent anonymous-channel seeds in advance. For each, create matched copies under two curricula:

1. Paired `[A,C]` and `[D,E]`, using the earlier 20/10/10 repetition blocks, completing each repeated block before switching.
2. Balanced four-way pairings at 10/5/5 repetitions each, matching frame count, channel dose and input timing.

Use training intensity 1 and the interval supported by the held-out calibration seed; retain one second if none improves. Wait 300 simulated seconds after final delivery. This anonymous-channel study does not reinterpret earlier natural-language teaching. Retain recorded host background at intensity 0.2, disclose sequences/hashes and do not select only successful seeds.

From the twelve training endpoints create five branches each, sixty branches total:

| Branch | Procedure | Purpose |
| --- | --- | --- |
| Background continues, no task cue | Observe for 60 s | Match the previous finding |
| All sensory input stops, no cue | Stop collection/replay, drain accepted external frames, observe for 60 s | Test persistence without new external input |
| All sensory input stops, cue A | Same withdrawal, 30 s quiet observation, A at intensity 0.5, another 30 s | Test a sustained change in pattern balance |
| Same, cue D | Match A's dose and timing | Test a different change |
| Same, novel cue N | Same channel count, intensity and timing | Separate familiar association from general perturbation |

Drain only committed **external** frames. Do not clear internal transmissions or wait for a self-sustaining internal queue to empty. Record each source's final arrival. A copy that dies before its cue remains a recorded death; it is not revived and presented as the same living consciousness.

Preregister another 24 branches: each paired parent gets the old depletion-removal intervention, disabled facilitation, disabled further consolidation and unchanged parameters after save/restore. Compare with the matching uncued branch, changing one factor at a time, for at most 60 s. Depletion removal must not be renamed normal sufficient supply. Stage one admits at most **96 instances**, without unbounded follow-ups.

### Measurements and decisions

- Record actual activation, inhibition and internal transmission for all nodes, including weak activity below display filters. Report duration, zero-activity time, active-node count and amplitude separately.
- Check whether the two trained groups always rise and fall together or show differentiated activity. Inspect normalized patterns alongside total magnitude; a brighter version of the same pattern is not a new pattern. Retain every node rather than just plausible answers.
- Compare full curves and states 1, 10 and 30 s after a cue. Does the change persist, return to the original pattern or become another pattern? Do not force a clustering method to find two brain regions.
- Six seeds are independent repetitions; branches sharing a parent are matched observations. Report individual seeds, differences, ranges and failures, not only means.
- Preserve **complete temporal-convergence outputs ranked by end activation**. Persistence, switching and behavior are separately preregistered endpoints for this new question, which cannot require persistent activity to cease before it can be studied. Report absent qualifying convergence explicitly; do not lower its threshold after seeing results.

If every condition merely produces the same mechanical oscillation, or cues only brighten it temporarily, restrict follow-up to competition and switching rather than large preference training. Proceed to stage two when independent seeds show history-dependent activity and sustained cue-driven changes.

## Stage two: let activity affect a small environment

Use **a virtual body that moves left or right around a one-dimensional ring**. No detailed limbs, eyes or 3D rendering are needed. Position, velocity and two spatial signals change over time; sensors report signals actually measured at the current location and the body's motion. A ring avoids mechanical trapping at walls. Swap region locations in evaluation to defeat fixed-direction shortcuts.

Use stripes and spots as observer labels for fixed anonymous sensory patterns with matched channel counts and intensity. Neither is inherently good; labels never enter the kernel. The simulated rules and encoding are declared environmental assumptions, not claims of a real retina.

Before reusing the world/body interfaces, verify full candidate-kernel birth, capture, restoration and continuation. Existing `PlanarBody`/`WorldPorts` hash projections are an **engineering interface baseline**, not proof that motor wiring emerged naturally; see [embodied differentiation (Chinese)](../../zh/embodied-functional-differentiation.md). Do not handpick useful nodes or train a goal-aware decoder.

The interface must support two distinguishable motion directions without giving an untrained model a fixed target-region preference. If existing interfaces cannot meet these boundaries, pause stage two and discuss wiring explicitly rather than supplying kernel rewards or artificial brain regions.

### Experience, selection and tendencies

Use opposite environments: in one, spending more time in stripes increases the chance of becoming a parent; in the other, spots do. **External selection** implements the goal. No reward/correctness label enters Core and scores never edit connections. Different environmental histories generate structural variation; record births and histories and do not insert arbitrary random edges.

With plentiful external supply, deliberate starvation is not used as punishment, but local depletion and recovery can still occur. Selection must be explicit rather than assuming the model knows which region is better. Unselected individuals do not become parents; **do not call a death interface or label nonselection natural death**.

Preserve the agreed inheritance boundary: inherit experience-shaped structure, clear activity at birth, evaluate independently born copies, and never write evaluation learning back into parents. Distinguish within-individual change from a change in population composition after selection. Start small rather than creating a large ecology simulation.

### Required comparisons

| Comparison | Alternative explanation addressed |
| --- | --- |
| Goal-based parent selection vs the same number of randomly selected parents | Time or repeated exposure alone produced the change |
| Stripes goal vs spots goal | Kernel, encoding or output wiring predetermines one preference |
| Actions affect surroundings vs replay another copy's exact sensory history with actions disconnected | Familiar input alone suffices; preserve actual replay deliveries rather than claiming two closed-loop histories are identical |
| Current neural activity controls movement vs fixed or recorded control | A simple controller or inertia already explains success; test equal starting conditions and exchanged regions |
| Reversed rules vs copies remaining under original rules | The tendency cannot adapt to changed conditions |

Use evaluation positions, sensory schedules and region swaps that were not used to select parents. Measure occupancy, return time from the opposing region, choices after changes, saturation and inactivity. To localize internal activity's contribution, temporarily silence loop nodes in **isolated copies**, compared with an equally sized, similarly active set elsewhere. If no matching nodes exist, disclose that rather than claiming selective causation. Silencing is a declared research intervention, not a deployment rule.

Freeze exact population sizes, generations and branches after stage one. Initial guidance: no more than four individuals per population, three generations, two opposing goals, random-selection controls and at least two independent environmental blocks. Include births and evaluation copies in a provisional 256-instance cap.

## Stage three: consistent versus conflicting experience

For models with different established tendencies, compare familiar experience-consistent stimulation, equally familiar stimulation that violates a learned relation, and dose-matched novel input. Use isolated copies from the same starting state, randomized ordering, and tests after rule reversal. Do not let earlier tests silently train later tests.

Preregister measurements without assigning a favorable sign: activation and inhibition over time, participating nodes, replacement of prior cycles, restabilization time and actions that change the environment. An omitted expected event needs additional dose- and timing-matched controls; less input causing ordinary decay is not evidence of disappointment.

Stronger activation under conflict is interpretable only with opposite-history, familiarity and dose controls. A stronger finding would be the same stimulus producing opposite approach/avoidance after opposite histories, further change after reversal, and dependence of those behaviors on current internal activity.

If all activation ceases, preserve last inputs, internal transmissions, inhibition, energy settings and death time. Check threshold and duration explanations. Death is an observable outcome, **not a required sign of suffering, dislike or consciousness**.

## Tools and evidence

Input calibration and stage one should reuse Runtime, CLI, full-state copying, temporal readouts and observation callbacks. Verify independent millisecond frame delivery first; tools must not silently merge frames. Candidate-kernel compatibility with world/ecology entry points still requires verification before stage two; documentation alone does not establish it.

If tooling is missing, add external controls first: source-specific stopping and pending external-frame listing; continuous activity recording without a cue-bound window; a shared timeline for world state, anonymous input and actions; and matched closed-loop/replay comparisons. Expose operations through CLI/Python and show humans the same evidence. No such implementation begins in this documentation turn.

Reports should show an understandable timeline: environmental signal → activation/inhibition → action → next environmental signal. Preserve raw numbers and temporal end rankings. Display sampling must not affect dynamics. Grouping, labels and narration remain read-only analysis.

## Budgets and stopping

- Preliminary input calibration: at most 96 instances, **256 MiB** total new storage, no new cases beyond 192 MiB; one CPU worker, 20 minutes aggregate execution and 40 minutes wall time. Stop if faithful spikes/states exceed the budget rather than reducing evidence fidelity silently.
- Stage one: at most 96 instances, one CPU worker, 30 minutes aggregate execution, 60 minutes orchestration wall time, three minutes wall time per instance. Use the first two registered instances to check speed and evidence size; include them in the sample rather than rerunning them. Stop and preserve evidence at any limit.
- All new local evidence, database storage and attachments: hard cap **512 MiB**. Stop admitting new instances at **384 MiB**, reserving the remainder for reports/archive. Monitor bytes throughout. Stop for a budget revision if faithful records do not fit; never silently drop frames or overwrite evidence.
- Process memory ≤4 GiB, available host memory ≥2 GiB, E drive reserve ≥15 GiB and C drive ≥5 GiB. Per-instance limits of 2,000 nodes and 20,000 edges are external stop conditions, not instructions to prune the kernel.
- Stages two and three require separate go-ahead. Suggested combined new-storage cap **2 GiB**, at least 25% reserved for delivery; do not automatically expand to 4 GiB. Preserve the earlier 1.882-GiB study.
- Read account usage anew at execution start. Proposed increase: stop expansion at one percentage point and stop work at two points. Usage is shared and coarse; check at stage boundaries, keep individual waits ≤60 s and avoid starting long stages near the limit. Old absolute readings of 41%/44% are not current boundaries. The user's earlier 20-point ceiling remains a looser outer limit.
- No paid AI, cloud compute, CUDA requirement or new hardware. No broad parameter sweep, vocabulary expansion or language task. Missing critical controls or a need to change the kernel/wiring principles requires a recorded discussion, not an improvised mechanism that produces the desired result.

## References and inference

These papers inform experimental observations rather than replace ThreeMind's assumptions or demonstrate that the project has reproduced their findings:

- [Kenet et al., 2003, Spontaneously emerging cortical representations of visual attributes](https://www.nature.com/articles/nature02078): switching spontaneous cortical patterns motivate examining change as well as persistence. The anesthetized preparation also prevents treating spontaneous activity alone as a consciousness test.
- [Keller et al., 2012, Sensorimotor mismatch signals in primary visual cortex of the behaving mouse](https://pubmed.ncbi.nlm.nih.gov/22681686/): manipulated movement/visual feedback motivates action-feedback, replay and changed-rule comparisons; it does not require installing a prediction-error module in ThreeMind.

The proposal's inference is that persistent activity carrying experience, changing with experience, and contributing causally to adaptation would provide an experimental foundation for the autonomous-consciousness research direction. Whether these properties appear is for the next data to establish.
