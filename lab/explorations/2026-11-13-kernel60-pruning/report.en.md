# R50: 0.018 removes weak connections but loses some novelty responses; retain 0.008

13 November 2026. [中文](report.zh.md) · [Preregistered protocol](protocol.en.md)

## Conclusion and decision

**The candidate failed the default-parameter validation. The 6.0 connection deletion threshold remains 0.008.** Raising it to 0.018 removed residual weak-stimulation connections in all eight origins at 30 seconds, while preserving all 300-second responses after massed repetition, spaced review and strong stimulation. However, it deleted the new target connections in four of eight novelty-course origins and eliminated their corresponding responses. It therefore failed the preregistered joint requirement to clear weak traces and preserve existing learned responses.

This is a completed negative parameter validation. It rejects adopting 0.018 as the default in this configuration and identifies the cost: some novelty-related traces are removed along with weak residual connections. No Core formula, kernel default, historical individual or earlier report was changed.

## Purpose, expectation and design

Retrospective R47b inspection found weak-stimulation weights near 0.017 at 30 seconds and generally higher target weights after three retention courses at 300 seconds. That suggested 0.018 but did not measure development under the higher threshold or establish preservation of novelty responses. Here both thresholds operated from birth.

Eight new independent origins supplied 640 continuous sequences, 320 per threshold. Courses, opposite histories, cue omissions and delay cohorts are paired observations within each origin; independent N is eight. Every sequence proceeded from birth through teaching to its first probe, without restoring an earlier state.

Both arms used 6.0, inverse-logarithmic decay, a 30-internal-second scale, continuing reinforcement age, and disabled retention-scale growth, relaxation and dormancy. The signal threshold remained enabled at 0.0004; the connection weight gate remained disabled. Only prune_weight differed.

The five R47 courses were a single weak pairing, eight massed pairings, eight progressively spaced reviews, a strong stimulus, and a novelty pairing. In the last course, a cue was paired with one output and then, 50 or 75 milliseconds later, with the other. Thus the same local network held two successive relationships. Novelty was distinct from repeated teaching.

A fixed passive instrument recorded twenty frames each during the one-second pre-cue baseline and response, measuring activation, inhibition, direct activation and associative activation. Subtracting baseline, cue omission and opposite histories yielded the experience-specific response. This local mechanism assay had no trained reader or body and was not a Transformer-based capability study.

Acceptance required weak-trace removal in at least six of eight origins, retained connections and measurable responses in at least six for each of the three retention courses, and preservation of paired response shape and connections in all eight origins for all four retained courses at each endpoint. Novelty was tested for added harm, without adding an absolute response-amplitude requirement. All targets were closed under these original rules.

## Results

| Endpoint | 0.008 | 0.018 | Interpretation |
| --- | --- | --- | --- |
| Both target directed connections present 1 second after weak stimulation | 8/8 | 8/8 | Both arms initially formed the connections |
| Both target connections absent 30 seconds after weak stimulation | 0/8 | 8/8 | The higher threshold cleared residual weak connections |
| Connections and response retained 300 seconds after massed repetition | 8/8 | 8/8 | Response vectors were exactly equal across arms |
| Connections and response retained 300 seconds after spaced review | 8/8 | 8/8 | Response vectors were exactly equal across arms |
| Connections and response retained 300 seconds after strong stimulation | 8/8 | 8/8 | Response vectors were exactly equal across arms |
| New target connections retained 300 seconds after the novelty course | 8/8 | 4/8 | Half the origins lost the new target connections |
| Novelty response met paired-preservation rules at 300 seconds | Reference | 0/8 | Four responses disappeared; four became stronger and changed, rather than disappearing |

All courses passed the cross-threshold preservation checks at one second. At 300 seconds, response RMS ranges were 0.00027961–0.00036692 for massed teaching, 0.00031152–0.00041385 for spaced review and 0.00034774–0.00044834 for strong stimulation, exactly equal across thresholds.

