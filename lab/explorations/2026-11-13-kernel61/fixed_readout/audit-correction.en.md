# R51k read-only audit correction: the active-node index

13 November 2026. All eight sources completed computation. After reading every source and 2,024 states, the original analysis stopped at line 137 of `audit_readout.py`: its intervention whitelist omitted `active`. The original tools, frozen copies and failure record are retained.

The `active` field indexes active nodes. The existing public configuration operation calculates node states at the unchanged current time and removes nodes whose activation has decayed to zero. All 32 saved plasticity operations follow this rule. Independent arithmetic using each earlier activation, state time, decay constant and zeroing threshold reproduces the resulting activation and index. Internal time, event sequence and queue remain unchanged.

`audit_readout_v2.py` explicitly requires this formula and index agreement before retaining all original continuity, matching, restoration, reader-state and inference checks. It does not allow arbitrary index changes. The new entry point, `analyze_v2.py`, uses the original `endpoint_view`, `summarize_unit` and `goals`; scores and scientific stopping rules are unchanged. State metadata are checked during causal file auditing, followed by one pass over any remaining files, avoiding duplicate traversal. Per-source scores are saved with source hashes to support interrupted read-only processing.

Only postprocessing tools change. Subjects, teaching, interventions, tests, originals and production Core remain unchanged; no student is rerun. This correction and its tool hashes are recorded before execution.
