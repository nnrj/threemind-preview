# E60: learning gaze shifts, fixation and eye–hand coordination

> **Revision r2 · 2026-10-10**
> Revision reason: Relocate generated evidence out of Git; preserve original bytes and conclusions.
> Original: [report.en.md](report.en.md); parent r1: [report.en.md](report.en.md)


2026-10-07. The bounded experiment is complete; reliable basic target control remains unachieved. Core dynamics, defaults and historical experiments remain unchanged. Research project: `5a6ba1f4-0906-4603-8a85-e625785dfb66`.

[中文](report.zh.md) · [Preregistration](design.en.md) · [Discussion](../../../docs/en/history/sources/2026-10-07-eye-hand-learning.md) · [Tools](tools.md)

## Main finding

Actual teaching covered movement, holding and retargeting, followed by student attempts and corrective demonstrations. **Mechanical control and adapter fitting work, but reliable requested gaze shifts, fixation and retargeting have not been learned.** Some trials enter the clear center and remain there; that alone does not establish learned attention. Matched controls do not show a consistent task benefit from existing connections.

This was not a course without a teacher or a controller unable to issue zero commands. A real bug in the new motor trainer was found and fixed before valid comparisons. Failed records remain available and must not be attributed to Core incapacity.

## Teaching and comparison

- Four tasks: look only, point only, both, and hold. A joint adapter is primary; independent eye/hand encoders are controls. Four physical outputs do not assign semantic regions inside Core.
- Each skill receives 13 lessons: ten starts 3 simulated seconds apart, followed by 6, 12 and 24 second gaps. Total: 52 lessons and 288 simulated seconds. Layouts/directions vary; this is not 13 repetitions of one fixed object concept. The scene and bodily environment persist between lessons.
- Teacher words, visible markers and physical guidance are real inputs. Assisted success is not autonomous success. Twelve separate practices are followed by 24 corrective demonstrations. Both the student's history and adapter training data are updated.
- Validation demonstrations come from separate clones and select adapter weights. The final 12 questions are unused in fitting or selection: six seconds each, a target switch at three seconds, three questions per task.
- All final comparisons start from a common physical world while retaining each Core's own time and state. Clock offsets are recorded. Subsequent action-dependent sensory differences remain a natural closed loop.

Eye angle, speed and motor power retain proprioceptive feedback. Wind, temperature, humidity, support, inertia and contact remain simulated environmental inputs. CPU telemetry is absent, but physical background is not removed. All four objects and the visible hand persist. The teacher marker enters through vision and ordinary instructions through text sensation.

The normal motor adapter receives only the last 16 ordered raw activation, inhibition, direct-contact and associative-contact samples and outputs four forces. It receives no task class, answer coordinates or object-name argument. There is no subtraction of an uncued clone or per-example amplitude normalization. The incoming-signal bypass is explicitly a non-Core control.

## Basic mechanics and optical visibility

Eight apparatus checks show that teacher physical control can turn and hold gaze; final hand errors are approximately 0.005–0.008 m. All 24 checked markers alter actual retinal input at the common initial pose and when aligned. Some peripheral markers affect only one receptor, compared with 6–10 after alignment. This excludes complete optical absence at those checked poses, not inadequate internal salience.

Scoring separates clear-center coverage, angular error, speed, duration and retargeting. It does not change Core convergence and imposes no 800 ms dwell gate. Brief entries are retained. Low speed plus alignment is a motor measurement; stillness in a wrong direction is not success.

## Trainer correction and preserved failures

The initial sampler divided batch size by the number of examples in a category instead of the number of categories. Large categories produced empty batches, NaN mean loss and zero gradients; only weight decay acted. Preserve the original three fits and two closed-loop tests as **tool failures**, excluded from capability comparisons. The corrected trainer rejects empty batches/nonfinite losses and has a meaningful large-sample learning regression test.

With the same unchanged teaching data, shared-architecture training/validation MSE becomes 0.0071/0.0456. Valid CPU and CUDA gradients rule out a general accelerator problem. All valid fits carry `fit2`, not a new Core identity.

A separately registered hidden-layer normalization and zero-output initialization variant reaches 0.0351 validation MSE and becomes the primary shared reader based on independent demonstrations. This architectural comparison is separate from fixing the sampler. See [reader amendment](reader-amendment.md) and [common-world comparison amendment](comparison-amendment.md).

