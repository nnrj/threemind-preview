# Depletion, facilitation and consolidation across timescales

[中文](design.zh.md)

2026-09-29. **Design complete; formal experiments not run; independent factor controls still require implementation and validation.** This document reports no new results. Freeze this design, the condition manifest, code hashes and resource baseline before execution. Record subsequent amendments without rewriting hypotheses after observing results.

Previous study: [mechanism attribution and discussion addendum](../2026-09-29-continuous-mechanisms/report.en.md). Preserve its project, instances, raw trajectories, archive and report revision 1. Create a separate project for execution.

## Questions

How long can depletion or facilitation make a previous input affect a later response? Do they strengthen, weaken or reverse pathway differences? Do they compensate for one another? Does consolidation make experience-dependent differences last substantially longer, and does it also affect immediate responses?

The proposed short-term/long-term division is a hypothesis. “Longer-term” means substantially beyond this model's short-state time constants, not evidence of years-long human memory. Unfamiliar, reversed or nonlinguistic response patterns remain outcomes worth reporting.

## Eight conditions and exact boundaries

Here F means facilitation, **not the previous study's `fast_*` trace**.

|D/F/L|Depletion|Facilitation|Positive consolidation of existing edges|
|---|---|---|---|
|000|Off|Off|Off|
|100|On|Off|Off|
|010|Off|On|Off|
|001|Off|Off|On|
|110|On|On|Off|
|101|On|Off|On|
|011|Off|On|On|
|111|On|On|On|

**D:** `stp_enabled=False` is unsuitable: it bypasses both depletion and facilitation and changes baseline release to 1. Instead, D=1 retains existing resource dynamics; D=0 uses available resource x=1 at release while retaining baseline utilization U and facilitation u. This is an explicitly artificial unlimited-supply control. Release is u×x with D, u without D. F=0 uses u=U. All four D/F conditions have the same first release after genuine rest. A tiny recovery constant is not an exact off switch.

**F:** Off uses fixed U; on uses existing facilitation with `stp_facilitation_tau_s=1.0`. The primary parameter layer retains U=0.5, recovery=0.8 s and active-state decay=0.003 s. Do not give only F-on groups a different U or recovery constant. When switching from nonfacilitating history, do not mistake the saved u=U for a rested facilitating state; wait equally and measure actual relaxation.

**L:** Block only positive increments to **existing-edge weight and stability**, from direct co-touch and transmitted activity. Keep the exact existing formulas when on. Retain initial edge formation, eligibility, traversal/touch histories, node support and local plasticity, fast traces, forgetting, decay and pruning. L-off is therefore not “no long-term learning whatsoever”: it isolates specified positive consolidation paths. Other histories can still affect retention.

`plasticity=False` is unsuitable because it also disables forgetting, support decay, pruning and fast-trace updates. Zeroing learning/associative rates alone leaves direct impulse terms; zeroing stability gain also alters node updates. Neither is the requested isolated L intervention.

Across all groups preserve inhibition and diffusion, self-inhibition, activation/trace/eligibility/stability/support decay, forgetting, pruning, novelty, fast trace, local context, clocks, thresholds and sensory mapping. Keep originally disabled optional features disabled. Compare complete configurations against a factor whitelist. Different forgetting trajectories caused by different activity are legitimate downstream effects, not grounds for compensatory edits. All-three-off does not mean all history dependence is removed.

## Prerequisites

Preserve `continuous/1` and `causal/9`. Implement a separately identified research candidate, provisionally `threemind.continuous-memory/1`, with independent resource-use and existing-edge consolidation controls; reuse existing facilitation. **This identity is proposed, not currently executable.** Bind parameters, state, definition hashes, CLI, protocol and UI parameter catalog consistently. No semantic targets or global importance scores enter the operators.

Required verification:

- D=1/F=0/L=1 reproduces the old continuous candidate, including Python/Rust behavior, local states, transmission, weights and readouts.
- Matched first releases; independently observable depression and facilitation under repeated pulses; recovery toward the same baseline.
- L-off blocks both positive edge-update paths while initial formation, node updates, eligibility, forgetting and pruning still operate. Check behavior, not just config flags.
- Advancement batching, observation and save/restore do not alter dynamics. Sampling does not consume resources or refresh traces.
- Preserve the current two-threshold ordering, including resource use by releases that fail the second threshold. Its validity remains a research question, not an unannounced fix.

