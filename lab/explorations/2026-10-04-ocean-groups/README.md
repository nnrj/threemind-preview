# E35–E36 commands

Use `.work/kernel-venv/Scripts/python.exe` at repository root.

```powershell
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-04-ocean-groups/experiment.py register --usage <fresh-account-percentage>
.work/kernel-venv/Scripts/python.exe -u lab/explorations/2026-10-04-ocean-groups/experiment.py batch --phase copies
.work/kernel-venv/Scripts/python.exe -u lab/explorations/2026-10-04-ocean-groups/experiment.py batch --phase mixed
```

One simulation worker; do not run while E34 is active. Preserve partial cases rather than overwriting them. Full states use `threemind.ocean-groups-state/1`, physical protocol `threemind.ocean-groups/1`; loading through a generic old-world reader must not discard group control. Existing Ocean/3 defaults remain unchanged.

Evidence: `.work/ocean-groups-20261004/`. The `usage.json` guard must reflect a fresh real account reading, not a fabricated timestamp. The report builder requires all ten registered outcomes and refuses to overwrite an existing report.

Read live cohort progress without rescanning large recordings or contacting Core:

```powershell
.work/kernel-venv/Scripts/python.exe -m lab.tools.ocean_live_status --root .work/ocean-groups-20261004 --output .work/ocean-groups-20261004/live-groups.json --cases mixed-g0-swap0 mixed-g0-swap1 mixed-g1-swap0 mixed-g1-swap1
```

`provisional-recorded-frame` is the most recent fully written observation, not a completed outcome. `lab.tools.ocean_process.food_heading` reduces directional feeding process measures once; `lab.tools.ocean_gallery` builds offline comparison players from actual media catalogs. These observers never advance the world or supply stimuli.

After simulations finish:

```powershell
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-04-ocean-groups/analyze.py
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-04-ocean-groups/figures.py
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-04-ocean-groups/report.py
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-04-ocean-groups/media.py
```

Analysis caches each completed case once; generating plots and films requires no new simulation. Open `.work/ocean-groups-20261004/media/gallery.html` for synchronized full-habitat playback of both assignments in both environments. FFmpeg is required for MP4 export; its local path is explicit in `media.py`. Independent controller-group metadata stays outside Core.

The scoped `publish.py` checks the verified local database destination before writing reports and media. Full evidence is archived locally instead of uploaded again. `delivery.json` records project, document and archive identities. Publication is separate from running a study; it must not target an arbitrary remote database.
