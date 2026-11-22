# Retained inhibition supports delayed choices; removing it makes the outputs indistinguishable

Revision 2, 14 November 2026: corrects one configuration description. The first edition called base-weight strengthening retention growth, although the saved configurations have time-scale growth and relaxation disabled. Experimental configurations, data, scores and conclusions are unchanged. [Retained first edition](report.en.md).

14 November 2026 · R51t4 · Four new encoding blocks, 64 complete systems and 896 continuous final questions.

## Scientific conclusions

**The configuration with faster inhibition decay retained choice between learned pairs.** Both it and the 6.1 task reference answered 32/32 short-delay, 32/32 long-delay and 32/32 distractor questions correctly, with no task-node observations reaching the preregistered saturation threshold. Together with R51t2, this identifies a configuration that retains inhibition, restores low-amplitude persistent activity and preserves discrimination in this curriculum.

**The batch did not establish a performance advantage for making this configuration the default.** The reference already answered every cued pairing question correctly, producing a ceiling. The candidate therefore did not achieve the required ten-percentage-point gain. The positive result is preserved ability, rather than improved cognitive performance. Shorter persistence in the earlier holding apparatus did not prevent the reference from answering 60-second-delay questions after this continuous curriculum.

**Removing inhibition caused a clear impairment.** All 96 cued pairing questions produced WAIT. Activity was present: the final half-second activation integral was exactly equal at both outputs, 0.405227652 activity-seconds each, giving a zero difference. Strong ongoing activity thus remained while discrimination between answers was lost. This supports retaining inhibition and measuring activity strength, selectivity and decisions separately.

**Prefix recovery in 6.1 failed.** None of the four profiles restored bidirectional A-B versus D-B discrimination in any block. Bounded review and correction did not solve it. The historical crossed investigation is reported separately as R51t5; its outcome does not replace this batch's scores.

## Purpose, conditions and complete curriculum

The author proposed that prolonging activity might weaken competition and discrimination. This experiment therefore measured delayed decisions as well as activity. Candidate selection used completed R51t2 data only; the new formal material was not used for tuning.

Seeds 941101–941104 define four new encoding blocks. Each crosses two tasks, two curricula exchanging C/E and four profiles, giving 64 systems. The material units are the four blocks; questions, exchanged curricula and profiles are nested or paired observations. The tasks teach A-C versus D-E pairs, or A-B-C versus D-B-E sequences sharing the middle stimulus.

Profiles are the 6.1 task reference; inhibition time constant reduced from 0.232135 to 0.058034 seconds; immediate novelty with inhibitory transmission excluded from connection strengthening; and inhibition disabled. The third profile retains inhibitory signals and changes whether their transmitted amount contributes to strengthening. Profiles apply from birth, so the comparison includes their combined effects on learning and answering.

The pairing task uses historical resource conditions: depletion off and a one-second facilitation time constant. The prefix task uses depletion on and facilitation time constant zero. Both explicitly enable strengthening of base connection weights (edge_consolidation_enabled=true); growth of the decay time scale and its relaxation remain disabled (retention_growth_enabled=false, retention_relaxation_enabled=false). All other parameters are recorded in the frozen configurations. These are declared task configurations, not a claim that every production default was used. Initial teaching replays the original 80 paired or 210 sequence inputs and fixed historical background. Later stages deliver an independent background stimulus of strength 0.2 every 0.5 seconds.

Initial teaching is followed by review at additional intervals of one, three and nine internal seconds. Four development questions then receive a review of the correct relation; an error adds two repetitions and two at 0.9 times the teaching strength, with increasing intervals. Correction uses development questions only and ends before final testing.

Each system then answers 14 continuous final questions: A and D at delays of 0.5, 3, 30 and 60 seconds; distractor questions at 3 and 30 seconds; and two 30-second blank questions. Prefix trials deliver B one second after the prefix and measure delay from B. Question order is randomized beforehand and shared across paired conditions. Final tests supply neither C/E answers nor score feedback.

Activation, inhibition, direct and associative activity are recorded every 50 milliseconds. A fixed process rule integrates C/E activation over the last half-second, selecting the larger output if their absolute difference exceeds 1×10⁻⁶ activity-seconds and otherwise choosing WAIT. Complete state continues through ordinary teaching and testing without per-question restoration. This mechanism task has no trained reader, motor adapter or body.

## Paired-association results

