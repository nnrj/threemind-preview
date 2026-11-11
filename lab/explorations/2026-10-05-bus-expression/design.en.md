# E49 registration: buses, observation and expression learning

2026-10-05, before execution. [Discussion](../../../docs/en/plans/bus-and-expression-calibration.md).

Identify whether transport, lossy observation, numerical training or unavailable information explains poor raw expression. Success does not require a positive language/reasoning claim.

Reuse E47/E48 sources223/251/279; raw17×119×6 presence/activity/inhibition/trace/support/stability values. Per-source training:16 cued original/reversed correspondence examples at532s. No blank supervision. Tests: new views,592s, unseen cyclic assignments, no-learning and unchanged no-cue outputs. Targets are training supervision only; decoding consumes anonymous state. Actual utterance accuracy is primary; matching no-cue output is a separate observation, never a deduction.

First audit identical inputs with conflicting targets, inter-class distances and raw ranges. Existing1200/6000-step models are historical baselines. New runs≤8000steps: learning rate0.001 vs0.0001; balanced full batch;0.01 initialization of the learnable input projection (not input scaling); flattened linear/small-MLP diagnostic. Require15/16 fit, select using source223 training only, confirm251/279;≤24models. Stop broad simulations if calibration fails.

Compare direct injection vs InputBus on identical inputs, and direct observation vs OutputBus. Separate transport from channel collisions, lost inhibition and time compression in the legacy observer. New sampling20ms, no claim about smaller transients.≤256new probes. Qualified models compare continued external calibration with same-data cold training, excluding unseen test answers. Only unseen≥6/8 consistently in two sources triggers targeted/matched cross-modal edge silencing; otherwise do not expand reasoning lessons. Register adaptive extensions before execution.

Budget:2GiB working soft,8GiB including archive/database hard; one worker,3hcompute,RSS4/GPU3GiB; RAM2/C5/D15/E15GiB reserves. Shared account starts48%;+5points stops expansion,+8stops new compute. Preserve old evidence; no service takeover/push. Publish notes, failures, original outputs and reports to a separate project.
