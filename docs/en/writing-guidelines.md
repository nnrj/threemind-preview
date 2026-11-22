# ThreeMind documentation and scientific writing guidelines

[中文](../zh/writing-guidelines.md) · [English](writing-guidelines.md) · [Chinese–English translation guidelines](translation-guidelines.md)

Established on 21 November 2026 from the author's repeated corrections during manuscript revision and confirmation on this date.

These guidelines apply to project documentation, experimental reports, manuscript drafts, supplementary materials, figure titles and captions, tables, and glossaries. A reader with relevant professional knowledge, but no involvement in the project, should be able to follow the questions, methods, evidence, and conclusions throughout. Precision comes from clear concepts, complete reasoning, and verifiable facts. Concision comes from removing repetition and improving sentence structure.

Before drafting or revising, read the source text and definitions designated by the author, then consult the protocols, implementation, and reports relevant to the task. Use passages already refined by the author as style references. Translation also follows the [translation guidelines](translation-guidelines.md); experimental conclusions follow the [conclusion contract](plans/experiment-conclusion-contract.md), and historical revisions follow the [editorial rules](history/editorial.md).

The examples illustrate writing choices. Their assumed conditions and quantities are not new experimental records. Check each scientific statement against the relevant experiment before using it. These guidelines govern expression; they do not change Core mechanisms, experimental criteria, or established definitions.

## 1. Align the subject, action, and object

State who does what, what the action affects, and who obtains the result. If a subject is omitted, the actor must still be unambiguous. Numbers, records, configurations, and experimental individuals have different roles and cannot stand in for one another indiscriminately.

**Poor:** “We selected two experience records, one starting from region 0 and the other from region 1.”

**Better:** “We selected two individuals, one that had started from region 0 and another that had started from region 1, and retrieved their respective experience records.”

**Poor:** “The adapter used motor coefficients to read node activation.”

**Better:** “The adapter read each node's activation level, multiplied it by the corresponding motor coefficient, and summed the products to generate a motor command.”

Repair such sentences by reconstructing the actual operation, rather than choosing a more abstract verb. Inanimate subjects are not categorically wrong: “the adapter reads the record” and “connection weights decay over time” can accurately describe the implementation.

## 2. Preserve necessary information and avoid invented jargon

Retain the steps, conditions, and data needed to understand the experiment. Split long sentences or remove repetition where helpful, but do not compress a process into a string of unexplained nouns. Prefer established technical terms and words with clear ordinary meanings. When a new concept needs a name, explain what it denotes.

**Poor:** “Opposite teaching histories used same-origin differential observation.”

**Better:** “Two copies received teaching with opposite stimulus pairings. To observe each copy, we then created cued and uncued observation copies from its current snapshot, recorded activity over the same time window, and calculated the numerical differences between corresponding entries.”

A short sentence is not necessarily clear, and a long sentence is not necessarily rigorous. The test is whether readers can understand what happened, rather than whether the fewest words were used. Once a term has been clearly defined, use it without repeating its definition each time.

## 3. Define terms on first use and use them consistently

A concept should have a stable name across the text, figures, tables, supplementary materials, and both languages. Explain unfamiliar terms using concepts readers already understand. Do not define a term by repeating it or by introducing another unexplained term. State any study-specific use of an established term.

**Poor:** “Target connections are the connections used for target intervention.”

**Better:** “In this experiment, target connections were those selected by a predefined rule for their relation to the taught association. We selected a separate set of control connections and describe below which properties were matched between the sets.”

Distinguish target connections from matched control connections, readouts from output adapters, and reading by a fixed rule from freezing a trainable component's parameters. Whether a component is trainable does not, by itself, determine its name. If a component has several functions, explain the role it serves in the experiment.

The glossary serves accurate expression. If an author-approved definition or translation differs from an older glossary, record the discrepancy and synchronize the glossary within the authorized scope. Do not change the concept to fit the old glossary. Preserve the meanings of distinct mechanisms in historical versions rather than treating their names as global synonyms.

## 4. Introduce the question and method before the result

