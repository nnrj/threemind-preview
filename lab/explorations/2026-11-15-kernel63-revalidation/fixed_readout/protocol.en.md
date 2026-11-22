# R63h: expressing new Core learning through a fixed personal readout

15 November 2026, before registration. The author approved temporal readout as primary and the original 110-ms endpoint as a separate control. This batch retains M5's eight origins and causal question on kernel 6.3. The 48-origin confirmation will have a separate record. This batch is not yet registered or run.

## Question and expectation

A personal readout learns only the old prompts and two response labels, then its parameters are frozen. The Core subsequently receives new paired teaching. We test whether the same readout can express the new relations, and locate their contribution by blocking and restoring new and old connections. Full-activity, output-port and direct sensory readouts are reported separately. We expect the output-port readout to express new learning, selective new-connection blocking to impair new relations, and restoration to recover responses. Full-activity readout and further calibration retain their own targets.

## Complete subject and readout

Use eight birth origins, seeds 1056100–1056107, and separate apparatus seed 1056002. Twelve anonymous channels ABUVZWXYCDKN are assigned at birth. A/B are declared output interfaces; personal readouts learn their response labels from old teaching. Preserve the Core, all readout weights and accumulated regression state, scales, samples, random state, interfaces, recent trajectories, response terminal and actuator. Ordinary questions continue without restoration; causal copies retain their source identity.

Record activation, inhibition, direct activation and associative activation every millisecond from 1 through 250 ms after each stimulus. Divide the 250 samples into five consecutive 50-ms bins. Each bin contributes the mean of each field on each channel, ordered by time, field and anonymous numerical channel: 240 features. Early and late activity remain distinguishable, and the complete millisecond trajectories are retained. The primary answer is formed at 250 ms. Neither the brightest node nor an answer-selected window is used.

The full readout receives all 240 features. The port readout uses the same vector and model with channels other than A/B zeroed. Two historical endpoint readouts use the same individual's 12 activation values at 110 ms, either full or port-restricted. The sensory control receives only the current 12-value stimulus. All five models start blank and use linear ridge regression without intercept, penalty 0.001. Calibration fixes each feature scale to its maximum absolute old-sample value, or 1 if that maximum is at most 1e−6. Later learning retains the scale and accumulated equations. Scores above 0.25 answer positive, below −0.25 negative, otherwise WAIT. Inference accepts feature values only, without question name, answer, stage or history identity.

Temporal and endpoint readers observe the same Core and do not feed each other. The passive response terminal does not change subsequent questions. Temporal results are primary; endpoint results remain separate regardless of which is better.

## Teaching, correction and freezing

Teach old relations UVA/ZWB for 16 rounds, each channel at strength 0.4, with 250-ms separation between groups. The fifteen between-round gaps are five of 0.8 s, five of 1.0 s and five of 1.2 s. Total teaching duration remains 18 s and the repeat count remains 16. This explicitly replaces the old M5 schedule's uniform one-second gap with gradually increasing intervals. Background K at 0.2 continues every 500 ms throughout lessons and questions.

Then collect the six old cues U, V, UV, Z, W and ZW at doses 0.7 and 0.9: twelve genuine activity sequences to calibrate the five readers. Labels train only the readouts. Six old-cue questions at dose 0.75 provide development checks. If either temporal full or port readout errs on one of the four single cues, the teacher repeats the corresponding old relation, collects another old-cue sample set and appends it to the retained regression equations. Joint cues remain separate, as in original M5, and do not trigger correction for the single-cue primary target. At most two correction rounds are permitted; the waits after corrective teaching before sampling are 6 and 18 internal seconds. These are not the complete intervals between every recurrence of a concept; actual input times are saved. No errors means no extra round. The final development check cannot trigger a third round.

Development observations are not final tests. After initial calibration and any bounded correction, freeze all readers and give the interleaved old/new baseline questions at total dose 0.8, one internal second each. From that complete parent, register opposite new histories and plasticity-on/off research branches. The new lesson again lasts 18 s with 16 increasingly spaced rounds, reviewing old relations while teaching XYA/CDB or XYB/CDA. Test the new relations immediately afterward. New labels cannot recalibrate the readout before this first-response test, because the target is expression through a fixed readout. All ordinary questions remain continuous.

