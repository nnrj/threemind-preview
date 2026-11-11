# Checks before any /5.2 integration

2026-11-09. These are engineering checks, not outcomes from the six-condition study.

- Existing `tests_v2/test_local51_equivalence.py`: **189 passed**, 16.63 seconds.
  The suite checks frozen /5 witnesses, /5–/5.1 equivalence, Python/native agreement,
  identity rejection, observation and time batching, restoration and expiry.
- Mathematical candidate reference: **9 passed**, 0.016 seconds. This validates
  the formulas and contribution-age bookkeeping in isolation, not a new Core.
- Existing implementation source aggregate:
  `706b4ae52ec80c95acbf496bd2d738018daa5d0517b6098cf4536de375002683`.
- Existing installed native binary:
  `cac92686d2e23a4b8e1dbe5ad96f1aa5f3b7ccbbe19121a79e705c4b1f528ee8`.
- R44's frozen source/protocol manifest and implementation manifest both match.
  There is no current diff under `src/` or `crates/`.

The first two pytest attempts were blocked during temporary-directory setup by
Windows sandbox permissions; they did not run the test bodies. The successful
attempt used a fresh isolated `.work/decay52-prechange-pytest-20261109-02`
directory under approved execution. It did not start services or use production
database contents. The originals and scientific subjects are not test fixtures.

Commands:

```powershell
.work/kernel-venv/Scripts/python.exe -X utf8 -m pytest tests_v2/test_local51_equivalence.py -q --maxfail=1 --tb=short --basetemp=.work/decay52-prechange-pytest-20261109-02
.work/kernel-venv/Scripts/python.exe -X utf8 -m unittest discover -s lab/explorations/2026-11-09-decay-mechanisms52 -p 'test_*.py' -v
```

The pytest directory above is a historical execution path; use a new empty path
for any later run. New /5.2 implementation and post-change regression results
must receive their own dated verification record.

## 17:40: recent-contribution precision

The mathematical reference now stores each contribution's elapsed age directly.
Subtracting a recent birth age from a cumulative age of 1e18 had lost a subsequent
unit of age in binary floating point. A new independent half-value check covers
this case for all three curves, and an extreme finite inverse-log argument checks
overflow-safe evaluation. **10 tests passed**, 0.015 seconds. This changes only
the isolated reference; the scientific studies and production implementation
remain untouched. The earlier nine-test result above is preserved as history.
