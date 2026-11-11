# R48a: Weight-dependent decay cleared weak experience but failed delayed retention

11 November 2026, first exploratory report. [中文](report.zh.md) · [Frozen protocol](protocol.en.md) · [Whole-system protocol](joint/protocol.en.md)

## Conclusion

**The proposed rule makes stronger weights decay more slowly in fractional terms, but its two registered settings did not achieve the intended balance of retention and forgetting.** The fast setting removed connections formed by weak stimuli within 30 internal seconds in all eight origins. Both settings, however, lost the target connections and experience-dependent responses at 300 seconds after spaced review, strong input and novel experience: 0/8 in every retention condition. The slow setting also failed weak-experience forgetting, at 0/8.

**Matched exponential controls obtained the same pass counts.** Faster overall decay can account for the fast setting's weak-experience clearance; weight dependence supplied no additional success on the registered goals. Inverse-logarithmic decay retained target connections in all three courses and retained temporal expression after spaced review and strong input in 7/8 and 8/8 origins, respectively. It won those two delayed-retention comparisons. None of the five arms met all targets, so the new rule is not recommended as the default.

## Question, equation and controls

The author requested a simple rule under which stronger connections forget more slowly in relative terms. We tested whether making the decay rate depend only on current weight could combine rapid forgetting of weak experience, retention of repeated and strong experience, and eventual forgetting without further reinforcement.

The candidate is

\[
\frac{dw}{dt}=-w[\lambda_{\min}+\lambda_{\mathrm{extra}}(1-w)],\qquad0\leq w\leq1.
\]

Time is measured in internal seconds and \(w\) is the persistent connection weight. Both settings use \(\lambda_{\min}=\ln2/86400\) per second; the extra rate is 0.06 or 0.012 per second. The minimum-rate calibration does not give an actual one-day connection lifetime: the extra decay operates as soon as weight falls below one. Reinforcement directly increases current weight. There are no lists of past contributions or numerical integration steps.

With \(a=\lambda_{\min}+\lambda_{\mathrm{extra}}\), \(b=\lambda_{\mathrm{extra}}\), and \(z=e^{-a\Delta t}\), the exact update is

\[
w'=\frac{awz}{a(1-w)+\lambda_{\min}w+bwz}.
\]

The five arms were inverse-logarithmic decay, fast and slow weight-dependent decay, and two matched exponentials. The latter use the constant rate \(\lambda_{\min}+\lambda_{\mathrm{extra}}(1-0.035)\), matching the candidate's instantaneous fractional rate near the existing birth weight. The matching value was chosen before execution. All arms retain identical inverse-logarithmic node support, other /5.3 mechanisms, inputs and Python backend. Retention-scale growth and relaxation are disabled.

Eight independent origins generated 1,280 continuous sequences. Fixed amplitude and phase variation distinguish origins; arms within an origin are paired. Each retention delay has a separately born, continuously developed cohort and a single formal probe, avoiding earlier tests as later review. Opposite teaching histories and cue-omission controls identify experience-dependent response differences. Parameters, seeds and input tables were frozen before execution.

## Expectations, measurements and scores

Each target required at least 6/8 origins. W requires that weak teaching actually formed both directed target connections and that both disappeared by 30 seconds. S requires both directions at 300 seconds. E compares twenty frames over one second before and after the cue, retaining activation, inhibition, direct and associative fields. After subtracting baseline and cue-omission controls, opposite histories are compared: early and late RMS must both exceed 0.0001, late RMS must be at least 10% of early RMS, and cosine similarity must reach 0.8. F projects the actual 300-second state through thirty days without any further reinforcement, requiring weights below the 0.008 deletion threshold.

Each triple below is **spaced review / strong input / novel experience**. Every denominator is eight independent origins.

| Arm | 300-s structure S | 300-s expression E | Conditional 30-day forgetting F | 30-s weak forgetting W |
| --- | --- | --- | --- | --- |
| Inverse logarithmic | 8 / 8 / 8 | 7 / 8 / 0 | 4 / 4 / 8 | 0 |
| Weight dependent, fast | 0 / 0 / 0 | 0 / 0 / 0 | 8 / 8 / 8 | 8 |
| Weight dependent, slow | 0 / 0 / 0 | 0 / 0 / 0 | 8 / 8 / 8 | 0 |
| Matched exponential, fast | 0 / 0 / 0 | 0 / 0 / 0 | 8 / 8 / 8 | 8 |
| Matched exponential, slow | 0 / 0 / 0 | 0 / 0 / 0 | 8 / 8 / 8 | 0 |

**The two fast arms met W; inverse logarithmic met S and E for review and strong input.** All arms failed E for novel experience. Weight-dependent and exponential arms had already lost target connections before 300 seconds, so their F passes reflect completed forgetting rather than long retention. Inverse-logarithmic F scored 4/8 for review and strong input, below the required 6/8.

