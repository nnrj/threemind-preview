# Engineering verification and performance: /5.3 and faithful /5.2 Rust

11 November 2026. [中文](engineering-report.zh.md) · [Use and mechanisms](../../../docs/en/v2-kernel53.md)

## Delivery conclusion

The independent /5.3 Python and genuine Rust implementations, persistence and existing interfaces pass the targeted verification. Faithful /5.2 Rust is integrated without changing its reference equations, contribution histories or saved identity. After integration, 441 targeted Python regressions and 20 Rust Core checks passed; 88 historical /5.2 reference-apparatus checks also passed. Scientific outcomes are separately reported in R47a/b/c.

The 441 checks include forty /5.2 native checks, six /5.2 standalone Runtime checks, eighty /5.3 checks, six feedback/weak-signal checks, and cross-version Runtime interoperability, /5.1 equivalence witnesses, historical default isolation, preserved memory witnesses and registry tests. They overlap earlier verification and are not added together as independent experiments. The twenty Rust checks include historical witnesses. One historical /5.2 test asserting a reference-only capability was explicitly deselected and preserved unchanged. A new test verifies genuine native routing while retaining identity and undefined-inheritance rejection.

The six additional checks cover six-node recurrent networks with/without an energy budget, positive weak transmission when the joint cutoff is off, and retained age after weak reinforcement of an old edge. The first energy fixture lacked sufficient local supply for associative transmission; the engineering fixture was changed to an explicit global budget before retesting recurrence. Neither Core nor scientific experiments changed. These tests check bounds, event and backend agreement; scientific retention and forgetting retain their registered criteria.

## Component measurements

Measurements use this machine's release build, three repeats per condition and median wall seconds. Construction, internal advancement, and state capture plus TMIND serialization are timed separately. Serialization includes Python-side format handling. Graphs consist of disjoint reciprocal pairs, with equal numbers of nodes and directed edges. Passive fixtures explicitly silence every node; active fixtures use normal dynamics.

Each cell gives passive advancement / active advancement / active-state save. Advancement spans one internal second.

| Backend and scale | Exponential | Power law | Inverse logarithmic | Power–exponential |
| --- | --- | --- | --- | --- |
| Python, 64 nodes/edges | 0.02348 / 0.08664 / 0.01191 | 0.02519 / 0.08560 / 0.01347 | 0.02540 / 0.08220 / 0.01205 | 0.02481 / 0.08395 / 0.01165 |
| Rust, 64 nodes/edges | 0.000473 / 0.003542 / 0.009786 | 0.000499 / 0.003548 / 0.009947 | 0.000687 / 0.003604 / 0.010078 | 0.000831 / 0.003998 / 0.010330 |
| Python, 1024 nodes/edges | 0.39936 / 1.47370 / 0.18712 | 0.41986 / 1.45943 / 0.17715 | 0.41212 / 1.39481 / 0.16916 | 0.39935 / 1.39400 / 0.16601 |
| Rust, 1024 nodes/edges | 0.007835 / 0.057876 / 0.143013 | 0.008231 / 0.058751 / 0.136238 | 0.011373 / 0.059680 / 0.134687 | 0.013400 / 0.066016 / 0.135503 |
| Rust, 8192 nodes/edges | 0.07551 / 0.50209 / 1.10512 | 0.07852 / 0.51212 / 1.10191 | 0.10268 / 0.52600 / 1.10929 | 0.11877 / 0.57112 / 1.08656 |

Rust advances these sparse active graphs substantially faster than Python, supporting its use for the scientific batches. Saving benefits less and exceeds one-second advancement cost at the largest scale. Further performance work should therefore measure scanning, event propagation and evidence saving separately. Simplifying a formula does not imply proportional whole-system acceleration. This fixture does not estimate dense-graph or million-node throughput.

The largest recorded process private allocation was 772,214,784 bytes. Largest JSON and TMIND states were 9,696,446 and 5,425,082 bytes. Digests were unchanged through save/restore and observation. Raw repetitions, counters and the script are in `engineering-v1`. Forty conditions with three repetitions are engineering measurements, not 120 independent scientific origins.

The earlier 64-node, ten-second measurements, scalar calls and thirteen-second input course remain in `benchmark.py` and are not pooled with this one-second scale test. R47c separately reports complete Transformer teaching: 32 individuals took 1,518.06 wall seconds, peak private memory about 1.65 GiB, and the largest complete individual 379,634 logical bytes, including personal model, Adam, random state and all dependencies. That scientific apparatus has a different size from these artificial scale graphs.

## Reproduction and products

Final backend checks used the release module in `.work/kernel53-delivery`. Windows default pytest temporary-directory permissions failed on this workstation, so isolated tests used the repository-local `pytest53_fixtures` plugin. Scientific assertions were unchanged. Normal temporary fixtures may be used elsewhere. Main commands:

```text
cargo build --offline --release -p threemind-native -p threemind-runtime -j 2
cargo test --offline -p threemind-core -j 2
pytest tests_v2/test_local52_native.py tests_v2/test_local52_runtime.py tests_v2/test_local53.py tests_v2/test_local53_feedback.py tests_v2/test_runtime_interop.py tests_v2/test_local51_equivalence.py tests_v2/test_local5_default_isolation.py tests_v2/test_memory2_preservation.py tests_v2/test_kernel_registry.py
```

Place the new native module first on the test process's import path to avoid testing an older installed module. Historical /5.2 checks used its original `test_integration.py` (excluding the obsolete capability assertion), `test_candidate.py` and `test_decay_reference.py`. New Python files passed Ruff F checks. Standalone CLI zero-time /5.2 and /5.3 specimens round-tripped through TMIND with correct identity and internal time.

| Local product | Bytes | SHA256 |
| --- | --- | --- |
| `_threemind_native.pyd` | 7,506,432 | `97b7db3202add74298f9c6510bccbc9ff238e1b84851d0225430694b71cae0aa` |
| `threemind-runtime.exe` | 11,858,432 | `f63e479ec683280fc16f3b2f9f7b3d76893a84106b290272302c245dc9c4a621` |

Engineering measurements and delivery manifest reside at `E:/ThreeMindData/experiments/2026-11-11-kernel53/engineering-v1`. The scientific `.work/native53-release` module remains intact. The final product adds /5.2 and does not replace the binaries frozen for the three scientific batches. Historical individuals, originals, running services, installed extensions and the global default are preserved. Commits are local only, without push.

## Same-day addition: installable wheel

Maturin produced a Windows x64 wheel for CPython≥3.11, 2,622,798 bytes, SHA256 `c4d3fb68e19deaea2d43905fe1fe500ea33d59f81ce6e6370d06c755a52f358c`. Sandbox permissions twice prevented pip temporary-directory creation. Automatic review then approved testing in the bounded target directory; `pip --target .work/kernel53-wheel-check` succeeded. The installed wheel passed forty /5.2, eighty /5.3 and six feedback checks, totaling 126, overlapping the verification above.

Its extension SHA256 is `a5e4a6aab73e1a99a1a2eb0b0cff0c8db064245a45ed60d39b217e10da30d7c3`. This is the Maturin build for the selected Python, listed separately from the earlier cargo product. Installation was isolated and did not overwrite active site-packages. The engineering directory preserves the original manifest and adds `wheel-addendum.json` and this report edition.
