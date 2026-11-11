# Robot tasks: configure, run and observe

[中文](../zh/robotics.md) · [Plan](plans/robotics-and-language.md)

Engineering protocols: `threemind.robot-task/1` for custom tasks and `/2` for official Playground tasks. Executable interfaces do not imply learned task performance. Each consciousness keeps its selected kernel identity.

## Interface

Open Worlds and Bodies → Robot Tasks. Select the custom arm/mobile body or installed G1, PiPER or SO-101 assets. Edit mechanics, control, measurable targets, sensor scales and physics periods; validate/preview, save a version, then create a consciousness. Graphic and JSON configuration share validation.

The custom arm has three rotary joints and a gripper. It senses joints, inertia and contact, plus an optional ideal optical bearing/range beacon measured in the endpoint frame within a configured range. Occlusion is not modelled. Task scores are not Core rewards.

Torque is default; position/velocity use explicitly external servo controllers. The only current skill is a scripted joint sweep, **not a trained grasping or walking policy**. Existing anonymous fixed output wiring is a declared baseline, not an emergent motor area. Continuous-joint position control uses a configured span around the initial position, not the large mechanical guard range.

SO-101 defaults to position servo and also offers ideal simulated torque. Selecting it sets `control.actuator_variant=ideal-torque`; protocol, evidence and snapshots retain that choice. Mechanics and force limits remain, but the physical servo firmware is not claimed to support raw torque. All real-model simulations need separate hardware calibration and validation.

Pause, step one sensory period or resume. Manual interventions provide world-frame forces/torques (N/Nm), normalized actuator commands in lexicographic actuator-ID order, release, full checkpoint requests and world-only reset. Pausing does not consume simulated intervention duration. Reset preserves the brain and admitted/in-flight input; it does not revive a dead instance.

Desktop shows world/configuration side by side; narrow screens switch Scene / Configuration / Sensors and Actions. Camera motion is observation-only. Raw measurements, actions and scores remain visible. Existing consciousness research tools supply checkpoint browsing and branching.

## Standalone and Agent operations