Use the existing 6.3 plasticity interface and record all affected processes, including connection creation, strengthening, decay and fast learning. This is a combined intervention, not a pure single-mechanism switch. Both on and off branches invoke the interface at the same current time; the Core clock is retained.

## Causal copies and subsequent calibration

Preserve each taught reference, then create sham, new-connection block, old-connection block and immediate-restoration copies, plus the plasticity-off branch. Targets are XYCD→AB and matched old connections UVZW→AB. Each set has four directed connections, equal degree distributions, mean contemporaneous weight residual at most 0.05 and mean source-activity residual during new teaching at most 0.02. Selection follows declared teaching interfaces, never final answers. Failed matching is invalid measurement. Blocking changes only the silenced-edge set; immediate restoration requires identical complete state.

Each branch answers six new and six old cues continuously. Primary denominators are four single new cues and four single old cues per history; two joint cues per group are reported separately. After the sham branch's first responses, retain one frozen-reader copy and one further-calibrated copy. The latter appends the six new-cue activity/label pairs to the four Core-based readers' retained equations; the direct sensory control remains frozen. Test both copies at doses 0.85 and 0.95, neither used for fitting. Their external inputs are identical and final Core states must match exactly. Further calibration does not revise first-response scores.

Offline early/late Core activity crossed with early/late readers locates activity and readout changes without altering subjects. That diagnostic includes fitting data and is distinguished from the held-out dose tests.

## Targets and decision rules

Retain the old M5 source-level thresholds. Both opposite histories must satisfy a target; at least six of eight origins must pass. Temporal full and port readouts are scored separately, and endpoint readouts use the same rules in a separate table.

1. Fixed expression: old baseline accuracy at least 75%; new accuracy after learning at least 75% and at least 50 percentage points higher than before learning; old accuracy remains at least 75%, losing no more than ten points.
2. Core attribution: new accuracy exceeds both plasticity-off and new-connection blocking by at least 50 points; old-connection blocking loses at most ten points on new relations, new-connection blocking loses at most ten points on old relations; restored per-question scores differ by at most 1e−9.
3. Readout scope: port readout exceeds full readout by at least 25 points on new questions and retains at least 75% old accuracy. A miss remains a miss, without further calibration to manufacture an advantage.
4. Further calibration: held-out new accuracy exceeds frozen-reader accuracy by at least 25 points while old accuracy loses at most ten points. Retain this criterion even if the frozen reader is already perfect.

Passing temporal port expression and attribution confirms that new Core learning can be expressed through the existing personal readout. If only the endpoint passes, the temporal features failed their target; this does not establish loss of the Core mechanism. If both valid readout conditions lose the previously established port expression and causal effect, finish delivery and pause the campaign as an adverse contradiction. Other ordinary negatives are delivered normally. Do not replace the primary window, omit origins or substitute later calibration for first responses.

## Apparatus, resources and delivery

Before registration, verify temporal bins, discrimination of order, anonymous port masking, readout save/restore/continued learning and the inference boundary. The separate apparatus then checks identical complete states under normal/frequent observation, complete save/restore and host pause, plus the intervention whitelist, restoration and matching. Apparatus answers do not select windows or thresholds.

Budgets are 4 GiB each for originals, archive and API readback, plus 128 MiB analysis and the 25 GiB reserve. Runtime is at most two hours and private memory 1 GiB. Check commit/RAM/C/E reserves of 5/4/5/25 GiB every second and pause at complete-source boundaries. Inspect the first source's cost; if it exceeds the eight-source per-unit allocation, stop and recalculate without deleting checkpoints. Preserve any new dead-host in-flight state for review.

Changes from old M5 are explicit: kernel version, temporal features, teaching intervals and bounded old-task correction. Origin count, linear model family, causal branches, historical score thresholds and cue types remain. The 110-ms condition is a same-experience control within this batch, not an exact replay of the old 5.1 curriculum. Deliver independent read-only recomputation, bilingual scientific conclusions, full original-package API readback and zero pending requests. Production Core, historical subjects and manuscripts remain unchanged.

This repeats historical R51k and incorporates its complete-origin host release and corrected active-index audit before the first registration; see the [implementation note](implementation-note.en.md). These tooling corrections are frozen together and do not alter the scientific course, parameters or scoring.
