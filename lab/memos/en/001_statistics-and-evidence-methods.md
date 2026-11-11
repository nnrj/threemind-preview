# 001 — Statistical Measures and Evidence Methods

[中文](../zh/001_统计指标与证据方法.md) | [English](001_statistics-and-evidence-methods.md)

## Purpose

Define common, exportable measures for per-tick dynamics, recurrent structures, temporal convergence, forgetting, and interventions. The analytics module remains outside Core: it reads output-bus frames, history, and frozen snapshots without participating in activation, propagation, inhibition, association, plasticity, or forgetting.

## Node and local-response measures

For each observation window preserve at least:

- first-active, peak, last-active, and exit tick;
- active duration, longest consecutive run, and re-entry count;
- peak, mean, activation integral, and integral above baseline;
- inhibition integral and direct/associative contact counts;
- tail persistence, support, stability, and their changes;
- actual propagation order and edges when traced. Never infer a causal path backward from a final state when no trace exists.

## Recurrent structures and response clusters

- anonymous structure signature, node set, and edge set;
- occurrence count, duration, interval, and source distribution;
- Jaccard similarity, cosine similarity, and trajectory distance across repeated probes;
- convergence latency, stable-set size, tail variation, and within-/between-cluster distance;
- distinguish residual decay, periodic oscillation, and stable response candidates;
- use labels only as offline annotations; anonymous nodes and edges define identity.

## System-level measures

- total activation, total inhibition, and active-node count;
- activation entropy, top-k concentration, or Gini coefficient;
- hotspot count, lifetime, migration speed, and revisit rate;
- node/edge counts, edge-weight and stability change rates, degree distribution, clustering, and connected components;
- effective propagation range, saturation ratio, topology birth, and forgetting rate;
- activation–inhibition lag, cross-correlation, and integral ratio;
- relation between fast activity and slower topology timescales.

## Statistical principles

1. Run paired trials from frozen snapshots; report independent seeds, repetitions, effect sizes, confidence intervals, and negative results.
2. Export tabular measures as CSV and per-tick events/sparse trajectories as JSONL; archive model packages, configuration, and checksums together.
3. Distinguish “trace not recorded” from zero; never fabricate missing dynamics from a final state.
4. Store raw observations, deterministic statistical summaries, and human/AI interpretations in separate layers.
5. Visualization downsampling must not modify source data; charts must declare window, baseline, sampling rate, and filters.
6. An activation budget or energy variable may be an explicit ablation condition, never an assumed default explanation of Core dynamics.

## Minimum evidence package for a paper

Every primary claim should trace to a protocol version, initial-snapshot checksum, model parameters, adapter state, seed, stimulus frames, raw per-tick or explicitly sampled records, analysis-code version, and final figures. Readable labels cannot replace anonymous primary data.
