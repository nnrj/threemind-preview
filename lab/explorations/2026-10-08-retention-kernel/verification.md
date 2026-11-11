# Verification record — 2026-10-08

[中文报告](report.zh.md) · [English report](report.en.md) · [Protocol](protocol.md)

Completed locally with an isolated release native wheel and independent release Rust Runtime under `.work/retention-v3`. No production installation, service restart, database startup, push or deployment was performed.

| Check | Result and scope |
| --- | --- |
| Focused Python/native/Runtime regression | **263 passed, 6 skipped**; final run 53.33 seconds |
| Skips | Isolated PostgreSQL cluster on port 55439 was not running: configuration (2), resource limits (1), process observation (2), checkpoint pipeline (1). Database-backed API/commit integration remains unverified in this session |
| Backend coverage | /3 auto/manual × adaptive/legacy × context toggles; state/observer equality, cross-restore, finite budget ordering; preserved causal/9 and continuous/memory/novelty witnesses |
| Independent Rust Runtime | Release executable, /3 JSON and .tmind import/export, SQLite continuation and new-default identity checks included in the 263 tests |
| Saved probe evidence | All **18** final checkpoints restore with exact state digests on both Python and Rust backends |
| Rust workspace | **5 passed**, no failures; offline native/Runtime release builds succeed |
| UI | TypeScript and Vite production build; no live-browser or running-service acceptance claimed |
| History | Four editions, **77 chapters**; bilingual coverage and local links validated |

Final selected suite:

```powershell
$env:PYTHONPATH='.work/retention-v3/native;src'
$env:THREEMIND_TEST_RUNTIME=(Resolve-Path .work/retention-v3/runtime-target/release/threemind-runtime.exe).Path
.work/kernel-venv/Scripts/python.exe -m pytest `
  tests_v2/test_retention_candidate.py tests_v2/test_causal9_baseline.py `
  tests_v2/test_memory_candidate.py tests_v2/test_novelty_candidate.py `
  tests_v2/test_continuous_candidate.py tests_v2/test_kernel_registry.py `
  tests_v2/test_configuration.py tests_v2/test_runtime_interop.py `
  tests_v2/test_resource_limits.py tests_v2/test_process_observation.py `
  tests_v2/test_ocean_contact.py tests_v2/test_ocean_evolution.py `
  tests_v2/test_checkpoint_pipeline.py tests_v2/test_energy.py `
  tests_v2/test_doc_resources.py -q -rs --disable-warnings `
  --basetemp=.work/retention-v3/pytest-final-2 `
  --junitxml=.work/retention-v3/validation.xml
```

Initial validation exposed a documentation-peer classification bug and Windows sandbox temp/process restrictions. Review corrected dormant capacity double counting and made finite-budget traversal stable across restore. Post-default validation found the standalone Rust default still selecting /2; it now selects /3. Two temporarily changed ocean assertions were restored after confirming their protocols explicitly bind /2, as required by historical identity preservation. The final suite above passes after these corrections. Probe data was not overwritten during these repairs; its unbounded-budget conditions are unaffected by the later stable-budget traversal change.

For reproducibility the structural probe script, effective configuration in each checkpoint, result tables and SHA-256 state digests are retained. Runtime timing is a single local observation, not a controlled scalability benchmark. Neither these checks nor state persistence demonstrate improved shape/color recognition. The next complete-system teaching experiment and optional-mechanism benefit studies remain separate work.
