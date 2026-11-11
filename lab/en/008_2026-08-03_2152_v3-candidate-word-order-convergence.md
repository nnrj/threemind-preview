# 008 — Candidate Word-Order Convergence in the V3 Temporal Readout

[中文](../zh/008_2026-08-03_2152_V3时序读出候选语序收敛.md) | [English](008_2026-08-03_2152_v3-candidate-word-order-convergence.md)

**Observation date:** 2026-08-03 21:52 (from the source-conversation timestamp)  
**Model and instrumentation:** V3; anonymous nodes; plaintext observation labels enabled; passive cross-sectional and temporal-convergence readouts used in parallel  
**Status:** important candidate phenomenon; an ordering artifact of the readout instruments has not yet been excluded

## Observation

After a related probe stimulus, the two external readouts presented different readable-label orders for the same response interval:

- the passive cross-sectional readout at tick 1366 displayed “乙 · 铃 · 铛 · 是”;
- the temporal-convergence readout covering ticks 1366–1378 displayed “乙 · 是 · 铃 · 铛”.

From the perspective of the human-language projection, the latter changes the unnatural “乙铃铛是” into “乙是铃铛”, which agrees with the previously trained relation. This is a candidate observation that temporal evolution produced an ordering convergence.

## Why this is not yet a demonstrated word-order correction

The screenshot does not compare per-frame sentences from one readout at two times. It compares two external observation algorithms:

1. the passive cross-sectional readout displays labels ordered by metrics such as activation within a single tick;
2. the temporal-convergence readout ranks nodes across a full window using duration, continuity, tail persistence, and excess activation integral before projecting labels.

The readable-order change therefore has at least two possible explanations:

- **internal-dynamics account:** anonymous nodes associated with the “乙—是—铃铛” relation acquired more persistent and stable relative activity through propagation and inhibitory competition, so the temporal window exposed an ordering closer to the learned relation;
- **instrument-ordering account:** the two readouts merely reordered the same active nodes using different ranking functions. The network need not have encoded a linear character sequence, and the display alone cannot demonstrate grammatical correction.

The current evidence cannot decide between these accounts. The result is recorded as candidate word-order convergence, not as established language ability.

## Relation to entry 005

[Entry 005](005_2026-08-01_0000_v3-probe-stimulus-convergence-mapping.md) records stimulus-specific temporal convergence. The present observation raises a stronger testable question: does convergence select not only a stable node set, but also a pattern of node persistence and activation ranking whose order corresponds to the stimulated relation?

If this result recurs in anonymous node trajectories and remains independent of display labels and readout ranking rules, it would provide stronger evidence that local network dynamics can form a structured response.

## Required validation

1. Preserve activation, inhibition, direct/associative contact, rank, and edge state for every anonymous node at every tick from 1366 through 1378, then reconstruct the complete trajectory.
2. Replay the same window using duration, activation-integral, composite, and fixed anonymous-node-ID orderings. If only one display ranking produces “乙是铃铛”, the readout-instrument explanation should be preferred.
3. Blind-test “甲是松子”, “乙是铃铛”, and shuffled or unrelated controls matched for length and character frequency; compare target-order occurrence rates.
4. Identify response signatures in label-free anonymous mode first, then attach labels offline during analysis to reduce observer bias from readable text.
5. Replicate from the same initial snapshot and across fresh consciousnesses, seeds, label permutations, and inhibition-on/off conditions.
6. Preregister a success criterion, such as the target anonymous relative order occurring significantly more often after the target stimulus than after shuffled and unrelated controls, and report effect sizes and confidence intervals.

## Interpretation boundary

The observation establishes that two readout scales ranked the same response differently and that the readable projection of the temporal-window ranking happened to match the trained relation more closely. It warrants controlled follow-up, but it does not yet demonstrate grammatical understanding or an internal character-level linear sequence representation.
