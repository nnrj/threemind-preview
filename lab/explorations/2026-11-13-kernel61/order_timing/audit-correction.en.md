# R51p audit correction: the waiting state of a newborn subject

14 November 2026. All 352 computation units completed, the host exited with code zero, and no STOP or in-flight marker remained. The first read-only audit stopped at the lifecycle assertion for the first teaching initial state. The frozen `analyze_timing.py` incorrectly required every state to be `active`. The original is a genuine 6.1 state at internal time zero, with no nodes or connections and lifecycle `waiting`: the normal state before the first stimulus. Its teaching endpoint is active at seven seconds, with five nodes and four connections.

The frozen analyzer is preserved. The separate `analyze_timing_v2.py` changes only this lifecycle condition: an initial file at time zero with no nodes or connections must be waiting; every developed state must still be active. The audit records hashes of both versions. The failed attempt created no final analysis.json or audit.json, no Core, no simulated advancement and no scientific result, and changed no originals. Input checks, continuity checks, integration, the four activity measures and preregistered decisions remain unchanged.

The unregistered R51q draft contained the same assertion and was corrected before its freeze. This corrects the audit's use of the existing lifecycle definition; it does not relax checks for dead or incomplete subjects.
