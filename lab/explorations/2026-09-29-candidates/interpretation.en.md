# Supplementary interpretation: what improved and what to investigate next

[中文](interpretation.zh.md) · [Original report](report.en.md) · [Protocol and reproduction materials](README.md)

This independent supplement organizes the discussion following the multi-kernel study completed on 2026-09-29. The original reports, evidence, protocol and kernels remain unchanged. No additional training results are introduced. Observations and research judgments are distinguished below.

## Overall assessment

**Basic associative memory has produced clear effects. The continuous candidate shows a promising response distinction that changes with prior experience. Prioritize continuous/1, retain causal/9 as an important research baseline, and reduce investment in the current LIF parameter/curriculum combination.**

Two concrete questions deserve attention before simply increasing training volume:

1. What local state preserves the continuous candidate's sequence-related distinction, and why does that distinction fade before a stable output remains?
2. How can separate, successive experiences naturally establish connections when they are not presented together?

The study uses anonymous symbols. A, B, C and familiar name/object pairings are reading aids, not evidence of natural-language understanding.

## 1. Experience left associations that a later cue could activate

Imagine four anonymous pairs as four name/object associations. After repeated joint stimulation, presenting one member made its partner more active than the other possible partners.

**Observed:**

- Both the baseline and continuous candidate showed matched-target activation advantages.
- Untrained controls and controls with plasticity disabled from birth did not show the same advantage.
- In the fixed condition with recorded host background and a one-second retention interval, 8 of 24 baseline probes produced qualifying converged readouts. The matched target led in all eight. The other sixteen did not produce qualifying stable readouts.
- In the same condition, all 24 continuous-candidate probes produced a matched-target peak advantage, but none produced a qualifying converged endpoint.

**Judgment:** the basic chain—experience changes structure, and a later cue evokes the associated response—is working. Describing these results simply as “ThreeMind did not remember” loses meaningful evidence. The more precise problem is that **an association forms, but does not reliably become a stable final output.**

A target lead compares the preregistered alternatives, not every node in the entire network. A peak captures a distinction during activity; a converged endpoint captures a distinction that survives to the reader's endpoint. Both are informative, for different purposes.

## 2. The continuous candidate's sequence discrimination is the strongest new lead

Teach:

```text
A → B → C
D → B → E
```

The successful teaching condition overlaps adjacent items: `A`, then `A+B`, then `B+C`, and likewise for the other sequence. Probes present `A→B` or `D→B` without the ending.

**Observed:** the continuous candidate favored C in peak activation after `A→B`, and E after `D→B`. Swapping teaching to `A→B→E, D→B→C` also swapped the favored endings.

|Condition|Continuous: matched-ending peak leads|Baseline: matched-ending peak leads|
|---|---:|---:|
|No background, original teaching|12/12|6/12|
|No background, swapped teaching|12/12|6/12|
|Background, original teaching|12/12|5/12|
|Background, swapped teaching|12/12|5/12|

**Judgment: this is the most valuable new lead in this round.** The continuous candidate retained an experience-dependent distinction that affected subsequent responses. It was not merely always preferring C or always preferring the last-taught ending. In these conditions, the distinction appeared more consistently than in the baseline.

Its magnitude is still small, and it fades during subsequent activity. The measurement covers the complete probe window; contributions before and after B arrives have not been separated. The new mechanisms were not individually disabled in this sequence task. What is established is that **changing the probe sequence and teaching relationship changes the activation preference**. Whether fast traces, short-term resources, local context or their interaction carries that distinction is the next question.

“No converged endpoint” should not bury this observation. It merits a focused experiment following the response through time.

## 3. Short-term synaptic resources have a large, demonstrable effect

In plain terms, transmission temporarily consumes available resources, which recover during rest.

**Observed:** without background, total continuous-candidate transmission during the twentieth repetition was:

|Setting|Transmission during repetition 20|
|---|---:|
|Short-term resources disabled|Approximately 2.14|
|Short-term resources enabled|Approximately 0.075|

That is a difference of roughly 28-fold. With resources enabled, an additional 0.1 s rest after repetition produced about 0.078 on the next stimulus; an additional 1 s produced about 0.169.

**Judgment:** repeated use and subsequent rest genuinely alter transmission in the implemented dynamics. This comes from local rules, not an external decision that a connection ought to become fatigued. The added mechanism has clear functional evidence and is worth retaining.

It can restrain amplification from repeated transmission, but may also suppress useful weak associations. Investigate release fraction and recovery speed together with learning; neither weaker nor stronger transmission is automatically preferable.

## 4. Relearning and separating conflicting experiences remain difficult

After learning the original pairs, additional training introduced different pairings:

- The baseline often activated several alternatives together without a clear winner.
- The continuous candidate continued favoring the original pair rather than clearly adopting the new pair.
- Baseline trained-pair weights reached their upper limit; continuous weights usually remained around 0.58–0.60.

**Judgment:** memories form, but competition and selection between old and new experience are not yet satisfactory. The baseline shows signs of excessive strengthening followed by interference. The continuous candidate retains old associations, but this round did not demonstrate flexible relearning.

Original pairs received 35 repetitions each; new pairs received only ten additional repetitions. This does not establish that the continuous candidate can never relearn or isolate one mechanism as the cause. The useful question is how local state can distinguish contexts after one cue has acquired several associations, rather than always activating all of them together.

More repetitions alone may not solve this. Equalize old/new exposure in a follow-up and inspect competition, retained connections and short-term state, rather than simply increasing forgetting or deleting connections according to a human answer key.

## 5. Pure sequential input did not form connections: inspect edge-growth conditions first

With A, B and C presented separately at one-second intervals, none of the three kernels formed task-symbol connections.

