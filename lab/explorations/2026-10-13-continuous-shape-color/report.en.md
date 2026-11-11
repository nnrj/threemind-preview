# E68: continuous whole-system shape/color teaching, correction and examination

October 13, 2026; revision 1. Liu Dongxu determined the research question and protocol. AI assisted with tools, execution, verification and this report. See the [preregistration](design.en.md) and [training protocol v 3](../../../docs/en/training-protocol.md). Historical evidence and negative results remain intact.

## 1. Conclusion

**In this batch, `/3.1` wins on final accuracy, `/2` on speed; final edge counts are similar.** Fresh complete individuals finished teaching, sampling, three corrective rounds and 72 final questions continuously. No per-question restoration or selection of an earlier minimum-loss peripheral state occurred. Final held-out-position scores were 66/72 (91.67%) for `/2` and 71/72 (98.61%) for `/3.1`: five answers and 6.94 percentage points apart. Both attribute questions were correct for 26/32 and 31/32 shape/color pairs, respectively. Both groups scored 72/72 in development rounds 2 and 3.

This batch **does not show overall behavioral degradation of `/3.1` relative to `/2`; it shows reduced final error at greater computational cost**. Native advance calls took 1.896 times as long, the final complete checkpoint was 4.34% larger, and the final edge count was 0.45% lower. `/2` is preferable for speed in this workload and `/3.1` for its observed final accuracy; no unspecified composite score is imposed.

There is one individual per version and one seed. Questions within a continuous life history are not independent subjects. Stable version-level superiority requires independently registered repetitions with new blank individuals. No rollback-dependent causal intervention was performed here, so the gain cannot be assigned entirely to Core's retention operator.

## 2. Conditions and continuity

The identities are `e68-2-223` and `e68-3.1-223`, running their explicit `threemind.continuous-memory/2` and `/3.1` identities on the Rust native backend. Each starts with zero time, nodes, edges, peripheral updates and recent history, with `previous_subject=null`. Neither E67 nor engineering specimens were reused. Core seed 223 and sensory seed 91, each version's default dynamics, and the declared eight-word personal reader were retained; no Core change or new kernel subversion was introduced.

The centered, clear-view apparatus fixes eye/hand geometry and has no connected motor reader; it does not override produced motor commands. Actual optical sampling and physical wind, temperature, humidity and gravity/support background remain connected. Text uses the existing anonymous character mapping at 50 ms/character, strength 1. The teacher provides ordinary sentences. The reader receives only four kinds of raw Core activity, with no image/scenario-answer bypass; labels are used for teaching, supervised reader calibration and scoring.

There are 104 initial lessons and 167,135,108 later lessons:514 teaching statements, plus 32 exact-error reanswers. Each corrective course uses the two groups' previous error union, similar cases and mixed review of successful cases. Sampling stages contain 48, 95, 81, 72 questions. Four 1200-update fits yield 4800 retained updates and 296 cumulative supervised samples. Each personal reader retains its own last weights, Adam and RNG; Core/body simulated time pauses during fitting. Final questions use two held-out positions, 36 questions each, one continuous pass and question-end argmax, with no final-answer retraining.

Each individual reaches 1555 simulated seconds:31,100 recorded frames at 50 ms intervals and 1259 complete boundaries including birth. `analyze.py` checked all 62,200 frames, 2518 parent-linked boundaries and 12,590 checkpoint members, including hashes, sizes, stage joins, body time, identity and committed update counts. Core, personal peripheral/optimizer/RNG, body, mappings and recent readout state are retained. Ordinary test experiences continue into the next stage; fitting does not restore an older physical state. `review_results.py` separately checks frozen sources, final boundaries, video source hashes and matched final-question conditions without creating or advancing a subject.

## 3. Scores and residual errors

| Continuous stage | /2 total; shape; color; pairs | /3.1 total; shape; color; pairs |
|---|---|---|
| After initial teaching | 51/72; 21/40; 30/32; 15/32 | 53/72; 23/40; 30/32; 17/32 |
| After correction 1 | 65/72; 33/40; 32/32; 25/32 | 69/72; 37/40; 32/32; 29/32 |
| After correction 2 | 72/72; 40/40; 32/32; 32/32 | 72/72; 40/40; 32/32; 32/32 |
| After review 3 | 72/72; 40/40; 32/32; 32/32 | 72/72; 40/40; 32/32; 32/32 |
| Final held-out positions | 66/72; 35/40; 31/32; 26/32 | 71/72; 39/40; 32/32; 31/32 |

A pair requires two correct attribute answers about the same object/position; these can occur in different contexts, rather than one combined utterance. Development is repeatedly tested and informs correction; it is not a feedback-free final test.

The first correction fixes 17 formerly incorrect questions in each group but causes 3 formerly correct answers to fail in `/2` and 1 in `/3.1`, net gains 14 and 16. Round 2 fixes the remaining 7 and 3 errors without new failures. Round 3 follows the preregistered 108 mixed-review lessons despite perfect development scores and preserves those scores. This supports the whole teaching/calibration procedure in this batch while preserving transient regressions as negative evidence. Teacher input, repeated exposure and supervised reader updates were not independently ablated.

At the two final positions, `/2` scores 32/36 and 34/36; `/3.1` scores 36/36 and 35/36. Both answer 66 questions correctly, both fail one, and only `/3.1` succeeds on five; no question is correct only in `/2`.

