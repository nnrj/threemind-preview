# Attribution of continuous-kernel effects: preregistered design

2026-09-29. Diagnose the earlier overlap-curriculum phenomenon without changing Core equations, mapping, temporal edge birth, or readout thresholds. Preserve the previous study; use a new project and independent descendants.

S = short-term synaptic resources, F = fast trace, C = receiver-local context allocation. Reuse block-0 anonymous channels and seed 9291000 for an exact anchor. Train `[A], [A,B], [B,C]` and `[D], [D,B], [B,E]`, with a second curriculum swapping C/E. Repetitions per sequence are 20, then 10, then 5: 210 frames at dose 1.0 and one simulated second spacing. Initial wait 2.2 seconds; post-training wait one second. Test dose 0.5; prefixes and B are one second apart; observe at most 12 seconds.

1. Validate read-only instrumentation: reproduce prior state and responses; compare 100-ms and 10-ms sampling for identical final Core state and temporal readouts. Halt attribution if this fails.
2. Full S/F/C factorial (8) × original/swapped associations (2) × forward/reverse curriculum order (2): 32 parents. Six independent probes each: A→B, D→B, B alone arriving at second 1, A alone, D alone, and no input (192 probes).
3. Four all-on parents: switch each independent test copy to the other seven configurations via public reconfigure, before the one-second hold. Two sequence probes per condition (56). Preserve structure, histories and queued events; record exact configuration intervention.
4. Preserved causal/9 reference: four matched parents and two sequence probes each (12 instances).
5. Background confirmation: all eight configurations, original associations/forward curriculum, replay the same recorded real host-0 telemetry at dose 0.2; A→B, D→B and B-only (32 instances).

Maximum 324 formal instances plus 8 validation instances. Execute in this order; explicitly label omitted stages if budgets stop execution.

Retain the original primary endpoint: converged temporal-readout last activation, descending. Nonconvergence stays nonconvergence. For mechanism diagnosis record ALL nodes every 10 ms with no candidate-threshold filtering, key-time structural/operator snapshots and observer events. Separate pre-B and post-B peak margins, peak times, activation-area margins, and endpoint. Compare sequence vs prefix-only at matched times; compare B-only/no-input to locate residual bias. Publish all eight cells, paired switch effects and interactions. Deterministic channel renamings and trajectory samples are not independent statistical replicates. Necessity/sufficiency claims are local to these conditions. Any new diagnostic extension must be recorded before execution.

One CPU process, at most two numeric threads, 4-hour wall time, 600 seconds/case, RSS 4 GiB, host free RAM 2 GiB, D/E free space 15 GiB. Total new DB + local storage <=2 GiB (stop at 1.8 GiB with closure reserve); raw local guard 0.65 GiB. Check storage every 60 seconds without scanning old data. Account usage starts at 39%; stop expanding at 42%. No paid AI, GPU or Transformer calls. Plan and bilingual results are saved via Lab services; original stimuli/configuration/state hashes/events/trajectories/source hashes retained. Observation never feeds back into Core.
