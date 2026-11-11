# Activity-process readout calibration

Status: implemented and calibrated. 2026-09-30. [Tool guide](../v2-observation-tools.md) · [Calibration report](../../../lab/validations/2026-09-30-process-readouts/report.en.md)

Recent studies exposed distinct measurement failures: responses ending before convergence, weak activity excluded by thresholds, background dominating final rankings, token templates missing active nodes, and device sources not opening observation windows. Unobserved, below a criterion, and no measured change within complete coverage are different outcomes.

The memory/transfer study (`lab/explorations/2026-09-30-memory-transfer/report.en.md`) recorded task responses and controlled disconnection/restoration effects despite 736 primary convergence windows missing the task response. Historical outcomes remain unchanged; this does not imply every negative readout conceals memory.

The user emphasizes that valuable information can reside in a changing process rather than a static endpoint. Record order, duration, movement, recurrence, increases and decreases. Per-node peaks must not be presented as a simultaneous state.

Implementation: introduce activity-analysis `/2` while retaining `/1` and the steady-state reader. New configurations use bounded full-window observation at 20 ms. Preserve convergence-time rankings separately from raw activity, signed baseline changes, temporal measurements and transitions. Add stimulus-free observation windows and complete-vector comparisons with explicit time alignment, missing coverage and causal limits. Connect UI, API, CLI and exports. Sampling must not change Core dynamics or legacy reader cadence.

Validation uses transient weak responses, sustained background, decreases, sequential transfers, recurrence, zero response, coverage failures and existing recorded trajectories. Compare Core hashes with observers enabled/disabled and after recovery across Python/Rust. No retraining, historical overwrite or data cleanup. New calibration evidence targets less than 256 MiB, single-process execution; publish the outcome separately before marking completion.

Delivered: 840 existing windows reanalyzed; 192/192 trained cued memory tests contain process activity, versus 0/48 untrained cued controls. Ninety-six full-vector comparisons distinguish targeted connection silencing from restoration and unrelated-edge controls. Zero new simulations; approximately 4.67 MiB new JSON evidence; 2,760 unchanged source-file hashes. Activity counts are not revised task accuracy.

The shared library, registry, declarative batches, same-source probes and UI/API/CLI/MCP operations reuse existing research orchestration. Twenty-millisecond sampling with 60 maximum period samples preserves the 1.2-second search range. Five kernels across Python/Rust pass observer/recovery invariance; the final Runtime/CLI regression passes 55 tests, and 1440/390-pixel interaction checks pass. Migration 054 is applied to local `threemind`, adding worker capability matching without rewriting historical data. Running application processes were not restarted.
