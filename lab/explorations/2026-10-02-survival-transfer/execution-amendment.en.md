# E27 execution note: parallel independent candidates

Recorded 2026-10-03 after the first formal candidate completed, before expanding concurrent execution.

The initial design used one process. Observed memory was about 0.5 GiB per candidate, with about 13 GiB still available and eight physical CPU cores. The first 218 simulated seconds took about451 wall seconds. Under the user's authorization to adjust resources, execution may now use at most three independent simulation processes, together below4 GiB, preserving2 GiB available memory and the original disk, account and aggregate four-hour compute budgets. The900 wall-second limit per case remains; concurrent process durations are added, not discounted.

This changes scheduling only. Protocols, seeds, mapping, the600 simulated-second horizon,40300 initial reserve,10100 units per qualifying grain, birth and death rules are unchanged. No live host/process telemetry enters Core. Each case has a separate directory; another process never takes over a started case. Completed cases are read back and never counted as additional samples.

The first case earned no food. That result checks accounting and resource costs; it does not justify changing task difficulty or energy rules. Runner signatures distinguish execution revisions. Engineering calibration remains separate from formal samples.
