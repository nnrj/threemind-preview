# Mechanism-by-Mechanism Comparison with Existing Network Families

> Public edition, 2026-11-11: private conversation locators and manuscript/submission discussions are omitted where present. Scientific records retain their original dates; the complete source remains unchanged.


[中文](../zh/algorithmic-comparison.md) | [English](algorithmic-comparison.md)

## Status

This memo positions the current ThreeMind Core against original papers at the mechanism level. It does not classify systems by canvas appearance or readable labels. It is neither a claim of proven originality nor an attempt to call similar mechanisms identical, and it must evolve with Core and the control experiments.

## Minimal mechanism profile of current ThreeMind

The unified Core currently has these defining properties:

- anonymous nodes; plaintext labels are external instrumentation and do not enter dynamics;
- adapters convert carriers into temporally framed stimuli that contact sensory channels;
- activation propagates locally over **existing directed edges** and decays;
- edge birth is normally driven by local coactivation within an input frame, while weight, stability, support, and eligibility change online;
- unsupported connections decay and may break; associative contact may also contribute to consolidation;
- spatial substrate, temporal association, local inhibition, energy simulation, and explicit compute budgets are optional;
- no supervised objective, error backpropagation, global semantic dictionary, or preloaded relation triples exist;
- passive/temporal readouts and analytics remain outside Core and only observe output.

A compact technical description is therefore: **an event/framed recurrent graph-dynamics experiment with growing topology, continuous online plasticity, forgetting, and optional local inhibition.**

## Comparison table

| Family | Shared or nearby mechanism | Critical difference | Current judgement |
| --- | --- | --- | --- |
| Hebbian learning / cell assemblies | local joint activity can strengthen association; repeated contact can form revisitable structure | ThreeMind is not one `Δw = ηxy` rule; it adds directed propagation, edge birth, stability, eligibility, support, forgetting, and adapter boundaries | **One of the closest relatives, not standard Hebb** |
| Oja's rule | weights may change from local activity | Oja has an explicit normalization term and principal-component behaviour; ThreeMind has neither equation nor PCA objective | **Different** |
| STDP | timing and local plasticity matter | STDP depends on precise pre-/postsynaptic spike order and an asymmetric timing window; ThreeMind currently uses ticks, within-frame coactivation, propagation contact, and optional temporal association | **Conceptually adjacent, implementation different; test directly** |
| Classical Hopfield | recurrent activity can revisit or appear to converge | classical models normally use fixed size, symmetric weights, stored patterns, and an energy-decrease guarantee; ThreeMind uses directed online-plastic topology under ongoing input and has no Lyapunov energy | **Not Hopfield; attractor status unproven** |
| Modern Hopfield | both may show association-like retrieval | modern Hopfield networks have explicit stored patterns, continuous energy updates, and analytic relation to attention; ThreeMind has no keys/queries, softmax, or pattern matrix | **Different** |
| Echo State / reservoir | recurrent transients, history dependence, and external readouts | reservoirs normally fix the recurrent pool and train the readout under an echo-state condition; ThreeMind continuously changes the internal topology, while its readout does not train Core | **Nearby dynamics, opposite learning target** |
| Competitive learning / ART | local competition may yield selective responses; both face stability–plasticity | ART has explicit matching, vigilance, and reset; ThreeMind declares no category matcher and derives inhibition from local adjacency | **Partly related, not equivalent** |
| Wilson–Cowan / Amari neural fields | excitation–inhibition, stable states, oscillations, and local competition are comparable | those systems use continuous population or field equations; ThreeMind uses discrete nodes and dynamic graph edges, with optional space | **Comparable phenomena, different equations and objects** |
| Backpropagation RNN | recurrence and sequential history | a standard RNN minimizes a dataset loss with BPTT over fixed parameters; ThreeMind has no supervised error or reverse pass, and observes online structural change itself | **Substantially different** |
| Transformer | both can produce context-dependent output from sequences | Transformers use layer-wise global self-attention and are commonly trained offline; ThreeMind uses local adjacency propagation and online topology changes, with no token embeddings or attention matrix | **Different architecture and learning regime** |
| Knowledge graph / symbolic system | both canvases may display nodes and edges | ThreeMind Core has no explicit entity, predicate, triple, or query semantics; labels are external instruments | **Visual resemblance only** |

