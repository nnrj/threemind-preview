# R46a: effects of six decay settings on retention, reinstatement and forgetting

First scientific report. The prospective protocol was frozen on 9 November 2026; this report is generated after full computation and independent verification. [中文](report.zh.md) · [Prospective protocol](assay_protocol.en.md)

## Scientific conclusion

**None of the six settings jointly met the preregistered retention, expression and forgetting requirements.** No tested candidate met all three requirements. The component successes and failures below follow the prospective criteria.

- Exponential / on: passed finite fading; failed selective structural retention, history-dependent temporal reinstatement.
- Exponential / off: passed finite fading; failed selective structural retention, history-dependent temporal reinstatement.
- Inverse-logarithmic / on: passed history-dependent temporal reinstatement; failed selective structural retention, finite fading.
- Inverse-logarithmic / off: passed history-dependent temporal reinstatement; failed selective structural retention, finite fading.
- Power-law / on: passed finite fading; failed selective structural retention, history-dependent temporal reinstatement.
- Power-law / off: passed finite fading; failed selective structural retention, history-dependent temporal reinstatement.

## Purpose, expectation and actual design

The author requested exponential, logarithmic and power-law decay crossed with relaxation on/off, seeking retention after strong or repeated exposure, forgetting of weak exposure and eventual fading without further review. R45 found that disabling relaxation alone did not improve the previous joint task and that natural half-life growth was small. R46a therefore directly compares the decay curves through local connections and their cue-driven responses.

All six settings use genuine 5.2 with the reference backend. Logarithmic means the specified inverse-logarithmic function; the power exponent is one. A single new contribution reaches one half at the same fixed timescale in all curves. Enabled relaxation retains the original linear rule. Formulas, settings, doses, measurements and thresholds were frozen before execution. Historical 5.1, the installed native module and global defaults remain unchanged.

Eight independent birth origins receive five courses: single weak (0.12), ordinary (0.4), higher dose (1.0), and eight massed or progressively spaced presentations at 0.4. Repeated courses match total dose, final presentation and course end. Opposite teaching histories, separate 1/300-second first-test cohorts and cue-present/omission controls yield 1,920 sequences continuously developed from birth. Nested conditions do not increase independent N. Courses end at internal second 128; the aggregate advance is 536,640 internal seconds.

Fixed stimulus adapters and a fixed temporal instrument are used, with no trained output head. Each one-second window preserves 20 frames of activation, inhibition, direct and associative activity. The post-cue process is differenced against the preceding background window, then against a same-age, same-history omission control, and finally between opposite histories. This isolates the history-dependent cue effect. Paired cue conditions have identical pre-cue Core, measurement and background-window hashes.

## Prospective targets and results

Review of the actual stimulus fields during execution found three channel amplitudes (0.12, 0.4 and 1.0), while `Stimulus.intensity` remained at its default 1.0 throughout. The dedicated strong-stimulus term, requiring overall intensity above 1.0, was not engaged. The registered `strong` course is therefore described by its actual operation: “higher dose 1.0.” Original numeric criteria and scores are retained. This batch completes the higher-dose/repetition curve comparison; retention attributable to the dedicated strong-stimulus mechanism requires the additional control. The design omission was recorded before full-batch outcomes were generated: [stimulus-field correction](stimulus-scope-correction.en.md).

Structural selection requires both original target connections after higher-dose and spaced exposure to survive 300 seconds and weak-exposure connections to disappear. Each component requires at least six of eight origins to meet it in both histories. Temporal reinstatement requires the 300-second history difference to have RMS above 1e-4, retain at least one tenth of the one-second RMS, and have cosine similarity at least 0.8; higher-dose and spaced courses each require six of eight origins. Finite fading projects teaching-end state for 30 internal days under no further reinforcement or structural damage, requiring weights below the deletion threshold. This is a conditional analytic prediction.

