# Central adapters

[简体中文](../../zh/reference/central-adapters.md) · [Adapter protocol (Chinese)](../../zh/v2-adapters-and-capabilities.md) · [E46](../plans/native-expression.md)

Proposed by the user and adopted as terminology on2026-10-05. This is a **user/task-facing functional category**, not a new Core layer, privileged bus access or a predefined brain region.

A central adapter learns transformations between complex external information, anonymous internal activity and useful output. It remains replaceable, optional and governed by the ordinary adapter protocol. A device essential for one application may be unnecessary for another.

| Category | Possible role | Boundary |
| --- | --- | --- |
| Language | Input encoding and activity-to-text/speech; directions trainable separately | Do not attribute answers produced by bypassing Core to the instance; text need not exhaust thought |
| Vision | Visual features and activity interpretation/reconstruction | Generated reconstruction is not demonstrated subjective vision |
| Hearing | Acoustic/speech mappings and activity readout | Do not silently encode human semantic answers in anonymous inputs |
| Motor | Body-state/execution translation and learned action expression | Declare prebuilt controllers; their strategies are not Core emergence |
| Multisensory coordination, candidate | Explicit joint observations, synchronization and expression | No automatic merging of unrelated sources or answer injection |

No new inheritance hierarchy, service or protocol is required solely by this name. Deployment/research manifests should identify role, directions, model/mapping versions, individual binding, calibration history, frozen/trainable status and dependencies. Shared models and individual alignment can coexist; switching individuals must not silently reuse the wrong calibration.

Preserve raw activity separately from interpretation. Teacher labels may train expression only in declared training partitions. Test whether the adapter can solve the task without learned Core activity. Aphasia is a conceptual analogy for distinguishing information from expression, not a diagnosis of established human language understanding in ThreeMind.

## Source

Translated excerpts from the project conversation,2026-10-05; original Chinese excerpts are preserved on the linked Chinese page:

> The architecture and essence do not differ, but their description gives them a special position.
> That position is not relative to Core, but relative to others or users interacting with Core indirectly.
> The categories are not permanent; they vary with actual needs. Embodied robots may also need a motor central adapter.

The user used monitors, keyboards and mice versus printers as an analogy for application-dependent importance. This is a functional description, not an additional Core axiom or experimental result.

## Same-day clarification: encoding, internal interpretation and expression

The user suggested that signal conversion, internal-pattern learning, inner monologue and speaking to others may have been conflated. Distinguish three roles, optionally packaged together:

- **Input encoding:** sound/text/images to measurements/features and anonymous stimuli. It may be independently pretrained/shared, but does not replace common provenance, channel, timing and delivery rules in the bus.
- **Internal activity interpretation:** an observed process to candidate readable text/images. A passive instrument, not an instruction to speak. Direct sensation versus recall and shared versus individual calibration remain separate comparisons.
- **Outward expression:** actual output activity drives text, speech or action, including when to communicate. Device execution must not be mistaken for an internally learned choice to speak. This batch has not established that choice.

“Inner-monologue adapter” is a convenient informal name; the present tool is more precisely an internal-activity language reader. Its text interprets activity; it does not establish that the activity was already a private sentence. Displaying that interpretation is not automatically a voluntary utterance. Input/output may share components or train separately; no evidence requires one permanent network.

Attention/output gating might matter, but this terminology adds no artificial selector or suppression of human-incomprehensible activity. The user's proposal that internal-pattern learning must be individual is a hypothesis tested by E46, not an assumption written into the result.

Translated source excerpt,2026-10-05: “We may have mixed up two language decoders; the language central adapter seems to have input and output.” The original Chinese page also preserves the user's uniform-bus requirement and individual-calibration hypothesis.

## Expression selection and attention: deferred question

The user subsequently proposed a neurological “gatekeeper” analogy and preferred that when/what to express develop through experience and existing dynamics. Decision2026-10-05: add no gatekeeper and enable no new attention switch in this batch; retain raw interpretation and later test selection in a communication environment. The analogy does not establish a single brain region or matching ThreeMind mechanism.

“Attention” refers to different mechanisms. Historical input competition has an independent switch. The actual continuous-memory/2 configurations saved in E46 have`context_enabled=true`, `context_mix=1`: local contextual arrival processing, not a decision to speak. A remembered disabled switch must not be generalized to every attention mechanism. No value changed here.

