# /5 versus /3.1 and /2: performance retest, 2026-10-13

[简体中文](../../zh/plans/memory5-performance-comparison-20261013.md)

## Conclusion

**/5 is not universally faster. It is slower than both /3.1 and /2 on the continuously active dense graphs tested here. On a 1,024-node, low-degree graph receiving rotating local inputs, default /5 reduces advancement time by 37.8% and 38.6%, respectively.** Small sparse graphs remain slower. Local execution does not automatically improve speed: this implementation has material scheduling and object-management costs, without disproving local mechanisms themselves.

The user subsequently authorized disabling half-life mechanisms in temporary engineering subjects to test the cost. Existing configuration can disable node and connection H separately without changing Core. **In the dense comparison, disabling both reduces median time by only 0.7%, with substantially overlapping sample ranges: no clear improvement was measured. On the 1,024-node sparse workload, the complete no-H configuration instead takes 5.74 times as long.** These results do not support the current no-H replacement configuration as a performance remedy, or H alone as the primary explanation for /5's slowdown.

These are kernel engineering workloads, not shape/color accuracy, learning, or artificial-consciousness results. This report supplements rather than replaces earlier delivery evidence.

## Scope and method

- Rust release engineering entry point, source baseline `8e9b68f8cf4d7f96fe7ee71a671fbba0b4ddb024`. Only benchmark inputs and configuration arms were extended; production kernels, application defaults, and historical individuals were unchanged.
- One warmup followed by seven measured repetitions per configuration and size; tables report medians. Configuration order alternates forward/reverse each round. Runs are serial to avoid competition between benchmark arms.
- Each repetition creates a separate blank temporary engineering object with seed=223. Each object receives its prescribed inputs and advances continuously; no formal research individual is read, restored, or rolled back.
- Inputs arrive every 50ms of simulated time. `dense` stimulates all n channels together; `pairs` rotates through disjoint two-channel packets. Amplitudes follow a fixed formula; ordinary learning and propagation remain enabled.
- All shared configuration fields of /2, /3.1, and /5 match, including the original 10ms solver interval, 100ms propagation interval, co-stimulus rule, and unlimited propagation/learning quotas. /5 does not use the old whole-graph solver scan; matching fields do not imply equivalent dynamics.
- Injection, Core advancement, capture, JSON encoding, and observation are timed separately. Advancement excludes database work, file writes, compression, UI, video, process startup, and Python wrappers. Capture and observation are checked for state-hash preservation.
- Repeated final-state hashes match within each arm, size, and workload. Tables show measured graph sizes, not inferred sizes. Weights, activity, and state formats differ between versions.
- Originals retain individual timings, full metrics, configurations, hashes, and tool/executable provenance. Separate batches experience host noise and are not strictly paired arithmetic ablations. Seven-sample ranges are not confidence intervals.

## Main results: advancement time

Times are wall-clock seconds; simulated seconds denote continuous progress within each new object. H is default `adaptive-half-life`; S is `legacy-stability`. Both use automatic node retention in this table.

| Input | Nodes / directed edges | Simulated seconds | /2 | /3.1 | /5 H | /5 S |
|---|---:|---:|---:|---:|---:|---:|
| Dense | 16 / 240 | 2 | 0.01718 | 0.03004 | 0.05631 | 0.06204 |
| Dense | 32 / 992 | 2 | 0.06968 | 0.12983 | 0.23552 | 0.25434 |
| Dense | 64 / 4032 | 2 | 0.29349 | 0.56403 | 1.00379 | 1.02831 |
| Dense | 128 / 16256 | 2 | 1.26974 | 2.46900 | 4.72420 | 4.85206 |
| Dense, longer | 64 / 4032 | 10 | 1.45748 | 2.82232 | 4.89612 | 5.46927 |
| Rotating pairs | 64 / 64 | 10 | 0.01041 | 0.01273 | 0.04331 | 0.05525 |
| Rotating pairs | 128 / 128 | 10 | 0.01386 | 0.01668 | 0.04373 | 0.06675 |
| Rotating pairs | 256 / 256 | 100 | 0.24352 | 0.26494 | 0.46598 | 1.03802 |
| Rotating pairs | 1024 / 1024 | 100 | 0.78088 | 0.77055 | 0.47909 | 2.78166 |

