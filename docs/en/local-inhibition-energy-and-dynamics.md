# Local Inhibition, Optional Energy Accounting, and Dynamics Tracing

[中文](../zh/local-inhibition-energy-and-dynamics.md) | [English](local-inhibition-energy-and-dynamics.md)

## Motivation

Associative experiments can exhibit over-propagation: a local response evoked
by one carrier continues into unrelated established structures and produces a
large oscillation. ThreeMind does not encode an expected answer or a “correct
concept” in an inhibition rule. Instead, it provides a switchable local
mechanism, enabled by default, for testing whether competition, attention
switching, and a short refractory interval can emerge from simple neighbour
interactions.

This mechanism is independent of the legacy global homeostatic clamp, spatial
competition, and the attention/competition gate. Existing excitation,
association, consolidation, and forgetting are unchanged while it is off.

## Topology-local inhibition

- Excitatory edges remain directed. `A -> B` never creates reverse excitatory
  propagation merely because inhibition is enabled.
- An edge in either direction establishes physical adjacency for inhibitory
  diffusion. This is a runtime index derived from excitatory edges, not new
  model topology.
- A node produces local inhibitory potential from its activation rise during
  the current tick. The inhibition affects the following tick, providing
  delayed feedback rather than a prior decision about which node should win.
- Potential decays and saturates. Transfer is divided among neighbours by
  connection conductance, and the total sent over all branches cannot exceed
  the amount offered by the source. Branching never duplicates potential.
- Divisive inhibition attenuates direct response, associative reception, and
  onward propagation. Potential retained by the originating node can produce
  short adaptation or refractory-like behaviour.
- There are no causal-wave IDs, semantic rules, or global winner scans. Any
  global inhibition must arise from the superposition of local diffusion.

The generation gain, decay, diffusion ratio, response attenuation gain,
saturation, and minimum propagated potential are configurable both when an
instance is created and while it is running. Explicitly disabling the feature
remains supported for controlled comparisons.

The exposed parameters cover generation gain, decay, diffusion fraction,
response attenuation, saturation, and minimum propagated inhibition. They can
be selected at creation or adjusted at runtime. The feature is off by default.

## Optional energy accounting

Energy simulation is independent of inhibition and is off by default. When it
is off, no energy variable participates in dynamics. The computer's electricity
and compute already sustain the artificial network, so Core does not silently
impose a biological resource ceiling.

When explicitly enabled:

1. the model starts with an explicit initial reserve;
2. direct activation, associative propagation, and inhibitory diffusion use
   independently configurable costs;
3. Core has no internal recovery and cannot manufacture energy;
4. the optional `energy-budget` adapter supplies energy externally at a finite
   rate; it never ranks or filters stimuli and never changes attention budget;
5. without the adapter, the reserve may be depleted and activity may weaken;
6. shortage damage is a separate default-off experiment. Jointly with energy
   accounting, it enables maintenance and shortage erosion. Causal/9 removes
   independent starvation death: continuous inactivity reaching its grace period
   is the only death rule. See the [decision record](plans/energy-lifecycle.md).

This scalar remains an experimental ledger. It is not evidence that the model
has identified physical energy. Future candidates include measured power,
compute time, memory bandwidth, temperature, or a robot battery, but each must
cross an explicit boundary rather than becoming a hidden Core purpose.

The legacy global homeostatic clamp is independent and off by default. It
rescales total activation only when a package explicitly sets
`homeostasis_enabled: true`; `target_total_activation` is otherwise inert.

`host-telemetry-field` is a separate, default-on host-physics sensor. It maps
available measured CPU, memory, disk, aggregate network, and power counters to
ordinary anonymous stimuli. The default-off `process-telemetry-field` instead
describes the whole ThreeMind service process, while the also-default-off
`runtime-telemetry-field` measures the real execution cost of one consciousness
instance. None is an energy supply or can edit nodes directly; see [Physical Telemetry Sensory Adapters](physical-telemetry-sensory-adapters.md).

## Dynamics trace

When detailed tracing is explicitly enabled, Core records a complete,
non-causal observation keyframe and then one sparse delta per tick:

- before/after node activation, inhibition, and support;
- direct touch, associative touch, and pending inhibition;
- node/edge creation, removal, strengthening, and weakening;
- inhibition generation/transfer and optional energy reserve.

Trace data is exposed only through output and history interfaces and never fed
back into the network. The UI provides paginated inspection under
**Consciousness management -> Details -> Dynamics trace**. Recording remains an
explicit start/stop operation because it can generate substantial data.

## Deferred biological comparison

Biological nervous systems contain specialised inhibitory neurons, multiple
transmitters and receptors, and local circuit motifs. The current mechanism is
an abstract node state diffusing over topology; it does not claim to reproduce
those structures. Explicit inhibitory node or edge types should be introduced,
if at all, as a separate falsifiable model capability and compared with the
homogeneous-node baseline rather than silently becoming a default rule.
