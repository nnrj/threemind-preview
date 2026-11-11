# R47c: initial learning, retention, reversal and relearning in complete individuals

11 November 2026, exploratory report, first edition. [中文](report.zh.md) · [Preregistered protocol](protocol.en.md) · [48-origin local confirmation](../confirmation/report.en.md)

## Scientific conclusions

**With inverse logarithmic decay, all eight individuals learned and retained the initial mappings, learned new mappings while retaining old performance, and relearned the original rule. These three preregistered objectives passed. Rule reversal passed in 4/8, below the required 6/8, and therefore failed.** Inverse logarithmic decay performed best on initial and new learning with retention. Power-law decay also achieved 8/8 for relearning the original rule, jointly meeting that objective.

**None of the four curves met all four learning objectives.** Exponential decay supported many correct immediate choices, but delayed accuracy fell to 50% in every stage, yielding 0/8 for all four objectives. Power law and power law followed by an exponential tail also fell short of 6/8 for initial retention, new learning and reversal. These conclusions follow the original criteria without adding a new requirement after the results.

For ThreeMind, the experiment delivers both a positive result and a specific improvement target. After simplifying decay to one weight and one age, the local retention advantage of inverse logarithmic decay also appears in continuous learning with a personal temporal Transformer and action feedback. The present curve, curriculum and reader updates do not yet sustain reversed rules in most origins. R47a/b also established failure of the weak-experience forgetting objective. Consequently, no configuration meets all requirements; the engineering power-law default and global creation default /3 remain unchanged.

## Purpose, expectations and complete subjects

The experiment asks whether retention measured with a fixed temporal instrument supports actual choices and how each curve balances old and new learning. Eight independent origins each supplied four complete individuals, one per curve: 32 individuals, paired by origin, independent N=8. They used genuine Rust /5.3, a 30-internal-second scale, age retained on reinforcement, and disabled timescale growth and relaxation. All were new subjects; historical individuals were not loaded.

Each subject retained its own Core, anonymous mapping, Transformer reader, Adam and random states, teaching and calibration history, recent activity, body position and actuator state. The reader observes activation, inhibition, direct and associative activity over twenty frames spanning one second, selecting eight uniformly spaced frames. The actuator executes the selected position, and proprioceptive feedback reports the actual position. Scoring answers are not inference inputs.

The four stages are initial P/A learning, addition of B, reversal of A, and restoration of A's original rule. Each includes interleaved lessons, reviews spaced by 2/6/18 seconds, and up to two corrections of development errors. All previous samples remain available, the personal reader continues learning, and the last optimizer state is committed. Final tests use stimulus amplitudes absent from calibration and development. Readers are fixed during these tests, while Core, body and internal time continue. Each goal requires at least 75% accuracy on both target and protected relations at both immediate and 300-second delayed tests, in at least 6/8 individuals per curve.

Delayed tests include the earlier immediate-test experience and measure retention within this continuous procedure. R47a/b separately used delay cohorts without earlier testing. Curves receive the same correction opportunity and limit, with actual correction counts allowed to differ. Results here concern the jointly trained complete systems.

## Primary scores and failure locations

| Curve | J1 Initial learning and retention | J2 New learning with old retention | J3 Reversal with unrelated retention | J4 Relearning with other retention |
| --- | --- | --- | --- | --- |
| Exponential | 0/8 | 0/8 | 0/8 | 0/8 |
| Power law | 1/8 | 3/8 | 3/8 | **8/8, passed** |
| Inverse logarithmic | **8/8, passed** | **8/8, passed** | 4/8 | **8/8, passed** |
| Power–exponential | 1/8 | 2/8 | 1/8 | 4/8 |

These counts require each individual to pass both tests and both relevant relation groups. The next table gives correct target-relation questions, immediate then delayed. Questions are nested observations, not additional independent origins.

| Curve | Initial P/A | New B | Reversed A | Restored original A |
| --- | --- | --- | --- | --- |
| Exponential | 120/128; 64/128 | 58/64; 32/64 | 62/64; 32/64 | 62/64; 32/64 |
| Power law | 128/128; 86/128 | 63/64; 45/64 | 61/64; 32/64 | 64/64; 64/64 |
| Inverse logarithmic | 128/128; 128/128 | 64/64; 64/64 | 59/64; 46/64 | 61/64; 61/64 |
| Power–exponential | 128/128; 86/128 | 64/64; 46/64 | 60/64; 43/64 | 64/64; 49/64 |

