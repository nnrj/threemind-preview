# Bodily associations remain retrievable after 300 seconds and depend on cue-output connections

13 November 2026, R51f, `continuous-memory/6.1`. Research record: `facdd50e-2c7f-5399-8237-7ac26537913e`. [Preregistered protocol](protocol.en.md) · [中文](report.zh.md) · [Campaign coverage](../coverage.en.md)

**This batch confirms that associations taught by pairing bodily sensations with anonymous markers remain retrievable after 300 internal seconds. All 192 trained cue probes produced the correct response direction; untrained controls passed 0/48. Blocking the cue node's outgoing connections eliminated retrieval in all 32 interventions. Removing the block restored complete states and all four activity trajectories exactly. Version 6.1 reproduced the E18 retention and connection-causality findings.**

The historical convergence score was 0/240: both task targets had ceased to be active by the readout's convergence point. The two preregistered targets therefore have distinct, explicit outcomes. Experience could be re-expressed by a cue, while the final converged state did not retain the transient response. Recording the full process detected the response that had occurred.

## Experimental organization

Actual measurements from two initial postures of a gravity-driven pendulum were paired with anonymous A/B markers. The continuous 32-episode course presented each posture 12 times consecutively, followed by four interleaved presentations of each. Each episode contained 0.4 seconds of physical input and a 0.2-second tail. Retention periods supplied only independent maintenance stimuli, without task rehearsal.

Four formal encoding blocks, 930101–930104, were tested under ordinary defaults and a one-second facilitation time constant. Sensory conditions were full input, joint position/velocity only, full input matched to the joint-only dose, shuffled inertial measurements, and no teaching. Each delay used separate research copies, preventing earlier tests from rehearsing later tests. Sixteen conditions on separate calibration seed 930199 selected a common intensity of 0.3 by the frozen rule. Formal cue intensity was 0.45.

The 616 formal conditions comprised 40 teaching lives, 120 retention copies, 360 cued/uncued probes and 96 intervention copies at 300 seconds. Including calibration, 632 conditions produced 1,264 complete initial/final states. Scientific replication comprises four encoding blocks; configurations, cues, delays and copies are nested observations. Subjects retained Core, clock, random state, inputs and fixed encoding. Bodily inputs were hash-verified physical recordings. The temporal readout was passive, with no trainable peripheral.

Every 100 ms, all-node activation, inhibition, direct activation and associative activation were recorded. Process scoring first subtracted the same-parent, same-time blank trajectory, then tested a measurable expected-target increment and an activation integral larger than the other target's. All 336 cued and intervention probes had the same complete 51-point grid spanning five seconds; no missing interval was filled with zero.

## Retention and temporal expression

Each cell contains four blocks and two cues, giving eight probes. Both configurations had the following counts.

| Sensory condition | After 1 s | After 60 s | After 300 s |
|---|---:|---:|---:|
| Full | 8/8 | 8/8 | 8/8 |
| Joint position/velocity only | 8/8 | 8/8 | 8/8 |
| Dose-matched full input | 8/8 | 8/8 | 8/8 |
| Shuffled inertial measurements | 8/8 | 8/8 | 8/8 |
| Untrained | 0/8 | 0/8 | 0/8 |

Mean expected-target activation integrals relative to the blank are below, in activation-strength × internal seconds.

| Configuration and sensation | 1 s | 60 s | 300 s |
|---|---:|---:|---:|
| Ordinary, full | 0.005531 | 0.012449 | 0.008238 |
| Ordinary, joint-only | 0.007112 | 0.013822 | 0.008967 |
| Ordinary, dose-matched | 0.005533 | 0.011950 | 0.007987 |
| Ordinary, shuffled inertial | 0.005531 | 0.012452 | 0.008239 |
| Facilitation, full | 0.005110 | 0.013199 | 0.008451 |
| Facilitation, joint-only | 0.007600 | 0.015094 | 0.009713 |
| Facilitation, dose-matched | 0.005900 | 0.012781 | 0.008283 |
| Facilitation, shuffled inertial | 0.005129 | 0.013203 | 0.008452 |

