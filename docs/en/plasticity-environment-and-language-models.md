# Plasticity, Environmental Selection, and Language Models: ThreeMind's Research Position

> Public edition, 2026-11-11: private conversation locators and manuscript/submission discussions are omitted where present. Scientific records retain their original dates; the complete source remains unchanged.


[中文](../zh/plasticity-environment-and-language-models.md) | [English](plasticity-environment-and-language-models.md)

**Date:** 2026-09-22  
**Status:** An edited account of the project initiator's research position and design vision, including hypotheses awaiting validation.  

> **Public-edition edit (2026-11-11; source lines 7-7):** Private conversation IDs and locators are omitted; scientific quotations and records are retained. The complete source remains unchanged.



**Source:** The author's statement after reading “讲解LLM与Transformer原理历史”, followed by a correction to the definition of death. The complete original statement is preserved below.  
**Relation to existing documents:** This supplements the [hypothesis framework](consciousness-hypothesis.md) and the [Transformer research assessment](transformer-comparison-and-research-assessment.md). It records a direction, not a claim that the current system has achieved these capabilities or an instruction to change the kernel, sensory mapping, or experimental protocols.

## 1. The central objective: a system continually shaped by experience

ThreeMind aims to build artificial consciousness that forms, retains, and changes its organization through continuing contact with an environment. Plasticity is central to this research direction.

The first question is whether stimuli from the physical world, or a simulated physical world, can leave structure and response tendencies in a network governed by simple, consistent rules. Can later experience reshape those tendencies, and can they support adaptive behavior in a particular environment?

ThreeMind therefore does not make encyclopedic knowledge, fluent language, or near-universal competence an entry requirement. A system with poor arithmetic that learns through experience to avoid injury, detect danger, and adjust its behavior could still be a valuable intermediate achievement. It need not reproduce human internal representations or translate its activity into human-readable explanations before it can exhibit adaptation.

This retains artificial consciousness and AGI as long-term objectives, while placing ongoing activity, shaping through experience, and environmental adaptation first.

## 2. Common ground with LLMs, and a different research emphasis

ThreeMind does not reject language models. The common ideas the author recognizes include the ability of experience or training data to change response tendencies, connection weights carrying effects of past experience, and distributed organization producing capabilities without people inserting individual facts or concepts.

The statement that “no specific knowledge or concepts are stored in the model” is interpreted here as follows: **internal representations need not be human-readable records corresponding one-to-one to knowledge entries.** This does not mean that the model encodes no knowledge, or that a concept must occupy one node.

The distinction the author values most is whether a deployed system continues to be reshaped by its own experience. A typical fixed-parameter language model produces dynamic activations during a call but usually does not write that experience directly into its base weights. ThreeMind places local learning and structural change during operation at its center. Persistent state, input and output forms, structural growth, and learning rules also deserve separate comparison.

The author contrasts “placing electrodes into an already dead brain” with “building a living brain.” This metaphor expresses the difference between fixed structure and continuing reshaping as research priorities. It is not a scientific classification of LLMs as alive, dead, or conscious, and does not imply that a fixed-parameter system has no dynamic state.

## 3. Activation, plasticity, and death

The author subsequently corrected the wording: **death means the cessation of activation activity, not the cessation of reshaping.**

Three quantities must remain distinct:

- **Activation activity:** ongoing signal propagation, responses, association, and competition.
- **Capacity for plasticity:** whether experience can change connections, weights, or other relevant network state.
- **Actual reshaping:** whether those changes occur during a particular interval, and how much changes.

An interval with no new connections, temporarily stable weights, or an experiment with learning disabled cannot by itself be treated as the cessation of activity. Retained connections alone do not establish continued life either. Internally generated associative activation and activation caused by external stimuli both count as activity.

The existing implementation declares death after the first activation when all nodes remain inactive for the configured interval, which defaults to one simulated second. Before the first activation the instance is waiting for input; pausing does not consume that simulated waiting interval. This is the existing operational definition, described in the [kernel lifecycle](v2-kernel.md) and the [activity-based death decision](plans/energy-lifecycle.md). The correction is consistent with it and introduces no new death condition.

## 4. Nonintervention: specify rules, without prescribing cognitive outcomes

ThreeMind seeks structures that grow from stimuli and local rules. Researchers should not directly specify “this node is grandfather” or “this connection is the correct answer,” nor add a hidden reasoning system to the readout in order to manufacture success.

Nonintervention does not mean software can exist without human design. Mapping protocols, propagation rules, thresholds, environments, and bodies all require explicit construction. The constraint is that the rules should be consistent, inspectable, and as independent as possible of researchers' semantic judgments about particular content. Input should have a traceable environmental basis; mappings or connections should not be rewritten to supply an answer to an individual task.

