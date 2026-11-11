# continuous-memory/5.1 optimization delivery and verification

2026-10-13. [中文](../../zh/plans/local-events-v51-delivery.md). Kernel engineering, not a new shape/color or consciousness-capability experiment. The user approved the optimization direction and explicitly named version 5.1. [Authority and boundaries](local-events-v5.md) · [Dialogue source](../history/sources/2026-10-13-kernel-performance-audit.md)

## Identity and scope

New `threemind.continuous-memory/5.1`, state schema `threemind.continuous-memory-state/5.1`, preserves `/5` formulas, numerical defaults, event ordering and research options. `/5`, `/4`, `/3.1` and `/2` remain available; the application default remains `/3`. No individual is migrated; cross-version restoration between 5 and 5.1 is explicitly rejected.

Rust compiles shared transitions in `local_shared.rs` with separate representations: historical `local.rs` retains string clocks, BTreeMap and JSON, while `local51.rs` supplies the new representation. This avoids duplicating scientific rules or adding new-container runtime overhead to historical kernels. Python remains the readable independent reference, adding only configuration-derived caching.

| Phase | Implemented change and reason | Behavioral boundary |
|---|---|---|
| P0 | Frozen pre-change sources/binaries and 30 configurations×18 boundaries×2 backends, with complete-state/readout witnesses | Fresh engineering fixtures only; no formal student restoration or E67/E68 alteration |
| P1 | Scalar reads replace full Edge clones where already settled; cache the configuration-only eligibility period factor | No merged learning, transmission or genuine settlement; configuration changes invalidate the cache |
| P2 | Numeric object/event local clocks and typed hot internal signal packets | Original string/JSON save shape, u 128 range, leading zeros, IDs, ordering and same-time phases retained; other messages and STP/fast-trace clocks are not comprehensively rewritten |
| P3 | Compact node/edge slots addressed by scientific ID, with original sorted traversal | Reused physical slots never reuse scientific IDs; delayed messages retain IDs; adjacency/deadline/queue ordering stays unchanged |
| P4 | No new expiry-skipping algorithm in this release | Unchanged-deadline suppression already existed in 5 and is not reported as a new gain |
| S study | Feasibility audit only; periodic stability recurrence retained | No proven bit-equivalent skip algorithm preserving earliest deletion time is established |

No global dynamics sweep, shortened input, skipped simulation events, altered step, disabledH, reduced graph limit or deleted research evidence is used to obtain speedup. Timing, capture and validation tools do not advance simulated time.

Compact slots reuse holes but capacity may remain at an individual's historical maximum simultaneously live population; deleting objects does not promise immediate return of all process memory. ID safety and short deletion/rebirth sequences are checked, while long large-scale churn/resident-memory behavior remains unmeasured. Snapshots omit physical slots and rebuild them from scientific IDs.

## Preservation and recovery

The final isolated native build passes 189 checks: 30-configuration frozen /5 traces; exact same-backend 5→5.1 boundary equivalence; existing Python/Rust tolerances; cache reconfiguration; complete-state restore and next input; observation/batching invariance; idle reclamation, deletion/reuse, dormancy/awakening, source/arrival/phase options, learning/decay ablations, strong inputs, local/shared energy and restored-message validation. Audit counters remain in full comparisons. Only declared identity fields and their validated derived definition hash are normalized.

20 Rust Core tests, 40 independent Runtime/world SQLite tests and 4 desktop/narrow creation tests pass. TypeScript/Vite builds pass.248 historical regression checks passed; 3 new Runtime cases initially used the old executable and failed, then passed in the 40-case rebuilt Runtime suite. Counts describe engineering checks, not independent scientific samples.

The first Lab batch passed 81 checks; its catalog test initially omitted 5.1 from the local-parameter classification and passed after extension. The additional full-host/prepared/template/bundle batch passed 52 checks and exposed the real host-routing defect below. After repair, 4 focused checks passed, including actual prepared→template→edit→start→ordinary Worker claim for default 3, 3.1 and 5.1, plus catalog-wide capability uniqueness. Batches overlap and are not summed as independent samples. The isolated database was stopped afterwards.

### Additional fix: minor-version host routing

The former `kernel_id.split('.')[-1]` naming collapsed both 3.1 and 5.1 to `worker.kernel_1`, whereas SQL requires `worker.kernel_continuous-memory3.1` and `worker.kernel_continuous-memory5.1`. Normal workers could not claim those jobs. A shared function now strips only the `threemind.` namespace, retaining the minor version for capability probes, default workers and data-package resumes. Integer-version names are unchanged.

This repairs host task matching, not Core rules or simulated time. Old ordinary-run SQL requirements were already correct and can match refreshed workers. Previously queued data-package resumes explicitly carrying the wrong `worker.kernel_1` are not silently rewritten; affected requests require separate inspection/resubmission. No live database task was modified. Installation is recorded at closeout.