When introducing a control, parameter freeze, state exchange, connection blockade, or local transplant, explain the question it addresses and then describe the comparison. Methods that determine how a result should be interpreted belong before that result.

**Poor:** “Performance decreased after blockade. The experiment used differences between two activity records.”

**Better:** “To isolate activity changes caused by the cue, we recorded cued and uncued activity and subtracted corresponding entries for the same channels, times, and measures. We used these records to calibrate and test the readout. After baseline testing, we froze its parameters and blocked the target connections to test whether performance depended on those connections.”

If a method was used from the first test, describe it with that test. If a control was added after a problem emerged, explain when and why it was added. Describe retrospective analysis and prospective prediction in their actual sequence.

## 5. Explain experimental subjects, derivation, and timing

Identify original individuals, teaching copies, observation copies, intervention copies, and offspring produced by reproduction. State when a state was saved, which state was copied, which subject received each operation, and which states were preserved continuously. Describe ordinary continuous development and causal-intervention branches according to the actual procedure.

**Poor:** “Three origins each produced two copies, one receiving opposite teaching and the other no cue.”

**Better:** “Each original individual first produced two teaching copies, which received opposite stimulus pairings. At observation, we created two observation copies from each teaching copy's complete current state: one received the cue and the other did not.”

Make the statistical unit explicit. Suppose A, B, and C are three independently created original individuals, each producing ten research copies. There are three independent origins; the thirty copies support comparisons within origins. Copy counts, question counts, observation times, and individuals within a shared world must not automatically be reported as independent sample sizes.

Distinguish internal time from elapsed host time, cumulative timestamps from additional durations. Advancing from 300 to 600 internal seconds adds 300 internal seconds; it is not “another 600 internal seconds.”

## 6. Distinguish the research question, experimental method, and measure

Organize sections around scientific questions. A task tests a question; a measure helps assess the result. These are distinct roles.

| Role | Example |
| --- | --- |
| Research question | Can environmental selection pressure guide individuals toward an intended behavioral tendency? |
[Public edition: manuscript editing or private locator omitted.]
| Measures | Nutrient intake, predation events, survival, and reproduction. |

Likewise, pairing objects with names can test how experience affects responses. Using names does not make “naming” the research question. Time spent in a region can measure a behavioral tendency. Explain that measure in the results without replacing every broader question with a question about regional occupancy.

A negative result should still answer the original question. “Guiding individual evolution through environmental selection pressure” can name a research direction; report clearly if the batch did not produce the expected result. A title asserting success, such as “Environmental selection produced a predatory tendency,” requires supporting evidence.

## 7. Give an explicit conclusion for each experiment

After reporting results, answer the experiment's question before introducing the next experiment. Explain what the comparison established, why, which effect it located, and what it means for ThreeMind. Scores and PASS/FAIL labels do not replace this explanation.

**Poor:** “Performance decreased in the experimental group and remained unchanged in the control group. Next, we describe transplantation.”

**Better:** “Blocking the target connections abolished the measured response, whereas blocking an equal number of control connections did not. The response returned when the blockade was removed. These comparisons establish a reversible, selective causal role for the target connections in this response. We next tested whether transplanting these connections could transfer the response.”

Every factual clause in that example requires evidence from the relevant experiment. When a comparison establishes a winner on a predefined measure, state which option performed better and on which measure. Do not replace a clear result with “there was a difference” merely to sound cautious.

A full report follows the reasoning from purpose and expectation through results and analysis to scientific conclusions and implications for ThreeMind. A manuscript may express this sequence in connected paragraphs without six mechanical subheadings.

## 8. Preserve established findings and assess each objective by its original criteria

When a predefined condition is met, state that it is met. Failure on a more demanding objective does not automatically cancel a separate established result. Success on one objective does not establish the others. Use the criteria and comparison scope specified in the relevant protocol.

**Poor:** “Although structural retention improved, the new task failed, so teaching had no effect.”

**Better:** “Spaced teaching improved connection retention, while expression of the new task did not meet the predefined criterion under this curriculum. Structural retention and new-task expression therefore had different outcomes.”

