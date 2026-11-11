# E47 stages A/B: a delay explanation excluded; inhibition improves discrimination

Recorded2026-10-05 before C results. This is not a final language-capability verdict.

**Repeated late text is not a decoding backlog in the old experiment.** Three sources, nine real windows and twelve readers yield36 window-reader pairs. CPU sequential, CPU reversed batches, reload,50ms queued and GPU batches produce180 outputs with identical tokens for each pair. All12 readers return empty text for all-zero activity. Late-window language/visual activations are zero while other activity remains. The words depend on current remaining activity and the reader, not an unfinished earlier visual window; they are not automatically credible inner speech.

**Earlier readouts missed distinguishable responses, and inhibition is informative to the instrument.** 378 new calibration copies plus390 old probes give768 evidence rows, still only three independent sources. Finite-vocabulary cosine readout, calibration0.4/0.6 and test0.5 with held-out views:

| After266s teaching and60s wait | Cue-specific word→object | Cue-specific visual→name |
| --- | ---: | ---: |
| Absolute activation, frozen266s calibration | 0/24 | 0/12 |
| Absolute activation,326s refit | 15/24 | 9/12 |
| Activation+inhibition contrast, frozen266s | 8/24 | 3/12 |
| Activation+inhibition contrast,326s refit | 18/24 | 12/12 |

Contrast subtracts a same-state/time no-cue twin. The entire directly stimulated modality is excluded from features; raw activity remains intact. Refit uses no test rows but knows current-state labels from other strengths/views. It establishes discriminable responses, not acquisition of new knowledge with frozen expression. The actual preceding-window baseline was less effective; a deployment solution remains open.

Of eight registered mode/conditioning combinations, joint activation/inhibition without additional mean/std conditioning scored highest on137/163,71.875% overall cue-specific correctness.191 was excluded from selection. Every state/direction is saved, not just favorable entries.

Sources: [registration](design.en.md) and `.work/expression-alignment-20261005/latency-output.json.gz`, `latency-summary.json`, `features.json.gz`, `feature-decodes.json.gz`, `feature-summary.json`, to be included in the final archive.

Proceed to registered C using new sources223/251/279. Expression learns identity and reversal; cyclic assignments are completely held out. Only answers following changed Core experience through the frozen reader pass the new-correspondence test.
