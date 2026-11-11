# E54: the pointer moves, but reference and shape–colour composition remain unresolved

> **Revision r2 · 2026-10-10**
> Revision reason: Verified original-file relocation; append location-resolution guidance and preserve the experiment conclusions.
> Original: [report.en.md](report.en.md); parent r1: [report.en.md](report.en.md)


2026-10-06. Project:`9bed9a44-fdf2-4947-bca7-af5a854fa691`.

[Registration](design.en.md) · [Execution amendments](execution-notes.md) · [Commands](README.md) · [中文](report.zh.md)

## Main finding

**The activity-to-body interface works:28 of 32 new marker targets were reached. Selecting the correct object from a scene using a pointer or words is still the bottleneck.** Ordinary attribute questions initially scored 42/48, but stricter reference tests and a no-Core-plasticity control prevent treating that score as evidence of learned compositional relations.

Both motor routes remain available. Marker control meets the registered mechanical criterion. Watching a teacher gives partial directional following, without demonstrated mediation by acquired teacher-to-self connections. Their tasks and success criteria differ; their fractions are not directly comparable.

## Apparatus and teaching

A separately versioned, restorable classroom uses MuJoCo surfaces for four solids and four colours. Four fixed spatial optical fields each supply 4×4 RGB/distance rays. Object names are not sensory fields. A planar pointer has inertia, damping, speed limits and boundaries; it is not a grasping robot arm. Teacher-marker coordinates are optical measurements encoded through anonymous sensory ports.

Four grey shapes precede colour cards, then shape/colour questions and answers. Each new teaching sentence repeats ten times before rotation, followed by reviews:368 lessons,326 simulated seconds. All four objects remain. Four diagonal colour–shape combinations are held out, including from training distractors: red sphere, yellow cylinder, blue cube, green cone.

Intensity stays 1. Existing anonymous TextSensor/2, NFKC and channel mapping remain; characters are separated by 50 ms. Actual body, vision and character observations at one sample are explicitly grouped. Physical feedback continues between lessons; no CPU telemetry or altered death rule. Forked trials and repeated frames are not independent learned individuals.

A small Transformer is trained from scratch on raw activation, inhibition, direct and associative activity copied through OutputBus. Attribute heads see six temporal samples; motor heads see the latest four frames. They do not read the stored structural graph. No no-cue subtraction or per-example amplitude scaling is used; ordinary internal Transformer operations remain.

The existing`raw-activity-stream/1`carries read-only observation frames, not solely actual connection-transmission events. That alternative remains untested here. Direct sensory-port responses are not labelled higher-level semantics.

Answers/actions are external **adapter training labels**. At inference no target coordinates, correct words, question IDs or solver outputs are passed directly to the head. However, a head can itself learn to solve a task using sensory responses transmitted through Core. Dependence on Core activity and dependence on learned Core connections therefore require separate controls.

## 1. A usable mechanical interface

32 demonstration episodes provide 864 action examples. Held-out starts and markers receive 150 ms observation then 2 sfree control. Reaching within 0.15 m counts as success; the registered threshold was 24/32.

| Process given to the same motor head | Reached | Median endpoint error |
| --- | ---: | ---: |
| Actual Core activity | **28/32** | **0.067 m** |
| Unrelated recorded activity | 1/32 | 0.844 m |
| Zero activity | 0/32 | 1.594 m |

This establishes continuous force translation and closed-loop control. The adapter learned teacher actions and Core directly sensed the marker. It does not independently establish endogenous motivation, language understanding or an evolved motor instinct.

## 2. High ordinary QA scores concealed a reference failure

Each source has its own head. After teaching, the plastic source has 399 nodes and 130243 edges; the source with Core plasticity disabled from birth has 414 nodes and 0 edges. This switch affects structural evolution too; it is not a surgical removal of one learning formula.

The no-learning control still runs Core; it is not a bypass. This new activity adapter does not replace existing language/graph expressors, and this study is not an exhaustive test of all existing expression routes.

| Test | Plastic Core | No Core plasticity |
| --- | ---: | ---: |
| Adapter training fit | 96/96 | 96/96 |
| Taught combinations, unseen viewpoints | **42/48** | **42/48** |
| Untaught combinations | **6/16** | **6/16** |
| Shape / colour subset | 0/8,6/8 | 0/8,6/8 |
| Fixed full scene, change pointer/category | **8/32** | **6/32** |

