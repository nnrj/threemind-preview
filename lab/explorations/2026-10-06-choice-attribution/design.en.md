# E57: where does a pointing choice come from?

Preregistered 2026-10-06. [中文](design.zh.md)

Separate learned Core history, transient sensory dynamics, the supervised external selector, and the servo. Preserve E56/E50 sources and conclusions. No Core, sensory encoding, or default changes.

## A: external sufficiency

Read E56 recorded inputs/activity, with its 48 calibration +12 practice labels and 24 confirmation questions. Use SpatialChoice, 1200 steps, seeds223/279/337, equal architecture/parameter count and training-only model selection. Conditions: learned Core eight samples; learning-disabled Core eight samples; direct incoming stimuli eight samples; direct stimuli all20 samples. The last condition checks missed character frames and is reported separately. Direct physical input occupies the first of four slots per anonymous channel, the other three zero. This is an external baseline, never forged Core activity. No text, object identity, answers, or target coordinates enter inference. Background retained. Confirmation questions are now fixed replication items, not newly blind tests. Do not select the best seed.

High bypass performance establishes task sufficiency without Core, not that the original system never uses Core. Low bypass performance alone cannot establish learning inside Core.

## B: same present, different histories

Two new Core sources223/279. Each has original/reversed naming histories and corresponding learning-disabled-from-birth controls. Four grey shapes, 4x4 optical sampling and full bodily/weather background. Names甲乙丁戊 denote shapes0/1/2/3 or1/2/3/0. Teacher markers and actual sentences teach each name ten consecutive times then three reviews with0/6/18simulated-second expanding gaps. Same dose/duration, object/name counts and rotated lesson locations.

For each source, one shared reader trains on32examples spanning both histories; no history ID is an inference input. Seed223,1200steps, then frozen. Equally train a learning-disabled reader and a direct-input reader. Test32queries in four held layouts/views. Paired identical scene/query has different correct targets; retain all objects and background and remove teacher markers. Common current body/world state removes physical-history leakage, explicitly an experimental relocation. A deterministic history-free reader has a maximum16/32 on these identical-input pairs.

Continue teaching Core only: reverse the original history versus equal original-history reviews. Freeze the reader and test16pairs at a common current world/time. Report both-correct pairs, correct directional changes, and nonspecific drift. Never retrain the reader to rescue this test.

Only if the fixed reader scores at least24/32 do selective visual-language edge silencing, count/weight-matched other-edge silencing, rescue, donor edge transfer and matched transfer. Select masks from physical channel inventories, not answers. Use the E50 copied-state intervention boundary. Below threshold, report that reliable history readout was not established and stop extended ablations; do not generalize that no internal learning occurred.

## Bounds and delivery

One worker,600new sources/forks,90minutes compute,4GiBprocess,2GiBfree RAM,2GiBsoft/4GiBhard additional evidence including archive,5/15GiBfree C/E. Account starts74%; +4points stops extension,+6stops computation, shared usage counted conservatively. Avoid redundant large-data hashing. Preserve every seed/failure/prediction. Publish new project with designs, input, snapshots, models and bilingual report, update history/backlog without rewriting older evidence. No expanded video or servo training: attribution is primary. Neither external success nor failure decides all prior Core causal findings or language/reasoning.