| Profile | Short, 0.5/3 s | Long, 30/60 s | Distractor | Correct WAIT without a cue |
| --- | ---: | ---: | ---: | ---: |
| 6.1 task reference | 32/32 | 32/32 | 32/32 | 0/16 |
| Faster inhibition decay | 32/32 | 32/32 | 32/32 | 0/16 |
| Immediate novelty; inhibitory transmission excluded from strengthening | 32/32 | 0/32 | 16/32 | 16/16 |
| Inhibition off | 0/32 | 0/32 | 0/32 | 16/16 |

The first two profiles reached the same accuracy in every block and scored 16/16 at each exact delay. Neither had task-node observations at or above 0.95 activation. The third profile retained short-delay answers but produced WAIT in every long-delay question. This combination impaired delayed expression; the result does not assign the impairment separately to either of its two changes.

Without inhibition, all 96 cued questions had exactly equal C/E integrals, each 0.405227651685247. Only approximately 0.0351% of task-node observations reached 0.95 activation. Checking the activation ceiling alone would therefore miss the failure: two outputs can be equally strong and uninformative without spending most of their time at the upper bound.

On blank questions, the reference and faster-decay profile still selected C or E. Prior experience was not cleared, and the fixed reader converted existing activity differences into choices. The rule therefore did not reliably distinguish an answer to a new cue from output without a new cue. The other profiles' correct WAIT responses on blanks must be read alongside their cued failures.

## Prefix results and preregistered targets

All four profiles produced the same scores: short delay 8/32, long delay 0/32, distractor 0/32 and blank WAIT 16/16. At the exact delays, 0.5-second questions scored 8/16; 3-, 30- and 60-second questions each scored 0/16, all WAIT. Prefix restoration was 0/4 blocks for every profile. The persistence candidate did not solve ending selection after the shared B.

Functional benefit required a long-delay gain of at least ten percentage points and accuracy of at least 75% in at least 3/4 blocks, with no more than five percentage points of short-delay loss and no more than 10% saturated task-node observations. Both candidates passed in 0/4 blocks for both tasks. The bidirectional prefix-restoration target also failed throughout.

For the reference and faster-decay pairing profiles, the accuracy ceiling allows the conclusion that both completed the task; it does not rank their remaining capacity. This measurement ceiling is not evidence that persistent activity has no function. Equal-output failure without inhibition and long-delay failure in the other combination were directly measured impairments.

## Implications for ThreeMind

Three findings guide the choice: an inhibition-preserving persistence configuration retains paired choices; removing inhibition destroys discrimination; and prolonging activity alone does not repair this prefix task. The current default is retained, with faster inhibition decay kept as a research candidate. A future default should follow task benefit rather than duration alone.

Rao and colleagues' monkey prefrontal study motivated attention to selectivity: blocking inhibition removed existing spatial tuning in many cells while creating it in some others. The equal-output result here is measured in ThreeMind itself. [Rao et al., 2000](https://pmc.ncbi.nlm.nih.gov/articles/PMC6774140/). Compte and colleagues' excitatory–inhibitory working-memory model also motivated preserving inhibition while examining the organization of persistent activity. [Compte et al., 2000](https://www.cns.nyu.edu/wanglab/publications/pdf/compte2000.pdf).

## Verification, resources and delivery

All 64 systems, 1,536 continuous phases, 3,200 complete states and 88,384 inputs passed audit. Independent integration reproduced all 896 final answers, with maximum arithmetic error 1.39×10⁻¹⁷. Denser or disabled observation, save/restore and a host pause produced identical complete Core states; the two identity fields of independently created calibration observers were checked separately.

The original read-only auditor compared string timestamps directly with an integer. A separate v2 normalizes the three numerical types before exact checking. The original auditor and correction record are retained; no individual or scoring rule was changed. Scientific execution took 56.73 minutes, with peak private memory 678.12 MiB and all 5/4/5/25-GiB reserves maintained.

Originals: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/delayed-choice61-v1`. Figures `figures/delayed-choice.*` and `figures/choice-processes.*` come from audited records. The zero difference for inhibition-off traces means equal outputs, not absent activation. The full archive and bilingual reports are closed after complete research-API readback and pending=0, recorded in `publication/completion.json`. Production Core, defaults and the manuscript are unchanged; comprehensive revalidation remains paused.

The pre-archive inventory contains 15,810 files, 280.61 MiB of logical content and 314.11 MiB of unique allocated storage, with no additional hard-link paths. This excludes subsequent archive and API-readback copies; see `storage-before-publication.json`.
