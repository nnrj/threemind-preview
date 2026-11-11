# 连续版机制归因：第二阶段补充方案

此方案在看到第一阶段部分结果后提出，不伪装为最初预注册。第一阶段中，短时资源开启而快痕迹、上下文关闭，仍然有两条提示各自匹配的结尾偏向；快痕迹和上下文都在但短时资源关闭，暂未出现同样的双向偏向。

待检验解释：前缀引起的弱活动，让不同边经历不同次数的资源释放；B 到达时，权重与剩余资源共同决定发送量。传播门槛可能使相近强度落到不同释放分支。因此对原教学正序的同一全开父本增加六组测试时配置，每组 A→B、D→B，共 12 个副本：默认；关闭抑制；资源恢复时间从 0.8 秒改为 0.08 或 8 秒；激活归零/逐边门槛 0.004 改为 0.0036 或 0.0044。

全部通过复制后的公开 reconfigure 接口变更。配置在复制时、等待一秒之前生效；训练父本、主线默认、感官映射、共同输入生边、读出器参数不变。门槛参数同时影响激活归零和逐边发送，不能把这一敏感性检查解释为只改变发送门槛的纯消融。关闭抑制也影响多条路径，需结合真实状态记录解释。

每 10 毫秒保存全部局部状态及公开事件，逐边追踪资源释放时刻、结尾实际到达量、峰值和时间。默认两副本必须复现第一阶段；否则暂停解释。新阶段仍包含在原 2 GiB/4 小时/42% 账户用量上限，不另开预算。不扫参数寻找最好成绩，只报告上述固定六组。已有结果原样保留。

English: This is a prospective amendment after partial factorial observations. Hypothesis: prefix activity changes per-edge release histories, and resource recovery plus learned weights and the existing threshold shape the later B response. Use the same all-on trained parent, 6 explicitly recorded test-time configurations × 2 cues: default, inhibition off, recovery tau 0.08/8 seconds (default 0.8), activation floor 0.0036/0.0044 (default 0.004). The last parameter couples zeroing and transmission thresholds and is not a selective transmission-only intervention. Record all local state every 10 ms and public event deliveries; require default replication. No default/kernel/training/encoding/edge-birth/readout change. These 12 copies remain within the original resource and account budgets. Publish all outcomes, without optimizing settings after seeing results.
