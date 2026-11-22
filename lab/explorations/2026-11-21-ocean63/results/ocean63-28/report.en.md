# OCEAN63-28　Feeding and reproduction with finite energy

We compared Core, passive and random control in three independent environments to test whether feeding could sustain reproduction.

Joint feeding, reproduction and energy-shortage test — met the criterion. Worlds meeting the feeding and reproduction criterion were [0, 1, 2].

In the common garden, feeding-rate differences for inherited versus blank Cores were -0.350, -0.350, -0.100 grains per living body-minute. Consistent benefit from inheritance — did not meet the criterion.

## Observations by world

Counts and living body-minutes start at the beginning of each row. Survivors are counted at its endpoint. A dash denotes a zero denominator or unavailable comparison.

| World | End (internal s) | Survivors | Births | Grains | Living body-min | Grains/body-min | Predations | Carrion meals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| common-0-blank | 300.000 | 4 | 0 | 100 | 20.000 | 5.000 | 0 | 0 |
| common-0-inherited | 300.000 | 4 | 0 | 93 | 20.000 | 4.650 | 0 | 0 |
| common-1-blank | 300.000 | 4 | 0 | 187 | 20.000 | 9.350 | 0 | 0 |
| common-1-inherited | 300.000 | 4 | 0 | 180 | 20.000 | 9.000 | 0 | 0 |
| common-2-blank | 300.000 | 4 | 0 | 181 | 20.000 | 9.050 | 0 | 0 |
| common-2-inherited | 300.000 | 4 | 0 | 179 | 20.000 | 8.950 | 0 | 0 |
| ecology-0-core | 900.000 | 14 | 12 | 312 | 214.548 | 1.454 | 0 | 0 |
| ecology-0-passive | 381.060 | 0 | 0 | 31 | 29.515 | 1.050 | 0 | 0 |
| ecology-0-random | 900.000 | 10 | 11 | 334 | 167.910 | 1.989 | 0 | 0 |
| ecology-1-core | 900.000 | 16 | 10 | 321 | 225.994 | 1.420 | 0 | 0 |
| ecology-1-passive | 900.000 | 1 | 0 | 50 | 56.762 | 0.881 | 0 | 0 |
| ecology-1-random | 900.000 | 13 | 12 | 336 | 187.319 | 1.794 | 0 | 0 |
| ecology-2-core | 900.000 | 16 | 11 | 323 | 227.530 | 1.420 | 0 | 0 |
| ecology-2-passive | 342.060 | 0 | 0 | 19 | 26.040 | 0.730 | 0 | 0 |
| ecology-2-random | 900.000 | 13 | 13 | 335 | 200.158 | 1.674 | 0 | 0 |
| enclosure-0 | 900.000 | 16 | 8 | 327 | 212.086 | 1.542 | 0 | 0 |
| enclosure-1 | 900.000 | 8 | 16 | 330 | 165.369 | 1.996 | 14 | 0 |
| enclosure-2 | 900.000 | 14 | 14 | 323 | 201.277 | 1.605 | 4 | 0 |

Independent environments and paired world branches define the experimental units. We independently counted events and living-body time from every 20-millisecond tick and checked checkpoint identity, timestamps, feedings, births and predations. Exact outcomes and lineage and time-point details are in findings.json.

## Comparison with the historical observations

| Controller | Historical grains | 6.3 grains | Historical births | 6.3 births | Historical survivors | 6.3 survivors |
|---|---:|---:|---:|---:|---:|---:|
| core | 1006 | 956 | 24 | 33 | 48 | 46 |
| passive | 137 | 100 | 0 | 0 | 0 | 1 |
| random | 1005 | 1005 | 24 | 36 | 47 | 36 |

Historical source in the repository: `lab/explorations/2026-10-03-primitive-ocean/report.r2.en.md`.
