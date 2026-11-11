# E37 · Enclosure-only inherited variation

See [design](design.zh.md) / [English](design.en.md). Full habitat, all Core-controlled, no contact consumption. Soft-envelope geometry is an explicitly separate apparatus; Core is unchanged.

```powershell
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-04-ocean-enclosure/experiment.py register --usage ACTUAL_ACCOUNT_USED_PERCENT
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-04-ocean-enclosure/experiment.py batch
```

`register` creates a new local Lab project only once. Each completed 300-second segment continues from its full final snapshot. Existing/partial outputs are never overwritten. Update `.work/ocean-enclosure-20261004/usage.json` from a real account usage reading within30minutes; do not fake its freshness. Resource stops retain final snapshots and input records. Old E28–E36 sources are read-only.

Evidence: `.work/ocean-enclosure-20261004`, per-segment Arrow inputs,100ms complete scenes,1s passive samples,150s and boundary snapshots. `capture_enabled=false` is checked by the new protocol. All offspring retain all-Core control; no maximum lifespan. CLI/Python export uses the same read-only `lab.tools.ocean_video` renderer with optional `show_evolution` panel.

Full-habitat overview and event clips are generated only from actual recorded frames, without advancing any model. Colours represent generations, not competing controllers or established species.
