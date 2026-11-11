# Research Notes and Working Agreements

[中文](../zh/research-notes.md) | [English](research-notes.md)

## Hypothesis under experiment

The project explores whether a continuously running, plastic associative system
can form persistent internal mappings from ongoing external stimulation. Its
ultimate aim is artificial consciousness, while the current implementation does
not claim to have achieved it. Visual activity, readouts, or language-like
fragments are not sufficient evidence of consciousness.

Working assumptions:

- A continuous experience process matters more than a static trained model.
- Internal mappings may differ between individuals while still allowing partial
  reference to the same external situation.
- Association may be initially wrong, indirect, or cross-modal; usefulness and
  repeated traversal can stabilize a path without requiring a symbolic rule.
- Forgetting is a dynamical decay of unsupported connection state, not a
  separate database cleanup policy. Strong or repeatedly traversed paths resist
  decay through their own weight, eligibility, stability, and support.
- A recalled/associated path is also a form of stimulation and can reinforce
  itself proportionally; reinforcement is not limited to exact repeated input.

## Non-negotiable implementation constraints

- Anonymous Core nodes and edges must not store input text as labels or values.
- Text is only a convenient experimental carrier. It is encoded by an external
  adapter just as images, audio, tool feedback, or other modalities may be.
- Readable labels, passive readouts, and AI interpretation logs are external
  observations; they must not silently become internal meanings or stimuli.
- Background stimulation should remain continuous while a consciousness runs,
  although the body and attention gate may make its delivered form weak,
  intermittent, filtered, or noisy.
- A visual animation is not evidence of a topological change. Presentation-only
  motion must be clearly optional and disabled by default.

## Experimental interpretation

A repeated structural signature, delayed activity after an input, clustering,
or a character-like readout is an observation worth logging and comparing. It
is not by itself proof of intention, comprehension, selfhood, or emergence.
Useful experiments require controls: changed stimulus order, unrelated
stimuli, disabled body/attention plugins, cloned packages, and repeated runs.

## Experimental discipline

The following practices were retained from the earlier ThreeMind baseline because
they remain useful independently of its former UI and kernel implementation:

1. **Protect causal boundaries.** Only an admitted `SensoryFrame` and the
   runtime's own update rules may change the associative state. Renderers,
   notifications, passive readouts, AI summaries, logs, and export tools are
   observers; none may write activation, node, or edge state back into Core.
2. **Keep the process genuinely continuous.** A running instance should remain
   coupled to an external environment signal, even if the body adapter or
   attention gate makes individual delivered frames sparse. Do not present an
   internally scripted "dream" sequence as spontaneous activity.
3. **Prefer local causes.** Propagation, association, reinforcement, and
   forgetting should be explainable through local state, incoming frames, and
   bounded neighbourhood dynamics. A global graph search must never silently
   supply a semantic answer.
4. **Make interventions recoverable.** Record model package version, random
   seed, parameters, adapter configuration, stimulus regime, and observation
   window. Take a named snapshot before material parameter changes; keep
   detailed traces opt-in and bounded in time.
5. **Record lifecycle transitions explicitly.** Creation, pause, resume,
   unresponsiveness, death, snapshot, portrait, clone, restore, and deletion
   are events, not invisible resets. A portrait preserves a terminal state; it
   must not be represented as an ongoing run.
6. **Treat negative results as data.** Collapse, non-recurrence, and failed
   discrimination are useful observations. A recurring visual motif alone is
   insufficient; report plausible alternatives such as a parameter-induced
   attractor, a display choice, or an observer threshold.

## Spatial baseline and comparison

The original baseline intentionally separated associative dynamics from
geometry: a 2D/3D layout was only a display projection. ThreeMind now also
supports optional spatial embedding for V3 experiments. This does not replace
the topology-first baseline. It creates a controlled comparison condition:
coordinates, neighbourhood radius, propagation attenuation, and local cluster
statistics are model attributes only when the package explicitly enables them.

When comparing non-spatial and spatial packages, keep the stimulus regime,
attention/body configuration, random seed policy, and observer thresholds as
close as possible. Screen distance, camera motion, and cosmetic layout remain
presentation data in every mode unless they are derived from the package's
actual spatial state.

## Deferred directions

- A decoder may later test stable stimulus-response mappings with related and
  unrelated probes, rather than assuming a structure means a word.
- Functional regions should emerge from sensory activity and connectivity,
  rather than being manually named in advance.
- Self-feedback, output organs, and remote physiological signals must remain
  optional experimental boundaries with observable delays and transformations.
- A future association-validation decoder may present related and unrelated
  probes, compare anonymous response fingerprints and latency, and retain only
  replicated stimulus-response relations. An LLM may help phrase a hypothesis
  after the quantitative comparison, but it must not select the result, feed
  Core, or count as evidence of internal meaning.
