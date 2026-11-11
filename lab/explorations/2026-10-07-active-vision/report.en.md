# E59: a cheaper eye, but useful gaze selection is not yet learned

2026-10-07 · [中文](report.zh.md) · [Measured results](results.json) · [Registration](design.en.md) · [Tools](tools.md)

## Main findings

**A movable eye with a sharp center and coarse periphery substantially reduced sensing and graph cost while retaining the scene. It did not produce reliable shape/color pointing.** After ten simulated seconds in the same scene, edges fell from 1,080,548 with the uniform whole-scene retina to 87,888 with the scanning eye: about 92% fewer. Advancement, sampling and recording took 100.5 versus 11.5 seconds, about an 8.7-fold speedup. No answer-based object crops were introduced. The scene, visible self, teacher and physical background remained present.

Internal connections also affected behavior. Silencing existing edges changed all twelve hand endpoints and four nearest-object choices. Restoring the edges restored all twelve endpoints and choices. However, normal/silenced/empty-command scores were 4/12, 5/12 and 4/12, with **zero actual target arrivals in every group**. Thus this apparatus demonstrates an internal contribution to changed movement, not a demonstrated benefit to correct selection. This does not retract earlier intervention evidence from E50 or E58 under their own conditions.

Engineering, bounded recognition and closed-loop controls are complete. Deformation, plural and negative pointing remain prerequisite-gated. Core equations, defaults, historical instances and evidence were not changed.

## Teaching was present; its review schedule needs correction

Fixed and scanning instances each received 104 lessons over 180 simulated seconds. Four shapes and four colors each received ten consecutive initial lessons and three review rounds. A physical teacher marker indicated the object while a short sentence such as “这是球体。” entered through the unchanged text mapping, one character per 50 ms at ordinary intensity 1. Wind, temperature, humidity, gravitational support, body and eye feedback continued. The teacher marker was removed for testing.

“Checkpoint selection by validation” refers to selecting the **external Transformer reader's weights** during 1,200 optimization steps. It does not select, delete or roll back Core experiences. Core teaching snapshots, inputs and subsequent processes are retained. External training/validation/test sets contain 72/24/24 questions with separate layouts. Targets are external supervision and offline scores, never an answer channel supplied to Core or to the fixed reader during evaluation.

There is a substantive curriculum limitation. Initial lessons start 1.5 seconds apart. Later round delays increase, but the first review interval varies from 12 to 106.5 seconds across concepts, followed by 18 and 30 seconds. Therefore this is **not a strictly expanding per-concept review schedule**. The earlier broad “dense-to-sparse review” description needs this correction. Early concepts may wait too long. Error-specific corrective Core teaching was not performed in this batch. Failure after this curriculum cannot be reported as failure after sufficient teaching and correction.

A read-only optical audit sampled the predetermined midpoint of every scanning lesson. The target was sampled in 96/104 midpoints. The teacher obscured about 15.5% of target subrays; no otherwise-visible midpoint target was completely occluded by the teacher. This measures visibility, not comprehension, and does not rule out partial loss of useful contours.

The scanning group uses **one eye physically changing optical direction within an intact scene**. It is not the old four simultaneous object crops. Those appear here only as a ten-second cost baseline.

## 1. Cost reduction and remaining graph density

| Same scene, 10 simulated seconds | Visual ports | Nodes | Edges | Advancement/sampling/recording | Sampled peak process RAM |
| --- | ---: | ---: | ---: | ---: | ---: |
| Old four fields, 4×4 each | 256 | 273 | 74,244 | 10.3 s | 612 MiB |
| Uniform whole retina, 16×16 | 1,024 | 1,040 | 1,080,548 | 100.5 s | 1,324 MiB |
| New eye, fixed | 272 | 288 | 82,644 | 10.2 s | 632 MiB |
| New eye, prescribed scan | 272 | 297 | 87,888 | 11.5 s | 649 MiB |
| New eye, scan, lower input gain | 272 | 297 | 87,888 | 10.3 s | 659 MiB |

The eye has 68 receptors: a 6×6 center and a 6×6 periphery excluding its central 2×2. Each averages fixed subrays and supplies RGB and distance. The periphery covers larger areas. Eye motion changes directions, not channel identities. Alongside 272 visual ports are 32 existing body/weather/contact measurements and ten signed eye measurements. Main gain is 0.03×64/68; the low-gain comparison uses 0.0075. No sample normalization or no-cue subtraction is used.