| Final question | Target attribute | /2 answer | /3.1 answer |
|---|---|---|---|
| `final-0-4` | red cylinder: shape | cube, wrong | cylinder |
| `final-0-9` | red cone: color | cone, wrong attribute | red |
| `final-0-11` | red cube: shape | cylinder, wrong | cube |
| `final-0-28` | yellow cube: shape | cylinder, wrong | cube |
| `final-1-2` | yellow cube: shape | cylinder, wrong | cylinder, wrong |
| `final-1-29` | blue cube: shape | cylinder, wrong | cube |

The common error occurs at 1521–1522 simulated seconds, position `(-0.018,0.006)`. Final evaluation changes position, order and life-history context together. It cannot isolate forgetting, retinal discrimination or the reader as the unique cause. No restorative retry or extra final-error teaching was performed. E67's 71/72 and 67/72 use independent checkpoint copies and different calibration selection, so they are not a controlled single-factor contrast with E68; their original evidence and correction remain.

## 4. Performance and size

| Measurement | /2 | /3.1 |
|---|---:|---:|
| Simulated seconds | 1555 | 1555 |
| Native advance calls | 124400 | 124400 |
| Native advance seconds | 3295.25 | 6247.26 |
| Complete-state save seconds | 6553.28 | 7377.49 |
| Core capture seconds, nested in saving | 608.48 | 704.89 |
| Activity observation seconds, including native observation | 185.52 | 189.55 |
| Raw-clip JSON encoding seconds | 109.86 | 113.59 |
| Raw-clip gzip seconds | 36.74 | 37.63 |
| Raw-clip write seconds | 12.14 | 12.86 |
| Personal-reader fitting seconds | 34.01 | 33.52 |
| Sum of stage wall seconds | 10493.59 | 14289.10 |
| Final nodes | 370 | 350 |
| Final edges | 119454 | 118922 |
| Latest complete individual MiB | 6.22 | 6.49 |
| Compressed Core/host portion MiB | 4.81 | 5.08 |
| Personal peripheral/optimizer/RNG portion MiB | 1.409 | 1.409 |
| All arm originals GiB, excluding replays | 8.883 | 9.313 |
| All historical complete boundaries GiB | 7.984 | 8.398 |

Native timing includes the call boundary and return overhead, measured with wall clocks on an ordinary shared workstation. The 89.6% native slowdown is present before attributing storage, plotting or video costs. Final graph size did not increase, so growth of the final graph cannot explain it; historical structures and operator-specific contributions still require profiling. This is not an exclusive-hardware microbenchmark.

Saving every unit independently and flushing complete state is the largest engineering cost here:2518 snapshots versus roughly 6.2–6.5 MiB for one current individual. Nested timers must not be summed. Raw-clip gzip does not include compression inside complete-state saving. Stage wall time excludes the subsequent platform attachment synchronization, inter-group waiting, analysis and video rendering. Incremental checkpointing is a future tooling option, not permission to remove E68 continuity evidence.

See the [delivery/storage supplement](delivery.en.md) for final file/video/shared-metadata totals. MiB/GiB are binary units; file lengths, live memory, database pages and deployed software must not be conflated.

## 5. Evidence and replay

Original root: `E:\ThreeMindData\experiments\2026-10-13-continuous-shape-color`; managed resource `research:e68-continuous-shape-color`. [Platform experiment](http://127.0.0.1:8877/research-records?project=1017ffd1-3d45-4194-bf23-23b1127b4e39&experiment=a272a6d0-958a-529b-bf2f-9b4fc9e7a3a9).

Paths below are relative to that root; the platform references originals without duplicating a full evidence package:

- `analysis/verified-results.json`: full result/continuity audit; `analysis/review-details.json`: delivery cross-check.
- `arms/<version>/<stage>/trials`, `clips`, `predictions.json`: questions, answers and recorded activity. `chain` holds boundary witnesses; `boundaries/001258` is the final complete individual.
- `replays/2/replay.mp4` and `replays/3.1/replay.mp4`: each 779.1 seconds, 1280×1024, 10 fps,H.264, 17 chapters. Each `export.json` gives source hashes and chapter timing.
- `replays/index.html` links 13 full-sampling HTML chapters per group. The videos include actual activation, inhibition, direct and associative curves against continuous internal time.
- Video speed is 8× teaching, 4× calibration sampling, 2× development and 1× final, with 1.3-second answer-reading holds. Four fitting summaries show saved results; no activity is invented during simulated pauses and replay never runs the model.
- `source-reference/manifest.json`, course JSONs, `questions.json` and each `blank-birth.json` preserve protocol, implementation and birth provenance.

Both video streams decode completely; actual encoded frames were inspected for time, Chinese text, real retinal samples, errors and four curves. Authentication expiry queued durable platform requests without stopping or resetting the subjects. Login was restored and queued records synchronized. The supplement and [execution notes](notes.en.md) document receipts and storage. E67 and `/4` remain stopped; the author's manuscript was not edited.

## 6. Remaining questions

These results support finite shape/color learning and corrective improvement under the declared continuous conditions. They do not independently establish subjective consciousness, open vocabulary, active eye/hand control, long unreviewed retention, or decisive Core-versus-reader causation. The personal reader itself learns from 296 supervised samples and must be acknowledged as part of the system.

Recommended next studies are multiple fresh-seed repetitions, spatial/order controls for the yellow-cube confusion and separately authorized causal branches. This report does not start them or revive `/4`. Current parameters, errors and historical evidence remain unchanged.
