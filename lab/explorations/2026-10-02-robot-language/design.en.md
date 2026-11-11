# E26: arm utility and language-adapter attribution — preregistration

Registered 2026-10-02 before execution. New external tools are used without Core changes or edits to historical evidence/defaults.

## Arm

Use the custom-arm/1 reach task with MuJoCo physical properties, contact, limits, gravity and fixed anonymous wiring. Direct torque is primary. Only declared joint, inertial, touch and ideal optical beacon measurements enter Core. Physics is 2 ms and sensory/action sampling 10 ms; Core timing is unchanged.

Initially use two wiring seeds, each with two candidates living six simulated seconds at independent development targets. Evaluate independent birth/1 copies for four seconds in each of two selection environments, selecting the lowest mean final distance. Evaluation activity never changes the parent. Three unseen environments compare blank, the first trained candidate, the selected candidate, the selected candidate with plasticity disabled, random actions, and separately labelled position-servo and fixed external-sweep references. Random actions update every 10 ms within [-1,1]; mechanical work differences are reported rather than claiming matched energy.

Primary outcomes: final distance, improvement from initial distance, and ever entering the 5 cm success radius. Also retain minimum distance, absolute mechanical work, contact, Core activity and every input/action. Two wiring seeds are a small utility pilot. Complete comparable results may be extended to four seeds, at most 108 robot episodes, without changing parameters to obtain success. Null results remain results.

## Language

Compare existing text input with a randomly initialized Transformer sense. Output is a scratch Transformer plus a learned mapping head. Calibrate output using Core processes elicited by four nouns (pine nut, bell, pottery cup, willow leaf, in Chinese), at intensities 0.5 and 1. Freeze conversion before assigning new names. Test independent intensity-0.8 exemplars; fewer than three correctly decoded nouns fails calibration, so later language errors cannot establish absent Core memory.

After conversion is frozen, teach four Chinese naming sentences and a separate reversed mapping. Each sentence initially repeats twelve consecutive times, followed by two shuffled review passes, intensity 1. Preserve normalization, framing, forgetting, inhibition, depletion and novelty defaults. Frozen scratch encodings may be batched only with verification against single-sentence encoding. Observe 500 ms after each sentence, without imposing a lifetime limit.

Probe each of four names at intensity 0.5 from copies of the same taught state. Compare original experience, reversed experience, blank Core, and exchanged, shuffled or constant output features. Strict decoding sees neither questions nor lessons/answers. Transformer-only input is a separately labelled external reference. Retain full trajectories and anonymous projections. Distinguish Core influence on language, experience-dependent Core changes and output following novel associations. None substitutes for the others. Report actual activity even if language conversion fails.

## Evidence and limits

Register a new Lab project and notes before running. Use public standalone Runtime interfaces; retain complete device states and input/action evidence. Do not claim or execute other jobs. One compute task, four cumulative hours, 256 instances, 8 GiB process-tree RAM and 3 GiB VRAM; retain 2 GiB free RAM, 8 GiB C and 30 GiB E. Stop expansion at 8 GiB evidence and stop simulations at 10 GiB. Account baseline 5%; stop expansion at +5 percentage points and new simulation at +8; refresh at least every 30 minutes. Hardware/tool failures, inadequate readout and budget censoring are explicit.

Official Playground tasks, real hardware transfer and open dialogue are outside this batch's conclusions. Docker Desktop currently cannot start; the official JAX/Linux worker acceptance remains incomplete. Existing 3D UI and commands are available; this batch mainly uses their shared Runtime Python interface, with reports, notes and evidence published through Lab services.
