# R47a: inverse logarithmic decay retains delayed responses; none of four curves meets the weak-memory forgetting target

11 November 2026, exploratory report, first edition. [中文](report.zh.md) · [Preregistered protocol](protocol.en.md) · [/5.3 plan](../../../docs/en/plans/kernel53.md)

## Conclusions

**Inverse logarithmic decay performed best in the registered 300-internal-second retention comparison.** For massed repetition, spaced review and strong stimulation, all eight independent origins retained the target connections and the experience-specific temporal response. Exponential decay lost both the target connections and the response in all three courses. Power-law and power-exponential decay retained some connections without consistently preserving the original response trajectory. Inverse logarithmic decay is therefore the principal candidate for independent confirmation and complete teaching tasks.

**None of the four curves met the complete retention-and-forgetting objective.** All retained connections formed by a single weak stimulus at 30 seconds, scoring 0/8 for weak-memory forgetting. Inverse logarithmic decay also met the registered conditional 30-day tail target in only 1/8 origins for spaced review and strong stimulation. No curve was selected as a default satisfying all objectives. The initial engineering selection remains power law; the project's global creation default remains historical version /3. This report changes neither.

Both mechanism checks were positive: **the specific strong-stimulus gain and the connection-arrival novelty gain operate in /5.3**, with 8/8 origins passing for every curve. Their identical-input, gain-disabled controls separate the gain effect from a mere increase in delivered input.

## Question and expectation

The author requested a simpler representation: one current weight and one decay age per connection, with reinforcement increasing the current weight while normally retaining accumulated age. This study compares four curves within that /5.3 architecture. The goal was to retain repeated and strong experiences, express them after a delay, and forget a weak one-off experience.

The curves were exponential, power law, inverse logarithmic and power law followed by an exponential tail. All used a 30-internal-second timescale H; the last curve switched at normalized age 10. Timescale growth and relaxation were disabled. Every condition developed continuously from birth through its own course and first test; separate cohorts served each delay. There were eight independent origins and 4,608 continuous sequences. Conditions sharing an origin were paired observations, not additional independent samples.

Measurement retained activation, inhibition, direct activation and associative activation for one second before and after the cue, with 20 frames per window. Baseline and cue-omission effects were subtracted before comparing opposite teaching histories. The registered expression rule required early and late root-mean-square response differences above 0.0001, a late magnitude at least 10% of the early magnitude, and temporal-vector cosine similarity of at least 0.8. At least 6/8 origins had to pass each target. The frozen protocol defines the full course and measurement procedure.

## Results and scientific interpretation

Entries containing three values always follow the order massed repetition / spaced review / strong stimulation. Each denominator is eight independent origins.

| Curve | Connection retention at 300 s, S | Expression retention at 300 s, E | Conditional 30-day tail without further reinforcement, F | Weak-memory forgetting at 30 s, W | Strong / novelty gains, G |
| --- | --- | --- | --- | --- | --- |
| Exponential | 0 / 0 / 0 | 0 / 0 / 0 | 8 / 8 / 8 | 0 | 8 / 8 |
| Power law | 2 / 5 / 8 | 0 / 0 / 1 | 8 / 8 / 8 | 0 | 8 / 8 |
| Inverse logarithmic | 8 / 8 / 8 | 8 / 8 / 8 | 8 / 1 / 1 | 0 | 8 / 8 |
| Power-exponential | 2 / 1 / 8 | 0 / 0 / 1 | 8 / 8 / 8 | 0 | 8 / 8 |

**S and E: inverse logarithmic decay preserved both structure and recognizable history-dependent responses.** Late RMS differences were 0.000311–0.000366, 0.000345–0.000413 and 0.000381–0.000448 across the three courses. Similarities to the early trajectories were 0.899–0.926, 0.933–0.943 and 0.927–0.948. Exponential late responses were all zero. Power-law and power-exponential strong-stimulus conditions retained measurable late responses, but seven origins exceeded the permitted trajectory change, leaving one passing origin for each curve. Their spaced-review early responses were all below the registered measurement threshold. These are distinct failure reasons; neither should be described indiscriminately as absence of any response.

**W: the current initial weights and 30-second scale did not produce rapid forgetting of weak input.** A retrospective edge audit found initial weak-input weights of 0.034565–0.034972 and 30-second weights of 0.016895–0.017309, all above the deletion threshold of 0.008. This explains the 0/8 scores. The next question concerns the relationship between initial connection strength, decay rate and deletion threshold. Selecting a longer-tailed curve alone does not solve it.

