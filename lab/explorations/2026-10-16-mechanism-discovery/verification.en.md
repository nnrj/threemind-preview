# Preparation verification and unexecuted work

[中文](verification.zh.md) · [Package](README.en.md)

16 October2026. Verification concerns offline tools/preparation, **not M1–M7 experimental effectiveness or actual apparatus acceptance**.

| Check | Outcome | Scope |
| --- | --- | --- |
| Preparation structure | Seven packages valid, all launch gates pending, execution_authorized=false | Valid format is not launch readiness |
| Selected evidence | 26/26 size/SHA256 matches,1,445,148 bytes | Two match existing relocation receipts; others are review snapshots, without full platform readback or recomputation |
| Isolated tests | 48 pass | No Core, database, service, network or subjects; covers mismatch/missing files, path escapes, missing/changing whole-state components, scope rejection and power calculations |
| Statistical cross-checks | Continuous simulation agrees with noncentral-t power; binary simulation agrees with exact enumeration | Numerical verification, not independent scientific replication |
| Static checks | Ruff passes for both new Python files | Existing runtime code unchanged |

Commands are in [README](README.en.md). Initial pytest setup encountered inaccessible Windows default temporary directories. Unique ordinary workspace fixtures then completed all checks without database startup or permission changes. Full audit/power JSON resides in ignored `.work/mechanism-preparation-20261016/`; test counts come from the actual pytest output in this turn. Synthetic fixtures are not formal individuals.

## Computed planning scenarios

Seed20261016,10,000 replications per candidate N, two-sided family error0.05 conservatively divided by comparison count. Select only when the Monte Carlo95% power **lower bound** reaches0.8.

| Assumed scenario | Power at48 with interval | Power at128 | Conditional decision |
| --- | --- | --- | --- |
| Normal origin-level paired differences,d=0.5,3 comparisons | 0.8290 [0.8215,0.8363] | 0.9987 | 48 |
| Normal paired differences,d=0.5,4 comparisons | 0.7985 [0.7905,0.8062] | 0.9983 | 64; power0.9198 [0.9143,0.9250] |
| One paired binary outcome/origin,difference0.10,baseline0.50,discordance0.30,4 comparisons | 0.0569 [0.0525,0.0616] | 0.2755 | Insufficient by128; redesign measurement |

Detailed files are `M1-continuous.json`, `M2-continuous.json`, `M3-binary-sensitivity.json` in the ignored directory. Names identify planning discussions, **not final estimators or chosen package sample sizes**. Original autonomy criteria include cross-source requirements; the third row is not power for that entire instrument. It illustrates the cost of sparse binary endpoints. Discordance0.30 is assumed, not estimated from new pilots; simulation intervals exclude assumption uncertainty.

Before formal execution use eight-origin pilots to estimate variation, nesting and pairing, then simulate the frozen estimator/family. Repeated questions can improve within-origin precision but cannot increase independent N. Separate delay cohorts add cultivation cost. If128 remains insufficient, improve measurement, narrow the primary question or redesign before confirmation; never choose endpoints after outcomes to obtain significance.

## Delivery boundary

Completed: bilingual program, stable R mapping, M1–M3 protocols, claim/evidence/alternatives matrix,26 selected source/summary identities, official abstract-level literature starting points, structural validation, streaming hash/witness comparison, power planning and isolated tests.

Pending: full platform original readback and endpoint recomputation, systematic literature comparison, concrete5.1 intervention adaptation/side effects, actual truth-isolation and observer-invariance acceptance, whole-state restoration, concrete task-table freeze, eight-origin pilots, formal N, confirmation and independent replication. No M1–M7 formal research records, experiment numbers or execution receipts were created. No new orchestrator replaces the unified API.

No individuals were created/loaded, simulation advanced, resource thresholds changed, E69/bounded retraining resumed, schedules activated, user services started/stopped, Core or author manuscripts modified. The user's pause and protocol gates govern later execution; tooling success does not remove them.