**Code finding:** baseline and continuous kernels default to growth from joint input; current LIF growth also relies on joint external contacts. A followed one second later by B does not automatically meet these conditions. Baseline and continuous already support an optional temporal-association growth policy, which this study did not enable. Its default half-second window is also shorter than the one-second input interval.

**Judgment:** this first exposes an unmet condition for connecting successive experiences, not a refutation of logical ability. When pathways never form, repeating the same material, increasing model size or buying a faster machine cannot substitute for examining the growth rule.

The design and explanation had a weakness: compatibility between default growth and isolated sequential input was not adequately checked first. This concrete explanation belongs alongside the original report, rather than leaving only the impression that sequence ability was absent.

An initial follow-up can use existing optional parameters: enable temporal-association growth, align its window with input spacing and actual activation persistence, and observe whether connections form naturally. Growth still depends on activity and other conditions; a longer window does not guarantee learning, and A→B connections must not be inserted manually.

## 6. Pause the current LIF combination; keep the temporal-accumulation lead

LIF membrane and learning traces primarily evolve over tens of milliseconds. Under one-second input spacing, relevant short-term state may disappear before the next stimulus.

**Observed:**

- Five intensity-0.5 stimuli at 10 ms spacing produced spike increments `[0,0,2,0,2]`; 100 ms and 1 s spacing produced zeros.
- Synchronous paired training left paired-edge weights at zero.
- In the two-node repetition test, independently disabling short-term resources or the adaptation current still left twentieth-pulse transmission at zero. These ablations did not run the same four-pair curriculum, so they cannot establish that disabling either mechanism failed to restore pairing. This corrects the preceding conversational interpretation, which conflated the two tests.

**Judgment:** the combination of default LIF parameters, one-second spacing and isolated half-intensity cues does not justify further repetition. It has both weak probe observability and failure to retain usable paired weights.

The next opportunity for LIF should use millisecond-scale, offset stimuli and directly inspect spike times and weight changes. Biological resemblance alone should not give it higher priority; this mismatched timing condition also cannot reject the entire spiking-model direction.

## 7. Investment priorities

|Direction|Finding in this round|Recommendation|
|---|---|---|
|continuous/1 as a whole|Paired discrimination and sequence-related preferences that follow swapped teaching|Highest priority for focused investigation|
|causal/9|Clear associations and some stable paired outputs; interference between relations|Retain; examine interference and excessive strengthening|
|Short-term resources|Large transmission changes and recovery after rest|Retain; study release and recovery parameters|
|Fast traces|Small contribution with defaults in simple repetition; twentieth-pulse emission changes about 0.46%|Avoid large investment before testing their role in sequence discrimination|
|Local context/attention|No difference in the two-node test, which lacks competing inputs|Test genuine competition; neither reject it nor credit it prematurely|
|Current LIF parameters/curriculum|No retained useful pair weights and mismatched cue timing|Pause larger training; perform a small timing diagnosis first|
|Scale and training volume alone|Cannot resolve the observed growth and timing barriers|Low priority now|

Positive results for the whole continuous candidate do not prove that all three added operators helped. Fast traces and local context deserve targeted tests, with larger investment following evidence of contribution.

## 8. What background stimulation and the local Transformer add

**Background stimulation:** it changed survival and readout conditions, but no edges connected background and task nodes in this study. The idea of background activity sustaining the task network was therefore not fully realized through these connections. This does not make background useless; investigate how sensory mapping and naturally formed connections bring it into contact with task activity. Enabling telemetry is not equivalent to supplying every node with energy.

**Local Transformer:** roughly 26,000 parameters were sufficient to discriminate rehearsed contexts on CPU. It is already useful as an inexpensive external comparison tool, without cloud deployment for tasks of this size. Its results belong to that tool; no probabilities were fed back into ThreeMind in this study, so integration benefits have not yet been demonstrated.

## Recommended next work

**If only one question can be pursued, trace the continuous candidate's sequence distinction: what preserves the earlier influence, and why does that distinction appear during activity but fail to remain as stable output?**

Proceed under fresh protocols, preserving the existing evidence:

1. Follow `A→B` and `D→B` over time, separating the prefix, post-B and decay periods. Add B-only and no-cue controls.
2. Individually disable short-term resources, fast traces and local context in that same sequence task. The earlier two-node repetition test cannot substitute for this.
3. Compare joint-input growth with the existing temporal-association option, explicitly relating input spacing, association window and activation duration.
4. Use a small, exposure-controlled old/new pairing experiment to examine retention and relearning together.
5. If resources permit, give LIF an offset-input experiment at its millisecond time scale.

These are recommendations, not newly executed experiments. Priorities follow observed structural change, plastic responses and dynamic distinctions, rather than treating immediate human-language answers as the only valuable outcome.

## Evidence pointers

- [Original report](report.en.md): all condition tables and structural checks.
- `summary.json`: grouped outcomes, target margins and per-block contrasts; `block-0.json` through `block-5.json`: individual measurements.
- `cases/.../events.jsonl.gz` and `observations.jsonl.gz`: recorded activity; `closure.json`: the 144-parent structural audit.
- [Analysis](analyze.py), [orchestration](run.py), [growth implementation](../../../src/threemind_core/restoration.py) and [LIF implementation](../../../src/threemind_kernels/lif.py): metric and mechanism definitions.
- Project: `cb3a2d4a-f8a2-440e-9182-75148e9454a8`. Original Chinese report: `dba0310d-848c-5f79-9b89-84597d9a4756`; original English report: `ebd9c65e-65f1-592e-a8b2-29d0e78e7e67`. Original revisions are retained.

This independently authored supplement postdates the frozen evidence archive and is not inside that earlier ZIP.
