# Spatial Embedding: Baseline and Experimental Decision

[中文](../zh/spatial-embedding-decision.md) | [English](spatial-embedding-decision.md)

## Decision

The ThreeMind mainline baseline model should keep **causal spatial embedding
disabled**. Spatial embedding remains a valuable, explicitly separate
experimental branch rather than a default condition of the core consciousness
hypothesis.

## Why the distinction matters

In the current runtime, spatial embedding is not a visual-only setting. When it
is enabled together with spatial-neighborhood rules, it changes the causal
dynamics:

- prospective edge creation is rejected when two nodes are farther apart than
  `spatial_radius`;
- associative propagation is attenuated by edge distance and blocked beyond the
  radius;
- optional `spatial_competition` can reduce the activation of a weaker spatial
  neighbor.

Thus, it does not merely render an existing topology in two or three dimensions.
It introduces a structural prior about which nodes may connect and how activity
may travel.

## Current implementation caveat

Node positions are currently deterministically derived from `sensory_seed` and
node ID. They are therefore reproducible, but they are not themselves grown
from the stimulus history. When causal spatial rules are enabled, these assigned
positions act like a pre-laid developmental geometry. This is a legitimate model
choice for a spatial experiment, but it should not be mistaken for spontaneous
spatial organization.

## Mainline baseline

For experiments focused on the original hypothesis, graph organization should
be attributable to direct touch, associative propagation, forgetting,
consolidation, local connection history, sensory adapters, and external stimulus
history. Keeping causal spatial embedding off prevents an unacknowledged
neighborhood prior from determining which paths are possible.

The UI may still offer a two- or three-dimensional **non-causal projection** for
inspection. Such a projection must be visibly documented as visualization only
and must not feed back into node creation, edge formation, propagation, or
competition.

## Spatial branch

A separate model package may enable spatial embedding to test a different
question:

> How do dimensionality, local spatial neighborhoods, propagation distance, and
> competition alter association, clustering, and persistent organization?

Every such experiment should archive the spatial dimensions, position-generation
rule, radius, neighborhood switch, competition strength, seed, and the matching
non-spatial baseline. Results must be interpreted as effects of a spatial prior,
not as evidence that the original non-spatial model requires space.

## Future direction

If future work makes positions themselves change through stimulus-dependent
activity, growth, or embodied feedback, that should be introduced as a new
explicit model hypothesis and tested against both the non-spatial baseline and
the current fixed-coordinate spatial branch.