## Joint versus separate control

On the same valid protocol, the original shared/separate readers spend only 1.98%/1.77% of requested-eye time aligned and slow in the 16 prototype questions. Neither provides reliable target control. Parameter counts differ (117,124 versus 107,812), so this is not a capacity-matched architecture-only comparison.

The revised shared reader reaches 17.81% on these prototype questions but performs worse on fresh confirmation questions. Eight persistent-marker questions also fail to resolve control. Their aggregate cannot be directly compared with a 16-question aggregate to estimate cue-duration effects. Closed-loop reliability remains the priority.

## Separating new Core experience from reader calibration

Each column below uses only the six questions requesting eye movement or the six requesting hand movement. **These are time fractions and distances, not answer accuracy or all-twelve averages.** Holding tasks therefore cannot inflate requested-movement results.

| Core experience / motor reader | Clear-center time | Aligned and slow time | Mean hand-target distance |
| --- | ---: | ---: | ---: |
| Before correction / original |4.86%|2.36%|0.924m|
| Before correction / updated |2.50%|0.42%|0.682m|
| After correction / original |8.19%|6.25%|1.051m|
| After correction / updated |10.00%|8.47%|0.706m|

With a fixed original reader, new experience changes actions: some eye metrics improve while the hand deteriorates. A new reader reduces hand distance without guaranteeing arrival. **Correction has effects but has not established four reliable, independently controllable skills.** All three look-only questions have zero aligned-slow time in all four conditions. Learned separation of eye/hand instructions is not established.

## Causal controls and the nose

With the updated reader fixed, silencing snapshot-existing connections changes all 12 eye and hand endpoints. Silencing then restoring reproduces every command in all 12 normal trials exactly. Mean associative-contact integral falls from about 9.20 to 0.162 and returns to 9.20 after restoration. **Existing internal connections participate in control; the apparatus is not acting solely on its own.** This does not establish correct target interpretation. Silencing preserves input responses, existing node states and newly born connections; it is not a complete Core shutdown.

| Same corrected student and reader | Aligned-slow time in eye tasks | Initially unaligned phases entering center | Of these, reaching aligned-slow | Mean hand distance |
| --- | ---: | ---: | ---: | ---: |
| Normal |8.47%|2/11|2/11|0.706m|
| Zero motor commands |25.00%|0/9|0/9|0.869m|
| Existing edges silenced |5.00%|4/11|2/11|0.685m|
| Edges restored |8.47%|2/11|2/11|0.706m|

Each condition has six eye-movement questions and twelve target phases. Earlier actions affect initial alignment in later phases, so denominators differ and are not independent random samples. The longest normal aligned-slow interval is 1.75 seconds. The zero-command condition's 25% comes entirely from already aligned starts; it never enters from outside. Reporting only stable time would overstate learning. Silenced trials also enter targets and have a slightly smaller mean hand distance. Internal influence is established; a consistent correctness benefit is not.

The explicit sensory bypass uses the same demonstrations, architecture and fitting steps, without reading Core to decide actions. It spends 12.64% of requested-eye time aligned and slow, with mean hand-target distance 0.640 m, and also fails to control targets reliably. This is not a strong upper-bound model; its slightly better averages do not establish that Core harms control. The direct-force reader and closed-loop course themselves need work, rather than assigning the problem solely to Core.

The nose is simplified head-fixed spherical geometry testing a visible bodily reference, not a reconstruction of all functions of a human nose. A fresh instance receives the same 52 lessons, with an independently trained reader of the same shared architecture. Compare the same 16 prototype questions:

| Condition | Clear-center time (8 eye tasks) | Aligned-slow time | Mean hand distance (8 hand tasks) |
| --- | ---: | ---: | ---: |
| No nose |25.42%|17.81%|0.792 m|
| Nose |11.15%|7.60%|0.864 m|

**The nose provides no benefit in this comparison.** Retain it as an option, disabled by default, rather than concluding that bodily references cannot help elsewhere. These are matched prototype questions, not the separate 12-question confirmation batch with its 8.47% normal result.

## What remains to solve

