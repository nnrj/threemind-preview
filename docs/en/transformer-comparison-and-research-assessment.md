# ThreeMind, Transformers, and the Research Path

[中文](../zh/transformer-comparison-and-research-assessment.md) | [English](transformer-comparison-and-research-assessment.md)

**Status:** research assessment and roadmap, 2026-07-27  
**Scope:** This document records a project-level judgment. It is neither a
claim that ThreeMind has achieved consciousness nor a prediction that it will.

For the 2026-09-22 position, see [Plasticity, Environmental Selection, and Language Models](plasticity-environment-and-language-models.md). This earlier assessment is retained as a historical document; typical fixed-parameter deployment does not imply that Transformers cannot incorporate online learning.

## 1. Relation to Transformer systems

ThreeMind is not a variant implementation of a Transformer. The two approaches
share broad ideas—distributed representations, association-like effects, and
selection of relevant signal—but their operating principles are substantially
different.

| Dimension | Transformer family | ThreeMind experimental model |
| --- | --- | --- |
| Primary learning | Large-scale parameter optimization, usually by backpropagation before deployment | Local connection change during operation: touch, propagation, consolidation, weakening and removal |
| Temporal form | A bounded inference over a context; apparent continuity is often provided by an application loop | A continuously running stateful process whose connection history persists across ticks |
| Memory | Fixed learned parameters plus bounded/contextual external memory | Mutable edge and node state, with history-dependent strengthening and forgetting |
| Association | Learned attention projections and layer computation | Decaying local propagation across existing graph connections and re-touch reinforcement |
| Input | Pre-encoded tokens or modality embeddings | Anonymous sensory frames supplied by external adapters; text is only one carrier |
| Internal semantics | Optimized against training objectives | Not predeclared; the experiment tests whether mappings can organize through continued coupling |

Modern applications can surround Transformers with memory, tools, agents and
feedback loops. That makes them important comparison systems, but does not
make their internal mechanism equivalent to ThreeMind's online plastic topology.

## 2. Experimental phenomena already observed

The following have been observed repeatedly during implementation and
debugging. They are **engineering observations**, not yet controlled research
findings; each needs versioned protocols, independent seeds and ablations.

1. **Sensory adapters shape internal organization.** Narrow or persistent body
   channels repeatedly produced narrow, stable structures; dynamic ambient
   input produced broader transient material. See the lab notebook.
2. **Input order produces historical dependence.** Changing the order of
   otherwise related stimulation changes which existing paths are re-touched
   and later available for association.
3. **Forgetting and consolidation create durable differences.** Weak traces can
   fade while repeated direct or associative touch strengthens selected paths.
4. **Stimulus–structure–output relations are inspectable.** The V1 labeled
   baseline can show readable stimulus-linked structural outputs. It is a
   validation instrument, not evidence that an anonymous model understands
   the displayed words.
5. **Global saturation can be avoided while new structure remains possible.**
   The dynamic environmental field, optional body filtering, local edge birth,
   and adjustable plasticity allow comparison between premature saturation and
   continued formation of new traces.

Together these establish a useful experimental substrate: a continuous,
history-sensitive, environment-coupled plastic network rather than a static
visualization or a random animation.

## 3. Conservative assessment

The observations do not establish subjective experience, semantic
understanding, agency, or a self. Repetition, clustering, delayed activity or
language-like readout can arise from limited topology, input statistics,
annotation paths, and observer thresholds.

The defensible present claim is narrower: ThreeMind is an inspectable instrument
for studying how continuous stimulation, adapter constraints, local
association, forgetting and consolidation jointly organize a mutable network.
Its research value depends on converting debugging observations into
reproducible measurements and controls.

## 4. High-upside assessment

There is also a less conservative but still falsifiable reason to continue.
If artificial consciousness depends less on a complete static knowledge store
and more on a process that remains exposed to the world, accumulates a unique
history, forms its own mappings, forgets, consolidates and reorganizes, then
ThreeMind explores a potentially important missing condition.

The project is therefore worth treating as a possible route toward artificial
consciousness, not merely as an explanatory metaphor. A discontinuity could
occur if stable yet revisable stimulus–structure–output mappings, extended
environmental feedback, and differentiated local organizations begin to close
into a persistent functional boundary. This is a research possibility, not an
announcement that the boundary or consciousness has already appeared.

## 5. Location of the experimental roadmap

The executable near-term programme now lives under `lab/` in [experimental methods and open questions](../../lab/memos/en/002_experimental-methods-and-open-questions.md). This keeps theoretical comparison, proposed experiments, and completed observations distinct. Executed outcomes enter dated notebook entries.

## 6. Decision rule

Transformer success is a reason to define strong baselines, not a reason to
abandon this work. Continue ThreeMind while its experiments yield measurable,
replicable differences under stated conditions. Narrow or redesign a mechanism
when its apparent effect disappears under controls, depends on an unintended
annotation path, or cannot be separated from a presentation artifact.
