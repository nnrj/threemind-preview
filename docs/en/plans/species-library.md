# Species library and enclosure-candidate selection

2026-10-04. Implemented following the user's follow-up. “Species” names a reusable research asset; archiving an individual does not establish biological speciation.

Models & evidence → Species library supports project-scoped browsing, search, import and export. A `.tmspecies` ZIP contains a versioned manifest and original `.tmind` state, including body traits/state, sensory/motor mapping seed, environment protocol, source time, ancestry and evidence. UI/API/CLI use the same immutable database rows. Corrections and additional evidence create a new bundle rather than overwrite old evidence.

Saving does not train or inject capability labels into Core. Reusing a founder follows existing `birth/1`: structural inheritance with cleared activity/short-term state, inherited body traits, and a declared energy endowment. The original state remains decodable. Individual bundles are not full-world recovery packages; complete ocean snapshots are retained separately.

This phase delivers library management in the UI. Habitat seeding uses `lab.tools.ocean_species.seed_founders` in Python; general graphical deployment orchestration remains unfinished. [E38 runner](../../../lab/explorations/2026-10-04-ocean-species/experiment.py) demonstrates complete-habitat reuse.

CLI: `python -m lab.tools.ocean_species save SNAPSHOT ID OUTPUT --name NAME --evidence JSON`; `import BUNDLE --project UUID`; `list --project UUID`; `export ASSET_ID OUTPUT --project UUID`. API: `GET/POST /api/v2/projects/{project}/species`, `GET .../{id}`, `GET .../{id}/download`. Upload field: `file`. Maximum 64 MiB; strict entries, state identity and finite values are validated under ordinary project permissions.

E37 individual 59's 300 s state is the first candidate; its enclosure occurred at 226.06 s, not at snapshot time. E38 uses 53 bodies including 11 inherited candidates in complete habitats. The first 300 s are shared; thereafter control and half-supply branches differ only in subsequent nutrient replenishment. Researcher replication is explicit. Failed replication is retained; the batch does not run indefinitely until a positive result.

[Design and budgets](../../../lab/explorations/2026-10-04-ocean-species/design.en.md) · [Original user statement](../../../lab/explorations/2026-10-04-ocean-species/design.zh.md) · [中文](../../zh/plans/species-library.md)
