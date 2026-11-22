# R51n: kernel 6.1 retains and recalls event order for 300 seconds

> Editorial revision, 14 November 2026: corrected spaces inserted into the evidence path and record identifier. Experimental results and decisions are unchanged. The [original English edition](report.v1.en.md) and original evidence archive are retained.

Report dated 14 November 2026; computation completed on 13 November. **Kernel 6.1 passed the primary replication of event-order expression and the 300-internal-second retention target.** Under an identical cue, individuals taught AX before BX responded more strongly to B, whereas individuals taught the reverse order responded more strongly to A. All four anonymous material blocks reproduced this result. At both 30 and 300 seconds, activation of A, B and X was zero before the cue, yet the cue elicited the order-dependent response difference again.

## Purpose and expectations

This batch replicates historical E20 under comprehensive revalidation plan v 2. It asks whether continuous experience leaves a difference between event orders that can be expressed after the original activation subsides. We expected 6.1 to retain order expression and, with slower decay, extend retention. A separate E21 state-exchange experiment will test whether connection weights specifically carry that difference. The [frozen protocol](protocol.en.md) specifies all conditions, primary decisions and stopping rules.

The primary condition uses a shared reference X, a 50-ms interval between the two events and the default facilitation time constant of zero. After both 1 and 30 seconds, AB and BA teaching must produce opposite A/B response advantages exceeding 1e−6 activation·seconds in absolute value, consistently across all four blocks. The same criterion at 300 seconds defines the preregistered improvement target. Either primacy or recency can meet the order-expression criterion; all positive conditions in this batch showed recency, meaning a stronger response to the event taught later.

## Methods and sample structure

The four original anonymous material blocks, 100121–100124, were retained. Each block compares facilitation time constants of 0/1 second, shared versus absent references, event intervals of 0.05/0.5/2 seconds and AB/BA teaching orders. There are 96 continuously taught references. Each provides six registered single-test diagnostic copies, separately waiting 1/30/300 seconds before receiving X or no cue. The total is 672 stages, including 576 probes. The material count is four blocks; condition copies and recorded frames do not increase the independent sample count.

Each reference receives 12 event pairs continuously from birth. Shared-reference teaching uses AX and BX; teaching without the reference uses A and B. Element values are 1 and stimulus intensity is 0.4. Every course ends with the same independent Y input. Independent K inputs of intensity 0.2 every 0.5 second maintain activity during waiting and testing. Separate waiting cohorts prevent earlier tests from rehearsing later tests. All 138,752 input frames were matched to the historical originals for codes, dose, enqueue time and order.

The test cue is X=0.5. A fixed passive readout records activation, inhibition, direct and associative activity every 20 ms for five seconds. The primary measure subtracts the corresponding no-cue integral from each A/B activation integral, then calculates the net advantage of the later event over the earlier event. Positive values indicate recency. No output adapter is trained and no order answer is supplied to Core. All individuals use genuine 6.1 and current defaults; facilitation at 0/1 second is a prespecified birth-configuration comparison.

## Results

| Target | Prespecified criterion | Result | Scientific conclusion |
|---|---|---|---|
| Retain order expression | Bidirectional expression in 4/4 blocks at both 1 and 30 seconds under the primary condition | 4/4 at each time,8/8 block conditions | Passed: the same cue expresses opposite teaching orders |
| Express order after activation subsides | A/B/X activation at most 1e−12 at 30 seconds, with bidirectional expression | 4/4 blocks passed; all relevant activations exactly zero | Passed: continuous activation of the task nodes is unnecessary for recall |
| Extend retention to 300 seconds | Bidirectional expression in 4/4 blocks at 300 seconds | 4/4 passed, versus 0/4 historically under the same condition | Passed: expressible retention of this course extends to 300 seconds |
| Cue-path control without a shared reference | Report whether previously untaught X elicits A/B | No order expression in 72 paired comparisons; A/B process integrals all zero | The corresponding X cue path was not formed |

The following table includes every shared-reference condition. Cells give the number of material blocks meeting the primary numerical threshold, followed by the later-minus-earlier net advantage in activation·seconds. Values were identical across the four blocks and the two opposite teaching orders. A 0/4 cell has no net order advantage in this observation window.

