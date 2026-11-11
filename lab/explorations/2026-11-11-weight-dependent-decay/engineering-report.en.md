# R48: Rust implementation, restoration, and performance verification

2026-11-11. [中文](engineering-report.zh.md) · [Usage](../../../docs/en/v2-weight-decay.md) · [Local scientific results](report.en.md) · [Whole-learner results](joint/report.en.md)

## Delivery conclusion

**The weight-dependent candidate now has a genuine Rust implementation, Python native binding, installable wheel, and standalone runtime, verified in this round.** Its kernel identity is `threemind.experimental-weight-decay/1` and its state identity is `threemind.experimental-weight-decay-state/1`. Python and Rust use the exact update tested in the scientific batches, without per-experience contribution lists or numerical integration.

This is a separate dynamics option. Node support, activation, inhibition, transmission, synaptic resources, reinforcement, and event ordering follow 5.3. Node support remains inverse logarithmic; connection decay selects among the five R48 arms. Genuine 5.1, 5.2, and 5.3 implementations and saved identities remain. The global default is still `continuous-memory/3`, and the 5.3 default remains power law.

Both scientific batches used their frozen Python reference backend. Rust was initially built in an isolated source copy. Actual source integration followed full API readback and completion of both scientific archives and bilingual reports. All 63 Rust files in the build copy match the integrated source byte for byte. Installed extensions and running services were not replaced; the new products require explicit selection.

## Verified capabilities

| Check | Observed result |
| --- | --- |
| Targeted Python checks using the direct cargo product | 406 passed in 49.26 seconds |
| Candidate checks using the actually installed isolated wheel | 54 passed in 5.50 seconds |
| Fixed Rust Core tests | 20 passed; the Runtime test executable contains zero additional tests |
| Ruff F checks for new Python implementation and tests | Passed |

The 406 checks include 54 candidate tests plus 5.3, native and standalone 5.2, 5.1 equivalence, kernel registration, artifact codecs, and configuration validation. Wheel tests repeat the same 54 candidate checks; these counts are not additional scientific samples.

Candidate checks cover five decay arms and four reception/energy/plasticity settings, comparing full states, graphs, and events step by step. Python and Rust states are cross-restored at multiple times and then advanced. Further checks cover partitioned advancement, observation without mutation, identity and birth-parameter constraints, JSON/TMIND input, SQLite save/resume, standalone creation at time zero, and exact decay from six engineering weights between 0.035 and 1.0. Floating comparison tolerances are 3×10⁻¹² relative and 3×10⁻¹⁴ absolute; discrete fields and event structure must match exactly.

The sandbox initially could not read the pip-created isolated directory, causing an import probe to find the old installed module. That diagnostic receipt is preserved. The approved isolated check then asserted the actual module path and candidate class before running all 54 tests successfully. This installation-environment issue never affected the scientific host. Source integration also encountered a file-write permission interruption; remaining entries were completed from the actual diff before verification.

## Performance and scale

These measurements use fresh engineering graphs, not formal individuals. The topology is disjoint reciprocal node pairs, with equal node and directed-edge counts. Each condition has three repeats with rotated rule order. Construction, advancement, and full-state capture/TMIND encoding are timed separately. Silenced graphs suppress all node sending to examine stored-structure update cost; active graphs use normal dynamics. Each trial advances one internal second. State digests match before and after encoding.

Values below are median wall seconds, ordered as silenced advancement / active advancement / active-state saving.

