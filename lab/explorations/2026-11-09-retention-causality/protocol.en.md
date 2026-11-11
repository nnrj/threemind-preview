# R44: Does connection retention limit joint judgments?

9 November 2026, v1, prospective protocol. The author authorized research to determine whether and how decay rules should improve. Production Core, defaults, R43 originals and the manuscript remain unchanged. [中文](protocol.zh.md)

R43 did not achieve stable joint judgments after initial teaching and two correction rounds. Subsequent read-only inspection found 30-internal-second half-lives on X0/X1-to-output connections at test start and their disappearance by the end of the 72-second test. This study asks whether longer retention preserves structure and improves answers, and whether retention matters during testing or earlier corrective teaching. Structural preservation and behavioral benefit have separate endpoints.

## Sources and continuity

Reuse eight independent R43 birth sources, each with two opposite-history copies. New branches are explicitly identified mechanistic copies, not resumed or rolled-back original individuals; independent N remains eight. Source: `E:/ThreeMindData/experiments/2026-11-09-context-revision/v1`. Work: `E:/ThreeMindData/experiments/2026-11-09-retention-causality/v1`. Copy and hash source files and complete personal-adapter dependencies without writing to the source directory.

Late interventions start from each `test-parent.json.gz`; early interventions from `teaching-0/whole.json.gz`. Exact parent times/hashes and whole Core, queues, personal weights, AdamW/RNG, body, mappings, actuator, recent windows and curriculum state are retained. Restore once per declared branch; subsequent teaching and 24 trials remain continuous, never restored per question. Reused questions are mechanistic diagnostic material, not unseen confirmation. Existing R43 scores are preserved.

## Retained methods

Keep the existing personal temporal Transformers fixed: twenty frames over each one-second answer, eight consumed frames, activation/inhibition/direct/associative fields and positional encoding. No mean-activation replacement or retraining of personal output adapters. Existing joint interface development and subsequent Core teaching are preserved in the parents.

Late arms receive no further teaching. Early arms continue the original two corrective/review rounds. Their teacher schedules are fixed by the original history's errors: ask again, show original and changed-dose examples, review old examples, two dense cycles plus additional 2/6/18-second gaps, then continuous development questions. A now-correct item is a review of an original error. New scores do not add teaching, change dosage or stop a round early. This fixed-curriculum causal comparison separates retention from additional instruction; it does not claim to correct every new branch-specific error. Environmental feedback still follows actual viewing actions and may therefore differ across branches.

Keep explicit K=.2 background every .5 internal seconds. Observation and host delays do not advance simulation. Testing supplies no teacher output-port signals, and adapters receive no answers, identifiers, history labels or raw sensory values.

## Intervention and controls

Using complete-state import, raise the current half-life of selected existing directed edges to at least 300 internal seconds, once at the declared parent. Do not change the exponential decay rule, learning rule or defaults. Normal learning and the .125-second-per-internal-second half-life decline continue; subsequent new edges follow their original rules.

Saved weights use lazy timestamps. Resolve each affected weight at the current time, re-encode its stored weight under the changed half-life and recompute only its expiry timer. A JSON weight change is therefore a representation adjustment: the current physical base weight is unchanged. All clocks, fast state, transmission resources, nodes, inhibition, queues, learning and random states remain intact. Field audits and native projected-weight checks must pass.

Targets are existing edges in both directions between X0/X1/D0/D1 and declared output ports. Matched edges connect Z0/Z1/Z2/Z3 with the same ports, also in both directions. Each selection contains 28 edges with equal counts and endpoint-degree distributions; the current mean base-weight mismatch must be at most .05 and is reported. Selection uses teaching/interfaces, never scores. The all-edge arm prolongs every existing edge and tests a broader intervention.

Late arms: baseline, target, matched, all. Early arms: baseline, target, all. Total: 112 diagnostic sequences, 2,688 trials and 96 early corrective/review stages. Early baselines must reproduce original teaching records and pretest Core state; every baseline trial must reproduce the original raw windows and outputs. A failed reproduction invalidates affected comparisons.

## Registered endpoints

Pool the two histories within each independent source. Three correct sound/vision/action outputs in the first new single-cue window constitute a joint correct answer. Report old trials, conflict revision and mixed trials separately.

|Goal|Prospective rule|Interpretation|
|---|---|---|
|Q1 Prevent structural loss|Late target arm retains at least90% of initial X0/X1↔output edges at test end in both histories, baseline retains at most10%; at least6/8 sources|Failure to retain structure prevents interpreting low scores as evidence against retention|
|Q2 Rapid test-period decay causes major answer loss|Late target joint gain over baseline at least25 percentage points and at least12.5 points greater than matched gain, old-trial damage at most12.5 points; at least6/8 sources|Preservation without benefit rejects the predicted major benefit of test-period prolongation in this batch; report actual effects and intervals|
|Q3 Longer retention supports further teaching|Early target and all-edge candidates evaluated separately: joint gain at least25 points over early baseline, old damage at most12.5 points, at least6/8 sources|Separate conclusions; no selection of favorable origins|
|Q4 Restore the original joint capability|For each candidate, each history has new joint accuracy at least75%, with all three outputs changing across opposite histories on at least50% of paired cues; at least6/8 sources|Only passing this rule counts as repairing the original joint goal; smaller valid benefits remain reported|

Late all-edge gains are prespecified broad-retention comparisons, not evidence of target specificity. Report paired source effects, denominators and95% source-bootstrap intervals. Reused eight-source exploration is not a powered population confirmation; intervals spanning meaningful benefit indicate insufficient precision. No intermediate sample additions, criterion changes or tuning of300seconds.

## Decay-model comparison and decision

With common initial weights and deletion thresholds, calculate30-second exponential,300-second exponential, power-law, inverse-logarithmic and fast/slow double-exponential candidates. The last three have a common30-second half-value time. Give formulas, values at1/30/60/300/1000seconds and threshold-crossing times. These are mathematical comparisons, not new subject runs or behavioral proof.

Stable Q2/Q3 gains with old skills retained support further work on experience-dependent retention growth before replacing the decay function. Q4 determines repair of the original capability. If longer-lived structure yields no major late or early benefit, do not recommend changing default decay on this evidence; prioritize transmission/inhibition and personal output expression. A production version change is outside this batch.

## Validation and delivery

Independent apparatus material uses the original non-scientific instrument source, excluded from N. Validate field isolation, native current weights, half-life targets, exact immediate undo, next-window restoration, observation/wall-clock isolation, baseline reproduction and analytic decay. Preserve new dead in-flight or unverifiable states and ask before further intervention.

Serial scientific host; commit/RAM/C/E reserves5/4/5/25GiB, checked each second, pause only at complete boundaries. Start with at least8GiB commit and34GiB data space. Private memory at most3GiB, scientific wall time4hours, originals3GiB plus archive/readback allowance. No deletion, lower thresholds or paid cloud. Register and read back both protocols before running; then independently recount, write bilingual scientific conclusions, perform full research-API archive readback and finalize at pending0. Update R44 and bilingual histories, with Classical adaptations for the phase; local Git only after data checks.