### User follow-up: assess naming, no rename this release

The user permits a feasibility/necessity assessment but explicitly rules out renaming this release. `threemind.continuous-memory/5.1` already expresses namespace, family and minor version clearly. Faulty parsing caused this bug; replacing the dot with a dash would not fix arbitrary string slicing.

Recommendation: retain stable scientific IDs. A future catalog may expose explicit `family`, `version` and display-name fields, with consumers looking up the whole `kernel_id` rather than splitting it independently. Those fields are not introduced here. Display labels or documented aliases are cheaper than replacing canonical IDs. The latter affects definition hashes, restoration, templates, tasks, packages, reports and historical links, requiring explicit compatibility while retaining old identities and originals. **A full rename is feasible but currently does not justify its migration cost and is not a prerequisite for performance optimization.**

## Stability S boundary counterexample

The existing recurrence updates eligibility, then decays/clamps stability, then decays weight using the new stability, with same-time transmission exemptions and strict pruning. A shortcut must also preserve first crossing time, phase anchors, deadlines and restored behavior.

Constructed numerical witness: disable stability decay and actual transmission, fixed S=.57, initial weight=.008599243778434221, period=.1 s, forgetting=.025. After 73 successive products yield .007999999999999997; exponentiation yields .008. At the default .008 strict deletion threshold the decisions differ. **This is an engineering boundary counterexample, not evidence of an observed formal-experiment failure.** S recurrence therefore remains unchanged; any proposed numerical/event-order change requires separate authorization.

## Evidence and reproduction

Generated originals remain ignored under `.work/memory51-validation/`: `baseline/`, `reference-traces-r2/` (1,080 boundary observations), `stability-lazy-feasibility.json`, and `wheels-final/`. Tracked `tests_v2/local51_baseline.py` contains compact digests only; `tools/memory51_witnesses.py` recreates independent engineering fixtures.

Performance separates Core advance, injection, observation, state construction and encoding. Process peak working set/commit and CPU include construction, capture and verification and are not Core-only memory/CPU. Repetitions and source/binary hashes are retained; numerical results appear below. No new formal research experiment or manuscript edit is included.


## Final performance and phase attribution

Native Rust Release, same workstation, alternating order, 1 warmup+7 measurements per condition; medians measure Core wall-clock advance. Main matrix: 9 workloads×6 arms×8 rounds=432 executions; 64 phase executions and 8 pre-change executable preservation checks give 504 listed engineering runs. Warmups/checks are not independent scientific samples.

**Relative to 5, 5.1 reduces default H cost 49.58–60.38% across all 9 conditions and S cost 51.27–58.11%. This is a clear optimization gain, but not universal dominance over 2.** Dense 16–128 default H remains 57–68% slower than 2; small sparse 64 remains 56% slower. Sparse 256/1024 saves 21.6%/73.7%, and neighbor 256 saves 19.7%. Against 3.1, dense saves 10.2–16.4% and sparse 1024 saves 73.4%, but sparse 64 is 42% slower. The 2.1% median improvement over 3.1 inbursts has overlapping ranges/outliers and is not treated as a clear advantage.

Table entries are real seconds. H/S select edge forgetting; automatic node support still has its own H. S is not an all-H-off condition. Versions 2/3.1 are external performance references with different mechanisms; 5 vs 5.1 is the matched-dynamics comparison. Actual nodes/edges are identical across versions in each row; 5/5.1 complete final states match after declared identity normalization only.

| Workload (nodes/edges; simulated s) | /2 | /3.1 | /5 H | /5.1 H | /5 S | /5.1 S |
|---|---:|---:|---:|---:|---:|---:|
| Dense 16/240; 2 s | 0.016738 | 0.030214 | 0.052208 | 0.026325 | 0.056672 | 0.027495 |
| Dense 32/992; 2 s | 0.065968 | 0.125383 | 0.233394 | 0.106785 | 0.231884 | 0.108721 |
| Dense 64/4032; 2 s | 0.297058 | 0.559160 | 0.974748 | 0.467614 | 1.003135 | 0.471931 |
| Dense 128/16256; 2 s | 1.331457 | 2.493283 | 4.900086 | 2.239047 | 5.022935 | 2.223021 |
| Disjoint pairs 64/64; 100 s | 0.131977 | 0.145340 | 0.461954 | 0.206346 | 0.625205 | 0.266723 |
| Disjoint pairs 256/256; 100 s | 0.245750 | 0.265132 | 0.485976 | 0.192567 | 1.095066 | 0.458767 |
| Disjoint pairs 1024/1024; 100 s | 0.737482 | 0.729593 | 0.470250 | 0.194193 | 2.447603 | 1.077302 |
| Neighbor pairs 256/512; 20 s | 0.043768 | 0.049466 | 0.079593 | 0.035146 | 0.240928 | 0.109585 |
| Bursts 64/4032; 10 s | 0.513567 | 0.835550 | 1.788551 | 0.817896 | 2.674371 | 1.303120 |

