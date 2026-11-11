# Raw output bus and expression calibration

2026-10-05,E49.[中文](../../zh/reference/bus-expression.md)

`threemind_runtime.activity_stream.RawActivityStream`publishes complete current node measurements through copied OutputBus subscriptions. `sample(engine)`does not advance time, rank, add semantic labels, compress or write back. `publish(frame)`supports replay. Callers explicitly choose sampling cadence.

Legacy `ProcessFeatures` remains version-compatible. It keeps activation and merges hash buckets/time bins; inhibition, some channel identity and within-bin order are lost in this observer, not in bus transport. New experiments use raw measurements without silently replacing old model inputs.

```powershell
.work/kernel-venv/Scripts/python.exe -m lab.tools.expression_calibration train --manifest layout.json --input teaching.jsonl --output new-reader.safetensors
.work/kernel-venv/Scripts/python.exe -m lab.tools.expression_calibration decode --manifest layout.json --input observations.jsonl --checkpoint new-reader.safetensors --output words.jsonl --device auto
```

Manifest:`threemind.raw-state-expression/1`. Each JSONL record:`{"id":"optional","process":{...}}`; training additionally requires `text`. Decode rejects that field. Raw frames pass OutputBus before declared projection; no per-sample scaling/subtraction, no dialogue cache, no answer-based output filtering.

Small-data training defaults to complete balanced batches;`--sampling random`reproduces sampling with replacement. Training`--checkpoint`continues the external reader only. Steps/rate are configurable.≤64teaching examples; CPU fallback; default30min/RSS4/GPU3GiB limits. Original training API, checkpoints and Core defaults remain unchanged. Exact four-name accuracy calibrates the instrument, not a general definition of language; approximate speech and correction through further teaching are evaluated separately.

New CLI-trained checkpoints bind anonymous channel/field layout; decoding and continuation reject reordered layouts even at equal width. Historical research checkpoints require their original receipt/manifest; do not infer ordering. This stream is not a complete connection snapshot. CPU CLI, label rejection and ordering rejection were verified: [E49 acceptance](../../../lab/explorations/2026-10-05-bus-expression/verification.json).
