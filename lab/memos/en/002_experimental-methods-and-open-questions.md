# 002 — Experimental Methods, Objectives, and Open Questions

[中文](../zh/002_实验方法与待验证问题.md) | [English](002_experimental-methods-and-open-questions.md)

## General rule

The experimental objective is not to make the system sound human. It is to turn candidate relations among stimulus, history, anonymous structure, and output into falsifiable propositions. Freeze the starting snapshot, parameters, adapters, background condition, seeds, stimulus order, success threshold, and counterexamples in advance.

## Priority experiments

1. **Stimulus discrimination:** do target, matched-unrelated, shuffled, and character-frequency-matched random inputs produce distinguishable anonymous response clusters?
2. **Order and history dependence:** with the same input multiset in different orders—or different histories followed by one future probe—do trajectories reliably diverge?
3. **Direct repetition versus associative consolidation:** match total contact and compare delayed retention after direct repetition versus associative reactivation alone.
4. **Forgetting, interference, and plasticity:** measure retention curves, interference from new relations, and ability to form new mappings after an established structure.
5. **Inhibition ablation:** from one snapshot compare local inhibition off/on for propagation, mixed output, oscillation, convergence latency, and specificity.
6. **Sensory organization:** do different adapters, channel maps, and serial/parallel compositions reliably induce different internal organizations?
7. **Binding and direction:** swap entities, reverse order, permute relation labels, and use new characters to test binding against position, frequency, or surface label.
8. **Untrained relations:** use transitive-kinship tasks to distinguish transient analogy contact from a stable new relation response; report negative outcomes.
9. **Continuous long text:** compare exact replay, same-topic different text, shuffling, and topic switching, including delayed probes.
10. **Clone divergence:** clone one snapshot, alter one environmental factor, and measure first divergence tick and later trajectory distance.
11. **Visual-artifact audit:** every claimed structural change must exist in Core state/history, not only in layout animation.

## Preregistration sketch: “A is called pine-nut / B is called bell”

- Create at least 100 independent trials from a frozen initial snapshot. Alternate the two statements for about 20 rounds with at least 20 ticks between rounds.
- Insert weak, semantically unrelated, length-matched distractors in intervals selected before the run, never in response to live outcomes.
- End with the corresponding incomplete probe; include untrained, mismatched-binding, shuffled, frequency-matched, and new-character controls.
- The primary endpoint is discriminability of anonymous response signatures by training condition, not merely appearance of readable target labels.
- Reveal plaintext labels only after anonymous analysis. Preregister similarity thresholds, success criteria, and statistical tests.

## Open questions, not established conclusions

- Are similar responses genuine basins or approximate revisits under noise?
- Do relation-local structures encode roles/direction, or only co-occurrence and position?
- Do fast activity and slow topology define a reproducible memory timescale?
- Do sensory constraints produce organizations that replicate across seeds?
- Does readable word-order change arise from internal dynamics or readout ranking?
- Under continuous background input, which recurrent structures are background-driven and which are residual propagation after a probe?

Every question must permit “no difference,” “not formed,” or “only within a parameter region” as a valid result.
