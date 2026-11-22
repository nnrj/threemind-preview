# R63t4: persistent activity, prefix information, and delayed choice

Prepared on 16 November 2026. Registration and execution require R63t1 and R63t2 to have verified research-API delivery, zero pending requests and no new scientific stop. This batch belongs to the authorized comprehensive 6.3 replication. Production kernels and defaults remain unchanged.

## Questions and candidate selection

Does restoring persistent activity improve delayed choices without saturation or loss of discrimination? Can the prefix candidate distinguish A-B from D-B after continuous teaching and correction with new encodings? Duration and accuracy are separate outcomes.

In historical R51t2, keeping inhibition gain at 0.24 and shortening its time constant from 0.2321354823145728 to 0.0580338705786432 seconds preserved activity after 300 seconds in both exchanged curricula, with final task activation about 0.060–0.081 and no saturation. The other candidate used immediate novelty with inhibitory learning disabled and had not restored prefix discrimination. Subsequent R51t4 tests of these candidates met neither the delayed-choice benefit nor prefix-recovery criterion.

This replication retains those four configurations and all original materials, courses and decision rules to compare the same experiment on 6.3. The new R63t2 candidate selection and rationale will also be frozen at registration. A different new selection will be documented, not silently substituted for a historical condition or misrepresented as matching the original candidate.

## Units and conditions

Four new encoding blocks use birth seeds 941101–941104. Each has two curricula with exchanged C/E relations, two tasks and four configurations: 64 complete systems, nested within four material blocks. They are not 64 independent sources. Apparatus material uses seed 941199 and a separate encoding.

The pair task reuses the 80-presentation A-C/D-E schedule; the prefix task reuses the 210-presentation A, A-B, B-C/D, D-B, B-E schedule. All historical channels receive one invertible XOR permutation, including the frozen background replay. Grouping, strengths and times remain fixed. Pair-task resources have depletion disabled and facilitation time constant 1 second; prefix-task resources have depletion enabled and facilitation time constant zero. These are historical task settings, not all production defaults.

Four configurations apply from birth: the 6.3 reference; shorter inhibition time constant only; immediate novelty with inhibitory learning disabled; inhibition disabled as a saturation control. This compares whole configurations during learning and answering. It does not isolate duration as the sole cause of accuracy differences; R51t2 separately tested post-teaching intervention.

The complete subject includes Core, event queue, observer, executed curriculum, answers and recent activity. There is no body or trainable peripheral. A fixed process readout converts Core activity to one of two choices. Teaching, questions, correction and final tests proceed continuously without per-question restoration.

## Curriculum and final material

After initial teaching, both relations receive three reviews with additional waits of 1, 3 and 9 internal seconds. Four development questions test A and D at delays of 0.5 and 1 second. Each answer is followed by one review of its relation. An error adds two original examples and two examples at 0.9 stimulus strength, with progressively longer onset intervals. There are two bounded development rounds; final errors never trigger further training.

Fourteen final questions include A and D at delays 0.5, 3, 30 and 60 seconds; both cues at 3 and 30 seconds with an untaught anonymous distractor halfway through the delay; and two 30-second blank trials. Prefix-task B follows the first cue by 1 second, and the delay is measured from B. Order is frozen by block and task and shared across configurations and exchanged curricula. Each question starts after a 2-second wait. Cue strength is 0.5 and distractor strength 0.3; new phases receive an independent background pulse of strength 0.2 every 0.5 seconds. Test input contains no C/E answer and receives no feedback. Effects of previous questions remain part of the individual.

Activation, inhibition, direct and associative activity of task, distractor and background nodes are recorded every 50 ms. The fixed readout compares C and E activation integrals over the final 0.5 seconds. An absolute difference greater than 1e-6 activity-seconds selects the larger; otherwise it returns WAIT. All four processes are retained. Neither the scoring time nor the primary formula may be selected after results. These are fixed-rule choices, not embodied movement scores.

## Decisions and verification

Clean 0.5/3-second questions form the short-delay category; clean 30/60-second questions form the long-delay category. Distractor and blank trials are separate. Within each block, results are pooled across the two exchanged curricula.

A retained-inhibition candidate has functional benefit only if at least 3/4 blocks improve long-delay accuracy by at least 10 percentage points and reach at least 75%, short-delay accuracy declines by no more than 5 points, and no more than 10% of task-node observations reach activation 0.95. These are bounded exploratory selection rules, not universal definitions of cognition.

Prefix recovery requires, in at least 3/4 blocks, correct A-B and D-B short-delay choices in both exchanged curricula and at least 75% long-delay accuracy in each curriculum. Exchanging one fixed preference for another does not pass. All errors, WAIT responses, blank false choices, process differences and saturation are reported. Process-level localization before and after B is secondary and cannot replace final accuracy.

Separate apparatus material tests scheduling, scoring, complete restoration, denser observation, observation disabled and host pauses against identical final states. Sources, inputs, question order, selection rationale and protocol are frozen and registered through the research API before execution. Originals, archive and API readback each have a 2 GiB allowance, with 128 MiB for analysis: 6.125 GiB at peak, in addition to the 25 GiB reserve. Commit/RAM/C/E reserves are 5/4/5/25 GiB, checked every second; host budget is two hours and each complete system five minutes. Complete boundaries are saved after questions. Incomplete states or observation effects are preserved and reported, never silently rolled back. Independent arithmetic verification, bilingual reporting and full API readback with zero pending requests close the batch.

## Replication evidence and stopping rules

The entry point is decision.py and the new data directory is delayed-choice-63-rerun-v1. Every formal system is newly created as 6.3, using frozen R63t1 teaching materials. Historical 6.1 data provide method, cost and result references only. Individuals and input envelopes have new identities. The 64 complete systems each undergo 24 phases: 1,536 phases, 3,200 initial/final states and 896 final questions. The four material blocks are independent repetitions; questions and exchanged curricula are nested observations.

Apparatus material with seed 941199 compares ordinary, denser and disabled observation, save/restore and a host pause for identical complete state and observer state. Preparation validates all 32 historical block summaries, four functional comparisons and independent integrals for 42 saved question trajectories. An improvement in one response while the other remains incorrect still fails prefix recovery. Formal analysis checks all state transitions, curricula, corrections, four recorded activity fields, anonymous input delivery and scoring. Final questions must contain no C/E answer inputs.

A clear loss of a previously attained primary goal pauses the campaign after evidence preservation. Repeated historical negatives are reported and closed without unlimited additional training or a new stop. Allocated bytes are recorded per comparable unit. Twice the historical allocation, or more than 50% above the apparatus-based frozen estimate, pauses at a complete boundary; total storage limits and the one-second resource guard also apply. Existing subject directories are not retried automatically. A resource pause requires independent verification before choosing a continuation entry. Orphaned incomplete phases are preserved and reported.
