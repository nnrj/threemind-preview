# ThreeMind Research Positioning and Literature Memo

[中文](../zh/literature-positioning.md) | [English](literature-positioning.md)

## Scope and status

This is a short literature-positioning memo, not a systematic review. It
records the nearest established research traditions, explains what is and is
not distinctive about ThreeMind, and identifies experiments that could turn a
design intuition into an empirical contribution. References are starting points
for deeper review, not endorsements of their theoretical claims.

## Executive conclusion

ThreeMind's constituent ideas are not unprecedented. Continuous plasticity,
associative activation, forgetting, embodied perception/action, attention, and
dynamic cognitive architectures all have substantial prior literature. Nor is
there a mature consensus theory that establishes that their combination creates
consciousness or AGI.

ThreeMind remains worth pursuing as an experimental instrument whose ultimate
engineering objective is artificial consciousness. Its potentially distinctive
contribution is the disciplined combination of anonymous internal state,
explicit input/output boundaries, local plastic dynamics, continuous external
coupling, lifecycle records, and reproducible controls. It should evaluate any
apparent success through falsifiable dynamical hypotheses, rather than declare
consciousness merely from an untested pattern.

## Nearest research traditions

### Plastic recurrent dynamics and continual learning

Plastic recurrent networks, Hebbian-style learning, associative memory, and
continual learning are mature families of work. Research on differentiable
plasticity demonstrates that recurrent networks with plastic connections can
be trained for fast learning and memory-like tasks. Continual-learning research
also documents a distinct problem relevant to ThreeMind: a system may lose its
capacity to learn new material, not merely forget old material.

- Miconi, Clune, and Stanley, *Differentiable plasticity: training plastic
  neural networks with backpropagation* (2018),
  [arXiv:1804.02464](https://arxiv.org/abs/1804.02464).
- Dohare et al., *Maintaining Plasticity in Deep Continual Learning* (2023),
  [arXiv:2306.13812](https://arxiv.org/abs/2306.13812).
- Morales, Mirasso, and Soriano, *Unveiling the role of plasticity rules in
  reservoir computing* (2021),
  [arXiv:2101.05848](https://arxiv.org/abs/2101.05848).

ThreeMind differs by treating online plasticity, decay, and associative reach as
the primary object of inspection, rather than as a learned component optimized
against a benchmark reward or supervised loss.

### Embodiment, development, and sensorimotor organization

Embodied and developmental approaches already study how ongoing bodily and
environmental coupling shapes learning. Developmental neurosimulation explicitly
links developmental trajectory, embodiment, and plasticity. Numenta's Thousand
Brains Project likewise promotes sensorimotor learning as an alternative to
purely static data-centric learning.

- Alicea et al., *Continual Developmental Neurosimulation Using Embodied
  Computational Agents* (2021),
  [arXiv:2103.05753](https://arxiv.org/abs/2103.05753).
- Numenta, *Thousand Brains Project* (project overview and open framework),
  [official announcement](https://www.numenta.com/press/2024/11/20/thousand-brains-project/).

ThreeMind's narrower claim is methodological: an adapter must make the carrier's
sampling and omissions explicit; anonymous Core state should not silently
inherit the human-readable meaning of the carrier.

### Integrative cognitive architectures

OpenCog/CogPrime is a particularly close architectural neighbour. Its work
includes attention allocation, short/long-term importance, forgetting,
spreading activation, memory distinctions, and embodiment interfaces. It is
more explicitly symbolic and goal-oriented than ThreeMind's anonymous-core
baseline, and it intentionally combines many cognitive subsystems.

- OpenCog, [Attention Allocation](https://wiki.opencog.org/w/Attention_Allocation).
- OpenCog, [CogPrime Overview](https://wiki.opencog.org/w/CogPrime_Overview).
- OpenCog, [framework overview](https://wiki.opencog.org/w/OpenCog%3AAbout).

The comparison is useful rather than threatening: ThreeMind can make a smaller
claim about local, inspectable dynamics without adopting a predeclared symbolic
knowledge graph, goals, or a theory-specific decomposition into cognitive
modules.

### Biological and whole-organism simulation

OpenWorm pursues a very different, more biologically grounded objective: a
bottom-up virtual *C. elegans* integrating nervous system, body, environment,
and behavioural validation. Its scope shows both the value and difficulty of
organism-level simulation; it does not provide a completed general solution to
mind or consciousness.

- OpenWorm, [modelling approach](https://docs.openworm.org/modeling/).
- OpenWorm, [project overview](https://openworm.readthedocs.io/en/stable/projects/).

ThreeMind is not a biological replica. It is a deliberately abstract comparison
system for asking which dynamical ingredients matter before attempting detailed
biophysical fidelity.

### Theories of consciousness

Prominent scientific accounts include recurrent processing, global workspace,
higher-order theories, predictive processing/active inference, and attention
schema accounts. They overlap with isolated ThreeMind ideas but do not converge
on a verified computational recipe for consciousness. Current work on AI
consciousness often frames theories as candidate indicator properties rather
than decisive tests.

- Butlin et al., *Consciousness in Artificial Intelligence: Insights from the
  Science of Consciousness* (2023),
  [arXiv:2308.08708](https://arxiv.org/abs/2308.08708).
- Whyte et al., *On the Minimal Theory of Consciousness Implicit in Active
  Inference* (2024), [arXiv:2410.06633](https://arxiv.org/abs/2410.06633).
- Czerner et al., *A Theoretical Computer Science Perspective on Consciousness*
  (2020), [arXiv:2011.09850](https://arxiv.org/abs/2011.09850).

ThreeMind should therefore not infer consciousness from recurrent patterns,
readable fragments, visual clustering, or persistence. Those are measurements
requiring controls, not verdicts on sentience.

## Where ThreeMind may be distinctive

The potentially original part is the conjunction, not the isolated mechanisms:

1. Anonymous nodes and edges avoid storing the stimulus text as internal
   semantics, while retaining labeled versions as comparative instrumentation.
2. Sensory adapters, body filtering, attention/competition, Core dynamics,
   output adapters, observers, and remote transport have explicit causal
   boundaries.
3. Associative traversal can reinforce a route; forgetting is modeled as decay
   of unsupported connection state rather than age-based archival deletion.
4. Continuous external contact, explicit death/unresponsiveness, snapshots,
   portraits, cloning, and provenance logs make lifecycle and intervention
   history inspectable.
5. The same platform can compare topology-first and optional spatial models
   without confusing a display layout with intrinsic geometry.

These are software-and-method contributions unless controlled experiments show
new reproducible dynamical effects. They are still valuable: reproducibility
and contamination control are often missing from informal emergence demos.

## Location of the experimental programme

Executable measures, controls, and objectives belong to the experiment workbench rather than this positioning memo. They have moved to [experimental methods and open questions](../../lab/memos/en/002_experimental-methods-and-open-questions.md) and the [control-experiment module plan](../../lab/memos/en/003_control-experiment-module-plan.md). This document retains the research positioning; completed positive and negative results belong in dated `lab/` notebook entries.

## Practical recommendation

Continue the project with artificial consciousness as its ultimate objective,
and use **measurable, reproducible experiments about plastic dynamical
organization** to determine whether it is moving toward that objective. Pause
or narrow a specific line of work if its only evidence is an intuitive
impression of agency or language-like output. Existing literature means the
project should cite, compare, and learn from predecessors—not that its
particular experimental platform is redundant.
