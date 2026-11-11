# 003 — Independent Control-Experiment Module Plan

[中文](../zh/003_对照组实验模块计划.md) | [English](003_control-experiment-module-plan.md)

## Goal

Add a Control Experiments page to the experiment workbench for common-input, common-metric comparisons between ThreeMind and established network families. Baselines must be independent packages or submodules that neither import nor modify ThreeMind Core. A host orchestrator handles lifecycle, stimulus broadcast, sampling, display, and statistics only.

## Page concept

- Split the central area into experimental arms: one ThreeMind arm and one or more baselines, each with independent state, topology/activity view, and resource measures.
- Use one right-hand protocol panel for starting state, stimulus sequence, framing, strength, background, seeds, trial count, and windows.
- A common timeline supports synchronized run, pause, single-tick, annotation, and evidence freezing.
- A lower or separate tab presents curves, difference plots, response clusters, forgetting/interference curves, and exports.
- Mark unsupported capabilities explicitly; do not add ThreeMind mechanisms to a baseline merely to manufacture fairness.

## Minimal protocol boundary

Each arm adapter implements, in its own namespace:

1. `create/reset` from explicit configuration and seed;
2. `accept(frame)` for the same non-semantic stimulus frame, or a declaration that no equivalent exists;
3. `tick(n)` to advance its dynamics;
4. `observe()` for common unit/node, connection, activity, and structural summaries;
5. `snapshot/restore` when supported;
6. `capabilities()` for plasticity, forgetting, inhibition, space, cloning, and related features.

This is an experiment-host protocol, not a reverse dependency added to ThreeMind Core.

## Candidate arms

1. A size-matched random recurrent graph, with no plasticity or matched decay, as a structural null.
2. A standard Hebbian recurrent network with matched units, framing, and decay.
3. A classical Hopfield network for energy convergence and error correction of stored patterns.
4. An echo-state/reservoir network for fixed recurrent dynamics plus a trained readout.
5. An STDP network for precise pre/post timing-dependent plasticity.
6. A Wilson–Cowan or simplified excitatory–inhibitory population model for oscillation, stable states, and inhibition.
7. Transformer/modern-Hopfield arms only for their different questions—global attention or pattern retrieval—not as an unfair consciousness ranking under mismatched scale and training.

## Fairness and audit

- Where meaningful, match unit/state dimension, input bandwidth, total ticks, seeds, and compute budget; report impossible matches explicitly.
- The orchestrator duplicates one stimulus frame; no arm can inspect another arm's internals.
- Shared metrics consume standard observations while raw arm-specific data remain available.
- Repeat across independent initial states and report uncertainty; do not conclude from one canvas comparison.
- Archive baseline implementation, version, parameters, and source paper with the experiment package.

## Stages

Stage 1: protocol, two-arm split view, random recurrent graph, and Hebbian baseline. Stage 2: Hopfield, reservoir, STDP, and common analytics. Stage 3: population models, Transformer-like controls, and batch scheduling only after the basic comparison is validated.
