# E23: background input and observation effects

The [Chinese preregistration](design.zh.md) and [English preregistration](design.en.md) specify the fixed criteria. [Execution notes](execution-notes.md) preserve runner errors and the serial confirmation of a scheduling deviation. No Core parameter or implementation changes are made.

Run from the repository root using the project's Python environment:

```powershell
$py = ".\.work\kernel-venv\Scripts\python.exe"
& $py lab/explorations/2026-10-01-observation-background/run.py prepare
& $py lab/explorations/2026-10-01-observation-background/run.py replication
& $py lab/explorations/2026-10-01-observation-background/run.py loads
& $py lab/explorations/2026-10-01-observation-background/run.py live
& $py lab/explorations/2026-10-01-observation-background/run.py later
& $py lab/explorations/2026-10-01-observation-background/analyze.py summary
& $py lab/explorations/2026-10-01-observation-background/analyze.py audit
```

These commands reference this exact registered study, not an invitation to overwrite it. Completed cases are loaded and verified; closed studies reject new simulation. A new research campaign needs a new name/work directory, updated true usage baseline and its own preregistration. The historical correction command `serial_check` is documented in the execution notes. Every subsequent stage waits for the preceding process to finish; an OS file lock now enforces one simulation worker per study.

Live telemetry requires real-time pacing. The helper `case_run_spec` validates this protocol, but does not itself drive a scheduler. Replay records both stimulus delivery times and when each future input entered the queue. Replacing live sampling with a tape never changes its encoded values or delivery schedule.

Minimal observation includes common receipts, low-frequency metrics, checkpoints and final capture. Dense observation additionally samples full state and existing readers; it is not an alteration of the model. Dummy load is deliberately separate from reading. No classical copies, OS random choices or conditional statistics are represented as a physical quantum experiment.

后续实验可复用 `lab/tools/service_study.py` 的显式实时协议、`lab/tools/study_lock.py` 的单 worker 锁，以及本目录的输入带排队时刻重放方法。协议与实验工具不侵入生产内核。原始输入、早期封存、后续选择、失败记录和串行重演均保留，不能只挑成功的记录分析。
