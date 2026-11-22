# R51t read-only audit correction: compare declared observation scopes

14 November 2026, following audit v2. Scientific computation is complete and no individual has been rerun. Before scientific scoring, v2 incorrectly required task-node arrays and all-node arrays to be identical in four instrument comparisons. The frozen case table explicitly assigns `scope=task` to the former and `scope=all` to the latter. Task-only records contain five task nodes at each time; all-node records also include background nodes.

Independent verification found exact agreement at all 1,502 samples in each of the four comparisons when both records use the declared task-node scope: 6,008 samples total. Each pair also has identical complete Core hashes at the shared pre-cue and final snapshots, totaling eight matching snapshots. Intermediate snapshot schedules differ, so all jointly saved snapshots are compared without requiring files at times that were not scheduled for both conditions.

New `analyze_timescales_v3.py` retains v2's empty-bus schema correction and checks observation controls at their frozen scopes. It first verifies both scope declarations, then compares every task-node field, time and life state at every sample, together with the shared complete snapshots. Scores, sample size, materials, interventions, thresholds and scientific stopping rules remain unchanged. Both earlier scripts and failure records are retained. This correction does not announce scientific findings.

Evidence is in the workspace's `audit-amendment-v3/proof.json`. The current read-only entry point is `analyze_timescales_v3.py --work <workspace>`, which first verifies the qualified v3 storage entry point. It reads saved materials and writes analysis without constructing or advancing a Core.
