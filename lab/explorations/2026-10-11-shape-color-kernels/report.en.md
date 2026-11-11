# E67: shape/color teaching, correction and performance on /2 and /3.1

[中文](report.zh.md) · [Preregistration and amendments](design.en.md) · [Execution notes](notes.zh.md) · [/4 performance review](performance-review.en.md) · [Training protocol](../../../docs/en/training-protocol.md)

**Revision3 two-arm interim report, reviewed October12,2026.** Both fixed courses, final evaluations, complete input comparison and videos are finished; the four-arm study remains in progress. Experimental dates: October11–12,2026. Managed resource `research:e67-shape-color-kernels`; formal record `7867ff04-5973-5e66-a438-ae84bfe46174`.

**Scope addendum, October12: this remains the revision3 two-arm interim report.** The user has reauthorized both `/4` conditions. A separate four-arm report will follow; completion of this report must not finalize all of E67. [Revision4 addendum](design-r4.en.md)

## 1. Conclusions and final scores

**For this shape/color task, `/2` outperformed `/3.1`: it reached perfect development scores earlier, answered four more final questions correctly and needed about half the native computation. `/3.1` showed no score benefit to compensate for its cost.** This is a measured regression under this course and one paired training seed, not a universal ranking or proof that excessive forgetting caused the difference.

| Final held-out locations | /2 | /3.1 |
|---|---:|---:|
| All attribute questions | **71/72 (98.61%)** | **67/72 (93.06%)** |
| Shape | 39/40 | 35/40 |
| Color | 32/32 | 32/32 |
| Both shape and color correct | 31/32 | 28/32 |
| First perfect development score | After correction round1 | After correction round2 |

Every final error called a cube a cylinder. `/2` missed the yellow cube at the first final location. `/3.1` missed green, blue, red and gray cubes there and the red cube at the second location. Errors did not overlap:66 questions were correct in both, five only in `/2`, and one only in `/3.1`. Gray objects have shape questions only and are excluded from the colored-pair denominator.

Both final readers answered all288 training examples correctly and both scored72/72 on development round3. The observed weakness is therefore **shape recognition after a location change**. Perfect fitting does not settle recognition, and different-location tests do not by themselves establish loss of an old memory. This study did not separate Core representation from personal-reader generalization or their interaction. The two `/4` arms remain to complete the four-way comparison; this interim result does not change kernel defaults.

## 2. Paired changes across correction rounds

All four development evaluations below are complete. Final locations differ from development locations and cannot be paired as identical questions.

| Stage | /2 total | /2 shape | /2 color | /2 both attributes | /3.1 total | /3.1 shape | /3.1 color | /3.1 both attributes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Initial | 53/72 | 27/40 | 26/32 | 14/32 | 55/72 | 26/40 | 29/32 | 16/32 |
| Correction 1 | 72/72 | 40/40 | 32/32 | 32/32 | 69/72 | 37/40 | 32/32 | 29/32 |
| Correction 2 | 72/72 | 40/40 | 32/32 | 32/32 | 72/72 | 40/40 | 32/32 | 32/32 |
| Correction 3 | 72/72 | 40/40 | 32/32 | 32/32 | 72/72 | 40/40 | 32/32 | 32/32 |

After round 1, `/2` corrected all 19 old errors and retained all 53 correct answers. `/3.1` corrected 16, regressed on 2 and remained wrong on 1. At the second development position, its remaining errors were a blue cylinder called a cube, a green cube called a cylinder and a red cylinder called a cube. Both arms had previously answered the first two correctly; both had missed the third. The common second-round curriculum included all three. After it, `/3.1` corrected all three and retained the other 69, reaching 72/72. `/2` retained 72/72. The registered third review round still follows before final held-out evaluation.

## 3. Matched teaching and complete individuals

Both individuals began blank on October 11: `e67-2-223` and `e67-3.1-223`, with Core/peripheral seed 223 and sensory/text seed 91. `/2` retains its original stability mechanism; `/3.1` uses its default adaptive half-life. Each retains its real defaults, own Core, input queue/clock, body/world, mappings, recent activity, expression peripheral, Adam and random state. Restoring evaluation copies does not add independent training seeds.

