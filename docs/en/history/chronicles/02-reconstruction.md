# Volume II — Reconstruction, gains and mechanisms recovered

[简体中文](../../../zh/history/chronicles/02-reconstruction.md) · [English](02-reconstruction.md)

## From workstation prototype to research platform

August work clarified background input. The 13 August plan made host physical telemetry the default while retaining separate random-environment and process controls. On 16 August, instance-computation feedback and default-disabled global homeostatic clamping were authorized. Host, shared process and individual runtime measurements are different; real CPU time is not Core energy. Feedback still enters through adapters and InputBus, not direct OutputBus recirculation. [August primary plans](../sources/august-adapters.md)

The root commit of 24 August preserved the old Python runtime, frontend and documents, later becoming the restoration baseline. Huge test-data versions in earlier Git history had led to rejected pushes and a backup/recreation discussion; the earlier backup was not recovered here. Late-August commits also changed peripheral functions such as audio capture. The September architecture review addressed growing graph overhead, large JSON model files, full graph copies, queues and evidence storage coupled together. Shared references in snapshots could invalidate matched-copy comparisons. [A01 · Second-generation assessment](../../../zh/second-generation-architecture-assessment.md) [Commit record](../sources/git-register.md)

The redesign separated the evolving in-memory model, Runtime integration and recovery, and Lab experimentation and evidence services. PostgreSQL became the workstation's fact store. Arrow serves columnar memory and transport; Parquet stores evidence files; DuckDB supports analysis. They are not interchangeable competing databases. Model export should be requested, not a large-file rewrite on each activation. Standalone Runtime must operate without the Lab database, while local deployment and account-isolated public hosting both remain possible. [A01 · Storage and deployment decisions](../../../zh/second-generation-architecture-assessment.md)

The default renderer moved from a mandatory ThreeJSON path to batched Three.js points, lines and instancing. This was a decision about the real-time graph update path, not a rejection of every ThreeJSON use. Video and explanatory visualization may still integrate separately. The surviving sources do not establish a universal performance ranking across all workloads.

## Approval to change time was not approval to discard other mechanisms

The researcher accepted timestamped delivery and simulated time so accelerated training need not wait for wall-clock years. Numerical steps, propagation cadence, display refresh and wall-clock speed were subsequently distinguished. A smaller solver step does not authorize repeating every nonlinear discrete operation more often. [D01 · Restoration and time conversion](../../plans/v3-restoration.md)

The rewrite also lost or changed capabilities: creation became JSON-heavy, ordinary instances acquired a mandatory duration, chat and readable passive output became inconvenient, and important sensory modes were buried. Old V3 edge birth, local plasticity, novelty, inhibition and forgetting were replaced by simplified rules. The researcher explicitly rejected treating those losses as an automatic cost of modernization. Restoration therefore moved to a source-based list of approved differences, recovered behavior and unresolved questions. [A03 · Capability restoration](../../../zh/v2-capability-restoration.md) [A04 · Behavior audit](../../v2-kernel-behavior-audit.md) [D01 · Restoration baseline](../../plans/v3-restoration.md)

## Recovery did not mean returning to frame-driven time

Restoration used the actual V3 formulas in `97d8592`, without reviving V1/V2 presets. It retained unified time and the approved ability of actual nonzero propagation to reinforce an edge independently. Weak signals pass an edge-by-edge threshold; a saturated receiver cannot undo transport cost already incurred. Edge birth retains coactivation, consolidation and novelty. Isolated nodes and small disconnected networks remain valid. Pruning again requires joint conditions rather than silence alone. Commit `c42baed` records this recovery. [D01 · Decisions, parameters and verification](../../plans/v3-restoration.md)

The recovered version used `causal/8` and `state/6`; the subsequent activity-only death rule produced `causal/9`. Versions preserve historical instances, so present defaults must not be projected backward. The location of old associative consolidation inside a candidate-edge branch is verifiable; the original author's motive for that organization is not recoverable from the initial import.

## Instruments are part of research capability

Graphical/JSON parameter synchronization, organs, comparisons, innate versions, ecological training, documents, notes and reports were progressively completed. A unified adapter means a common identity, sampling and transport boundary, not identical capabilities for every device. Evaluation uses independent newborn copies and does not write test learning back to parents. Motor output still used fixed projection; learned functional brain regions had not thereby been demonstrated. [A02 · Validation log](../../../zh/v2-validation.md) [A03 · Restoration ledger](../../../zh/v2-capability-restoration.md) [P04 · Differentiation boundary](../../../zh/embodied-functional-differentiation.md)

The lesson was concrete: a successful build or responding API does not establish recovered interaction or equivalent dynamics. A further chat correction appears in the next volume. An acceptance entry is evidence of a check, not immunity from later correction.

---

Compiled on 2026-10-01, covering the record available on that date. Original evidence is retained separately from later interpretation.
