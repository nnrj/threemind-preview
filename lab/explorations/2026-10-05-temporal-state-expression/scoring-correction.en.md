# E48: separate actual naming from cue-specific scoring

2026-10-05, item-level review after stage A.

Stage A reported9/12 for activation/inhibition and12/12 after adding history at326s. Both were **cue-specific correct counts** under the old criterion: correct and different from the matched no-cue output. Actual naming is12/12 in both cases. The change is that no-cue output was a name in the former and blank in the latter. Describing this broadly as improved naming was imprecise. Append this correction without overwriting the original record.

Report actual correctness and cue specificity separately. A cue-specific penalty is not absent response, failed naming or absent internal association. Preserve no-cue text; matching words may arise from different processes or ongoing activity, requiring process/intervention evidence. Scoring does not alter outputs.

Also isolate the old assumption that no-cue calibration should be blank. That can train rejection for a limited task, but is not ground truth for free association. Add one source223 all-channel-history decoder, omitting the two no-cue blank supervision examples and using the16 taught correspondences,6000 steps, otherwise matching the longer-training control. Retain no-cue testing without declaring blank to be its true label. Word-like output alone does not verify inner-monologue translation. One additional model only.

Keep the old scores and training for provenance. The new main expression neither subtracts a baseline nor normalizes individual samples nor filters content using no-cue output.
