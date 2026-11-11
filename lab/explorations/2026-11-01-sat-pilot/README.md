# ThreeMind 3-SAT pilot — 1 November 2026

A separately authorized, bounded exploration, using `continuous-memory/5.1` without kernel changes. Historical experiments and automations remain paused.

- [中文报告](report.zh.md) / [English report](report.en.md) / [交付核验](delivery.md)
- [中文协议](protocol.zh.md) / [English protocol](protocol.en.md)
- The study asks whether a learned local preference improves a declared hybrid 3-SAT search system. It does not ask the Core to parse formulas or invent a solver.
- Original states, materials, traces and receipts belong under `E:/ThreeMindData/experiments/2026-11-01-sat-pilot/v1`, outside Git. `runner-manifest.json` there freezes the executed runner; later analysis and publishing files are separately recorded as postprocessing.
- The eight independently born sources and their explicit paired research branches are the registered units. Individual problems, decisions and branches are nested observations.

## Commands

Run from the project root, using its existing environment:

```powershell
.work/kernel-venv/Scripts/python.exe -X utf8 -m unittest discover -s lab/explorations/2026-11-01-sat-pilot -p test_sat.py -v
.work/kernel-venv/Scripts/python.exe -X utf8 lab/explorations/2026-11-01-sat-pilot/sat_driver.py status
```

`test_analysis.py` additionally checks rejection of corrupted copies of an existing local trace. It never changes the originals or loads a subject. Without those local originals it is explicitly skipped.

This v1 computation is finished. Do not restart its students. The historical `awaiting-analysis` status records the completed computational boundary; `publication/completion.json` records final delivery.

The registered one-time execution order is `prepare`, `apparatus`, review the hash-bound apparatus receipt, then `run`, all through `sat_driver.py`. Never repeat `prepare` or `apparatus` on an existing workspace. `run` refuses unresolved STOP/in-flight and already-computed states. A new independent replication requires a separately registered directory and new preregistered seeds/materials; repeating the same seeds is deterministic reproduction, not additional N; changing the source of an already frozen study is rejected. The runner does not automatically retire a resource STOP or recover an orphaned in-flight unit.

After computation, `analyze.py --work <directory>` replays stored arithmetic and random choices without importing or instantiating the Core. If a frozen analysis already exists, it returns that result explicitly without a new replay. `publish.py --work <directory> --review <review.json>` registers reviewed bilingual reports, reads all four protocol/report documents back, downloads the entire original archive, verifies every member and only then finalizes the same research record. Publication has its own idempotent namespace and completion receipt; it never reruns a student.

The executed test materials contain reference solutions for independent scoring. `Subject.query` accepts only a four-valued anonymous category; neither the Core nor its fixed port decoder reads an oracle, problem identifier or formula. The declared external search scaffold computes break counts and selects unsatisfied clauses. That division of work is part of the result, not an unreported shortcut.

[2026-11-01 G3比较范围补注 / Comparison-scope addendum](scope-note.md) — 原评分与首版报告不变 / Scores and first edition unchanged.

2026-11-01 later: [dated training-procedure correction](../2026-11-01-sat-curriculum/v1-procedure-correction.zh.md) and [new independent compliant v2](../2026-11-01-sat-curriculum/report.zh.md). Original v1 scores and archive unchanged; its completed record carries the bilingual correction.
