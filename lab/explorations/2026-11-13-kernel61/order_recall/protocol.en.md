# R51n: retention and expression of event order in 6.1

13 November 2026. Preregistered protocol for E20 in comprehensive revalidation plan v2. E21 state exchange and E22 dose and phase controls remain separate batches. Registration and execution require completed R51l delivery without a campaign stop.

## Questions, expectations and decisions

After the same two events occur in opposite orders, can a common cue elicit different responses? Can this effect persist after activation of the task nodes has subsided? The study retains E20 materials and compares opposite teaching histories, cue versus no cue, event intervals and retention intervals. We expect order expression to persist in 6.1; slower decay may extend its retention.

The primary target is the historically stable bidirectional expression of order. With a shared reference, a 50-ms event interval and the default facilitation time constant of zero, all four material blocks must show opposite A/B net advantages for AB versus BA teaching, with absolute margins above 1e-6 after both 1 and 30 seconds. Net activity is the five-second activation integral following the cue minus the corresponding no-cue integral. Both histories must pass, and the direction must be consistent across the four blocks at each retention interval. Historically the later event prevailed. A reproducible primacy effect still meets the historical bidirectional-expression criterion and will be reported as a direction change. The 1e-9 sensitivity analysis cannot replace the primary criterion.

The second target tests expression after task activation has subsided at 30 seconds. Activation of A, B and X is read at the pre-cue time, alongside connection-weight differences. This target passes only if all task activations are at most 1e-12 and the primary expression target passes. Subsequent E21-style exchange will test the causal contribution of particular connections; this batch does not replace it.

Retention at 300 seconds is a prospective improvement target. Under the same shared-reference, 50-ms, default-facilitation condition, all four blocks must show bidirectional expression with absolute net margins above 1e-6 and a consistent direction across blocks. Recency and primacy are reported distinctly. A negative result on this extension completes normally. All 144 block comparisons across the 36 interval, retention, facilitation and reference conditions are disclosed. No window is selected from outcomes. The no-shared-reference condition tests whether previously untaught X elicits A/B activity; it is a cue-path control, not a dose-matched comparison.

A failed primary target is an adverse contradiction of established order expression. Evidence will be delivered before the campaign pauses for review. If expression persists but task activation remains at 30 seconds, the second target fails; that observation alone does not locate the state storing order, so the planned E21 state exchange will address the mechanism. Invalid originals or measurement are classified as apparatus failures. The transmission threshold will not be adjusted to obtain a passing result.

## Individuals, materials and continuity

The four anonymous material blocks retain seeds 100121–100124. Apparatus seed 100199 is separate. Each block combines facilitation constants 0/1 s, absent/shared reference, event intervals 0.05/0.5/2 s, and AB/BA order. These yield 96 continuously taught parents within four blocks, not 96 independent repetitions. The current 6.1 defaults are used, including inverse-logarithmic decay, deletion threshold 0.008 and transmission threshold 0.0004. Only the seed and declared facilitation constant differ.

Events are A/B without a reference and AX/BX with a reference. Element values are 1 and stimulus intensity is 0.4. Twelve event pairs are taught; the second event is followed by 0.5 s. After the final pair, an additional 0.2 s precedes the common last input Y=0.2. Independent K=0.2 maintains activity every 0.5 s. Total dose differs between reference conditions; E22 retains the separate dose-matched study.

Each intact teaching parent provides six registered diagnostic copies: independent waits of 1, 30 or 300 s, followed by X=0.5 or no cue. Earlier tests cannot rehearse later retention conditions. K continues through waiting and testing. Each copy receives one test and a complete five-second observation. There are 672 stages. Ordinary teaching is continuous, and diagnostic copies never overwrite the intact reference. This passive mechanism study uses a fixed temporal readout and requires no trainable peripheral.

## Timing and measurement

`spec.py` checks every historical input's code, intensity, scheduled time, enqueue time and order against preserved E20 originals. Teaching input is processed at the current clock before maintenance for the next interval is queued. Prequeuing the entire course would change same-time event ordering and is prohibited. Historical states are never loaded as 6.1; all teaching subjects are newly created.

Activation, inhibition, direct and associative activity of all nodes are sampled every 20 ms during the five-second probe. Complete states before and after teaching inputs, initial/final stage states, pre-cue states, input receipts and trajectories are saved. The external passive observer, queues, curriculum position and clock accompany saved state. This task has no body or trained adapter.

An independent apparatus compares identical input with no repeated observation, 20-ms observation, a different observation interval, save/restore, and a host pause. Observation, saving and host delays do not advance simulation. The read-only audit recomputes inputs, parent hashes, times, integrals, denominators and decisions without rerunning scientific individuals.

## Resources, stops and delivery

Scientific hosts run serially. A one-second guard retains 5/4/5/25 GiB of commit/RAM/C/E capacity, with a 1-GiB host-private limit. A parent and its six diagnostic copies form one complete unit; the limits are ten minutes per unit and two hours per batch. The 96 historical E20 units occupy 117,816,605 logical bytes and 129,859,328 allocated bytes; the largest unit occupies 1,421,352 allocated bytes. Each new unit is estimated at 1.5 times its historical allocated size, allowing additional complete-state files. Allocation reaching twice the historical unit, or exceeding the new estimate by 50%, triggers a complete-boundary review. Originals, archive and API readback each have a 1-GiB batch cap, plus 128 MiB for analysis and a 25-GiB disk reserve. Apparatus costs are checked before formal execution. A new orphan in-flight marker is preserved and reported.

Reports in both languages explain purpose, expectation, result, analysis, scientific conclusion and significance. Completion requires full API readback and pending=0. Coverage and history are updated. Production Core, defaults, historical evidence and the author manuscript are preserved.