Inverse logarithmic decay scored 128/128 on protected relations at both tests in each of the last three stages. Its reversal failures concern the changed A mappings: origin 2 scored 3/8 immediately; origins 4, 5 and 6 scored 4/8, 4/8 and 5/8 after the delay. The other four origins reached 6/8 in both tests. Failure therefore arose in establishing or retaining the new reversed mapping, rather than general loss of all performance.

Power law also scored 128/128 on protected relations throughout the last three stages. Power–exponential scored 128/128 immediately and 95/128, 102/128 and 103/128 after the respective delays. Exponential scored 113/128, 119/128 and 121/128 immediately and 64/128 after every delay. Much of the difference appears after the delay; the systems were not uniformly unable to learn initially.

Eight origins constitute an exploratory sample. Wilson 95% intervals are approximately 67.6%–100% for 8/8 and 21.5%–78.5% for 4/8; `analysis-v1.json` contains all individual scores and intervals. The registered sample goals have explicit verdicts. Estimating population success rates more precisely would require fresh confirmation origins.

## Correction, interpretation and implications

Development scores after standard teaching, before correction, and at the final development test were as follows, ordered initial/new/reversal/return. Denominators are 64 in the initial stage and 96 subsequently: exponential 56→60 / 90→90 / 96→96 / 96→96; power law 64→64 / 96→96 / 78→96 / 96→96; inverse logarithmic 64→64 / 96→96 / 92→93 / 94→96; power–exponential 64→64 / 95→96 / 96→96 / 96→96. Development scores do not replace final tests.

Correction raised power-law reversal development scores from 78/96 to 96/96, yet delayed reversed-A performance was 32/64. Thus correction improved current answers without reliably preserving the new rule. Inverse logarithmic decay preserved initial and added mappings but still failed reversal in four origins. Retaining experience and updating a conflicting rule are distinct objectives.

The findings support inverse logarithmic decay as a candidate for further long-term retention research, while providing no complete default winner. A focused next question is how retained old-rule connections and historical training material in the personal reader each affect reversal. This is a new question arising from the results and requires a new intervention protocol; no unperformed attribution is presented as a finding, and completed scores remain unchanged.

## Integrity, scale and cost

An independent program, without importing Core or the primary analyzer, rechecked 1,084 complete boundaries, 453 adapter dependency files and 11,788 sampling/development/test answers; final tests comprised 5,632 questions. Answers, actual actuator positions, four-field temporal records, answer-free proprioceptive feedback and scores were consistent. Each fit committed 1,200 optimizer updates, totaling 181,200. Core state and internal time remained unchanged during fitting. State chains were continuous, with no rollback, rerun or orphaned in-flight unit.

The host ran for 1,518.06 wall seconds (25.30 minutes), with peak private memory of 1,774,616,576 bytes (about 1.65 GiB). Minimum available commit was 9,907,073,024 bytes, and no guard limit was reached. Costs below cover eight individuals per curve. Actual curriculum lengths differ with correction; total times do not isolate formula speed.

| Curve | Operation wall seconds | Summed internal seconds | Optimizer updates | Teacher lessons |
| --- | --- | --- | --- | --- |
| Exponential | 338.10 | 16,643.0 | 45,600 | 2,090 |
| Power law | 397.02 | 17,157.0 | 51,600 | 2,194 |
| Inverse logarithmic | 356.42 | 16,578.0 | 44,400 | 2,056 |
| Power–exponential | 320.11 | 16,184.5 | 39,600 | 1,959 |

Before archiving, 4,180 original files occupied 142,757,955 logical bytes and 151,570,560 allocated bytes after file-identity deduplication, with no duplicate hard links. The largest final complete individual comprised its compressed state and three adapter dependency files: 379,634 logical and 381,304 allocated bytes. Its Core had eleven nodes and sixteen directed edges; the whole-state file occupied 105,617 bytes and adapter dependencies 274,017 bytes. Directory, MFT and research-database overhead are excluded; archives and readback need additional space. These are measured sizes for this small choice apparatus.

Originals: `E:/ThreeMindData/experiments/2026-11-11-kernel53/joint-v1`. Research record: `234feecd-728a-5849-926a-e8f49fcba4ed`. Protocol, implementation, materials and scientific modules were frozen before execution. The assistant prepared this report and independent arithmetic audit. Completion follows full archive and bilingual text readback through the unified research API; the final receipt is `publication/completion.json`.
