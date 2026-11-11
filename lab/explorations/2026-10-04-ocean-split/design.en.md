# E41: separate turning/feeding and partial-coverage cultivation

2026-10-04, conditional preregistration. Activate only if both E39–E40 branches reach 900 simulated seconds without a complete-enclosure consumption. A resource stop before that milestone does not satisfy the condition.

The user allows consumption after at least half coverage if full enclosure keeps failing, and requires separate worlds so easier predation cannot dominate turning/feeding cultivation. The Chinese original is preserved in [the Chinese design](design.zh.md).

Fork the **entire shared E39 world at 300 s**, retaining all 70 bodies, brains, ancestry, food, environment and random state. Twenty natural births have already occurred; all three source lineages remain present. Old instances and evidence are not overwritten.

- **turning** disables inter-individual consumption, retaining collisions, senses, body costs, nutrients, mutation and reproduction.
- **coverage** allows consumption when at least 50% of the prey's capsule area is overlapped continuously for the existing shell-adjusted duration, with shell cost and bilateral juvenile protection. Touch alone remains insufficient; contact capture stays disabled.

Neither branch enables sharing, fusion or directed motor policies. Protocol/state `threemind.ocean-enclosure/3` and `state/3` isolate this apparatus; the original full-enclosure environment remains intact. These are distinct cultivation directions, not a declaration that final population counts alone measure controller superiority.

Coverage is capsule intersection area divided by prey area, using a declared fixed 96-segment inscribed polygon approximation. Analytic equal-circle overlap error is below 0.001 in tested coverage, with rotation and periodic-boundary tests. The 50% rule is an approved experimental condition, not a universal biological claim. A 100% setting delegates to the old complete-containment geometry.

Both bodies may qualify simultaneously. The user confirmed contention by the existing body quantity `thrust × (0.25 + grip) × radius²`; exact ties are broken reproducibly by the environment seed, unordered pair and encounter time, retained during contact rather than giving low IDs priority. An alternative `larger` mode requires a larger consumer and is unused here. Read-only geometry queries cannot register a future winner; only an actual environmental step can do that.

Each direction advances 300–600 and 600–900 s, alternating with one worker, at most four segments and two simulation wall hours. New evidence: 4 GiB extension stop, 6 GiB hard limit; process 4 GiB, free RAM 2 GiB, C 5 GiB and E 15 GiB. Actual account baseline +3 points stops extension and +5 stops simulations. Partial completion is reported rather than bypassing the guard.

Retain passive turning criteria and live species archives, including repeated, parent-improved and combined observations. Save measured coverage, shell cost, dwell, energy source, ancestry and full-habitat original-speed clips. Partial consumption is labeled `body_consumed_by_coverage`, never silently described as complete enclosure. The question is whether relaxed environmental opportunity can accumulate and how turning lineages persist without predation; active hunting and internal mechanism attribution still require matched interventions.

[Previous registration](../2026-10-04-ocean-culture/design.en.md)
