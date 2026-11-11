# Multi-kernel research: preserving hypotheses while broadening mechanisms

[中文](../zh/kernel-evolution-principles.md) · [Implementation record](plans/multi-kernel-implementation.md)

## Boundaries confirmed on 2026-09-28

ThreeMind studies continuously stimulated systems with plastic structure and ongoing activity. Adaptation, retention, forgetting, transfer and autonomous responses are targets; human-readable language is not the sole criterion. **Activation activity stopping means death**, not plasticity stopping. This is the project's operational definition, not an established scientific test of consciousness.

New kernels may adopt different hypotheses. Original hypotheses, protocols and tests remain bound to the original kernel. This round preserves Git `b53fba1`, `threemind.causal/9` / `threemind.state/6`, runnable and default. Existing consciousnesses never silently acquire candidate dynamics. Engineering acceptance, improvement over controls, and interpretations concerning consciousness or AGI are separate conclusions.

Biology is one eligible basis, not the only one. Biological, physical and chemical evidence, and explicitly realizable, testable mathematical models, are eligible. Missing biological analogues do not disqualify a mechanism; invoking universal laws is not evidence by itself. Specify states, units, equations, input sources, locality, resources, numerical methods and limits. Distinguish empirical evidence, published models and project abstractions.

Kernels must not encode semantic answers, correct behaviors or fixed functional brain regions. Environment constraints and selection pressure may be applied as recorded external conditions. Thresholds, boundaries and initial conditions remain modeling choices: disclose and ablate them rather than hiding desired answers inside them.

Prefer local node/edge information and messages that actually arrived. Changes may affect the whole network through time and propagation. Observers, reports and external models must not covertly turn human judgments of importance into kernel protection rules. Receptive ranges, time scales and competition are explicit hypotheses, not licenses to manufacture associations. Unreadable inputs follow the same sensory mapping and dynamics.

## Candidate mechanisms and implementation

Transformer addressing, fast weights and time representations may inspire mechanisms; a small complete model may serve as a separate comparator or adapter. Inspiration is not a complete Transformer implementation or a mathematical equivalence. External knowledge, objectives and contribution are recorded separately. Predictions do not feed back by default. Remote models are explicit optional adapters; local independent operation remains fundamental.

Continuous activation and membrane/spiking dynamics have different state semantics and belong to different kernels. Parameter choices and ablations need not each define a kernel, but fundamental equations, structural growth and death criteria must be versioned. A membrane candidate must account for subthreshold voltage and synaptic current, not mistake an interval without spikes for death. Dormant structure and memory traces alone are not ongoing activity.

Declarative JSON selects trusted versioned operators and parameters, not embedded Python, JavaScript or JSONP. Research interpretation and native execution share definitions, states and witnesses. Standalone deployment binds operators and protocols; **learned weights and topology remain mutable**. A backend is not a scientific model; cross-kernel conversion is not ordinary restoration.

A task failure alone does not disprove the direction; a local effect does not prove consciousness. Validate adaptation, interference, reversal, temporal dependencies, nonlinguistic stimuli and unseen conditions, reporting negative results and resource boundaries.

## Original statements

Original Chinese text, including typos, is preserved below. The later clarification broadens the basis beyond biology.

> 好的。在借鉴 Transformer    以及其他已知的任何有益研究成果的时候，如果某个机制确实很好，但与 ThreeMind 的假设、原则不兼容，可以修改假设、增减原则。但有两个前提：原有的假设、原则必须保留并与原内核关联起来（关联的手段包括文档声明、协议版本的绑定、Test 的验证）；引入的新机制，必须是非认为预设倾向的（人为倾向只能通过施加环境选择压力有环境选择压力或其他外部约束去实现，不能写死在内核里），新机制的刺激来源必须有现实机制的依据（包括神经科学的证据、演化中的现象、人脑的机制等），不能是凭空捏造的，不能为了达到某种人类看来漂亮的效果而杜撰的。相比于漂亮的输入输出，ThreeMind更需要物理、化学、生物的真实机制，真实映射，即使这让输入输出难以被人类理解。人可以不知道狗在想什么，但无法否认狗有意识。人可以无法理解外星人，也无法断定外星人没有意识。ThreeMInd接受人类无法理解的自发存在，不接受人为塑造的提现木偶。此外，新引入的机制尽量是作用于简单的局部、做简单的事，但使得连接在时间、空间维度，在整体上，涌现出复杂现象。新引入的机制，应尽量避免全局遍历获得自己的入参，但它的出参可以在时间、空间维度上通过一系列传播影响整体。所有连接都按照一些简单的机制在被刺激改变，结果涌现出了复杂，这种复杂不是被塑造出来的。最终，即使输入人类完全无法理解的乱码，模型本身也会基于这团乱码涌现自己的模式，对于人类而言毫无意义，对于这个意识而言，那是一个有秩序的丰富的世界。我这段话的原文，以及你整理后的内容，可以写入 docs 的适当位置。你可据此继续完善计划。在你认为合适的时候，可以生成供你将来实施的plan

> ThreeMind 把对生物机制的模拟作为一条可行路线，但不排斥其他实现。我相信生物大脑只是众多AGI机制中的一种。所以可以稍微调整我的表述，没有生物机制依据，但有物理、化学基础，有宇宙法则支撑的，也可以作为一种内核方案。不因一种机制在生物中找不到就否定，如果它确实有益于AGI，或者确实达到了与生物机制类似的效果，则可以作为合格的机制引入。不能排斥仿生之外的可能性。

> 这次我们不必多选一，我们可以在一个统一的架子下，允许通过配置的方式实现多个内核。配置的方式不好实现或性能低的话，也可以直接代码写多个版本的。连续激活与膜电位等可分别支持，作为不同类型内核或内核的不同属性。还可以更灵活一些，有一个统一的框架或者编译器，然后内核的机制由JSON配置作为代码，编译器处理后可产出内核的二进制、脚本之类的，JSONP配置既可以解释执行方便研究和调试，也可以编译后去运行保证在机器人等生产环境的性能。你可评估，是直接写死代码，还是如何实现。我们这次不是只能做一个内核。

> 如果两种机制是两种完全不同的动力学，而不是统一动力学的不同属性选择，则应该作为两个内核。你评估看如何处理合适。我希望边界更清晰，不要为了省事而把两种本质不同的模型混在一起。但也不要拆得细碎，某些确实能通过简单的属性调整来控制的，则无需另外实现一个独立内核。
