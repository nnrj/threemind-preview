# Fixed-function addressing in 6.0: engineering verification

Date: 12 November 2026. [中文](engineering-report.zh.md) · [Version description](../../../docs/en/v2-kernel60.md)

## Objective and authorization

The author authorized an independent 6.0 kernel that changes addressing while retaining the other 5.3 mechanisms. Eligibility and stability fields could be removed only if unused. The author subsequently clarified that addresses are virtual node identifiers and authorized local Git commits without pushing.

The engineering targets are stable node identities for equal stimulus codes, removal of the code-to-sequential-ID allocation table, Python/Rust agreement, preserved historical identities and evidence, and observation without simulated-time advancement. The existing unsigned 32-bit code domain is retained, with `F(c)=c`.

## Implementation and verification

| Check | Result | Meaning |
| --- | --- | --- |
| Dedicated 6.0 tests | 92 passed | Address boundaries, independent imports, parameter interfaces, persistence and dynamics |
| Included: comparison with 5.3 | 36 conditions passed with exact state equality | Matching node identifiers, four decay curves and nine configuration combinations |
| Included: Python/Rust comparison | 36 conditions passed | Sparse identifiers; exact discrete values; relative/absolute floating tolerances 3×10⁻¹² and 3×10⁻¹⁴ |
| Historical, native and standalone-runtime regressions | 458 passed | Includes 6.0 JSON, `.tmind` and SQLite interoperability |
| Rust foundation tests | 20 passed | Timestamps, storage, numerical mechanisms and historical behavior |
| General configuration tests | 3 passed, 2 skipped | Skipped checks require a test database that was not running; they are not service-level verification |
| Frontend | TypeScript and production build passed | 6.0 is selectable; 5.3 remains the creation default |
| Offline packages | Python and native wheels passed after isolated installation | Imported from the packages; sparse addresses and complete `.tmind` restoration verified without replacing the existing installation |
| Historical files | All 27 historical kernel source/test hashes matched their task-start values | Pre-existing working-tree edits were preserved and are distinguished from this task's edits |

Two initial failures were incorrect calls in the new tests: positional intervention arguments and an extra format argument to the auto-detecting decoder. Correcting those test calls resolved them. The Windows sandbox also prevented pytest temporary-directory access and Vite child-process creation; verification was completed within the authorized isolated local test scope.

All subjects were new engineering fixtures. No formal research individual was loaded, advanced or rerun. Original research data, manuscripts and old reports were not changed.

## Conclusion

Fixed-function addressing is implemented. Tests confirm stable addresses for identical codes and agreement between Python and Rust. When the two versions use matching node identifiers, the retained 5.3 rules produce identical complete states. Replacing birth-order identifiers with fixed addresses can affect positions, energy regions and simultaneous ordering through the original identifier-based rules; this result does not assert identical trajectories for arbitrary historical courses.

Eligibility and stability were retained: eligibility contributes to stability updates, node stability affects local plasticity, and these states remain part of observation and persistence.

## Address-reuse decision awaiting the author

If a deleted node is recreated at the same address, an old in-flight signal can reach the new node. Version 5.3 never reuses sequential identifiers and therefore does not redirect such signals. The author has been asked to choose between generation checks that discard old signals and explicitly accepting delivery to the fixed address. Until this decision returns, this boundary is not recorded as finally accepted and 6.0 is not made the default.

## Recheck locations

- `tests_v2/test_local60.py`: engineering targets and assertions.
- `tests_v2/test_runtime_interop.py`: runtime and storage interoperability.
- `.work/kernel60/new-tests.xml` and `regression.xml`: ignored local test results.
- `.work/kernel60/baseline-hashes.json`: source hashes at task start.
- `.work/native60-release/`: isolated native module and standalone Rust runtime; running services are unchanged.

These checks establish compliance with the implementation contract. Mechanism, shape–color and embodied studies require separate protocols and do not gain new scientific results from engineering fixtures.

## 13 November 2026 addendum: both delivery policies accepted

The author reaffirmed that both policies should be implemented if straightforward, with option 2, delivery to the address, as the default. This resolves the pending decision recorded above. Version 6.0 now provides `inflight_delivery="address"` (default) and `"same-birth"` in the API and bilingual workbench.

The default delivers a signal to the node present at its address on arrival, including a replacement. The alternative uses each node's birth ordinal and the cumulative birth count at emission to exclude signals predating recreation. Deleting a sender does not recall signals already emitted to a surviving receiver; wake events check both connection endpoints. Neither policy creates nodes from in-flight signals. This addition belongs only to 6.0; shared 5.3 parameters and decay and learning formulas are unchanged.

All 134 final 6.0 checks passed. They cover both policies, excitation and inhibition, connection awakening, deletion and recreation at the same internal timestamp, absent receivers, subsequent fresh signals, invalid checkpoint metadata, cross-backend restoration and the standalone Rust runtime. Both policies preserve complete states across saving and restoration; observation leaves state unchanged. The original 36 comparisons with 5.3 still pass, excluding only version declarations, the new 6.0 setting and birth ordinals from comparison while retaining all dynamical quantities, events and clocks.

Historical and runtime regressions passed all 458 checks. General configuration checks added 3 passes and 2 database-dependent skips, giving 461 passes and 2 skips together. Twenty Rust foundation checks and the TypeScript/production frontend build passed. Of 50 task-start hash entries, 48 are unchanged; only registry and package-export integration files changed during the preceding stage to expose 6.0. Historical implementations and tests are unchanged.

Both final wheels passed isolated installation with explicit import-path checks, both policies and backends, and restoration of in-flight `.tmind` states. Sandbox access restrictions initially caused imports to fall back to the older installation; path assertions prevented a false success, and verification passed in an environment able to read the isolated installation. After confirming the project native module was not in use, the accepted native wheel was installed into `.work/kernel-venv`, without altering running services. The Python runtime continues to use the project's editable source.

**Engineering conclusion: fixed-function addressing and both author-selected in-flight delivery policies are implemented and accepted.** Version 6.0 is explicitly selectable; the global creation default remains 5.3. Historical subjects, original evidence, manuscripts and research conclusions are preserved.

Final local records are `.work/kernel60/final-specialized.xml`, `final-regression.xml` and `final-wheel-validation.json`. Packages are in `final-wheels/`; the standalone runtime is in `.work/native60-final/`. These generated products remain outside Git. Earlier scores and the pending-decision record above are retained as implementation history.