## Primary references

- Hebb's cell assemblies and activity-dependent plasticity: *The Organization of Behavior* (1949; [bibliographic record](https://openlibrary.org/books/OL28404517M/The_organization_of_behavior)). ThreeMind is intellectually related, but its edge update is a project-specific engineering model.
- Hopfield's 1982 model stored memories as stable collective states. The classical model is not the current ThreeMind implementation. [PNAS / PubMed](https://pubmed.ncbi.nlm.nih.gov/6953413/)
- Oja's normalized local update yields principal-component behaviour; ThreeMind has no such objective. [DOI](https://doi.org/10.1007/BF00275687)
- Bi and Poo demonstrated a narrow, asymmetric spike-timing window for synaptic modification; ThreeMind is not spike-level STDP. [Original paper PDF](https://www.gatsby.ucl.ac.uk/~pel/course_wuhan/papers/bi.poo_1998.pdf)
- Jaeger's echo-state approach separates recurrent dynamics from a trainable readout; ThreeMind likewise externalizes readout, but makes its recurrent graph plastic. [Fraunhofer record](https://publica.fraunhofer.de/entities/publication/7d4a7eec-a22c-4df0-903d-93f9cd5aca02)
- Wilson–Cowan equations produce stable states, hysteresis, and limit cycles in coupled excitatory/inhibitory populations. They are a control model for inhibition, not the implementation source of Core. [Original paper PDF](https://www.gatsby.ucl.ac.uk/~qhuys/theoretical_neuroscience/Wilson-Cowan72.pdf)
- Amari studied pattern formation in lateral-inhibition neural fields; ThreeMind can compare phenomena while retaining different spatial and mathematical assumptions. [DOI](https://doi.org/10.1007/BF00337259)
- Modern Hopfield networks use continuous states and an energy function with a defined relationship to Transformer attention. This is why convergence-like appearance alone cannot place ThreeMind in that class. [OpenReview](https://openreview.net/forum?id=tL89RnzIiCd)

> **Public-edition edit (2026-11-11; source lines 50-50):** Manuscript text, writing/submission discussion or links to non-public manuscript documents are omitted. Where a paragraph mixed these with research information, the research information is retained in this public extract. The complete source remains unchanged.



- Backpropagation adjusts weights to reduce output error; ThreeMind has no corresponding training signal. [Nature](https://doi.org/10.1038/323533a0)

## Phenomena that screenshots cannot classify

Reactivation of a similar structure after the same input may arise from Hebbian association, reservoir-state recurrence, a Hopfield attractor, an encoder collision, or residual decay. Synchronized activation/inhibition, migrating hotspots, and apparently corrected label order are likewise not unique signatures. Formal terminology requires repeated perturbation/recovery, basin-boundary, energy, or trajectory evidence as appropriate.

## Current originality judgement

ThreeMind is **not a wholly unrelated new mathematical class**: local coactivity-dependent strengthening and recurrent propagation clearly belong to established connectionist and dynamical-systems traditions. It is also **not a literal reimplementation of Hebb, Hopfield, or reservoir computing**. Its most plausible contribution is the combination of anonymous semantic boundaries, adapter-mediated continuous input, dynamic topology birth/death, associative consolidation and forgetting, local inhibition, lifecycle/provenance audit, temporal-window readout, and a reproducible experiment platform.

Whether that combination produces capabilities absent from matched existing models is an empirical question for the [independent control-experiment plan](../../lab/memos/en/003_control-experiment-module-plan.md). If matched Hebbian recurrent graphs behave identically, the novelty claim must shrink. Stable reproducible differences under matched resources and input would themselves constitute the scientific contribution.
