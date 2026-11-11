# Memory, sequence, transfer and adaptation study

The commands call the same public Core, Runtime and Lab interfaces used by the platform. No Core dynamics source is changed. Designs, amendments and reports are bilingual; full observations and checkpoints are stored in the independent study project and evidence archive. GUI users can open the project in **实验笔记 / 记录与报告**.

## Read the completed study

- `design.zh.md` / `design.en.md`: initial prospective design.
- `analysis-registration.md`: common sequence reference and analysis details.
- `memory-intervention-registration.md`: post-discovery silencing/restoration controls.
- `body-removal-registration.md`: all proprioceptive channels removed, ordinary preset only.
- `transfer-trace-registration.md`: eight passive replays of the reversed transfer response.
- `report.zh.md` / `report.en.md`: results, limits and next steps.
- `delivery.zh.md` / `delivery.en.md`: verified platform IDs and resource accounting.

## CLI and reproducibility

Use the configured local database and native extension described in the project setup guide. From the repository root in PowerShell:

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
$study = 'lab/explorations/2026-09-30-memory-transfer'
$env:PYTHONUTF8 = '1'

# Read-only reanalysis. Choose an output name that does not already exist.
& $py "$study/analyze.py" --name independent-reanalysis
```

For a **new reproduction**, use a new `.work` subdirectory. Do not reuse an old project or remove its `STOP` file. Enter the actual current account usage as the starting percentage; resource guards remain in force.

```powershell
$env:THREEMIND_MEMORY_STUDY_DIR = '.work/memory-transfer-reproduction-01'
$env:THREEMIND_MEMORY_USAGE_START = '70' # Example only: replace with the actual current used percentage.
& $py "$study/experiment.py" prepare
& $py "$study/experiment.py" calibrate
& $py "$study/register_calibration.py"
& $py "$study/register_details.py"
& $py "$study/register_body.py"
& $py "$study/verify_memory.py" --register-only
& $py "$study/trace_transfer.py" --register-only
& $py "$study/experiment.py" memory
& $py "$study/experiment.py" sequence
& $py "$study/experiment.py" transfer
& $py "$study/verify_memory.py"
& $py "$study/trace_transfer.py"
& $py "$study/experiment.py" adaptation
& $py "$study/experiment.py" without_body
& $py "$study/analyze.py" --name analysis-final
```

Run stages sequentially and stop on any error. The original run deliberately registered its two discovery follow-ups after observing the first results; a fresh reproduction may prospectively include them all. `--seed 930101` (repeatable flag) selects a registered seed subset for staged execution. Completed cases are loaded, not overwritten; completed-stage receipts are immutable too, so do not rerun an entire already-completed stage merely to check progress. A `STOP` file blocks new simulations but not read-only analysis.

`trace_transfer.py` attaches passive recording after an existing observation callback. It does not add stepping boundaries; every replay must match the original final full Core-state hash. `verify_memory.py` uses explicit reversible interventions, records selected edges and preserves the source snapshots.

The initial evidence scanner read all previous files before each fork. Later stages keep single-worker admission counts in memory and refresh storage totals every 30 seconds. Counts, wall time, host memory, free disk and usage admission checks still run; the 1 GiB reserve covers publication. The complete process-start runner bundle is authoritative provenance. Early single-file shorthand hashes could reflect later file edits and are listed in the audit; their frozen bundles and Core identities remain available.

In the probe helper, `probe_intensity` describes only an **additional anonymous cue** after any physical episode. A value of zero in transfer cases means no extra cue, not zero physical input. The physical intensity is 0.3 in this study, with every actual value saved in its stimulus-unit payload and the calibration receipt. Later helper versions explicitly include this scope label.

Default evidence path: `.work/memory-transfer-20260930`. It is intentionally excluded from Git. The project database and verified archive hold the evidence; repository commits hold the protocols, tools and bilingual reports. No paid AI provider or GPU is used by this study.

## Evidence export and publication

After analysis, `audit.py` verifies all saved checkpoints and sets `STOP`. `export_inputs.py` then uses the public streaming input exporter to produce every envelope and delivery frame; its manifest must cover every case before `publish.py` accepts the archive. This phase is read-only for inputs and does not simulate further.

PostgreSQL JSONB does not retain a floating zero's sign. If exported payload metadata no longer matches its pre-storage hash, the exporter may recover only signed zeros from the already recorded physical measurements. The recovered payload must match the original hash exactly, and all changes must be inside measurement metadata. Separate `inputs-original-payloads.jsonl.gz` sidecars record the recovered payload, both hashes, changed paths and provenance; the database export itself is never rewritten. Any other mismatch aborts publication. `inputs-export.json` lists compressed file hashes and complete input counts.

`verify_export.py` also reconstructs every input using the existing stimulus-unit or anonymous-frame decoder and compares it with the actual delivered channels, intensities and timestamps. It rechecks all recovered original payload hashes from disk without creating a Core instance. Publication requires this receipt too.

`figures.py` creates PNG/SVG figures. `publish.py` writes bilingual reports and records to this study project, verifies the archive before upload and again after database readback, and creates `delivery.json`. It refuses to execute another project's queued work. A new reproduction needs its own result narrative and count checks before publication; do not reuse the original report as a report of new results.
