# E32 complete-habitat controls

[中文设计](design.zh.md) · [English design](design.en.md)

The experiment preserves the complete shared ocean in every counterfactual. Only the named focal engine or controller changes. Core and Ocean/3 physics are unchanged. This replaces E31's isolated apparatus as the primary ecological comparison; it does not rewrite that evidence.

Sources: `base-protocol.json` is the completed E30 group-0 Core protocol, copied unchanged. `experiment.py` records E32's declared world size, population and food changes explicitly. Evidence: `.work/ocean-community-20261003`, independent local project `0b662685-7484-4c20-b1cb-064b53a582e4`.

```powershell
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-03-ocean-community/experiment.py batch
```

Completed cases are reused; partial/failed cases are never silently overwritten. Refresh the local `usage.json` from actual account readings at most 30 minutes apart. The budget guard saves a full state before stopping. No live host telemetry, remote provider or user-run service is involved.

Meaningful apparatus validation: 10 tests passed (`test_ocean_community.py`, `test_ocean_contact.py`). They cover relative-time birth equivalence, finite reserve/physical habitat preservation, save/restore of the focal random controller, complete scene recording, calibrated capture/shell behavior and stable nutrient counter noise. Tests are not biological or ecological findings. Full evidence is not repeatedly replayed or hashed.

The paired births have the **current** focal Core reserve as their explicit initial reserve. They do not acquire a new founder endowment, a younger body or renewed juvenile protection. A historical bookkeeping offset resets previous expense counters without changing any physical energy.
