# Retention audit and candidate decay functions

2026-11-09. This document reports implementation findings, original-state checks and mathematical calculations. Behavioral conclusions are reported separately. [中文](mechanism-audit.zh.md)

## Current retention rule

Under adaptive retention, `continuous-memory/5.1` stores a separate half-life for each node and directed connection. A connection's base weight sets its current transmission coefficient; its half-life controls how quickly that weight falls without reinforcement.

\[
H(t)=\max(H_{\min},H_0-r t),\qquad
w(t)=w_0\exp\left[-\ln 2\int_0^t\frac{du}{H(u)}\right].
\]

The actual configuration has a 30-second minimum, a 2,592,000-second maximum and a half-life relaxation rate of 0.125 seconds per internal second. Thirty seconds is a lower bound, not a fixed lifetime for every memory. At that bound, weight decays exponentially with a fixed 30-second half-life. The active-connection deletion threshold in this study is 0.008.

Without reinforcement, a weight of 0.025 falls to 0.0125 after 30 seconds and reaches 0.008 after approximately 49.32 seconds. Such a connection can disappear during the 72-second R43 test. Lifetime therefore depends jointly on initial weight, half-life and deletion threshold.

Implementation: [analytic decay and expiry](../../../crates/threemind-core/src/retention.rs:178), [local connection maintenance](../../../crates/threemind-core/src/local_shared.rs). Code hashes and actual configurations are preserved in the frozen manifest and source-audit-v1.json.

## Why repeated teaching need not extend connection half-life

Shared external stimulation can create connections or increase their base weight, stability and touch count. This path does not directly increase connection half-life. Actual associative sends can increase both weight and half-life. Node retention has a separate growth path; a persistent node does not establish persistence of its neighboring connections.

The default growth rule uses \(L=\ln(H_{\max}/H_{\min})\) and \(x=\ln(H/H_{\min})\):

\[
H_{\mathrm{new}}=H_{\min}\exp\{L-(L-x)\exp(-g d/L)\},
\]

capped at the maximum. The current gain is \(g=0.2\); a connection's dose \(d\) is 0.1 times the actual associative amount sent. “Log-saturating” names this half-life growth rule, not a logarithmic weight-decay function.

Near \(H=30\), small sends add approximately 0.6 seconds of half-life per unit sent. In a local linear approximation, offsetting the 0.125-second-per-second relaxation would require about 0.2083 units sent per second. This explains why occasional weak use need not accumulate a longer half-life. It is an analytic approximation, not a measured flow rate or a universal network threshold.

Implementation: [shared-stimulation updates](../../../crates/threemind-core/src/local_shared.rs:1095), [growth after actual sends](../../../crates/threemind-core/src/local_shared.rs:1491), [growth formula](../../../crates/threemind-core/src/retention.rs:212).

## Original states

Across eight independent R43 origins and two teaching histories, the pretest states contained 256 directed connections linking X0/X1 and the declared output ports in both directions. Their current half-lives were all 30 seconds and their current base weights ranged from 0.019613 to 0.029655. Every last_pass_us value was nonzero: these surviving connections had transmitted signals.

All 256 were absent after the original 72-second test. The per-trial survival series and original hashes are in source-audit-v1.json. R44 separately tests the behavioral consequences of preventing this loss.

## Curve shape versus retention scale

“Logarithmic decay” requires a specified function. Subtracting a logarithm eventually produces negative weights unless clipped; the mathematical comparison instead uses a positive inverse-logarithmic function. Except for the explicitly longer 300-second exponential, every candidate reaches half its initial value at 30 seconds.

With the 256 observed starting weights and a 0.008 threshold, and without subsequent reinforcement, interference or state dependence:

| Mathematical candidate | Fraction at 60 s | Fraction at 300 s | Median threshold-crossing time |
|---|---:|---:|---:|
| 30-second exponential | 0.2500 | 0.000977 | 49.71 s |
| 300-second exponential | 0.8706 | 0.5000 | 497.06 s |
| Power law, \((1+t/30)^{-1}\) | 0.3333 | 0.09091 | 64.60 s |
| Inverse log, \([1+\ln(1+t/(30/(e-1)))]^{-1}\) | 0.4016 | 0.25638 | 132.92 s |
| Two exponentials, 80% fast and 20% slow | 0.2969 | 0.10007 | 55.52 s |

