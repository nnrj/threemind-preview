# AS63-01: Evidence-storage allowance and complete-state continuation

17 November 2026. This is an engineering amendment during execution, not a scientific protocol revision.

The initial 3GiB allowance for originals came from three independent apparatus stages. The first four formal populations used204,824,345;202,896,609;205,972,903; and207,807,010bytes. Their mean projects approximately3.06GiB for16populations, slightly above the allowance. Approximately43GiB remains free, preserving the existing25GiB reserve. To complete the authorized16populations without discarding evidence, increase each allowance for originals, archive, and complete API readback from3GiB to4GiB. The six-hour computational limit, memory limits, and minimum disk reserves remain unchanged.

Retain the original protocol, executor, frozen manifest, and every completed individual. The added executor changes only the storage allowance and supports continuation of the currently paused stage from complete state. Seeds, candidates, sensors, dynamics, birth rule, timing, curriculum, selection, controls, measurements, and statistical criteria remain unchanged. No experienced interval is rerun.

Before continuation, an independent apparatus check using seed1117099 pauses a three-second process at a complete step boundary at1.2internal seconds. Continuing from that state reproduces the uninterrupted process's entire inputs, actions, trajectory, and final complete state exactly. This instrument material is excluded from the formal sample.

Use the original host's existing STOP check to save at the next complete step boundary, including the Core, readout host, input queue, body, energy supplier, and external scheduling clocks. Preserve the interruption evidence and marker, verify that the original worker has exited, then resume through the added executor. Completed stages are read only. The interrupted stage retains all earlier trajectory rows and runs only its remaining internal duration. Host pause time never enters simulated time. The interruption evidence remains beside the completed result.

The added executor is a reviewable copy of study.py with changes restricted to storage allowance, continuation entry, and host-time accounting. It is not a new kernel. Pre-pause host time is estimated from the existing progress record and its timestamp; that population's host duration is marked as estimated. Scientific time and outcomes are audited exactly. The separately registered layout conditions and their1GiB allowance remain unchanged.