The exploratory success rates retain uncertainty: 95% Wilson intervals are 67.6–100% for 8/8, 52.9–97.8% for 7/8, and 0–32.4% for 0/8. Directions, delays and records nested within origins do not increase independent N.

## Why the combined goal failed

The following post-result explanation is saved separately in `retrospective-diagnostics-v1.json`; original scores remain unchanged.

**Learned weights occupied a range where this rule makes only small distinctions.** Weak teaching formed weights of 0.03433–0.03502. The fast weight-dependent arm ended spaced teaching at 0.04104–0.04641; strong input produced 0.09244–0.12241. Across these ranges, the multiplier \(1-w\) remains near one. Stronger experience therefore received insufficient additional retention. Fast decay removed weak experience and required memories together; slow decay delayed weak forgetting without retaining the 300-second targets.

All target connections were absent at 300 seconds in both teaching histories and all eight origins for both weight-dependent and both matched-exponential arms; their late experience differences were zero. Inverse-logarithmic novelty instead retained structure and nonzero late responses, but temporal similarity was only 0.572–0.777, below 0.8 in every origin. Three origins also had early responses below the registered measurement floor. One inverse-logarithmic review origin failed that early floor; the other seven passed. These distinct failure modes are reported separately.

**The equation also bounds the lifetime separation.** Without further reinforcement, time from initial weight \(w\) to threshold \(\theta\) is

\[
T(w)=\frac1a\ln\frac{w(a-b\theta)}{\theta(a-bw)}.
\]

At \(\theta=0.008\), across this equation's positive parameters, the lifetime ratio for weights 0.9 versus 0.035 is at most 4.668; the corresponding bound for 0.99 is approximately 6.262. The bounds occur as \(b/a\) approaches one. Under the fast setting, weight 0.035 reaches threshold after approximately 25.05 seconds, whereas 0.9 lasts about 116.92 seconds. Greater weight prolongs retention, but adjusting speed alone cannot make these two specified initial weights satisfy both forgetting within 30 seconds and retention to 300 seconds. This deduction assumes no subsequent reinforcement; the experiments execute actual associative reinforcement normally.

## Meaning for ThreeMind and next step

The study establishes a simple implementation in which current weight controls fractional decay. It rejects the expectation that the two registered parameter settings meet the complete retention–forgetting goals. Rapid forgetting is useful, but here it matched the exponential control while sacrificing delayed retention. **The evidence supports keeping inverse logarithmic as the retention reference and retaining the new rule as an independent research option, without changing defaults.**

R48b next develops forty whole individuals under the frozen protocol, including personal temporal Transformers, progressively spaced review and up to two correction rounds. It tests initial learning, new learning, reversal and relearning. These behavioral questions require their own experiment; this result does not replace it or alter its parameters. Rust support follows both frozen batches and must preserve experimental identity and Python equivalence.

## Originals, continuity and cost

An independent program recomputed every score and checked 2,560 complete boundaries, 5,120 file hashes and birth–teaching–probe state chains, with agreement throughout. The sum of internal times was 273,920 seconds. No rollback or replay after death occurred; observation and saving did not advance simulation.

| Item | Measurement |
| --- | --- |
| Host wall time | 622.24 s, about 10.37 min |
| Peak private memory | 133,029,888 bytes, about 126.9 MiB |
| Teaching and probe operation times | Inverse logarithmic 121.69 s; weight fast 89.05 s; weight slow 106.93 s; matched fast 88.00 s; matched slow 105.86 s; 256 sequences per arm |
| Pre-archive inventory | 9,406 files; 27,406,018 logical bytes; 52,123,128 allocated file-stream bytes |
| Largest complete local state in that inventory | 6,528 compressed bytes, 8,192 allocated bytes; 3 nodes and 2 directed connections |

Arms differ in surviving connections and event counts, so these operation times are not an equal-workload formula benchmark. A separate fixed-size, 64-node Python engineering measurement gave median advance times of approximately 0.071–0.074 seconds across the five arms. Rust receives its own matched-workload measurement. Whole individuals additionally require personal adapter dependencies; this table describes the local assay. File identities deduplicate hard links, of which this batch had none; directory metadata is excluded. Diagnostics, reports and archives were added after this inventory; final archive size is recorded in the delivery receipt.

Originals: `E:/ThreeMindData/experiments/2026-11-11-weight-dependent-decay/assay-v1`. Record: `aa70f38d-6464-51f1-9226-15355094e844`. Main analysis: `analysis-v1.json`; independent arithmetic: `independent-audit-v1.json`; full-readback completion receipt: `publication/completion.json`. The assistant authored the report and arithmetic audit; these are not labeled external researcher replication.
