# E49: expression can follow a changing mind, but the adapter must learn to keep up

> **Revision r2 · 2026-10-10**
> Revision reason: Verified original-file relocation; append location-resolution guidance and preserve the experiment conclusions.
> Original: [report.en.md](report.en.md); parent r1: [report.en.md](report.en.md)


2026-10-05. Completed. [中文](report.zh.md) · [Registration](design.en.md) · [Measured results](results.json) · [Tools](../../../docs/en/reference/bus-expression.md)

**We found a tractable obstacle: the small Transformer had not adequately learned its own calibration examples. Balanced training produced24/24 held-out-view names across three Core histories. After further Core teaching and adapter recalibration, two histories each scored4/4 on a new view and again60 simulated seconds later. Core equations, defaults and sensory mapping remained unchanged.**

**A frozen adapter still does not reliably express unseen correspondences.** This round establishes usable expression of a small taught vocabulary and an adapter that can follow changing activity. It does not establish independent relation transfer, compositional reasoning or natural conversation. It is not a bound on ThreeMind's possible capabilities and does not revoke earlier ocean intervention evidence.

## Scope and controls

Reuse E47/E48 evidence for sources223/251/279, four objects and four names. Core seeds and teaching order differ; input adapter/wiring seed is71 throughout. These are not arbitrary heterogeneous encodings. A2-second process is represented by17 samples,119 anonymous channels and presence, activation, inhibition, trace, support and stability. Values are absolute: no no-cue subtraction or per-example normalization.

The195,264-parameter Transformer starts without pretrained weights and generates text bytes. Supervised words are supplied only for fitting. Inference receives anonymous state, with no question, source identity, answer, artificial time labels or dialogue cache. Calibration uses views8/10 at intensity0.4/0.6; held-out view9 uses0.5.

Keep continuous-memory/2, ordinary teaching intensity1, inhibition, local depletion/recovery, forgetting, lifecycle and the existing extra strong-stimulus term. Replay previously measured physical telemetry so observation load cannot change the input tape. No-cue means no current object cue, not absence of environmental input.

Every additional branch was registered first: [coverage/correction](followup-registration.en.md), [Core re-teaching](reteaching-registration.en.md), [alternating calibration](joint-registration.en.md), [shared adapter](shared-registration.en.md). Cycle1 becomes explicitly taught in correction/joint models; its original unseen scores remain intact. Cycle2 remains held out.

## Buses and information loss

Representative direct-injection and default InputBus cases have identical queues, final states and trajectories. Observer labels do not enter Core. Explicit admission policies may still apply their declared rules; this is not a claim that every configured input filter is transparent.

Eight actual probes,101frames each, match between direct observation and OutputBus. The older language `ProcessFeatures`, however, keeps positive activation, hashes channels together and pools time bins. Controlled changes to inhibition or order within a bin can disappear entirely from its feature vector. That is observer compression, not bus packet loss.

E48 already read raw state directly, so this legacy loss cannot explain all E48 underfitting. The new `RawActivityStream` transports copied observed-node frames without rank selection or semantic labels. It does not advance Core and is not a complete connection-snapshot protocol. Expression projection still declares fields and sampling; full101-frame recordings are retained. Activity below20ms resolution was not observed. See [audit](audit.json).

## A measured improvement in external training

The previous loop sampled with replacement. The new small-data recipe uses every teaching example at each update. Inputs, architecture, learning rate and loss are unchanged. Checkpoint selection uses training accuracy and loss only.

| Source/method | Fit | Taught original/reversed mapping, new view | Same mappings60s later |
|---|---:|---:|---:|
|223, random replacement,2500steps|12/16|6/8|Full receipt retained|
|223, balanced full batch,2500steps|16/16|8/8|1/8|
|251, balanced,1500steps|16/16|8/8|7/8|
|279, balanced,1500steps|16/16|8/8|4/8|

