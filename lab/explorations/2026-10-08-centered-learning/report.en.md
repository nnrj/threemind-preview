# E65: central continuation fixes targeted errors, but shape transfer remains unreliable

[中文](report.zh.md) · [Preregistration](design.en.md) · [Verification](verification.md) · [Handoff](HANDOFF.md) · [Training protocol](../../../docs/en/training-protocol.md)

October 8, 2026, Beijing. Completed. Continue E64's complete individual and its own peripheral, with fixed eye/hand and a single object in the clear central field. **Primary 33/36; changed-position confirmation 30/36. Color is 16/16 in both; shape is 17/20 and 14/20. All five targeted errors are corrected in both sets, but recognition of every combination is not reliable.**

## 1. Actual answers

| Metric | Before, primary position | After, primary | Confirmation position |
| --- | ---: | ---: | ---: |
| All attribute questions | 30/36 | 33/36 | 30/36 |
| Shape | 15/20 | 17/20 | 14/20 |
| Gray shapes | 4/4 | 4/4 | 3/4 |
| Colored-object shapes | 11/16 | 13/16 | 11/16 |
| Color | 15/16 | 16/16 | 16/16 |
| Objects with both attributes correct | 10/16 | 13/16 | 11/16 |
| Five targeted errors | 0/5 | 5/5 | 5/5 |

Combined correctness requires correct shape and color answers from separate complete copies of the same origin. It is neither simultaneous two-word output nor continuous dialogue. Gray objects are queried only for shape; gray is outside the eight-word answer vocabulary.

The paired primary comparison has five wrong-to-correct, two correct-to-wrong and one still-wrong answer: net +3. Red-cylinder, yellow-cube, green-cylinder and red-cube shape, plus yellow-cone color, are corrected in both post-tests. Previously correct blue-sphere and blue-cone shape answers regress; the correction benefit must not hide that loss.

Hold the **final calibration coverage** fixed when comparing before and after:

| Attribute types | Before | Primary | Confirmation |
| --- | ---: | ---: | ---: |
| 30 types covered by final calibration | 25/30 | 30/30 | 27/30 |
| 6 types never calibrated | 5/6 | 3/6 | 3/6 |

The six uncovered types are both attributes of green sphere, blue sphere and blue cone. Both post-tests get their colors 3/3 and shapes 0/3. Under the original pre-training coverage of 22 types, baseline scores were 22/22 covered and 8/14 uncovered. That is a different grouping, retained in the original results rather than silently substituted.

## 2. Every post-test error

| Object / question | Expected | Primary answer | Confirmation answer | Finally calibrated |
| --- | --- | --- | --- | --- |
| Green sphere / shape | Sphere | Green | Green | No |
| Blue sphere / shape | Sphere | Cylinder | Cylinder | No |
| Blue cone / shape | Cone | Cylinder | Cylinder | No |
| Blue cube / shape | Cube | Correct | Cylinder | Yes |
| Green cube / shape | Cube | Correct | Cylinder | Yes |
| Gray cube / shape | Cube | Correct | Cylinder | Yes |

Thus the remaining problem includes three changed-position failures of calibrated content, not just new combinations. Objects remain inside the clear central field; these are not failures to locate or fixate them.

## 3. Executed procedure and continuity

Start from complete E64 `e64-blank-223`, continuous-memory/2, Core seed 223 and sensory/text seed 91, at 219 simulated seconds and 2400 computed peripheral updates. Hash-check the copied reference and confirm the original is unchanged at completion. E56's four-field success informs the method; the actual subject remains E64's whole-eye eight-word system, without transplanting E56's four-position head.

Freeze the course before E65 baseline answers, using repeated E64 errors. Give each of five targets ten consecutive normal demonstrations, followed by three thirteen-lesson rounds mixing four gray shapes, four colored-cube color examples and the five targets. Each lesson lasts 1.5 seconds; add 0/6/18 seconds before review rounds. Total 89 lessons, 157.5 seconds; the main subject advances 219 to 376.5 seconds with ongoing body/environment input. `lesson-timing.json` records actual starts/ends; `teaching-intervals.json` derives recurrence intervals per concept and exact example/attribute. This is teacher demonstration, not E56's answer-free matched exposure.

Collect 48 genuine answer-free questions from independent complete copies of the taught state. Read eight raw activation/inhibition/direct/associative frames across all twenty steps of the one-second question. Continue the same eight-word peripheral for 1200 updates on old 48+12 plus new 48 examples, retaining weights, Adam and sampling RNG. Select only by full training loss. Computed updates reach 3600; retained-state count is 3452; loss 0.037364 and accuracy 106/108. Read-only rescoring gives old first corpus 48/48, old later corpus 11/12, new corpus 47/48. Before continued calibration, the new query corpus scores 36/48; this is calibration data and is not directly comparable to the different 36-question baseline.

Teaching does not update peripheral weights; offline calibration does not advance Core/body. Full snapshots retain Core, queues/clocks, recent readout, body/world, sensory mappings and personal learning state. This is explicitly registered teaching plus instrument calibration, not continuous online joint learning. Primary offset `(0.010,0.010)` and confirmation `(-0.010,-0.010)` are excluded from this study's teaching/calibration. Full questions, seeds, offsets and budgets are preregistered.

## 4. Interpretation and limits

The complete system answers most central-recognition questions. Color is correct at both reserved positions, and the teaching/calibration package corrects the five historical target errors. **Uncalibrated shape transfer remains unresolved, some formerly correct answers regress, and calibrated shapes can fail after a small position change.** This is not E56-level perfect functional success.

One trained source remains one source despite 160 complete creations/restores; two test sets are not independent seeds. Holdouts cover two small position shifts and specified uncalibrated pairs, not new shape categories, rotation, size, free scenes or dialogue. Teaching, elapsed experience and peripheral calibration change together; no matched-time/no-teaching or fixed-old-reader comparison separates their contributions. No connection intervention was performed, so correct answers are not exclusively attributed to learned Core concepts.

Stop after the registered course; do not fit further using these final errors. A separately registered follow-up could rehearse cube shapes across more positions/colors and preserve earlier correct examples, with fresh held-out positions/pairs to check retention and transfer. This is a recommendation, not an executed extension. E63's STOP, E64's historical gate, Core defaults and original data remain intact.

## 5. Evidence and delivery

All seven stages completed, with no interrupted case; 160 complete creations/restores and 28.39 compute minutes. Replay preserves 247 clips / 6270 frames: all 89 lessons, environmental intervals, 48 calibration queries, baseline and both complete post-tests, including every failure. The standalone HTML is 37,004,739 bytes; it does not simulate Core or invent trajectories.

- Reference: `.work/centered-learning-20261008/reference/system`.
- Taught, before continued calibration: `.work/centered-learning-20261008/cases/teaching/system`.
- Final complete individual: `.work/centered-learning-20261008/cases/final-fit/system`.
- Original frames, predictions and activity: each working `cases/<stage>/`; summary: this directory's `results.json`.
- Replay: `.work/centered-learning-20261008/centered-learning.html`; index: `replay-manifest.json`.
- Local Lab project: `f0b5f84b-0d0d-4837-81b4-9064f7f908d2`; database/archive identifiers are recorded by publication in `delivery.json`.

See the [verification record](verification.md) for actual restoration, optical, actuator and evidence checks. Publication only reads existing results; it does not rerun teaching or Core.