With the Runtime `world` extra, neither Lab nor PostgreSQL is required:

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
& $py -m threemind_runtime.robot_cli template custom-arm-reach --output arm.json
& $py -m threemind_runtime.robot_cli run --task arm.json --store arm.sqlite --until-us 1000000 --evidence arm-first.jsonl
& $py -m threemind_runtime.robot_cli run --store arm.sqlite --resume --until-us 2000000 --evidence arm-next.jsonl
```

SQLite retains exact Core and world continuation, integration state, sensory deadline and pending input. `--model` imports a brain; `--export` exports a brain model, **not complete robot continuation**. Output files use exclusive creation. `--action` is an explicit normalized external-action control, not credited to Core. Wall-time/evidence budgets stop execution; death is not silently reversed.

Install public assets explicitly, with pinned revision, size, Git hashes and licenses:

```powershell
& $py -m threemind_runtime.robot_cli assets install so101
& $py -m threemind_runtime.robot_cli template so101 --output so101.json
```

Cache defaults to `.work/robot-assets-cache`; `THREEMIND_ROBOT_ASSETS` overrides it. Loading/preview never downloads. The shared REST operation catalog exposes `robot.catalogue`, `robot.validate`, `robot.asset_template`, `world.observe`, `world.protocol` and existing creation/command/research/snapshot/branch operations to CLI and MCP. `robot_control` takes `force`, `actuators`, `release` or `reset_world`, with the same protocol validation. Frozen studies reject unregistered interventions.

## Acceptance and remaining scope

Engineering checks cover custom arm/mobile control modes, real-asset loading, SO-101 ideal torque selection, sensors/metrics, non-mutating observation, exact continuation, both Core backends and historical kernel identity. 1440/390-pixel browser acceptance exercises configuration, save, creation, intervention, stepping and checkpoint request; historical world regressions are retained.

Playground reference tasks, actual hardware links, manufacturing URDF/CAD and learned robot performance remain separate deliverables. The custom worlds are not renamed public benchmarks. Working interfaces do not mean learned grasping, navigation or walking.

## 2026-10-02 delivery addendum: official Playground task

The earlier pending status above describes that earlier phase. Official **PandaPickCube** is now integrated. Select it under Worlds and Bodies → Robot tasks → Robot template, configure sensors/backend, validate, then save or create a consciousness. A Windows UI requires no JAX installation: after a capable Linux worker saves its checkpoint, the same geometry, poses, measurements, actions and scores are available. Configuration was tested at 1440 and 390 pixels.

This is a separate `threemind.robot-task/2`, not a renamed custom torque task. Source is pinned to `ef4fefc13033c0468af4ef651847f5348af0c7d7`, Menagerie to `1b86ece576591213e2b666ebf59508454200ca97`; sources and all 79 Panda files are verified. Loading never downloads. The upstream incremental position servos, 5 ms physics, 20 ms actions, 150-step episode and reward function remain intact. Actual acceptance used **JAX/CPU**, explicitly distinct from upstream's default Warp implementation; no bitwise backend equivalence is claimed. JAX/CUDA and Warp/CUDA have explicit configuration/capability matching but no GPU task acceptance in this delivery. The CPU image does not advertise a GPU it lacks.

Default input uses joint position/velocity, contacts and optional local ideal optical beacons without occlusion. An explicit privileged option exposes the official state vector, including global information. Neither mode supplies reward, termination flags or correct actions to Core. Fixed anonymous output projection has configurable gain. Scores may drive external selection; they do not demonstrate learned ability. Episode termination pauses the experiment, not the consciousness's life. World reset is explicit and retains Core's clock and experience; dead consciousnesses are not revived.

Snapshots contain the complete official array tree, random state, control/sensory timing, Core, pending inputs, dependency and backend identities. Mismatched continuations are rejected. Initial display poses are computed on a separate observer copy without modifying upstream reset state. Meshes use bounded compressed payloads with SHA-256; the API displays them without reconstructing physics. This Panda scene is approximately 26.1 MiB as JSON and 4.24 MiB as a saved carrier. Long trials still need checkpoint/evidence budgets; cross-checkpoint scene deduplication remains future work.

### Docker Desktop with an existing workstation

No CUDA reinstall is needed for this CPU image. Ordinary Windows workers can keep their existing tasks. Update the code environment and database first; start the dedicated worker explicitly. Acceptance did not start or take over user workstation services.

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
docker build --target lab -f deploy/Dockerfile -t threemind-lab:local .
docker build -f deploy/Dockerfile.playground -t threemind-playground:local .
& $py -m threemind_lab.cli migrate
& $py scripts/playground-worker.py --check
& $py scripts/playground-worker.py
```

The launcher passes only the application database connection, without mounting `.env`, admin credentials, source or Docker socket. Localhost becomes `host.docker.internal`; the existing port is retained (5433 on this workstation). `--database-host` overrides the reachable host. `--check` verifies sources, CPU and database schema without claiming jobs. If PostgreSQL rejects the container address, configure that database's network access rather than treating it as a model failure. `--task-family playground` prevents claiming ordinary consciousness jobs. Defaults are 6 GiB, 2 CPUs and a read-only root. First-task compilation is reused within the worker and does not advance simulation time.

Standalone operations remain `python -m threemind_runtime.robot_cli`, template `playground-panda`, and `run --store ... --resume` for complete continuation. API/MCP reuse robot/world, advance and snapshot operations. Historical `/1` protocols and hashes are unchanged.

### Actual acceptance and limits

An offline container verified official reset/step, non-mutating observation and exact world/Core continuation. The actual API → database → Linux worker ran all 150 steps, paused at the boundary, refused implicit restart, reset only the world, stepped again and served the scene without rebuilding physics. The complete-episode Core hash was unchanged by the initial-display fix and compressed scene representation. Native robot/API/CLI, dedicated routing and both UI widths were separately checked. The workstation database is now at schema 57; the container launcher's `--check` also connected to the actual existing PostgreSQL database without claiming jobs. [Validation summary](../benchmarks/2026-10-02-playground-validation.json)

The first integration attempt hit the disposable database's 256 MiB memory limit and is recorded as a failure. After giving that test database 1 GiB and compressing scene data, acceptance passed. Existing research data was unaffected. These are engineering checks, not extra E26 samples or learned-grasping results; physical robot transfer remains unverified. References: [pinned source](https://github.com/google-deepmind/mujoco_playground/tree/ef4fefc13033c0468af4ef651847f5348af0c7d7), [JAX installation](https://docs.jax.dev/en/latest/installation.html).
