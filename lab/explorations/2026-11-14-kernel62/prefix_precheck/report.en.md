# Restoring prefix discrimination: pre-release screening has a causal role

15 November 2026 · R51t8 · Research record `9e626bd1-2fee-501a-bf0f-ec3c08309496`.

## Scientific conclusion

**Screening weak signals before resource release is a key condition for restored prefix discrimination.** Adding only this step to the previously unsuccessful historical-inhibition/0.004 condition restored both curricula. Removing only this step from the successful complete historical emission process abolished discrimination in both. These forward and reverse interventions provide convergent causal evidence.

**Recovery also depends on the accompanying inhibitory transmission rule and threshold.** This study holds stability retention and immediate novelty fixed while comparing emission. With 6.2 inhibition, neither the 0.0004 nor the 0.004 threshold restored discrimination. Historical inhibition with the 0.0004 threshold also failed. The successful combination was **pre-release screening, an excitatory connection threshold of 0.004, and historical inhibitory transmission**. Production 6.2 and its defaults remain unchanged.

## Purpose and expectations

R51t7 restored discrimination in a research derivative retaining 6.2 fixed-function addressing, but replaced the complete emission process. Here we isolated a specific difference: whether resources are released and consumed before rejecting a signal below the final amount threshold.

Three questions were registered: whether adding pre-release screening rescues a specified failed combination; whether removing it destroys success; and whether recovery also depends on threshold magnitude and inhibitory transmission. All retain the original decision rules. [Preregistered protocol](protocol.en.md)

## Experimental organization

The two exchanged curricula teach A–B–C and D–B–E, exchanging C/E in the second. Each new research subject receives 212.2 internal seconds of continuous teaching. The complete trained parent is preserved. Separate, declared AB and DB diagnostic copies then test whether the earlier A or D changes the correct ending evoked after the same B. These copies and their purpose were disclosed before execution; parents were not rolled back or overwritten.

There is no trainable readout, body or actuator. Anonymous stimuli, doses, timing and order match the frozen materials; expected answers reach only the scorer. Activation, inhibition, direct and associative activity are recorded every 10 ms, with teaching states every 100 ms. The primary measure is the correct-ending activation peak minus the alternative peak after B. Both prefixes must exceed 1e-6 to pass a curriculum.

Historical inhibitory transmission distributes the node's available inhibitory output in proportion to neighboring connections' base weights. This pathway does not consume connection-level synaptic resources or strengthen connections. In 6.2, excitation and inhibition travel along directed connections through a shared resource-release process, and inhibition can contribute to learning. This study compares these two existing pathways without separately modifying their constituent rules.

Five new conditions, two blocks and three stages per block give 30 new stages. Five corresponding controls reuse 30 completed R51t7 stages, with their hashes, states and traces checked again. The unit remains two curriculum blocks. Branches and recording points do not add independent replication. This is causal localization on existing development materials.

## Results

The table shows the first curriculum; the exchanged curriculum yields the same verdicts. Positive differences favor the correct ending. Thresholds refer to the excitatory connection signal amount; source-node threshold parameter values are not adjusted. The 6.2 inhibitory connection threshold stays at 0.0004. All conditions use stability retention and immediate novelty.

| Condition | AB peak difference | DB peak difference | Curricula passed | Evidence |
|---|---:|---:|---:|---|
| 6.2 inhibition, 0.0004, no pre-screening | 0.000997287 | -0.000997332 | 0/2 | R51t7 originals |
| Same, with pre-screening | 0.000998074 | -0.000998136 | 0/2 | New runs |
| 6.2 inhibition, 0.004, no pre-screening | 0.000570700 | -0.000570702 | 0/2 | R51t7 originals |
| Same, with pre-screening | 0.001558728 | -0.001558713 | 0/2 | New runs |
| Historical inhibition, 0.0004, no pre-screening | 0.000558579 | -0.000558675 | 0/2 | R51t7 originals |
| Same, with pre-screening | 0.000557867 | -0.000557963 | 0/2 | New runs |
| Historical inhibition, 0.004, no pre-screening | 0.000318883 | -0.000318894 | 0/2 | R51t7 originals |
| **Same, with pre-screening** | 0.000978373 | 0.002735434 | 2/2 | New runs |
| Complete historical emission | 0.000978373 | 0.002735434 | 2/2 | R51t7 originals |
| Complete historical emission, removing only the pre-release amount check | 0.000318883 | -0.000318894 | 0/2 | New runs |