|Setting|Higher dose retained|Spaced retained|Weak forgotten|Higher dose process|Spaced process|Finite fading: higher/spaced|All targets|
|---|---|---|---|---|---|---|---|
|Exponential / on|0/8|0/8|8/8|0/8|0/8|8/8; 8/8|Fail|
|Exponential / off|0/8|0/8|8/8|0/8|0/8|8/8; 8/8|Fail|
|Inverse-logarithmic / on|8/8|8/8|0/8|8/8|8/8|0/8; 8/8|Fail|
|Inverse-logarithmic / off|8/8|8/8|0/8|8/8|8/8|0/8; 8/8|Fail|
|Power-law / on|8/8|0/8|8/8|8/8|0/8|8/8; 8/8|Fail|
|Power-law / off|8/8|0/8|8/8|8/8|0/8|8/8; 8/8|Fail|

Every denominator is eight independent origins, with six-of-eight thresholds. Finite-fading entries are higher-dose/spaced, respectively. Overall success requires structural selection, temporal reinstatement and finite fading together. Connections never formed are reported separately and are not counted as forgotten.

## Mechanistic interpretation of the results

**The experiment rejects the explanation that disabling timescale relaxation alone is sufficient to preserve this repeated teaching.** Turning relaxation on or off produced identical component verdicts within each curve. All 384 target connections after the two repeated courses had a teaching-end timescale of 30 seconds and a last successful associative-send time of zero, although repeated co-stimulation had updated connections. In the current implementation, a connection's timescale grows only after successful associative transmission with the corresponding learning switches enabled. These courses increased connection weights without engaging the condition that extends retention time. Disabling relaxation therefore had no extended timescale to preserve. A single higher-dose exposure did trigger transmission, but the largest timescale with relaxation disabled was only 30.0115 seconds. Saved state and the existing update rule jointly support this explanation.

**Changing the decay curve changes which experiences persist, with distinct benefits and costs.** Exponential settings lost all five courses' target connections by 300 seconds. Inverse-logarithmic settings retained all five courses' connections and history-dependent processes. They solved the tested repeated courses' 300-second retention but failed selective forgetting of weak exposure: weak connections still weighed about 0.009217, above the 0.008 deletion threshold. Their higher-dose connections also remained slightly above the prospective threshold in the conditional 30-day forecast, at about 0.008369. Power-law settings retained higher-dose experience, forgot weak experience and passed finite fading, but lost both repeated courses' original target connections by 300 seconds. Thus inverse-logarithmic decay wins the tested repeated-experience retention comparison; power-law decay provides a benefit in distinguishing higher from weak dose. No setting wins across all registered requirements.

Node and connection survival distinguish two observed cases. Every missing target connection under exponential decay lacked at least one endpoint at 300 seconds. Under power-law decay, both repeated courses retained the two endpoints while losing the original connection. The latter directly establishes loss of the tested repeated-experience connection while its nodes remain. The former records endpoint status at 300 seconds; deletion order requires separate event evidence.

**Every detectable history effect at 300 seconds is expressed through inhibition.** Field-wise decomposition gives zero history difference in activation, direct activation and associative activation. Nonzero differences occur in inhibition, with field RMS about 0.018450 and combined four-field RMS about 0.009225. Inhibition was part of the prospective primary measure, so the corresponding temporal-retention passes stand in full. Retained experience can therefore be expressed by inhibiting subsequent activity; measuring positive activation alone would miss the retained history effect in this assay.

Equal-dose spaced teaching did not improve 300-second connection weight over massed teaching. Under inverse-logarithmic decay, mean weights were about 0.019121 for spaced and 0.020502 for massed teaching, a difference of -0.001381. Both courses lost their target connections by this delay under the other curves. This answers the comparison of the fixed schedules used here; altered intervals or doses require a new course.

These explanations use the complete results and the prospectively specified field decomposition. Checking the transmission rule in source is retrospective mechanistic interpretation. Primary measures and verdicts are preserved.


The assay fixes courses and initial parameters and disables energy consumption. In all 240 condition cells, the eight birth seeds remapped anonymous channel identities but produced exactly identical numeric outcomes. The original eight-origin denominator is retained to describe these repetitions. Point-valued bootstrap intervals describe repeatability under the fixed condition. Generalization across doses, timings or environments is assessed by experiments that actually vary those conditions.

