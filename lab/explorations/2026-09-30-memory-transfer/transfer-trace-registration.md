# 迁移反向响应的观察补录 / Recording the reverse transfer response

查看原定迁移结果后追加：仅关节条件的 48 次检验均有原对应方向优势；完整、等剂量完整、惯性错位三组的 144 次检验均出现相反方向的积分优势。原定评分窗口从物理片段开始后 0.6 秒开始，不能据此知道输入过程中的活动。

使用余下 8 个实例预算，复演普通默认、种子 930101／930102、原场景、完整／仅关节、正负两方向，保留全部原输入及其递送时间。只在已有观察回调后附加全节点活动采样，不增加推进边界，不修改读出条件。记录实际内核采样时间，不能把批次结尾的状态冒充批次内某个事件时刻。

额外采样覆盖物理输入期间及原来的 5 秒检验；最大间隔由已有观察循环决定（20 ms），可能在同一模拟时刻多次采样。每个副本的最终完整内核状态哈希必须与原对应实例一致，否则视为工具干扰并停止解释，保留失败记录。比较输入期间、输入结束后至原评分起点、原评分期间的目标活动及抑制、直接／联想分量；不事后颠倒原评分答案，也不替换主要收敛指标。

此前未提示副本的时间轨迹可用于同一绝对时刻的局部对照：迁移检验与未提示记录只重叠 4.4 秒，若使用则明确标记这一范围，不补齐缺失的最后 0.6 秒。总预算恰为 1536 个实例，其他限制不变。该补录属于发现后的机制描述，不是独立新任务上的确认，也不验证反向现象的唯一原因。

After inspecting the original transfer matrix, add eight observation-only replays: ordinary preset, seeds 930101/930102, original physical domain, full/joint-only sensors and both directions. Capture all-node state after the existing observer callback without adding advancement boundaries. Require exact final Core-state hash equality with the original case. Record actual snapshot times, including duplicates, rather than attributing a batch-final snapshot to an earlier event. Compare during-input and post-input phases without relabelling answers. Existing no-cue traces provide only a 4.4-second absolute-time overlap; never fill the missing tail. Total reaches the existing 1536-instance cap. This is a post-discovery description, not proof of a unique mechanism.
