# Practical robotics and bidirectional language adapters

[中文](../../zh/plans/robotics-and-language.md) · [Research progress](research-backlog.md)

Recorded 2026-10-02. Approved for implementation; approval is not evidence of completion.

## Scope and decisions

Assess practical usefulness independently of consciousness or AGI claims. Implement arm tasks first, connect humanoids and mobile robots, then restricted language experiments. Reuse adapters, operation catalog, evidence, snapshots and workers. Preserve Core dynamics, historical identities, data and mappings. Environment scores select externally; they must not write Core edges.

Raw torque is the default. Joint position/velocity servos and existing skill policies are separate modes with explicit parameters and contribution. Unsupported modes fail explicitly. Physical mass, inertia, friction, collision and actuator limits remain. Custom virtual bodies avoid restrictions imposed by commercial motor firmware: a three-joint arm plus one-degree gripper and a differential-drive base, with editable mechanical descriptions for future hardware design, not a claim of manufacturing-ready CAD.

## Simulator and task architecture

MuJoCo is primary; Menagerie assets require pinned versions, hashes and per-model licenses. Playground supplies unchanged reference tasks. robosuite, ManiSkill, Isaac Lab and Webots/ROS 2 remain optional later integrations. Arm tasks progress from reaching/contact/pushing toward grasping. PiPER and SO-101 are optional real models, with SO-101 position servos not relabelled raw torque. G1 and mobile models initially verify loading, sensing, actuation, observation and restore; walking and navigation remain separate learning studies. TurtleBot3 is an optional corresponding real model.

New custom tasks use 2 ms physics and 10 ms action/proprioception, without changing Core propagation. Official tasks retain their timing; modified variants have distinct identities. Existing fixed anonymous activation projection is a declared wiring baseline, not evidence of emergent motor regions. Joint/inertial/contact/range signals enter anonymous ports; visual sensation is optional, human 3D observation available. Hidden truth and scores remain evaluator-only unless explicitly measurable by declared sensors.

The task interface covers load/reset/step/sample/action/observe/snapshot/restore. Resetting a world never silently resets a brain or revives a dead instance. Snapshots include Core, integration, adapters, RNG and pending input. Selection adds task success, time, distance and contact metrics while keeping independently born evaluation copies and held-out environments. Deployment bundles include model, Runtime, mappings, units, control mode and calibration; Runtime remains database-free.

## Language and attribution

Use Transformers and PEFT in isolated compute jobs: Qwen3-Embedding-0.6B for input and Qwen3-0.6B for output. Freeze base models initially and train necessary mapping heads; any LoRA is versioned explicitly, then frozen before formal comparisons. The existing tiny numeric Transformer remains available and is not presented as an NLP model.

Three configurations: Core-only text input/process readout; strict bidirectional conversion with output decoder limited to declared Core activity processes and no lesson/question/answer bypass; and explicit language-knowledge assistance with recorded information exposure. Unreadable activity stays unreadable rather than producing an invented answer. Brief responses do not require an 800 ms hold.

Roadmap: restricted naming/experience/interaction; then infant-style learning with objects, speakers, joint attention, turn-taking, consequences and spaced repetition; eventually inheritable ThreeMind language structures shaped by environments/populations, reducing and removing Transformer assistance. Only the first stage and enabling interfaces are current implementation scope.

## UI and equivalent operations

Robot tasks belong in Worlds & Bodies; curricula, branches, selection and reports reuse Experiments & Training. Add Dialogue Experiments without removing the existing consciousness-side chat. Wide screens show scene/control/readout together; narrow screens use tabs. Normal workflows have forms and equivalent advanced JSON. Camera movement is observation-only; applying force is an explicit intervention with receipt. UI, REST, CLI and MCP invoke the same services.

## Acceptance and bounded studies

Load/run/observe/restore all three body categories, executable examples for control modes, fixed-input observer invariance, pause/step/branch, version rejection, backpressure/errors and 1440/390 layouts. Simulated success does not validate physical transfer.

Arm comparisons: blank, trained, environmentally selected, frozen learning and random action; external controllers separately reported. Measure success, distance improvement, unseen positions, cost and failures. Language mappings/experiences are generated after converter training; compare correct/blank/swapped/shuffled/fixed Core activity and Transformer alone, selective intervention/restoration and removal of assistance. Causal influence from Core and storage of experience in Core are separate claims.

