# R48b: The slow rule improved immediate learning but failed delayed retention

2026-11-11. First report, eight-origin exploration. [中文](report.zh.md) · [Preregistered protocol](protocol.en.md) · [Local assay R48a](../report.en.md)

## Scientific conclusion

**The tested weight-dependent rule improved immediate learning but did not meet the registered learning-and-retention goals.** The slow rule scored 128/128 on the immediate initial test, compared with 111/128 for matched slow exponential decay. Seven of eight paired origins improved and one tied, a mean gain of 13.28 percentage points. The slow rule required no additional correction in any stage and used 38,400 personal-adapter updates, one-third fewer than the matched slow exponential group's 57,600. These are positive results obtained in this batch.

**The benefit did not survive the 300-internal-second delay.** The slow rule scored 50% in every delayed stage; the fast rule scored 50% both immediately and after the delay. Both candidates passed 0/8 complete goals at each of initial learning, new learning, reversal, and return to the old rule. Both matched exponential controls also scored 0/8 throughout. Inverse-logarithmic decay passed 8/8 for initial learning, new learning, and return, winning these retention tasks; reversal passed 4/8, below the preregistered six-origin target.

This round therefore selects no new default decay rule. **Stronger weights do forget more slowly in relative terms, but this particular formula at the two registered settings did not jointly solve weak-experience removal, retention of useful experience, and rule updating.** The immediate benefit of the slow rule is retained as a finding; the case for making it the default is rejected by the registered outcomes. No group passed all targets, and the batch closes under its original criteria.

## Question and design

R48a measured local connections and temporal internal responses. R48b tested whether complete individuals could make correct choices: learn new relations, retain old ones, update a reversed rule, and relearn an earlier rule. Matched exponential controls distinguished a benefit of weight dependence from a change in overall decay speed.

The candidate uses

\[
dw/dt=-w[\lambda_{\min}+\lambda_{\mathrm{extra}}(1-w)]
\]

and updates the current weight with its exact solution. The minimum rate is \(\ln2/86400\) per internal second; the additional rates are 0.06 and 0.012 for the fast and slow settings. Each matched exponential has the same instantaneous relative rate at birth weight 0.035. Node support uses inverse-logarithmic decay in all five groups. Other 5.3 mechanisms are identical, and retention-scale growth and relaxation are disabled. The formula and all parameters were frozen before execution.

Eight new origins each supplied five group members, for 40 complete individuals. Independent N is eight origins. The five individuals within an origin are paired; questions, frames, and saved states do not increase N. Every learner continuously retained its Core, personal temporal Transformer, Adam state, random state, old samples, recent activity, body position, actuator, and internal clock. Ordinary stages and questions never restored an earlier checkpoint.

The personal Transformer observes activation, inhibition, direct activity, and associative activity at two output ports over one second: 20 frames, uniformly sampled to eight reader frames. It has width 48, four heads, and one layer, uses AdamW, and retains the final state of each 1,200-update fit. Teaching is followed by reviews at intervals of 2, 6, and 18 internal seconds. Development errors trigger at most two rounds of targeted lessons, review, and continued fitting. Correct answers are available to the teacher and supervised adapter fitting; formal inference observes only the Core output process.

Final tests use four cue amplitudes withheld from sampling and development. Each individual receives 16 initial questions per test and 24 in each later stage. An immediate test is followed by 300 seconds of background stimulation and then a delayed test, retaining earlier test experiences. The reader selects 0 or 1, a fixed actuator moves to that position, and the actual position feeds back into the Core. This is a closed-loop discrete-choice experiment.

## Expected outcomes and complete goals

J1 requires learning and retaining P/A. J2 requires learning B while retaining P/A. J3 reverses A while protecting P/B. J4 restores the original A while protecting P/B. An individual must score at least 75% on both target and protected relations in both immediate and delayed tests. A group meets a goal when at least six of eight origins pass.

| Group | J1 Initial learning and retention | J2 New learning and old retention | J3 Reversal | J4 Return |
| --- | --- | --- | --- | --- |
| Inverse logarithmic | **8/8** | **8/8** | 4/8 | **8/8** |
| Weight fast | 0/8 | 0/8 | 0/8 | 0/8 |
| Weight slow | 0/8 | 0/8 | 0/8 | 0/8 |
| Matched exponential fast | 0/8 | 0/8 | 0/8 | 0/8 |
| Matched exponential slow | 0/8 | 0/8 | 0/8 | 0/8 |

The 95% Wilson intervals for origin pass proportions are 67.6–100% for 8/8, 21.5–78.5% for 4/8, and 0–32.4% for 0/8. These are exploratory results with all original thresholds and denominators retained. Inverse-logarithmic reversal has high pooled accuracy, but some individuals fail the joint target/protected and immediate/delayed requirements. J3 therefore fails as registered.

## Immediate benefit and delayed failure

The following descriptive table reports correct answers as immediate→delayed. Initial denominators are 128; later denominators are 192 each. There are 1,408 formal questions per group and 7,040 in total.

| Group | Initial, /128 | New, /192 | Reversal, /192 | Return, /192 |
| --- | --- | --- | --- | --- |
| Inverse logarithmic | 128→126 | 192→192 | 188→178 | 188→189 |
| Weight fast | 64→64 | 96→96 | 96→96 | 96→96 |
| Weight slow | 128→64 | 177→96 | 182→96 | 183→96 |
| Matched exponential fast | 64→64 | 96→96 | 96→96 | 96→96 |
| Matched exponential slow | 111→64 | 158→96 | 181→96 | 181→96 |

