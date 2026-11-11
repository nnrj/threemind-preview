# Process readout calibration — 2026-09-30

[中文报告](report.zh.md) · [English report](report.en.md) · [Tool guide](../../../docs/zh/v2-observation-tools.md)

Source: `.work/memory-transfer-20260930/cases/` from the completed memory/transfer study. Never modifies source files or restarts its training. Output: `.work/process-readout-calibration-20260930/`. Scripts reject existing evidence outputs; choose a **new** `DEST` if deliberately rerunning rather than deleting previous evidence.

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
& $py lab/validations/2026-09-30-process-readouts/calibrate.py
& $py lab/validations/2026-09-30-process-readouts/compare_controls.py
& $py lab/validations/2026-09-30-process-readouts/figures.py
```

`calibrate.py` extracts old activity windows, derives process measurements through the shared library, and checks source hashes again. It allows at most 2,000 windows, 120 wall seconds and 256 MiB generated JSON. `compare_controls.py` uses the shared comparison on the bounded 96-control set, capped at 64 MiB output. Neither script advances Core. `figures.py` plots an actual old sample sequence without smoothing or new simulation.

| Evidence | Bytes | SHA-256 |
|---|---:|---|
| `calibration.json` | 3,794,583 | `b698274bf0e8b72e8ae17954b1e6cb2cb2f4806b922f9b480b95f8d19813399b` |
| `controlled-comparisons.json` | 1,097,442 | `e3a2a06600607ce74a4f667ac46b118f709220390b6a7c66be86d9fe39920863` |

The tracked `summary.json` preserves counts and evidence hashes. Full per-window results and the source checksum manifest remain in the new local evidence directory; they are not duplicated into Git. The original experiment report and database project remain unchanged.
