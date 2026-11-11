# Preserve learned motor translations while correcting errors

2026-10-07, R41. The user proposed revisiting previously correct examples alongside each new correction. The assistant accepts this as a priority next-batch comparison. **Not implemented; E62 weights, learning rules and results remain intact.**

## Evidence

The current peripheral already rehearses samples, but retains only the latest256 in a FIFO. On unchanged old activity records, pre/post-correction pose MSE changes0.0430→0.1365; on new-cache records it changes0.3752→0.00553. New fitting therefore accompanies degraded earlier translation, independently of rerunning Core. Eviction, coverage, step size and capacity have not been isolated. [Report](../../../lab/explorations/2026-10-07-continuous-development/report.en.md).

## Minimal comparison

1. Branch one complete organism into current recent-cache, historical random-retention and representative-history mixture conditions. Each continues its own weights, optimizer, Core, body, recent output and RNG; no head replacement. Declared between-group training differences are allowed.
2. Rehearse previously correctly translated teacher examples alongside corrections, retaining representative actions, directions and teaching stages. Start with a1:1 old/new mixture as a peripheral training arrangement, without injecting semantic labels or prescribed behavioral preferences into Core.
3. Match update counts, batch size and total cache capacity. Test larger capacity separately, not as evidence for mixture alone. Previously correct translation is defined using teacher supervision and independent output error, not teacher-assisted physical arrival.
4. Do not reinforce an old erroneous label when teaching explicitly corrects it; retain provenance and correction records. Held-out questions/answers never enter rehearsal.
5. Measure frozen old/new-record translation and independent closed-loop action. Cache fit alone is insufficient. If reliable behavior emerges, test Core contribution with the same frozen reader and connection silence/restoration.

This concerns retention in the motor peripheral, not Core forgetting, plasticity or strong-stimulus rules. Normal growth retains the latest complete state, without best-head rollback. New cache strategies need explicit configuration/versioning and complete save/restore; E62 remains the old-rule baseline.

## Relation to centered-object diagnosis

R39 separates recognition from scanning/search. New single-object teaching still starts with blank Core and its own new peripheral, not E56/E62 knowledge. It may reuse validated shared reading and a declared training procedure. A preliminary R41 retention comparison may use complete E62 copies; that is a peripheral-training diagnostic, not the new centered individual's developmental history.

[Centered objects](centered-object-and-body-calibration.md) · [Continuity](system-continuity-audit.md) · [中文](../../zh/plans/motor-rehearsal.md)

## 2026-10-07: E63 execution begins

The user approved continuation. Three cache policies keep complete individual systems with equal capacity and update counts. E62 evidence is unchanged. See [E63](rehearsal-centered.md).