## Retention quantities and spacing

|Setting|Course|Histories with both edges|Original edges at 300 s|Median taught H (s)|Mean taught weight|Mean late weight|
|---|---|---|---|---|---|---|
|Exponential / on|Single weak|16/16|0/32|30|0.035158|0|
|Exponential / on|Single ordinary|16/16|0/32|30|0.0488541|0|
|Exponential / on|Higher dose 1.0|16/16|0/32|30|0.105555|0|
|Exponential / on|Massed repetition|16/16|0/32|30|0.0691853|0|
|Exponential / on|Spaced repetition|16/16|0/32|30|0.0424714|0|
|Exponential / off|Single weak|16/16|0/32|30|0.035158|0|
|Exponential / off|Single ordinary|16/16|0/32|30|0.0488541|0|
|Exponential / off|Higher dose 1.0|16/16|0/32|30.0115|0.105556|0|
|Exponential / off|Massed repetition|16/16|0/32|30|0.0691853|0|
|Exponential / off|Spaced repetition|16/16|0/32|30|0.0424714|0|
|Inverse-logarithmic / on|Single weak|16/16|32/32|30|0.0340816|0.00921702|
|Inverse-logarithmic / on|Single ordinary|16/16|32/32|30|0.0473583|0.0128076|
|Inverse-logarithmic / on|Higher dose 1.0|16/16|32/32|30|0.102323|0.027672|
|Inverse-logarithmic / on|Massed repetition|16/16|32/32|30|0.0617305|0.0205018|
|Inverse-logarithmic / on|Spaced repetition|16/16|32/32|30|0.0298043|0.0191212|
|Inverse-logarithmic / off|Single weak|16/16|32/32|30|0.0340816|0.00921702|
|Inverse-logarithmic / off|Single ordinary|16/16|32/32|30|0.0473583|0.0128076|
|Inverse-logarithmic / off|Higher dose 1.0|16/16|32/32|30.0115|0.102325|0.0276745|
|Inverse-logarithmic / off|Massed repetition|16/16|32/32|30|0.0617305|0.0205018|
|Inverse-logarithmic / off|Spaced repetition|16/16|32/32|30|0.0298043|0.0191212|
|Power-law / on|Single weak|16/16|0/32|30|0.0348191|0|
|Power-law / on|Single ordinary|16/16|0/32|30|0.0483832|0|
|Power-law / on|Higher dose 1.0|16/16|32/32|30|0.104538|0.00979047|
|Power-law / on|Massed repetition|16/16|0/32|30|0.0663046|0|
|Power-law / on|Spaced repetition|16/16|0/32|30|0.0212293|0|
|Power-law / off|Single weak|16/16|0/32|30|0.0348191|0|
|Power-law / off|Single ordinary|16/16|0/32|30|0.0483832|0|
|Power-law / off|Higher dose 1.0|16/16|32/32|30.0115|0.104539|0.00979387|
|Power-law / off|Massed repetition|16/16|0/32|30|0.0663046|0|
|Power-law / off|Spaced repetition|16/16|0/32|30|0.0212293|0|

Each row includes two histories per origin. Mean late weight uses 32 original target connections, counting absent connections as zero; it is a structural measurement, not answer accuracy. H denotes the teaching-end decay timescale.

|Setting|Spaced minus massed: mean late weight|Origin-bootstrap 95% interval|
|---|---|---|
|Exponential / on|0|[0, 0]|
|Exponential / off|0|[0, 0]|
|Inverse-logarithmic / on|-0.00138064|[-0.00138064, -0.00138064]|
|Inverse-logarithmic / off|-0.00138064|[-0.00138064, -0.00138064]|
|Power-law / on|0|[0, 0]|
|Power-law / off|0|[0, 0]|

Spaced and massed teaching match presentation count and per-channel dose. The table reports the observed spaced-minus-massed direction without assuming a spacing benefit.

## Meaning for ThreeMind and subsequent choice