At 30 seconds, weak-course experience-specific responses were zero in both arms. The benefit was therefore **removal of residual connections**, rather than behavioral forgetting newly caused by the candidate. Under the lower threshold, connections remained, but this cue and temporal instrument already elicited no measured experience-specific response.

Novelty-course baseline-arm RMS at 300 seconds ranged from 0.00007974 to 0.00010525. Under 0.018, origins 0, 1, 2 and 7 fell to zero, whereas origins 3, 4, 5 and 6 rose to 0.00026990–0.00028071. The latter four retained stronger responses and must not be described as having lost them.

The 95% Wilson intervals are approximately 67.6%–100% for 8/8, 21.5%–78.5% for 4/8, and 0%–32.4% for 0/8. These describe small-sample uncertainty; the observed counts and the decision remain explicit.

## Why novelty was affected

The following post-hoc connection inspection is saved separately in retrospective-diagnostics-v1.json; it does not replace the primary outcome.

In the four origins that lost the new target, corresponding baseline connections still weighed 0.01723–0.01786 at 300 seconds, below the proposed threshold. They had been deleted in the 0.018 arm, with the cue responses disappearing. **A relatively weak connection can represent either a disposable one-off trace or a novelty-related experience that still produces a response.** Current weight alone did not completely separate them in this study.

In the other four origins, new target weights remained 0.01882–0.01960 and were exactly equal across arms. The higher-threshold arm had instead removed other connections left by the earlier pairing, and the response became stronger. The paired intervention identifies the threshold change as the cause. Assigning that increase specifically to inhibition or competition would require an additional intervention, so this is recorded as a mechanistic lead rather than a completed attribution.

**The study identifies both the benefit and cost of raising the threshold.** It clears weak residual connections and preserves three stronger courses but changes the network formed by successive novelty pairings. The original proposal considered the three retention courses and missed this cost. This paired validation corrects the basis for the default decision. Further work should address the overlap between weak-trace removal and novelty retention rather than raise the deletion threshold across the board. This batch does not search additional values or change decay formulas.

## Verification, resources and evidence

All twelve instrument engineering checks passed. A separate program verified 1,280 complete boundaries, 2,560 state/result file hashes, and independently recomputed every decision. All 640 actual curricula and 320 paired input streams matched registration. The original audit stopped because it compared string-encoded checkpoint timestamps directly with integer receipt timestamps. The frozen audit.py is preserved; audit_v2.py adds only integer conversion. No data, scientific formula, criterion or experimental execution changed.

| Cost | Measured value |
| --- | --- |
| Scientific host wall time | 90.28 seconds |
| Teaching/probe operation time | 22.29 seconds for 0.008; 21.96 seconds for 0.018; 320 sequences each |
| Peak host private memory | 87.80 MiB |
| Total internal time across cohorts | 145,344 seconds |
| Pre-archive inventory | 4,934 files; 25,947,289 logical bytes; 38,511,584 allocated bytes |
| Largest complete state in that inventory | 6,559 compressed bytes; 8,192 allocated bytes; three nodes, two connections, no trained peripheral |

File identities were used to deduplicate hard links; none were duplicated here. Directory and database overhead are excluded. Cost differences are descriptive, not evidence of a whole-system speedup. The guard did not trigger; no rollback, death or orphan in-flight state occurred. Source and native-binary fingerprints were frozen with the evidence. Production kernel sources were unchanged.

Originals: E:/ThreeMindData/experiments/2026-11-13-kernel60-pruning/quick-v1. Project: 7119c32a-f173-454d-b105-d4a415d1fb68. Record: 5afbbd07-419b-5abe-bba8-f40e361a3eab. Main results: analysis-v1.json; audit: independent-audit-v1.json. Full archive readback and zero pending operations are documented by publication/completion.json. Both analysis and independent-program verification were performed by the same assistant, not an external replicator.
