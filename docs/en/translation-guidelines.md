# ThreeMind Chinese–English translation guidelines

[中文](../zh/translation-guidelines.md) · [English](translation-guidelines.md) · [Documentation and scientific writing guidelines](writing-guidelines.md)

Established on 21 November 2026 from the author's requirements during Chinese revision, English translation, and terminology discussions. Use alongside the writing guidelines for translating and synchronizing manuscripts, reports, technical documentation, supplementary methods, glossaries, and figure and table text.

Translation should combine fidelity, clarity, and natural expression. **Fidelity** preserves facts, definitions, research claims, reasoning, and the strength of conclusions. **Clarity** lets English readers understand the subjects, procedures, and reasons. **Natural expression** uses fluent, precise academic English. Meet all three together. Accuracy does not require word-for-word translation, and fluency does not authorize changing the author's scientific claims.

## 1. Establish the source and synchronize within the requested scope

Translate from the corrected Chinese version designated by the author for the current task. Use an older English draft to locate existing wording and corresponding passages, not to override the new Chinese text. For whole-document work, record the Chinese and English files and versions used. For a sentence or paragraph request, the text supplied by the user is sufficient.

When the Chinese revision changes one sentence, update that sentence and any necessary transitions in English. Do not casually rewrite the entire paragraph or alter neighboring conclusions. Preserve passages the author has designated for retention. Apply abstract limits, title lengths, and formatting requirements to the current task, rather than imposing the constraints of one submission on every subsequent version.

**Poor:** The author adds “and apply it in new situations,” but the translation repeats the older paragraph and omits the addition.

**Better:** Translate the addition in its corresponding sentence, check adjacent references and transitions, and retain the remaining accurate text.

## 2. Translate the proposition faithfully, including its strength and scope

First identify what a sentence asserts: who did what under which conditions, which judgment the evidence supports, and which words express a hypothesis, possibility, causal relation, or comparison. Preserve these relationships. Do not routinely dilute “the experiments show” into “may be compatible with” to sound cautious. Equally, do not turn a hypothesis awaiting a test into an established fact.

| Chinese source | Unsuitable translation | Suitable translation |
| --- | --- | --- |
| 这些结果表明，经历形成的连接参与组织响应。 | These results may be compatible with a possible role for experience. | These results show that connections formed through experience help organize responses. |
| 我们假设，持续经历能够塑造自主活动。 | We demonstrate that ongoing experience shapes autonomous activity. | We hypothesize that ongoing experience can shape autonomous activity. |

Choose verbs such as `show`, `demonstrate`, `support`, and `suggest` according to context and evidence. Do not impose a mechanical one-to-one verb list. Preserve the claim's certainty, scope, and causal meaning.

Translate autonomous activity, artificial consciousness model, self-consciousness, and related concepts according to their respective definitions in the source. Do not remove the model's research framing for caution, or translate satisfaction of autonomous-activity criteria as validation of a different concept.

## 3. Preserve the author's definitions rather than introducing new ones

A definition's subject, scope, components, and exceptions are substantive content. Translate them fully and use the definition consistently thereafter. If a definition contains a technical problem, identify it and its evidence, then act within existing authorization. Do not silently correct it only in English.

**Poor:** The source discusses meaning assigned by an external observer, but the translation adds that “meaning here refers only to task answers,” narrowing the proposition.

**Better:** Translate the proposition faithfully. Present any proposed restriction of “meaning” separately for the author's decision, then synchronize both versions if approved.

Likewise, “semantics are not predefined” differs from “no state has any meaning.” “The Core receives no answers” differs from “the whole system, including teacher-supervised adapters, receives no answers.” Translation must preserve which component a constraint applies to.

## 4. Identify the concept before choosing a word; update glossaries to reflect approved definitions

Prefer terms familiar to professional readers and appropriate to the actual mechanism. Author-approved definitions and translations take precedence over unconfirmed wording in older drafts. When a glossary is outdated, record the discrepancy and update it within the authorized scope. Do not remove a meaningful component such as “center” merely to fit an old glossary.

Start terminology checks with the [project glossary](terminology.md), while also checking definitions in the author's current source. If a term's established usage is uncertain, consult original papers, formal textbooks, or authoritative technical documentation. Without supporting usage, explain it as descriptive wording rather than presenting it as a recognized technical name. If a Chinese rendering is awkward, improve it without changing the quantity or mechanism denoted by the English term.

The table identifies distinctions to check when choosing words for the current document. It does not replace that document's full glossary or authorize global renaming.

