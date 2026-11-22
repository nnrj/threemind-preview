# R51k continuation at a complete-source boundary

13 November 2026. After completing sources o0 and o1, the frozen runner reached 1,074,475,008 bytes of private memory and stopped under its 1-GiB host budget. There is no incomplete unit. Commit, physical memory and C/E storage still meet the 5/4/5/25-GiB reserves.

The runner retains its previous `result` while calling the next `measurement.unit`. Loading o0's 40,463,715-byte JSON in a read-only diagnostic increased private memory from 9,306,112 to 194,539,520 bytes; releasing it reduced usage to 11,812,864 bytes. Thus retaining a completed result adds about 176.65 MiB. No Core was created or advanced in this diagnostic.

A separate continuation tool verifies the completed sources and checkpoint hashes under the lock, archives the exact STOP and previous host/resource records, and retires only that matching active STOP. Sources o0 and o1 are not rerun. Each remaining source, o2–o7, calls the unchanged frozen `measurement.unit` in its own serial host, which exits upon completing the entire source. Teaching, calibration, ordinary questions, correction and causal copies remain continuous within each complete individual. Frozen code, case table, sample size, 1-GiB limit, cumulative two-hour budget, storage limits and scientific rules are unchanged.

Any new STOP is preserved and halts continuation; it is not automatically retired. Resource and elapsed-time summaries retain the initial budget crossing. The change concerns host lifetime between independent sources, not scientific operations or Core dynamics. After R51k, the author's newly requested inertial-response investigation precedes the remaining batches.