The two-exponential example uses half-lives of 22.18894 and 300 seconds. The table's 300-second exponential has a constant half-life; actual R44 half-lives continue relaxing and growing under the original operator.

The calculation shows that **a long tail can extend retention, but a weak connection may cross the deletion threshold before that tail has much influence**. In this equal-half-value comparison, the inverse-logarithmic curve also falls faster initially. Retention of useful experience, removal of irrelevant connections and adaptation to changed relationships must be assessed together in behavior.

An additional analytic bound is useful. If half-life remains at 30 seconds without reinforcement, even the maximum initial weight of 1 reaches 0.008 after approximately 208.97 seconds. Increasing weight cannot substitute for growing retention indefinitely. Conversely, the same inverse-logarithmic candidate takes approximately 19.95 days to reach the threshold from weight 0.1 and \(1.24\times10^{55}\) seconds from weight 1. A few minutes gained for weak connections therefore do not justify adopting this formula globally. These are calculations under stated assumptions, not extremely long subject runs.

## The unresolved historical question

The 2026-10-08 `continuous-memory/3` repair report already identified insufficient default retention gain. After 120 seconds of repeated input, the largest connection half-life was approximately 40.33 seconds, and connections were absent after 300 seconds without reinforcement; the legacy-stability condition retained connections. Calibration gains of 2 and 4 improved structural persistence, but those gains had not been tested against prolonged background input and rule reversal, so defaults were preserved. [Historical report](../2026-10-08-retention-repair/report.en.md)

That was a structural experiment on a historical version. R44 tests behavior of complete `/5.1` systems. The two are reported separately: the old result establishes an unresolved retention-parameter problem, while R44 asks whether retention explains the current joint-judgment failure. The first candidate investigations should preserve the existing local-send basis of retention growth and compare growth magnitude with relaxation rate. Adding a new trigger for consolidation would require an explicit account of the changed local-mechanism hypothesis.

## Related work and candidate choices

Fusi, Drew and Abbott's cascade model combines states with different levels of plasticity to address the storage–retention tradeoff. It is a multistate memory mechanism, beyond replacing one decay curve. [Original paper, 2005](https://www.rctn.org/cadieu/pdf/FusiNeuron05.pdf)

Benna and Fusi developed interacting fast and slow variables and analyzed retention during continuing memory storage. This motivates multiscale candidates; the two-exponential arithmetic above does not implement their system. [Original paper, 2016](https://www.gatsby.ucl.ac.uk/~pel/tnlectures/papers/benna_fusi.pdf)

ThreeMind already has experience-dependent half-lives. The immediate question is whether its curriculum establishes sufficient retention and whether extending it improves behavior. If it does, the smallest candidate concerns which local uses grow retention, by how much and how quickly retention relaxes. A multiscale mechanism becomes relevant when a specific single-scale tradeoff is demonstrated. The completed behavioral study determines the next decision; this audit does not change production defaults.

## Candidate implementations must compose consistently over time

This is a numerical implementation check, without subjects or changes to behavioral criteria. Advancing 30 seconds without reinforcement in one step or in ten 3-second steps should yield the same weight.

Naively applying \(w\leftarrow w f(\Delta t)\), resetting decay age at every call, preserves the exponential result of approximately 0.5. It instead gives 0.38554 for the power law, 0.22951 for the inverse logarithm and 0.46886 for the mixed exponentials, although all three single-step values should be 0.5. Such an implementation would make maintenance or observation frequency affect the model.

Without new reinforcement, retaining age \(a\) and applying \(w\leftarrow w f(a+\Delta t)/f(a)\) preserves composition. The two-exponential candidate can also retain and update its fast and slow components separately. Numerical checks with 1, 2, 10 and 60 partitions pass. New learning requires an explicit rule for the ages of old and new increments; restarting a clock must not silently refresh all earlier experience. The current adaptive-half-life operator retains weight and half-life and has passed composition checks across its lower bound.

Original calculations are in candidate-consistency-v1.json, produced by [candidate_consistency.py](candidate_consistency.py). This establishes an implementation requirement, not a new behavioral result.
