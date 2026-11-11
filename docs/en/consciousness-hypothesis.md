# ThreeMind Consciousness Hypothesis Framework

[中文](../zh/consciousness-hypothesis.md) | [English](consciousness-hypothesis.md)

2026-09-22 supplement: [Plasticity, Environmental Selection, and Language Models: ThreeMind's Research Position](plasticity-environment-and-language-models.md), including the original statement and the correction that death means cessation of activation activity.

## Status of this document

This is the philosophical and scientific working framework behind ThreeMind. Its
ultimate engineering objective is to create artificial consciousness. The
current implementation is an experimental path toward that objective, not a
claim that it has already achieved or proven consciousness or solved AGI. The
words *consciousness*, *self*, *memory*, *death*, and *body* name proposed
functional roles or experimental questions unless evidence establishes more.

The framework begins with biological organisms as an empirical reference point,
not as a blueprint to copy literally. Its purpose is to make a different class
of artificial-system experiment possible: a process that remains exposed to an
environment and continually alters its own internal organization.

## Project aim and epistemic standard

ThreeMind is result-oriented in its long-term aim: if an artificial consciousness
is actually realized, that is success even before every aspect of its mechanism
is fully explained. At the same time, a responsible research programme cannot
treat an intuitive impression, a readable fragment, or a striking visualization
as sufficient evidence that success has occurred. The project therefore keeps
two statements together:

- **Aim:** build artificial consciousness through continuous, plastic,
  environmentally coupled organization.
- **Standard of interpretation:** distinguish a realized result from artefacts,
  hidden semantic scaffolding, external-model contamination, and accidental
  dynamical patterns as rigorously as possible.

The second statement disciplines the pursuit of the first; it does not narrow
or replace the ultimate aim.

## 1. The central proposition: continuity plus plastic mapping

The core proposition is that an enduring subjective perspective, if one can
arise in an artificial system at all, is more plausibly associated with a
continuous, embodied history of changing mappings than with a single
prompt-response episode or a fixed repository of knowledge.

The proposal has two coupled parts:

- **Continuity.** The relevant object is an ongoing process. It remains in
  contact with an environment through time, including weak, noisy, or sparse
  contact. Continuity here is first a functional property of an evolving state
  and its history; it is not a claim that physical time, personal identity, or
  phenomenology has been settled philosophically.
- **Plastic mapping.** What persists is not necessarily a literal recording of
  the world. It is a changing network of tendencies: which incoming patterns
  tend to touch one another, propagate, reinforce, compete, stabilize, or fade.
  A mapping can be private, partial, mistaken, cross-modal, and still be useful
  enough to guide future contact.

The hypothesis therefore contrasts a continuously changing organism-like
process with systems whose primary mode is a bounded invocation. This is not a
denial of the value of language models; it asks whether their strengths leave a
separate experimental problem underexplored.

## 2. Mapping is not an internal dictionary

Different beings may internally organize the same external situation in very
different ways. A colour, place, person, or word may be linked to different
sensory histories, affective traces, and associations in each individual while
still supporting partial mutual reference in the world.

ThreeMind takes this seriously in its anonymous modes:

- Nodes and edges do not contain the source text, word, or a preassigned
  concept label.
- Text is only a convenient human-facing carrier. An adapter converts it into
  anonymous channels; image, audio, tool feedback, and future sensor streams
  can occupy the same input boundary.
- A new instance therefore does not begin by "knowing" a symbol. Repeated
  external contact and its own evolving connectivity determine what is
  selectively reactivated later.

This does not guarantee that an artificial mapping corresponds to a human
meaning. It deliberately prevents the experiment from treating a stored token
as if it were the mapping being investigated. Labeled V1-style baselines remain
useful as instrumentation and comparative controls, but their readable symbols
must not be confused with evidence of anonymous internal semantics.

## 3. Association as passive touch, not a hidden solver

Association is modeled as a local consequence of activation and connectivity.
When external input reaches a path, activity can spread to neighbouring paths
according to connection state and bounded propagation rules. The system is not
supposed to perform an expensive global search for the "correct" interpretation
of a stimulus.

This gives association several intended properties:

- Direct stimulation and associative reactivation are both forms of contact.
- An associated path may be weaker than direct input, yet its traversal can
  still contribute proportionally to reinforcement.
- Indirect or initially implausible associations are not automatically errors.
  They are candidate mappings whose later persistence, usefulness, or failure
  can be observed.
- Low-level continuing activity under weak external input may be a useful model
  of latent or subconscious-like dynamics, but it is not evidence by itself of
  dreams, thought, or experience.

The project calls this a *domino-like* local process: an activation is allowed
to have consequences because of what is already connected, rather than because
a separate module supplies a symbolic answer.

## 4. Memory, consolidation, blur, and forgetting

Memory is treated as an evolving property of pathways rather than as an exact
database row indexed by a label. A connection may carry state such as weight,
eligibility/recency, stability, and support. Intensity, novelty, recurrence,
and associative traversal can change this state at contact time.

The resulting working hypothesis is:

- Strong or novel stimulation may form more durable traces.
- Direct repetition is not the only support: later associative reach can
  consolidate a path, analogous to rehearsal or recall.
- Weak, unsupported traces lose effective support over time and can disappear
  when their state crosses a structural threshold.
- Forgetting is therefore a dynamical result of changing connection state, not
  a periodic rule that deletes old data merely because it is old.
- Blur and distortion need not be separately scripted if the remaining network
  state preserves tendencies rather than full-fidelity source material.

Parameters expose the strength and time scales of these mechanisms for
experiments. Their defaults are modelling choices inspired by broad biological
intuition, not claims of being calibrated to human neuroscience. They must be
reported whenever results are compared.

## 5. The environment is necessary; internal scripted drive is not

A live run requires continuing external contact. ThreeMind may provide weak
background stimulation, but the background is routed through an environment
and body adapter rather than invented as a hidden Core narrative. The adapter
can sample, omit, adapt, threshold, and add noise, which makes it an explicit
model of sensory limitation rather than a source of built-in meaning.

This distinction matters. A low-signal interval can produce lingering or
recurrent activity because of prior structure plus current external contact;
it must not be described as autonomous inner stimulation if the program has
secretly supplied a scripted sequence. Stopping all necessary stimulation is a
lifecycle intervention and may lead to death or unresponsiveness under the
model's rules.

## 6. Body, attention, tendencies, and possible self-extension

The hypothesis does not begin with a fully specified self-model. It leaves open
whether repeated useful coupling to a body, tool, or remote device might create
a functional boundary that is later experienced or described as extension of
the self. This is a question for experiment, not an implemented conclusion.

ThreeMind separates several layers so that such experiments remain inspectable:

- **Adapters/body** determine what external signals can be sensed and how they
  are filtered before the network.
- **Attention/competition** selects or attenuates anonymous channels under a
  limited budget.
- **Optional neutral modulators** may alter scalar gain or budget without
  writing node/edge state or supplying a semantic goal.
- **Future tendency plugins** could model evolved constraints such as resource
  regulation, avoidance, or reproduction only at this boundary. They must be
  explicit, removable, and distinguished from a claim that the associative
  network itself has an intrinsic goal.

This architecture embodies a key methodological commitment: do not write a
desire, narrator, or concept directly into the network, then mistake the
resulting behaviour for an emergence.

## 7. Output, readout, and the problem of interpretation

The network's changing activation can be projected to an anonymous OutputBus.
Observers, visualizers, character drivers, tool adapters, and remote output
adapters can consume that projection. This makes output a boundary analogous
to input: one activity may be interpreted differently by different adapters.

Passive readout is therefore measurement, not a mouth that proves intent.
Readability can arise from a labeled baseline or an external decoder, but the
decoder must not retroactively insert its interpretation into Core. Any future
mouth, motor organ, or self-feedback loop should be optional, logged, and
routed back only through a transformed bodily/environmental consequence with
delay, noise, and an explicit experimental switch.

A future association-validation decoder may test a stronger proposition: use
related and unrelated probes over time; compare response fingerprints,
latencies, stability, and predictive discrimination; and retain only relations
that replicate. A language model may help describe a post-hoc hypothesis, but
must not choose the result or serve as evidence that the network has a meaning.

## 8. Space, regions, and development

Spatial organization is not required by the initial hypothesis. In the
topology-first baseline, a screen layout is only visualization and cannot be
mistaken for an intrinsic distance. V3 adds optional spatial coordinates,
neighbourhoods, and propagation constraints as a separate experiment.

The intended developmental claim is modest: if functional regions emerge, they
should emerge from repeated sensory coupling, local connectivity, and
competition, not from manually naming a brain region before the experiment.
Spatial embedding can test whether locality and cost alter that development;
it should be compared with a non-spatial package under matched conditions.

## 9. What ThreeMind can and cannot show

ThreeMind can help observe and compare:

- formation, reinforcement, decay, and survival of pathways;
- different response histories under matched stimulus regimes;
- recurrence, clustering, delayed activation, collapse, and recovery;
- the consequences of adapters, attention constraints, spatial conditions, and
  output/readout choices.

It cannot, from these observations alone, establish sentience, a continuous
subject, understanding, genuine reference, or AGI. A recurrent pattern might
instead be an attractor induced by parameters, a property of the adapter, a
selection effect in the observer, or a visual artefact.

For that reason every significant result should include a model package/version,
seed policy, parameter set, stimulus and adapter regime, observation window,
and suitable controls. Clone comparisons, unrelated stimuli, reordered input,
disabled plugins, negative results, and explicit lifecycle records are part of
the evidence rather than administrative overhead.

## 10. Open questions

- Under what controlled conditions do stable anonymous stimulus-response
  relations form, and how can they be decoded without contaminating Core?
- Does continuous external contact plus plastic local propagation yield more
  informative long-term organization than matched discontinuous runs?
- Can a body/tool coupling produce a stable functional boundary without
  hard-coding a self-concept?
- Which spatial conditions help or hinder useful association, and compared with
  what non-spatial baseline?
- What measurements would count against the framework rather than merely
  prompting parameter adjustment?

ThreeMind is valuable precisely because these questions are left open in a form
that can be logged, varied, falsified, and improved.