The latter sources confirm the chosen recipe; their held-out answers were not used for selection. The three individual adapters total24/24 at the calibrated time. An MLP diagnostic fit only9/16; unused learning-rate/initialization candidates were not pursued once calibration succeeded.

The useful result is specific: the same physical object can yield the name associated with its taught Core history, including reversed teaching, on a held-out view. It is not general language competence, and by itself does not identify which memory mechanism carries that distinction.

## A later decoding failure is not automatically forgotten memory

For223, an adapter fitted at532s scores1/8 at592s. Without changing the saved Core or its trajectory, fitting only the592s calibration views restores8/8 on held-out views. Covering48examples across normal266/326s and continued/reversed532/592s gives24/24 across the six held-out groups.

Late states therefore retain usable distinctions. This does not establish complete preservation of every original memory or prove that a particular connection stores it. It does invalidate inferring total forgetting from this frozen reader's errors. Latest-only calibration also has a cost: the592s adapter scores only2/8 back at532s. Broader state coverage matters.

We did not reduce forgetting merely to compensate for reader drift. A later parameter study should require independently reliable observation of excessively rapid loss.

## Correction: distinguish teaching Core from teaching the adapter

First add cycle1 calibration views to the adapter's training. Source223 rises from1/4 to4/4 on its new view, both with continued weights and cold training;279 reaches3/4 with continued calibration. Unseen cycle2 remains poor. This is adapter learning with supplied targets, not independent Core relation inference.

Next actually teach Core: clone each source's592s cycle1 state into background-only waiting,48balanced reviews, and48reviews of mistaken items. Use ordinary intensity1, original images/short sentences and denser early/later sparser reviews. The teacher selects lessons, but no error flag enters Core and no connection is directly edited. Freeze the expression adapter.

| Source/treatment |650s|710s|
|---|---:|---:|
|223, wait|1/4|1/4|
|223, balanced review|3/4|3/4|
|223, targeted review|3/4|2/4|
|279, wait|2/4|4/4|
|279, balanced review|0/4|0/4|
|279, targeted review|0/4|0/4|

One source improves through teaching Core alone; the other cannot be read correctly with that frozen adapter. Report both. The0/4 does not establish erased memory. [All re-teaching outputs](reteaching-results.json) include errors, no-cue words and lifecycle status. These are two histories, not population statistics.

Finally calibrate after experience changes. Select the two balanced-review branches, collect8new calibration-view examples at710s, combine with24previous examples, and retain the existing710s test view. Advance identical background to770s without fitting that time.

|Source|Frozen reader at710s|Continued calibration:710/770s|Cold fit, same data:710/770s|
|---|---:|---:|---:|
|223|3/4|4/4,4/4|4/4,4/4|
|279|0/4|4/4,4/4|4/4,4/4|

All four adapters fit32/32 and retain8/8 for old original/reversed532s and4/4 cycle1. Some uncovered old times still fail. Continued training stops at1000steps versus1500cold, but already incurred earlier training cost.

This is a concrete gain for **Core teaching followed by language-adapter learning**. It accommodates correction rather than demanding flawless first responses. It remains supervised alternating calibration, not unsupervised coevolution.

## Sharing an adapter

One adapter trained on32original/reversed examples from223/251, without source identity, scores16/16 on their held-out views and **8/8 on279, never used for adapter fitting**. Each source scores6/8 at the late time; cycle1 scores1/4,2/4,2/4; cycle2 is0/4 throughout.

Thus a completely separate adapter per mind is not currently a demonstrated necessity. A shared basis followed by experience-specific calibration is a useful candidate. Different wiring, larger populations and sentences remain untested.

## Have earlier gains been lost?

[Effective-config audit](effective-mechanisms.json) restores omitted serialized fields through the actual configuration class. It covers mechanisms and recent parameter gains relevant to this language line, not every historical hypothesis.

