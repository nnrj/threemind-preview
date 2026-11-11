# 多内核的小规模工程比较 / Small multi-kernel engineering comparison

日期 / Date: 2026-09-28。可重跑脚本：`scripts/compare-kernel-mechanisms.py`。

这是机制检查，不是配对记忆、关系推理或 AGI 实验。没有选择漂亮答案或修改文本映射。使用匿名通道 101、202，0～0.5 模拟秒内每 0.1 秒共同输入一次，0.65 秒单独输入 101，统一观察到 0.9 秒。协议、全部定义、37 次指标采样及最终模型保存在[原始 JSON](../../../docs/benchmarks/kernel-candidates-2026-09-28.json)。每个案例独立新建；不改动现有实验。

This is a mechanism check, not a paired-memory, relational-reasoning or AGI experiment. Anonymous channels 101 and 202 receive the same frame every 0.1 simulation seconds from 0 through 0.5; channel 101 alone is stimulated at 0.65. Each independently created case is observed through 0.9 seconds. Full definitions, protocol, 37 metric samples and final states are retained in the linked JSON. No existing experiment or text mapping was changed.

| 条件 / Case | 末次总激活或投影 / Final sum | 平均慢权重 / Mean slow weight | 发出量 / Sent |
| --- | ---: | ---: | ---: |
| causal/9 | 0.776001 | 0.267321 | 0.908006 |
| continuous/1 三算子关闭 / all new operators off | 0.776001 | 0.267321 | 0.908006 |
| continuous/1 默认 / defaults | 0.635281 | 0.261701 | 0.140567 |
| continuous/1 关闭短时资源 / no STP | 0.777524 | 0.267355 | 0.914497 |
| continuous/1 关闭快迹 / no fast trace | 0.635254 | 0.261700 | 0.140402 |
| continuous/1 关闭上下文 / no context | 0.635281 | 0.261701 | 0.140567 |
| lif/1 默认 / defaults | 0.00000207327 | 不适用此原核汇总 / different measurement | 0 nA |
| lif/1 关闭短时资源 / no STP | 0.00000207327 | 同上 / as above | 0 nA |
| lif/1 关闭 STDP / no STDP | 0.00000207327 | 同上 / as above | 0 nA |

- 关闭全部连续新算子与原核一致。短时资源明显减小本协议下的发出量；快迹作用较小。这里每个节点只有一个邻居，上下文算子没有多来源竞争，所以关闭它结果不变，不能据此断言它没有作用。
- LIF 本协议使用默认电流增益，没有越阈发放，仍存在阈下电位／电流活动。这支持“无脉冲不等于死亡”的工程检查；不是认知失败结论，也不比较其去极化投影与原核激活的大小。高电流校准、STDP 正反序及多来源上下文由专门单元测试覆盖。
- 九种条件的原始状态、逐点指标和脉冲输出经 Python／Rust 核对，采用原核数值容差；九个模型均精确恢复为自身保存哈希。

All-off continuous behavior matches the preserved kernel. Short-term resource depletion reduces emitted signal in this protocol; the fast-trace effect is small. With one neighbor per node there is no multi-source context competition, so context ablation is neutral here. This does not establish that the operator is ineffective.

Default LIF input stays subthreshold in this protocol: zero spikes coexist with evolving voltage/current. This checks that no spike does not imply death. It is neither a cognitive-failure conclusion nor a valid magnitude comparison between depolarization and original activation. Dedicated unit tests cover higher-current calibration, STDP order and multiple context sources.

All nine raw final states, sampled metrics and spike outputs match Python/Rust within baseline numerical tolerance. Each model restores with its own exact saved hash.

资源 / Resources: 每次脚本上限 60 秒、1 GiB RSS、2 MiB 输出；native 测得内核检查约 0.061 秒，结束时 RSS 29,806,592 字节，证据 1,064,579 字节。reference 约 0.229 秒，结束时 RSS 26,509,312 字节。计时不含 Python 启动，也不是正式性能基准或峰值内存报告。没有 GPU、云服务或长时间训练。Hard checks: 60 seconds, 1 GiB observed RSS and 2 MiB output; figures exclude interpreter startup and are not a formal performance benchmark or peak-memory measurement.

下一步应先校准输入／读出时间尺度及不同内核的刺激单位，再独立设计保持、干扰、反转、顺序和环境适应实验。此轮没有启动这些探索，也没有宣称研究假设已被证实。Next: calibrate sensory/readout timescales and per-kernel input units before separate retention, interference, reversal, sequence or adaptation experiments. Those exploratory experiments were not started here.
