# R51t10 recording amendment: remove repeated whole-state hashing

2026-11-15. Added during execution; the original protocol, tool and completed states remain intact.

The first teaching stage took 78.98 seconds. The recorder captured and hashed the complete state before and after each observation, sometimes repeating this check at the same timestamp. These captures include every connection. They test observer neutrality but are not stimuli, scoring operations or additional recorded variables.

Execution pauses after a complete stage. The revised recorder calls the already tested read-only `observation_nodes` method directly. Sampling times, four activity components, inputs, internal advancement order, complete initial/final states, scoring and budgets remain unchanged. On independent codes, both backends and all four switch combinations must produce identical final-state hashes and byte-identical decompressed records with the old and new recorders. Following verification, archival and API registration, execution resumes from the complete current boundary without repeating completed stages.

This is a research-instrument correction. Production kernels, resource reserves and historical evidence are unchanged. The new entry point, `recording_v2.py run`, executes the original frozen plan. The work directory preserves the boundary, exact STOP file, verification and new source hashes. Scientific comparisons and decision rules remain unchanged.
