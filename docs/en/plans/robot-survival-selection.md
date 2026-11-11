# Finite-energy robot selection and survivor reproduction

[中文](../../zh/plans/robot-survival-selection.md) · [Research progress](research-backlog.md) · [E27 registration](../../../lab/explorations/2026-10-02-survival-transfer/design.en.md)

Recorded 2026-10-03. This page preserves decisions and tool boundaries. E27 results are reported separately; later tools do not rewrite earlier samples.

## Change from the previous selection experiment

E26 developed candidates for only seconds and selected them using target distance in independently born evaluation copies. The user requested longer selection during operation: finite initial energy, replenishment from actual physical task completion, starvation through existing Core dynamics, then reproduction of survivors. At the observation horizon, remaining energy chooses parents. A living individual not selected is preserved, not falsely recorded as dead.

The primary task must grasp a free cup and pour its grains into another cup. Vision, touch, joint and inertial measurements are permitted; object names, correct actions and task answers are not delivered to Core. An attached-cup secondary task is allowed only after the primary shows no effect. Rigid grains are not liquid; fluid and glass-fracture simulation remain future work. No energy theft between individuals is introduced.

## Energy and lifecycle

Core energy has experimental units. Absolute actuator mechanical work is recorded separately in joules and is not deducted from the Core balance a second time. Birth energy is supplied by the experimental environment. Actual completed units create food credit, delivered on a fixed schedule through the existing `supply_energy` port. Offered and accepted energy remain separate when capacity limits acceptance.

An empty reserve does not clear activation. Existing affordability, decay and lifecycle rules determine death. Never activated, depleted, task failure, censored observation, technical failure and Core death are distinct outcomes. Grasp/lift observations alone do not earn food. Each grain can be paid once per batch after 200 ms inside the receiver; this is a physical task-meter rule, not a consciousness-convergence rule.

Restocking is an explicit external intervention and does not reset robot or Core. No candidate receives ad hoc rescue food. Reproduction uses existing `birth/1`: inherited structure, cleared immediate activity, equal initial energy for offspring. The experiment does not charge birth energy to parents and is not claimed to be a closed energy-conserving ecosystem. No eligible survivor ends the lineage. Living nonparents retain snapshots; resource stops are not labeled starvation.

## Apparatus and frozen numbers

The pinned Menagerie Panda retains three-dimensional mechanics, coupled gripper, gravity, inertia, friction and contact. Candidates use raw torques without IK, action scripts or automatic grasping. A separate engineering controller first proves physical feasibility; it never demonstrates actions to candidates and its score is not a ThreeMind learning result.

Physics steps are 2 ms, actions/nonvisual senses 20 ms, camera samples 100 ms. Vision is a fixed luminance conversion of actual 16×12 renderings with raw values retained. It has no detector/semantic labels and is a low-resolution research sensor, not a claim of real-robot visual precision. Measured remaining energy is an interoceptive input. Live CPU/host telemetry is off.

Initial reserve 40300, capacity 161200, energy per qualifying grain 10100, settlement every 1 second, restock every 30 seconds. The last 10 seconds of a 30-second engineering calibration measured 167.589854 units/second: approximately 240 seconds of initial reserve and 60 seconds per grain, without guaranteeing any individual's lifetime.

Each candidate has a 600 simulated-second observation horizon. Start with 16, extend to 32 only if budgets permit; at most two descendant generations. The attached-cup secondary has 8 founders. The execution amendment allows at most three independent processes with 4 GiB combined memory; their wall durations add toward the four-hour compute budget. Inputs, seeds, raw measurements, actions, energy, Core/physical states and lineages are retained. [Design](../../../lab/explorations/2026-10-02-survival-transfer/design.en.md) · [Execution amendment](../../../lab/explorations/2026-10-02-survival-transfer/execution-amendment.en.md)

## Reusable research tools

These are development/research tools. Neither independent Runtime nor historical Core dynamics change. Python uses `lab.tools.granular_session.SurvivalSession`; the CLI shares its protocol validation. Evidence directories must be new.

From the project root:

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
& $py -m threemind_runtime.playground_assets install
& $py -m lab.tools.granular_survival template --output .work/my-survival.json
& $py -m lab.tools.granular_survival validate .work/my-survival.json
& $py -m lab.tools.granular_survival run --protocol .work/my-survival.json --seconds 600 --output .work/my-individual
```

E27 was verified with MuJoCo 3.14.0; exact physical restoration requires the recorded version and pinned assets, not an arbitrary simulator upgrade. Assets are installed explicitly, never downloaded during execution. Already verified assets are reused. `template` does not simulate; `run` does. `schema` exports the configuration schema. `core` uses existing kernel parameters; `world` controls physics/sampling periods, image size, force limits, projection gain, restocking, seeds and attached/free cup. `energy_per_grain` and `food_interval_us` control food. Attached and free-cup task success rates must remain separate.

```powershell
& $py -m lab.tools.granular_survival run --protocol .work/my-survival.json --seconds 60 --resume .work/my-individual --output .work/my-continuation
& $py -m lab.tools.granular_survival select .work/individual-a .work/individual-b --parents 1 --offspring 4 --output .work/selection.json
& $py -m lab.tools.granular_survival run --protocol .work/my-survival.json --seconds 600 --birth-from .work/individual-a --output .work/child-a
```

`select` reads actual saved lifecycle/energy and horizon completion; failed or censored cases are ineligible. It creates a plan without deleting or starting individuals. `--birth-from` requires an active uncensored horizon survivor and preserves the parent. `--resume` continues the same individual. Ctrl+C requests saving after the current physics/Core step; `--stop-file` also pauses safely. Technical failures are marked separately and do not imply verified resumability.

`lab.tools.survival.TaskFood` generalizes timed task-food accounting with retry deduplication, balance validation and restoration. `select_survivors` produces a reproduction plan without modifying Core or parents. Other tasks must still provide credible physical measurements and object deduplication.

E27 notes, reports and evidence are published to existing notebook/report modules. Full cohort launch for this new granular task currently uses the research CLI/Python API; complete graphical orchestration in the robot page is not claimed. Future UI integration must share the same protocol and survival semantics, not substitute E26's endpoint ranking for in-operation elimination.

## Replaying evidence

`python -m lab.tools.granular_replay CASE --core-only --output NEW_FOLDER` replays recorded stimuli and food, checking each recorded pre-action activation and the full final Core hash. Without `--core-only`, it replays recorded physical actions and exports a video, a time sequence and verification receipt. The display camera uses an independent MuJoCo data copy.

Strict visual replay is the default. Some long replays produced a few luminance differences of 1/255 while physical measurements remained identical. `--allow-pixel-variation` explicitly permits and reports those rendering differences while retaining exact physical measurement, event and endpoint checks. Such a result is **not exact sensory reproduction**. Original evidence stays unchanged; Core reproducibility uses recorded stimuli rather than newly rendered images. Each replay requires a fresh output folder. Video replay currently starts from birth; arbitrary continuation segments need their initial physical checkpoint and are not claimed as supported.
