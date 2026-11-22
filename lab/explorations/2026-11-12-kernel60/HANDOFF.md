# Current handoff — 2026-11-13: 6.0 engineering complete

The author answered the remaining question: implement both policies if straightforward, default to option 2 (deliver to the address). Both are implemented and verified. `inflight_delivery="address"` is the default; `"same-birth"` discards signals predating receiver recreation. Node birth ordinals and event birth limits identify lifetimes without changing F(c)=c or retaining deleted-node histories. Wake checks both endpoints; sender deletion does not recall signals already sent to a surviving receiver.

Final results: 134 dedicated tests; 461 regression/configuration tests passed with 2 database-dependent skips; 20 Rust tests; frontend build; isolated wheel verification. The accepted native wheel is installed in project `.work/kernel-venv`; Python uses editable project source. No service restart or scientific run. Global creation default remains 5.3. R49 engineering is complete. Do not repeat old pending questions or rerun scientific experiments from this handoff.

Final generated products: `.work/native60-final/`, `.work/kernel60/final-wheels/`, `final-specialized.xml`, `final-regression.xml`, `final-wheel-validation.json`. Historical source hashes remain intact except the two declared registry/export integration files. Local commits authorized; no push.

---

## Preserved initial handoff (superseded by the decision above)

# 6.0 engineering handoff — 2026-11-12

Scope authorized by the user: independent 6.0 fixed-function addressing, retaining the other 5.3 rules. Addresses are virtual node IDs. Local `git add .` / commits are authorized; no push. Previous experiments remain paused; this work does not modify manuscripts or original research evidence.

## Current state

- Python and Rust own 6.0 transitions, configuration and state identity. `F(c)=c` on the existing uint32 stimulus-code domain; no `receptors` allocation map. Sparse containers avoid address-range-sized allocations.
- Eligibility/stability retained because they are still used. Global creation default remains 5.3.
- Native binding, standalone runtime, artifact codecs, registry, API parameters and bilingual frontend option wired.
- Dedicated tests: 92 passed. Broader historical/native/runtime regressions: 458 passed. Rust foundation tests: 20 passed. Configuration checks: 3 passed, 2 database-dependent skips. Frontend production build passed. History validation passed (4 editions, 141 chapters).
- 27 historical source/test file hashes match the task-start snapshot. Existing changes to 5.3 defaults, manuscript supplementary_v3 and other files were already present and preserved.
- Isolated artifacts: `.work/native60-release/`; wheels: `.work/kernel60/wheels/`; verification XML and task-start hashes: `.work/kernel60/`. No running service or installed native package has been replaced.
- After the user-interrupted turn, package import and complete `.tmind` roundtrips passed from an isolated wheel installation. Hashes are recorded in `.work/kernel60/wheel-validation.json`. Git staging completed before the interruption; no experiment or build needs restarting. The address-reuse question was re-presented because no answer had arrived.

## Pending author decision

An asynchronous question asks how to handle a signal sent before deletion when a node has been recreated at the same fixed address:

1. Discard the old signal, using a per-birth generation check; this preserves the old no-redirection behavior without restoring an address-allocation table.
2. Deliver to the fixed address, explicitly accepting redelivery to a newly created node.

The present prototype routes by fixed address. Do not claim final acceptance or silently treat lack of a response as approval. If the user selects generation checks, implement and test the complete event paths (excitation, inhibition and wake), state restoration and both backends; preserve the historical kernels. If the user selects address delivery, freeze and test that behavior explicitly. Update both reports, histories and R49 accordingly before final delivery/installation.

## Verification commands

Use `.work/kernel-venv/Scripts/python.exe -X utf8`. Set `PYTHONPATH` to `.work/native60-release` and `src` for isolated native tests, and `THREEMIND_TEST_RUNTIME` to `.work/native60-release/threemind-runtime.exe` for independent-runtime tests. Windows sandbox restrictions prevented pytest temporary directories and Vite subprocesses; authorized local tests succeeded outside that restriction with basetemp under `.work/kernel60`.

`tests_v2/test_local60.py` includes exact cross-version comparisons only where addresses coincide, sparse-address cross-backend tests, observation/time partitioning, artifact roundtrips, API parameters, and direct execution with 5.3 imports forbidden. Different addresses still feed the unchanged spatial/energy functions and tie ordering, so arbitrary old courses need not have identical trajectories.

Before commits run `scripts/check-git-data.py --all-tracked`. Research originals, generated test states and binaries stay outside Git. Do not rerun `.work/build_kernel60.py` or `.work/wire_kernel60.py`: these were one-time extraction/integration helpers and would overwrite subsequent edits or duplicate registrations.