Neither head answered in the wrong attribute category on ordinary viewpoint trials. Shuffling actual processes reduces the plastic source's42/48 to 4/48; zeroing gives 6/48. The head uses Core-transmitted content, but matching no-plasticity performance means this success does not require acquired connections.

Ordinary distractors share an attribute with the target, potentially revealing it through scene statistics. Under a fixed scene and four different teacher pointers, only 1/8 scene×category groups changes output. The 42/48 score therefore does not establish understanding of“this.” The stricter assay was registered before execution; original scores and denominators remain intact.

### One external calibration correction

64 balanced-reference, grey-shape and colour-card samples are added to the original 96. The head fits 160/160. The taught Core snapshot stays unchanged: **this is reader calibration, not Core re-education**. Retesting already-inspected failures is explicitly exploratory:44/48 taught combinations, new views;8/16 untaught combinations, split 1/8 shape and 7/8 colour.

New strict-reference scenes score **6/32**, although all 8/8 scene×category groups now vary with the pointer. The head has become pointer-sensitive without reliably selecting the correct object. Changed output is not itself successful relational transfer.

Identical correction for the no-plasticity source also fits 160/160:40/48 familiar-view tests,9/16 untaught combinations, and 9/32 new reference trials, with 6/8 groups pointer-sensitive. Correction establishes no clear plastic-source advantage in composition/reference. The small 44 versus 40 familiar-view difference cannot by itself locate a learned-edge benefit.

### Does the sensor contain distinguishable shapes?

An offline calibration with the **correct optical slot already known** matches held-out depth measurements against grey-shape training-view templates. It scores 112/128 across colours and positions:32/32 each for sphere, cylinder, cone;16/32 for cube. Every error is a cube at view 5 classified as a cylinder. Geometry information is available, while low-resolution viewpoint generalisation remains imperfect.

This oracle bypasses Core and knows the selected field. It is neither a successful consciousness test nor a solution to reference. It separates sensor identifiability from selection, Core learning and expression;128 renders are not 128 consciousness instances.

## 3. Watching another limb

Teacher and learner limbs have disjoint anonymous ports. They co-move ten times per direction. Teacher-only movement then tests 12 unseen angles over 1 second. A displacement over 0.05 m and directional error under 45 degrees counts; this differs from marker-reaching accuracy.

| Core ports visible to the adapter | Normal |56 teacher→self edges muted | Teacher movement hidden |
| --- | ---: | ---: | ---: |
| Self ports only, restrictive causal assay | 3/12 | 3/12 | 3/12 |
| Teacher and self ports | **7/12** | **7/12** | 3/12 |

Matched-other-edge masking and rescue also give 3/12 in the restricted assay; rescue restores its exact direction values. The full reader partly follows demonstrations, but cross-edge masking does not remove the effect. This supports use of teacher-induced activity, not acquired imitation mediation or semantic self/other understanding.

Self-only observation is a research control, never a deployment restriction. An initial attempt failed after 0.2 simulated seconds because the observer did not explicitly declare excluded teacher ports. The observer contract was repaired and a new case retained separately; partial evidence remains. Core and stimuli were unchanged.

## 4. Naming a target without a visible teacher marker

The taught Core receives 120 more guided episodes, ten per taught combination, producing 2400 adapter examples. Each full scene is a2×2 shape–colour grid, each attribute repeated twice. Target location and camera view use independent seeded balanced schedules. Only ordinary sensory text supplies the request to Core; the motor head sees no question text or target coordinates. Physical feedback from guided motion enters Core. The head is fitted afterwards, not continuously updated while autonomously acting.

Held-out views/starts with no target marker and 2 seconds free control yield **2/32 reached,10/32 nearest to the correct object, median error 0.842 m**. Taught pairs:2/24 reached,7/24 nearest correct. Untaught pairs:0/8 reached,3/8 nearest correct. Nearest-object selection has a1/4 reference level; physical reaching does not share that chance rate.

This language-directed pointer is not reliable and does not demonstrate held-out compositional selection. Marker 28/32 versus language 2/32 is not a surgical question-only contrast: curricula, states and adapter inputs differ. It establishes a usable first interface and an unresolved second task, not a diagnosed defective Core rule.