**F: slower decay improved retention while extending the unreinforced tail.** Exponential, power-law and power-exponential curves all met this study's finite-tail condition. Inverse logarithmic decay met it for massed repetition but failed in seven origins each for spaced review and strong stimulation. F is an analytic calculation from observed weights and ages at 300 seconds, conditional on no subsequent reinforcement. It is not a 30-day cultivation record. The 30-second weak-memory and 30-day tail targets were prespecified engineering requirements, not measured human-memory constants.

**G: controlled comparisons support both specific gain mechanisms.** Immediate post-teaching target weights increased for strong input relative to identical strong input with its gain disabled, and for the arrival-window novelty condition relative to its gain-disabled control. All origins and curves passed. Both mechanisms therefore retain an actual strengthening effect in /5.3.

This is an exploratory batch. The original analysis reports 95% Wilson intervals for every success rate: approximately 67.6%–100% for 8/8 and 0%–32.4% for 0/8. The eight-origin comparison is complete; population success rates will be assessed in fresh confirmation origins. Exploratory observations will not enter confirmation statistics.

## Meaning for ThreeMind and next decisions

**One-weight, one-age dynamics can support experience retention and temporal expression beyond the original 30-second scale.** Inverse logarithmic decay preserved responses at 300 seconds in all three courses. Simplifying the representation to a single age therefore does not inherently sacrifice retention. This curve is the supported leading candidate for the local retention task.

The results reject the expectation that simply selecting one of these four fixed-scale curves would satisfy every retention and forgetting target in this apparatus. They identify a concrete trade-off between weak-experience removal and a long tail. The next steps are independent confirmation with 48 fresh origins and materials, followed by joint development with personal temporal Transformers, correction, rule reversal and relearning. Task-specific defaults will be selected after those tests. A fifth strategy depending on stimulus strength still requires an explicit rule; no implicit strength-dependent switching or historical-kernel change was introduced here.

A retrospective decomposition shows that the history differences at 300 seconds reside mainly in associative-activation and inhibition records. Instantaneous activation and direct-activation differences at the 50-ms sample points were zero. Reading only instantaneous activation would therefore miss the recorded transmission process. Complete temporal fields remain necessary for subsequent personal adapters. The present result concerns a fixed measurement instrument, rather than a trained action or language capability.

## Evidence, continuity and cost

Each sequence has complete teaching and first-test boundaries. An independent audit checked all 9,216 boundaries, 18,432 file hashes and birth–teaching–test state chains. A separate program importing neither Core nor the primary analysis reproduced every target score. There was no rollback, repeat creation of completed subjects or alteration of historical evidence.

| Quantity | Measurement |
| --- | --- |
| Total internal time | 914,816 seconds, summed over all continuous cohorts |
| Host wall time | 759.47 seconds, approximately 12.66 minutes |
| Peak host private memory | 308,822,016 bytes, approximately 294.5 MiB |
| Summed teaching and test operation times | Exponential 67.76 s; power law 70.83 s; inverse logarithmic 73.51 s; power-exponential 72.68 s; 1,152 sequences each |
| Inventory before archiving | 32,695 files; 91,114,560 logical bytes; 178,247,184 allocated file-stream bytes |
| Largest complete state in that inventory | 6,441 compressed bytes, 8,192 allocated bytes; three nodes and two directed connections; no learned-peripheral dependencies |

Operation timings exclude some guarding, serialization, hashing and publication costs; host duration includes such running overhead. Costs were similar across curves in this small apparatus: inverse logarithmic operation time was approximately 8.5% higher than exponential. This complete local instrument is not representative of the storage footprint of an individual with personal Transformers. File identities were used to deduplicate hard links; none were duplicated here. Directory and filesystem metadata are excluded. The inventory predates additional diagnostics, reports and archives; the final delivery receipt records archive size.

Originals: `E:/ThreeMindData/experiments/2026-11-11-kernel53/assay-v1`. Record: `3e575053-b083-5e69-918f-14de0f55ed66`. Main analysis: `analysis-v1.json`; independent arithmetic: `independent-audit-v1.json`; retrospective explanation: `retrospective-diagnostics-v1.json`; storage: `storage-inventory-v1.json`. Finalization is evidenced by `publication/completion.json` after archive and full research-API readback.

This report and independent arithmetic were produced by the assistant and are not labelled external-researcher replication. Initial implementation commit: `b619cb6a`. Frozen manifests preserve complete source, material and binary fingerprints.
