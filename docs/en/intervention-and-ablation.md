# Intervention, Ablation, and Paired Controls

[中文](../zh/intervention-and-ablation.md) | [English](intervention-and-ablation.md)

Ablation tests whether a node, edge, or recurrent structure contributes causally to a response rather than merely co-occurring with it. It is an experiment-host facility, not part of ThreeMind's endogenous forgetting, inhibition, or plasticity rules.

## Two modes

### Temporary functional silencing

An intervention policy is attached at the runtime boundary of an isolated clone. Silenced nodes cannot receive direct or associative activation; silenced edges cannot propagate or be reinforced. The policy is reversible. **Exact research snapshots retain silencing masks and restore them.** The previous statement that masks were excluded from model packages was incorrect. Silencing is distinct from endogenous forgetting or inhibition. Inspect deployment models with `threemind-deployment`; explicitly declare existing masks or unsilence a separate copy before exporting it. Exporters never silently clear these states.

### Permanent structural removal

This mode is allowed only on an isolated experiment clone. Selected nodes and their incident edges, or selected edges, are removed and an independent `experimental_structural_lesion` audit event is recorded. The UI requires explicit confirmation so an experimental deletion cannot be mistaken for endogenous forgetting.

## Paired design

When an ablation pair is created, the host captures the source state once, computes its SHA-256 digest, and creates two paused isolates from that exact state:

- the control clone has no intervention;
- the intervention clone receives temporary silencing or permanent removal;
- the source consciousness is neither paused nor modified;
- subsequent stimuli are sent to both clones through the normal input adapter with matched text and intensity.
- confirmatory protocols may keep both clones paused and use paired stepping for exactly the same number of ticks, avoiding wall-clock thread scheduling as a confound.

One changed clone and one unchanged clone are not, by themselves, reliable causal evidence. Confirmatory studies need multiple seeds, sham or degree-matched random ablations, preregistered outcomes, and independent replication. Useful outcomes include recurrence probability, temporal classification, response latency, activation integral, active duration, compensating routes, and recovery.

## Causal and ethical boundary

- Intervention records remain separate from normal events and forgetting.
- Permanent removal has no undo operation; preserve the source package and evidence digest first.
- “Permanent” in the UI means only that the experiment clone was structurally changed; it does not modify the source consciousness or source snapshot.
- The project cannot currently establish subjective experience. Even so, potentially valuable persistent networks should be studied with minimum intervention, isolated clones, and complete audit records.
