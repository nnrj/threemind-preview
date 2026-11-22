# OCEAN63-38　Food supply, predation and descent

We selected a parent on its own observed complete enclosure and consumption of live prey. Parent found — False.

Matched supply branches established — True.

The comparisons below start at the supply change. Both branches shared the entire preceding history of a single world.

600 internal seconds. New grain intakes, predations and births under original and halved supply were [322, 0, 20] / [221, 0, 14] . Increased predation with lower supply — did not meet the criterion.

900 internal seconds. New grain intakes, predations and births under original and halved supply were [767, 0, 49] / [506, 1, 35] . Increased predation with lower supply — met the criterion.

original — IDs of hunters from the candidate lineage [], predations 0, naturally born hunters [].

reduced — IDs of hunters from the candidate lineage [], predations 0, naturally born hunters [].

At least two lineage members account for three or more predations — insufficient observations.

## Observations by world

Counts and living body-minutes start at the beginning of each row. Survivors are counted at its endpoint. A dash denotes a zero denominator or unavailable comparison.

| World | End (internal s) | Survivors | Births | Grains | Living body-min | Grains/body-min | Predations | Carrion meals |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| common | 300.000 | 55 | 7 | 356 | 267.846 | 1.329 | 0 | 0 |
| original | 900.000 | 88 | 49 | 767 | 707.395 | 1.084 | 0 | 0 |
| parent-search | 1200.000 | 88 | 60 | 1342 | 1289.293 | 1.041 | 0 | 0 |
| reduced | 900.000 | 73 | 35 | 506 | 638.768 | 0.792 | 1 | 0 |

Independent environments and paired world branches define the experimental units. We independently counted events and living-body time from every 20-millisecond tick and checked checkpoint identity, timestamps, feedings, births and predations. Exact outcomes and lineage and time-point details are in findings.json.

## Comparison with the historical observations

Historical E38 used the saved state of individual 59 at 300 internal seconds, after its own predation event. The 6.3 study saves the new parent's state at its first qualifying event. Both historical branches were observed through 600 internal seconds.

| Supply | Historical total grains | 6.3 total grains | Historical total births | 6.3 total births | Historical post-fork predations | 6.3 post-fork predations |
|---|---:|---:|---:|---:|---:|---:|
| original | 858 | 678 | 24 | 27 | 0 | 0 |
| reduced | 740 | 577 | 21 | 21 | 0 | 0 |

Historical source in the repository: `lab/explorations/2026-10-04-ocean-species/report.r2.en.md`.
