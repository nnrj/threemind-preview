# 旧内核参数逐项对照

此表由 `scripts/audit-legacy-parameters.py` 从旧 RuntimeConfig 字段集合核对生成，不读取 data。已提供表示存在新实现与配置入口，不表示与旧动力学数值等价。待恢复项均未算作完成。

**此表只验证字段目录覆盖，不能证明功能完整。** 公式、默认值及缺失行为以[新旧内核行为核查](v2-kernel-behavior-audit.md)为准；旧表的“已提供”不代表行为保留获得验收。

| 旧参数 | 状态 | 新入口 / 安排 | 说明 |
| --- | --- | --- | --- |
| `tick_seconds` | 时间重定义 | step_us / Runtime.clock / speed | 数值分辨率与宿主调度分开，旧 tick 秒数不能原样解释。 |
| `activation_decay` | 时间重定义 | activation_tau | 每帧比例改为秒制指数时间常数。 |
| `propagation_gain` | 时间重定义 | propagation_rate / delay_us | 传播速率按模拟秒积分并保留正因果延迟。 |
| `propagation_activation_min` | 已提供 | propagation_activation_min | C1：传播源激活门槛，0 关闭；在途事件不受追溯修改。 |
| `node_activation_floor` | 已提供 | activation_floor | 显式消退阈值。 |
| `direct_gain` | 已提供 | direct_gain | 直接刺激增益。 |
| `learning_rate` | 时间重定义 | learning_rate | 每条外部事件的冲量系数；默认值有变，不能视为旧实验的等价数值。 |
| `edge_decay` | 时间重定义 | forgetting_rate | 按秒积分并包含稳定度保护。 |
| `edge_birth_weight` | 已提供 | birth_weight | 初始权重系数。 |
| `stability_gain` | 已提供 | stability_gain | 稳定度增长。 |
| `stability_decay` | 时间重定义 | stability_tau | 按模拟秒定义。 |
| `consolidation_first_gain` | 已提供 | first_gain | 首次巩固。 |
| `consolidation_repeat_gain` | 已提供 | repeat_gain | 重复巩固。 |
| `consolidation_intensity_gain` | 已提供 | intensity_gain | 强度巩固。 |
| `consolidation_associative_gain` | 已提供 | associative_gain | 联想经过巩固。 |
| `consolidation_cap` | 已提供 | consolidation_cap | C1：单次直接刺激巩固上限，默认保持 0.42。 |
| `prune_threshold` | 已提供 | prune_weight | 连接修剪阈值。 |
| `node_support_gain` | 已提供 | support_gain | 节点支持度增长。 |
| `node_support_decay` | 时间重定义 | support_tau | 按模拟秒定义。 |
| `node_support_prune_threshold` | 已提供 | prune_support | 支持度阈值；默认值及联合判定条件已有变化。 |
| `node_prune_after` | 规则替换 | 无活动、无抑制、无连接且无支持 | 旧版年龄条件是低支持、无活动、孤立节点删除的联合保护；新版移除该保护并改变阈值，需按行为审计讨论，不能称为纯等价换算。 |
| `association_window` | 时间重定义 | association_window_us | C1：包含边界的实际触达模拟时间窗，独立于 trace_tau。 |
| `edge_birth_policy` | 已提供 | edge_birth_policy | C1：默认同一刺激共同触达，temporal-association 为显式对照。 |
| `attention_budget` | 规则替换 | attention_budget | C4：恢复每感官帧幅度选择容量；不合并宿主 tick 内的多个帧；0 在竞争开启时阻断通道。 |
| `attention_competition_enabled` | 已提供 | attention_competition_enabled | C4：默认透明，显式竞争及全局标量调制、模拟时限、原始与通过帧证据、模型恢复和 UI 已接入。 |
| `edge_adaptation_limit` | 时间重定义 | edge_adaptation_limit | C2：固定模拟周期共享适应预算；账本、相位与计数随模型恢复。 |
| `propagation_limit` | 时间重定义 | propagation_limit | C2：固定数值步内正兴奋边操作预算，默认不限，记录跳过次数。 |
| `edge_birth_activation_product_min` | 已提供 | edge_birth_activation_product_min | C1：只限制新生连接，既有边仍可适应；0 关闭。 |
| `local_novelty_gain` | 已提供 | local_novelty_gain | C1：已有邻域、非零弱联想再入的生边加成，默认 0；无语义评分。 |
| `novelty_touch_reference` | 时间重定义 | novelty_touch_reference | C1：参考连续衰减的联想活动，不冒充旧 tick 瞬时量。 |
| `homeostasis_enabled` | 已提供 | homeostasis_enabled | C1：默认关闭的全局钳制对照，因果／数值边界执行。 |
| `target_total_activation` | 已提供 | target_total_activation | C1：比例压低过量活动，不抬高不足的激活。 |
| `topology_inhibition_enabled` | 已提供 | inhibition | 拓扑局部抑制开关。 |
| `inhibition_generation_gain` | 已提供 | inhibition_gain | 抑制生成。 |
| `inhibition_decay` | 时间重定义 | inhibition_tau | 按模拟秒定义。 |
| `inhibition_diffusion` | 时间重定义 | inhibition_diffusion_rate | 按秒转移有限抑制势。 |
| `inhibition_response_gain` | 已提供 | inhibition_response_gain | 分流响应。 |
| `inhibition_saturation` | 已提供 | inhibition_saturation | C1：状态与二进制模型支持大于 1 的抑制势，暂停调低按新上限限幅。 |
| `inhibition_propagation_min` | 时间重定义 | inhibition_propagation_min | C1：模拟秒流量门槛，乘步长后比较；自抑制生成不受此门槛控制。 |
| `energy_simulation_enabled` | 已提供 | energy_simulation_enabled | C3：默认关闭；直接响应、传播及抑制转移按实际量收费，外部供给不产生激活。 |
| `energy_initial_reserve` | 已提供 | energy_initial_reserve | C3：出生固定初值；恢复和已有账本开关不补发，旧版首次建账记录起点。 |
| `energy_capacity` | 已提供 | energy_capacity | C3：正容量；调低造成的已有储备舍弃记入账本。 |
| `energy_direct_cost` | 已提供 | energy_direct_cost | C3：对抑制及饱和后的实际直接响应收费，不足时限制响应量。 |
| `energy_associative_cost` | 已提供 | energy_associative_cost | C3：对已发出传播收费，抵达不重复收费。 |
| `energy_inhibition_cost` | 已提供 | energy_inhibition_cost | C3：实际转移收费，未付费余量保留在源。 |
| `irreversible_energy_death_enabled` | 已确认调整 | energy_starvation_damage_enabled | 2026-09-09：仅保留默认关闭的维护、缺能损伤；死亡统一按活动宽限期。 |
| `energy_maintenance_cost_per_node` | 时间重定义 | energy_maintenance_cost_per_node | C3：按节点实际存在的模拟秒积分，在因果／数值边界结算。 |
| `energy_maintenance_cost_per_edge` | 时间重定义 | energy_maintenance_cost_per_edge | C3：按连接实际存在的模拟秒积分，非观察调用次数。 |
| `energy_starvation_structural_decay` | 时间重定义 | energy_starvation_structural_decay | C3：按秒指数消退，由未付维护比例调节，显式损伤独立于学习开关。 |
| `energy_starvation_death_ticks` | 已确认移除 | quiescence_death_us | 2026-09-09：删除独立缺能期限；无激活宽限期不是饥饿参数换名。 |
| `response_epsilon` | 规则替换 | activation_floor + 在途兴奋事件 | 不再根据对刺激反应低就判断死亡。 |
| `unresponsive_window` | 规则替换 | 输入关闭且活动与在途兴奋均耗尽 | 不响应窗口不再作为默认生命终结规则；响应延迟仍需读出器测量。 |
| `max_nodes` | 已提供 | max_nodes | C2：显式节点容量，默认不限；拒绝新受体并计数，调低不删除已有结构。 |
| `max_edges` | 已提供 | max_edges | C2：显式连接容量，默认不限；拒绝新边并计数，既有边可继续适应。 |
| `random_seed` | 作用拆分 | RunSpec.seed / Config.seed | 环境与感官使用前者；后者是固定发育身份，C5 开启因果空间时用于确定性坐标，默认关闭时不影响演化。 |

合计 55 个旧 RuntimeConfig 字段都有目录映射；这不是剩余恢复工作数量。未等价保留、未充分说明的规则替换及配置类之外的缺失，见行为核查。空间、感官、读出与宿主设置不在该类中。
