# First 3-SAT pilot: Local choice, solving benefit and connection contributions

1 November 2026. Item R42, version v1. Eight independently born sources; the apparatus source is separate. This first report does not replace historical studies.

**Conclusion: normal teaching does not improve full-test success; the sustained-policy target fails; WalkSAT clearly wins this batch.**

## Purpose and prospective expectations

The question is whether ThreeMind can use a taught local preference during continuous 3-SAT search and gain an actual solving benefit. A 3-SAT instance requires a Boolean assignment satisfying every three-literal clause. An action flips one variable.

G1 requires normal teaching to improve mean SAT success over shuffled teaching by at least 10 percentage points, with improvement in at least six of eight sources. G2 requires target silencing to reduce mean zero-break choice on eligible non-noise decisions by at least 20 points, with an absolute mean matched-silencing change no larger than five points. Every relevant arm/source must have at least 20 eligible decisions; all matching must pass; sham and restored scientific trajectories must match intact exactly. G3 compares actual success, flips and runtime without presupposing a ThreeMind win. G1 and G2 answer distinct questions.

This is the registered eight-source exploration. Sources, not problems, branches or decisions, are the independent statistical units. Paired source effects and 10,000 fixed-seed source bootstrap draws are reported. The registered targets are not altered or followed by additional training on these test results.

## Division of work

External code randomly selects an unsatisfied clause and randomly orders its three candidate variables. It computes the number of currently satisfied clauses that each flip would break, called the break count. An input adapter encodes this as four anonymous categories: zero, one, two, or at least three. Core receives personal category channels, not the formula, satisfying assignment or problem identifier.

The teacher demonstrates a zero-break preference using genuine local states of separate training formulas. This is an experimenter-selected existing heuristic. Sixteen examples per category, with corresponding irrelevant control pairings, produce 128 presentations of 250 ms plus one second before and after: 34 internal seconds. Shuffled teaching rotates the category paired with the positive port, preserving marginal input/port counts, dose and time.

The port reader is fixed from birth and never trained. It subtracts the activation of one port from the other. Each candidate is presented for 200 ms, with a read at 110 ms. The highest score wins, ties are random, and 25% of decisions use uniform random exploration. Candidates are queried sequentially with continuously evolving Core state, no per-problem resets and no answer teaching during tests. A fixed background stimulus maintains activity. The chosen variable is flipped before the next percept. This is therefore a hybrid local-search system with a Core learning component.

Each source receives 24 satisfiable test formulas: twelve with 12 variables/50 clauses and twelve with 20 variables/84 clauses, interleaved. Random 3-CNF is conditioned on satisfiability by DPLL rejection, without planted assignments or exact overlap with teaching formulas. Each test allows at most 96 flips. An independent verifier checks every reported assignment. Failure to find a solution is UNKNOWN. Two unsatisfiable sentinels per source use differently ordered clauses of the same contradiction construction. They check false positives, are excluded from SAT success rates and are not independent capability samples.

## Causal comparisons and integrity

Each normally taught parent produces five explicit research copies: intact, sham, target, matched and restored. Shuffled teaching supplies the sixth Core condition. The targets are four taught category-to-preference connections; matched controls are four taught connections excluded from action readout. Selection uses teaching and the parent state only, never tests. The immediate intervention changes only the existing silenced-edge set; restoration must recover the complete scientific state exactly. Each branch then continuously experiences the full test sequence.

Random local search and WalkSAT use the same local constraint information and flip limit. Random local search uniformly selects a variable from the unsatisfied clause. WalkSAT prefers zero break; otherwise it chooses randomly with probability 0.5 and minimizes break count on the other decisions. DPLL prepares and verifies materials; it is not a Core solver component.

The separate apparatus source checks passive observation, complete save/restore and subsequent responses, sham/restoration, intervention fields and matching. Six pure algorithm tests compare DPLL against small exhaustive searches and check break counts, sentinels, trajectories and materials. Six further auditor tests reject corrupted assignments, break counts, stimuli, complete input chains and success flags. These are checks by the executing assistant, not an external replication.

## Results, analysis and scientific conclusions

**Conclusion: normal teaching did not improve full-test 3-SAT success. Target connections caused a small local-choice difference, below the preregistered magnitude. WalkSAT wins this batch on success, flip cost and measured solving time. This training/readout arrangement should not be scaled directly to larger SAT problems.**

An early learned readout effect is present: target silencing removes its nonzero scores, whereas matched silencing does not change success. The effect does not sustain the complete search sequence. This is an unfavorable application result and rejects the specific expectation that this short teaching course provides a sustained, useful solving preference. It identifies a bottleneck in the current curriculum, query timing and fixed readout.

### G1: actual solving benefit fails

| Condition | Solved/192 | Success | Mean flips | SAT solve-function seconds |
| --- | ---: | ---: | ---: | ---: |
| Normal teaching | 98 | 51.04% | 68.09 | 9.367 |
| Sham | 98 | 51.04% | 68.09 | 9.325 |
| Target silencing | 96 | 50.00% | 69.21 | 9.529 |
| Matched silencing | 98 | 51.04% | 68.09 | 9.578 |
| Restored | 98 | 51.04% | 68.09 | 9.934 |
| Shuffled teaching | 98 | 51.04% | 68.24 | 9.973 |
| Random local search | 93 | 48.44% | 69.29 | 1.556 |
| WalkSAT | 172 | 89.58% | 34.17 | 0.838 |

