# M2 relearning-assay calibration: none of four doses establishes a usable window

2026-10-16. Code and protocol frozen at ef686a6; existing S configuration of continuous-memory/5.1. Eight independent calibration origins; record 7e197612-43b2-5bed-84f2-22e397bfec75. [Protocol](m2-relearning-assay-protocol.en.md) · [中文](m2-relearning-assay-report.zh.md)

**This batch rejects the apparatus expectation that at least one of the four prespecified doses would produce a qualifying acquisition window.** Every dose qualified in 0/8 origins, and none of the 64 branches expressed the correct response within 16 lessons. No dose is selected, and this apparatus will not proceed to a savings confirmation. Execution and evidence validation succeeded; the acquisition-window target failed. This is an unfavorable result for the present measurement design and a final decision on this batch's complete target.

## Purpose and expectation

In the earlier X2 apparatus, both experienced and naive systems passed after the minimum two lessons, preventing measurement of faster relearning. The original zero-lesson savings and failed target remain unchanged. This separate batch used new origins to ask whether naive acquisition could be placed inside a measurable intermediate range, without selecting doses by an experienced group's advantage.

A history qualified only if its baseline was incorrect, first correct response occurred during lessons 2–12, and at least three of the last four responses were correct. Both opposite histories had to qualify within each origin, and at least 6/8 origins had to qualify at a dose. The lowest qualifying dose would be selected. Immediate first-lesson success, no correct expression by lesson 16, and unstable expression were prespecified failures. Invalid originals would instead yield invalid measurement. There was no experienced comparison group: savings itself was outside this batch's target from the outset.

## Results

| Dose per teaching channel | Qualifying origins | Correct baseline | Correct at each of lessons 1–16 | First correct lesson | Correct in last four |
| --- | ---: | ---: | --- | --- | --- |
| 0.10 | 0/8 | 0/16 | 0/16 at every lesson | Not reached in all 16 histories | 0/4 in every history |
| 0.20 | 0/8 | 0/16 | 0/16 at every lesson | Not reached in all 16 histories | 0/4 in every history |
| 0.30 | 0/8 | 0/16 | 0/16 at every lesson | Not reached in all 16 histories | 0/4 in every history |
| 0.40 | 0/8 | 0/16 | 0/16 at every lesson | Not reached in all 16 histories | 0/4 in every history |

Sixteen histories at each dose comprise two opposite mappings per independent origin; they are not 16 independent births. There were 64 baseline probes and 1,024 post-teaching probes, totaling 1,088. Every signed A−B response at the frozen 110 ms endpoint was exactly zero. Zero is correct for neither opposite history. The machine-readable first-correct value of 17 is a sentinel for failure to reach correctness within 16 lessons, **not an observed successful seventeenth lesson**.

![Four-dose continuous acquisition curves](E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-relearning-assay-v1/figure-v1.png)

## Analysis, scientific conclusion, and decision

No measurable rising acquisition curve appeared. All four doses tied at zero on the primary response; the frozen 16-lesson course did not resolve the apparatus problem. The proposal to directly compare relearning speeds under these doses, maintenance intervals, and fixed endpoint is therefore rejected. The preregistered decision is to stop this apparatus from proceeding to savings confirmation, without extending lessons, increasing doses, or changing the endpoint to rescue its score.

For ThreeMind, **this curriculum and measurement combination supplies no usable first-acquisition speed reference**. Two groups both lacking expression would not establish which learns faster. The result constrains the measurement design. It is not an experienced-versus-naive memory comparison: the experienced-group count is zero, so this batch supplies neither a positive nor a negative estimate of savings. That scope was fixed before execution and is not a post-result increase in the target.

The cause of zero expression was not isolated by factor-specific causal interventions in this batch. It must not be assigned to a particular maintenance mechanism, dose, or readout time. Further work on this question needs a separate apparatus-diagnostic protocol to locate the information loss, followed by new-origin validation of a discriminating scale. It cannot rewrite the earlier X2 scores. The already prepared M3 confirmation proceeds next; this local M2 apparatus failure does not block the full M1–M7 program.

## Continuity, verification, and cost

Independent origin seeds were 1086100–1086107, excluding instrument seeds and previous exploration. Each naive parent continuously experienced 47 internal seconds of declared maintenance and an N stimulus, then supplied eight registered whole-system copies: four doses by two mappings. Each branch received a baseline probe followed by 16 continuous XYA or XYB teaching events, two-second maintenance intervals, and 1.5-second X probes. Answer channels appeared only in declared teaching frames. Evaluation experience remained in each branch; there was no per-lesson restoration. Final age was 104.5 internal seconds per branch, with four nodes and six edges. Branch ages are not summed into one individual's lifespan; independent N remains eight.

Core, fixed AB projection, mappings, RNG, body, input history, recent activity, and actuator state were saved. There was no learned-reader optimizer. Formal apparatus paths with ordinary execution, frequent observation, whole-state save/restore, and wall-clock pause had identical final SHA256 values. A separate file/arithmetic audit checked eight origins, 64 branches, 1,088 probes, and 1,168 whole snapshots, including answer isolation, continuous prefixes, 110 ms endpoints, and the frozen selection rule, without loading a Core engine. The executing assistant reviewed both reports and the figure; these are internal checks, not external replication.

The single host completed without STOP or residual in-flight marker. Elapsed host time was 326.56 seconds including saving and synchronization, not isolated Core compute time; peak private memory was 606,154,752 bytes. Minimum available system commit/RAM/C/E bytes were 12,624,449,536 / 13,919,481,856 / 9,114,267,648 / 43,353,767,936. Resource reserves remained 5/4/5/25 GiB.

Before publication there were 1,224 files, 49,956,902 logical bytes, the same hard-link-deduplicated logical size, and 51,853,304 allocated file-stream bytes, with zero duplicate hard-link entries. Compressed whole-snapshot minimum/median/maximum were 5,917 / 40,766.5 / 76,598 bytes. Allocation was measured through Windows FileStandardInfo; later archives/API readback, directory/MFT, and database overhead are excluded. Actual complete API archive/member and report-text readback with pending zero are documented separately in the delivery receipt.

This batch closes as a valid negative: **the specified acquisition window was absent, and no candidate dose is adopted.** This preserves the earlier findings and prevents an assay without dynamic range from being used to claim a memory mechanism result.
