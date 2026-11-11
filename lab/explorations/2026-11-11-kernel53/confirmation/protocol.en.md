# R47b: confirming delayed experience retention in 48 fresh /5.3 origins

11 November 2026, confirmatory protocol frozen before execution. [中文](protocol.zh.md) · [Exploration](../report.en.md)

## Purpose, expectations and conclusions

R47a found inverse logarithmic retention in 8/8 origins for three 300-second courses, with lower expression-retention rates for the other curves. This batch asks whether the advantage replicates in 48 fresh origins. The earlier failure of all four curves to remove weak connections by 30 seconds remains a registered question; it is not omitted to manufacture a combined winner.

The primary continuous endpoint is each origin's arithmetic mean of the 300-second history-response RMS across massed repetition, spaced review and strong stimulation. The vector, four fields, 20 frames and baseline/cue-omission subtraction follow R47a. Three paired comparisons test whether inverse logarithmic decay exceeds exponential, power-law and power-exponential decay. One-sided paired t tests use Bonferroni family alpha 0.05, hence alpha=0.05/3 each. Raw differences, standardized effects and corresponding one-sided lower bounds are reported. Zero-variance differences use exact sign probabilities instead of division by zero or infinite t; all-zero differences provide no evidence of superiority. A separate implementation checks arithmetic.

A positive mean difference meeting its alpha threshold confirms superiority on that endpoint. All three must pass to confirm superiority to all three alternatives. Failed comparisons are reported as unconfirmed with intervals, not as equivalence. This endpoint measures the magnitude of late history-dependent responses; preservation of the early trajectory is separately adjudicated by E below.

S, E, W and F retain their original operational definitions. Each of three retention courses tests S: both directed target connections survive in both histories at 300 seconds; E: 1- and 300-second RMS exceed 0.0001, the late RMS is at least 10% of the early RMS, and cosine similarity is at least 0.8; and F: extant 300-second edges analytically fall below 0.008 after another 30 days without reinforcement. W requires both histories' weak-input target connections to be absent at 30 seconds. Each target requires 36/48 successes. Only meeting all S/E/W/F targets yields a combined apparatus candidate. There is no ranking by total passed items. Gain mechanisms G already received identical-input on/off controls in exploration and are not re-estimated here.

## Origins, materials and sample size

Forty-eight independent birth origins use seeds 261111480–261111527, disjoint from exploration. Each generates new anonymous mappings, an input amplitude multiplier between 0.85 and 1.15 and a timing phase. Conditions are paired within origins. These are fresh realizations from the same task distribution; this study tests independent replication, not transfer to a new task. `cases.json` freezes formal materials without choosing parameters from their responses.

The three retention courses have separate continuous cohorts at 1 and 300 seconds; weak input has a 30-second cohort. Each has two opposite histories and cue-present/omitted conditions. There are 48×4×(3×2+1)×2×2=5,376 sequences and 10,752 complete boundaries, with independent N=48. Each sequence develops from birth to its first test without per-question reset. This fixed instrument has no personal learned peripheral and does not substitute for joint-development tasks.

Planning used paired standardized effect 0.5 on the continuous endpoint, one-sided alpha 0.05/3 and 48 origins. Fifty thousand prespecified normal-difference simulations give power 0.8937, Monte Carlo standard error 0.00138, exceeding the 80% target. Normal differences are a planning model, not a power guarantee for every distribution or binary criterion. N is fixed; formal results cannot trigger sample additions to pursue significance. Personal-adapter tasks are separately registered.

## Execution and boundaries

The verified R47a `Assay` is reused with fresh origins and selected courses/delays. H=30, A=10, reinforcement retains age, timescale growth/relaxation remain off, and the same Rust /5.3 binary is used. Core formulas and historical study files are unchanged. The driver, independent audit, analysis, protocol, power material and implementation fingerprints are frozen before starting; synthetic verification uses separate seeds.

One scientific host runs at a time. Commit/RAM/C/E reserves are 5/4/5/25 GiB, checked each second, with private memory at most 1 GiB, host time at most two hours and originals at most 3 GiB. Exploration suggests approximately 15–25 minutes; actual cost is measured. Originals, archive and API readback reserve 9 GiB plus the 25-GiB floor. Resource stops occur at complete boundaries; new deaths or orphan in-flight states are preserved and require discussion. Historical paused experiments and user services remain untouched.

Completion requires independent continuity, file and arithmetic checks, explicit comparative conclusions, effect sizes, intervals and interpretation of every target. Reviewed bilingual reports and a fully read-back original archive with pending=0 precede finalization. Personal temporal-Transformer joint development, correction, reversal and relearning follow as a distinct system-level layer.
