# Activity contrasts and timestamped language interpretation

[中文](../../zh/reference/expression-observation-tools.md) · [E47 design](../plans/expression-alignment.md)

`lab.tools.expression_observation` reads recorded dictionaries outside Core. It owns no engine and performs no dynamics writes. E46 tools and manifests retain their original meaning.

`threemind.timed-expression/1` preserves window ID, simulated sample interval, host enqueue/start/completion times, batch duration and size. Host and simulation clocks are distinct; do not subtract them as a model delay. Late display remains attached to its original sampled window.

`threemind.expression-observation/1` supports absolute activity, same-state no-cue differences and subtraction of a preceding window's channel means, optionally combining activation and inhibition. Preserve signed changes, floor1e-8, and explicitly declared input-channel exclusions. Original evidence remains intact. Feature column ordinals are external observation layout, not new receptors.

**The same-state no-cue twin is a research counterfactual, not a normal deployed sense.** It requires an identical checkpoint/background schedule. Preceding-window mode needs only past observations but need not discriminate equally well. Label raw activity, contrasts and generated interpretations separately.

From the repository root using the project Python:

```powershell
.work/kernel-venv/Scripts/python.exe -m lab.tools.expression_observation project --manifest manifest.json --input processes.jsonl --output features.jsonl
.work/kernel-venv/Scripts/python.exe -m lab.tools.expression_observation decode --manifest manifest.json --input processes.jsonl --output words.jsonl --device auto
```

Each JSONL row contains`id`, `process` and the required`baseline`. Processes require`start_us/end_us/planned_end_us/trajectory`; nodes require`channel/activation` plus`inhibition`for joint features. Paired intervals must match; preceding windows cannot contain the future. Maximum256MiB and16384rows per file; outputs are exclusive and never overwritten.

The manifest contains`observation`(projection/mode/fields/schema), with`checkpoint`relative to its location and training-only`feature_calibration`for decoding. E47 model manifests are directly usable. CUDA requests fall back to CPU when unavailable and report the actual device. Preserve raw tokens, malformed text and blanks; interpretation does not command Core to speak.

Finite-phrase similarity is a control instrument, not free language. Save model, observation layout, calibration provenance and individual binding together; weights alone do not establish compatibility with another instance.
## Connection controls and applicability (2026-10-05)

`lab.tools.connection_controls.cross_domain_masks(image, left, right)` accepts an exported state dictionary and disjoint channel sets. It returns crossing edges and an equal-count control selected from other edges by nearest available weight. This pure-data function does not hold or mutate Core. It reports per-edge error, weight totals and `topology_matched: false`; insufficient controls return `None`. Execution requires an explicit research copy and the existing silence interface. Nearest available does not guarantee balanced weight: E47 control weight totals were only66.3%–72.7% of targets. A selected domain is not a predefined semantic brain area; silencing its pathway is not automatically an intervention on advanced reasoning.

**Same-state subtraction removes activity shared with the unprompted twin, and normalization removes overall amplitude.** All-channel contrast is not complete raw state. Identical unprompted processes cancel by construction, which cannot establish absent inner speech or autonomous activity. E47's new heads learned no-cue→blank and are prompted-response readers. Unprompted interpretation still requires unsubtracted continuous evidence and independent validation. [E47 report](../../../lab/explorations/2026-10-05-expression-alignment/report.en.md)
