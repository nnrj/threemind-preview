# E67 shape/color comparison: /2 and /3.1; /4 deferred

[中文协议](design.zh.md) · [English protocol](design.en.md) · [执行札记](notes.zh.md)

This folder contains source and small research documents. Raw records, complete
subjects, source freezes, delivery receipts and replay media live in the managed
resource `research:e67-shape-color-kernels`, initially at
`E:\ThreeMindData\experiments\2026-10-11-shape-color-kernels`.

Platform project: `7f6d896d-ba85-49fa-a034-9969fb57503f`.
Formal record: `7867ff04-5973-5e66-a438-ae84bfe46174` (`E67`).
Find it in **实验总览**, independently of the current project filter.

Protocol revision3 continues the existing `/2` and `/3.1` subjects. The original
four-arm registration remains: `/4 adaptive-half-life` retains a partial initial
course and its complete checkpoints, while `/4 legacy-stability` was not born.
Both `/4` arms are deferred by the user's choice. Each born subject has its own
learned peripheral. This is a registered
research host using the standard input/output adapters and authenticated record
API. It does not fabricate a Lab worker instance that could only restore Core
without its learned reader and physical world.

## Entry points

Use the project's `.work\kernel-venv\Scripts\python.exe`. The API server must be
available and the ordinary platform credentials/session configured. Do not put
credentials in this folder. Historical raw data and `source-reference*` freezes
must not be edited to satisfy a changed implementation.

```powershell
$study = 'E:\ThreeMindData\experiments\2026-10-11-shape-color-kernels'
$runner = 'lab/explorations/2026-10-11-shape-color-kernels/experiment.py'
# Only if no runner is already active; a cooperative resource lock prevents a second writer.
.\.work\kernel-venv\Scripts\python.exe -u $runner run --work $study
```

The E67 identity is fixed. A genuinely new repeat requires a separately
registered study; do not erase this one's completed phases. The `prepare` and
`amend` and `amend-two` commands have already been executed for E67. `run` verifies its frozen
implementation, skips completed stages and resumes incomplete work from saved
complete sources. A `STOP` file in the study directory requests a host stop;
it is not an input to consciousness. Previously persisted evidence remains.

The October12 continuation uses `pipeline.py`: one independent host process
runs the frozen two-arm simulation, then input auditing, figures, both videos
and original publication. It records `pipeline-status.json`; inspect that and
the existing process/logs before starting anything. The cooperative writer lock
rejects a duplicate writer. The pipeline preserves the already reviewed first
STOP as an evidence file, but refuses to clear any later STOP automatically.
Final report review/publication remains a separate step. Simulation has no chat
session dependency and an exporter failure cannot rerun a completed subject.

`preflight --work <new ignored development directory>` is engineering validation,
not a formal score. It checks kernel identity, complete continuation, the next
learning update and optical scope. The optional empty-scene apparatus is tested
there; no background-only delayed retention phase is part of E67's formal run.

## Read-only analysis and replay

After `computation-complete.json` exists and the runner has exited:

```powershell
.\.work\kernel-venv\Scripts\python.exe lab/explorations/2026-10-11-shape-color-kernels/analyze.py --work $study --audit-inputs
.\.work\kernel-venv\Scripts\python.exe lab/explorations/2026-10-11-shape-color-kernels/figures.py --work $study
.\.work\kernel-venv\Scripts\python.exe lab/explorations/2026-10-11-shape-color-kernels/replay.py --work $study
```

These commands only read measured trajectories and create analysis/media. They
do not rerun the subject. Keep storage migration/cleanup paused while producing
outputs, or wrap the commands in the same `ResearchStorage.writer` cooperative
lock. Two MP4s and all-frame HTML chapters are placed under `replays/`.
Teaching is 8×, calibration sampling 4×, development tests 2× and final questions
1×, with explicitly marked answer holds. Errors are included. Four short cards
per video show saved peripheral-calibration results and unchanged Core time;
these are metadata summaries, not invented activity or test scores.

`publish.py originals` links frozen source bundles, engineering verification,
analysis and replay media. Once the two final reports have been reviewed,
`publish.py reports` saves report/note bodies, validates evidence and finalizes
the formal record. Both require `--work $study`, normal platform authorization,
and the managed resource lock. No route invokes a learning or stimulus action.

Native-call timing, full restoration, observation, peripheral learning and
encoding/I/O are separate. Stage elapsed time excludes its ending API attachment
sync. One question is a branch from a complete source, not an independent
training replicate. The two completed arms share a paired seed and matched curriculum;
inferences beyond this design require further evidence.
