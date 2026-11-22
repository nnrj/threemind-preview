# 6.1 local deletion and sender thresholds — engineering contract

Approved on 2026-11-13: local deletion by default, optional whole-graph deletion, separate activation/inhibition sender thresholds, and equivalent emission optimizations. This is a new version, not a repair of historical 6.0 instances. No existing research subject, original, or manuscript is changed.

## Changes and fixed scope

- `deletion_strategy`: `local` (default) or `global-scan`. Local deadlines use the single-age curve's analytic crossing and the existing structure-check grid. Arrivals, novelty and emissions precede deletion at the same internal time. Actual value is checked again before deletion. An indexed queue replaces each object's prior deadline; it does not accumulate stale events. Isolated inactive nodes have their own support deadline.
- `activation_send_threshold=0.004`, `inhibition_send_threshold=0.002`: source-state thresholds, separately applied to offers and future emission scheduling. Zero disables the respective gate for positive activity. Incoming activity may restart emission. Existing node zeroing, connection signal threshold, STP, energy and learning rules remain distinct and unchanged.
- Equivalent optimizations: typed cached configuration, numeric runtime timestamps for short-term edge state, fewer edge copies and redundant allocations. Restore/export retains explicit state and version identity.
- 6.0 retains its original defaults and implementation. 6.1 becomes the new-instance default after checks pass. Previously registered 6.0 experiments remain paused; this engineering task does not relabel them as 6.1 experiments.

## Required checks and completion rules

1. Python/Rust agreement for both deletion strategies, all four curves, both age policies, retention relaxation, dormancy, finite energy, in-flight policies, reproduction and restore.
2. Local expiration: no full-graph deletion visits; idle edges still expire; reinforcement replaces deadlines; same-time reinforcement precedes deletion; isolated nodes expire; missing local deadlines are rejected; save/observation and advance partitioning do not change evolution.
3. Separate gates stop subthreshold recurring sends and wake on new inputs; zero gates with global deletion reproduce 6.0 on fixed witnesses after removing only version/config identity differences. Equivalent optimization may not discard events or change resource spending.
4. Bounded engineering benchmark reuses R51b's 1,024-node/edge and 4,096-node/edge fixtures. Compare 5.1, frozen 6.0, 6.1 global/zero, 6.1 local/zero, 6.1 global/default, and 6.1 local/default. Report actual state sizes, timer counts, wall time and process memory separately. Do not infer long-duration novel-input network growth from fixed topology.
5. Invalid state or failed semantic check blocks release. Performance above the approved 2x 5.1 gate blocks scientific resumption, even if the implementation itself passes. Preserve all negative results.

This protocol measures engineering behavior, not new organism learning. Expected benefits are removal of repeated weak emission work and deletion work proportional to affected objects. Local timers may increase storage per edge; this cost must be measured.
