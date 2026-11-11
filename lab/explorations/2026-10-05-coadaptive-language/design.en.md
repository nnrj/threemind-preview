# E52: coadaptive teaching, corrections and shared referents

2026-10-05, preregistration. [Discussion and original quotation](../../../docs/en/plans/coadaptive-language-center.md) · [简体中文](design.zh.md)

Unchanged continuous-memory/2 defaults, frozen sensory encoder,20ms language frames, ordinary intensity1, joint visual dose10, probe intensity.5, identical recorded physical background. Four MuJoCo bodies cross two colors and two shapes, using the original ray measurements and anonymous wiring. No semantic labels or answers enter Core other than ordinary teacher sentences.

Stages: teach red/blue spheres; add red/blue boxes; exchange the spheres' names while retaining the boxes' names. Per object four forms: name, color, shape, same-color reference; first10consecutive repeats each, then reviews at2/4s intervals. Each stage has eight teaching interactions: prompt without answer,2s observation, actual generated utterance optionally returned through the same encoder, followed by an ordinary teacher demonstration. The external training target attaches to the pre-answer observation; this is supervision, not proof that Core already encoded that meaning.

Two batches of four examples update the adapter within each stage, from prior weights. FIFO replay64, historical observations retain their contemporaneous labels. Adam restarts each update. Training-only checkpoint selection. Stage0updates1000/2000steps; later updates1000each. Base fit requires7/8. One preregistered failure diagnostic permits2500steps at.0003, saved separately. First source223, second279only after the base gate.

Arms: adaptive expression with self-hearing, adaptive expression without self-hearing, adaptive expression with Core plasticity disabled. Teacher curriculum identical; self-hearing adds real input, not equal total sensory dose. The frozen base head reads identical later observations as a static control.

Tests use visual+pronoun, color/shape descriptions, held-out rephrasing and same-color relations; the latter two are not adapter-calibration prompts. Repeated color/shape across distinct objects prevents one-property identification. Report naming, correction, retained names, within-referent consistency and between-referent distinction separately. Keep no-cue outputs without invented truth.

If naming supports interpretation, fixed-head controls include cross-domain edge silencing, approximate matched silencing, rescue and same-origin snapshot exchange. Cross-stage exchange changes age and history together and is not a clean content transplant; an additional opposite curriculum fork may be used within budget. All evaluation occurs on copied snapshots without test-answer feedback. Sources advance only through registered teaching. Save inputs, raw processes, utterances, demonstrations and adapter revisions. Six local fields/17samples, no counterfactual subtraction or answer-conditioned selection.

Budget:640instances,3h aggregate compute,oneworker,RSS4/GPU3GiB; local3GiB soft/8GiB total hard; freeRAM2/C5/E15GiB; shared usage52% baseline,+6/+10points. Failed calibration stops expansion, not relabeled as failed unseen concepts. No Core/default/old-evidence changes. This first adapter uses continual gradient updates, not fast weights, and does not claim general reasoning or validated inner speech.

## 2026-10-05 amendment: translation rather than answering

During the first source the user clarified that the ideal peripheral only translates, while permitting comparisons with a more capable adapter and continuation of the registered run. Preserve that distinction.

Add a preregistered stricter control: separate copies of each main-source snapshot receive only “甲。”“乙。”“丁。”“戊。” at.4/.6intensity with normal background and2s observation. The peripheral receives literal transcription supervision only, never object names, object-name assignments or object-question answers. Initial8examples/1500steps, then8additional examples/1000steps at each later stage. These word cues occur only in training copies, not in the real test. Frozen and updated transcribers read the already recorded primary test observations. Below7/8transcription fit, report instrument failure; no test-selected tuning. Word production remains learned; the control blocks direct task-fact supervision rather than claiming to forbid all computation mathematically.

## Post-first-source registration: calibration context versus referent

The first feedback source already scored4/16 after stages1/2 despite fitting8/8 teaching observations. This question is motivated by those results, not claimed to have been preregistered originally. Sequential demonstrations change object, time and background together. For each of the two feedback sources, take8 independent copies of its stage2 checkpoint, balancing four visual(view8) and four description observations. Retain its24 prior demonstrations and continue once for1000steps, without test-based selection.

Use12 additional independent test copies per source: visual view11, unseen rephrasing such as "What is the name of the red sphere?", and unseen relational wording such as "What is the name of the sphere with the same color as the red box?". Both original and newly calibrated heads read the exact same raw test processes. Calibration examples are excluded from test scores. This is a diagnostic of context-sensitive translation, not a pure-translator success: object-answer supervision is still present. The40extra copies count toward the same640copy/3h budget. Causal attribution is considered only after meaningful performance; no inference that improved external calibration establishes Core reasoning.


2026-10-05 before transcription execution: the same main-source transcriber also reads existing no-self-hearing and Core-plasticity-off test trajectories. All actual words are saved; no Core rerun. These arms have different teaching/self-hearing histories and this is not a single-pathway intervention; it checks whether direct sensory traces can also support similar answers.


## Bounded diagnostic after transcription underfit

Both initial Transformer transcribers fit2/8 and stopped later phases. Read-only inspection finds about0.08584maximum raw difference between the .4intensity first two words, still0.06180at120ms; the17point observation did not erase all differences. Before execution, add a finite-vocabulary linear ridge transcriber on the same raw six fields/17times (fixedridge=.0001, intercept, no centering, baseline subtraction or per-example scaling; no task answers). Four new copies per source test actual heard words at withheld intensity.5. The fixed stage0reader then reads existing three-arm questions at all stages without new supervision. At most8new copies within the original budget. Recognizing heard words will not itself establish recalled-word translation.