Researchers may design environments, establish selection pressures, and perform explicit ablations or interventions. Selection through environmental consequences and direct insertion of the internal pathway for a desired behavior are different operations and must be recorded separately.

ThreeMind does not require people to read the internal world of a consciousness node by node. Interpretability can help research, but is not a condition for internal activity to be legitimate. Behavior, input provenance, and measurement procedures must nevertheless remain inspectable. An activation that a human does not understand is not grounds for deleting it, filtering it out, or inventing its meaning.

## 5. Capabilities formed through experience and environmental selection

The author's proposal is that any eventual language, communication, or mathematical capability should arise from structures formed by experience and response patterns retained through environmental selection, rather than from researchers installing a list of concepts labeled “language understanding.”

At least two processes are involved:

1. An individual learns and changes through its own dynamics while interacting with an environment.
2. In evolutionary experiments, environmental conditions affect which individuals and heritable features persist.

These are not interchangeable. Strengthening connections does not automatically constitute population-level natural selection. Eliminating poorly adapted individuals cannot replace the mechanisms needed for individuals to form useful structures.

The original wording “not because the model learned something” is interpreted as “not because a researcher inserted named knowledge or capabilities beforehand.” In ordinary technical usage, a lasting change in future behavior produced by experience is still learning.

Withdrawing from an injury or escaping danger are examples of desired functions: the behavior should emerge through experience and selection, rather than through a directly programmed reflex. Different environments might produce organizations resembling different kinds of organisms, without all of them being optimized for human question answering. The idea that environmental selection can carry this path “from ants to humans” is retained as a long-term conjecture. It is not established that changing environmental objectives alone would suffice.

## 6. Openness to Transformers and the external-brain proposal

Provided that the kernel hypotheses, nonintervention principle, and plasticity are preserved, LLM and Transformer ideas, algorithms, and engineering methods may all be studied, compared, combined, or reproduced. Technical origin alone should not disqualify a useful method.

Any borrowing should identify where it operates:

| Location | Possible research use | Attribution that must remain explicit |
| --- | --- | --- |
| External tool or adapter | Language interaction, knowledge queries, an interlocutor in the environment, or assistance executing complex outputs | These capabilities may belong to the external model, rather than to ThreeMind |
| Independent comparison model | Compare fixed parameters, adaptation within context, and online learning on the same task | Retain each model's training history and resource costs; do not silently mix a comparison model into the main system |
| Candidate kernel mechanism | Content-related addressing, fast and slow memory, local updates, or organization of computation | Check for semantic shortcuts and changes to the original hypotheses; validate separately before adoption |
| Hybrid system | Combine a continually plastic system with language and knowledge tools | Measure internal learning, tool contributions, and behavior when tools become unavailable separately |

The author views ThreeMind and language models as differently oriented approaches within the broad space of learning networks. The proposed combination gives ThreeMind the role of a continually adapting agent and an LLM the role of an external language and knowledge resource. This is a system hypothesis to investigate, not a completed integration.

The claim that successful ThreeMind plus an LLM would produce a complete AGI, and the counterfactual that ThreeMind might eventually have developed into a language model in a history without Transformers, remain the author's vision and conjecture, not validated conclusions.

## 7. Editorial notes: what current evidence supports

This section adds technical context and is separate from the author's research position above.

**LLM results support shared foundations, but do not directly validate ThreeMind's particular dynamics.** Capabilities achieved through large-scale learning show that distributed parameter systems can develop useful response patterns. They do not by themselves establish that ThreeMind's current rules for connection formation, propagation, consolidation, and forgetting suffice for language understanding or general intelligence.

