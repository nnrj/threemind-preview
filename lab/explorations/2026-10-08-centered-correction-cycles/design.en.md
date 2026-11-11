# E66: blank-start central recognition with correction cycles

Registered October 8, 2026, Beijing time, before this study's stimulation or questions. The user requests correction, similar-example strengthening, rehearsal and retesting from a blank complete subject. Follow [training protocol v2](../../../docs/en/training-protocol.md). An explicit forgetting-curve comparison is recorded separately for subsequent design; it is not a second variable in this batch.

## Subject and retained reference

Create `e66-blank-223`: continuous-memory/2, Core seed 223, sensory/text seed 91, its own untrained eight-word peripheral from birth, clock zero. Check the preserved E56 birth and ordinary-text configurations. E64/E65 supply methods and historical comparisons, not learned state; reusing the birth seed is not an independent-seed replication. Keep originals intact.

Retain E64's complete physical eye (68 receptors, fine center/coarse surround), object geometry, ordinary stimuli, anonymous mappings, wind/body background and fixed eye/hand apparatus. One unmarked object occupies the clear center. Conservatively project the four shapes' bounding boxes at all registered positions within central half-width 0.075; do not enlarge images or receptors.

Retain ActivityController: projection 48, one temporal Transformer layer, four heads, feedforward 96, dropout zero. Inference receives only raw Core activation/inhibition/direct/associative. Each answer-free question lasts 1 second/20 ticks, with eight evenly rounded samples spanning first to last; score final argmax. A combination succeeds when its two independently restored attribute questions both succeed, not by simultaneous two-word output.

Keep the continuous teaching lineage's Core, clocks/queues, body/world, mappings, current/recent activity, personal weights/Adam/RNG and lesson cursor. Calibration/evaluation questions use independent complete copies and do not write back. Offline peripheral calibration does not advance Core/body; this is E64's declared alternating procedure, not continuous online co-development. No E63 branch, connection intervention or old-gate change.

## Initial stage

Repeat E64: four gray shapes and four colored-cube color concepts, ten consecutive 1.5-second demonstrations each, then three interleaved eight-lesson reviews preceded by additional background intervals of 0, 6 and 18 seconds. Total 104 lessons/180 simulated seconds. Cycle `(0,0),(-.008,0),(.008,0),(0,.008)` with repetition indices continuing into review.

Collect E64's initial 48 actual question records: eight basic examples at four positions, plus the eight pairs `(s,s),(s,(s+1)%4)` at center, both attributes. Calibrate its own peripheral for 1200 steps: AdamW .002, weight decay .0001, batch<=32, gradient clip 1. Select minimum full training loss every 50 steps and the last step, retaining matching Adam/RNG and both computed/committed counters. Then collect the initial development baseline.

## Up to three correction cycles

The complete 36-type grid is four gray-shape questions plus both attributes of 16 colored shapes. At `(.010,.010)` and `(-.010,-.010)`, this gives 72 development questions with stable IDs and fixed shuffled orders. They are explicitly allowed to choose lessons.

Freeze each round's curriculum from the preceding development failures and, if applicable, a failed early confirmation explicitly reclassified as development:

1. Re-present every failed question at its failed position in the continuous teaching subject, ask for 1 second, record the current response, immediately demonstrate the correct ordinary statement for 1.5 seconds. Retain original errors even when the current answer has become correct.
2. Deduplicate error types by object/attribute; give three further consecutive 1.5-second demonstrations per type at registered teaching positions.
3. Build similar examples: same shape across colors and same color across shapes for shape errors; corresponding one-factor changes for color errors; add the other attribute of a colored object. Union these with prior successes and eight basics, covering all 36 types. Order failed types, neighbors, then remaining old examples; repeat this order for three 1.5-second-per-item reviews with additional gaps 0, 6 and 18 seconds. Save actual per-item timing; do not claim a human forgetting-curve fit.
4. Strengthening/review positions cycle `(0,0),(-.012,0),(.012,0),(0,-.012),(0,.012)`; direct correction retains exposed development positions. Collect 72 new answer-free calibration records, the 36 types at `(.006,-.006),(-.006,.006)`, from the taught complete source.
5. Continue its own weights/Adam/RNG for 1200 steps on all old plus new calibration records, at most 264 records and 4800 computed steps. Development/final activity never enters fitting; test scores never select weights. Retest the fixed 72-question bank and record corrections, regressions, persistent errors and conjunction scores.

At most three rounds. If development has no errors, proceed to independent confirmation rather than unnecessary training. After round three, confirm regardless of development score and stop. Per round there are at most 144 failed-question feedback events (72 development plus 72 reclassified confirmation), three extra demonstrations for at most 36 error types and three complete reviews, subject to aggregate budgets. No extra rounds or Core changes to chase success.

## Confirmation and interpretation

Reserve one fresh two-position bank per possible stopping round, 36 questions per position: round 0 `(.013,-.013),(-.013,.013)`; round 1 `(.014,-.014),(-.014,.014)`; round 2 `(.016,.012),(-.016,-.012)`; round 3 `(.018,-.006),(-.018,.006)`. Open a bank only at 72/72 development or at round three.

Both sets must reach 36/36, with shape 20/20, color 16/16 and conjunctions 16/16 each, to claim all-correct within this scope. If an early confirmation fails and rounds remain, seal its original result, explicitly reclassify it as development and correct its failures; the next confirmation must use its fresh reserved positions. The final confirmation remains untrained. Freeze inference and retain every success/failure and raw process.

Report both-position development scores each round, paired transitions, corrected/similar/previously successful examples, final sets and readability of retained calibration records. This is one trained source. Teaching, broader calibration coverage and further fitting change together; no single-mechanism attribution or unregistered follow-up experiment is made. A lack of improvement is preserved for discussion.

## Evidence and limits

Use `.work/centered-correction-cycles-20261008`. Freeze design, banks, generated curricula/error sources, complete birth/stage states, process records, calibration activity, predictions and selection. Verify complete restore by next input/activity/Core and next weights/Adam/RNG on isolated copies. Preserve all frames in chaptered replays plus a full archive. Deliver bilingual reports and synchronized history/backlog.

Measured weekly usage starts at 24%; no new stage at 29%, hard stop at 31%, refresh actual readings every 30 minutes. At most 1024 complete creations/restores, 180 aggregate compute minutes including failed phases, 12 hours orchestration, 4 GiB local plus positive shared-database growth soft limit, 6 GiB archive hard limit. RSS<=4 GiB, free RAM>=2 GiB, C/E free space>=5/15 GiB. One process, two CPU threads, GPU allocation<=60%, STOP honored. Do not reset/increase budgets; incomplete work is not negative evidence. Use only the already-running localhost:5433/threemind database for this study, without service lifecycle changes, unrelated job claims or paid models.

## 09:48 prospective addendum link

The original frozen design and main loop are preserved. Add a separately reported [retention check of reclassified confirmation failures](retention-check.en.md) after the loop, within original budgets. The last never-trained confirmation remains held out.
