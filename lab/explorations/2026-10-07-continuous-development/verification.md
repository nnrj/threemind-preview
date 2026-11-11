# E62 engineering verification / 工程验证

2026-10-07. This file records actual checks, not behavioral success criteria.

- `pytest tests/test_developmental_system.py tests/test_developmental_curriculum.py -q --basetemp=.work/pytest-developmental-05 --tb=short`: **8 passed**. Full Core/body/raw-window state and the next actions/updates match after restore; optimizer, replay and RNG continue; mismatched individual and overwrite are rejected; teacher metadata is excluded from inferred motor input; body/servo and toy/self-hearing restoration pass; exact registered course/review order and resume cursor are checked.
- After adding read-only calibration inspection: `pytest tests/test_developmental_system.py -k inspection -q --basetemp=.work/pytest-developmental-inspection --tb=short`: **1 passed**. Inspection leaves the next learned parameters identical to an uninspected restored reference.
- `tools/validate_history.py`: **4 editions,71 chapters**, bilingual coverage and local links valid at this check. Update after any later new links.
- Actual teaching uses CUDA for the small Transformer and the existing native CPU Core. No Core implementation, dynamics version, mapping or ordinary default was changed.
- The initial supervision-time pilot and the later system-memory interruption are explicitly preserved; neither is counted as an independent failed behavioral evaluation. Their computation remains in the budget.

The focused tests used an isolated project-local temporary directory. Default-sandbox temporary-directory permissions required the already authorized elevated test execution. No user service was taken over.

Replay packaging has a test distinguishing teacher assistance from own output and preserving recorded frames. Browser-based visual acceptance and video rendering are **not claimed** by these checks. Previous local-browser access restrictions are not bypassed.

Read-only calibration scores concern retained supervised samples. Independent unassisted actions and Core-intervention results belong in the experiment report, not this engineering checklist.

## Final targeted verification

`pytest tests/test_developmental_system.py tests/test_developmental_curriculum.py -q --basetemp=.work/pytest-developmental-final --tb=short`: **9 passed in16.21s** after the snapshot rename retry and cross-stage inspection changes. Cross-stage inspection rejects another individual's samples and leaves the next actual learning update unchanged.

The actual saved birth identifies `threemind.continuous-memory/2` with `threemind.continuous-memory-state/2`; the generic Study implementation catalog is not the selected instance's identity. Complete-system storage remains`developmental-system/2`.

The final replay packages **275 clips /16,170 recorded frames** across full direct teaching, intervals, corrections and all five completed test conditions. It neither re-simulates nor selects only successes. Source parsing and the original replay provenance test pass; browser visual acceptance is still not claimed.