Open comparisons: whether existing dynamics can learn selective expression from communication consequences; if something is missing, whether to add a semantically neutral local mechanism or external execution adapter; controls that preserve internal activity while changing outward expression. Do not assume a separate gate, attention, or human-like anatomy is necessary.

Translated user excerpts: “I would prefer it to form naturally through internal evolution, or automatically through enough input under the existing dynamics.” “This can be deferred; continue the planned experiment and record it afterward.”

## Observational interpretation and an expression tool the instance can use

In a further same-day supplement, the user distinguished fragmentary, imperfect interpretation for researchers from an expression tool through which an instance can act. Such a tool should preserve temporal order and compositional relationships; downstream adapters could render text, sound, music or other forms. The requested logical sequence does not authorize the adapter to supply correct reasoning or fluent answers on the instance's behalf.

One possible implementation reuses replaceable conversion components in two different paths. The observational path reads activity and preserves uncertainty. The expression path accepts actual output-bus activity over time, produces external actions, and lets their environmental consequences return through ordinary sensors. Whether and how the instance chooses to communicate must be tested in a communication environment. E46 does not establish purposeful use of an expression tool; automatically vocalizing a state interpretation is not that result.

A common intermediate sequence with text/music sub-adapters and separate task-specific expression adapters remain alternatives. Temporal fidelity, reuse and experiments should decide whether the intermediate representation is useful. This adds neither a prescribed human grammar nor a Core protocol change. The user explicitly asked not to interrupt E46; no new speech-selection mechanism was implemented.

Original Chinese excerpts (2026-10-05, same project conversation; the paragraphs above are summaries):

> 内部模式的解码器可以不准确，表达器则应该能有效表达 ThreeMind “想”传达的信息。

> 内部模式解码器服务的是观察者、研究者及想要了解 ThreeMind 内部意识活动者，而 表达器 是供 ThreeMind 内核使用的工具

> 我目前无法设想，ThreeMind 如何使用它，还是看起来需要工具主动去解读 ThreeMind ？

## Constraints from E46

[Measured results](../../../lab/explorations/2026-10-05-native-language/report.en.md) support calibrating actual association patterns, not mandatory co-development or dependable new-knowledge expression. The current tool remains observational. A common expression sequence, purposeful use and output choice remain open; naming a role does not implement it.

### 2026-10-05: Role evidence from E47

Jointly calibrated individual expression produced correct names through cross-sensory pathways; new assignments and voluntary expression remain unresolved. The best reader subtracts an unprompted twin and is a research response-interpretation tool, not a test for absent inner speech. Preserving absolute activity/context/order is a next direction. Observer decoding is not a speech action chosen by the instance. A co-developing language center may continue learning; freezing is an attribution tool.

[E47 report](../../../lab/explorations/2026-10-05-expression-alignment/report.en.md)

## 2026-10-07 · System continuity / 个体连续性

Engineering replaceability does not permit changing an individual’s center during ordinary development. Core, its adapter weights/learning state/recent buffers and body form the experimental organism; groups may differ. Offline refits, cold starts, transplantation and ablation require explicit identity and scope. Branch evaluation from complete snapshots; do not roll back only an adapter to a “best” checkpoint while Core remains at a different time. Existing tools do not yet fully support this; R40 lists the gaps.

[R40](../plans/system-continuity-audit.md)
## 2026-10-07: translate the choice, execute with a servo

The user endorsed the functional division of activity reader selecting a position and servo execution. A motor center should translate particular internal Core activity into bodily targets; a servo, robot driver and physical body provide local feedback, forces and motion constraints. Core need not relearn a low-level motor driver, and the division does not authorize deciding the target on Core's behalf.

Inference reads actual Core activity, with answers confined to declared supervision. Nevertheless a peripheral might recognize the target from direct sensory activity. Passing through Core is not by itself proof that a choice primarily comes from its developed internal pattern. Keep the reader fixed and use explicit history/connection/activity interventions and restoration to measure effects on actual choice, motion and correctness. Functional viability and causal attribution are separate findings.

This is an engineering analogy, not a one-to-one anatomical identification. E62 retains each individual's own peripheral and learning state, testing basic action before extending shape/color pointing. [Current boundary](../../../lab/explorations/2026-10-07-continuous-development/control-boundary.en.md).
