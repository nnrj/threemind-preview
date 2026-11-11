# M4 material audit: existing E69 cannot replace a balanced specialization experiment

16 October 2026; read-only measurement-preparation report v1. Research record `54969028-d859-5c60-a800-01360b505107`.

**Conclusion: the existing E69 materials fail the preregistered identifiability requirements for the three-condition comparison. There is no isolated-hand condition, and hand and joint motion occur in one development stage. Task differences cannot be separated from developmental time. The approved balanced eye/hand/joint prospective experiment is therefore necessary.** This batch closes the material-eligibility question; the dedicated M4 experiment addresses natural functional specialization.

## Purpose, expectation and scope

The user requested a test of whether experience-shaped connections develop stable functional specialization during eye-only, hand-only and joint activity. We first assess whether committed materials from paused E69 can support that comparison, controlling against mistaking input mappings, training periods or sparse movements for functional regions.

The [preregistered protocol](m4-material-protocol.en.md) was frozen in commit `148a502`. Eligibility requires at least eight questions containing a continuous 0.3-second segment of each of eye-only, hand-only and joint motion in both time blocks (development rounds 0/1 and 2/3), plus an isolated-hand condition, interleaved tasks within time blocks and later confirmation materials. The latter three were known to be absent; the expectation was that a dedicated prospective experiment remained necessary. This audit quantifies all selected materials without fitting functional groups or intervening on them.

There is one independent individual, `e69-5.1-223`: **N=1**. Four gaze and four coordination development rounds, each with 24 complete autonomous questions, provide **192 questions and 23,040 frames**. Assisted trials, unfinished semantic work and the unperformed final test are excluded. Questions, frames and segments are nested observations. E69's original authorized rollback remains in its provenance; this audit neither resumed nor advanced the individual.

## Results and registered verdicts

Primary motion thresholds are eye speed ≥0.08 rad/s and hand speed ≥0.01 m/s, sustained for at least six frames. These are movement states, not curriculum conditions or correct pointing.

| Target or necessary condition | Observed result | Verdict |
| --- | --- | --- |
| Complete, unassisted, recomputable source material | 594 source-file hashes verified; all 192 questions complete and unassisted; 120 frames each | Pass |
| At least eight eligible questions for each movement class in both blocks | Early block: eye-only 57, hand-only 0, joint 0; late block: 91, 6, 4 | Fail |
| Isolated-hand condition | No isolated-hand curriculum/test condition | Absent |
| Interleaved task conditions and later confirmation | Both absent | Absent |
| Complete the three-condition functional-specialization test from these materials | Necessary controls and behavioral coverage missing | Ineligible; dedicated prospective experiment required |

Of 1,536 new hand decisions, **6 were MOVE and 1,530 WAIT (99.61%)**. All six MOVE decisions occurred in `coordination-dev-2`; there were no inherited MOVE commands. All new hand decisions in the other seven stages were WAIT. At primary thresholds, the mutually exclusive frame counts are eye-only 7,096, hand-only 130, joint 71 and neither 15,743. Questions containing qualifying segments number 148, 6, 4 and 192, respectively; one question may contain multiple classes, so those counts must not be added as independent questions.

| Stage (24 questions each) | Eye-only questions | Hand-only questions | Joint questions |
| --- | ---: | ---: | ---: |
| gaze-dev-0 | 3 | 0 | 0 |
| gaze-dev-1 | 17 | 0 | 0 |
| gaze-dev-2 | 23 | 0 | 0 |
| gaze-dev-3 | 22 | 0 | 0 |
| coordination-dev-0 | 13 | 0 | 0 |
| coordination-dev-1 | 24 | 0 | 0 |
| coordination-dev-2 | 22 | 6 | 4 |
| coordination-dev-3 | 24 | 0 | 0 |

All nine preregistered sensitivity pairs are reported below as questions with qualifying segments. Every row has 192 questions containing a neither-moving segment.

| Eye rad/s | Hand m/s | Eye-only | Hand-only | Joint |
| ---: | ---: | ---: | ---: | ---: |
| 0.04 | 0.005 | 162 | 7 | 5 |
| 0.04 | 0.01 | 162 | 6 | 4 |
| 0.04 | 0.02 | 162 | 6 | 3 |
| 0.08 | 0.005 | 147 | 7 | 5 |
| 0.08 | 0.01 | 148 | 6 | 4 |
| 0.08 | 0.02 | 148 | 6 | 3 |
| 0.16 | 0.005 | 144 | 7 | 5 |
| 0.16 | 0.01 | 145 | 7 | 4 |
| 0.16 | 0.02 | 145 | 6 | 2 |

## Analysis, scientific conclusion and implications for ThreeMind

**The proposition that existing E69 provides the necessary three-condition comparison is rejected.** This is not merely imprecise estimation: necessary experimental conditions never occurred, and the available hand activity is confined to one period. Behavioral clustering here would conflate training stage, sensory pathways and body state with functional specialization. Across all nine threshold pairs, only six or seven questions contain hand-only segments and two to five contain joint segments; reasonable threshold changes cannot create missing controls.

**For ThreeMind, this is unfavorable evidence for using the old materials as a natural-specialization test and favorable evidence for the decision to build balanced measurements.** It does not test whether specialization exists and makes no positive or negative verdict on that mechanism, as specified before analysis. The original M4 target remains stable task selectivity across questions and time blocks, with selective behavioral consequences under targeted/matched intervention and restoration. Birth-assigned energy `region`, graph layout and receptor groups do not establish learned specialization.

**The 99.61% WAIT rate directly describes these 192 questions.** It establishes sparse autonomous hand-action coverage. WAIT training history was not manipulated here, so its causal contribution is not determined by this audit; the prior bounded comparison remains separate. Naturally occurring movement segments cannot substitute for an isolated-hand training condition.

Decision: proceed with the already approved prospective M4 design, balancing eye/hand/joint experience, crossing curriculum order, randomizing individual interfaces, separating development from confirmation and preregistering selective intervention/restoration. E69 remains paused; no extra stimulation, body immobilization or question reruns are used to fill historical gaps.

## Verification, performance and evidence

The analysis uses only standard-library JSON/gzip reading, loads no Core, creates no individual and modifies no source. An independent file/arithmetic audit rehashed all 594 source files, recounted decisions in all 192 questions and independently recomputed nine thresholds for the fixed first/last question of each stage (16 trajectories). All checks agree. This is an executing-assistant audit using independent arithmetic, not external-researcher replication.

Read-only analysis took 135.39 seconds with peak private memory of 152.18 MiB; these are not simulated-student performance figures. The manifest references 1,078,995,211 source bytes. The delivery package includes **independent byte copies of these selected materials**, analysis, audit, protocols and tools; it is not the entire E69 dataset or a measurement of full-individual storage. Copies are checked against the manifest, and the original STOP/current boundary remain intact.

Work: `E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m4-materials-v1`. The `materials.json` SHA256 is `086696890efdb4994b9226bf0ceea83aba87f2b0f337236e998802f9a733cdac`; current boundary 2014/11059 seconds has SHA256 `611a6b907f6e33498e4befa33d2ddee5105a6f51f3d7c60c4a6cf60d9a1fe3a6`. Primary results are `analysis-v1.json`, audit `audit-v1.json` and copy receipt `source-copy-v1.json`. Full API archive readback and finalization receipts are recorded separately in the delivery note.

**This audit establishes that existing E69 lacks separable hand and joint conditions; a dedicated balanced prospective experiment is necessary to test natural functional specialization.**
