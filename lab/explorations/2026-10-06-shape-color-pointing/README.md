# E54 — Shape, colour and pointing

[中文设计](design.zh.md) · [English design](design.en.md) · [执行补充 / Amendments](execution-notes.md)

Completed first study: [中文报告](report.zh.md) · [English report](report.en.md). Measurements are in `results.json`; database document/artifact identities and storage accounting are in `delivery.json`.

The study never changes Core or old instances. New evidence lives in `.work/shape-color-20261006` and its independently registered research project. Existing case directories are immutable to the runner; an interrupted case requires review and an explicit new case identity, not silent rerunning over its evidence.

From the repository root, use the project Python:

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
$study = 'lab/explorations/2026-10-06-shape-color-pointing/experiment.py'
& $py $study --help
```

Commands are `prepare`, `motor`, `motor-test --mode normal|zero|shuffled`, `teach --seed 223 [--frozen]`, `collect`, `fit`, `reference [--corrected]`, `correct [--frozen]`, `goal-train`, `goal-test --mode normal|zero|wrong-request|silence`, and `imitate`. `collect --intervention silence|rescue` and `score` reuse the same frozen expression head. They are explicit research interventions, not runtime defaults. `correct` adds the registered external reader calibration; it does not reteach the Core. Prepared work already exists: do not run `prepare` again. Refresh the study's `usage.json` from an actual account reading before a run; never invent a lower figure to bypass the budget. Creating `STOP` in the work directory halts new advancement at the guard.

Reusable tools:

- `lab.tools.shape_color_world`: four geometric objects, RGB/depth sensing, a damped two-axis pointer; versioned state/restore.
- `lab.tools.imitation_world`: distinct teacher/self channels; no mirrored channel IDs or direction labels in stimuli.
- `lab.tools.activity_controller`: a small Transformer accepting raw activity sequences; separate external training targets; safe tensor checkpoints and CPU/GPU execution. It can learn the task itself, so performance must be interpreted with controls.
- `replay.py`: packages already-recorded scenes, physical sensing, outputs and pointer paths; no inference or new Core activity. HTML can be viewed through a research artifact and supports frame seeking/screenshots.
- `sensor_check.py`: offline depth-template identifiability calibration with a known optical slot. It bypasses Core, is not a model answer, and never supplies its classifications as stimuli.
- `summarize.py` and `publish.py`: summarise immutable cases and save the new reports/artifacts through the research services. Publication never claims or executes unrelated jobs.

The language head has eight words, not an unrestricted language model. The pointer is an experimental plane carriage, not a deployed robot arm. Teacher-guided movement, visible-marker following, language-directed choice and internally generated intention are different assays.

Run affected tests with `python -m pytest tests/test_shape_color_world.py tests/test_raw_activity_stream.py`. No whole-database scan, repetitive evidence hashing or user-service restart is required.