Do not execute a confounded eight-condition comparison before these gates pass.

## Execution order and size

### Stage 0: calibration and replication

Use paired and repeated pulses to calibrate local operators across intervals; these are numerical checks, not whole-network memory discoveries. Reproduce the previous A→B/D→B effect and resource trajectory before the new factorial study. Treat old parent states as read-only; any conversion needs a new identity and provenance.

### Stage 1: transient effects on a shared learned network

Use the previous anonymous A/B/C/D/E mapping and seed 9291000. Two primary teaching blocks swap endings: A-B-C/D-B-E and A-B-E/D-B-C. Actual frames remain `[A]→[A,B]→[B,C]` and counterparts. Repeat each sequence 20, 10 and 5 times in successive rounds, with 1-s spacing and intensity 1.0. This is an anonymous mechanism task, not an alteration of the user's language sentences or sensor mapping.

Split each common parent into eight conditions and wait equally for 20 simulated seconds after registered D/F/L reconfiguration. Maintain identical real telemetry replay. Measure whether task-edge resources, utilization and fast traces have relaxed within 1e-6 of their resting values; label residual history rather than silently resetting it.

Independent probe copies receive A→B or D→B, intensity 0.5, at **0.1, 1 or 3 s** gaps. Include age-matched B-only at every gap, plus A-only, D-only and no-task-input trajectories covering the longest observation horizon. No probe alters the parent or another probe.

Total: `2 teaching blocks × 8 conditions × (3 gaps × 3 probes + 3 controls) = 192 probe copies`, excluding preparation. Teaching blocks are counterbalances, not independent random population samples. At short gaps distinguish lingering activity from latent synaptic state. Measure whether F extends, suppresses or reverses D-dependent differences.

### Stage 2: retention after repeated experience

Train new instances independently of Stage 1. Cross all eight conditions with two ending assignments. Paired teaching uses `[A,C]` and `[D,E]`, each repeated **20, 10, 10** times across rounds: 80 frames total, intensity 1.0, interval 1 s.

The dose-matched nonspecific curriculum uses `[A,C]`, `[A,E]`, `[D,C]`, `[D,E]`, each repeated **10, 5, 5** times: also 80 frames, identical channel counts, intensity and frame width but no stable one-to-one pairing. Preserve full presentation order; the histories are dose-matched, not identical.

Branch independently from the training endpoint for delays of **1, 30 and 300 s**. Probe only A or D at intensity 0.5. Forgetting, inhibition and identical background continue throughout each wait. Probe each copy once to avoid test-driven retraining.

Total: `2 assignments × 8 conditions × 2 curricula = 32 training parents`; `32 × 3 delays × 2 probes = 192 probe copies`. Report both pre-probe structural changes and reactivation. Persisting weights without retrievable response do not demonstrate usable retained memory.

Maintain each condition's L setting during training and probing for the primary total-effect analysis. If a persistent L effect appears, add independent train-L-on/test-L-off copies in Stage 3 to separate retained structure from learning during readout. Do not turn learning off across the primary study.

### Stage 3: bounded extensions

Pre-register each extension's complete comparison set before execution; publish every outcome, including reversals:

1. First test a new channel seed and reversed teaching order, then 0.3/10-s gaps.
2. If facilitation operates but is weak, test a second, lower-U parameter layer across **all eight conditions**. Freeze it before results and report it separately; do not replace the default layer or change parameters only in F-on cases.
3. If L has persistent effects, test readout-only L removal. With remaining budget, use AB/BA followed by a common Q to examine actual order sensitivity; this is a new task, not something the different-prefix result already establishes.

At most 160 whole-network extension instances. The entire study is capped at **650 whole-network instances**, including calibration, parents, preparations and probes. Stage 0 and preparation may use at most 40; primary stages use 192+32+192=416. Unused allowance is not a target.

## Background, readout and evidence

