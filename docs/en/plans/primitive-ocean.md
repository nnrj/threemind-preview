# Primitive ocean: from feeding opportunities to environmental selection

2026-10-03. Implementation and experiments started; completion is tracked in E28 and the research backlog.

E27's24individuals obtained no task food and produced no offspring. The user proposed a easier contact-feeding body instead of encoding a correct motor policy into Core. Preserve E27 and ordinary `continuous-memory/2`, including forgetting, inhibition, depletion/recovery and activity-defined death. The new external apparatus is `threemind.ocean/1`; the explicitly funded birth initialization is `ocean-birth/1`.

Identity clarification, 2026-10-03: `ocean-birth/1` names the study's initialization rule; it is not a separate serialized snapshot field. Restore actually checks `threemind.ocean/1`, frozen apparatus source hashes, Core version and state hashes together. The documentary name does not imply a new Core birth protocol implementation.

The apparatus is a periodic planar neutral-buoyancy approximation with inertia, viscous drag, uniform current, local chemical/contact/motion/orientation sensing and an explicitly fixed nonsemantic motor projection. It is not a complete early-Earth or fluid simulation. The16-body limit is a computing boundary that defers reproduction, not natural mortality or ecological carrying capacity. Stillness/circling is not classified as abnormal.

The formal study used a16-body cap; the general tool template defaults to24. They are different configurations, not different ecological death rules.

## Energy and inheritance

Existing ecology separates body resource failure from Core death. E28 therefore credits physically contacted nutrients into a body store and replenishes actual Core expenditures via its existing energy port. Core alone determines whether activity ceases. Standard `birth/1` grants a starting reserve; unlimited cloning of that reserve would manufacture food. E28 explicitly starts offspring with zero free energy, then transfers food deducted from the parent store, plus declared reproductive loss. The parent brain and historical birth behavior are unchanged; new initial configuration identities are rebound correctly.

Only phase two mutates body radius, thrust and sensing range. Predation requires complete geometric enclosure plus dwell, not contact alone. Recover only a declared fraction of bodily food stores; do not duplicate the still-running prey brain's reserve. Body loss closes sensory input; the archived brain continues naturally until genuine death.

## Operation

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
& $py -m lab.tools.ocean_cli template | Set-Content -Encoding utf8 ocean.json
& $py -m lab.tools.ocean_cli validate ocean.json
& $py -m lab.tools.ocean_cli run ocean.json .work/my-ocean --seconds 900 --wall-seconds 1200
& $py -m lab.tools.ocean_cli verify .work/my-ocean
& $py -m lab.tools.ocean_view .work/my-ocean .work/my-ocean-view.html
```

The JSON protocol, Python `Ocean` interface and CLI use one apparatus. `schema` exports the configuration contract. `--resume` accepts an immutable population checkpoint/final directory with its manifest; use a fresh output directory and the unchanged protocol. Snapshots include all brains, birth offsets, world, RNG, nutrient stores and lineage. No database is needed to run them.

The general template is not E28's calibrated formal configuration. Reproduce the first Core-driven world with its saved actual settings:

```powershell
& $py -m lab.tools.ocean_cli run lab/explorations/2026-10-03-primitive-ocean/protocols/phase1-core.json .work/my-ocean-replica --seconds 900 --wall-seconds 1800
```

Phase two also inherits living phase-one brains; enabling `predation` alone does not reproduce that experiment. The runner and evidence archive retain those sources. A complete saved phase-two `initial` checkpoint can be used with `--resume` and its unchanged protocol, without a database.

The offline HTML viewer offers timeline playback, bodies, lineage, intake and reserves from measured records. It does not launch/control training or deliver stimuli. The platform's notes/records/reports display the registration and findings; a dedicated ocean graphical launch/orchestration form remains future work. Do not confuse the viewer with a complete real-time training UI.

`--seconds` is an observation horizon, not a death age. Living individuals are paused and preserved. Create an empty `STOP` file in the output directory for a checkpoint after the current sampling boundary. A forcibly killed process can resume from the latest complete checkpoint; a missing manifest marks an incomplete snapshot. Errors and resource censoring remain separate from death.

## Interpretation and sources

See [E28 registration](../../../lab/explorations/2026-10-03-primitive-ocean/design.en.md) and [execution record](../../../lab/explorations/2026-10-03-primitive-ocean/execution-notes.md). Full-evidence storage was explicitly amended from4GiB to a6GiBsoft/8GiBhard budget without changing scientific criteria.

Feeding, reproduction, useful movement, inherited adaptation and speciation are different endpoints. Common-environment inherited/blank comparisons equalize body, energy and wiring. Temporary size clusters do not establish species; stable heritable and ecological differences require further evidence.

## Original proposal and translation

The verbatim Chinese proposal is preserved in the [Chinese counterpart](../../zh/plans/primitive-ocean.md). Translation: the previous task may be too difficult and its feeding requirement too strict; training should progress gradually. Simulate a nutrient-rich primitive ocean, give consciousness a plankton-like body and feed it on nutrient contact. Let consciousness control movement without prescribing a preference. Provide enough environmental/proprioceptive information to distinguish water, nutrients and posture. No fixed death age; finite global supply should permit starvation if reproduction outruns food. After clear first-stage results, add random beneficial/harmful body mutations and mutually ingestible organisms, requiring one to enclose another and allowing conversion losses. Observe survival selection, competition, adaptation and possibly different species. The user permits corrections or discussion.

The phrase about conversion was interpreted, from the explicit demand for losses, as incomplete rather than perfect recovery. The60%example is a configurable external assumption, not a biological constant or a number specified by the user. A different intended meaning would require a separate digestion model discussion.

## E28 completed

[Report / 报告](../../../lab/explorations/2026-10-03-primitive-ocean/report.en.md) · [Delivery / 交付](../../../lab/explorations/2026-10-03-primitive-ocean/delivery.en.md)
