# R51l: 48-source confirmation of selective transfer of learned responses and closed-loop choices

13 November 2026. **All 48 independent sources met the preregistered target. Target-connection transplantation changed 480/480 first choices and 480/480 final choices after feedback to the donor's learned direction, while preserving the recipient's original responses on 480/480 unrelated trials. Replacing the original connections restored the original responses.** The result confirms that experience-formed local connections in 6.1 can selectively transfer learned correspondences and alter actions and subsequent sensory feedback.

## Purpose and expectation

This independent confirmation followed the eight-source R51j exploration. It retained the historical M1 confirmation's 48 sources, six strata and primary criteria. We tested whether selective local transfer replicated in new sources, teaching intensities, retention intervals and untaught stimulus combinations. We expected target transplantation to work, sham and matched transplantation to lack the same target-task gain, unrelated responses to remain intact, and restoration to recover the original responses. The [preregistered protocol](protocol.en.md) fixed materials, interventions, scoring, statistics and stopping conditions.

## Methods

Teaching intensities of 0.38, 0.42 and 0.46 crossed with retention intervals of 2 and 5 seconds formed six strata, each with eight new sources. Two opposite teaching histories began from the same birth conditions within each source and each completed 16 continuous rounds of anonymous stimulation. Teaching copies and diagnostic trials were nested within their source; exploratory sources were excluded.

The two connections associated with X and Y were targeted; the two associated with Z and W were matched controls. Both groups led to answer channel A or B. Selection used teaching data only. Connection counts and endpoint degrees matched; allowed residuals in current weights and teaching activity were each 0.02. Their observed maxima were 0.000527 and 0.000603.

Each history had seven conditions: intact reference, sham, target whole bundle, matched whole bundle, target persistent bundle, target fast bundle, and restoration. Each condition received five target cues—X, Y, XY, XN and YN—and five unrelated cues—Z, W, ZW, ZN and WN. Mixtures containing N had not been taught. Each diagnostic copy ran continuously for 1.5 internal seconds from its registered complete intervention boundary, giving 6,720 probes.

The readout rule remained the answer-channel difference A−B, with no readout training. At 110 ms, differences exceeding positive or negative 1e-4 selected one of two gates; otherwise the subject waited. The actual choice determined the next stimulus at 250 ms, and final gate position was recorded at 360 ms. The environment function received the action, not the answer or donor history. First and final choices therefore separately measured behavioral consequences of transfer.

For each source, the primary gain was the minimum of eight accuracy differences across two histories, two choice times, and comparisons with sham and matched transplantation. A source qualified if this minimum was at least 0.50, target accuracy at least 0.75, maximum unrelated loss at most 0.10, and restored accuracy identical to the reference. The batch required all 48 sources to be valid, at least 36 to qualify, a mean minimum gain of at least 0.50, and a two-sided source-level P<0.05.

## Results

Target trials are scored against the donor's direction; unrelated trials are scored against the recipient's original direction. The intact reference's 0/480 target score means that it retained its own original teaching correspondence.

| Condition | First target choices matching donor | Final target choices matching donor | First unrelated responses retained | Final unrelated responses retained |
|---|---:|---:|---:|---:|
| Intact reference | 0/480 | 0/480 | 480/480 | 480/480 |
| Sham | 0/480 | 0/480 | 480/480 | 480/480 |
| **Target whole-bundle transplant** | **480/480** | **480/480** | **480/480** | **480/480** |
| Matched whole-bundle transplant | 0/480 | 0/480 | 0/480 | 0/480 |
| **Target persistent-bundle transplant** | **480/480** | **480/480** | **480/480** | **480/480** |
| Target fast-bundle exchange | 0/480 | 0/480 | 480/480 | 480/480 |
| Original connections restored | 0/480 | 0/480 | 480/480 | 480/480 |

**All 48/48 sources passed the primary target, with 8/8 passing in every stratum.** Every source had a minimum gain of 1.00, or 100 percentage points, and zero unrelated loss. Both target-transplant conditions achieved 192/192 first and final choices on the untaught XN and YN mixtures. Matched transplantation changed the other correspondence carried by its connections: unrelated responses departed from the recipient's original direction, without improving target responses. The effect followed the relationship being exchanged.

Because all 48 source gains were identical, the preregistered exact two-sided sign test applied: P=7.1054×10⁻¹⁵. The exact 95% interval for the proportion of positive-gain sources was 92.60%–100%. The empirical source-bootstrap interval was [1.00, 1.00], reflecting identical gains in this sample; the nondegenerate proportion interval is reported alongside it. The 200,000-draw sign-flip sensitivity analysis gave P=4.99998×10⁻⁶. Trials and frames were not counted as additional independent observations.

The 96 target whole-bundle exchanges changed the target endpoints of 192 connections and the corresponding timer endpoints; all other numeric fields of paired connections were equal. Persistent-bundle transfer produced the same choices. All 96 fast-bundle exchanges had identical fields on both sides, so they made no changes and produced no transfer. This identifies connection destinations as the operative fields in this batch; the fast-bundle condition is a zero-change reference. Sham and restoration preserved complete state and millisecond response trajectories exactly relative to their intact references.

## Scientific conclusion and significance for ThreeMind

**The learned choice correspondences in this batch were carried by the destinations of experience-formed local connections. Transplanting those connections selectively transferred responses and choices during a two-step action–perception process; unchanged connections continued to express the recipient's unrelated relationships.** The fixed readout did not relearn, sham had no benefit, matched transplantation changed another relationship, and restoration recovered the original choices. Together these controls establish the causal role of local experience-formed structure.

This batch met its independent confirmation target across six teaching and retention conditions and untaught mixed cues. It is favorable evidence for 6.1 and supports the claim that experience organizes behavior through identifiable, transferable internal connections. No campaign stopping condition was triggered. Event-order and the remaining original-scale replications follow.

## Evidence, audit and cost

The read-only audit verified 7,680 complete states, 6,720 causal diagnostic copies and 10,080,000 response frames. Matching residuals, actual feedback, integrals, source scores and statistics were independently recomputed. No Core was created or advanced. This is an audit of saved originals by the executing assistant; external replication is a separate category.

Scientific execution took approximately 27.00 minutes, with peak host-private memory of 570.96 MiB. Before analysis, originals occupied 135.34 MiB logically and 146.38 MiB in allocated storage. The resource guard did not pause execution. Originals are under `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/transfer-confirmation61-v1/`, research record `4058fdf3-7108-5599-ab32-ed3a0c27a5ca`. The archive and final complete API-readback receipt are documented in `publication/completion.json` there. Historical experiments, intact parents, production Core and defaults are preserved.
