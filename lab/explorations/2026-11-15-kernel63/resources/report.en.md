# R51t14: Independent synaptic resources implemented in 6.3; prefix discrimination was not restored

2026-11-15. Research record: `f954be8d-6e00-56e1-bb72-ef86d4502e94`.

**Conclusion: separate excitatory and inhibitory synaptic resources are implemented in Python and Rust. Separating resources alone did not restore prefix discrimination in this batch. Shared resources remain the default.** Both resource modes passed 0/2 material blocks under each of four retention/allocation configurations. Independent resources changed response magnitudes and, in one configuration, the preferred ending. They did not make each prefix favor its own correct ending.

## Implementation and use

The new 6.3 setting is `config.separate_inhibition_resources`: `false` selects shared resources and is the default; `true` selects independent pools. The UI exposes the same choice. It is fixed at birth and stored in the complete artifact. Earlier 6.3 artifacts lacking this field retain shared operation.

Shared mode preserves the original release procedure: both signal types in one connection emission use the same resource state and release fraction. Independent mode stores available, active and temporarily unavailable resources and utilization separately. Each pool recovers under identical parameters. Excitatory transmission depletes only the excitatory pool, and inhibitory transmission only the inhibitory pool. Inhibition remains resource-limited and continues to reinforce the connection. Weights, short-term enhancement, retention and learning records remain shared. Sending thresholds, connection thresholds, decay and usage-time rules are unchanged.

Each pool starts with available resources of 1. This option removes interaction through a common resource state and increases combined available capacity. The experiment tests that complete proposal. Separating these two contributions would require a separately specified comparison; none was added to this batch.

Python, native Rust and the standalone Rust runtime implement the option. JSON and tmind artifacts retain both resource states. Offspring still reset fast state under the existing birth rule. A missing optional-field entry in artifact validation was corrected and tested before formal computation. The global creation default remains kernel 6.1; existing services were not restarted.

## Purpose, expectation and design

We tested the expectation that separate resource pools would restore prefix discrimination while inhibitory learning remained enabled. Materials and scoring criteria were inherited unchanged.

Profile P uses 6.3's default inverse-log retention, arrival-window novelty and transmission settings. Profile S uses stability retention, immediate novelty and an excitatory connection threshold of 0.004. Each profile compares per-connection inhibitory transmission and allocation in proportion to effective connection weights, crossed with shared versus independent resources. Within a resource pair, only the new option differs. Inhibitory learning remains enabled; inhibition does not update last transmission time. See the [protocol](protocol.en.md) for complete settings.

Each condition receives two teaching blocks with exchanged endings, developing continuously for 212.2 internal seconds. A complete teaching reference is retained; AB and DB are registered diagnostic copies. A or D is followed one second later by the same B. Activity is observed for 15 seconds at 10-ms intervals, giving 1502 points per process. Eight conditions × two blocks × training and two diagnostics give 48 stages. The units are two material blocks; copies and observations do not increase independent N. No trainable readout is added to this passive mechanism test.

In the first block, C is correct after AB and E after DB; the second block exchanges the endings. After B, the correct ending's peak activation must exceed the alternative by more than 1e-6. Both prefixes must pass for a block to pass, and both blocks must pass to declare restoration. These criteria were fixed before computation.

## Results

Margins below are the correct peak minus the alternative peak. Positive values point in the correct direction. The two blocks have identical answer-adjusted margins, so the table gives one set; all 32 diagnostic scores appear in [scores.csv](scores.csv).

| Profile | Inhibitory allocation | Resources | AB margin | DB margin | Blocks passed |
| --- | --- | --- | ---: | ---: | ---: |
| P | Per-connection | Shared | -0.000133286 | +0.000133321 | 0/2 |
| P | Per-connection | Independent | -0.000073069 | +0.000072017 | 0/2 |
| P | Proportional | Shared | -0.000136852 | +0.000136902 | 0/2 |
| P | Proportional | Independent | +0.000061865 | -0.000061888 | 0/2 |
| S | Per-connection | Shared | +0.001559534 | -0.001559515 | 0/2 |
| S | Per-connection | Independent | +0.001700958 | -0.001700915 | 0/2 |
| S | Proportional | Shared | +0.001663111 | -0.001663101 | 0/2 |
| S | Proportional | Independent | +0.001848867 | -0.001848832 | 0/2 |

