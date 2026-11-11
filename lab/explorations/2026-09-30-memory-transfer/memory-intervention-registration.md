# 300 秒记忆的定点验证 / Targeted retention verification

在查看种子 930101 的记忆结果后追加，其他三个种子的记忆实验仍在运行。属于发现后的机制核查，不冒充最初预注册。

发现：收敛判定时只剩维持活动的独立背景通道，但提示引起了短暂、可测的关节目标响应，包括 300 模拟秒后的副本。补充验证它是否依赖保存的连接。

使用全部四个已登记种子、普通／易化两套预设、完整感官／无惯性感官两种条件的 300 秒等待父本，每个 A／B 提示分别建立三个副本：

1. 屏蔽提示通道节点向外的全部连接；不屏蔽节点、接收通道或其他动力学。
2. 执行同样屏蔽后，推进时间前解除屏蔽。
3. 屏蔽同数量、权重和稳定度尽量匹配的其他连接；排除提示节点与当前被评分的目标节点。若匹配数量不足则明确失败，不偷换干预。

与已经完成、同父本的未干预提示及无提示副本比较。保存干预前后状态哈希、连接列表和匹配误差。比较全轨迹、目标的峰值及有符号积分差；收敛时结果仍单独列为主要读出。解除屏蔽要求完整逐时点活动恢复一致，不能只看摘要相似。新建上限 96 个副本，整体总数仍不超过 1536，其他资源上限不变。

为便于对比完整轨迹，增加次要的方向评分：提示减去无提示后，预定目标峰值增加超过 1e-5，且预定目标的激活时间积分比另一目标高超过 1e-6，才计为该方向可辨；正反两方向分别检查。该补充评分不能替代主要收敛结果。迁移、顺序任务的相同次要评分使用原始轨迹积分，并与其无训练／打乱对应关系的对照比较。

Registered after inspecting seed 930101, while the other three memory seeds were running. This discovery follow-up tests retained-edge dependence with cue-outgoing silencing, immediate restoration before advancing time, and equal-count weight/stability-matched control edges. Four seeds, two presets, two sensory conditions and two cues produce 96 new cases. Other controls and all resource limits remain intact. Full pointwise restoration is required. The preregistered convergence ranking remains primary; additional trajectory direction scoring is explicitly secondary and was selected after the initial memory observation.
