# E34 prospective capture attribution

[中文登记](design.zh.md) · [English registration](design.en.md) · [执行记录](execution-notes.md)

```powershell
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-03-ocean-hunting/experiment.py batch
```

Local project:`315c50a4-0a3a-4b07-b760-0fc053730a39`.
Evidence:`.work/ocean-hunting-20261003`.
The actual registration date is2026-10-04 China time; the directory retains the drafting date.

Two complete E32 world snapshots supply prospectively selected encounters. At most2scouts+32focal forks; they are not34 independent populations. Keep one simulation worker across all studies. Update`usage.json`from an actual account reading at least every30minutes. Completed cases are reused; paused/failed cases remain and stop automatic continuation.

Explicit future environment configuration:

```python
from lab.tools.ocean_community import load
world = load(full_world_snapshot)
world.research['parent_protection'] = 'bilateral-until-maturity/1'
```

Saving/restoring this whole-world wrapper preserves the rule. Missing configuration retains legacy one-way protection; do not edit an old experiment or silently reinterpret its stored world. All E34 arms have the new rule; no mechanism is inserted into Core.
