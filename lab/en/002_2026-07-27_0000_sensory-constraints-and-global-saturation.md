# 002 — Sensory Constraints, Fixed Fields, and Global Saturation

[中文](../zh/002_2026-07-27_0000_感官约束与全局饱和.md) | [English](002_2026-07-27_0000_sensory-constraints-and-global-saturation.md)

**Date:** 2026-07-27  
**Status:** implementation-informed observation; controlled replication pending

## Observation set

Several recent runs exposed three related regimes.

1. When a body adapter compressed ambient input into a small, persistent set
   of channels, a newly created network rapidly formed a small repeatable
   structure, often visually triangle-like.
2. When the supplied background itself was effectively fixed or had too few
   changing components, the same limited receptors were repeatedly co-active.
   The network consequently consolidated a stable response pattern rather
   than continuing to produce many short-lived peripheral traces.
3. In late saturated runs, most or all available receptors acquired edges to
   the same connected component. The visualization then looked like one dense
   whole: activity could travel across much of the graph, and new input was
   mostly absorbed by the already-established component rather than producing
   visibly separate, temporary structures.

The third phenomenon is called **global saturation** in this notebook. It
means a single densely coupled connected component under the current input
and plasticity conditions. It does **not** mean a global self, a global
workspace, or a unified conscious experience.

## Implementation audit and proximate causes

The first regime was not caused by a Core rule that draws triangles. The body
adapter's then-minimal projection exposed only a few recurrent channel
identities. Local co-activation could therefore repeatedly reinforce only a
small set of receptor pairs.

The second regime has the same causal shape at a different layer: a fixed
environmental field supplies low sensory variety. Repeatedly delivering the
same or nearly the same pulse pattern preferentially re-touches the same local
edges. Consolidation then wins over forgetting for that pattern. It is an
expected interaction between input statistics and local plasticity, not proof
that the Core has a hidden preference for a particular topology.

The third regime follows when recurrent co-activation and association have
already supplied enough cross-links that local propagation reaches much of the
network. At that point, an incoming pulse has few unconnected receptor pairs
left to differentiate. This is a topology-and-input condition, not evidence
of an intentional whole-network decision.

The current repair separates an always-available dynamic ambient field from
the optional body filter. The ambient adapter supplies a changing baseline and
transient disturbances; the body adapter, if enabled, filters that field. The
default body adapter is off. This makes it possible to compare unfiltered
environmental variety against a restricted sensory body instead of treating
one narrow body projection as the universal baseline.

## Relation to the working hypothesis

These observations support a narrower, testable part of the hypothesis: the
form of sensory access can shape which internal mappings are likely to
stabilize. The network does not receive a human-readable concept of a body;
it receives only the pulses made available by the adapter. A persistent,
low-variety channel geometry can therefore canalize the graph toward a small
recurrent organization.

They also sharpen an important constraint on the hypothesis. Continuous
stimulation alone is insufficient. Its variation, channel diversity, temporal
structure, and route through adapters all matter. A stable pattern may be a
legitimate learned regularity, but a rapid transition to global saturation can
also eliminate the transient, weakly connected material needed to study
forgetting, association, and new mapping formation.

## Biological analogy — and its limit

The closest biological analogy is not “the system has discovered a triangle.”
It is a sensory bottleneck or a restricted receptive field: an organism whose
available sensors repeatedly report a small, regular subset of its environment
will develop and reinforce pathways suited to that subset. In development,
this resembles canalization under constrained input. In the globally saturated
case, broad synchronization is a closer analogy than integration; excessive
synchrony in biological brains can reduce differentiation rather than imply a
richer cognitive state.

These are analogies for experimental design, not claims that ThreeMind currently
reproduces neural development, biological selfhood, or consciousness.

## Required controls

1. Hold Core parameters and seed policy fixed while comparing: dynamic ambient
   field alone, the same field through a body adapter, and a deliberately
   fixed field.
2. Measure channel diversity, receptor count, number of connected components,
   edge density, stability distribution, and the rate of creation and removal
   of isolated/peripheral traces.
3. Sweep body channel count, sampling interval, threshold, adaptation and
   noise independently.
4. For saturation, compare local co-activation against the optional temporal
   association edge-birth policy; report the policy explicitly.
5. Repeat with independent sensory seeds and preserve snapshots plus stimulus
   histories so apparent regularity can be distinguished from one trajectory.

## Recording discipline

Screenshots are useful clues, but screen geometry is not itself graph
geometry. Every future claim about a stable pattern should record the model
package, adapter configuration, stimulus history, seed policy, observer
thresholds, and whether the observed state later decayed, diversified, or
remained saturated.
