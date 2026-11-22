# Three dynamical questions: findings, mechanisms and decisions

14 November 2026. Four separately registered batches complete the authorized studies. Comprehensive revalidation remains paused. Production Core, defaults and the manuscript have not been changed.

## Findings

### Inertial reversal: identical experience can support opposite preferences under different transmission conditions

Starting from the same complete teaching state, changing only the test-time activation-transmission threshold from 0.0004 to 0.004 reversed both response directions in all four encoding blocks. Initial connections, fast activity and random state were identical. This isolates expression from the earlier comparison that changed configuration from birth. **The same connections left by teaching can produce opposite response preferences under different transmission conditions.**

Reversal did not deliver the preregistered closed-loop posture benefit. Error decreased 8.61% under one actuator polarity and increased 0.49% under the other. None of 160 Core-controlled tasks stabilized, whereas the PD body reference succeeded in 8/8. This fixed process readout and fixed-torque control did not form an effective stabilization strategy. Retain the current threshold and study reversal as a controllable expression property. [Report](body_report/report.en.md)

### Persistence: inhibition can be retained, and strong activity can still lose discrimination

After unchanged teaching, retaining inhibition gain while reducing its decay time constant to one quarter restored 300-second low-amplitude activity in both material blocks. Maximum task activation in the final window was 0.0604–0.0812, without saturation. **Restoring persistence does not require removing inhibition.** [Mechanism report](mechanism_report/report.en.md)

New encodings, continuous teaching, spaced review and bounded correction then tested decisions. Both the reference and candidate scored 32/32 on short-delay, long-delay and distractor pairing questions. The candidate preserved discrimination. The reference also reached the ceiling, so this batch established no superior accuracy for the candidate.

Removing inhibition caused failure to select on all 96 cued pairing questions. Both outputs remained active: their last-half-second activation integrals were exactly equal at 0.405227652 each. Only about 0.0351% of task-node observations reached 0.95 activation, so widespread saturation is not an adequate description. **Activity duration, strength and discriminative choice must be measured separately.**

This addresses the author's concern directly: removing inhibition impairs discrimination in this apparatus, whereas retaining inhibition with faster decay avoids that impairment. The current default remains because the candidate did not outperform it. Blank-question failures are also retained: neither the reference nor candidate reliably selected WAIT without a new cue. [Delayed-choice report, revision 2](decision_report/report-r2.en.md)

### Prefix discrimination: two rules jointly restore the ability

The 11 preliminary 6.1 configurations and four later continuous-curriculum profiles did not recover distinct taught endings after A-B and D-B. Process records showed that A/D activity differences remained before B, but the endings failed to switch with the prefix.

The historical factor crossing found a clear combination: **immediate novelty and legacy connection retention jointly restored both exchanged-material blocks in genuine 3.1 and 5.1; either change alone failed.** Changing node retention added no effect. Legacy retention had restored persistence earlier, but prefix discrimination additionally required immediate novelty. The two abilities therefore have different conditions. [Crossed-study report](prefix_cross_report/report.en.md)

This recovery belongs to the named historical implementations; recovery in 6.1 remains unfinished. The next question is now specific: separate the useful strengthening and forgetting operations in legacy retention and their interaction with immediate novelty. Legacy retention changes multiple processes, so importing it wholesale would not identify a single causal component.

## Recommendations for 6.2 [Public edition: manuscript editing or private locator omitted.]

1. Retain inhibition, fixed-function addressing and local deletion. Do not raise the default transmission threshold or remove inhibition merely to maximize activity duration.
2. Retain the shorter inhibition time constant as a tested research configuration. It restores low-amplitude persistence and preserves paired choice but did not outperform the reference here.
3. Prefix discrimination is the main candidate issue for 6.2. Specify how novelty timing, weight strengthening and forgetting would change before the author decides on implementation and necessary revalidation. Preserve completed 6.1 findings under their true identity; select future tests by actual effects of a change.
4. Preserve the manuscript's historical results and add the changes exposed by replication, their investigation and these findings. Rao et al., Compte et al., and Brooks and Cullen are recorded with their actual uses in the [reference guide](references.en.md). Cite them where those ideas enter the argument. [Public edition: manuscript editing or private locator omitted.]

These are recommendations derived from the completed studies. No production 6.2 or default change has been implemented, and comprehensive revalidation has not resumed.

## Evidence and delivery

| Batch | Actual scope | Complete archive readback through the API |
| --- | --- | ---: |
| R51t2 | Two exchanged-material blocks, 110 new stages | 1,650 members, pending=0 |
| R51t3 | Four encoding blocks, 296 stages | 3,860 members, pending=0 |
| R51t4 | Four new encoding blocks, 64 systems, 1,536 continuous phases, 896 final questions | 15,808 members, pending=0; revision 2 also read back |
| R51t5 | Two exchanged-material blocks, 42 new and 30 reused stages | 934 members, pending=0 |

Stages, diagnostic copies and questions were not counted as additional independent sources. The corresponding directories under `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/` are `dynamics-function61-v1`, `closed-body61-v1`, `delayed-choice61-v1` and `prefix-cross61-v1`. Each retains frozen protocols, complete states, inputs and outputs, read-only analyses and receipts.

R51t4's timestamp-type audit error was corrected in a separate v2. A report phrase that confused weight strengthening with retention growth was corrected in dated revision 2. Original tools, first-edition reports, archives and scores remain intact; no individual was rerun. Logical and allocated storage were measured separately, and every batch maintained the 5/4/5/25-GiB resource reserves.