Default H phase attribution: dense 64 nodes/2 simulated seconds and pairs 1024 nodes/100 seconds. Independently compiled variants retain identical complete final states.

| Workload | /5 | P1 | P1+P2 | P1+P2+P3 |
|---|---:|---:|---:|---:|
| dense | 0.899371 | 0.827256 | 0.486957 | 0.433993 |
| pairs | 0.437485 | 0.415343 | 0.198476 | 0.182027 |

P2 time/message representation is the main contributor: 41.1% less dense cost and 52.2% less sparse cost on top ofP1. P3 adds 10.9%/8.3% overP1+P2. Parsing/construction/copying were substantial implementation costs, not unavoidable local-dynamics costs. Deadline trees, local scheduling and real retention mechanisms remain necessary work; this does not establish that every local architecture beats scanning. The release therefore stops wider container/deadline rewriting, retains P4 behavior and does not implement lazy S skipping.

Component medians below; process resources cover the whole engineering executable, including capture/encoding/validation, not Core-exclusive memory/CPU or complete media/database/peripheral/replay costs.

| Workload | Arm | Injection ms | Capture ms | Encoding ms | Observe ms | Process CPU s | Peak working set MiB | Peak commit MiB | State JSON bytes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dense | 2 | 0.739 | 19.570 | 7.422 | 0.120 | 0.54688 | 62.58 | 60.85 | 2059927 |
| dense | 3.1 | 0.711 | 21.544 | 8.417 | 1.155 | 0.82812 | 69.00 | 70.73 | 2297693 |
| dense | 5-h | 0.679 | 25.503 | 11.543 | 4.179 | 1.32812 | 75.37 | 76.49 | 2666628 |
| dense | 5.1-h | 0.763 | 24.190 | 10.139 | 2.386 | 0.79688 | 73.21 | 74.33 | 2666637 |
| dense | 5-s | 0.796 | 24.766 | 9.275 | 3.553 | 1.31250 | 75.10 | 76.23 | 2663575 |
| dense | 5.1-s | 0.887 | 24.150 | 8.782 | 1.897 | 0.78125 | 72.87 | 74.02 | 2663584 |
| pairs | 2 | 2.263 | 6.337 | 2.518 | 0.071 | 0.84375 | 24.20 | 21.74 | 729050 |
| pairs | 3.1 | 2.342 | 7.208 | 3.080 | 0.469 | 0.82812 | 26.80 | 24.16 | 826711 |
| pairs | 5-h | 2.130 | 10.332 | 4.118 | 1.785 | 0.60938 | 32.83 | 32.03 | 1116855 |
| pairs | 5.1-h | 1.800 | 10.545 | 4.012 | 0.994 | 0.34375 | 32.13 | 31.27 | 1116864 |
| pairs | 5-s | 4.121 | 10.079 | 4.280 | 1.762 | 2.59375 | 32.98 | 32.20 | 1117460 |
| pairs | 5.1-s | 3.002 | 10.714 | 4.463 | 0.882 | 1.21875 | 32.41 | 31.43 | 1117469 |

No nodes or edges were removed to gain speed. State JSON is exactly 9 bytes larger for 5.1 in every matched condition because of declared identity strings; runtime slots/caches are not saved. Dense 64 H process peak working set changes 75.37→73.21 MiB, sparse 1024 changes 32.83→32.13 MiB, while some small cases increase slightly. **This is not a substantial memory-compression result.** All samples/ranges/counters remain available; sparse 1024 S still performs 897382 expiry checks versus 3942 for H.

Evidence: `matrix-dense/`, `matrix-pairs/`, `matrix-chain/`, `matrix-burst/`, each with source/binary SHA-256 and per-round results in `summary.json`; phase results in `stages-r2/measurements/`; `frozen-binary-preservation.json` checks 2, 3.1 and both 5 modes against pre-change executables on both workloads. This new same-batch comparison does not overwrite historical measurements.

## Installation and use

The final verified wheel is installed in `.work/kernel-venv`; installed .pyd bytes match the wheel hash. Fresh 2, 3.1, 4, 5, 5.1 engineering samples pass exact restore/continuation checks. Receipt: `installation-receipt.json`. Frontend production assets and standalone Rust Runtime are rebuilt. No database migration or live research-task edit is required. No Python host or 8877 listener was present before installation; no resident service was started.

On next ThreeMind startup, select `continuous-memory/5.1`, then its template and parameters. Existing individuals retain their versions; 5 checkpoints are not silently converted. Application default remains 3; no unified rename this release. Shape/color accuracy, long-term retention and multi-seed research remain separate future work, not conclusions from engineering throughput.
