# E67 typical-case diagnosis: causal contributions of Core edges and the reader

October12,2026, adjunct revision1. Original final scores remain /2 71/72 and /3.1 67/72. These twelve post-outcome, purposively selected cases are not a new held-out score or independent subject replications.

## Findings

**Existing Core connections have a reversible causal role in correct answers to specific shape questions in both versions. Learned reader parameters also determine answers, including one demonstrated /3.1 regression with exactly the same Core activity.** Success cannot be attributed wholly to the reader, and an error cannot automatically be attributed to Core forgetting.

With the final personal reader and identical sensory inputs fixed:

| Kernel | Normal correct | Existing edges silent | Immediate rescue | Correct to wrong | Wrong to correct |
|---|---:|---:|---:|---:|---:|
| /2 | 11/12 | 7/12 | 11/12 | 4 | 0 |
| /3.1 | 10/12 | 6/12 | 10/12 | 4 | 0 |

There are eight shape and four color questions per arm. All four sampled color answers remain correct after silencing. All24 normal copies exactly reproduce the original eight activity frames and answers; all24 rescues exactly reproduce normal activity/answers. All72 copies retain matched recorded inputs and unchanged reader weight hashes. There are 9 changed answers overall, including wrong-to-different-wrong changes; answer dependence is distinct from beneficial correctness.

The /2 green cube at positionA changes cube→cylinder→cube; its green sphere changes sphere→cylinder→sphere. The /3.1 gray cone changes cone→sphere→cone and yellow cube changes cube→cylinder→cube. Conversely /2 already misclassifies that yellow cube as cylinder and retains the error under both controls. This does not identify that error as solely Core or solely reader caused. PositionA is(0.018,-0.006), B(-0.018,0.006), within the central clear field.

| Kernel | Original question | Truth | Normal | Old edges silent | Immediate rescue |
|---|---|---|---|---|---|
| /2 | final-0-0 | cube | cube | cylinder | cube |
| /2 | final-0-1 | cylinder | cylinder | cylinder | cylinder |
| /2 | final-0-2 | sphere | sphere | cylinder | sphere |
| /2 | final-0-3 | cone | cone | cone | cone |
| /2 | final-0-6 | blue | blue | blue | blue |
| /2 | final-0-9 | red | red | red | red |
| /2 | final-0-28 | cube | cylinder | cylinder | cylinder |
| /2 | final-0-30 | yellow | yellow | yellow | yellow |
| /2 | final-0-31 | green | green | green | green |
| /2 | final-1-2 | cube | cube | cylinder | cube |
| /2 | final-1-3 | cube | cube | cube | cube |
| /2 | final-1-10 | cube | cube | cylinder | cube |
| /3.1 | final-0-0 | cube | cylinder | sphere | cylinder |
| /3.1 | final-0-1 | cylinder | cylinder | cylinder | cylinder |
| /3.1 | final-0-2 | sphere | sphere | sphere | sphere |
| /3.1 | final-0-3 | cone | cone | sphere | cone |
| /3.1 | final-0-6 | blue | blue | blue | blue |
| /3.1 | final-0-9 | red | red | red | red |
| /3.1 | final-0-28 | cube | cube | cylinder | cube |
| /3.1 | final-0-30 | yellow | yellow | yellow | yellow |
| /3.1 | final-0-31 | green | green | green | green |
| /3.1 | final-1-2 | cube | cube | cylinder | cube |
| /3.1 | final-1-3 | cube | cube | cylinder | cube |
| /3.1 | final-1-10 | cube | cylinder | cylinder | cylinder |

## Fix activity, vary the individual's own reader stage

The same saved final activity is inferred by that individual's own birth, initial-fit and final-fit reader. No real subject is refitted or transplanted, and readers are not interchanged between individuals.

| Kernel | Birth reader | Initial-fit reader | Final reader | Final reader on zeros |
|---|---:|---:|---:|---:|
| /2 | 1/12 | 6/12 | 11/12 | 1/12 |
| /3.1 | 1/12 | 9/12 | 10/12 | 1/12 |

Both birth readers output red for every selected question. On zero activity the final /2 reader always outputs cone and /3.1 sphere, each accidentally matching one case. This diagnoses input dependence, not whole-Core removal.

For /3.1 green cube final-0-0, identical final Core activity yields **cube with the initial-fit reader but cylinder with the final reader**. The readout function therefore determines this error under a fixed activity representation. It is not evidence that every earlier reader is superior: initial-fit scores9/12 versus final10/12 in this sample, with two corrections and one regression. On fixed final activity /2 has 5 corrections and 0 regressions. Historical readers may see distribution mismatch; these conditional comparisons cannot be added as percentages of the full learning process.

## Intervention and interpretation

One-time silence targets all135,576 source edges in /2 and136,068 in /3.1 through the existing intervention API. Immediate state changes are limited to silence membership and sequence; weights, nodes, configuration, clock and reader are preserved. Rescue is a separate same-source copy silenced and immediately unsilenced before the question, not rewinding a copy after it has developed.

Existing node activity, two in-flight signal/inhibition events and new edges remain. Silent copies form 8374–10550 new edges per /2 question and 8934–10464 per /3.1 question; no surviving original edge escapes the silence set. New transport sent across the twelve questions falls by99.897% and99.715% respectively, but residual association is nonzero. These are transport measurements, **not cognitive contribution percentages**.

The specific necessity question is answered positively for the identified cases. Semantic storage or independent concept recognition inside Core is not localized: silencing also changes general activation/inhibition and the reader's input distribution. Direct-sensory alternative readers were not trained. The diagnosis does not explain all five /3.1 shape errors or uniquely assign its overall deficit. It establishes reader-stage boundary changes as a concrete issue to investigate before assuming retention tuning is the remedy. Further semantic-specific or learning-history controls require a new protocol, not post-result sample expansion.

## Provenance and isolation

Originals use `research:e67-causal-probes-20261012`, under `E:\ThreeMindData\experiments\2026-10-12-e67-causal-probes`, linked to E67 through its normal research APIs. Complete parent systems and source hashes remain unchanged; terminal traces are not represented as resumable trained individuals. Preregistered plan/source hashes, per-case traces, reader-stage results and completion/analysis receipts are preserved. Earlier E67 reports and negative results remain intact.

The independent diagnostic process uses one low-priority CPU thread on one logical processor and no GPU. The existing /4 host continues without restart or curriculum change. Disclose the overlapping interval in later wall-clock comparisons; it is not exclusive-machine benchmarking. `record_cost.py` appends resource-aware database reference accounting, keeping adjunct evidence separate from main-course per-arm costs without changing the frozen publisher.

[Protocol](design.en.md) · [Reproduction and continuation](README.md) · [Original two-arm interim report](../2026-10-11-shape-color-kernels/report.en.md)
