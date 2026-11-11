# Multi-kernel research tooling and initial experiments

[中文](../../zh/plans/research-tooling-and-candidate-experiments.md)

## Authorization and boundaries

Implementation approved on 2026-09-29. Complete and verify foundational tools before scientific experiments. Preserve causal/9, continuous/1 and lif/1 formulas, sensory mapping, and existing experiments. Activation cessation defines death; budget stops do not. The user additionally authorized optional parameters and new kernel types/variants when needed. Version additions separately, document justification and ablations, and preserve the baseline. Changes during a study require a new protocol and batch rather than pooling changed conditions. Discuss new hypothesis conflicts rather than adjusting mechanisms for attractive results.

GPU acceleration applies to the local Transformer tool, not the three CPU kernels. Implement device selection and fallback first. Real GPU validation awaits the user's CUDA-enabled PyTorch environment; simulated failures are not real-device validation.

## Delivery status

Approved work without linked validation remains **incomplete**.

|Stage|Delivery|Status|
|---|---|---|
|A1|Device discovery, auto/cpu/cuda, VRAM budget, CPU fallback, execution evidence|Implemented; real GPU validation in C|
|A2|Shared API/CLI/MCP operation catalog, request identity, revisions, progress and cancellation|Implemented and verified|
|A3|Bounded repeat/stage protocols, anonymous frames, absolute time targets, recovery and calibration|Implemented and verified|
|A4|Compressed experiment snapshots, import, read-only viewing and recovery under new identities; file/peer/OCI distribution|Implemented; live OCI registry validation pending|
|A5|Desktop/mobile UI, capability parity, code/data separation, human-controlled cleanup preview|Implemented and verified|
|B|Calibration, adaptation/recovery, pair retention/interference, sequence/context and independent Transformer controls|Six blocks complete; see study report|
|C|Real GPU consistency and performance validation|Awaiting environment configuration|

### Implementation evidence (updated as work proceeds)

- 2026-09-29: device policy, isolated CPU fallback and CLI discovery are connected. Eleven CPU/simulated-fault checks pass. This environment reports PyTorch 2.14.0+cpu; real GPU remains unverified.
- The operation catalog uses actual API schemas. CLI and optional official MCP SDK 2.2.0 share one client. Project request receipts occupy a new table without altering consciousness data. Unknown outcomes prohibit blind re-execution.
- research-plan/3 stores compact stages/repetitions and derives the current repetition from a durable step index, without expanding a huge list. Anonymous frames are supported. Existing /2 serialization/hashes remain unchanged. Ten stage recovery, legacy plan and real stdio MCP handshake checks pass.
- Database tests use isolated PostgreSQL on 55439. The launcher stops only services it started and keeps logs outside PGDATA. Skipped or connection-failed attempts are not counted as passing.
- Snapshot checks cover stage wait cursors, in-flight signals, pending image/text commands, equal state hashes after independent continuation, permissions and invalid archives. File/peer transfer and bounded OCI subprocess checks pass; no real OCI registry was contacted.
- The final Python regression completed 39 checks before exposing a historical fixture that did not reverse migrations 51–53. After fixing that fixture, all 18 migration, model-reference, device-wiring and readout-fidelity checks passed. CPU Transformer serving and real MCP stdio handshakes are verified.
- Production build, TypeScript and translation audit pass. Four kernel-page browser checks and four research-tool checks pass, covering narrow layouts, bidirectional stage GUI/JSON editing, pagination, snapshot save/view/paused restoration and Canvas 2D fallback when WebGL is unavailable. Temporal evidence displays classification and final activation ordering alongside its full original record.
- See the [research tools guide](../v2-research-tools.md) for contracts and limitations. Whole-population coordinator checkpoints are outside this single-consciousness restoration scope; do not claim restoration of an entire population experiment.
- Completed 72 calibration cells, six blocks with 2,832 formal outcome rows, and 12 CPU Transformer controls. All three kernel formulas and default sensory mappings remain unchanged. The [English report](../../../lab/explorations/2026-09-29-candidates/report.en.md) and [execution sources and reproduction boundaries](../../../lab/explorations/2026-09-29-candidates/README.md) document conditions, findings, limitations and audit evidence.
- Bilingual reports, six block records, Markdown/HTML exports and the member-verified raw evidence archive are stored in the project. [Delivery and measured resources](../../../lab/explorations/2026-09-29-candidates/delivery.en.md) are recorded separately. Report attachment fixes pass path isolation and actual desktop/mobile service checks, including independent table scrolling and original-size image links.

