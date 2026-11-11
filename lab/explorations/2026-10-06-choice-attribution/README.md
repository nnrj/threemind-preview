# E57 choice attribution

Use `.work/kernel-venv/Scripts/python.exe` from the repository. All runs use a
new project and `.work/choice-attribution-20261006`. E56 is read-only input.

```text
lab/explorations/2026-10-06-choice-attribution/experiment.py prepare
lab/explorations/2026-10-06-choice-attribution/experiment.py baselines
lab/explorations/2026-10-06-choice-attribution/experiment.py history --seed 223
lab/explorations/2026-10-06-choice-attribution/experiment.py history --seed 279
```

The actual sequential execution is recorded in `execution-notes.md`: A,
source223 B, C/D, selective223 controls, E diagnostic, F real-state controls,
then source279 B with the preregistered weather variation. Supplement commands:

```text
lab/explorations/2026-10-06-choice-attribution/controls.py --seed 223
lab/explorations/2026-10-06-choice-attribution/absent_activity.py
lab/explorations/2026-10-06-choice-attribution/practice_dose.py
lab/explorations/2026-10-06-choice-attribution/reader_sensitivity.py
lab/explorations/2026-10-06-choice-attribution/marker_state.py
lab/explorations/2026-10-06-choice-attribution/audit_inputs.py
lab/explorations/2026-10-06-choice-attribution/analyze.py --save
lab/explorations/2026-10-06-choice-attribution/publish.py
```

Run the sensitivity diagnostic again after source279 (completed223 is skipped).
Audit and final-result files are created once and refuse overwrites. Publish only
after the bilingual reports exist. Do not rerun simulations just to republish.

Prepare once. Other commands skip completed cases but refuse incomplete-case
overwrites. `STOP` in the new work folder stops at a guard boundary. Refresh
`usage.json` with actual account usage at least every30minutes. Do not change
the registered budgets silently. No user service restart or Docker is needed.

The direct-stimulus control uses the same channel layout and model capacity,
with zero padding for fields that are not defined for stimuli. It does not
generate or replace Core observations. No scaling by test examples, no
unprompted subtraction, no test answer in inference.

The new teaching has one reader across conflicting histories, current physical
inputs checked equal, and fixed-reader Core-only correction. It measures
selection, not new continuous arm-control learning. See bilingual designs for
criteria and the difference between sources, clones and independent trials.
