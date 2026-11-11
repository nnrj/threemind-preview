# Native-pattern language instruments

[简体中文](../../zh/reference/native-expression-tools.md) · [E46](../plans/native-expression.md) · [Central adapters](central-adapters.md)

These external tools consume anonymous trajectories from existing observation interfaces. Physical-sensation template comparison remains a separate instrument; this reader can learn an individual's actual distributed pattern.

- `threemind_transformer.native_readout.NativeProjection`: versioned channel exclusions, temporal bins, magnitude floor and unknown-channel reporting. Question/answer metadata is not model input; no state writes.
- `PrototypeLanguage`: cosine attention over examples and a finite phrase vocabulary, with unresolved/tied/silent outcomes. Probabilities express uncalibrated similarity, not semantic truth.
- `lab.tools.native_expression.FeatureCalibration`: train-only numerical centering/scaling, frozen for testing; explicit partition checks.
- Existing `TemporalLanguage`: scratch byte generation from temporal features. Manifests retain features, training sources, individual binding, shared scope and relative checkpoint paths.

Python and CLI use the same classes. JSONL outputs are never overwritten:

```powershell
& .work/kernel-venv/Scripts/python.exe -m threemind_transformer.native_readout project --config projection.json --input processes.jsonl --output features.jsonl
& .work/kernel-venv/Scripts/python.exe -m threemind_transformer.native_readout fit --config attention-settings.json --input training.jsonl --output prototypes.json
& .work/kernel-venv/Scripts/python.exe -m threemind_transformer.native_readout decode --config prototypes.json --input features.jsonl --output words.jsonl
& .work/kernel-venv/Scripts/python.exe -m lab.tools.native_expression --manifest expression.json --input processes.jsonl --output translated.jsonl --device auto
```

Attention settings may be`{}`. Training rows contain`split: "train"`, two-dimensional`values`and`text`; test rows are rejected by fitting. Processes contain`start_us/end_us/planned_end_us/trajectory`, with node`channel/activation`. A`process`wrapper is accepted; unrelated wrapper metadata is not forwarded. Projection configuration comes from`NativeProjection.to_dict()`; E46 generates expression manifests. CPU is supported; auto or unavailable CUDA falls back to CPU and records the device. No remote providers are called.

Output is **passive linguistic interpretation of activity**, not evidence that the individual chose to speak. Preserve raw trajectories, unedited text, unresolved cases and errors; do not polish them through another language model.

E46's prepare/reassessment/sources/train/initial/continuations/new-experience commands implement a frozen study, not arbitrary overwriting of existing evidence. Reports and evidence expose the results in the research platform. These experimental heads do not replace the ordinary chat's default device.