In the longer 64-node dense run, default /5 takes **1.73 times** /3.1's time and **3.36 times** /2's time: extending the run to ten simulated seconds does not reverse the result. For the 1,024-node low-degree graph, seven-sample ranges are 0.44441–0.51611s for default /5, 0.74414–0.83717s for /3.1, and 0.76432–0.87122s for /2. This advantage exceeds the observed repetition variation. The graph consists of independent channel pairs, not an arbitrary 1,024-node network.

## Component costs and state size

This table uses the same 64-node / 4,032-edge, ten-simulated-second batch. Times are milliseconds. State bytes measure one uncompressed complete Core JSON state, not process memory, a complete peripheral-equipped individual, or total experiment storage.

| Arm | Injection | Advancement | Capture | Encoding | Observation | State bytes |
|---|---:|---:|---:|---:|---:|---:|
| /2 | 3.123 | 1457.484 | 18.702 | 8.006 | 0.095 | 2,013,494 |
| /3.1 | 2.843 | 2822.322 | 19.804 | 8.898 | 1.188 | 2,314,620 |
| /5 H | 3.421 | 4896.118 | 24.579 | 10.083 | 4.114 | 2,687,907 |
| /5 S | 4.098 | 5469.267 | 25.149 | 8.822 | 3.361 | 2,633,385 |

Capture and observation also differ, but they are outside advancement timing and cannot explain the measured Core slowdown. Tool wall time is not injected as additional simulated time.

## Temporary H-disable comparison

`legacy-stability` **disables connection H only**: automatic nodes still compute their own H. The additional 2×2 comparison uses existing parameters exclusively:

| Engineering arm | Connection retention | Node retention | Active H mechanisms | Median / range, dense 64 nodes, 2s (wall seconds) |
|---|---|---|---|---:|
| `5-h` | adaptive-half-life | automatic | Nodes and edges | 1.04653 / 0.99875–1.16084 |
| `5-s` | legacy-stability | automatic | Nodes | 1.07579 / 0.97280–1.13717 |
| `5-h-manual` | adaptive-half-life | manual | Edges | 1.01988 / 0.96811–1.11101 |
| `5-no-h` | legacy-stability | manual | No runtime H calculation | 1.03946 / 0.99187–1.12438 |

Disabling H does not delete forgetting. Connections use stability-based forgetting and 100ms expiry maintenance; nodes use linear support reinforcement/decay with a 0.006 support threshold and 80-second last-touch wait. Ordinary weight reinforcement, activation, inhibition, short-term resources, fast traces, and fatigue remain; their exponential calculations are outside H. H fields are still initialized and saved, but no longer grow, decay, or predict expiry. Local dose multiplications may still be evaluated before the branch; this does not claim to eliminate every multiplication.

This therefore measures **H mechanisms versus their existing replacement rules**, not an arithmetic-only ablation preserving identical weight trajectories. Dense advancement changes from 1.04653 to 1.03946s, a 0.675% reduction, insufficient to claim a substantial speedup. Disabling node H alone reduces the median by about 2.55%, also within strongly overlapping ranges. Neither result says H functions have zero cost.

The same-batch sparse comparison uses 1,024 nodes, 1,024 edges, and 100 simulated seconds:

| Engineering arm | Median advancement (seconds) | Seven-sample range (seconds) | Expiry checks |
|---|---:|---:|---:|
| `5-h` | 0.47693 | 0.45569–0.52360 | 3,942 |
| `5-s` | 2.68755 | 2.61077–2.79593 | 897,382 |
| `5-h-manual` | 0.44922 | 0.44090–0.49221 | 3,942 |
| `5-no-h` | 2.73532 | 2.58067–3.81583 | 897,382 |

