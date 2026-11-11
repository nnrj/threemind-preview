# 2026-11-01补注：G3比较的是完整实现 / G3 compares complete implementations

本补注在首版报告和原包交付后追加。实验标准、原数据、成绩及首版报告均保留不变。

首版报告“使用同一局部约束信息”指信息来自同一公开的约束计算过程。具体处理不同：外部环境计算整数破坏数；ThreeMind输入适配器将其分为0、1、2、至少3四级，只教零破坏优先，使用25%随机探索；WalkSAT直接使用完整整数破坏数，预置零破坏优先和其余情况下的最小破坏规则，后者噪声概率为0.5。G3评估这些已登记的完整实现，明确由WalkSAT胜出。分数差同时包含适配、策略和查询方式的差异，不作为单独网络架构效应的估计。

G1的正常教学与打乱教学使用相同的输入离散化、读出器、查询时序和探索概率，二者均为98/192的结论不受此补注影响。G2的目标、匹配、假干预与恢复也使用相同的完整装置。

This dated addendum follows delivery of the first report and original archive. Criteria, data, scores and the first edition are unchanged.

The report's phrase “same local constraint information” refers to the same source of public constraint computations. Processing differs: the environment computes integer break counts; ThreeMind's adapter quantizes them into 0, 1, 2, or at least 3, teaches only the zero-break preference and uses 25% random exploration. WalkSAT directly uses integer counts, a built-in zero-break preference and otherwise a minimum-break rule with 0.5 noise. G3 compares these registered complete implementations, and WalkSAT remains the clear winner. The performance difference includes adapter, policy and querying differences; it is not an isolated estimate of network architecture.

G1 uses identical quantization, reader, timing and exploration under normal and shuffled teaching, so its 98/192 versus 98/192 finding is unchanged. All G2 intervention conditions likewise share the same complete apparatus.