Each initial exploration: at most 4 wall-clock hours and 512 episodes, one compute task, 8 GiB RAM, 3 GiB GPU budget with at least 512 MiB headroom. Evidence: stop expansion at 8 GiB, stop/save at 10 GiB. Preserve RAM 2 GiB, C 8 GiB and E 30 GiB; caches on E. Take a fresh shared quota baseline before simulations: +5 percentage points stop expansion, +8 stop new simulations. Record engineering and experiment budgets separately. Native Windows uses CPU MuJoCo; Playground GPU JAX is a Linux-worker capability, not a cluster requirement.

## Delivery checklist

- [x] D: bilingual decisions, dialogue, history and progress.
- [x] R: versioned robot tasks, custom raw bodies, real assets and reference tasks.
- [x] O: shared execution/observation/snapshots/selection metrics/API/CLI/MCP.
- [x] U: robot/dialogue UI and wide/narrow acceptance.
- [x] E: arm comparisons and stored design/results (E26; reliable utility not established).
- [x] L: language models, protocol and restricted attribution study (E26; calibration passed, new assignments did not).
- [x] V: regression, standalone Runtime, documentation and local commits, no push.

## Dialogue record

Original Chinese excerpts remain in the [Chinese source](../../zh/plans/robotics-and-language.md#对话史料). English translations:

> The purpose is to answer a question: whether or not ThreeMind ultimately demonstrates autonomous consciousness or creates AGI, can it be useful at this stage? This robot environment should offer equivalent CLI, API and UI operations so agent researchers and human researchers can design and perform experiments. Visualization matters for human operation.

> If existing physical robot models cannot satisfy the maximum raw-control requirement, adapt them separately. Simulation can include our own body that meets it, with optional adaptations for real models. I may later try to build the body we need through methods such as 3D printing.

Editorial summary, not verbatim quotation: the user selected all three robot categories with arms evaluated first; raw torque default with optional servo/skill modes; strict language conversion separated from knowledge assistance; temporary Transformer innate-language assistance followed by environmentally selected inheritable ThreeMind language. These are decisions and aspirations, not measured results.

## Primary references

[Playground](https://github.com/google-deepmind/mujoco_playground), [Menagerie](https://github.com/google-deepmind/mujoco_menagerie), [SO-101](https://huggingface.co/docs/lerobot/en/so101), [PiPER control](https://github.com/agilexrobotics/pyAgxArm/blob/master/docs/piper/firmware_reference.md), [JAX platforms](https://docs.jax.dev/en/latest/installation.html), [Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B), [Qwen3 embedding](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B), [PEFT](https://huggingface.co/docs/peft/index). These establish interfaces and candidate capabilities, not ThreeMind's learning or transfer performance.


## 2026-10-02 amendment: distinguish hardware interfaces from simulator choices

User clarification (translation; the Chinese plan retains the original):

> Does rejecting SO-101 raw torque mean it cannot connect at all, or that it is an option rejected by default? I want a choice rather than rejection alone. Please correct any misunderstanding.

SO-101 connects through servo modes. Simulation additionally permits an explicit `control.actuator_variant=ideal-torque` motor replacement, retaining mechanics, inertia and force limits. Default `profile` does not invent a hardware torque interface. The selected variant is recorded in protocol hashes, actions and snapshots; continuation cannot silently switch it. This narrows the earlier unsupported-mode rejection: commercial firmware must not restrict simulation research. Transfer to a physical SO-101 remains unverified; no real device has been connected.


## Engineering progress (2026-10-02)

Robot protocol, standalone exact continuation, task library, API/CLI/MCP, three body categories and initial 1440/390 interaction checks are accepted. Assets include G1/PiPER/SO-101; custom arm/mobile mechanics are editable. Manual controls retain evidence, and SO-101 supports an explicit ideal-torque variant. Historical-world regressions remain; Core dynamics source was not changed. See [operations and remaining scope](../robotics.md). Playground tasks, practical controls, language tools and dialogue UI remain ongoing; R/U/E/L/V as a whole are not yet marked done.


## 2026-10-02 addition: language peripherals from random weights

The user explicitly added a randomly initialized Transformer alongside Qwen, with independent input/output routing. Byte tokens avoid a hidden pretrained tokenizer. Training uses supplied material and creates new versions; comparisons freeze the mapping. Strict decoding receives the measured activity process; assistance may see the input question. See the [language adapter guide and source statement](../language-adapters.md). Core dynamics and peripheral ownership stay unchanged.

## 2026-10-02: public-task delivery after Docker recovery

After the user started Docker, pinned PandaPickCube sources/assets were connected through robot-task/2. CPU physics, complete continuation, 150-step termination, world-only reset and cross-platform scene access were exercised. The dedicated worker only claims Playground jobs. Compressed observer scenes reduce storage overhead. Core and original E26 evidence remain unchanged; engineering acceptance is not learned grasping or CUDA acceptance.

[Playground](../robotics.md)
