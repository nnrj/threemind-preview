# ThreeMind 与既有网络机制的逐项对比

> 2026-11-11 公开节选：涉及私有会话定位、论文整理和投稿讨论的部分已省略。科研记录保留原日期，完整原件未改。


[中文](algorithmic-comparison.md) | [English](../en/algorithmic-comparison.md)

## 文档性质

本文依据当前 ThreeMind Core 源码和原始论文作机制级定位，不以画布外观或可读标签作类比。它不是“证明独创”的声明，也不把机制相似误写成实现相同。结论应随 Core 和对照实验更新。

## 当前 ThreeMind 的最小机制画像

当前统一内核具有以下关键性质：

- 匿名节点；明文标签属于外部观察注释，不参与动力学；
- 适配器把载体转换为有时间结构的刺激帧，直接触达感受通道；
- 激活沿**既有有向边**局部传播并衰减；
- 默认连接新生主要来自同一输入帧内局部共激活，权重、稳定度、支持度与 eligibility 在线变化；
- 未获支持的连接逐步衰减并可断开，联想触达也可贡献巩固；
- 可选空间基底、时间关联、局部抑制、能量模拟及显式计算预算；
- 没有监督目标、误差反向传播、全局语义词典或预先写入的关系三元组；
- 被动/时间区间读出与统计位于 Core 外，只观察输出。

因此，一个准确而克制的技术描述是：**ThreeMind 是一个拓扑可生长、持续在线可塑、带遗忘与可选局部抑制的事件/帧驱动循环图动力学实验系统。**

## 对比结论表

| 研究家族 | 相同或相近处 | 关键差异 | 当前判断 |
| --- | --- | --- | --- |
| Hebbian / cell assembly | 局部共同活动可增强关联；重复触达形成可再激活结构 | ThreeMind 不是单一 `Δw = ηxy`；还包含有向传播、连接新生、稳定度、eligibility、支撑度、遗忘和适配器边界 | **机制亲缘最近之一，但不等同标准 Hebb** |
| Oja 规则 | 都可从局部活动更新权重 | Oja 规则有明确归一化项并趋向主成分；ThreeMind 没有该方程或 PCA 目标 | **不同** |
| STDP | 都重视时间邻近与局部可塑性 | STDP 依赖精确的突触前/后 spike 时序和不对称时间窗；ThreeMind 目前以 tick、帧内共激活、传播触达和可选时间关联更新 | **概念相邻，实现不同；需对照** |
| 经典 Hopfield | 都是循环网络，可能出现状态重访或收敛样现象 | 经典模型通常固定规模、对称权重、预存模式并有能量下降保证；ThreeMind 权重可有向、拓扑在线生灭、持续受外界驱动，未定义 Lyapunov 能量 | **不是 Hopfield；“吸引子”尚待证明** |
| 现代 Hopfield | 都可能表现关联检索 | 现代 Hopfield 使用显式存储模式、连续状态/能量更新，与 attention 有解析等价；ThreeMind 无 key/query、softmax 或模式矩阵 | **不同** |
| Echo State / reservoir | 都利用循环瞬态、历史依赖和外部读出 | reservoir 通常保持循环池固定，只训练读出并要求 echo-state 条件；ThreeMind 让内部拓扑持续可塑，读出器不负责训练 Core | **动力学相近，学习对象相反** |
| 竞争学习 / ART | 都可能通过局部竞争形成选择性响应，并关心稳定—可塑性 | ART 有显式匹配、警戒和重置机制；ThreeMind 不预设类别匹配器，局部抑制仅由邻接动力学产生 | **部分相近，不等同** |
| Wilson–Cowan / Amari 神经场 | 都研究兴奋—抑制、稳定态、振荡与局部竞争 | 这些模型通常是连续群体/空间场方程；ThreeMind 是离散节点和动态连接图，空间还可关闭 | **现象层可比，方程与对象不同** |
| 普通反向传播 RNN | 都有循环状态和序列历史 | 后者以数据集、损失函数和 BPTT 优化固定参数；ThreeMind 无监督误差或反传，在线结构变化本身是观察对象 | **显著不同** |
| Transformer | 都可对序列输入形成上下文依赖输出 | Transformer 在层内做全局 self-attention，通常离线训练后推理；ThreeMind 只做局部邻接传播、持续在线改变拓扑，没有 token embedding 或注意力矩阵 | **架构和学习范式均不同** |
| 知识图谱/符号系统 | 画布都可显示节点和边，可读标签会造成视觉相似 | ThreeMind Core 无显式实体、谓词、三元组或查询语义；标签是外部仪器 | **仅外观相似，计算含义不同** |