E64/E66's centered single-object apparatus uses E56's repetition, complete-question sampling and temporal reader procedure. The MuJoCo physical scene has one 68-receptor eye, 56 checked shape/location combinations with a maximum conservative projected extent of 0.06217, inside central half-width 0.075, fixed eye/hand and ordinary text and physical background. Fixed gaze is an apparatus condition, not learned fixation. This is not a background-only delayed retention experiment.

The eight-word peripheral receives only its own Core's activation, inhibition, direct and associative activity, without direct image values, scene truth or question-category metadata. Labels serve teaching, supervised calibration and scoring. Questions enter through ordinary text sensation; eight uniformly spaced frames span the complete 1-second, 20-step question. The final eight-word argmax is scored. A shape/color pair means two separate same-source attribute questions both correct, not one free-language two-attribute answer.

Initial teaching contains 104 lessons over 180 simulated seconds: ten consecutive examples for each of eight concepts, followed by three reviews with extra gaps of 0, 6 and 18 seconds. Every correction round takes the union of both arms' preceding development errors. Both reanswer these questions and immediately receive ordinary correct statements; each error type receives three additional examples. All 36 object-attribute types are reviewed three times, including similar shapes/colors and previously correct items. Curriculum, input order and simulated duration match. The visible object and physical background remain during review gaps.

Every round adds 72 ordinary calibration questions and deduplicated actual error conditions, retains all old material and continues each individual's reader for 1200 updates. The 48-dimensional, one-layer, four-head temporal Transformer has feedforward size 96, dropout 0, AdamW learning rate0.002, weight decay0.0001, batch≤32 and gradient clipping 1. The lowest training-loss point retains its matching optimizer/RNG; test scores never select it. Calibration does not advance Core/body and is instrument fitting, not additional consciousness lessons.

Two fixed development positions provide 36 questions each and guide correction. Final positions `(.018,-.006)` and `(-.018,.006)` are absent from teaching/calibration. The final test occurs once after three rounds and cannot trigger more training. Concepts and shape/color types were reviewed; locations are held out, not new categories or unseen combinations. Each question restores its declared complete source independently and does not write its experience back into the teaching line.

This is a system comparison at one paired training seed, including each learned peripheral. No connection ablation was performed; overall performance cannot be attributed entirely to Core, and the eight-word task does not establish free language or subjective consciousness. Earlier E56/E64/E65/E66 subjects, criteria and findings remain intact.

The completed read-only audit confirms equal hashes for the actual frame-by-frame input sequences in every teaching, calibration-sampling, development and final stage. Across each of the five evaluations, neither arm had a byte-identical input sequence or reader-activity window assigned contradictory labels. This excludes exact contradictions, not difficult-to-separate distinct signals. No simulation or training was performed by the audit. The paired table is `analysis/paired-question-scores.csv`; full verification is `analysis/verified-results.json`.

## 4. Performance and graph size

Each arm received497 lessons and865.5 mainline simulated seconds. Including calibration sampling and evaluation copies, each advanced1513.5 simulated seconds through121080 native advance calls and655 complete restorations. The following totals come from17 saved stages:

| Measurement | /2 | /3.1 |
|---|---:|---:|
| Native Core advance | 3375.49s | 6455.88s |
| Native wall seconds per simulated second | 2.230 | 4.266 |
| Complete-system restoration | 2735.66s | 3358.22s |
| Total stage work, including restoration | 6934.52s (115.58min) | 10729.51s (178.83min) |
| Observation calls | 189.95s | 195.56s |
| Process JSON encoding | 108.61s | 112.84s |
| Process gzip compression | 37.05s | 38.05s |
| Process original writes | 12.54s | 13.31s |
| Complete-checkpoint saving, including packaging | 181.25s | 222.77s |
| Four instrument-fitting timers | 39.71s | 39.40s |
| Final mainline nodes | 400 | 398 |
| Final mainline edges | 135576 | 136068 |
| Directed edge density | 84.95% | 86.12% |
| Mean edge weight | 0.561208 | 0.124091 |

`/3.1` required about1.913 times the native advance,1.228 times the restoration and1.547 times the total stage work. Of its extra3794.98 stage seconds, about3080.39 came from native advance and622.56 from complete restoration. The main gap is already inside native calls, rather than video export or database attachment upload. Final edge counts differ by only492 (0.36%); round3 teaching alone was about2.04 times slower. Merely retaining more edges is therefore insufficient to explain the observed gap. Final scale does not describe every earlier graph, and no function-level CPU profile was collected.