Scanning uses 1.18 times the old four-field edge count. After teaching it has 411 nodes/157,126 edges; fixed vision has 402/150,116. However, ten-second edge densities remain close to one. Existing co-arrival rules allow weak positive co-touched inputs to form candidate edges, and simultaneous dense visual input still creates dense structure. Lower gain did not reduce this comparison's edge count. No new eye-dependent identity proliferation or explicit forced attachment to an existing large network was found. Reducing sensory dimensionality is not a proven repair of long-term edge formation or retention. Core thresholds and the disabled amplitude TopK gate remain unchanged.

## 2. Recognition remains unreliable

An optical test distinguishes four gray shapes at the same central location. That establishes available sensory differences, not learned recognition. Shared local readers consume unchanged activation, inhibition, direct arrival and associative arrival, or direct incoming stimuli in the bypass control. They receive external target supervision and are not presumed to be pure intention translators.

| Hand reader, 3-second process | Train nearest/72 | Validation nearest/24 | Test nearest/24 | Test arrivals/24 | Color/shape/combination, 8 each |
| --- | ---: | ---: | ---: | ---: | --- |
| Fixed, Core activity | 44 | 6 | 8 | 7 | 4 / 2 / 2 |
| Fixed, direct input | 34 | 12 | 6 | 6 | 2 / 2 / 2 |
| Scanning, Core activity | 26 | 7 | 5 | 2 | 2 / 2 / 1 |
| Scanning, direct input | 30 | 5 | 5 | 2 | 3 / 2 / 0 |

These scores execute the decoded direction through a calibrated hand servo. Nearest-object correctness and arrival within 0.20 m are distinct; the former can reflect spatial bias at low performance. All one/two/three-second scores are retained; the best instant is not chosen retrospectively.

During scanning tests, the target remained inside the field for an average 92.3% of samples but inside the sharp center for only 14.0%. At the final sample, even an offline oracle choosing the closest receptor projection could land within 0.20 m for only 14/24 questions before motor error. This identifies a coarse-periphery versus precise-pointing geometry limitation, not fourteen cognitive errors. Looking, inspecting and pointing need to be learned as a process rather than treating a peripheral pixel as an exact coordinate.

## 3. Reading all frames did not solve the problem

The original reader subsamples sixteen of sixty actual observations in three seconds; Core receives all inputs. A separately [registered amendment](sequence-amendment.md) compares all sixty samples against sixteen using the same larger-capacity reader, training data and optimization budget. Core teaching, inputs and raw outputs are unchanged. Twenty-four fresh-layout questions were scored only after selection was frozen.

| New scanning reader | Validation nearest/24 | Fresh holdout nearest/24 | Holdout arrivals/24 |
| --- | ---: | ---: | ---: |
| Core activity, full 60 | 4 | 4 | 0 |
| Core activity, 16 | 7 | 5 | 0 |
| Direct input, full 60 | 7 | 1 | 0 |
| Direct input, 16 | 5 | 5 | 2 |

The complete-process tool is retained, but it has no demonstrated gain here and is not promoted to a default. Sparse sampling omits some query events, not every red/blue distinction: the unchanged adjacent-byte encoding retains another differing frame. Omission alone is not an established root cause.

## 4. Closed-loop behavior and connection interventions

Baseline recognition did not meet the registered 18/24 expansion gate. A bounded diagnostic uses the first four questions of each category in the predetermined fresh-holdout order: twelve total, without selecting successes. Every question restores the same scanning teaching state. Two separately trained readers control eyes and hand; observations are resampled after physical motion. The original reader trained on one/two/three-second windows is used here; the new full-process reader was trained only on three-second windows and is not treated as a validated short-prefix controller.

| Actual closed-loop condition | Nearest/12 | Arrivals/12 | Summed associative-arrival integral |
| --- | ---: | ---: | ---: |
| No further eye commands; Core-driven hand | 2 | 0 | 67.70 |
| Prescribed scan; Core-driven hand | 1 | 0 | 77.32 |
| Learned gaze; eye and hand read Core | 4 | 0 | 65.70 |
| Both commands cut; Core still receives environment | 4 | 0 | 152.47 |
| Learned gaze; existing edges silenced | 5 | 0 | 3.69 |
| Learned gaze; existing edges restored | 4 | 0 | 65.70 |
| Learned gaze; direct sensory input bypass | 2 | 0 | 90.14 |

