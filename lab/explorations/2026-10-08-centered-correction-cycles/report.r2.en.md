# E66: measured blank-start correction-cycle results

> **Revision r2 · 2026-10-10**
> Revision reason: Verified original-file relocation; append location-resolution guidance and preserve the experiment conclusions.
> Original: [report.en.md](report.en.md); parent r1: [report.en.md](report.en.md)


[中文](report.zh.md) · [Original registration](design.en.md) · [Retention addendum](retention-check.en.md) · [Verification](verification.md) · [Handoff](HANDOFF.md) · [Training protocol](../../../docs/en/training-protocol.md)

October 8, 2026, Beijing time. **One new blank complete subject completed 3 correction/reinforcement/review/calibration rounds. Fixed development: 53/72 → 72/72. Last fresh-position confirmation: 70/72; later-registered old-error retention: 2/7, confusable contrasts: 7/7.** The original maximum was three rounds; recorded stop reason: `three-round-limit`. Fixed development, final held-out confirmation and the later diagnostic have separate roles. Scores from different confirmation positions are not matched before/after effects.

## 1. Fixed development bank

Each position has36questions: four gray shapes and both attributes of all16colored shapes. Round0 follows initial teaching/calibration and precedes correction. A conjunction requires two independently restored attribute answers to be correct, not one simultaneous two-word response.

| Correction rounds | All attributes | Shape | Color | Both attributes correct |
| --- | ---: | ---: | ---: | ---: |
| 0 | 53/72 | 27/40 | 26/32 | 14/32 |
| 1 | 72/72 | 40/40 | 32/32 | 32/32 |
| 2 | 72/72 | 40/40 | 32/32 | 32/32 |
| 3 | 72/72 | 40/40 | 32/32 | 32/32 |

Baseline to final development: 19wrong-to-correct, 0correct-to-wrong, 0persistent failures and 53retained successes. Round one corrected all19baseline errors and retained all53successes. Full per-round predictions and `results.json` preserve subsequent changes.

## 2. Fresh-position confirmations

| Round / position | All | Shape | Color | Both attributes | Evidence role |
| --- | ---: | ---: | ---: | ---: | --- |
| 1 / 1 | 33/36 | 17/20 | 16/16 | 14/16 | later development / 后转开发 |
| 1 / 2 | 35/36 | 19/20 | 16/16 | 15/16 | later development / 后转开发 |
| 2 / 1 | 34/36 | 18/20 | 16/16 | 14/16 | later development / 后转开发 |
| 2 / 2 | 35/36 | 19/20 | 16/16 | 15/16 | later development / 后转开发 |
| 3 / 1 | 34/36 | 18/20 | 16/16 | 14/16 | final held-out / 最终留出 |
| 3 / 2 | 36/36 | 20/20 | 16/16 | 16/16 | final held-out / 最终留出 |

Each round uses a different reserved pair of positions. Failed early confirmation results are sealed, then explicitly reclassified as development for teaching. Cross-round confirmation differences are not paired gains. The last confirmation positions occur in neither teaching nor fitting. Conservative bounding-box projections for all four shapes at20positions remain inside the original clear center: maximum absolute coordinate0.06264044 versus half-width0.075. Every recorded eye/hand command is zero.

| 位置 / Position | 对象 / Object | 属性 / Attribute | 实际回答 / Answer |
| --- | --- | --- | --- |
| 1 | 黄色立方体 | shape | 圆柱体 |
| 1 | 红色立方体 | shape | 圆柱体 |

## 3. Actual teacher feedback and review

| Stage | Demonstrations | Failed-question reanswers | Already correct on reanswer | Immediate correct demonstrations |
| --- | ---: | ---: | ---: | ---: |
| correction-1 | 160 | 19 | 1/19 | 19 |
| correction-2 | 121 | 4 | 0/4 | 4 |
| correction-3 | 120 | 3 | 1/3 | 3 |
| initial-teaching | 104 | 0 | 0/0 | 0 |

There are 505 demonstrations and 26 failed-question reanswers immediately followed by ordinary correct sensory statements. Round one covers 19 failed questions/11 types, 160 lessons and 283 simulated seconds. Round two covers four first-confirmation cube-shape errors: yellow at both positions, green and gray at one position, all previously answered cylinder; 121 lessons/209.5 seconds. Round three covers three second-confirmation cube errors: red/yellow at one position and blue at the other; 120 lessons/207 seconds. Every round includes one-factor neighbors and rehearsal of the complete 36-type grid.

Initial teaching retains E64's104lessons/180seconds. Concentrated demonstrations recur every1.5seconds; the last two initial review start intervals are18and30seconds. Full correction-round reviews recur at60and72seconds for the same type. Interleaved lessons count toward these intervals. Raw timing and `teaching-intervals.json` retain actual times. This is dense-to-sparse practice, not a fitted human Ebbinghaus schedule.

## 4. Later-registered retention diagnostic

Registered at09:48 and executed only after the original loop: restore final complete copies to re-answer all previously reclassified confirmation failures plus matched confusable contrasts, under a24-question cap. Freeze the bank by the declared rule before answering, exclude the final never-trained bank, and do not use this diagnostic for model selection or further fitting.