The `/3.1` mainline retention counters record about1.932 billion edge settlements and7.46 million node settlements. These are work counters, not distinct edges or measured CPU percentages. Its lower mean weight does not automatically establish worse memory; that causal relationship would require a separate intervention.

Native calls include return encoding. Observation includes nested native observation, and checkpoint-saving totals include internal work; do not sum nested timers twice. Stage totals exclude ending platform attachment synchronization, video export and this analysis. End-of-stage RSS is not peak memory; sequential ordinary workstation measurements are not exclusive-hardware microbenchmarks. The revision4 comparison will separately measure all experiment files, one complete individual, Core encodings and isolated-restoration RSS. Cumulative originals are not the size of one consciousness.

Overnight non-execution is excluded from kernel time. `/4` preflight and partial teaching are reported in the separate [performance review](performance-review.en.md), not mixed into these two arms' scores or timings.

## 5. Interruption, scope and tools

The original three-kernel registration expanded to four conditions before birth in revision 2, including both `/4` retention schemes. The user subsequently selected `/2` and `/3.1` only and deferred both `/4` arms. Revision 3 was registered before correction round 1, preserving old protocols and source freezes. Later shared curricula use only the two active arms' errors; no rebirth or peripheral replacement occurred.

The assistant edited files on October 11 evening but failed to register revision 3 or launch continuation. The user's October 12 complaint led to verification that no runner existed and STOP remained. This was an execution omission, not slow-kernel computation. Actual continuation began at 09:07 China time under an independent host that sequences simulation, analysis and export.

Tools added explicit kernel selection while retaining saved identities, isolated empty-scene preflight, matched curricula, complete recording, durable execution, question-level comparison, scientific figures and replay export. Core dynamics and numerical defaults were not changed for the study; no new kernel subversion was introduced. Calibration sampling, teaching, development and final evaluation are identified separately.

## 6. Evidence, replay and remaining work

The original root is `E:\ThreeMindData\experiments\2026-10-11-shape-color-kernels`. Each video covers1177 clips and30270 original sample frames, with7710 output frames across17 chapters: H.264,1280×800,10fps,771 seconds (12:51). Teaching plays at8x, calibration sampling4x, development2x and final1x, with answer-reading holds. Four fitting stages use saved-result summary cards rather than fabricated activity. Codec, dimensions, duration, frame count and SHA256 were checked, alongside sampled error and fitting-summary frames. Each arm's13 HTML chapters retain all sampled frames. The old revision3 index describes the then-current `/4` deferral; the later scope addendum and revision4 supersede that decision.

| Replay | File relative to the original root | SHA256 |
|---|---|---|
| /2 | `replays/2/replay.mp4` | `cf682b5d5476d7f9b81eee18af9b6dfde4f01813d1f0583441b546e071d96f66` |
| /3.1 | `replays/3.1/replay.mp4` | `bfa9d5373c170241fb7c19c84f13d435355fb3766041eaba7fb38fd676ea7c5f` |

Each `export.json` preserves source hashes and chapter boundaries. `computation-complete.json` establishes only the two-arm revision3 computation. An ordinary-account API check after computation found36 stage entries and5401 evidence references, with execution still `running`; exports and continued `/4` work add further references. `publish_interim.py` registers these bilingual texts and the execution-note snapshot without invoking the old two-arm finalizer. The full-study byte-verification receipt and formal completion await all four arms; current coverage is not represented as complete.

[Platform record](http://127.0.0.1:8877/research-records?project=7f6d896d-ba85-49fa-a034-9969fb57503f&experiment=7867ff04-5973-5e66-a438-ae84bfe46174). Originals remain in managed storage; only code and small reports enter Git, without push.

During revision3, `/4 adaptive-half-life` retained a complete lesson48 checkpoint at72 simulated seconds and65 original lesson clips; later clips are not a complete checkpoint. `/4 legacy-stability` was not formally born. At13:32 China time on October12, revision4 was registered and the independent host actually resumed default `/4` from that source, with the stability arm to follow. A separate four-arm/storage report remains due. The user-authorized hourly continuation is active; low disk pauses `/4` first. Long periods without review, multiple independent training seeds, eye control and new categories were not tested here.
