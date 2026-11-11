# E33 no-predation control

The only physical protocol change from E32 is`predation=false`. This retains contacts and all sensory/body/world rules. It is not a new Core mechanism.

```powershell
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-03-ocean-no-predation/experiment.py batch
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-03-ocean-no-predation/analyze.py
```

Local study project:`0d64c773-bdab-4de5-a4a5-fcbc48964403`.
Evidence:`.work/ocean-no-predation-20261003`.
Actual account usage at registration:18%. Update`usage.json`from actual account readings at most30minutes apart. Keep one simulation worker across E32/E33. Completed cases are reused; partial cases are retained and never silently overwritten.

The two world seeds are the independent units. The97-body capacity criterion is right-censored at120simulated seconds if not reached; the recorded scene sampling resolution is0.1s. E32 provides the already completed predation-enabled comparisons.
