# ThreeMind 研究定位与文献备忘

[中文](literature-positioning.md) | [English](../en/literature-positioning.md)

## 范围与定位

本文是一份简短的研究定位与文献备忘，不是系统性文献综述。它记录最接近的既有研究传统，说明 ThreeMind 哪些部分具有、哪些部分不具有独特性，并列出可将设计直觉转化为实证贡献的实验方向。文献仅是深入阅读的起点，不等于认可其全部理论主张。

## 核心结论

ThreeMind 的组成性想法并不新：持续可塑性、联想激活、遗忘、具身感知/行动、注意与动态认知架构，都已有大量研究。也不存在一个成熟共识理论能够证明：把它们组合起来就会产生意识或 AGI。

ThreeMind 仍值得继续；其最终工程目标是实现人工意识。其可能的独特贡献，是把匿名内部状态、明确输入/输出边界、局部可塑动力学、持续外界耦合、生命周期记录和可复现对照组合在一起。任何疑似成功都应通过可证伪的动力学假设来检验，而不能仅凭未经检验的图样宣布意识。

## 最接近的研究传统

### 可塑循环动力学与持续学习

可塑循环网络、Hebbian 式学习、联想记忆和持续学习都是成熟研究家族。可微可塑性研究表明，带可塑连接的循环网络能被训练用于快速学习和类似记忆的任务；持续学习研究也指出一个与 ThreeMind 直接相关的问题：系统可能不只是遗忘旧材料，还会失去学习新材料的能力。

- Miconi、Clune、Stanley，*Differentiable plasticity: training plastic neural networks with backpropagation*（2018），[arXiv:1804.02464](https://arxiv.org/abs/1804.02464)。
- Dohare 等，*Maintaining Plasticity in Deep Continual Learning*（2023），[arXiv:2306.13812](https://arxiv.org/abs/2306.13812)。
- Morales、Mirasso、Soriano，*Unveiling the role of plasticity rules in reservoir computing*（2021），[arXiv:2101.05848](https://arxiv.org/abs/2101.05848)。

ThreeMind 的区别在于：把在线可塑、衰减和联想性触达作为首要观察对象，而不是将其作为针对基准奖励或监督损失优化出的组件。

### 具身、发展与感知运动组织

具身和发展式路线早已研究持续的躯体—环境耦合如何塑造学习。发展性神经模拟明确连接了发展轨迹、具身性和可塑性；Numenta 的 Thousand Brains Project 也主张以感知运动学习替代纯静态、数据中心式的学习观。

- Alicea 等，*Continual Developmental Neurosimulation Using Embodied Computational Agents*（2021），[arXiv:2103.05753](https://arxiv.org/abs/2103.05753)。
- Numenta，*Thousand Brains Project*，[官方公告](https://www.numenta.com/press/2024/11/20/thousand-brains-project/)。

ThreeMind 更窄的主张是方法论上的：适配器必须让载体的采样和遗漏显式可见；匿名 Core 不应暗中继承人类可读载体的意义。

### 整合式认知架构

OpenCog/CogPrime 是很接近的架构邻居。它包含注意分配、短/长期重要度、遗忘、扩散激活、记忆区分与具身接口；但它比 ThreeMind 的匿名内核基线更明确地采用符号结构与目标导向，也有意整合众多认知子系统。

- OpenCog，[Attention Allocation](https://wiki.opencog.org/w/Attention_Allocation)。
- OpenCog，[CogPrime Overview](https://wiki.opencog.org/w/CogPrime_Overview)。
- OpenCog，[框架概览](https://wiki.opencog.org/w/OpenCog%3AAbout)。

这种比较并不削弱 ThreeMind：ThreeMind 可以提出一个更小的主张——研究局部、可检查的动力学——而不采用预设符号知识图、目标，或理论预先划定的认知模块。

### 生物与整生物模拟

OpenWorm 追求的是另一种、更具生物学依据的目标：从底层构建整合神经系统、躯体、环境与行为验证的 *C. elegans* 虚拟体。它展示了整生物模拟的价值和难度，但并未提供已经完成的一般心灵或意识解决方案。

- OpenWorm，[建模方法](https://docs.openworm.org/modeling/)。
- OpenWorm，[项目概览](https://openworm.readthedocs.io/en/stable/projects/)。

ThreeMind 不是生物复制品，而是一个刻意抽象的比较系统：在尝试高保真生物物理之前，先询问哪些动力学成分可能重要。

### 意识理论

主要科学理论包括循环处理、全局工作空间、高阶理论、预测处理/主动推断和注意图式等。它们会与 ThreeMind 的个别想法相交，却没有收敛到一个已经验证的意识计算配方。当前 AI 意识研究通常把这些理论表述为候选指标性质，而非决定性测试。

- Butlin 等，*Consciousness in Artificial Intelligence: Insights from the Science of Consciousness*（2023），[arXiv:2308.08708](https://arxiv.org/abs/2308.08708)。
- Whyte 等，*On the Minimal Theory of Consciousness Implicit in Active Inference*（2024），[arXiv:2410.06633](https://arxiv.org/abs/2410.06633)。
- Czerner 等，*A Theoretical Computer Science Perspective on Consciousness*（2020），[arXiv:2011.09850](https://arxiv.org/abs/2011.09850)。

因此，ThreeMind 不应从重复结构、可读片段、视觉聚集或持久性推断意识；它们只是需要对照的测量结果。

## ThreeMind 可能的独特性

潜在原创性在于组合，而不在每个孤立机制：

1. 匿名节点和连接避免将刺激文本当作内部语义保存，同时保留带标签版本作比较仪器；
2. 感官适配器、躯体过滤、注意/竞争、Core 动力学、输出适配器、观察器和网络传输之间有明确因果边界；
3. 联想性经过可增强通路；遗忘被建模为缺少支持的连接状态衰减，而不是按年龄清理归档；
4. 持续外界接触、明确的死亡/无响应、快照、遗照、克隆和来源日志，使生命周期与干预历史可检查；
5. 同一平台可比较拓扑优先模型与可选空间模型，而不会把显示布局误认作内在几何。

在受控实验展示新的可复现动力学效应之前，这些首先是软件与方法贡献；但它们仍有价值，因为可复现性和污染控制常常缺失于非正式的“涌现演示”。

## 实验计划归档位置

可执行的统计指标、对照和实验目标属于实验工作台，而不是理论定位本文。它们已移入 [实验方法与待验证问题](../../lab/memos/zh/002_实验方法与待验证问题.md) 和 [对照组实验模块计划](../../lab/memos/zh/003_对照组实验模块计划.md)。本文只保留研究定位；实际执行后的正、负结果均进入带日期的 `lab/` 实验日志。

## 实务建议

应以实现人工意识为最终目标继续项目，并用**关于可塑动力学组织的可测、可复现实验**判断项目是否正在接近该目标。若某一具体路线唯一的证据只是对能动性或类语言输出的直觉印象，则应暂停或收窄该路线。既有研究意味着需要引用、比较和吸收前人，而不意味着这个特定实验平台已经冗余。