The complete no-H configuration takes **5.74 times** default H's time. Despite substantial no-H variation, its fastest sample remains much slower than default H's slowest sample. Disabling node H alone reduces the median by 5.81%, but overlapping ranges do not establish a stable benefit. All four end with identical graph sizes and no deleted nodes or edges; support and weight trajectories are not equivalent. These expiry counts use the same /5 counter and can compare maintenance frequency. They include multiple kinds of expiry check, not CPU cycles, and do not establish a timing percentage.

## Why local execution can remain slower

Source inspection supports the following cost sources, without CPU sampling or a precise percentage attribution:

1. /2 and /3.1 use dense numeric rows plus indexes; /5 uses tree-based nodes, edges, events, and deadlines. Local settlement still incurs lookups, cloning, string timestamps, and deadline maintenance. See the [older executor](../../../crates/threemind-core/src/lib.rs) and [local executor](../../../crates/threemind-core/src/local.rs).
2. The older path combines a propagation round into one signal event; /5 emits events per source node before reception grouping. Dense activity leaves little irrelevant work to avoid while retaining event-management costs. See `emit_continuous` in [older propagation](../../../crates/threemind-core/src/continuous.rs), and `emit` / `advance_impl` in the local executor.
3. /5 S maintains connection stability forgetting at each propagation period; default H can predict a distant expiry directly. Replacing H can thus increase maintenance events. The much slower S result on the 1,024-node sparse graph fits this implementation difference, without showing that H arithmetic itself is cheaper than stability arithmetic.
4. Counters have different definitions. In the 64-node short run, /3.1's 161,280 `edge_settlements` count necessary time settlements; /5 H's 399,168 `edge_visits` increment before same-time shortcut returns. Their ratio is not a 2.475-fold work multiplier. `scan_visits=0` means the scan-control propagation branch was unused, not that all program maintenance is globally scan-free.

Same-day isolated counts and nested timing locate edge settlement/copying, tree deadlines, and periodic S expiry; all12 paired complete final-state hashes match. Another66 uninstrumented candidate runs preserve final states: caching plus read-only weight access reduces large-sparse median time by10.58%, versus5.54% with overlapping dense ranges. Final-state matches do not establish every trajectory's equivalence, and production integration has not occurred. See [root causes and candidate limits](memory5-root-cause-20261013.md). This report does not authorize removing H, changing learning rules, or replacing formal defaults.

## Originals and reproduction

Originals remain in the repository's ignored `.work/memory5-validation/` directory, not copied into Git. Each batch contains `summary.json`, `configs.json`, and per-repetition files:

| Directory | Contents |
|---|---|
| `costs-r4-compare-2-31` | Dense short runs, 16–128 nodes |
| `costs-r5-longer` | Dense 64 nodes, 10 seconds |
| `costs-r6-pairs` | Paired 64 / 128 nodes, 10 seconds |
| `costs-r7-large-pairs` | Paired 256 / 1024 nodes, 100 seconds |
| `costs-r8-no-h-dense` | Dense 2×2 H-disable comparison |
| `costs-r9-no-h-pairs` | Sparse 2×2 H-disable comparison |

Representative commands, from the repository root; output directories must not already exist:

```powershell
cargo build -p threemind-core --example memory5_costs --release --offline
$env:PYTHONPATH = 'src'
.\.work\kernel-venv\Scripts\python.exe -X utf8 tools\benchmark_memory5.py --output .work\memory5-validation\fresh-compare --arms 2 3.1 5-h 5-s --channels 64 --seconds 10 --repeats 7 --warmups 1 --pattern dense
.\.work\kernel-venv\Scripts\python.exe -X utf8 tools\benchmark_memory5.py --output .work\memory5-validation\fresh-no-h --arms 5-h 5-s 5-h-manual 5-no-h --channels 1024 --seconds 100 --repeats 7 --warmups 1 --pattern pairs
```