| Backend and size | Inverse log | Weight fast | Weight slow | Matched exp. fast | Matched exp. slow |
| --- | --- | --- | --- | --- | --- |
| Python, 64 nodes/64 edges | 0.024994 / 0.083126 / 0.011996 | 0.022892 / 0.077911 / 0.011628 | 0.022854 / 0.081416 / 0.012044 | 0.021990 / 0.077085 / 0.011422 | 0.021944 / 0.081095 / 0.011816 |
| Rust, 64 nodes/64 edges | 0.000757 / 0.003691 / 0.009983 | 0.000616 / 0.003558 / 0.009900 | 0.000617 / 0.003709 / 0.010272 | 0.000639 / 0.003568 / 0.009898 | 0.000635 / 0.003689 / 0.009707 |
| Python, 1024 nodes/1024 edges | 0.396936 / 1.336156 / 0.161986 | 0.369114 / 1.305263 / 0.159897 | 0.371541 / 1.364036 / 0.161715 | 0.352178 / 1.292850 / 0.167975 | 0.356315 / 1.343759 / 0.166212 |
| Rust, 1024 nodes/1024 edges | 0.012266 / 0.063176 / 0.138454 | 0.010141 / 0.057810 / 0.139474 | 0.010188 / 0.060925 / 0.137838 | 0.010398 / 0.061945 / 0.139719 | 0.010434 / 0.064522 / 0.140892 |
| Rust, 8192 nodes/8192 edges | 0.110398 / 0.531121 / 1.087516 | 0.094664 / 0.512416 / 1.095209 | 0.093847 / 0.540525 / 1.102769 | 0.095159 / 0.517403 / 1.088244 | 0.097356 / 0.543005 / 1.087981 |

**For the same rule at 1024 active nodes, Rust advances 20.8–22.6 times faster than Python.** At 8192 nodes, weight fast/slow use approximately 14%/15% less silenced advancement time than inverse log. Active advancement uses about 3.5% less and 1.8% more, respectively. The candidate adds no substantial whole-system performance burden and yields no order-of-magnitude improvement. Active slow groups visit nodes 286,720 times, compared with 270,336 for the fast groups and inverse log; actual activity workloads still differ. Full counters are preserved.

At 8192 nodes, saving a state takes approximately 1.09–1.10 seconds, more than advancing one internal second at 0.51–0.54 seconds. Reducing long-experiment cost should therefore examine save frequency and evidence encoding separately, rather than suppressing internal activity for speed. Earlier 5.3 exponential, power-law, inverse-logarithmic, and piecewise comparisons remain in the separate [R47 engineering report](../2026-11-11-kernel53/engineering-report.en.md).

This benchmark contains 50 conditions and 150 engineering repeats, taking 152.54 seconds. A one-second guard checks 5/4/5/25GiB reserves for commit/RAM/C/E and stops only after a complete engineering unit; no guard fired. Sampled peak private memory was 850,964,480 bytes, about 811.5MiB. Maximum JSON state size was 9,672,124 bytes and maximum TMIND size 5,425,338 bytes. These graphs contain no trained Transformer; whole-learner and curriculum costs are reported in R48b.

## Products and reproduction

| Product | Bytes | SHA256 |
| --- | ---: | --- |
| Direct cargo native module `_threemind_native.pyd` | 7,950,336 | `a39520e48a097ed820c94481b78e0d1047f9df5973fb835bf4d36a08fa69bdfa` |
| Standalone `threemind-runtime.exe` | 12,239,872 | `e7687306c7847cb87649a35aa66ebb4778b09b08791abd6d11d21ea7d5e5613a` |
| Windows x64 CPython≥3.11 abi3 wheel | 2,771,052 | `43fa727848e9e80ae7d5f30b082c22e42b5fe2bb9ed6b2d1cdee45990967b175` |

The extension inside the wheel has SHA256 `0b41496e602c2132c3e85ff7909a2ee704197d4a848337c9f5e2d285a8b62dcd`, separately verified and recorded from the direct cargo build. Local products are in `.work/r48-delivery/`. Permanent engineering storage is `E:/ThreeMindData/experiments/2026-11-11-weight-dependent-decay/engineering-v1`, containing products, source checksums, logs, all repeated measurements and counters, and a delivery manifest.

The integrated sources build through existing commands:

```text
cargo build --offline --release -p threemind-native -p threemind-runtime
cargo test --offline -p threemind-core
pytest tests_v2/test_weight_decay.py
```

The final command requires the test process to prioritize the newly built native module and `THREEMIND_TEST_RUNTIME` to identify the new executable. Local verification used a workspace temporary-directory fixture because of system-temp permissions; standard environments can use pytest's default fixture. `benchmark_runtime.py` reproduces engineering measurements. Scientific success and failure remain determined by the frozen R48a/b criteria.
