# Temporal-window Convergence Readout

[中文](../zh/temporal-window-readout.md) | [English](temporal-window-readout.md)

## Purpose and boundary

ThreeMind retains the original **single-tick snapshot reader** and adds a
parallel **temporal-window convergence reader**. The former asks which
structure or touch set is prominent in one frame. The latter asks which nodes
remain on the activity stage after one carrier and whether the response
converges, oscillates, decays as a residue, or disappears as a transient. Both
are read-only `OutputBus` adapters. Neither changes nodes, edges, activation,
inhibition, or learning rules.

A temporal result cannot assign semantics to an anonymous model merely from
its topology. It can establish that an input packet reproducibly evokes a
dynamical response. Text may be displayed only when the model has external
observation labels or a separately validated decoding map. Anonymous evidence
and raw metrics remain the primary scientific record.

## Causal window

The input bus already gives a complete carrier an `envelope_id` and frames a
long carrier in order. Core now projects only this audit context with an
anonymous `OutputFrame`:

- envelope identity;
- frame index and frame count;
- input-adapter identity;
- external source.

These fields are never consulted by a dynamics method and contain no carrier
text. The reader opens a window when the first frame arrives and continues
after the final frame, so transport time for a long carrier is not mistaken
for a completed network response. Overlapping envelopes are recorded
explicitly instead of being silently assigned one causal interpretation.

## Measurements and classifications

Each window first retains several pre-stimulus ticks of activation mean and
natural variation, then subtracts that baseline from the response. For every
candidate node it records:

- active ticks above baseline, longest continuous run, and re-entry count;
- activation integral, excess-over-baseline integral, peak and mean;
- direct touch, associative touch, inhibition, and stability;
- persistence after carrier delivery ends;
- active-set similarity and normalized activation-distribution drift.

The default candidate scope includes nodes that were associatively touched or
remained active after delivery. This reduces the chance that the reader merely
echoes sensory input nodes. The experimenter may select associative-only or all
above-baseline activity instead.

The auditable classifications are:

- **converged:** a stable tail candidate set with sufficiently small
  distribution drift;
- **oscillatory:** a repeating tail-set period;
- **residual decay:** chiefly a fading remnant rather than a stable response;
- **transient:** activity disappears within the minimum window;
- **unresolved:** no other condition is met before the maximum window;
- **interrupted:** observation is disabled before a window completes.

Composite ranking includes active duration, longest run, tail persistence, and
excess activation integral by default. Activation strength can be excluded, or
ranking can be changed to duration or activation integral directly. Every
event stores all candidate metrics and its configuration snapshot. The display
limit never truncates the scientific record.

## Operation

Single-tick and temporal readouts can be enabled independently under
**Settings → Observation, readout & records**. Temporal observation defaults
to manual carriers only; AI and ambient carriers require explicit opt-in to
avoid an unbounded collection of overlapping environmental windows. Completed
results are:

- shown in the stimulus conversation with a tick range and classification;
- written to the consciousness passive-readout history;
- persisted in the model package and configured history backend;
- annotated with external labels in readable observation modes, while
  anonymous mode shows only response identity and node IDs.

Detailed dynamics tracing remains independent. Temporal readout does not
require per-tick trace recording because it subscribes to the live
`OutputBus`; tracing exists for later replay and finer scientific audit.