Responses were stronger at 60 seconds than at one second, then weakened at 300 seconds. Retention and expression therefore showed a nonmonotonic relationship. Facilitation increased the mean 300-second integral in every sensory condition. For full sensation, it rose from 0.008238 to 0.008451, approximately 2.58%. This batch establishes that configuration difference on the registered measure; the local-resource and prediction studies will test its internal components separately.

Before the 300-second cue, task-target activation, inhibition and direct-activation records were zero. Associative-activity records still contained nonzero values, up to 0.00114034. The paired cued-minus-blank comparison identifies the subsequent correct response as an effect of the cue.

## What the interventions establish

| Intervention | Probes | Process result | State and trajectory checks |
|---|---:|---|---|
| Block all outgoing cue connections | 32 | Correct retrieval 0/32; target increment integrals all zero | The cue no longer elicited task-target activity |
| Block matched other connections | 32 | Correct retrieval 32/32 | Expected-target integrals were unchanged or increased by 0–0.273% |
| Apply and immediately remove the block | 32 | Correct retrieval 32/32 | All complete Core states identical; maximum all-node error across four activity fields was zero |

Matched sets had equal edge counts and were selected by pre-cue weight and stability distance, excluding the cue and both task targets. Maximum individual matching distance was 0.051427; all edge-level residuals are preserved. Matched blocking changed some other activity, with a maximum whole-network trajectory difference of 0.004243, while retaining every correct task direction. This contrasts with complete elimination of retrieval under target blocking.

**The intervention establishes the retained outgoing cue connections as necessary pathways for re-expressing the bodily association.** With cue, delay and readout fixed, removing that pathway removes the response, and restoring it restores the response exactly. Together with the absent untrained response, this connects teaching-induced associations, retained internal connections and later retrievable output.

## Scientific conclusion and continuation

This batch fully reproduced E18's 192 trained process-retention probes and 48 untrained controls, together with its 32 causal blocking/restoration comparisons. This is a favorable result for ThreeMind: fixed-function addressing, local deletion and emission thresholds in 6.1 preserved associative retention and cued expression in this apparatus. The 300-second retention target was met.

The stable converged-output target failed, at 0/240. This directly supports temporal readout for these responses: activity appeared during the process and then subsided, so reading only the convergence point missed the response. Retention duration and immediate expression strength should accordingly be measured separately.

No campaign scientific stopping condition was triggered. Continue the registered five-system criteria, bodily transfer, sequence and remaining mechanism studies. This batch does not replace the still-pending transfer, sequence and closed-loop parts of E18.

## Verification, resources and evidence

Identity, time, parent relationships and fixed-function addressing passed verification for all 1,264 states. A separate read-only program recomputed 336 trajectories using 45-digit Decimal arithmetic, with a maximum arithmetic discrepancy of 1.73×10⁻¹⁸. No Core engine was loaded or advanced. These are internal checks performed by the research assistant. Separate instrument and calibration originals are retained.

The formal host took 2,229.45 seconds, or 37.16 minutes; calibration took 10.70 seconds. Timers inside individual conditions summed to 1,409.17 seconds. The host timer also covers loading, saving and boundary checks; separate kernel performance measurements are reported in R51c. Maximum observed size was 12 nodes and 60 directed connections. Private memory peaked at 946.43 MiB in one-second samples. Minimum commit/RAM/C/E headroom was approximately 12.80/12.41/10.50/91.48 GiB, above the 5/4/5/25-GiB reserves. Pre-analysis originals occupied 246.36 MiB logically and 255.91 MiB of allocated storage; archive and API readback copies are additional.

Originals are in `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/body-memory61-v1/`. `frozen.json` records protocol, material, source and native-binary hashes; `analysis.json` contains complete denominators and condition-level results; `audit.json` and `arithmetic-verification.json` record verification. Final delivery is established by `publication/completion.json`, complete API readback and pending=0. Historical E18 reports, kernels and originals remain unchanged.