| Chinese concept or wording | English treatment | Distinction to preserve |
| --- | --- | --- |
| 刺激 | stimulus; plural stimuli | `Input` may label an interface input, but should not replace the defined term stimulus throughout; check figures too. |
| 响应 | response | Distinguish responses, response differences, and behavior as defined in the text; do not alternate them merely for variety. |
| 激活、激活信号 | activation; activation signal | Distinguish a state or process from a transmitted signal. Explain and consistently use any alternative approved terminology. |
| 抑制、抑制信号 | inhibition; inhibitory signal | Keep these distinct from the mechanism described as short-term depression. |
| 读出器、输出适配器 | readout; output adapter | Translate according to their defined roles, rather than merging them because both may be trainable. |
| 按固定规则读出 | read out responses using a fixed rule | A fixed reading rule does not automatically mean an experiment freezing learned parameters. |
| 参数冻结的读出器 | a readout with frozen parameters | Identify the component whose parameters are no longer updated. |
| 参数冻结的输出适配器 | an output adapter with frozen parameters | Preserve the component's identity rather than abbreviating it ambiguously as fixed readout. |
| 运动中枢适配器 | motor-center adapter, when this defined name is used | Preserve the functional meaning of center rather than shortening it solely for convenience. |
| 内核 | Core, when used as the component's formal name | Use consistent capitalization in prose. Preserve code identifiers, version strings, filenames, and kernel in cited sources. |

Consistent concept naming does not require a Chinese word to have one English equivalent in every context. If 独立来源 is defined as the shared statistical origin of an original individual and its copies, use `independent origin` when that translation has been confirmed. Translate 数据来源 according to its meaning as a data source or provenance. Do not replace origins, instances, individuals, configurations, and paired comparison sets indiscriminately with `instance` or `source`.

Also check whether the Chinese wording mistranslates an appropriate English term. For example, `exposure` in a stimulation experiment may mean receiving stimulation, rather than photographic exposure. If `learned response` is rendered as 习得响应, keep it consistent with the established translation of response and explain that it refers to a response pattern acquired through learning. Natural terminology still requires clear methods; an English phrase is not automatically an established technical term that needs no explanation.

Choose words by their actual meaning. For example, if a formula concerns signal `amplitude`, do not replace it with “ease of conduction” solely because the Chinese wording sounds awkward: that changes the quantity being discussed. Chinese 传导 and 传递 also need not correspond word for word to `conduction` and `transmission`. Check the process and usage in the relevant field, then use the confirmed translation consistently.

## 5. Preserve quantities, statistical units, and logical conditions

Check origins, individuals, copies, questions, worlds, repetitions, denominators, effect sizes, and intervals individually. Preserve the scope of words such as all, at least, only, and both. Pay particular attention to joint criteria: failure to succeed in both conditions does not mean failure in every component condition.

**Chinese:** “八个提示中，没有一个在两种配对关系相反的教学条件下都得到正确的新目标回答。”

**Incorrect:** “None of the eight questions was answered correctly.”

**Correct:** “None of the eight prompts yielded correct new-target answers under both teaching conditions with opposite stimulus pairings.”

Here, 0/8 means that none of the eight prompts met the requirement for success under both conditions. It does not mean that eight individual answers were all wrong. Similarly, 64 comparison sets containing five systems each must retain the distinction between sets and systems, rather than becoming 320 independent comparisons.

Check percentages versus percentage points, response magnitudes versus response differences, and activity durations versus observation windows. Do not omit qualifiers that determine a quantity's meaning merely to shorten the English.

## 6. Preserve experimental steps, actors, and continuity

Readers must be able to distinguish who receives teaching, generates a response, reads activity, updates parameters, and executes an action. Preserve the actual sequence of saving, copying, teaching, testing, intervention, and restoration. Distinguish snapshot copies from offspring and complete individuals from Core-only states as the source does.

**Chinese:** “适配器读取节点激活，再按运动系数计算指令。”

**Incorrect:** “The coefficients read node activation and generate commands.”

**Correct:** “The adapter reads node activation and uses the motor coefficients to calculate commands.”

If subtracting the uncued record from the cued record means elementwise numerical subtraction, write `subtract the uncued activity values from the corresponding cued values`, not `take the set difference`. Reading an activity process over a time window must not become sampling a state at a single instant.

Distinguish internal time from elapsed execution time. “从300内部秒运行至600内部秒” can be translated as `advanced from 300 to 600 internal seconds`. If the document instead uses `seconds of simulated time`, define that convention and use it consistently.

## 7. Restructure sentences into natural English while preserving the explanation

