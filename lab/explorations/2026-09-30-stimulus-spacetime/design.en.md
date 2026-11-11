# Stimuli, backgrounds and physical references: preregistration

2026-09-30. Unchanged continuous-memory/2 dynamics, forgetting, inhibition, depletion/recovery, timing and propagation thresholds. Seeds 93001/93002; ordinary defaults versus the 1-second facilitation preset. Independent instances/exact clones; no old projects modified. Planned 260 instances, maximum 384. One worker, 90 simulation wall-clock minutes, RSS 4 GiB, evidence soft/hard limits 3/4 GiB; available RAM ≥2 GiB, C/E free ≥5/15 GiB. Account growth +3 percentage points stops expansion; +5 stops new simulations, including shared usage.

## Backgrounds

Establish a two-channel network using ten ordinary pulses 100 ms apart. Then deliver 48 samples at 100 ms intervals and intensity 0.2: fresh single random channels; fresh two-channel groups; twelve random groups repeated four times; fixed channels with random amplitudes; existing synthetic field; recorded real host telemetry. Preserve correlations and raw telemetry provenance. Input doses are measured, not claimed equal across different source types. Track edge appearance/disappearance, channel reuse, actual dose and cross-links to the original network. Fork a 0.5-intensity cue and a no-cue control; observe for 15 simulated seconds or actual death. Edge lifetimes still open at cutoff are right-censored.

## Intensity and history

Three histories from identical initial conditions: untrained, one two-channel input at intensity 4, ten at intensity 1. All history windows are one simulated second. Fork cues at 0.2/1/4 and no-cue controls, observing five seconds. Separate equal-drive controls compare amplitude 1 × intensity 1 against amplitude 0.25 × intensity 4. Record received drive, activation increments and extra consolidation without asserting physical equivalence of their formulas.

## Physical references

Record four seconds each of an inertial cart and gravity pendulum, including initial/final physical state and raw measurements; replay twice for eight-second training. Physics step 5 ms, sensing 20 ms, unchanged Core cadence. Conditions: complete joint observation; remove accelerometer/gyroscope; split each group into independent elements; shuffle samples with a fixed seed; no training. Complete/split/shuffled conditions preserve per-channel total dose, sample timestamps and observation duration. Removing proprioception intentionally removes its dose while other senses stay identical; no replacement noise or scaling. Fork a shared joint-position cue (recorded amplitude, intensity 0.5) and no-cue control for five-second observations. Labels, coordinates, absolute time and answers never reach Core.

## Analysis and stopping

Primary outcome: descending activation at the activity reader's **pattern-convergence decision**. Preserve legacy stable-convergence results and full sampled trajectories. Periodicity and nonconvergence are distinct outcomes. A no-cue control may lack an envelope window; compare its actual trajectory, not an invented zero rank. Peak/integral, structure and traversals are secondary. These passive scenes have no actuators; no behavioral-adaptation claim is made. Results concern effects of physical references and grouping, not proof of subjective time. No result-driven formula or threshold changes. Preserve failures and partial evidence; stop on budgets and register any later extension separately.