With the same full scene, start and source state, change only the request to another physically present object. **Only 1 of 32 pairs changes the nearest selected object**; median endpoint change is 0.035 m. The new request is selected 8/32 and physically reached 2/32. No pair correctly follows both requests. The concrete failure is **failure to switch the requested target**, not merely imprecise final movement.

Masking edges present at the fork changes reaching 2/32 to 0/32, nearest choice 10/32 to 9/32, and median error 0.842 to 1.156 m. Existing connections affect motor performance, but this low-success assay does not establish their support for correct language-directed selection. Normal input and subsequent learning remain; no death, mapping or dynamics change is introduced.

## Interpretation and next choices

The usable motor interface and the reference-test correction are the clearest gains. **High aggregate QA accuracy can coexist with failure to select the pointed object.** The no-learning control separates adapter competence from acquired Core contributions. This does not revoke E50's distinct connection-masking/rescue evidence.

No Core formula/default change follows from these results. A better next candidate is repeated, balanced teacher pointing, questions and answers in the full scene, delivered as actual Core experience. The current correction trained only the external reader. Independently vary position and view, gradually add distractors, and avoid frequency/view shortcuts. A physically movable gaze/head is another candidate; answer-dependent cropping is not.

Persistent request representation during movement also needs investigation. The motor head currently reads only 200 ms of recent activity. Longer **actual processes** can be compared without supplying hidden targets or answers. Whether this helps is untested; current failures do not localise a Core memory defect.

L/M/S vision, energy-grounded motor motivation, long-term selection, semantic self/other learning, free dialogue and general reasoning remain untested. The second plastic source 279 was deferred after the prerequisite reference failure; unexecuted work is not a negative result. Preserve both motor tools, prefer the mechanically validated interface for subsequent studies, and retain imitation as a research route.

## Evidence and resources

25 stages completed,872 Core sources/probe forks created,83.19 minutes of completed-stage compute. One separate observer failure stopped at 0.2 simulated seconds and remains archived. Account usage 59%→62%includes any concurrent account activity. GPU trains/runs external adapters; Core uses the native CPU backend. Nine targeted sensory, motor, restore and isolated-output tests pass. No old-data scan or repeated database hashing.

The independent project retains design, amendments, bilingual reports, actual input/activity/state/configuration/controllers and results. Interactive replay shows actual four-object layouts, sensor pixels, pointer/teacher motion, and both incorrect and correct answers; it supports selection, seeking, playback and screenshots. Geometry icons are a diagram; pixels are measured input. Answers belong to the completed observation window, not newly generated at the displayed frame.

The viewer contains 80 clips selected by fixed indices, not correctness. Playback, seeking, screenshot export and absence of horizontal overflow were verified at 1440/390 pixels. Original sensory timestamps remain; the displayed clock belongs to Core observation after the subsequent 50 ms advancement.

Raw records:`.work/shape-color-20261006`. Compact measured summary:`results.json`; publication inventory:`delivery.json`. Existing experiments, instances, Core source/defaults and adapters are not replaced. Delivery of this bounded study does not complete the entire research backlog.

## 2026-10-06 appendix: E55 retest, without replacing E54

The user identified missing changing physical background and expanding item-specific reviews. E54 had position/velocity/contact, but not the new continuous environmental measurements or the later review schedule. With these retained, E55 strict QA is29/48, no-learning26/48, existing-edge silence27/48; three motor heads reach0/32,1/32,1/32. Materials, curriculum and calibration differ, so cross-study score differences do not identify the cause. Original E54 results/criteria stay intact.[Follow-up report](../2026-10-06-grounded-reviews/report.en.md)

## 2026-10-07: system-continuity scope note

Teacher/servo movement precedes separately fitted activity readers; expression correction can create a new reader. Assembly-level recognition/pointing scores remain, but improvement after refitting is not uninterrupted learning of one whole organism. Selectively recheck recognition, correction and attribution after continuous basic control; no blanket rerun of optics.

[Continuity audit / 连续性核查](../../../docs/en/plans/system-continuity-audit.md)


> **Storage-location revision · 2026-10-10**
> This edition adds the verified move of the selected originals to `E:\ThreeMindData`. Stable scientific identities and hashes, experiment dates, measurements and conclusions remain unchanged. Paths in the preserved body describe historical sources; use the registered evidence resolver for current locations. Repository documents and frozen fixtures remain in place, and source copies are retained. Structured query data and running checkpoints remain in the database. This annotation does not assert that missing historical evidence was recovered.