Reorder clauses, split long sentences, supply subjects required by English grammar, and replace nominalizations with verbs where useful. Explain the purpose, operation, and result so that professional readers do not have to reread repeatedly. Avoid stacks of abstract nouns, successive passive constructions, and undefined abbreviations.

**Awkward:** “The implementation of the verification of the effect of connection blockade was conducted.”

**Natural:** “We tested how blocking the connections affected the response.”

Active voice often clarifies who acted; `The target connections were blocked` is also natural when the intervention object is the focus. Not every sentence needs to start with `we`. Do not accumulate nouns for an academic tone or change defined terms merely to avoid repetition.

If the source omits a necessary subject, comparison, or step, first check the surrounding passage and cited methods. If the meaning remains unresolved, identify the omission and ask a specific question when necessary. Do not invent a plausible procedure to make the prose flow. Complete authorized language edits directly and identify added explanations that affect scientific meaning separately.

## 8. Choose tense according to the subject and preserve temporal information

Past tense generally describes completed procedures and results in a particular experiment. Present tense commonly describes definitions, rules, and the contents of figures or the article. Express future work according to whether it is planned or merely possible. Choose tense contextually: do not translate every Chinese 了 mechanically, or remove all information about completion and sequence for concision.

- “实验采用了两套外设。” may become `The experiment used two peripheral configurations.`
- “输出适配器将响应转换为指令。” may describe a general function as `The output adapter converts responses into commands.`
- “固定参数后，我们继续教学。” may become `After freezing the parameters, we continued teaching.`

Do not use tense or connectives to invent precedence, necessity, or causality that the source does not assert. For example, adding `therefore` does not turn a temporal sequence into evidence of causation.

## 9. Check the text, figures, tables, and supplementary materials together

Use the same approved names for stimuli, components, conditions, and measures in the text, figure labels, captions, table headings, glossary, and supplementary methods. Do not use `stimulus` in the text and silently replace it with `input` in a figure. Likewise, freezing a readout's parameters should not become an ambiguous figure label such as `fixed mapping`.

English captions should identify panels, groups, measures, and necessary statistical information. Direct readers to detailed methods with specific section or experiment identifiers. Avoid abruptly appending operational asides such as “stored separately” or “recorded separately.”

Preserve formulas, parameter symbols, code fields, version identifiers, figure and table numbers, and citation correspondence. Verify bibliographic authors, titles, and publication details against real sources; do not present a translated title as the official English title. Cite research that actually informed the study and is used in its argument where the relevant claim or method is discussed.

English lists can generally use `1.`, `2.`; inline enumerations can use `(i)`, `(ii)`. Follow the target document's consistent format. Check specific journal or platform requirements at submission, rather than making one template's constraints permanent requirements for every document.

## 10. Distinguish translation, technical correction, and abridgment

Translation preserves corresponding content. Technical correction resolves a conflict with implementation or evidence. Abridgment removes content for a specific length. An authorized task may include all three, but the author should be able to identify changes in meaning.

A request to translate does not authorize omitting theoretical claims, important conditions, or conclusions. When abridgment is explicitly requested, preserve the research question, principal methods, key results, and conclusion, then remove repetition and secondary detail. A word limit is a maximum, not a target that must be reached exactly. Do not create ambiguity to save a few words. Distinguish full and shortened versions when both are requested.

If facts conflict, identify the source wording, evidence, and proposed change rather than resolving the conflict silently in English. Implement and list corrections already authorized; continue to respect protected passages. Corrections to scientific interpretations in published reports follow the [conclusion contract](plans/experiment-conclusion-contract.md), using appended revisions.

## Translation and final review

Read the Chinese text and relevant definitions before translating paragraph by paragraph. After drafting, compare both versions for meaning, then set the Chinese aside and read the English as a standalone paper for naturalness and continuity. Finally check figures, tables, terminology, and cross-references.

For each paragraph, check at least:

- Are subjects, actions, objects, comparisons, and causal relationships preserved?
- Are definitions, questions, conclusion strength, and material conditions intact?
- Are logical terms such as all, only, both, and at least translated correctly?
- Do data, units, denominators, times, versions, and citations agree?
- Does any added English explanation have support in the source or an authorized revision?
- Can English readers understand why the experiment was done, how it was done, and what it found?
- Are terms consistent across the text, figures, tables, and supplementary materials?
- Is the current Chinese revision fully reflected, with unaffected approved content retained?

For key definitions, ambiguous statistical sentences, and major conclusions, an additional Chinese paraphrase of the English can help compare meanings. It does not replace checking the source and evidence. When delivering a whole document, identify the versions actually synchronized and list substantive corrections, terminology changes, and unresolved decisions. When asked for one translated sentence, provide the sentence without attaching a review report.
