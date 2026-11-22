# R51t7 supplement 2: the excitatory signal-amount threshold

14 November 2026. Replacing inhibitory transmission alone failed in both curriculum blocks. It removed the first discrepancy at 3.3 seconds, but weights and recent-transmission states still diverged from 3.5 seconds. Source inspection identified another difference: 5.1 truncates excitatory signals below 0.004, whereas the default 6.2 connection threshold is 0.0004. The full-emission replacement is still running. The following conditions have not yet been run.

The last two candidates allowed by the original protocol are:

3. Stability-based retention and immediate novelty, with the 6.2 excitatory connection threshold set to 0.004. Inhibition retains the 6.2 rule and its 0.0004 threshold.
4. The same excitatory threshold combined with the old inhibitory-transmission rule from supplement 1.

Together with the corresponding lower-threshold references, these conditions test the threshold and its interaction with inhibitory transmission. The old 5.1 emitter also checks the amount before short-term resource release. These candidates change only the existing 6.2 post-release threshold; matching that value does not make the full emission rules identical.

Both use existing configuration fields and the calibrated research implementation. Production code remains frozen. Two blocks and three stages per block give 12 additional stages. Teaching, intact parents, diagnostic copies, recording and the original recovery criterion are unchanged. Recovery in candidate 3 establishes sufficiency of the threshold adjustment in the stability/immediate configuration; recovery only in candidate 4 establishes sufficiency of the combined changes. Failure rejects those sufficiency hypotheses. No result changes production defaults automatically.

This exhausts the four-candidate allowance. No further parameter search is added. The original allowance of 16 post-teaching copies remains available to exchange weights or transmission configuration among completed candidates and distinguish formation from expression. These rules are fixed before the additional data are produced.