| Preregistered question | Result and scientific judgment |
|---|---|
| Does adding pre-screening rescue historical inhibition at 0.004? | **Yes: 0/2 becomes 2/2. That addition is sufficient in this combination.** |
| Does removing only the pre-release amount check destroy the successful historical process? | **Yes: 2/2 becomes 0/2. The check is necessary within that successful combination.** |
| Does pre-screening also restore the tested combinations retaining 6.2 inhibition or the lower threshold? | **No: all three yield 0/2, rejecting sufficiency in those combinations.** |

## How the ordering affects learning

Let effective connection weight be w, the node's offered signal S, and the distance factor d. The pre-release amount is q=wSd. Resource release multiplies it by a release fraction r, where 0≤r≤1. Let θ denote the connection signal threshold.

When q is already below θ, qr remains below θ. The existing 6.2 process can nevertheless release resources before discarding this inevitably subthreshold signal. The research candidate compares q with the same threshold before release. For the shared 6.2 transmission path, release is skipped only when neither signal type can pass. Otherwise resources are released once and the post-release tests remain. No third threshold or change to source-node emission was introduced.

The earliest recorded difference occurs at 3.9 internal seconds on A→B and B→A. Projected to that same time, available resource is 0.215375 with screening and 0.107688 without it: exactly half. Recorded node activity, base weights and stability are still identical at that point. The calculation accounts for the different lazy-update timestamps. Weight and response differences appear subsequently.

The screened successful condition matches the complete historical-emission reference at **all 4,246 teaching recording points** across both curricula: task-node states, connection weights, stability and short-term resources agree exactly. The two prefix response differences also agree. The successful reference can therefore be reproduced by a more explicit combination rather than treating the entire historical emission method as an indivisible remedy.

The interventions support a concrete explanation: **resource consumption by unsuccessful transmission changes later propagation and, consequently, the weight relations and responses formed through experience.** This is a dynamical effect, not merely a computational optimization. The failed lower-threshold and 6.2-inhibition comparisons identify the accompanying conditions that the demonstrated recovery requires.

## Implications for ThreeMind

The study narrows the complete emission replacement to a resource-release condition supported by forward and reverse intervention, together with an explicitly tested threshold/inhibition combination. Prefix discrimination should remain a functional check for future kernels: it reveals changes in capability that measurements of connection survival, activation magnitude or short-lived responses can miss.

Fixed-function addressing remains in every new condition. Loss and recovery occur with the same addressing through changes in transmission. Preserve the successful combination as a reference for subsequent implementation. If retaining 6.2 inhibitory transmission is the goal, its resource use, inhibitory allocation and learning contributions should receive separately registered comparisons. The present authorization covers localization; production kernels, defaults, the comprehensive replication and the manuscript were not changed.

## Validation and delivery

Apparatus tests used separate encodings. With screening off, three reference modes match the previous implementation's complete scientific states. Observation on/off, full restoration, partitioned advancement and host pauses yield identical final states for each new candidate. An AST check confirms that the reverse intervention removes exactly one pre-release amount comparison.

All 30 new stages completed without a resource pause or simulation rollback. Summed execution time was 22.95 minutes; peak process private memory was 95.37 MiB. Read-only auditing covers 120 initial/final states, 40 diagnostic traces and complete parentage. Independent recalculation of peaks and integrals across all four activity measures has a maximum discrepancy of 3.9e-18. Frozen kernel source hashes are unchanged. Completed controls were not rerun.

Originals: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/prefix-precheck62-v1`. `analysis.json` contains the matrix and first differences; `resource-analysis.json` contains same-time projections; `audit.json` records verification. The final receipt for complete-package API readback and zero pending requests is `publication/completion.json`, mirrored as `delivery.json` in the repository. This is project-internal experimentation and independent arithmetic verification; external reproduction is recorded separately.

[R51t7 recovery study](../prefix_recovery/report.en.md) · [Strengthening, stability and novelty analysis](../../2026-11-13-kernel61/prefix_components/report.en.md)