All formal conditions replay the same recorded host telemetry at intensity 0.2 through the existing protocol. If recordings are shorter than a long trial, explicitly register periodic replay and timestamp offsets, identically across conditions; do not call it live data. Preserve mapping and inspect actual overlap/interaction with task channels. Do not assume isolation in advance.

Controls share the same background from birth and the same absolute timing. Preserve ordinary activity-based death. A copy that dies before its probe is unavailable/undelivered, not a measured zero, and is not automatically revived. Background standardizes conditions; it does not guarantee memory.

The primary behavioral endpoint remains **activation and ranking at the end of a qualifying converged temporal-readout window**. Save full reader state/classification/reason and compute ranking from `last_activation`, not the default composite score. Count decay, truncation, death and missingness separately; never replace convergence with a peak.

Mechanistic outcomes are separately reported: complete C/E response trajectories; prespecified area/peak; first arrival and final effective response; signed matching-minus-alternative differences; pre/post release x/u, transmitted amounts, both threshold decisions, weight/stability/eligibility/fast trace/inhibition. Record forward pairing, reversed pairing, fixed-target bias and no measurable differentiation.

Sample post-cue mechanism trajectories every 10 ms without changing the 10-ms solver step or 100-ms propagation cadence. Keep the reader at its existing 100-ms sampling interval. **Use a common sequence-window cap of 15 s** so a 3-s gap still has 12 s of subsequent observation; all other reader convergence settings remain unchanged. Stage 0's original 12-s replication is separate.

Do not record every full state during long waits. Save stimuli, seeds, hashes, start/end/pre-probe checkpoints and one-second summaries; dense trajectories focus on probing. Full transmission-event recording is limited to designated representative cases. Preserve full temporal readouts; UI sampling is not scientific evidence.

## Comparison and interpretation

Show all eight conditions at each block/time point. Use matched B-only, dose controls and reversed ending assignment to identify fixed bias. Report raw responses, signed differences and within-block causal contrasts. If no qualifying convergence occurs, the primary outcome is unavailable; measured transient effects are still reported separately.

For example, at L=0 the D×F interaction is `Y110−Y100−Y010+Y000`; repeat at L=1 and calculate other pairwise and three-factor contrasts. Show each factor's effect under all four settings of the other two before averaging. Do not average away sign reversals.

Time samples and shared-parent descendants are not independent training replications. This small study uses reproducible local interventions to investigate mechanisms; population statistics require additional independently trained seeds and a balanced design.

Describe persistence with both a preregistered absolute difference tolerance of 1e-6 and 50% of the baseline effect, retaining its sign. Plot nonmonotonic or reversed effects without forcing an exponential half-life. Distinguish exact equality from being below a tolerance.

## Resources and delivery

- **2 GiB total new storage**, including local files, DB increment and published archive copies. Stop admitting trials at 1.6 GiB; reserve 0.4 GiB for publication. A later expansion toward the user's previously permitted 4 GiB requires an explicit budget amendment.
- At most 650 whole-network instances; 5 minutes wall time per instance, 60 minutes cumulative simulation compute, 2 hours per complete orchestration. One CPU worker; no CUDA, remote model or paid service required.
- Process RSS ≤4 GiB, host available RAM ≥2 GiB, workspace disk free ≥15 GiB, system disk free ≥5 GiB. Check before cases, between stages and around publication. Preserve evidence and stop rather than retrying indefinitely.
- Account weekly usage was **41% at design start**. A **3-percentage-point** increase is the soft ceiling: near/at 44%, stop expansion and document completed work. Account usage is coarse and shared with other work, not exact study token attribution. Rebaseline explicitly after a quota reset. The original prohibition on exceeding a 20-percentage-point campaign increase remains.
- Isolation failures, observation-induced changes, restore mismatches or unavailable controls stop dependent formal comparisons. Do not fill unrun conditions with zeros or endlessly search for favorable settings.

Deliver bilingual design notes and reports in a new platform project, all condition/config differences, task manifest, input/state hashes, resource accounting, plots/tables and reproducible CLI entrypoints. Explain findings in ordinary language before technical detail. Only executed and checked work is marked complete.
