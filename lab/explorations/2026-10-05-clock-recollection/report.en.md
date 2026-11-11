# E51: clock readings and sentence forms work; recent events are not reliably recounted

2026-10-05. [Chinese](report.zh.md) · [Registration/correction](design.en.md) · [Results](results.json) · [Discussion](../../../docs/en/plans/clock-grounded-recollection.md)

**A perceptible clock is connected and the system produces now/just-now sentence forms, but the named recent object is often wrong. Different preceding experiences nevertheless leave different current activity, and plastic learning increases that influence.** Neither “no past information remains” nor “reliable experience retelling is achieved” describes these results.

## What ran

The populated four-object MuJoCo scene remains. An external pointer rotates every4simulated seconds; four directional photometers sample every250ms. Anonymous measured light levels enter Core, not temporal answer tags or object identities. The teacher names clock sectors and demonstrates current/past questions and answers. Original encoding is retained; this batch delivers language frames20ms apart.

Twelve ordered object pairs receive ten consecutive **complete scenario/question/answer demonstrations** each, then two increasingly spaced reviews:144episodes over652simulated seconds. This does not mean one isolated sentence was repeated consecutively without its scenario. A no-learning copy receives the identical course with only plasticity disabled; inhibition, forgetting and replayed physical telemetry remain enabled.

Probes briefly show two objects in sequence, then ask now or just-now without supplying the answer. Each object has five visual frames, total amount10, ordinary intensity1. The current object remains in the simulated world but is **not continuously sampled until response completion**. This is recounting after brief exposure, not a complete continuous visual conversation. The clock continues through the question/observation.

The external reader learns32experience observations and4clock examples. Four ordered pairs are excluded from reader calibration, although Core has seen all12demonstration types. This tests new observed sequences, not an entirely untaught logical rule. Input remains six local dynamic fields at17actual times; no static full-graph history, baseline subtraction or per-query scaling.

## Outcomes

| Test | Correct/count |
| --- | --- |
| Clock names at new angles within each sector |4/4|
| Learned-source now prefix |12/12|
| Learned-source just-now prefix |12/12|
| Learned-source current object/full answer |3/12|
| Learned-source previous object/full answer |2/12|
| Four reader-held-out orders, now/just-now |1/4,0/4|
| No-learning current full answers |6/12|
| No-learning past full answers/object name only |0/12,3/12|

Clock naming is a narrow perceptual-expression result, not proof that Core understands elapsed time. Correct temporal prefixes may rely on the question itself. Stationary, shifted and faster-clock controls each give1/4for either question; the baseline is already weak, so one extra correct answer cannot establish temporal improvement or clock irrelevance.

Example: after red sphere then blue box, the system answers “I see the red sphere now”; asked just-now, it answers “I just saw the green cylinder.” These are wrong referents, not merely imperfect wording. Tolerant object-only scoring does not repair the learned group's result.

## A positive internal result

A read-only audit holds the present object, question, clock and background equal while varying the preceding object:12paired comparisons, plus12in the no-learning copy. **All24actual17-frame reader inputs differ.** Differences are analysis measures, never subtracted from or supplied as expression inputs.

Maximum absolute local-field differences range **.000496–.005751** after learning, versus **.00000436–.000345** without learning. Within this source and these comparisons, every learned-case difference exceeds the no-learning range. **Plastic learning strengthens the preceding experience's influence on later activity; it does not yet yield correct language.** Amplitude is not semantic accuracy or a new consciousness criterion. Wider sources and long-term retention remain untested.

Dense trajectories also differ. Local selection retains every differing field entry in the learned comparisons; one example has133participating nodes out of136stored, so genuine participation can be widespread. Some no-learning differences are omitted, but all selected/sampled inputs still differ. Both audits are retained in the archive.

## Why expansion stopped

After2500steps, the reader fits only **12/36of its own teaching observations**, below the preregistered33-pass gate. The second source and longer periods were therefore not run. Its failures cannot establish that another faithful tool could not decode the remaining information, or that Core lacks time-related memory. No Core formula was changed and no auxiliary classifier was substituted for successful retelling.

Hours/yesterday have not yet been taught or tested. First locate why weaker experience differences are not reliably expressed alongside the strong question/clock context; separately test continuous vision versus brief exposure, then extend temporal references and language. Preserve raw outputs; do not restore baseline subtraction to manufacture answers. If expression improves, selective association silencing/rescue can locate the content source.

## Delivery

The Python clock tool has explicit origin/rate/phase/gain. Tests cover period/shift/rate, and4clock channels do not collide with20visual or63text channels. The first amount10single-frame probe was rejected before delivery; five amount2ordinary frames corrected the tool, preserving the failed directory and original teaching.

**114sources/probes,1research reader**, approximately **697s (11.6min)** cumulative simulation/training and **90MiB** pre-archive evidence, plus offline auditing. Shared account51%→52%. Final archive/database footprint is in `delivery.json`. Bilingual reports, original answers, inputs, states, checkpoints and failures are published separately; Core, defaults and previous evidence remain unchanged.