| Facilitation time constant | Event interval | Wait 1 second | Wait 30 seconds | Wait 300 seconds |
|---|---|---|---|---|
| 0 seconds (default) | 0.05 seconds | 4/4 (0.0000838982) | 4/4 (0.00173015) | 4/4 (0.000272409) |
| 0 seconds | 0.5 seconds | 0/4 (0) | 4/4 (0.0000806076) | 0/4 (0) |
| 0 seconds | 2 seconds | 0/4 (0) | 0/4 (0) | 0/4 (0) |
| 1 second | 0.05 seconds | 4/4 (0.00244467) | 4/4 (0.00202735) | 4/4 (0.000272845) |
| 1 second | 0.5 seconds | 0/4 (0) | 4/4 (0.0000806834) | 0/4 (0) |
| 1 second | 2 seconds | 0/4 (0) | 0/4 (0) | 0/4 (0) |

Across all 144 paired comparisons,32 met the 1e−6 threshold; the 1e−9 sensitivity analysis also counted 32. Historical E20 counted 28. Condition-level comparisons explain the changes more clearly: the 50-ms course now expresses order at 300 seconds; the 0.5-second course changes from weak primacy at 1 second in the historical experiment to recency at 30 seconds; the historical 1-second primacy effect with a 2-second event interval and facilitation was not reproduced in 6.1. **Kernel 6.1 extends retention of the short-interval course but does not strengthen every course at every time.** These changes remain in the report rather than being replaced by an aggregate pass count.

## Analysis and scientific conclusions

The opposite teaching histories use the same stimuli and doses, the same final independent input and the same test cue, yet A/B response advantages reverse with teaching order. The current cue therefore does not supply the response direction; prior experience produces the difference. At 30 and 300 seconds, task activation is zero before the cue but a directional difference reappears afterward. The course has left an internal state that can express its history again.

Connection observations agree with this finding. In the default-facilitation, 50-ms condition at 30 seconds, AX-before-BX teaching yields current X→A and X→B weights of 0.0901706 and 0.135202; reverse teaching exchanges these values. At 300 seconds, the corresponding weights remain 0.0490646 and 0.0735387. These are weights projected to the same current time. E21 will directly test their causal contribution by exchanging state groups.

In the default condition, the net advantage is small at 1 second, larger at 30 seconds and smaller again at 300 seconds. With a 0.5-second event interval, no net advantage appears at 1 second, but recency appears at 30 seconds. **The expression of an experience changes with the retention interval and is not captured by a single monotonically decreasing response curve.** The planned state-exchange and resource controls will locate the contributing states.

For ThreeMind, this is a favorable mechanism result: **kernel 6.1 retains the influence of experienced event order on subsequent responses and extends expressible retention of the original 50-ms course to 300 internal seconds. The task nodes need not remain continuously active.** Both the primary and improvement targets were completed without triggering the frozen scientific stop. State exchange, timing and dose-matched reference comparisons follow under the original plan. The default transmission threshold remains 0.0004; its review will also consider the course-dependent changes found here.

## Originals and verification

Read-only checks cover 6,528 complete states, 672 stages and 138,752 delivered input frames, including parent–child state identity, genuine kernel version, fixed-function addresses, configuration, clocks, full trajectories and scores. Independent integration at 45-digit decimal precision differed by at most 1.11×10⁻¹⁶. Five apparatus modes—no observation, regular observation, sparse observation, save/restore and a host pause—produced identical final states. The executing assistant performed these checks without creating or advancing formal individuals.

Scientific computation took 34.37 minutes; peak private memory was 599.75 MiB. Before analysis, evidence occupied 116.94 MiB logically and 145.63 MiB as allocated in the storage audit. The maximum per-unit storage ratio to the corresponding historical unit was 1.104, below the stopping threshold. Lossless compression preserved every archive member's original bytes and complete-state hashes; see the [storage amendment](storage-amendment.en.md). No resource stop was triggered.

Originals: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/order-recall61-v1/`. Research record: `f2a0b318-840d-51de-b58e-cba8843721a1`. Full results are in `analysis.json`, checks in `audit.json`, and final API archive/readback evidence in `publication/completion.json`. Historical reports and originals, production Core and the author's manuscript remain intact.
