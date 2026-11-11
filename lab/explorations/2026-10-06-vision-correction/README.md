# E56 vision and correction

Frozen historical studies are not upgraded. This study uses a new world protocol
and ordinary existing Core stimuli. No dynamics or runtime defaults are changed.

Run with the project's `.work/kernel-venv/Scripts/python.exe` from the repository:

```text
lab/explorations/2026-10-06-vision-correction/optics.py
lab/explorations/2026-10-06-vision-correction/experiment.py prepare
lab/explorations/2026-10-06-vision-correction/experiment.py suite --resolution 4
lab/explorations/2026-10-06-vision-correction/experiment.py foundation --resolution 6
```

`prepare` is once only. A suite skips completed stages and refuses to overwrite
an incomplete stage; it never restarts an old consciousness automatically.
`teach`, `collect`, `fit`, `evaluate` and `correct` expose individual phases.
`foundation` runs only initial teaching, calibration, fitting and formal tests.
The denser-eye correction branches require a fresh measured resource estimate;
do not automatically run a second full suite within the same finite budget.
Use `--source corrected` or `--source exposure` for the two branches, and
`--split calibration|practice|test`. `evaluate --mode zero|silence` uses the same
reader and settings but changes the declared observation or edge intervention.

`analyze.py`, `replay.py` and `publish.py` consume completed records only.
Publication goes through the existing ThreeMind research services; no worker
or user service is started. Account usage in the study's `usage.json` must be
refreshed from actual account readings at least every30minutes. Do not invent
usage values to pass the guard. `STOP` safely prevents further simulation;
partial evidence remains.

The world tool `lab/tools/classroom_eye.py` supports4,6,8,12,16rays per side,
restoration, unchanged body ports and explicit total optical gain. The bounded
Core experiment intentionally exposes only4and6. The sensor-only diagnostic
also checks8. Servo movement executes the externally decoded endpoint; it
does not know the requested answer and is not a claim of newly learned motor
dynamics inside Core.

An exploratory shared-field decoder can be fitted to already recorded examples:

```text
lab/explorations/2026-10-06-vision-correction/shared.py fit --resolution 4 --source corrected
lab/explorations/2026-10-06-vision-correction/shared.py test --resolution 4 --source corrected
```

Existing test scores used to choose this candidate are development results.
`test` uses separately registered scenes in `confirmation-tasks.json`.
No Core input, dynamics, background or requested target is altered by fitting
the external reader. Its own learned skill must not be attributed to Core.

`nolearning.py` runs the matched4×4control with the existing Core `plasticity`
option disabled, retaining physical input, node activation/inhibition and
recovery. It receives the same initial course and exposure scenes, and its own
shared reader receives the same48+12labelled calibration trials/1200steps.
No original-trained reader is unfairly imposed on the control. The command
skips completed stages; it does not erase a partial stage.

To keep both the reader and present physical world fixed while comparing Core
histories at the same simulated time:

```text
lab/explorations/2026-10-06-vision-correction/shared.py test --source corrected --reader-source exposure --world-source exposure
```

This is a declared common-test-world intervention, not uninterrupted natural
teaching. Core state/history is retained; current world state is restored from
the reference source. A different simulation time is rejected. A source's own
reader remains the default when these optional arguments are omitted.

For fixed-reader attribution, `shared.py test --source exposure --mode silence`
blocks existing edges. `--mode rescue` immediately removes the same block on
an independent original-state copy before its query. Zero and shuffled-activity
predictions are recorded in every confirmation result. None is by itself a
general consciousness or language test.

After simulation, `replay.py` creates an interactive record of **all completed
pointing trials**, including incorrect choices and attribution controls. It does
not replace the complete teaching processes preserved in the evidence archive.
The same canvas exposes `classroomReplay.frame(time)` for deterministic export:

```text
node lab/explorations/2026-10-06-vision-correction/check_replay.mjs .work/vision-correction-20261006/replay.html
node tools/export_classroom_replay.mjs --input .work/vision-correction-20261006/replay.html --output .work/vision-correction-20261006/pointing.mp4
```

The MP4 includes every recorded pointing outcome at normal simulation speed,
plus a one-second result hold. It does not rerun Core or regenerate answers.
`circle_audit.py` separately locates the two user-reported E55 moments against
their original video timeline and recorded actuation, after the main study.

`circle_core_disabled.py` then reruns the entire original physical course with
**no Core created**, retaining the initial body, weather and teacher scene
schedule. It saves its independently computed trajectory before loading any
recorded positions for comparison. It never feeds old motion/activity back as
control. This distinguishes Core-off from the earlier structural-learning-off
comparison. It refuses to overwrite its result or trace; the completed516-second
physical-only control took5.20wall seconds and adds1.17MiB.