Every condition includes eight sources and 24 SAT problems per source. Unknown outcomes remain in the denominator and cost 96 flips. No initial assignment already satisfied its formula; all successes are newly found assignments. Solve-function time excludes teaching, checkpointing and API work.

Normal and shuffled teaching both solve 98/192 (51.04%). The paired source mean difference is 0.00 percentage points, with a 95% source bootstrap interval of −2.08 to +2.08 points. Two sources improve, two decline and four tie. **G1 fails: this batch does not support the registered benefit of at least 10 points**, which also lies outside the exploratory interval. Normal teaching solves five more problems than random local search, but shuffled teaching solves the same 98; those five cannot be credited to the normal teaching history.

By size, normal and shuffled teaching both solve 70/96 at 12 variables and 28/96 at 20. WalkSAT solves 92/96 and 80/96; random local search solves 61/96 and 32/96.

### G2: a small connection effect, below the sustained-policy target

Source-averaged zero-break choice is 38.715% under sham and 37.886% under target silencing: a decrease of 0.829 points, with a 95% source bootstrap interval of 0.411 to 1.297 points. The mean matched-silencing change is zero. The prospective target decrease was at least 20 points. All matching passes; relevant source/arm denominators range from 339 to 461, exceeding the required 20. This is not an invalid or undersampled endpoint. Eligible decisions are those actually encountered on each condition's trajectory; they are not claimed to be identical stimulus pairs across diverging paths.

**G2 fails. The scientific conclusion is that the four taught connections make a small positive contribution to local choice but do not establish the preregistered sustained preference.** This result is not zero connection influence. Target silencing solves 96/192, two fewer than normal teaching. Matched, sham and restored conditions each solve 98/192. Intact, sham and restored scientific trajectories and complete states agree exactly for every problem, giving reversible-intervention evidence for the small contribution.

### G3: WalkSAT wins

WalkSAT solves 172/192 (89.58%), 74 more than normal teaching and 38.54 points higher. It solves more problems in all eight sources. Its mean capped flip cost is 34.17 versus 68.09; cumulative SAT solve-function time is about 0.838 versus 9.367 seconds. **WalkSAT is the actual efficiency winner in this batch.** The established heuristic works on these materials; the current Core apparatus does not sustain its benefit.

## Retrospective read-only diagnosis

This descriptive analysis was added after primary scoring. It changes neither G1/G2 nor the subjects. Of 43,830 intact candidate queries, only 169 (0.386%) have a score magnitude exceeding the fixed decoder's 1e−12 numerical tolerance. None of the 44,472 target-silenced queries exceeds it. Matched, sham and restored conditions each retain 169.

Across the eight intact sources, the last nonzero score occurs at internal time 55.11–60.91 seconds, or 21.11–26.91 seconds after teaching ends. All later query scores are zero. The first problem-boundary observation of an edge-free graph is later, at 132.4–156.4 internal seconds. These are observed checkpoint times, not exact edge-deletion timestamps.

**Useful readout differences cease first; the original connections subsequently cease to persist.** With equal scores, the declared decoder breaks ties randomly, so most later search relies on random choice. This accounts for the absence of sustained solving benefit. Readout cessation precedes observed connection removal; the later removal alone does not explain the entire early loss of expression.

A future, separately registered short continuous-query study should distinguish query order, read timing, fast activity/inhibition and retention, with sustained expression of the taught preference as its complete target. Only after that succeeds should fresh SAT materials test benefit. This is a recommendation; no extra teaching, reruns, kernel changes or further batch were triggered here.

## Integrity, cost and implications

The independent auditor instantiates no Core. It checks 1,664 complete trajectories, 1,248 whole-state transitions and input digest chains, 16 teaching histories, same-time matching weights/degrees/activity in eight sources, and 416 sham/restoration problem comparisons. All 128 sentinel trajectories end UNKNOWN. There are zero false SAT claims and zero ordinary-test rollbacks. Primary analysis, retrospective diagnosis and originals remain separate.

Compute-host wall time is 23.86 minutes; peak private memory is 103.28 MiB. The sixteen teaching histories consume 0.737 seconds of computation. The largest saved problem-boundary graph has 13 nodes and 32 edges. The longest branch reaches 1338.4 internal seconds and the maximum input count is 9327. DPLL reference time for all test materials totals 0.158 seconds and is excluded from the student. Full checkpointing and per-problem boundary checks account for substantial wall-clock overhead; full-batch wall time is not pure solver computation.

Pre-analysis originals occupy 21,102,427 logical bytes (20.12 MiB). Archive, full API download and allocated disk use are listed in the [delivery verification](delivery.md). The 5/4/5/25 GiB commit/RAM/C/E reserves remain intact, with no resource pause or new death. Core, historical individuals, experiments, automations and author manuscripts are unchanged.

For ThreeMind, the completed result is a specific negative application finding: this short curriculum and single-time fixed port readout do not turn a taught local preference into useful sustained 3-SAT benefit. A small causal effect of taught internal connections remains established. The next concrete research question concerns sustained expression and retention. Complexity-class equality is outside this finite pilot's registered target; no P=NP or P≠NP conclusion is proposed.

[Prospective protocol](protocol.en.md) · [Auditor](analyze.py) · [Retrospective diagnostic](diagnose.py) · [Delivery](delivery.md)
