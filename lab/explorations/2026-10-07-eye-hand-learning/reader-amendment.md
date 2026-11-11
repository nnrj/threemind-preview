# E60：外设拟合稳定性追加 / Reader fitting amendment

2026-10-07，原52课和独立12示范完成，首版闭环比较正在执行；未开启confirmation留出集。

同一验证示范上，始终不发力的MSE为0.08754，共同/独立首版为0.20457/0.16144；训练误差也为0.15688/0.13720，高于零动作0.05968。读头平均输出存在明显偏移。这个事实提示尚不能把动作失败直接归为Core缺少意图；不宣称已知唯一原因。

追加外设/2：保留同一Transformer输入、序列、通道、标签、输出范围及共同/独立组织，仅在时序隐藏表示末端增加LayerNorm，输出层采用零权重、零偏置起步，避免没有学习就持续输出任意力。内部归一化是外设网络计算，不修改传给它的原始Core字段，也不改变Core、输入或证据。首版仍可完整加载。训练增加至最多4000步，逐100步记录验证曲线；这不是额外的Core教学。

先拟合两种组织与一个直接入射对照，只按原独立示范误差判断是否值得进入闭环。旧test已开始观察，后续旧test均视为诊断，最终confirmation在完成外设选择与纠错后才执行。所有候选保留，不能用某个好看的轨迹挑模型。

English: before using the confirmation holdout, first readers have validation MSE0.20457/0.16144 versus0.08754 for zero force, with similarly poor training fit. Add version2 with a final hidden LayerNorm and zero-initialized output layer, up to4000training steps and saved validation curves. Raw inputs, teacher labels, Core and sensory mappings stay unchanged; version1 remains loadable. Compare shared/separate/bypass on the same demonstration validation. Already viewed tests are diagnostics; confirmation is reserved until selection and correction finish.

## 同日更正：首版失败的工具原因已定位 / Same-day correction

在实际启用/2之前，梯度检查定位到批次采样错误：`32//len(b)`误用了单类样本数，应为`32//len(bins)`（类别数）。两类均超过32个样本后，每批为空，损失为NaN而反向梯度为零，只发生权重衰减。因此最初三个C-fit以及两个D闭环属于**未训练外设的工具失败证据**，不能用于判定Core不会注视、共同或独立中枢孰优。旧记录保留。加入非空数据/批次、有限训练损失检查及大样本确实降低误差的测试。后续拟合统一记录`continuous-motor-fit/2`，case名含`fit2`。原/1结构先正常重训；/2仅作为已登记的外设对照，不能把修正BUG的收益归给LayerNorm或零初始化。

Before fitting the proposed architecture/2, gradient inspection found a sampler bug: the divisor was the number of samples in a bin rather than the number of bins. Large bins produced empty batches, NaN loss and zero gradients; only weight decay occurred. The first three fits and two closed-loop evaluations therefore document an untrained-adapter tooling failure, not a Core or shared/separate-control result. Preserve them; reject empty/nonfinite fitting and test real loss reduction on large bins. Corrected fits carry `continuous-motor-fit/2` and `fit2` case identities. Retrain architecture/1 first; do not attribute the bug fix to architecture/2.
