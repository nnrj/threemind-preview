# E48 bounded decoder-fit check

2026-10-05, after the1200-step raw activity/history results and before longer training.

The planned small Transformer answers only4–7 of18 **training** items correctly. It has not calibrated its own translation, so test failure cannot show absent Core information or useless richer state. Preserve the original results.

Add one step-count control: first train source223's raw all-channel history features from the same random seed for6000 steps. Data, split, architecture, learning rate and numerical values stay fixed. Repeat for251/279 only if training accuracy reaches at least17/18; never choose parameters using unseen-mapping scores. Otherwise stop optimization this round and report an expression-training obstacle. At most three models, within E48's aggregate limits.

No-cue blank labels are calibration for this limited naming task, not evidence of absent internal activity. This decoder is not released as a general inner-monologue interpreter.
