# Protocol-compliant teaching and temporal readout for 3-SAT: v2 report

1 November 2026. Eight independent paired origins, 16 continuously developing students. Computation, input-chain audit and independent frozen-reader replay are complete. Project `7137e322-c160-424e-8832-55b29111fd31`, record `9219955f-127c-5196-95db-fa62081ca9b8`; archive and local API completion receipts are in [delivery](delivery.md).

## Purpose and expectations

Does a complete ThreeMind system, taught with initial repetition, increasingly spaced review, development correction/retesting and a personal temporal Transformer, improve bounded 3-SAT local search? Does correct Core pair teaching add benefit beyond correct peripheral supervision? Targets, the 10-percentage-point threshold and interval rules were fixed before formal execution. [Protocol](protocol.en.md)

## Actual training

Each paired origin contains two separately continuous students using genuine continuous-memory/5.1 defaults. Each category receives ten dense demonstrations, followed by three reviews with additional delays of 2, 6 and 18 internal seconds. Demonstrations last 1.5 seconds and use ordinary stimuli; actual per-category times and gaps are preserved. Each student received 112 demonstrations and 4800 continuous optimizer updates.

Each candidate question supplies a complete one-second process: 20 raw frames and eight fixed samples spanning first to last. Activation, inhibition, direct and associative activity use a fixed layout. Every student owns a one-layer, four-head Transformer (width 48, feed-forward 96, 21,986 parameters), AdamW and learning RNG. Calibration uses unassisted questions and commits the last optimizer state, without best-loss restoration. All sixteen students actually completed three review/retest cycles after initial teaching. Original-error and similar-condition sampling paths passed isolated apparatus checks. All development local questions were 16/16 and no local classification errors occurred in development SAT. The actual later cycles therefore reviewed all categories; unsolved formulas were not relabeled as local classification mistakes.

The final 26 problems (24 SAT and two contradictory sentinels) are experienced continuously with frozen reader weights and continuing ordinary Core dynamics. No Core default or half-life changed and no ordinary student was rewound. Final ages span 4098–5859 internal seconds. Independent paired N is eight, not the number of students, questions or frames.

## Final results

|Method|Solved SAT|Solved fraction|Final local classifications|SAT flips|
|---|---:|---:|---:|---:|
|Normal teaching + personal temporal reader|162/192|84.38%|27312/27312|7568|
|Shuffled Core pairing + personal temporal reader|162/192|84.38%|27312/27312|7568|
|Random local search|103/192|53.65%|not applicable|13239|
|Matched-information zero-break rule|162/192|84.38%|not applicable|7568|
|WalkSAT|168/192|87.50%|not applicable|6432|

Normal minus random solving benefit is 30.73 percentage points, with a 97.5% paired-origin interval [21.35—39.06]. Normal minus shuffled is 0.00 points [0.00—0.00]. **G3 passes:** every SAT claim passes an independent verifier and all contradictory sentinels return UNKNOWN. Flip totals include the 96-step cap for failures.

Solved fractions use 192 satisfiable problems per method. The 27,312 local classifications and 208 action trajectories also include two contradictory sentinels per origin. They are nested observations; independent paired N remains eight.

|Final formula size|Normal|Shuffled|Random|Quantized rule|WalkSAT|
|---|---:|---:|---:|---:|---:|
|12 variables|91/96|91/96|70/96|91/96|90/96|
|20 variables|71/96|71/96|33/96|71/96|78/96|

## Analysis, scientific conclusions and meaning

1. **G1 passes: the learned local strategy improves complete-system solving over random local search by the registered criterion.** The behavioral endpoint comes from held-out formulas under the declared hybrid search architecture.
2. **G2 fails: normal Core pair teaching provides no demonstrated additional solving benefit over shuffled pairing in this batch.** Both conditions receive correct peripheral supervision. This comparison closes the registered teaching-history question without substituting complete-system performance for Core-specific learning.
3. **All 208 full action trajectories in each learned condition exactly match the quantized-rule reference. The system successfully implements the specified learned local rule.** The rule reference shares categorical information, the action decoder and 25% random-choice probability. WalkSAT solves 168/192 using exact break counts and its different noise policy, a comparison of complete implementations.
4. **Protocol-compliant continuous teaching and temporal readout were executed.** The normal students make 27312/27312 correct final local classifications; conclusions use actual behavior, not fitting loss. Half-life changes were explicitly deferred and no retention mechanism repair was implemented.

The taught policy prefers zero-break candidates. Core receives four anonymous categories; formula analysis and bit flips are external. Held-out formulas have 12 or 20 variables. The task does not test reading an entire formula and inventing an arbitrary SAT algorithm. v1 and v2 differ in material, teaching and readout; causal effect estimates use within-v2 paired controls, not cross-batch score subtraction.

In the observed batch, WalkSAT solves the most formulas with the fewest flips. Its solved-fraction lead over normal teaching is 3.125 points, but the paired-origin interval crosses zero; no population-level statistical superiority is declared. Normal students spend 55.03 seconds solving the 192 SAT problems, versus 1.52 for random search, 0.93 for the quantized rule and 0.78 for WalkSAT, excluding teaching, checkpointing and sentinels. The quantized rule reproduces the learned trajectories faster. The practical conclusion is explicit: learning and sustained execution work, but this SAT configuration offers no performance benefit over directly implementing that rule and is not scaled up.

## Integrity, cost and historical correction

Thirteen apparatus, three host-guard and four arithmetic checks pass. The independent read-only audit checks 1040 final trajectories, 480 complete-state transitions, 54624 final temporal questions and 1792 demonstrations. All 54624 frozen-reader replay predictions agree. Calibration does not advance Core time; unchanged Core configuration and frozen final readers are verified. No local classification mistake occurred in the formal batch, so it contains no actual mistake-repair case. Error-path coverage comes from the isolated apparatus tests. These are assistant checks, not author/human review or external replication.

Scientific-host wall time is 20.02 minutes, peak private memory 1.662 GiB. System reserves stay at 5/4/5/25 GiB commit/RAM/C/data. The initial 1-GiB process allowance omitted torch load cost and paused safely at the complete zero-second birth boundary. A separately recorded 2-GiB host allowance resumed that same state without changing curriculum or losing internal time. [Host amendment](host-budget-note.en.md). Actual disk allocation and complete-subject dependency sizes are reported in delivery.

The original v1 scores and evidence package remain intact. A [dated procedure correction](v1-procedure-correction.en.md) was appended to its completed research record, identifying omitted review, correction and temporal personal readout. Its archive hash is unchanged. Historical studies, automations and author manuscripts are untouched; no further SAT batch starts automatically.
