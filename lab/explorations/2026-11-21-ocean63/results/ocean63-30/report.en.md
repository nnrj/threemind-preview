# OCEAN63-30　Neural propagation and feeding

Starting from each of two independent environments, we compared four controllers. Each group began with 31 individuals and received the sensory consequences of its own movements.

Feeding with Core control versus both random controls — did not meet the criterion.

The differences in feeding rate between full propagation and direct sensory responses were -0.907, 0.174 grains per living body-minute in the two environments. Consistent gain — did not meet the criterion.

The direct-response control retained its own Core and peripherals. Propagation and inhibitory diffusion were disabled from birth, so subsequent action, sensation and energy use contributed to the observed difference.

## Observations by world

Counts and living body-minutes start at the beginning of each row. Survivors are counted at its endpoint. A dash denotes a zero denominator or unavailable comparison.

| World | End (internal s) | Survivors | Births | Grains | Living body-min | Grains/body-min | Predations | Carrion meals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| world-0-core | 600.000 | 23 | 10 | 192 | 223.202 | 0.860 | 18 | 0 |
| world-0-direct | 600.000 | 11 | 24 | 229 | 129.589 | 1.767 | 44 | 0 |
| world-0-random | 600.000 | 11 | 9 | 241 | 152.995 | 1.575 | 24 | 0 |
| world-0-random-fast | 600.000 | 25 | 0 | 58 | 288.899 | 0.201 | 1 | 0 |
| world-1-core | 600.000 | 10 | 9 | 234 | 136.591 | 1.713 | 26 | 0 |
| world-1-direct | 600.000 | 19 | 26 | 246 | 159.816 | 1.539 | 38 | 0 |
| world-1-random | 600.000 | 12 | 10 | 251 | 156.336 | 1.606 | 26 | 0 |
| world-1-random-fast | 600.000 | 22 | 0 | 60 | 274.929 | 0.218 | 2 | 0 |

Independent environments and paired world branches define the experimental units. We independently counted events and living-body time from every 20-millisecond tick and checked checkpoint identity, timestamps, feedings, births and predations. Exact outcomes and lineage and time-point details are in findings.json.

## Comparison with the historical observations

| World | Controller | Historical grains | 6.3 grains | Historical grains/body-min | 6.3 grains/body-min |
|---|---|---:|---:|---:|---:|
| 1 | core | 401 | 192 | 3.497 | 0.860 |
| 1 | random | 268 | 241 | 2.537 | 1.575 |
| 1 | random-fast | 46 | 58 | 0.297 | 0.201 |
| 2 | core | 355 | 234 | 3.459 | 1.713 |
| 2 | random | 324 | 251 | 2.477 | 1.606 |
| 2 | random-fast | 35 | 60 | 0.252 | 0.218 |

Historical source in the repository: `lab/explorations/2026-10-03-ocean-causality/report.r2.en.md`.