## 关键文献依据

- Hebb 的细胞集合与活动依赖可塑性源自 *The Organization of Behavior*（1949；[书目信息](https://openlibrary.org/books/OL28404517M/The_organization_of_behavior)）。ThreeMind 与其有思想亲缘，但当前边更新方程是项目自己的工程模型。
- Hopfield 1982 模型讨论大量简单单元的集体计算性质，并以稳定状态存储记忆；其经典模型不是 ThreeMind 当前实现。[PNAS / PubMed](https://pubmed.ncbi.nlm.nih.gov/6953413/)
- Oja 规则以带归一化的局部更新得到主成分行为；ThreeMind 没有该目标。[DOI](https://doi.org/10.1007/BF00275687)
- Bi 与 Poo 的实验显示突触改变对精确 spike 时序的窄而不对称窗口敏感；ThreeMind 尚不是 spike 级 STDP。[原论文 PDF](https://www.gatsby.ucl.ac.uk/~pel/course_wuhan/papers/bi.poo_1998.pdf)
- Jaeger 的 Echo State 路线把循环池动力学与可训练读出分开；ThreeMind 的读出同样在外部，但循环图本身持续可塑。[Fraunhofer 记录](https://publica.fraunhofer.de/entities/publication/7d4a7eec-a22c-4df0-903d-93f9cd5aca02)
- Wilson–Cowan 用耦合非线性方程描述兴奋/抑制群体，并得到稳定态、滞后与极限环；可作为抑制动力学对照，而非当前 Core 的实现来源。[原论文 PDF](https://www.gatsby.ucl.ac.uk/~qhuys/theoretical_neuroscience/Wilson-Cowan72.pdf)
- Amari 研究侧抑制神经场的模式形成；ThreeMind 的局部抑制可以比较其现象，但空间/方程不同。[DOI](https://doi.org/10.1007/BF00337259)
- 现代 Hopfield 网络使用连续状态和能量函数，其更新与 Transformer attention 存在明确联系；这恰好说明为何 ThreeMind 的局部有向传播不能仅凭“收敛”归入该类。[OpenReview](https://openreview.net/forum?id=tL89RnzIiCd)

> **公开版删节／调整（2026-11-11，原文件第50-50行）：**省略论文正文、写作／投稿讨论或相应非公开文档链接；同段涉及的实验事实、技术说明与运行决定在公开节选中保留。完整原件未改。



- 反向传播网络按输出误差调整权重；ThreeMind 没有该训练信号。[Nature](https://doi.org/10.1038/323533a0)

## 哪些现象不能仅凭截图归类

“相同刺激重新激活相似结构”可由 Hebbian 式联想、reservoir 状态重访、Hopfield 吸引、输入编码碰撞或单纯衰减残留等多种机制产生。“总激活与抑制同步”“热点迁移”“词序看似纠正”也非任何单一模型的专属签名。只有在重复、扰动、恢复、盆地边界、能量或轨迹统计满足相应定义后，才可使用严格术语。

## 当前原创性判断

ThreeMind **不是对既有神经网络完全无关的全新数学门类**；其局部共同活动增强与循环传播明显属于既有连接主义和动力系统传统。它也**不是把 Hebb、Hopfield 或 reservoir 原样重做一遍**。当前最可能的贡献在于：匿名语义边界、适配器化持续输入、动态拓扑生灭、联想巩固与遗忘、局部抑制、生命周期/来源审计、时间区间读出以及可复现实验平台的组合。

该组合是否产生既有模型没有的动力学能力，不能靠先验争论解决，必须由[独立对照组实验计划](../../lab/memos/zh/003_对照组实验模块计划.md)直接比较。若结果与匹配的 Hebbian 循环图完全一致，应诚实收缩创新主张；若在相同资源与输入条件下呈现稳定可复现的差异，则差异本身才是科学贡献。