The experiment establishes that the decay curve determines the observed retention–forgetting tradeoff, while disabling timescale relaxation does not solve retention of the repeated courses. The immediate research direction is to identify why weight increases from co-stimulation fail to become sufficiently durable retention, while distinguishing connection persistence from expression through inhibition. Component benefits do not change global defaults.

The next approved step is the matched comparison of the dedicated strong-stimulus and connection-novelty terms, using eight genuinely different input conditions to test whether immediate enhancement becomes a 300-second structural and activity benefit. The complete personal temporal Transformer joint task remains the next-layer objective, with existing courses and individuals preserved. A new retention update rule requires a separately stated candidate and authorization.

## Cost, integrity and delivery

|Setting|Implementation|Sequences|Mean operation s/sequence|Maximum boundary private GiB|
|---|---|---|---|---|
|Exponential / on|original-frozen|40|0.201|1.376|
|Exponential / on|exact-acceleration-v2|280|0.206|1.483|
|Exponential / off|original-frozen|40|0.203|1.378|
|Exponential / off|exact-acceleration-v2|280|0.209|1.486|
|Inverse-logarithmic / on|original-frozen|40|8.867|1.385|
|Inverse-logarithmic / on|exact-acceleration-v2|280|6.523|1.499|
|Inverse-logarithmic / off|original-frozen|40|8.932|1.392|
|Inverse-logarithmic / off|exact-acceleration-v2|280|6.534|1.505|
|Power-law / on|original-frozen|15|89.050|1.408|
|Power-law / on|exact-acceleration-v2|305|11.381|1.505|
|Power-law / off|exact-acceleration-v2|320|11.376|1.511|

Mean per-sequence operation time sums teaching and probe receipts, including simulation, state capture and original writing, while excluding preceding directory-budget checks and outer control overhead. The first 175 sequences used the original implementation; the remaining 1,745 used a separately frozen exact-acceleration tool. The strata differ in origin and course composition and describe actual costs. Five isolated long-probe copies exactly matched original raw windows and complete states; two power-law probes fell from about 154–156 seconds to 18 seconds. The tool preserves operations, formulas and every contribution; production Core source is unchanged. Total scientific-host wall time was 18,306.49 seconds, including 2,288.56 seconds before the complete pause. After complete boundary 1,751, directory-budget accounting was replaced by an equivalent implementation after twelve engineering checks and byte comparisons on four immutable directories. The prior 10,136.22 seconds remain included. Sequence 876 resumed its 128-second taught state without reteaching. [Directory-accounting addendum](scan-addendum.en.md). Engineering validation time is separately recorded. Peak private memory was 1.511 GiB. Minimum commit/RAM/C/E headroom was 9.188/10.230/19.759/98.650 GiB; reserves remained 5/4/5/25 GiB. [Operational addendum](operations-addendum.en.md)

All 3,840 boundary hashes, continuous times, identities and mappings passed verification. The independent audit reads JSON and directly implements the formulas without loading subjects. Its frozen revision had a final counter overwritten by a condition dictionary. The original and failure log are retained; revision 2 only corrects that variable and records its own provenance, then passes complete-data verification. Scientific inputs, scores and criteria are unchanged; see [tool correction](postprocessing-correction-v2.md).

Before publication, 13,975 original files occupied 96.208 MiB logically and 128.774 MiB in allocated streams deduplicated by file identity. The largest complete compressed subject occupied 24,005 bytes, expanding to 115,415 JSON bytes; it contained 6 nodes, 2 directed connections and 904 decay contributions. This assay's complete subject includes fixed adapters and a temporal instrument, without separately stored learned-weight dependencies. Windows allocation excludes directory/MFT/database overhead; details are in `storage-inventory-v1.json`. Figures, inputs, temporal observations, complete subjects, source fingerprints, analysis and audit records are archived together. Review is attributed to the executing assistant and an independent arithmetic implementation; external replication is a separate category.

Originals: `E:/ThreeMindData/experiments/2026-11-09-decay-mechanisms52/assay-v1`. Research record: `e03f79a3-c92c-505d-bb37-6fad8e21355e`. Full API readback, archive hashes, final pending count and subsequent decisions are recorded in [delivery](delivery.md).