Distinguish negative results, invalid measurement, insufficient precision, and work not performed. Failure to meet an effect criterion does not automatically establish absence of an effect. Clear conclusions remain compatible with reporting sample sizes, effects, intervals, and material conditions accurately.

## 9. Remove irrelevant negations and qualifications

Keep conclusions focused on the actual question. Do not introduce a larger, previously unexamined claim after a completed test and end by saying it has not been proved. Avoid abruptly inserting operational reminders, archival arrangements, or self-justification into scientific exposition.

**Poor:** “The individual met all four autonomous-activity criteria, but this does not prove that it has every human cognitive ability.”

**Better:** “The individual met all four predefined criteria and exhibited autonomous activity as defined in this study.”

**Poor:** “The conditions produced different responses; the materials were stored separately.”

**Better:** Explain how the responses differed and why that matters to the conclusion. Put necessary storage locations in the materials-availability statement or evidence index.

Retain limitations that affect interpretation and explain them concretely: what was matched, what the readout observed, or whether the evidence distinguishes two explanations. Distinguish hypotheses, direct observations, and mechanistic interpretations. These details should help readers assess the current question, rather than repeatedly introduce unrelated negative claims.

## 10. Organize sections around questions and develop paragraphs progressively

Give each paragraph a central point, connect it to the preceding discussion, and then introduce new information. Place evidence for the same mechanism in the relevant section. After defining a concept or explaining a method, use the established term and cross-reference where useful. Let the argument determine section length; avoid splitting one continuous explanation into numerous fragments.

[Public edition: manuscript editing or private locator omitted.]

**Better:** Place that experiment in the section on experience dependence, connection causality, or personal output adapters, and explain which claim it supports. Keep the environmental-selection section focused on environmental selection.

The introduction establishes the question, related work, constructive approach, and main contributions. The main text provides the methods and evidence needed to understand the principal results. Detailed formulas, parameter lists, and reproduction steps may go in supplementary methods. Do not remove definitions, key controls, or conditions that affect the conclusion merely to save space. Captions should explain groups, symbols, and quantities.

## 11. Respect the author's text and separate technical correction from stylistic revision

Use the source version and editing scope designated by the author. Preserve the structure, research claims, and terminology of passages the author has refined. Correct spelling, grammar, and repetition within the authorized scope. Do not use stylistic revision to replace the research question, narrow a definition, or change a conclusion.

**Poor:** Recasting a proposed artificial consciousness model as a memory device during polishing, or silently changing its theoretical claim in translation.

**Better:** Preserve the research framing. If a passage conflicts with the relevant implementation or experimental record, identify the original wording, evidence, proposed replacement, and change in meaning, then act within the authorization already given.

Complete and document necessary technical corrections already authorized; do not ask again for the same permission. Ask a specific question only when a substantive change remains unauthorized and existing decisions do not resolve it. Ordinary copyediting requires no additional approval process.

Translation preserves the Chinese text's facts, logic, and strength of conclusions while using natural English. Substantive changes must be traceable across both versions; the English version must not quietly introduce a different argument.

## Drafting and review

Before starting, confirm the source, editing scope, and key terminology. Organize evidence by scientific question and provide a conclusion after each result. Read the draft continuously from the perspective of a professional who did not take part in the experiments, then check data, units, versions, figures, tables, and citations.

Before delivery, check:

- Is the actor clear for each action, with unambiguous references?
- Are new concepts explained and names used consistently?
- Do methods precede results, with reasons for additional controls?
- Are original individuals, copies, offspring, worlds, and statistical units distinguished?
- Do quantities, denominators, times, controls, and Core versions match the evidence?
- Does each experiment answer its question and explain its significance?
- Are there post-result criteria, irrelevant negations, unsupported attributions, or vague conclusions?
- Are the author's approved wording and correspondence across languages and figures preserved?

Use this review to find concrete problems; do not insert a compliance declaration for every item into the paper. When correcting the scientific interpretation of a published report, follow the conclusion contract: append a dated, sourced revision and preserve the original text, criteria, and evidence.
