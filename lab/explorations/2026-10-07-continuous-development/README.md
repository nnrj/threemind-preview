# E62 continuous-development operations

Run from the repository root with `.work/kernel-venv/Scripts/python.exe`. These commands use a dedicated local research project; they do not modify old studies or launch services. Run only one simulation worker. `usage.json` requires a fresh, actually queried account percentage at least every30 minutes.

```powershell
& '.work/kernel-venv/Scripts/python.exe' lab/explorations/2026-10-07-continuous-development/experiment.py develop --seed 223 --group direct
& '.work/kernel-venv/Scripts/python.exe' lab/explorations/2026-10-07-continuous-development/experiment.py evaluate --seed 223 --group direct --mode normal
```

`direct` begins at the complete blank birth and skips unsupervised preschool, **not motor teaching/calibration**. `explore`/`quiet` prepend30 simulated seconds. The same individual's weights, Adam, replay, RNG, Core, body and recent activity persist. Teacher assistance is recorded independently of own motor output.

For an interrupted newly checkpointed run, pass an actual complete checkpoint directory containing `complete.json` and `curriculum.json`:

```powershell
& '.work/kernel-venv/Scripts/python.exe' lab/explorations/2026-10-07-continuous-development/experiment.py develop --seed 223 --group direct --resume-from '.work/continuous-development-20261007/cases/s223-direct-aligned/teaching-look-0'
```

This example applies only if that checkpoint exists. Resume writes a new `...-resume-teaching-look-0` case, does not overwrite the interrupted process, and repeats only the unsaved tail. Use `evaluate --source-case` to explicitly evaluate a completed resume case. Never restore a Core-only file as an intact organism.

```powershell
& '.work/kernel-venv/Scripts/python.exe' lab/explorations/2026-10-07-continuous-development/experiment.py evaluate --seed 223 --group direct --checkpoint before-teaching --mode normal
& '.work/kernel-venv/Scripts/python.exe' lab/explorations/2026-10-07-continuous-development/experiment.py evaluate --seed 223 --group direct --mode silence
& '.work/kernel-venv/Scripts/python.exe' lab/explorations/2026-10-07-continuous-development/experiment.py evaluate --seed 223 --group direct --mode rescue
& '.work/kernel-venv/Scripts/python.exe' lab/explorations/2026-10-07-continuous-development/experiment.py correct --seed 223 --group direct
& '.work/kernel-venv/Scripts/python.exe' lab/explorations/2026-10-07-continuous-development/experiment.py evaluate --seed 223 --group direct --after-correction --mode normal
```

Execute those optional conditions only when relevant and within the registered budget. Corrective teaching continues the original taught system; evaluation/ablation copies do not write back into development. Model replacement, changing mappings, or independent refitting is not an implicit calibration command.

The reusable Python interfaces are `DevelopmentalSession.step/save/restore`, `DevelopmentalMotor.teach`, and `DevelopmentalWorld.execute_pose`. The complete-system schema is`threemind.developmental-system/2`. Old`/1` training snapshots cannot silently resume with corrected supervision timing; an untrained`/1` birth can be restored. No kernel version is changed.

Read-only calibration diagnostics (only retained supervised examples, **not** behavioral success):

```powershell
& '.work/kernel-venv/Scripts/python.exe' -m lab.tools.developmental_inspect '.work/continuous-development-20261007/cases/s223-direct-aligned/system/motor' --output '.work/continuous-development-20261007/motor-calibration.json'
```

This does not fit weights or advance Core. It separates “can the reader reproduce its supervision?” from “can the complete organism act independently?”.

Add `--examples-from <earlier-or-later-motor-directory>` to read a fixed teacher cache from another stage of the **same** individual. Identity and mapping must match. This isolates changed translation on unchanged activity records from changes caused by rerunning Core. It still does not measure independent behavioral success; do not import the cache into the organism or change its optimizer.

[Recovered historical workflow](recovered-workflow.en.md) · [Chinese](recovered-workflow.zh.md) · [Registration](design.zh.md) · [Resource interruption](resource-interruption.md)