Old errors: 2/7. Contrasts: 7/7, originally 7/7. There are 5 persistent old errors, so 72/72 on the fixed development bank cannot replace exact-condition retesting. Full rows are in `cases/retention-retest/predictions.json`. These are exposed development examples, not fresh generalization evidence.

## 5. Calibration and complete continuity

| Stage | Correct fixed calibration records | Minimum training loss | Computed updates | Committed-state updates |
| --- | ---: | ---: | ---: | ---: |
| initial-fit | 48/48 | 0.00002191 | 1200 | 1200 |
| fit-1 | 118/120 | 0.01800970 | 2400 | 2351 |
| fit-2 | 192/192 | 0.00141516 | 3600 | 2802 |
| fit-3 | 264/264 | 0.00004930 | 4800 | 4002 |

Create `e66-blank-223` from zero: continuous-memory/2,Core223,sensory/text91, its own untrained eight-word peripheral at birth. The birth clock and update count are zero. No learned E64/E65 state is imported; reuse of a birth seed is not an independent-seed replication.

Questions last1second/20ticks with eight samples spanning the whole answer-free query. Continue personal weights,Adam and RNG on all earlier calibration records plus72new records per round. Offline calibration leaves Core/body unchanged; minimum training loss selects matching weights/optimizer/RNG, explaining computed versus committed counters. Teaching leaves peripheral weights unchanged. Inference receives only declared raw Core activity, with no truth or scene-category input.

Preserve Core,queues/clocks,body/world,mappings,current/recent activity,lesson cursor and personal learning state. Isolated next-input/activity/Core and next-weight/Adam/RNG restoration agree. Every fit preserves complete physical/Core/recent state field by field. Final mainline age is879.5simulated seconds, at `cases/fit-3/system`. Independent evaluation copies do not write back and are not independent trained subjects.

## 6. Interpretation and remaining work

The combined package of feedback,similar-example/old-example rehearsal,broader calibration and continued fitting improves this subject's fixed development answers. Teaching,coverage,fitting and elapsed time change together; no single component or Core concept-learning contribution is isolated. Interpret fresh confirmations and exposed-error retention within their respective scopes. New shape classes,long-term retention,free scenes,eye control,a second training source and connection attribution remain untested.

Read-only comparison of the four first-confirmation cube failures with matched same-color/position cylinders finds distinct retinal input and distinct sampled Core activity in every pair. Distinctness does not establish sufficient discriminability or identify the failure mechanism. `recorded-shape-differences.json` and `diagnose.py` preserve this comparison; it adds no simulation or learning.

New peripheral-calibration positions remain fixed at `(.006,-.006)` and `(-.006,.006)` each round. The continuous subject experiences teacher correction at farther failed positions, but post-teaching question activity at those positions is not added to peripheral fitting. Residual errors may therefore involve reader adaptation to position changes; no matched comparison identifies this as the cause. A later study could recollect already-reclassified failures and nearby examples for personal calibration, with fresh final questions. This proposal was not executed here. E66 used the frozen protocol v2; subsequent v2.1 guidance records coverage checks and exact-condition error retesting without changing this experiment.

The explicit Ebbinghaus-based schedule comparison is unexecuted. A later design should specify its curve/algorithm and model-time units,match demonstration counts,stimulus dose,total duration and recency,and measure several retention delays. Distinguish a literature curve from this model's fitted retention curve. General increasing-spacing results do not show that curve matching is better.

## 7. Evidence

21completed stages,0stopped records,792complete creations/restores,one trained source,148.02aggregate compute minutes including evaluation,restoration and the supplement. Replay preserves all1321clips/33230frames in16chapters, including every success,failure,teacher statement,review,calibration and test.

Workspace: `.work/centered-correction-cycles-20261008`; replay entry:`replays/index.html`; local Lab project:`2bece525-31f1-4df8-93cf-cb3bd8dc9132`. Complete snapshots,frozen source/design,raw activity,selection records and bilingual reports are archived; `delivery.json` records publication details. E63 STOP,E64 historical gates,old experiments and Core/defaults remain intact.

## 8. User-requested consolidation audit after completion

After the three-round loop, the user proposed excessive forgetting or disabled consolidation as possible explanations. A read-only audit confirms plasticity and edge_consolidation_enabled are true in continuous-memory/2, with unchanged configuration at five mainline times and the registered native implementation matching frozen sources. Of 144,159 final edges, 88,279 have stability at least 0.99. Consolidation was enabled; stability itself still decays on a common time scale, without a separate per-edge time constant that keeps lengthening with cumulative use. Whether more persistent protection is needed remains open and is not an established explanation for residual errors. Core, parameters and saved subjects remain unchanged; no simulation was added. [Audit and formula limits](consolidation-audit.en.md)


> **Storage-location revision · 2026-10-10**
> This edition adds the verified move of the selected originals to `E:\ThreeMindData`. Stable scientific identities and hashes, experiment dates, measurements and conclusions remain unchanged. Paths in the preserved body describe historical sources; use the registered evidence resolver for current locations. Repository documents and frozen fixtures remain in place, and source copies are retained. Structured query data and running checkpoints remain in the database. This annotation does not assert that missing historical evidence was recovered.