1. The apparatus can move and hold; checked teacher markers reach the retina. The unresolved path is from experienced activity to reliable closed-loop target control. Successful mechanics is not evidence of formed intention, and failed control does not establish absence of intention in Core.
2. Predicting four forces directly asks one small reader to learn task relationships, target location and braking. A future comparison could separate activity-to-target-posture translation from a physical servo without object answers. Retain the current route. This recommendation was not implemented in E60.
3. Earlier successful shared spatial reading remains in the old tools. The new continuous-force reader consumes anonymous channels without reusing the earlier receptor-wise shared-weight architecture. This unresolved structural difference prevents interpreting E60 as disproving the earlier benefit. Combining shared spatial reading with continuous control is a candidate, while keeping scene/answer information out of inference.
4. Holding, retargeting and independently moving eye/hand require separate teaching and assessment. Offline action loss is insufficient. Skills are currently blocked in the order look, point, both, hold; effects of recent lessons on earlier skills remain untested. After initial concentrated repetition, interleaved review and longer autonomous practice followed by correction should precede deciding to change Core. The bounded 52-lesson course and one correction round do not exhaust teachability.
5. Deformed shapes, negation, plural pointing, neck control and a full robot remain deferred. Historical activity evidence and criteria remain intact. No global attention mechanism or Core default changes were introduced.

The user's additional proposal separating environmental selection, energy feedback and teaching is preserved as [future memo R37](../../../docs/en/plans/training-regimes.md). No reward condition was added in this batch; methods and resulting capabilities are assessed separately.

## Delivery, resources and checks

The batch completes 34 stages and 206 instance creations/restores, using approximately 126.14 compute minutes within the 150-minute limit. There are 168 valid closed-loop test questions and 32 preserved trials with the initial faulty trainer. Nose/no-nose each receive 52 lessons, alongside 24 corrective demonstrations and independent validation. No reward teaching or energy-rule change was introduced. One encoding/environment source does not establish a model-family-wide result.

Chaptered replay includes every completed lesson, interval, practice, correct/incorrect trial and identified tool failure: 21 chapters, 400 clips and 39,840 original sampled frames. Each segment states its control source: teacher, Core-activity reader, incoming bypass or disconnected output. No idealized paths are invented and replay does not execute Core. PNG capture and WebM recording remain available; chapters avoid loading the whole study at once, with the largest approximately 33.85 MiB.

Twenty-one relevant tests pass. The saved reader's maximum CPU/CUDA output difference is about `1.42e-7`; the scientific figure was visually checked. Account usage increased by approximately 3 percentage points by simulation completion, counting shared-account activity. No resource guard stopped the study and no old data was deleted. Final storage and report readback are recorded in `delivery.json`; [verification scope](verification.md) separates completed checks from unverified behavior.

The browser security policy denied local-file preview. No alternate browser or proxy bypass was used. Replay can be opened locally by the user, but automated browser visual validation remains unavailable. Static and packing checks are not a substitute for viewing it.

[All results](/api/v2/storage/research-artifacts/research-artifact:67d3dbad18aa3b984fb3d640/content) · [Paired interventions and gaze phases](paired-results.json) · [Execution notes](execution-notes.md) · [Complete chaptered replay](../../../.work/eye-hand-learning-20261007/eye-hand-learning.html) · [Summary figure](../../../.work/eye-hand-learning-20261007/eye-hand-results.png)

## 2026-10-07: system-continuity scope note

A new motor head is fitted offline after teacher-driven motion, and correction fitting creates another head instead of continuing weights/optimizer. Before/after correction is therefore not continuous learning of the same whole individual. All 12 actions changing under silence and restoring under rescue with one saved head remain valid. Retest basic control and correction in a continuous system, without first repeating every nose/organization branch.

[Continuity audit / 连续性核查](../../../docs/en/plans/system-continuity-audit.md)


## Data location revision

Selected generated evidence has been archived and verified byte for byte. Original reports, criteria, conclusions and embedded source_commit values are preserved. The logical downloads below require the current host administrator. The data directory is not public.

`data/experiments/2026-10-07-eye-hand-learning/`

[Location and hash index / 位置及哈希登记](../../artifact-index/2026-10-09-relocations.json)

- [results.json](/api/v2/storage/research-artifacts/research-artifact:67d3dbad18aa3b984fb3d640/content) — 312769 B; SHA-256 `2562b078f0c2d7b06aed5b6c0eccc073170e8ddc641ce5db035b564bdf2eaecd`.
