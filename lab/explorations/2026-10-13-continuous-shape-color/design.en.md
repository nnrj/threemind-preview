# E68: continuous shape/color teaching, examination and correction (/2, /3.1)

Preregistration v1, 2026-10-13. Decisions by Liu Dongxu; AI-assisted implementation and execution. Follow [training protocol v3](../../../docs/en/training-protocol.md), the E56 functional reference and the E67 continuity correction. This is a new study; preserve all E67 subjects and evidence and keep /4 stopped.

## Subjects and apparatus

Two newly born complete individuals use `threemind.continuous-memory/2` and `/3.1`, explicitly confirmed by the user. Core seed223, sensory seed91; each owns its vocabulary peripheral, Adam and sampling RNG from birth. Native Rust, unchanged version defaults, no dynamics tuning. A single object occupies the physical eye's clear center. Eye/hand are fixed by the diagnostic apparatus; no motor reader is connected and no conscious motor output is overwritten. Wind, temperature, humidity, gravity/support and body feedback remain. Ordinary anonymous text input: one character per50ms, strength1. The eight-word peripheral receives only raw Core activation, inhibition, direct and associative activity, never scene labels or retinal pixels.

## Continuity and interruption

Each arm is born once. Teaching, calibration sampling, fitting its own peripheral, development questions, correction, review and final questions use the same living object, or resume its latest complete current state. All examination experiences feed subsequent stages. No per-question restoration, return to the pre-test state, peripheral replacement or minimum-loss rollback. Pausing wall-clock execution is allowed; it does not rewind internal time.

Persist the complete system and cursor after every teaching/question unit and fitting block. Record identity, predecessor digest, monotonic sequence, start/end simulated time, original inputs/activity and state hashes. A durable in-flight marker precedes advancement. An incomplete unit or uncertain state after a crash must stop automatic continuation: explain the lost boundary and ask the user, never silently recompute from an older checkpoint. This study contains no rollback-dependent ablation/transplant. **Ask Liu Dongxu before any proposed comparison that requires rollback**, even if historical controls used it. Rendering reads originals only.

## Fixed curriculum and scoring

Both arms receive matched curricula and identical banks, with their own uninterrupted state. One arm may wait at a complete boundary while the other advances.

1. 104 initial lessons: four gray shapes and four colored objects, ten consecutive lessons each and three interleaved reviews. Each lesson1.5s; extra gaps0/6/18s, total180 simulated seconds. Object and background remain during gaps.
2. Sample48 real answer-free questions continuously, 1s/20ticks each, retaining eight evenly spaced raw frames covering the whole utterance. All48s remain in the student's history.
3. Continue its peripheral1200 AdamW updates on its calibration corpus: projection48, one temporal Transformer, four heads, feedforward96, dropout0, lr.002, weight decay.0001, batch≤32, clip1. Core/body time pauses during this explicitly declared instrument calibration; optimization steps are not lived simulation experiences. **Retain the last update, never an earlier loss minimum**, while keeping the same weights/Adam/RNG. Architecture and Core are unchanged.
4. Answer72 development questions in sequence:40 shape and32 color. A pair succeeds when both attribute questions for the same object/position succeed (32 pairs); this is not a simultaneous two-attribute utterance and contexts can differ.
5. Three corrective rounds use the union of both arms' preceding development errors: re-answer original failed conditions, immediate ordinary teacher correction, three extra examples per failed type, and three interleaved passes over all36 object/attribute types. Include similar and previously correct examples, with extra gaps0/6/18s. Complete registered reviews even after a perfect development result.
6. Each round collects72 prescribed calibration questions plus original failed conditions, continuously. Continue1200 updates on all retained personal calibration examples, then retest the72 development questions. Every end state supplies the next stage.
7. Finally answer72 held-out-position questions once, continuously. Score the fixed question-end argmax; preserve errors. Final positions are excluded from teaching/calibration; final answers never select a checkpoint or trigger unregistered extra training. End after the registered three rounds and final test.

Reuse the declared E67 question generators for this new batch, not its subjects or scores. Record actual concept exposure times;0/6/18 are extra gaps, not a fitted human forgetting curve. E56/E67 successes retain their historical evidence limits.

## Recording, resources and delivery

Register E68, protocols, conditions and managed originals through the authenticated platform before birth. AI/human recording standards match. Originals stay in the managed data root, outside Git; retain complete boundary snapshots. Sync stage indexes and hashes; an authentication outage queues durable records without resetting or repeating the subject. Stop if original bytes cannot be saved reliably. Reserve25GiB free disk and2GiB available RAM; pause at safe boundaries without deleting old research data.

Measure native computation, observation, inference/calibration, serialization/saving, wall time, graph size and storage separately. Report one complete individual versus all research evidence. Engineering tests cover continuity chains, exact next input/update after full recovery, pauses and prevention of replay after uncertain interruption; their artificial fixtures are not formal participants.

Deliver one MP4 and full-frame HTML per arm. Teaching8x, calibration sampling4x, development2x, final1x, with explicitly labelled answer holds. **Below the video, plot all four recorded activity curves against actual simulated time**, continuous across questions and aligned with the scene, answer and current cursor. Do not invent activity during paused fitting. Supply per-stage and full-run series. Bilingual reports, canonical records and histories distinguish performance, accuracy, single-seed/finite-task limitations and untested causal attribution. No new kernel identity is needed because dynamics remain unchanged.
