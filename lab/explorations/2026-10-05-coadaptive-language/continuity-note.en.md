# E52 · 2026-10-07: system-continuity scope note

Core, expression weights and teaching replay actually continue across stages; this is not stage-by-stage random reinitialization. The old manifest explicitly restarts Adam per update. Complete optimizer, random position and recent windows were not persisted together. Preserve measured co-updates and fixed-adapter controls; add full learning-state support next, without discarding all results or claiming complete continuous restoration.

[R40](../../../docs/en/plans/system-continuity-audit.md)
