# E25: calibrating brief-response readouts without new simulations

Registered 2026-10-02 using the fixed [criteria and provenance](../../../docs/en/plans/response-readout.md). Can existing brief target responses be read directly without requiring 800 ms persistence, while distinguishing missing samples, sampled inactivity and failure to reach sustained stability?

Include all 96 E23 `replication-v2/*/*/*/dense/wait*/cue*/result.json` conditions, all E24 matrix probes, expression conditions and live records including input replay. Exclude teaching stages; never select by favorable response size. Targets A/B retain their original anonymous `priority-memory/1` channel identities, not the most active nodes after observing the result.

Record response status/count, simultaneous sample rankings and single-point/boundary flags, alongside unchanged local pattern/amplitude stability, global classification and original probe availability. Check uncued controls and verify every reported activation against its source sample. Unavailable windows remain unavailable, not zero. Reanalysis supplies no new independent experimental replications and does not retroactively replace original primary criteria.

Budget: no Core advancement or training, at most 400 result records, 600 seconds offline computation, 512 MiB new-file hard limit, one process below 2 GiB RSS. Retain 2 GiB system RAM, C 5 GiB, E 15 GiB. Read only specified evidence. Hash source results, trajectories and states before/after. Publish designs, reports and derived evidence in a separate project.
