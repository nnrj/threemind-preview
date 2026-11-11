# Raw state expression tools

2026-10-05, E48. [Chinese](../../zh/reference/raw-state-expression.md) · [Decisions](../plans/temporal-input-and-state-expression.md)

`python -m lab.tools.raw_state_expression --manifest layout.json --input processes.jsonl --output new-output.jsonl`

Add`--checkpoint reader.safetensors --device auto`for direct decoding with CPU fallback. Each line is`{"id":"sample-1","process":{...}}`; output is new-only; input file limit256MiB.

`threemind.raw-state-expression/1` declares anonymous channels, fields, and sample count. It selects explicit recorded samples and returns their actual times without subtraction, per-sample scaling, clipping, semantic filtering or top-k. Unknown channels/missing evidence fail rather than becoming zero. Explicit direct-sensory exclusions are attribution instruments, not full-state expression.

`threemind.raw-graph-state-expression/1` reads five full snapshots: node activation/inhibition/trace/support/stability/plasticity/direct and associative arrivals/generated and pending inhibition/touch counts; directed edge weight/stability/eligibility/touch counts; available/active/utilization short-term states; fast values, presence and local ages in seconds. Stored lazy-state values and their ages remain explicit. Limit262144columns and5samples.

This is expanded dynamical-state reading, not the entire state container verbatim. Full restoration images remain evidence. Configuration, seeds, labels, experiment IDs and pending external lessons are not decoder inputs. Internal in-flight messages and all global counters are not yet feature columns; do not claim exhaustive information. Inputs retain their magnitudes; the Transformer still learns transformations within its existing architecture.

Each decode starts with an empty cache and receives no earlier conversation/output. Weights learn translation rules; this differs from storing a current answer or dialogue memory in the adapter. Freeze weights for new-assignment attribution and separately declare developmental training/held-out splits.

`ridge_fit/ridge_predict` is a fixed-regularization raw linear diagnostic with a learned intercept, not evidence of reasoning by itself. Use learning-disabled, reversal, held-out mapping and pathway controls.

2026-10-05 delivery addition: actual correctness and cue specificity are separate. No-cue blank is not semantic ground truth and must not filter expression or disprove autonomous activity. [Correction](../../../lab/explorations/2026-10-05-temporal-state-expression/scoring-correction.en.md)
