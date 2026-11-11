# E38 execution and reuse

One simulation worker, after E37 finishes. Current environment and Core versions remain fixed.

```powershell
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-04-ocean-species/experiment.py register --usage ACTUAL_ACCOUNT_PERCENT
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-04-ocean-species/experiment.py batch
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-04-ocean-species/analyze.py
```

Do not repeat registration over existing evidence. `usage.json` must be refreshed from a real account reading at least every30minutes. STOP file or resource limits pause and preserve partial results; do not pretend a partial result is the900s endpoint.

Shared0–300s is simulated once. Both complete habitat forks start there. Control and reduced supply have separate300–600 and600–900s evidence. The reduced branch changes future replenishment to one particle every2s; existing particles are retained. This is a designed nutrient intervention, not a Core change.

2026-10-04 closeout correction: the preceding sentence describes scheduled segments. In the actual execution, reduced600–900s was **not started**, because usage reached the registered extension threshold. Both branches have600s evidence; only control has900s. Final analysis compares the common endpoint and separately retains the extension. See [closeout](turning-and-closeout.md).

`event-species/*.tmspecies` saves each successful predator immediately after the actual event, before later experiences or starvation. These are imported into the species library after each segment. Full world/brain snapshots at segment boundaries and intermediate checkpoints remain separate. Archived capabilities are claims with evidence, not semantic inputs or new neural rules.

The explicit copying of E37 candidate59 into11 founders is recorded in world.research.species_founders. Bodies, structural inheritance, mapping and energy are preserved as declared; founder placement and all neighboring bodies/food remain intact. No isolated arena is used.

[中文登记与用户原话](design.zh.md) · [English design](design.en.md) · [Library operations](../../../docs/en/plans/species-library.md)
