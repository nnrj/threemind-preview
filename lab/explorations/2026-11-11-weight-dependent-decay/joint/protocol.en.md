# R48b: continuous joint learning with weight-dependent decay

2026-11-11, preregistered version 1. [中文](protocol.zh.md) · [Rule, parameters and local tests](../protocol.en.md)

This authorized study tests actual selection, retention, reversal and relearning. It reuses the validated R47c personal temporal Transformer, teaching, correction, spaced review and body feedback. Changes are the isolated research identity, connection-decay arms and new sources. Node support is inverse-logarithmic in every arm; all use Python. R48a outcomes neither substitute for these scores nor change this course.

Eight new sources, seeds 261111900–261111907, each raise five whole individuals: inverse-logarithmic, weight-fast, weight-slow, matched-fast and matched-slow. There are 40 individuals, independent N=8. Rates and equations follow R48a without searching or selecting origins. Every individual preserves Core, mappings, personal Transformer, Adam, RNG, all samples, recent activity, body, actuator, curriculum and internal time.

## Targets and scientific interpretation

Target and protected relations must each score ≥75% in both immediate and 300-s delayed tests; each arm requires ≥6/8 origins per goal. J1 learns and retains P/A; J2 adds B while preserving P/A; J3 reverses A while preserving P/B; J4 restores original A while preserving P/B. Score each goal separately. A candidate meets this study's combined objective only if all four goals and R48a's weak-forgetting/retention targets pass.

Matched exponential controls distinguish weight dependence from an overall slowing of decay. Inverse-logarithmic is the retention reference. Report source-paired accuracy, success fractions, intervals and costs. This is an eight-origin exploration. If no candidate meets the combined objective, end this bounded study without moving criteria. Successful local properties and unsuccessful behavioral targets receive separate explicit conclusions.

## Curriculum, reader and continuity

Keep R47c's 48-dimensional, four-head, one-layer Transformer with feedforward width96 and dropout0; AdamW learning rate0.002, weight decay0.0001, batch≤32, gradient clip1,1200 updates per fit, committing the last complete state. Reader inputs are the two declared output ports' activation, inhibition, direct and associative activity over20 frames/1s, sampled uniformly to8 frames. No cross-individual reader swap or optimizer rollback. Inference receives no labels, current rules, question IDs or correct positions.

Stages: P0→0/P1→1/A0→0/A1→1; add B0→0/B1→1; reverse A; restore A. Each stage teaches every current correspondence eight times in shuffled interleaved order. Each1.5-s lesson presents cue and target output at amplitude0.4 at offsets0,0.25,0.5,0.75,1s. Review every correspondence after gaps2,6,18s. Background0.2 arrives every0.5s. Later stages also test development performance before teaching.

Calibration uses answer-free cues at amplitudes0.76,0.8,0.84,0.8; labels supervise only the external reader. Keep all historical samples and continue for1200 updates. Development amplitudes are0.76,0.84. Each erroneous correspondence receives five corrective lessons, followed by reviews of all correspondences at2,6,18s, new sampling, continuous fitting and development testing. At most two correction rounds; stop extra correction when development is perfect. Keep teacher, development and final scores distinct.

Held-out amplitudes0.72,0.78,0.86,0.9 are unused in calibration/development. Shuffle with the individual's RNG. The first stage has16 questions, later stages24 each. After immediate testing, continue background for300s and test again. Delayed testing includes earlier test experience; R48a supplies independent first-probe retention cohorts. Final testing freezes the reader, gives no correct-answer feedback, and continuously advances Core/body/time without per-question resets.

Reader output selects0/1. A fixed actuator moves to that position and returns only actual-position amplitude0.2 proprioception. Scoring then compares the correct target. Report correct choices and unchanged/changed positions, not learned physical arm control.

## Verification, resources and delivery

Verify the next question and next optimizer update after whole-state restoration,20-frame/8-frame/four-field recording, truth-isolated feedback and nonperturbing observation using separate engineering seeds. Start R48b once after R48a delivery. One-second guard reserves5/4/5/25GiB commit/RAM/C/E; startup≥8GiB commit and≥37GiB E. Limits are4GiB originals,3GiB private memory,4host hours. Estimated runtime30–60minutes, measured costs reported separately. Pause only at complete boundaries; preserve unexpected in-flight state without replay.

Independently verify every file hash, state chain and choice arithmetic. Bilingual reports state purposes, predictions, results, analysis and conclusions, separating local mechanism measurements from complete-system performance. Read full reports and original archive back through the unified API with pending=0. No automatic default change, production installation or new parameter search follows.