|Mechanism|Current default and actual experiment|Decision|
|---|---|---|
|Local depletion/recovery, edge consolidation, plasticity|Enabled; recovery0.8s|Retain|
|Continuous fast connections and local competition|`fast_enabled` and `context_enabled` true|Retain; distinguish frame-input competition|
|Local novelty|arrival-window, gain0.018, reference0.2|Already default|
|Extra strong-input consolidation|Coefficient0.075; normal preset1, strong4|Keep previous decision; ordinary teaching uses1|
|Inhibition, forgetting, propagation consolidation|Enabled; learning0.055, associative0.01, forgetting0.025|Retain|
|Extra facilitation1s|Research preset exists; normal0|Do not universally enable: E45 scored6/32 against default7/32|
|Frame competition/global clamp|Default off; different from local competition|No blanket enabling|
|Raw activation/inhibition/process|Actually used, absolute values retained|Continue through raw output interface|
|Balanced training and state coverage|Positive E49 controls|Balanced is default for the new CLI; coverage/alternating calibration documented|

E45 doubled learning and faster recovery each scored5/32; stronger inhibition7/32 with a worse auxiliary measure. Its historical scoring differs, so do not subtract those numbers from E49. [Original report](../2026-10-05-language-calibration/report.en.md) remains intact. Conditional results do not imply these mechanisms are useless elsewhere.

No missing established general Core gain was found in this audited scope, and no new controlled result warrants changing Core defaults. Positive **tool** gains are implemented rather than mislabelled as Core upgrades. Historical kernels, instances and evidence retain their identities.

## Explicit conclusions and next decisions

|Goal|Conclusion|
|---|---|
|Express a few taught name/object mappings|Achieved for tested new views and covered states, as actual text bytes|
|Correct errors through additional teaching|Conditionally achieved: one source with frozen adapter; both after recalibration|
|One adapter must belong exclusively to one mind|Not necessary in this tested common-wiring setting|
|Frozen adapter expresses unseen correspondences reliably|Not yet achieved; registered transfer gate unmet|
|Compositional reasoning or natural conversation|Not established; complex course not started, not a completed negative test|
|No-cue words are trustworthy inner speech|Not established; all original words retained, but a four-word decoder can itself be biased|

Next candidates are a shared expression basis with continuing individual calibration, a small online teaching/correction loop, and only then sentence/relation work with matched pathway interventions. The remaining issue is stable expression of new correspondences across changing internal states; no single necessary Core-equation change has been localized.

## Delivery and resources

Added read-only raw output, balanced/continued calibration API/CLI, real CPU decoding and existing GPU fallback selection. Inference rejects teaching targets. Newly bound checkpoints check exact channel/field layout. Old production chat models/protocols are not silently replaced. Research tools are callable through Python/CLI, and existing report/evidence pages expose the study; the experimental decoder is not installed as every mind's mouth.

102new source/branch/probe cases,14Transformer models and1MLP diagnostic. Recorded compute has a conservative upper sum526s, including small overlapping audit time. Work before archive is about144MiB. The256-case/24-training/3-hour budget was not exhausted. Shared usage was48→49% when new simulation stopped; final publication storage and usage are in `publication-resources.json`. No previous data was deleted and no paid model was called.

Acceptance covers representative bus trajectories, raw projection/stream tests, a real saved model decoded on CPU through the CLI, rejection of inference labels and wrong channel ordering. [CLI receipt](verification.json). No repeated full-database hash scans. Bilingual notes, reports, original-output viewer and archive belong to **E49 总线与表达器校准**, project `2bbb612d-ed99-4021-8886-c250e33727f7`. New states, inputs, processes, models and failures are retained; E47/E48 dependencies are referenced read-only.


> **Storage-location revision · 2026-10-10**
> This edition adds the verified move of the selected originals to `E:\ThreeMindData`. Stable scientific identities and hashes, experiment dates, measurements and conclusions remain unchanged. Paths in the preserved body describe historical sources; use the registered evidence resolver for current locations. Repository documents and frozen fixtures remain in place, and source copies are retained. Structured query data and running checkpoints remain in the database. This annotation does not assert that missing historical evidence was recovered.
