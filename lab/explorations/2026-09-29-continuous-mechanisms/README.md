# Continuous-kernel attribution study

[Report](report.en.md) · [中文](README_CN.md)

341 instances, 2026-09-29. A full 2×2×2 factorial, curriculum counterbalancing, test-time switches and matched telemetry identify short-term resources interacting with existing inhibition, thresholds and learned weights. Fast trace contributes little here; context allocation contributes no measured change; threshold perturbations expose fragility. No Core/default changes or old-data replacement.

Project: `e769cd2d-c636-41b0-a266-6af1cca4b805`. Plans, notes, nine records and bilingual reports are published using Lab services. Raw evidence and parent states are downloadable from the reports.

CLI: use `.work/kernel-venv/Scripts/python.exe lab/explorations/2026-09-29-continuous-mechanisms/run.py` with phases `prepare`, `validate`, `factorial --bits 111` (all eight masks), `test-switch`, `baseline`, `background`. Existing study preparation is rejected; completed instances are hash-checked and loaded. For a fresh independent replication, copy the orchestration into a new study directory with explicit new WORK/project/budgets and a new design. Exact validation depends on the previous block-0 evidence; without it, establish a declared fresh reference rather than claiming that validation passed.

`diagnose.py preregister/run` registers and executes the six-setting diagnostic amendment. `analyze.py` produces `analysis-v2.json`, correctly censoring undelivered B-only controls. `mechanistic.py` re-evaluates existing equations on saved observations and plots them; it performs no new training. `audit.py` verifies instances and parent hashes. `publish.py` reads and checks every archive member before uploading and saving reports.

Runtime uses existing native CPU engines, RuntimeInputs, ReadoutSession, public reconfigure and Lab persistence services. Observation uses public event streams; no state edits, fabricated inputs, or feedback from the observer. Storage is isolated under `.work/continuous-mechanisms-20260929/`; previous data is not scanned or cleaned.

Evidence: frozen designs/source hashes; `validation.json`; full factorial/switch/background/baseline/diagnostic results; per-case configuration/state hashes; compressed all-node trajectories and public events; compressed parent states and diagnostic snapshots; analysis v2, mechanistic equation checks, audit and context-trajectory parity. See [design](design.en.md), [report](report.en.md) and [final delivery](delivery.en.md). Archive member SHA-256 hashes are verified before publication. Delivery records are generated afterwards and retained separately.