The slow rule consistently outperformed its matched exponential in the immediate initial test. Its mean immediate new-learning gain was 9.90 percentage points, with both positive and negative differences across origins. Immediate reversal and return differed by only 0.52 and 1.04 points. Thus the clearest benefit is **easier initial learning with less correction**. These component interpretations do not replace complete goals, and pooled question proportions are not treated as independent-sample statistics.

After results were available, a read-only follow-up checked 160 complete states saved before delayed probing and the recorded reader sequences. It produced `delay-readout-followup-v1.json` and `descriptive-analysis-v1.json`, identifying two kinds of failure:

1. **Fast decay removed connections that should have been retained.** All delayed reader sequences were zero in weight fast and both matched exponential groups. Every correct delayed answer in weight fast and matched exponential fast occurred when the body already occupied the correct position; all new-position choices failed. Their 50% therefore does not indicate learning both relations.
2. **Surviving connections can also fail to support correct expression.** Before the initial delayed test, all eight weight-slow individuals still had eight connections, with weights 0.013421–0.015323, yet scored only 64/128. These individuals had not lost every connection, but the decayed Core activity and existing personal reader no longer sustained correct choices. This rules out the explanation that every failure in the batch was simply connection deletion. Identifying the specific loss of discriminability in transmission and readout requires a separately registered intervention study.

A further read-only appendix examined R48a's review histories. In weight fast and matched exponential fast, all eight origins and both opposing histories lost and subsequently recreated the target connection during long review gaps, twice per history. Neither slow group nor inverse-logarithmic decay showed these recreations. Fast-group reviews therefore repeatedly recreated a connection instead of continuously strengthening the same surviving connection. The appendix preserves source hashes and references R48a's delivered archive; that report and archive remain unchanged.

## Meaning for ThreeMind

This round establishes a concrete trade-off: **linearly decreasing relative decay with current weight can improve some immediate learning, but does not provide the retention required here.** Fast decay discards useful experience too quickly. Slow decay improves initial learning without preserving the benefit in delayed tests. R48a's analytical derivation also bounds the survival-time ratio available to specified strong and weak initial weights; changing speed alone cannot arbitrarily separate those times.

For the tested ThreeMind conditions, inverse-logarithmic decay remains the more reliable retention reference, with reversal a clear difficulty. The decision is to preserve the independent candidate and all negative results, keep production defaults unchanged, and end this bounded parameter comparison. Any later rule should make distinguishable, preregistered predictions for weak-experience removal, strong-experience retention, and reversal. Rust implementation supports reproduction and subsequent performance comparison; it does not change this scientific scoring.

## Continuity, audit, and cost

An independent arithmetic program checked 40 individuals, 1,820 complete boundaries, 939 adapter dependency files, and all 18,620 development, sampling, and formal queries. It verified 366,000 optimizer updates and complete state chains; actual actuator commands matched output choices. Total internal time was 95,692.5 seconds. The host completed normally, with no dead-host replay or rollback. Measurement, saving, and analysis did not advance simulated time.

| Group, eight individuals each | Teaching lessons | Adapter updates | Internal seconds | Operation wall seconds |
| --- | ---: | ---: | ---: | ---: |
| Inverse logarithmic | 2,005 | 42,000 | 16,377.5 | 574.02 |
| Weight fast | 3,828 | 112,800 | 22,602 | 1,012.15 |
| Weight slow | 1,936 | 38,400 | 16,088 | 497.10 |
| Matched exponential fast | 3,872 | 115,200 | 22,768 | 1,025.98 |
| Matched exponential slow | 2,454 | 57,600 | 17,857 | 654.10 |

Wall times include different correction and activity workloads. An isolated Rust compilation overlapped part of execution. These are descriptive batch costs; equal-size formula/backend performance is measured separately.

Total host wall time was 3,965.00 seconds, or 66.08 minutes. Peak private memory was 1,835,446,272 bytes, about 1.71GiB. Minimum available commit/RAM/C/E remained above the 5/4/5/25GiB guards. The pre-archive inventory contains 6,890 files, 244,443,860 logical bytes, and 258,713,328 allocated file-stream bytes after deduplication by file identity. No duplicate hard links occurred. The largest compressed whole-state file is 104,576 bytes; with personal-adapter and optimizer dependencies it comprises four files, 378,589 logical bytes and 381,304 allocated bytes. Directory metadata is excluded. Reports, appendices, figures, and archives were added later; the delivery receipt records final package size.

## Originals and reproduction

Originals reside at `E:/ThreeMindData/experiments/2026-11-11-weight-dependent-decay/joint-v1`. Research record: `1663e2c1-430f-539f-9e0b-aa6a2af33e91`. Primary analysis is `analysis-v1.json`; independent verification is `independent-audit-v1.json`. Additional diagnostics are explicitly retrospective. `figures/r48-registered-results` provides PNG/SVG/PDF views of both batches' registered goals and the six-origin threshold. Completion is recorded in `publication/completion.json` after full unified-API readback of both protocols, reports, and the original archive. Analysis and review were performed by the assistant, not registered as external researcher replication.
