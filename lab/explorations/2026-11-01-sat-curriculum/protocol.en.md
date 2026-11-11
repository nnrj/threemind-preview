# R42: protocol-compliant teaching and temporal readout for 3-SAT, v2

1 November 2026. Preregistered before formal execution. Source, material and actual implementation hashes are frozen at registration. The author explicitly requested a new SAT run under the training protocol and deferred half-life changes. The v1 evidence and all historical paused studies remain intact.

## Questions and fixed conclusions

Can a complete system taught a local preference, including its personal temporal Transformer, improve bounded 3-SAT local search? The Core receives four anonymous break-count categories (0, 1, 2, at least 3), not the formula. Formula processing, unsatisfied-clause selection and bit flipping are declared environmental algorithms.

G1: the normally taught system must improve solved SAT fraction over random local search by at least 10 percentage points, with a positive lower endpoint of a two-sided 97.5% paired-origin bootstrap interval. Passing supports a useful learned local strategy in this configuration. Missing the threshold is reported explicitly; a wide interval is inconclusive rather than proof of universal inability.

G2: normal versus shuffled Core teaching uses the same effect/interval rule. Both personal readers receive correct peripheral supervision. This compares declared adaptive training conditions: their error-driven later curricula can differ, so it is not a pure single-mechanism ablation. No advantage means no demonstrated additional SAT benefit from correct Core pair teaching in this batch.

G3: every SAT output must pass an independent bit-mask witness verifier. Contradictory sentinels must return UNKNOWN. Any false SAT invalidates performance interpretation. Exhaustion is never reported as UNSAT.

The quantized-rule reference uses the same four categories, zero-break preference and 25% random-choice probability. WalkSAT uses full break counts and its declared zero-break/50%-noise policy; it compares complete implementations, not architecture alone. G1 and G2 use 50,000 paired-origin bootstrap draws with seed 2111199 and 97.5% intervals for the two-comparison reporting family, plus descriptive 95% intervals and every origin's raw difference.

Eight independent seed groups each contain two separately continuous students, normal and shuffled, initialized with matched configurations/materials. Every student owns its reader, Adam and RNG. The 16 students, 24 SAT questions per arm, frames and repeated probes do not inflate paired N=8. This is an exploratory batch, not a 48-origin confirmation or a test of P versus NP.

## Mandatory training preflight and baseline comparison

Reference procedures are E56/E64 and training protocol v3. Task-specific differences are explicit:

1. Each candidate question lasts one internal second, with 20 raw frames at 50-ms intervals. Frames 0,3,5,8,11,14,16,19 span the complete process; all 20 are saved. Seven personal anonymous ports supply activation, inhibition, direct and associative activity in a fixed layout (28 features). No per-question rescaling or baseline subtraction.
2. The established ActivityController architecture is reused: 48-dimensional projection, one temporal Transformer layer, four heads, feed-forward width96, dropout0, two outputs (prefer/avoid). All selected frames participate in temporal attention. No formula, answer, question identifier or channel identity is an inference feature.
3. Each personal reader uses AdamW, lr0.002, weight decay0.0001, batch at most32, gradient clip1, 1200 updates per calibration. Only continue_calibration is used: last-state weights, optimizer and RNG remain continuous; no best-loss rewind. Core time does not advance during this peripheral computation.
4. Initial teaching gives each category ten dense demonstrations, then three interleaved whole-category reviews after additional delays of2,6,18 internal seconds. Each demonstration lasts1.5seconds with five ordinary0.4 co-stimulations at250-ms spacing. Actual per-category times, gaps and doses are saved. This is increasingly spaced review, not a claim to fit a human memory curve exactly.
5. Initial reader calibration samples48 unassisted one-second questions,12 per category, using actual question activity. Correct labels supervise the peripheral only after recording. Teacher-answer co-stimulation is absent during these questions.
6. There are at most three corrective cycles, with at least one review/retest cycle even if initial development is perfect. Each saves mistakes first, then teaches up to16 original error conditions plus all four older categories in two dense passes and2/6/18-second reviews. New unassisted calibration includes original mistakes, similar development conditions and48 older examples; the same reader continues for1200 updates. No mistakes are invented when development is correct.
7. Development after every calibration includes16 balanced local questions and four independent development SAT formulas, each limited to24 flips. Stop correction after at least one review cycle when all16 local answers are correct, no local classification mistakes occur in development SAT, and at least3/4 formulas are solved; otherwise stop after cycle3. Regardless of success, preserve the current individual and proceed to the final assessment without selecting a better earlier state.
8. Complete checkpoints preserve Core, personal weights/Adam/learning RNG, curriculum RNG, recent complete activity, channel mapping, SAT assignment/environment RNG, actuator and curriculum cursor. Save each complete training stage and final formula. Ordinary teaching, calibration, correction and testing never rewind. Observation/save and wall-clock delays do not advance simulation.

Normal teaching pairs categories with the appropriate P/N event; shuffled teaching permutes those labels within each demonstration round, preserving that round's label counts, doses, duration and review structure. Both readers learn from correct peripheral labels. Direct Core activation can reveal category identity to the reader; complete-system success therefore has its declared system-level meaning, while G2 measures the additional contribution of the teaching condition. This distinction is part of the preregistration.

## Materials and scoring

New seeds2111100 through2111107. Each group has eight12-variable/50-clause teaching formulas, separately generated development formulas,12 final12-variable/50-clause formulas and12 final20-variable/84-clause formulas, plus two contradictory sentinels. The existing random3-CNF generator conditions on satisfiability using DPLL without planting an answer. Freeze all materials and validate no overlap; v1 final questions are not reused.

The environment selects an unsatisfied clause, shuffles its three candidates and computes each break count. Their anonymous categories enter Core sequentially. Only the complete recorded Core process enters the reader. The actuator sees three binary predictions; with25% probability it picks randomly, otherwise it selects uniformly among preferred candidates (all avoided means a tie). The formal limit is96 flips. References share initial formula, assignment and RNG seed; divergent actions naturally change later inputs. Unseen-formula transfer is not unseen-category transfer: all four categories were taught.

The26 final problems are experienced continuously. Reader weights freeze while ordinary Core dynamics continue. Final data are never used for calibration, correction or model selection. Report local classification, solved fraction by size, flips including truncation, wall time, internal seconds, training cost, evidence volume and resource peaks. Separate teaching, development and final scores.

## Validation, resources and delivery

Before registration, isolated apparatus checks cover full-window input, actual review spacing, correction coverage, complete-state restoration, the next optimizer update, passive observation, answer isolation and bounded closed-loop traces. Apparatus results do not enter N or choose final problems. An initial spacing assertion wrongly compared against one random interleaved gap; its failure remains preserved. The corrected check compares the last two reviews against the concept's median dense gap. Neither curriculum nor Core changed.

Serial execution. One-second external guard retains5/4/5/25GiB of commit/RAM/C/data storage; starting also requires2GiB commit allowance and4GiB evidence/archive/readback allowance. Scientific-original budget1GiB, host budget2hours, private memory1GiB. Stops take effect only after complete boundaries. A new dead subject or orphaned in-flight record is preserved and reported, never silently rerun. No Core, API, default half-life or historical-study changes.

After computation, perform read-only analysis and independent arithmetic checks; deliver bilingual purpose, expectation, results, analysis, scientific conclusions and meaning for ThreeMind. Register through the existing local unified research API, read back the entire evidence package and verify pending=0 before completion. Update bilingual backlog/history and major-phase Classical Chinese adaptations, pass Git data checks and commit locally only. Append a dated v1 procedure correction without changing its original scores or evidence.