## Tool contracts

- UI, CLI and MCP share services, authorization and validation. No direct SQL bypass. Operations expose schemas, capabilities, prerequisites, request IDs, results and reconciliation of unknown outcomes.
- Retry the original request ID; freeze absolute advance targets. Scientific undo means checkpoint branching.
- Snapshots preserve kernel/in-flight state, input cursors, sensory/readout context, RNG, repeat/stage cursor, dependencies and versions. Exact recovery is promised only at committed boundaries. Transformer recovery initially covers completed training-task boundaries.
- Import read-only or as a paused new experiment; never overwrite source evidence. Unsupported versions are read-only. Reconnecting physical devices changes the recorded environment condition.
- Kernel definitions, learned models and experiment bundles are distinct. Use `threemind.experiment-bundle/1`, ZIP64, streaming chunks, hashes and decompression budgets; reuse Arrow/Parquet and Zstd for numeric evidence.
- Local files, authenticated ThreeMind peers and optional ORAS/OCI distribution preserve digests and lineage. Pulling never executes content. Do not package credentials or executable pickle.
- Auto selects GPU only after bounded measurements including transfers show stable speedup of at least 20%. Explicit GPU preference may override performance advice. Use FP32; do not silently alter batch size, data or architecture. Preserve failed GPU attempts and retry once from initial conditions in a fresh CPU child within the original remaining budget.
- Cleanup requires human confirmation. Export is not deletion; do not rewrite Git history or scan old large datasets.

## Experiments

Use six distinct anonymous-channel/real-environment recording blocks; these do not automatically constitute six statistically independent mechanism samples. Separate calibration material and freeze parameters before formal runs. Independently born kernels receive matching external inputs; never translate state across kernel families.

1. Calibration: intensities 0.125/0.25/0.5/1/2/4; intervals 0.01/0.1/1/10 simulated seconds. Predefine selection of the smallest observable, nonsaturating dose.
2. Repetition/adaptation/recovery: twenty repetitions, rest 0.1/1/10 seconds; individual continuous STP/fast-trace/context and LIF STP/adaptation ablations.
3. Pair retention/interference: four anonymous pairs, blocked twenty initial repetitions then ten and five revisits; retention 1/10/100 seconds, untrained/no-plasticity/remapped controls.
4. Order/context: A→B→C and D→B→E, control unigram and first-order transition counts. Separate pure sequence and explicitly overlapping sensory conditions; never wire neural connections manually.
5. Transformer probability controls with frequency/first-order baselines; no Core feedback in this phase.

Long training uses genuinely recorded host telemetry at intensity 0.2 with no-background controls. Conditions within a block replay the same recording. Do not loop a short recording to fabricate independent samples. Continuous-kernel primary evidence is final activation sorted at temporal convergence; peaks/integrals/probes are secondary. Report LIF voltage, current, actual spikes and display projection separately. Nonconvergence, death and budget censoring are distinct outcomes.

The original plan allowed at most two follow-ups, each with four fresh blocks. This round stops at the fixed matrix without using those additional branches; millisecond-scale LIF readouts, offset inputs and edge-growth auditing remain future recommendations. Save design notes before execution, records per batch and bilingual reports separating facts, interpretations, alternatives and limitations.

## Resource limits

One runtime worker, two numerical CPU threads, 4 GiB process RSS, at most 24 hours total compute; stop when the matrix completes. Compressed evidence target 4 GiB, hard cap 8 GiB. New database/cache/export/temp occupancy at most 20 GiB; preserve at least 15 GiB free on both data and database volumes. Temporary files live on E. Save progress on budget stops; no silent observational downsampling.

Default GPU allowance 2 GiB with 512 MiB headroom and one task at a time. These are allocation/monitoring controls, not OS-enforced isolation. Build/install caches have a separate ledger but still require actual free-space checks.

Experimental Codex account-usage increase is capped at ten percentage points of total allowance; engineering and experiments have separate ledgers. Check between batches and conservatively include other account activity. Autonomous runners do not invoke AI narration/generation. Preserve old data; use local staged commits, no push.
