# How repetition and teaching timing affect order responses

14 November 2026, R51p. This genuine kernel 6.1 batch repeats the E21 timing and reference experiments under comprehensive revalidation plan v2. The transmission threshold remains 0.0004, the deletion threshold 0.008, and other defaults are unchanged.

**Kernel 6.1 preserves order expression produced by dense repetition: the effect of teaching order remains readable after one and 30 seconds at all five teaching offsets.** Dense teaching passed 80/80 bidirectional comparisons. Sparse teaching passed 160/240, retaining all 148 historically positive conditions and adding 12. Separate references produced no target activity in any of 64 comparisons, matching the historical result.

All new positive responses showed a recency advantage: the later-taught target had the larger net response. Forty historical sparse-course comparisons changed from primacy to recency. They still distinguished opposite teaching orders, with a changed response preference. Expression and its direction are reported separately, as preregistered.

## Purpose and design

R51n established expression of event order after task-node activity had subsided, and R51o identified the causal role of connection weights through state exchange. This batch asked how course arrangement affects expression: whether dense repetition requires a precise teaching offset, how intervals between and within pairs change expression, and whether separating a common reference preserves the order response.

One teaching course repeatedly presents AX followed by BX; its counterpart reverses the order. Both are tested with the same X cue. Letters label the records; the Core receives anonymous codes and numerical intensities. For each target, the activation integral after a cue is reduced by the corresponding blank integral. Order expression requires opposite signs of net A−B after opposite teaching histories, with both absolute differences exceeding 1e−6 activation-seconds. Either primacy or recency can meet this preregistered criterion.

Four anonymous material blocks, 100121–100124, supplied 352 continuous teaching references and 1,472 single-test diagnostic copies, totaling 1,824 stages. Each reference received 12 stimulus pairs at intensity 0.4, with facilitation time constants of zero or one second. Dense pair starts were 550 milliseconds apart; sparse pair starts were 2.5 seconds apart. Teaching offsets were 0, 20, 40, 60 or 80 milliseconds. Within-pair intervals and reference arrangements were varied separately. Registered diagnostic copies waited one or 30 seconds before a five-second observation window. Activation, inhibition, direct activity and associative activity were recorded for all nodes every 20 milliseconds.

The material scale is four blocks. Counts of 80, 240 and 64 refer to bidirectional comparisons across configurations and waits; neither those counts nor the numbers of references and copies are independent-source counts. Readout was fixed and passive, with no trainable personal adapter.

## Results

| Course | Historical E21 order expression | Kernel 6.1 order expression | Direction in 6.1 |
|---|---:|---:|---|
| Dense repetition, five offsets | 80/80 | 80/80 | Recency in every comparison |
| Sparse repetition, three within-pair intervals | 148/240 | 160/240 | 160 recency effects; no target activity in the remaining 80 |
| Separate AX/BZ references | 0/64 | 0/64 | No A or B activity in all 64 |

Without facilitation, dense-course recency margins ranged from 0.00269925 to 0.00278302 after one second and from 0.00155324 to 0.00174174 after 30 seconds. With a one-second facilitation constant, the corresponding ranges were 0.00186464–0.00296502 and 0.00173585–0.00202388 activation-seconds. All exceeded the registered threshold. **Dense-course order expression covers all five offsets and persists through the 30-second test; the primary target is met.**

Sparse-course results depended on within-pair interval and waiting time. Each table cell contains 20 comparisons: four blocks and five teaching offsets.

| Within-pair interval | Facilitation constant | One-second wait | 30-second wait |
|---|---:|---:|---:|
| 50 milliseconds | 0 seconds | 20/20 | 20/20 |
| 50 milliseconds | 1 second | 20/20 | 20/20 |
| 500 milliseconds | 0 seconds | 20/20 | 0/20 |
| 500 milliseconds | 1 second | 20/20 | 0/20 |
| 2,000 milliseconds | 0 seconds | 20/20 | 0/20 |
| 2,000 milliseconds | 1 second | 20/20 | 0/20 |

The 12 newly positive comparisons all used a 50-millisecond within-pair interval, no facilitation and a 30-second wait, with offsets of zero, 20 or 40 milliseconds—four blocks at each offset. Every historically positive condition retained bidirectional order expression. At 500- or 2,000-millisecond within-pair intervals, responses expressed order after one second; after 30 seconds, the raw A and B activities were zero throughout the window. These zeros reflect absent target activation, rather than cancellation during blank subtraction.

Separate references replaced AX/BX with AX/BZ and used X or Z cues. Neither A nor B became active in any of the 64 comparisons. Shared-reference courses therefore performed better in this batch. This comparison changes both X exposure and pairing structure; the next R51q batch uses the historical E22 dose-matched materials to separate these factors.

## Analysis, scientific conclusion and significance for ThreeMind

**Kernel 6.1 preserves every historically positive E21 order-expression condition and extends the effective teaching offsets at a 30-second wait for the short within-pair interval.** This supports the experience-dependent mechanism: the same current cue elicits different responses after opposite teaching histories, without requiring dense teaching to occur at one precise offset.

Course arrangement has practical consequences for retention and expression. Sparse courses with a 50-millisecond within-pair interval remain effective at both waits; courses with 500- or 2,000-millisecond intervals are effective only at the one-second test in this batch. Repetition cadence, within-pair interval and test time must therefore be recorded separately. “Taught 12 times” does not adequately describe the experience.

Response direction is also a result. Forty historical primacy effects became recency effects, showing that version changes alter the relative expression of earlier and later teaching. The original criterion asks whether opposite histories reverse the response difference, and all historical positives retain that property. The revalidation is favorable, with the directional changes preserved for the later default-threshold review. No single unisolated parameter is assigned responsibility for differences between versions.

The primary target passed and no scientific stopping condition was triggered. Planned E22 reference, jitter and bodily-mechanism comparisons continue, followed by the retained shape-color, embodied and 3-SAT work.

## Evidence, verification and resources

Read-only verification covered 5,120 complete states, 88,720 inputs and 1,824 stages, checking genuine 6.1 identity, fixed-function addresses, continuity, input order and default settings. Independent 45-digit decimal arithmetic differed from ordinary integration by at most 1.1102230246251565×10⁻¹⁶. Counts at the 1e−9 numerical check matched the primary 1e−6 threshold. Three independent apparatus courses produced identical final Core hashes under normal, disabled or sparse observation, full save/restore and host pause.

The first audit incorrectly required a newborn empty state to be active and stopped at the first initial state. The frozen script and failed-attempt record are retained. A separate corrected analyzer requires waiting only for an initial file at time zero with no nodes or connections, while every developed state must remain active. It completed the verification without rerunning subjects or changing scoring. See [audit-correction.en.md](audit-correction.en.md).

Scientific computation took 1,938.97 seconds, or 32.32 minutes, with peak private memory of 605.42 MiB. Before analysis, files totaled 217.15 MiB logically and 250.09 MiB in actual allocation. Per-unit file measurements were 1.126–1.206 times the corresponding historical values, below the 1.5-times estimate. Commit, RAM and C/E availability remained above the 5/4/5/25 GiB reserves, with no resource STOP or orphaned in-flight state.

Originals are in `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/order-timing61-v1`, research record `f260db39-9864-5d43-8a48-d3f4da1ff0fb`. `analysis.json` contains new results; `postprocessing/historical-comparison.json` contains all 384 matched historical comparisons and source hashes. The archive, member manifest and full API readback receipt are `originals.zip`, `manifest.json` and `publication/completion.json`; closure requires verified coverage and pending=0. This is a within-project replication.