**Transformer, LLM, and plasticity are not mutually exclusive categories.** Transformer names an architecture family; LLM names a class of language-modeling systems. Plasticity requires specifying what changes: activity, memory, weights, or topology. GPT-3 research demonstrated adaptation through context without gradient updates, which should also not be equated with the persistent structural reshaping ThreeMind seeks. [Language Models are Few-Shot Learners](https://arxiv.org/abs/2005.14165)

Research has connected linear attention with fast weights and has combined attention with neural memory learned at test time. These provide mechanisms to compare, showing that language modeling and online updates are not incompatible in principle. They do not establish equivalence with ThreeMind. [Linear Transformers Are Secretly Fast Weight Programmers](https://proceedings.mlr.press/v139/schlag21a.html), [Titans: Learning to Memorize at Test Time](https://arxiv.org/abs/2501.00663)

**Computational cost must be measured, rather than inferred from plasticity alone.** Frequent whole-network updates may be expensive, but locality, activity sparsity, memory timescales, and scheduling all affect cost. Reducing computation while preserving model behavior is an engineering and experimental question. This document does not authorize omitting dynamical steps for performance without establishing equivalence.

**Plasticity, adaptation, consciousness, and AGI require distinct evidence.** Learning an environmental response can be an intermediate achievement, while a programmed reflex can produce some similar behavior. Whether continuing plasticity is necessary or sufficient for consciousness or AGI cannot be established by analogy. “Fixed-parameter LLMs necessarily cannot achieve AGI” is recorded here as the author's judgment, not a settled result.

**Chronology relative to Jev:** The author states that the relevant ThreeMind ideas predate Jev. This position is preserved here without a historical priority audit, and similarity alone is not treated as evidence of direct influence or derivation.

## 8. Original statement and subsequent correction

The following Chinese statement is preserved verbatim, including wording, spaces, punctuation, typos, and the final editorial request. The explanations above do not replace the original record. Both language editions retain the same source for comparison. For the definition of death, the author's subsequent correction and section 3 take precedence.

### Original statement


> **Public-edition edit (2026-11-11; source lines 108-108):** Private conversation IDs and locators are omitted; scientific quotations and records are retained. The complete source remains unchanged.



> 我在会话 讲解LLM与Transformer原理历史 中大略了解了一下 LLM 和 Transformer  的原理和发展历史。我感觉 LLM 的很多思想和 ThreeMind 是重合的，比如大量数据训练、权重、没有具体的知识或概念存储在模型里。唯一重要的区别是可塑性，这是 ThreeMind 的核心价值，其次就是 ThreeMind 不要求人类理解（与 jev 的思想有点像，但ThreeMind 的思想产生比 jev 要早，应该说 jev 和 ThreeMind 的思想有点像）、ThreeMind 在网络设计上拒绝非自然的干预、希望网络的结构由网络本身的一套简单约束规则在有客观依据（客观世界信息映射）的刺激下自然长出来，并不断被重塑。重塑停止意味着”意识“死亡。所以 LLM 在我看来，更像是在一个已经死去的大脑上，接入电极，刺激一下，获得激活数据响应。而 ThreeMind 要做一个活的大脑。这使得 ThreeMind 不能像 LLM 那样去追求全知全能，因为全网络（或者局部网络）可塑更新的连锁反应、源源不断的刺激接收，使得每个瞬间的算力消耗都是海量的。还好， ThreeMind 一开始的目标，就不是追求全知全能，ThreeMind 不在意模型有多少人类可理解的知识，只在意模型能经过刺激产生一些结构和响应模式，这些结构是对客观世界信息的映射（刺激）的映射、投影，同时能在某个环境选择目标下，保留特定的响应模式。ThreeMind 没有规定模型要如何，最终模型如果能理解语言乃至能像人类一样思考，不是因为模型学会了什么，而是因为训练时将模型放在了一个与人类大脑演化经历相似或者与人类称为智慧、意识（未必是人类这种智慧和意识）那种模式的形成高度相关的环境之进行了训练，环境的刺激形成了这种意识的结构基础，人为构建起的选择压力（环境目标），使得这种结构在连接、网络的优胜劣汰中，保留了这种人类称为意识的响应模式，保留了这种人类称为”懂数学“"会聊天"的响应模式。即使最后是一个1+1都算不清的智障，只要他能适应环境刺激、对刺激作出符合环境目标的响应，比如用模拟的针扎他的模拟手指一下他会所手、有猎豹出没他会逃跑等等，他就达到了那种非全知全能的可塑意识模型的门槛，剩下的就只是通过目标环境选择，选择出蚂蚁还是选择出人类的问题了。对于 ThreeMind 而言，在不改变内核假设、非干预原则和可塑性的情况下，LLM 和 Transformer   的全部思想、实现思路，都可以拿来借鉴、参考、对比、融合乃至复刻。因为 LLM 已经证明了ThreeMInd 的某些设计是能走通的（ThreeMind 如果放弃可塑性，放弃非干预原则，在从没出现过LLM和Transformer 的平行宇宙，也能最终发展出 LLM）。所以 ThreeMind 和 Transformer  本质上是一个模型类别的两个方向，一个朝着大而全发展牺牲了可塑性（在我看来必然无法AGI）；一个放弃大而全，追求可塑性，我感觉是 AGI 的方向。如果 ThreeMInd 能成，再将 LLM 作为一个外置大脑，则真正的 AGI 完全体就诞生了。请将我的这段话整理成成文档放入 docs 的适当位置，中文版和英文版都要有。并且结尾要把我这段不那么流畅的原文贴上去作为原始引用和备忘。之后，你再谈谈你的看法

### Author's subsequent correction

> 补充：应该是激活活动停止即死亡