For P with per-connection transmission, AB's C/E peaks were 0.019635489/0.019768775 with shared resources and 0.019729611/0.019802679 with independent resources. The incorrect preference weakened, but E remained larger than C. E was also larger after DB: both prefixes still favored the same ending. With proportional allocation in P, independent resources changed the common preference from E to C. Both S allocation conditions continued to favor C after either prefix. These changes concern ending preference, not recovery of the prefix-dependent correspondence.

The independent pools were used. Teaching endpoints contained 124–201 separate inhibitory resource states. In the first P/per-connection AB diagnostic, total inhibitory signal delivered to target nodes increased from approximately 0.06590 to 0.29151, while excitatory transmission was approximately 2.26786 and 2.26714. Inhibition was not disabled: it received its own resources, with a measurable change in transmission. Separate pools therefore do not reproduce inhibition bypassing resource consumption. These transport totals interpret the result; they do not replace the primary prefix score.

No condition met the preregistered trigger for new-encoding tests. The batch ended after 48 stages without additional search. R51t11's historical 2/2 result remains intact under its complete configuration, including inhibitory resource bypass and disabled explicit inhibitory learning.

## Performance and integrity

The 32-node, 60-internal-second benchmark used one warm-up and five measured runs per condition. Medians follow. Old and new shared modes had exactly matching numerical states and events.

| Inhibitory allocation | Resource mode | Median time (ms) | Events | State (KiB) | Peak process commit (MiB) |
| --- | --- | ---: | ---: | ---: | ---: |
| Per-connection | Old shared | 159.29 | 1771 | 603.73 | 29.29 |
| Per-connection | New shared | 161.27 | 1771 | 603.81 | 29.24 |
| Per-connection | New independent | 161.07 | 1772 | 724.97 | 30.61 |
| Proportional | Old shared | 227.26 | 1769 | 603.72 | 29.27 |
| Proportional | New shared | 230.00 | 1769 | 603.79 | 29.16 |
| Proportional | New independent | 230.22 | 1771 | 725.09 | 30.59 |

Shared-mode median time increased by approximately 1.2% after adding the option. Independent and new shared modes differed by less than 0.2%. This short benchmark shows no substantial runtime cost, while independent resources increased complete-state size by approximately 20.1% and process peak commit by 4.7–4.9%. These measurements describe this machine and material. Formal prefix teaching and diagnostic computation summed to 99.78 seconds; the host took 130.46 seconds including saving and other work. Peak process private memory was approximately 95.44 MiB; originals occupied 49.79 MiB at audit.

All 96 complete states and 32 processes were verified. A separate read-only calculation reproduced every prefix score with zero difference. Forty-eight shared teaching and diagnostic boundaries exactly matched their numerical counterparts in R51t13, with new configuration metadata accounted for separately. Observation, save/restore, partitioned advancement and wall-clock pauses produced identical complete states in all eight apparatus conditions. There were 692 passing engineering/interface checks and seven environment-dependent skips; 6.3 Python/native Rust and standalone JSON/tmind checks were executed. The frontend build passed.

## Scientific conclusion and decision

**This batch rejects the expectation that separating synaptic resources alone is sufficient to restore prefix discrimination.** Independent pools are an effective dynamical intervention, but did not produce the required prefix selectivity in these four configurations. This is an unfavorable result for the proposed direct solution and a useful constraint on further diagnosis: resource separation has now been implemented and tested, and should not continue to be presented as an untested immediate remedy.

The independent-resource option is retained as requested, with shared operation as the default. Prefix recovery remains unresolved, and the broader revalidation programme remains paused. No thresholds, inhibitory-learning settings or training duration were changed to obtain a pass. Earlier reports and scores are preserved.

## Reproduction and delivery

- [Preregistered protocol](protocol.en.md), [independent scoring and state audit](audit.py), [summary](summary.json), and [all diagnostic scores](scores.csv).
- Originals: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/resources63-v1`, containing complete states, inputs, processes, frozen source, resource logs and benchmark evidence.
- The [research API receipt](delivery.json) records archive verification, full readback and pending requests. These checks are author-side automated verification, not independent replication by an external researcher.
