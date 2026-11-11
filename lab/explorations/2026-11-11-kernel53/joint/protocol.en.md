# R47c: continuous joint development, correction and relearning under four decay curves

11 November 2026, preregistered protocol. [中文](protocol.zh.md) · [/5.3 plan](../../../../docs/en/plans/kernel53.md)

## Goals and scientific decisions

R47a/b compare connections and temporal responses with a fixed instrument. R47c asks whether a complete Core–personal temporal Transformer–actuator system learns choices, retains old abilities, adapts to reversed rules and relearns the original rules, and how the four curves differ. This is an eight-origin exploration; local-instrument successes do not score for this study.

Eight fresh origins use seeds 261111700–261111707. Each has matched individuals under exponential, power-law, inverse logarithmic and power-exponential decay, giving 32 complete individuals and independent N=8. All use H=30, A=10, retained reinforcement age and disabled timescale growth/relaxation, with otherwise identical /5.3 defaults. No historical subject is loaded.

Each stage has unassisted immediate and subsequent 300-second delayed tests. Relevant subgroups must each reach 75% accuracy in both tests; a curve meets a goal when at least 6/8 origins pass.

| Goal | Course and expectation | Scientific decision |
| --- | --- | --- |
| J1 Initial learning and retention | P0→0, P1→1, A0→0, A1→1; balanced four-cue scoring | Whether initial correspondences are learned and retained in this continuous procedure |
| J2 New learning and old ability | Add B0→0 and B1→1; score new B and old P/A separately | Whether learning new correspondences preserves old choices |
| J3 Reversal | A0→1 and A1→0, with P/B unchanged; score A and protected P/B separately | Whether opposite rules can be learned while preserving unrelated ability |
| J4 Return | A0→0 and A1→1 again, with P/B unchanged; separate A and P/B | Whether original rules can be relearned while retaining other choices |

Passing explicitly supports the stated ability. Failure is explained by stage and subgroup. Development and correction scores remain separate from teaching demonstrations, training loss and final scores. Teaching counts and optimizer updates quantify actual relearning cost. There is no equivalent initial-learning versus relearning cost control; lower correction cost is descriptive, not automatically a single-mechanism effect.

A curve meeting all J goals is a capability candidate for this complete task. Goals remain separate rather than forming a universal rank by number passed. Default selection also considers R47a/b retention, weak-experience forgetting and cost. If no curve meets the complete objective, the conclusion is no combined default candidate, retaining positive component findings.

## Complete subject and reference differences

Each subject includes genuine Rust /5.3, anonymous mappings, its own temporal Transformer reader, Adam and learning RNG, every previous calibration sample, the latest 20-frame process, internal clock and input queue, body position, last actuator command, world stage and curriculum cursor. Ordinary teaching, sampling, calibration, development, correction and testing continue that same complete state.

| Component | Procedure and reference |
| --- | --- |
| Temporal reading | E56/R43 one-second, 20-frame windows, eight evenly selected frames; raw activation, inhibition, direct and associative fields without per-question scaling or baseline subtraction |
| Personal reader | Established ActivityController: width 48, four heads, one Transformer layer, feed-forward width 96, dropout zero; two declared output ports, eight raw features, two choice words |
| Continued learning | CalibratedActivity.continue_calibration; AdamW learning rate 0.002, weight decay 0.0001, batch at most 32, gradient clipping 1, 1,200 updates per fit; last state committed, no minimum-loss rollback |
| Task adaptation | R43's three sound/vision/action heads become one anonymous binary-choice task to isolate decay; each new individual gets its own reader, with no replacement of an existing peripheral |
| Actuator | Executes selected position 0 or 1 and returns actual position as proprioceptive stimulation; no physical arm, servo or visual recognition; the study measures choice and memory |
| Calibration | Actual cue-only response windows; labels supervise the external reader only; Core receives no task labels, and inference receives no item number, label, current rule or correct location |
| Later reader learning | Unlike R43's subsequent frozen-reader question, each stage continues joint development; readers are fixed during formal tests while Core and body continue |

The observation API reads the registered port process without advancing time. During optimizer updates, Core and body remain at their current internal instant; the updated reader then continues in the same subject. Optimizer steps are not simulation seconds.

## Teaching, review, correction and materials

The initial stage has four P/A correspondences; later stages have six P/A/B correspondences. Each stage begins with eight interleaved lessons per current correspondence, shuffled by the individual's RNG. Each 1.5-second lesson jointly stimulates the cue and target port at amplitude 0.4 at 0, 0.25, 0.5, 0.75 and 1 second. Reviews follow gaps of 2, 6 and 18 seconds, with one lesson for every current correspondence. A separate background channel receives 0.2 every 0.5 seconds. Actual timing and all inputs are saved.

After the teaching-and-review sequence, each correspondence is sampled with cue-only amplitudes 0.76, 0.8, 0.84 and 0.8. Its full response supervises 1,200 reader updates using the current teacher correspondence. All earlier calibration records remain in the learning pool, which stays below 1,024 samples. Development questions use amplitudes 0.76 and 0.84 per cue. New-learning, reversal and return stages also begin with development questions before teaching to record prior ability and old-rule responses.

If development questions contain errors, each erroneous correspondence receives five additional lessons; all current correspondences receive spaced reviews at gaps 2, 6 and 18 seconds. New response samples join the old pool for 1,200 continued updates, followed by another development test. There are at most two correction rounds, stopping earlier only when all development responses are correct. Curves receive the same correction opportunity and cap. Initial, corrective and development performances are saved separately.

Formal questions use amplitudes 0.72, 0.78, 0.86 and 0.9, absent from calibration/development, in RNG-shuffled order. There are 16 initial-stage questions and 24 in each later stage. Immediate testing is followed by 300 seconds of continued background and then delayed testing in a new order. Delayed performance includes earlier immediate-test experience; pure first-probe retention belongs to the independent delay cohorts of R47a/b. Formal questions never supply correct answers or update/select the reader.

The largest raw output logit determines the choice, which directly drives the actuator. The scorer compares the answer afterwards. Proprioception reports actual position, not correctness. Start position and whether it changed are recorded. Scores describe correct choices, not physical motor learning or eye–hand coordination.

## Freezing, validation, resources and delivery

Origins, rules, course caps and analysis are frozen before execution. Engineering seed 98765063 completed its first 1,200-update calibration and 8/8 development questions in 6.80 wall seconds; it is excluded from scientific N. Before formal execution, full-state restoration must preserve the next answer and optimizer update; read-only observation, four-field windows, actual-actuator feedback and historical witnesses are checked.

Each declared operation has a complete boundary saving before/after hashes, results, model/Adam/RNG dependencies and internal time. New death, orphan in-flight state, inconsistent originals or truth leakage causes preservation and a stop. Ordinary negative results complete normally.

Budgets are 4 GiB originals, 3 GiB private memory and four host hours; commit/RAM/C/E reserves are 5/4/5/25 GiB, checked each second. Startup requires at least 8 GiB commit headroom and 37 GiB disk for originals, archive, readback and reserve. The guard requests complete-operation pauses and never discards partial optimizer progress. Calibration suggests 15–40 minutes; actual costs are reported. One scientific host starts only after R47b delivery; historical experiments and user services remain unchanged.

Independent auditing covers state chains, peripheral dependencies, raw answers and scores. Bilingual reports explain purpose, expectations, results, analysis, scientific conclusions and significance for ThreeMind, with source and subgroup denominators. Full research-API archive readback, matching bilingual documents and pending=0 precede finalization. Joint-development improvements and later default/fifth-strategy decisions require their own actual evidence.