The fixed-eye control preserves common initial eye position/velocity and therefore includes brief inertial settling. Empty commands likewise do not remove wind or body inertia. Silencing affects edges present in the snapshot, not already emitted signals or subsequently formed edges; association is not literally zero.

Silencing changes all twelve hand endpoints and four nearest choices; rescue restores every endpoint/choice and recorded arrival integral. Association falls about 94.4%, establishing an internal contribution. Yet correctness does not fall. Empty commands change all twelve choices while retaining four correct nearest objects, exposing the limitations of that aggregate score alone.

Learned gaze keeps the target in the sharp center for about 9.7% of samples, versus 14.3% under prescribed scanning. Target field coverage is about 76.3% with Core-based learned gaze and 97.1% with direct-input gaze, yet the latter scores only 2/12. Seeing, query selection and physically reaching the target are different parts of the task.

Association occurs during scanning, but useful decision-making from scanning has not been established here. Initial fixed/scanning ten-second association integrals are approximately 0.000816/0.000814. Scanning raises mean activation, but changed sensory drive cannot simply be renamed an association benefit. The user's prediction about association during useful gaze decisions remains open for better taught gaze behavior.

## 5. Next work, in order

1. Repair **per-concept** review scheduling and log its actual intervals. Add teacher correction, renewed demonstration and restatement after errors, with matched observation controls. This correction phase is not completed here.
2. Teach how to look: demonstration of fixation/tracking, followed by teacher-free, answer-coordinate-free evaluation. Verify stable central inspection before precise pointing. Demonstration is environmental teaching, not an answer tag injected into Core.
3. Establish reliable external reading of already taught processes. Moving retinal coordinates, limited fitting and training on prescribed rather than learned motion all remain candidates. Use actual closed-loop teaching records and distinguish external decoding from Core memory before changing dynamics.
4. Once basic eye–hand behavior works, resume deformation, plural/negative pointing and more selective activity ablation/transplantation. These remain open tasks; unperformed tests are not failed tests.

The cost-saving eye is useful to continue with. Global Core attention is neither implemented nor validated by this batch. Shared receptor reading, which helped earlier experiments, is retained; it does not alone remove the new difficulties of moving retinal coordinates, coverage and teaching.

## Delivery and resources

Versioned sensing, bus/raw-output/physics integration, process readers, gaze analysis, complete state restoration and Python/CLI tools are available. The [complete replay](../../../.work/active-vision-20261007/active-vision.html) contains both 104-lesson courses, all 84 closed-loop trials and three ten-second apparatus controls: 299 clips and 12,840 recorded frames, including errors. It supports PNG/WebM and does not advance Core. These are laboratory tools, not a claim that all controls are integrated into the production world editor.

Fourteen affected tests pass. The full replay passes 1440/390-width playback, overflow, screenshot and actual WebM decoding checks. A GTX1650 runs external-reader CUDA training; Core retains its CPU path. There are 39 completed stages, 98 creation/restoration branches and 76.10 cumulative compute minutes, with no budget-stopped simulation. One Core random seed is used: questions and branches are not independent brains. Local pre-archive evidence is about 1 GiB; final local/database totals are in `delivery.json`. Shared usage went from 80% to 82% by simulation completion, not an exact task billing measurement.

Only this study is archived, using one-pass ZIP CRC and ordinary upload verification. No old large-data scan, cleanup or user-service change was performed. Inputs, activity, world snapshots, external weights, predictions and teaching audits are preserved in the independent research project. Bilingual reports use existing research-document services. [Execution notes](execution-notes.md) · [Discussion source](../../../docs/en/history/sources/2026-10-07-active-vision.md)

## 2026-10-07: system-continuity scope note

Teaching/sampling use scripted scanning; the learned closed loop installs newly fitted eye/hand selectors. This handover cannot refute eye-movement learning by one continuing system. Foveation cost reduction and fixed-reader intervention effects remain. Co-development interpretations require R40 retesting; scripted scans remain explicit instrument controls.

[Continuity audit / 连续性核查](../../../docs/en/plans/system-continuity-audit.md)
