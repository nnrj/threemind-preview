"""Public configuration catalogue and creation/continuation policy.

The catalogue describes real Core/Runtime fields. It does not implement dynamics
and is shared by every graphical configuration entry point.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from dataclasses import fields as dataclass_fields

from pydantic import ValidationError

from threemind_core.spec import BUDGET_DEFAULTS, DYNAMICS, ENERGY_DEFAULTS
from threemind_kernels.registry import DEFAULT_KERNEL, kernel_catalog, resolve_kernel
from threemind_runtime.body import BODY_CONFIGS
from threemind_runtime.energy_supply import EnergySupplyConfig
from threemind_runtime.live_media import LiveCaptureConfig
from threemind_runtime.media import MEDIA_CONFIGS
from threemind_runtime.readout_config import READOUT_CONFIGS
from threemind_runtime.sensory import INPUT_BUS_LIMITS, TEXT_LIMITS
from threemind_runtime.source_policies import SourcePolicies
from threemind_runtime.telemetry import telemetry_parameters
from threemind_runtime.world_schema import default_world

from .kernel_parameters import candidate_fields, kernel_defaults
from .protocols import RunSpec

CORE_IMMUTABLE = {"step_us", "seed", "energy_initial_reserve"}
PROTOCOL_IMMUTABLE = {
    "kernel_id",
    "world_protocol",
    "robot_protocol",
    "seed",
    "environment_seed",
    "replay",
    "phases",
    "intervention",
    "study_id",
    "condition",
    "block_seed",
}
PROTOCOL_IMMUTABLE |= {"text_sensor.encoding", "text_sensor.normalization", "text_sensor.channel_count"}
PROTOCOL_IMMUTABLE |= {
    f"{root}.{f.name}" for root, cls in MEDIA_CONFIGS.items() for f in dataclass_fields(cls) if f.metadata["immutable"]
}

# path, label, unit, group, description. Defaults and limits come from the
# executable contracts below, never from a second set of UI constants.
CORE_FIELDS = [
    ("plasticity", "持续可塑性", "", "basic", "允许刺激塑造连接、巩固和遗忘。关闭后保留传播，但停止可塑变化。"),
    ("inhibition", "拓扑局部抑制", "", "basic", "沿已有邻接关系产生和传播局部抑制，不添加新的兴奋连接。"),
    ("step_us", "数值步长", "μs", "time", "固定求解格点间隔。改变它属于数值收敛实验，应创建独立实例。"),
    ("delay_us", "因果传播延迟", "μs", "time", "新发出的内部信号的递送延迟；修改后，已经在途的事件保留原时间戳。"),
    (
        "propagation_interval_us",
        "传播节律",
        "μs",
        "time",
        "默认 100000（0.1 模拟秒）。传播和离散非线性操作的模型节律，独立于数值步长与显示刷新。修改后从生效时刻开始新周期。",
    ),
    (
        "quiescence_death_us",
        "无激活死亡宽限期",
        "μs",
        "time",
        "首次激活后，全部节点连续无激活达到此时长才死亡；默认 1 模拟秒。0 表示同一时刻事件处理完后立即判定，不代表关闭死亡。",
    ),
    (
        "node_prune_after_us",
        "孤立节点未触达期限",
        "μs",
        "pruning",
        "默认 80 模拟秒。须同时孤立、无激活、支持不足且超过此未触达期限才修剪；0 仅撤去等待期限。",
    ),
    (
        "eligibility_tau",
        "连接资格迹衰减时间常数",
        "s",
        "memory",
        "旧每 0.1 秒保留 0.78，换算为独立时间常数；资格迹影响稳定度损失。",
    ),
    ("activation_tau", "激活衰减时间常数", "s", "time", "无新触达时，激活按 exp(−Δt/τ) 衰减。"),
    (
        "trace_tau",
        "节点触达痕迹时间常数",
        "s",
        "time",
        "控制节点触达痕迹，旧每 0.1 秒保留 0.82；与连接资格迹分别配置。",
    ),
    ("inhibition_tau", "抑制衰减时间常数", "s", "inhibition", "控制局部抑制势的衰减速度。"),
    (
        "stability_tau",
        "连接稳定度损失时间尺度",
        "s",
        "memory",
        "每周期损失 Δt/τ × (1−资格迹)，是线性损失尺度，不是指数衰减；节点稳定度按旧机制在触达时增长。",
    ),
    (
        "support_tau",
        "节点支持度损失时间尺度",
        "s",
        "memory",
        "损失 Δt/τ × (1−节点稳定度)，是线性损失尺度；关闭请使用支持度衰减开关。",
    ),
    ("propagation_rate", "联想传播速率", "s⁻¹", "excitation", "沿既有有向连接发出延迟信号；0 表示不产生新的联想传播。"),
    ("direct_gain", "直接刺激增益", "", "excitation", "外部匿名通道对直接激活的增益。"),
    ("learning_rate", "连接学习率", "每次外部事件", "memory", "每次递送外部刺激的权重增量系数，不是每个数值步的增量。"),
    ("birth_weight", "新连接初始权重", "", "memory", "同一外部刺激中的共同触达形成新连接时使用。"),
    ("first_gain", "首次触达巩固增益", "", "memory", "首次共同触达时的巩固增益。"),
    ("repeat_gain", "重复触达巩固增益", "", "memory", "重复直接触达时的巩固增益。"),
    (
        "intensity_gain",
        "刺激强度巩固增益",
        "",
        "memory",
        "默认 0.075，开启额外强刺激巩固；设为 0 关闭。额外项乘以 max(0, 输入强度 − 1)，输入强度大于 1 才触发；关闭后普通触达仍可巩固。",
    ),
    ("associative_gain", "联想经过巩固增益", "", "memory", "已有连接被联想经过时的局部巩固贡献。"),
    ("stability_gain", "稳定度增长增益", "", "memory", "触达对稳定度增长的贡献。"),
    ("support_gain", "节点支持度增益", "", "memory", "触达对节点支持度增长的贡献。"),
    ("forgetting_rate", "连接遗忘速率", "s⁻¹", "pruning", "按模拟时间和稳定度保护计算权重衰减。"),
    ("inhibition_gain", "抑制生成增益", "", "inhibition", "活动产生局部抑制的强度。"),
    ("inhibition_diffusion_rate", "抑制扩散速率", "s⁻¹", "inhibition", "沿既有拓扑邻接扩散有限抑制势。"),
    ("inhibition_response_gain", "抑制响应增益", "", "inhibition", "抑制势对节点响应的分流强度。"),
    ("activation_floor", "激活消退阈值", "", "pruning", "低于该值的衰减活动归零，参与消退及生命周期判定。"),
    ("prune_weight", "连接修剪阈值", "", "pruning", "可塑性开启时，权重低于该阈值的连接可被移除。"),
    (
        "prune_support",
        "节点回收支持度阈值",
        "",
        "pruning",
        "与节点活动及连接状态共同决定回收；新版仅手动模式生效，0切换至死节点保持时间。",
    ),
    (
        "max_nodes",
        "模型节点容量",
        "个",
        "resources",
        "留空不限，0 禁止新受体出生。调低不删除已有节点；每次拒绝均计入模型资源账本。",
    ),
    (
        "max_edges",
        "模型连接容量",
        "条",
        "resources",
        "留空不限，0 禁止新连接。已有连接仍可变化，达到容量后新边请求会记录为拒绝。",
    ),
    (
        "propagation_limit",
        "每周期兴奋传播预算",
        "边／传播周期",
        "resources",
        "留空不限。按源激活、连接权重及身份顺序选择正传播，记录未发送边数；不限制抑制扩散。",
    ),
    (
        "edge_adaptation_limit",
        "每周期连接适应预算",
        "次／传播周期",
        "resources",
        "留空不限。共同触达适应与传播巩固共享传播周期长度的时间窗预算，暂停和观察不补发；显式修改传播周期会重置本窗用量。",
    ),
    (
        "propagation_activation_min",
        "传播源激活下限",
        "",
        "optional",
        "可选截断对照；低于该值的源不发出联想信号。0 关闭额外截断，既有在途事件不变。",
    ),
    ("consolidation_cap", "单次巩固上限", "", "memory", "限制每个节点从一次直接刺激获得的巩固冲量，默认 0.42。"),
    (
        "edge_birth_policy",
        "连接形成策略",
        "",
        "optional",
        "默认同一刺激共同触达。时窗对照允许最近实际触达且仍活动的节点连接到当前实际触达节点；不预造连接。",
    ),
    (
        "association_window_us",
        "时窗生边窗口",
        "μs",
        "optional",
        "时窗对照的包含边界窗口；参考节点最后一次实际正触达，包括内部信号，独立于资格痕迹衰减。",
    ),
    (
        "edge_birth_activation_product_min",
        "新连接激活乘积下限",
        "",
        "optional",
        "按旧候选规则限制共同激活候选，包括出生与已有边更新。0 关闭额外门槛，不限制独立传播巩固。",
    ),
    (
        "local_novelty_gain",
        "局部新颖巩固增益",
        "",
        "optional",
        "只对已有连接邻域中的非零弱联想再入给予一次生边加成。0 关闭；不是输入语义或新词评分。",
    ),
    (
        "novelty_touch_reference",
        "新颖联想参考量",
        "",
        "optional",
        "局部新颖使用的衰减联想活动参考量；没有联想再入不算新颖，达到参考量时加成为 0。",
    ),
    (
        "homeostasis_enabled",
        "启用全局激活钳制",
        "",
        "optional",
        "显式全局资源对照，默认关闭。每个因果／数值边界按比例压低过大的总激活。",
    ),
    (
        "target_total_activation",
        "全局激活目标上限",
        "",
        "optional",
        "只在全局钳制开启时使用；不放大低激活，不参与显示档位。",
    ),
    (
        "inhibition_saturation",
        "抑制势饱和上限",
        "",
        "inhibition",
        "软饱和曲线 cap × tanh(q/cap) 的尺度，默认 1；按传播节律执行，非每次数值小步硬封顶。",
    ),
    (
        "inhibition_propagation_min",
        "抑制扩散流量下限",
        "势／次传播",
        "optional",
        "默认每次传播门槛 0.002，不乘数值步长；0 关闭截断。生成的自抑制不受此门槛限制。",
    ),
    (
        "seed",
        "内核身份种子",
        "",
        "identity",
        "创建后固定。因果空间开启时，用于可复现的发育几何；关闭空间时不参与连接选择。环境与感官种子另行配置。",
    ),
]

CORE_FIELDS += [
    (
        f"{name}_decay_enabled",
        f"启用{label}衰减",
        "",
        group,
        "关闭后相应随时间损失为零；保留时间常数以便重新启用，不将 τ=0 解释为关闭。",
    )
    for name, label, group in (
        ("activation", "激活", "time"),
        ("trace", "节点痕迹", "time"),
        ("inhibition", "抑制", "inhibition"),
        ("eligibility", "连接资格迹", "memory"),
        ("stability", "连接稳定度", "memory"),
        ("support", "节点支持度", "memory"),
    )
]

CORE_FIELDS += [
    (
        "energy_simulation_enabled",
        "启用能量记账",
        "",
        "energy",
        "默认关闭的实验资源约束；内核不会自行补给，计量不代表焦耳。",
    ),
    (
        "energy_initial_reserve",
        "初始能量储备",
        "实验单位",
        "energy",
        "出生时赋予一次；已有账本的开关和恢复不补发。旧动力学只读，不自动升级。",
    ),
    (
        "energy_capacity",
        "能量储备容量",
        "实验单位",
        "energy",
        "外部供给最多填充到此值；暂停调低时，超过容量的储备记入舍弃账本。",
    ),
    (
        "energy_direct_cost",
        "直接响应能量成本",
        "单位／激活量",
        "energy",
        "直接刺激在目标抑制和饱和之前按触达量收费；储备不足降低可负担的触达量。",
    ),
    (
        "energy_associative_cost",
        "联想传播能量成本",
        "单位／传播量",
        "energy",
        "只对实际允许发出的兴奋传播收费，抵达目标时不重复扣费。",
    ),
    (
        "energy_inhibition_cost",
        "抑制扩散能量成本",
        "单位／转移量",
        "energy",
        "按实际转移的抑制势收费，不足时保留未转移的抑制势。",
    ),
    (
        "energy_starvation_damage_enabled",
        "启用缺能结构损伤",
        "",
        "energy",
        "默认关闭；与能量记账同时开启后，维护成本及缺能侵蚀生效。缺能不清空激活、不独立判死。",
    ),
    (
        "energy_maintenance_cost_per_node",
        "节点维护成本",
        "单位／节点／秒",
        "energy",
        "按节点实际存在的模拟时长积分，在实际因果与数值边界结算。",
    ),
    (
        "energy_maintenance_cost_per_edge",
        "连接维护成本",
        "单位／连接／秒",
        "energy",
        "按连接实际存在的模拟时长计费；观察或暂停不重置计数。",
    ),
    (
        "energy_starvation_structural_decay",
        "饥饿结构侵蚀速率",
        "s⁻¹",
        "energy",
        "未付维护比例加快连接权重、稳定度与节点支持度的指数消退；显式损伤独立于可塑学习。",
    ),
]

CORE_FIELDS += [
    (
        "attention_competition_enabled",
        "启用输入注意竞争",
        "",
        "attention",
        "默认透明。启用后在每个感官帧实际递送时选择通道；不按相关性、新颖度或语义排序。",
    ),
    (
        "attention_budget",
        "每帧注意通道容量",
        "通道／感官帧",
        "attention",
        "默认 28，关闭竞争时不起筛选作用；0 在启用竞争时阻断全部通道。并列保持原始帧顺序。",
    ),
]

CORE_FIELDS += [
    (
        "spatial_embedding",
        "启用因果空间基底",
        "",
        "spatial",
        "默认关闭。开启会改变连接适应、传播和可选竞争；坐标是显式发育先验，不是自发空间组织。",
    ),
    (
        "spatial_dimensions",
        "因果空间维数",
        "维",
        "spatial",
        "1～64 维。由固定内核身份种子和节点身份生成；暂停改变维数保留前面的坐标轴，在途事件不改写。",
    ),
    (
        "neighborhood_enabled",
        "启用空间邻域约束",
        "",
        "spatial",
        "限制半径之外的连接适应，并对半径内兴奋传播作距离衰减。抑制仍按已有拓扑传递。",
    ),
    (
        "spatial_radius",
        "空间邻域半径",
        "基底坐标单位",
        "spatial",
        "正半径。缩小不删除已有连接；空间竞争也使用此半径，与邻域开关独立。",
    ),
    (
        "spatial_competition_rate",
        "空间竞争速率",
        "每模拟秒",
        "spatial",
        "默认 0。固定数值边界上，已有半径内有向边的较强源压低较弱目标；使用同一边界快照避免遍历次序偏差。",
    ),
]

RUN_FIELDS = [
    ("kernel_id", "意识内核", "", "basic", "科学模型与版本；创建后固定，后端选择不会改变动力学。"),
    (
        "environment",
        "环境与感官来源",
        "",
        "basic",
        "选择当前实例连接的物理环境或外部输入入口。暂停后更换环境会重置适配器，已有在途信号仍按原时间递送。",
    ),
    (
        "clock",
        "时钟模式",
        "",
        "basic",
        "实时模式绑定宿主单调时钟；尽速训练只加快计算，不改变模拟时间单位。宿主遥测要求实时模式。",
    ),
    (
        "duration_s",
        "运行时长（模拟秒）",
        "s",
        "basic",
        "可选，留空表示持续运行（无限）。填写时从本次起点计量模拟秒数，到期停止计算并保留状态，不等同于意识死亡。",
    ),
    (
        "seed",
        "感官身份种子",
        "",
        "basic",
        "决定感官通道、执行器映射与躯体过滤身份；独立环境种子为空时，也用于环境随机化。创建后固定。",
    ),
    (
        "environment_seed",
        "环境随机化种子",
        "",
        "senses",
        "留空沿用感官身份种子，保持旧行为。仅模拟物理与合成来源使用，其他来源保留该配置但不产生随机刺激。配对实验由区组种子列表管理，此处留空。",
    ),
    ("speed", "时间倍率", "倍", "basic", "仅指定倍率模式使用。实时为 1 倍；尽速模式不受该值限制。"),
    (
        "sample_us",
        "观测采样间隔",
        "μs",
        "recording",
        "保存研究指标的模拟时间间隔。该值影响证据分辨率，不影响显示刷新率。",
    ),
    (
        "checkpoint_us",
        "恢复检查点间隔",
        "μs",
        "recording",
        "按模拟时间提交恢复状态；正常模式还保留最多约 2 秒宿主时间的提交边界。",
    ),
    ("trace", "详细动力学追踪", "", "recording", "每个数值边界保存完整恢复状态，存储开销明显增加。"),
    (
        "record_spikes",
        "记录脉冲事件",
        "",
        "recording",
        "脉冲候选保存实际发放时间及节点；关闭只影响记录，不改变动力学。",
    ),
    (
        "max_channels",
        "每帧感官通道上限",
        "通道",
        "senses",
        "留空表示不限制。显式设置后按幅度选择通道，会改变实验输入，不能当作纯显示优化。",
    ),
    (
        "actuator_feedback",
        "身体动作反馈",
        "",
        "senses",
        "在模拟身体环境中，将匿名激活映射为身体动作，再由物理环境形成后续感觉。",
    ),
]
CHOICES = {
    "environment": [
        ("mujoco", "模拟物理环境 · 平面身体"),
        ("world", "可配置物理世界与躯体"),
        ("robot", "机器人任务 · 原始力矩与可选控制器"),
        ("host", "本机物理遥测 · CPU 与内存"),
        ("manual", "手动递送匿名刺激"),
        ("replay", "记录输入重放"),
        ("ambient", "合成环境场 · 显式实验载体"),
    ],
    "clock": [("realtime", "实时 · 与物理时间关联"), ("scaled", "指定时间倍率"), ("unbounded", "尽速训练")],
}


def default_spec(kernel_id=None):
    kernel_id = resolve_kernel(kernel_id).kernel_id
    return RunSpec(
        kernel_id=kernel_id,
        config=asdict(resolve_kernel(kernel_id).configuration()),
        activity_readout={"enabled": True, "analysis_version": 2, "interval_us": 20000, "periodic_max_samples": 60},
        host_telemetry={"intensity": 0.2},
        process_telemetry={"intensity": 0.2},
        runtime_telemetry={"intensity": 0.2},
    ).model_dump()


def catalogue(kernel_id=None):
    from threemind_runtime.stimulus_presets import TEXT_INTENSITY_PRESETS, research_presets

    defaults = default_spec()
    fields = []
    for key, label, unit, group, hint in CORE_FIELDS:
        value = defaults["config"][key]
        item = {
            "path": f"config.{key}",
            "label": label,
            "unit": unit,
            "group": group,
            "hint": hint,
            "type": "integer"
            if key in BUDGET_DEFAULTS
            else {bool: "boolean", int: "integer", float: "number", str: "string"}[type(value)],
            "default": value,
            "immutable": key in CORE_IMMUTABLE,
            "nullable": key in BUDGET_DEFAULTS,
            "kernels": [
                "threemind.causal/9",
                "threemind.continuous/1",
                "threemind.continuous-memory/1",
                "threemind.continuous-memory/2",
                "threemind.continuous-memory/3",
                "threemind.continuous-memory/3.1",
                "threemind.continuous-memory/4",
                "threemind.continuous-memory/5",
                "threemind.continuous-memory/5.1",
                "threemind.continuous-memory/5.2",
                "threemind.continuous-memory/5.3",
            ],
        }
        if type(value) in (float, int) or key in BUDGET_DEFAULTS:
            item["minimum"] = (
                1
                if key
                in (
                    "step_us",
                    "delay_us",
                    "propagation_interval_us",
                    "association_window_us",
                )
                else 0
            )
            if key.endswith("_tau"):
                item["exclusiveMinimum"] = 0
            if type(value) is int or key in BUDGET_DEFAULTS:
                item["maximum"] = 2**53 - 1
            if key == "birth_weight":
                item["maximum"] = 1
            if key in ("activation_floor", "prune_weight"):
                item["exclusiveMaximum"] = 1
            if key in (
                "propagation_activation_min",
                "consolidation_cap",
                "edge_birth_activation_product_min",
                "local_novelty_gain",
                "novelty_touch_reference",
            ):
                item["maximum"] = 1
            if key in ("novelty_touch_reference", "target_total_activation", "inhibition_saturation"):
                item["exclusiveMinimum"] = 0
            if key in ("inhibition_saturation", "inhibition_propagation_min"):
                item["maximum"] = 1_000_000
            if key in ENERGY_DEFAULTS and type(value) is float:
                item["maximum"] = 1e12
            if key == "energy_capacity":
                item["exclusiveMinimum"] = 0
            if key == "attention_budget":
                item["maximum"] = 100000
            if key == "spatial_dimensions":
                item.update(minimum=1, maximum=64)
            if key == "spatial_radius":
                item.update(exclusiveMinimum=0, maximum=1e6)
            if key == "spatial_competition_rate":
                item["maximum"] = 1e6
        if key == "edge_birth_policy":
            item["choices"] = [("co-stimulus", "同一刺激共同触达（默认）"), ("temporal-association", "时窗关联对照")]
        fields.append(item)
    run_schema = RunSpec.model_json_schema()
    for key, label, unit, group, hint in RUN_FIELDS:
        rule = run_schema["properties"][key]
        numeric = next((r for r in rule.get("anyOf", []) if r.get("type") != "null"), rule)
        fields.append(
            {
                **{
                    k: v
                    for k, v in numeric.items()
                    if k in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "type")
                },
                "path": key,
                "label": label,
                "unit": unit,
                "group": group,
                "hint": hint,
                "default": defaults[key],
                "immutable": key in PROTOCOL_IMMUTABLE,
                "nullable": key in ("max_channels", "environment_seed", "duration_s"),
                "null_label": {"environment_seed": "沿用感官身份种子", "duration_s": "持续运行（无限）"}.get(key),
                "choices": [(k["kernel_id"], f'{k["display_name"]}（{k["description"]}）') for k in kernel_catalog()]
                if key == "kernel_id"
                else CHOICES.get(key),
            }
        )
        if key == "environment":
            fields.append(
                {
                    "path": "robot_protocol",
                    "label": "机器人任务与控制协议",
                    "unit": "",
                    "group": "basic",
                    "hint": "选择躯体、感官、控制模式和环境目标；创建后固定。",
                    "type": "robot",
                    "default": None,
                    "immutable": True,
                    "nullable": True,
                }
            )
            fields.append(
                {
                    "path": "world_protocol",
                    "label": "世界与躯体协议",
                    "unit": "",
                    "group": "basic",
                    "hint": "独立配置物理、感官和执行器；协议在创建后固定，可从世界库选择或新建。",
                    "type": "world",
                    "default": None,
                    "immutable": True,
                    "nullable": True,
                }
            )
    for path, label, unit, hint, choices in (
        ("text_sensor.enabled", "启用文本感官", "", "关闭后拒绝新的文本载体；已经接收的帧仍按原配置递送。", None),
        (
            "text_sensor.encoding",
            "文本感官编码",
            "",
            "匿名分布式与外部标签观察的脉冲完全相同；明文字符是独立的逐字符对照，不为内核赋予语义。",
            [
                ("anonymous-distributed", "匿名分布式"),
                ("labeled-observation", "外部标签观察"),
                ("literal-character", "明文字符对照"),
            ],
        ),
        (
            "text_sensor.normalization",
            "文本规范化",
            "",
            "原始载体始终完整保留。NFKC 只在感官编码前应用，空格与换行不删除。",
            [("NFKC", "Unicode NFKC"), ("none", "保留原始字符")],
        ),
        (
            "text_sensor.channel_count",
            "分布式感受通道数",
            "个",
            "字节、字节对和位置特征折叠到有限感受器。明文字符模式按字符分配独立通道，不使用此数量。",
            None,
        ),
        (
            "text_sensor.frame_characters",
            "每帧字符数",
            "字符",
            "按字符边界分帧，完整载体不截断；跨帧上下文字节特征保留。",
            None,
        ),
        (
            "text_sensor.frame_interval_us",
            "文本帧间隔",
            "μs",
            "各帧在不同模拟时刻递送，避免把长载体变为一次全局共同触达。",
            None,
        ),
        (
            "text_sensor.gain",
            "文本感官增益",
            "倍",
            "缩放感受器幅度，再限制到 [0, 1]；与提交载体时的刺激强度分开记录。",
            None,
        ),
        (
            "text_sensor.max_carrier_characters",
            "单次文本接收上限",
            "字符",
            "超限整条拒绝并提示，不自动裁剪。可按研究负载提高。",
            None,
        ),
        (
            "input_bus.max_pending_frames",
            "待递送帧预算",
            "帧",
            "输入接收的资源预算，与节点/连接或显示数量无关。预算满时整个新载体被拒绝。",
            None,
        ),
        (
            "input_bus.max_pending_channels",
            "待递送通道条目预算",
            "条",
            "累计待处理帧中的通道条目，防止突发载体耗尽内存；不截断已接收输入。",
            None,
        ),
    ):
        root, key = path.split(".")
        value = defaults[root][key]
        rule = (TEXT_LIMITS if root == "text_sensor" else INPUT_BUS_LIMITS).get(key)
        fields.append(
            {
                "path": path,
                "label": label,
                "unit": unit,
                "hint": hint,
                "group": "text" if root == "text_sensor" else "transport",
                "default": value,
                "immutable": path in PROTOCOL_IMMUTABLE,
                "type": "boolean"
                if type(value) is bool
                else "integer"
                if type(value) is int
                else "number"
                if type(value) is float
                else "string",
                "choices": choices,
                **(
                    {"minimum": rule[0], "maximum": rule[1]}
                    if rule
                    else {"minimum": 0, "maximum": 100}
                    if key == "gain"
                    else {}
                ),
            }
        )
    for root, cls in (
        MEDIA_CONFIGS
        | READOUT_CONFIGS
        | BODY_CONFIGS
        | {"live_capture": LiveCaptureConfig, "energy_supply": EnergySupplyConfig, "source_policies": SourcePolicies}
    ).items():
        for f in dataclass_fields(cls):
            fields.append(
                {
                    **{k: v for k, v in f.metadata.items() if v is not None},
                    "path": f"{root}.{f.name}",
                    "group": root,
                    "default": f.default,
                    "type": "number"
                    if f.default is None
                    else {bool: "boolean", int: "integer", float: "number", str: "string"}[type(f.default)],
                }
            )
    for root, path, field, default, label in telemetry_parameters():
        fields.append(
            {
                **{k: v for k, v in field.metadata.items() if v is not None},
                "path": f"{root}.{path}",
                "label": f"{label} · {field.metadata['label']}",
                "group": root,
                "default": default,
                "type": {bool: "boolean", int: "integer", float: "number"}[type(default)],
            }
        )
    fields.extend(candidate_fields())
    for item in fields:
        if item["path"] == "record_spikes":
            item["kernels"] = ["threemind.lif/1"]
        if item["group"] == "energy_supply":
            item["kernels"] = [
                "threemind.causal/9",
                "threemind.continuous/1",
                "threemind.continuous-memory/1",
                "threemind.continuous-memory/2",
                "threemind.continuous-memory/3",
                "threemind.continuous-memory/3.1",
                "threemind.continuous-memory/4",
                "threemind.continuous-memory/5",
                "threemind.continuous-memory/5.1",
                "threemind.continuous-memory/5.2",
                "threemind.continuous-memory/5.3",
            ]
    for item in fields:
        if item["path"] in ("config.propagation_limit", "config.edge_adaptation_limit"):
            item["kernels"] = [
                k
                for k in item.get("kernels", ())
                if k not in ("threemind.continuous-memory/3", "threemind.continuous-memory/3.1", "threemind.continuous-memory/4", "threemind.continuous-memory/5", "threemind.continuous-memory/5.1", "threemind.continuous-memory/5.2", "threemind.continuous-memory/5.3")
            ]
        if item["path"] in (
            "config.homeostasis_enabled",
            "config.target_total_activation",
            "config.spatial_competition_rate",
            "config.attention_competition_enabled",
            "config.attention_budget",
            "config.edge_birth_policy",
            "config.association_window_us",
            "config.step_us",
        ):
            item["kernels"] = [k for k in item.get("kernels", ()) if k not in ("threemind.continuous-memory/4", "threemind.continuous-memory/5", "threemind.continuous-memory/5.1", "threemind.continuous-memory/5.2", "threemind.continuous-memory/5.3")]
    # Reuse the actual /5.3 field descriptions while keeping R48 identity,
    # defaults and constraints separate from every historical version.
    from .kernel_parameters import weight_decay_fields
    fields.extend(weight_decay_fields(fields))
    for item in fields:
        item.update(scope="instance", target="new-instance or selected individual",
                    source="kernel/runtime executable default",
                    effect="new-instance only" if item.get("immutable") else "pause before updating an existing individual")
    # Historical kernels own their accepted field sets and validation. Modern
    # constraints must not be imposed on a similarly named historical field.
    labels = {item["path"]: item for item in fields if item["path"].startswith("config.")}
    for descriptor in kernel_catalog():
        identity = descriptor["kernel_id"]
        if identity != "unified-associative" and identity not in {f"threemind.causal/{n}" for n in range(1, 9)}:
            continue
        for key, value in resolve_kernel(identity).config_fields().items():
            original = labels.get(f"config.{key}", {})
            field = {
                "path": f"config.{key}", "label": original.get("label", key),
                "unit": original.get("unit", ""), "group": original.get("group", "legacy"),
                "hint": f'{descriptor["display_name"]} · 历史版本原始参数；按该版本校验。',
                "type": {bool: "boolean", int: "integer", float: "number", str: "string"}.get(type(value),
                         "number" if key in ("propagation_activation_min", "edge_birth_activation_product_min") else "integer"),
                "default": value, "nullable": value is None, "kernels": [identity],
                "immutable": key in ("step_us", "seed", "tick_seconds"),
                "scope": "instance", "target": "new-instance or selected individual",
                "source": "historical kernel executable default",
                "effect": "new-instance only" if key in ("step_us", "seed", "tick_seconds") else "pause before updating an existing individual",
            }
            if identity == "unified-associative" and key == "sensory_encoding":
                field["choices"] = [(name, name) for name in ("anonymous-distributed", "legacy-labeled", "labeled-observation", "literal-character")]
            fields.append(field)
    if kernel_id is not None:
        identity = resolve_kernel(kernel_id).kernel_id
        defaults = default_spec(kernel_id=identity)
        fields = [item for item in fields if not item.get("kernels") or identity in item["kernels"]]
        for item in fields:
            if item["path"].startswith("config.") and item["path"][7:] in defaults["config"]:
                item["default"] = defaults["config"][item["path"][7:]]
    for item in fields:
        if item["path"] in {"text_sensor.encoding", "text_sensor.channel_count", "text_sensor.normalization",
                            "text_sensor.gain", "text_sensor.frame_interval_us"}:
            item["kernels"] = [row["kernel_id"] for row in kernel_catalog() if row["kernel_id"] != "unified-associative"]
    if kernel_id == "unified-associative":
        fields = [item for item in fields if not item.get("kernels") or kernel_id in item["kernels"]]
    return {
        "schema": "threemind.configuration/1",
        "text_intensity_presets": TEXT_INTENSITY_PRESETS,
        "research_presets": research_presets(),
        "dynamics": DYNAMICS,
        "supported_dynamics": [row["kernel_id"] for row in kernel_catalog()],
        "kernels": kernel_catalog(),
        "kernel_defaults": kernel_defaults(),
        "defaults": defaults,
        "world_default": default_world().model_dump(mode="json"),
        "fields": fields,
        "run_schema": run_schema,
        "immutable": [f"config.{k}" for k in sorted(CORE_IMMUTABLE)] + sorted(PROTOCOL_IMMUTABLE),
        "kernel_immutable": {
            "threemind.experimental-weight-decay/1": [f"config.{k}" for k in (
                "edge_rule", "minimum_rate", "extra_rate", "matching_weight",
                "propagation_interval_us", "decay_curve", "decay_transition_age", "reinforcement_age_policy",
                "structure_check_interval_us", "retention_growth_enabled", "retention_relaxation_enabled",
                "novelty_mode", "consolidation_mode", "memory_growth_formula",
                "propagation_mode", "propagation_phase", "arrival_mode", "reception_mode", "energy_model",
                "energy_distribution", "energy_seed", "energy_region_count")],
            "unified-associative": [f"config.{key}" for key in ("tick_seconds", "random_seed", "node_payload",
                                                               "spatial_embedding", "spatial_dimensions", "sensory_encoding")],
            "threemind.continuous-memory/4": [
                f"config.{k}"
                for k in (
                    "propagation_interval_us",
                    "novelty_mode",
                    "consolidation_mode",
                    "memory_growth_formula",
                    "propagation_mode",
                    "propagation_phase",
                    "arrival_mode",
                    "reception_mode",
                    "energy_model",
                    "energy_distribution",
                    "energy_seed",
                    "energy_region_count",
                )
            ],
            "threemind.continuous-memory/5": [
                f"config.{k}"
                for k in (
                    "propagation_interval_us",
                    "novelty_mode",
                    "consolidation_mode",
                    "memory_growth_formula",
                    "propagation_mode",
                    "propagation_phase",
                    "arrival_mode",
                    "reception_mode",
                    "energy_model",
                    "energy_distribution",
                    "energy_seed",
                    "energy_region_count",
                )
            ],
            "threemind.continuous-memory/5.1": [
                f"config.{k}"
                for k in (
                    "propagation_interval_us",
                    "novelty_mode",
                    "consolidation_mode",
                    "memory_growth_formula",
                    "propagation_mode",
                    "propagation_phase",
                    "arrival_mode",
                    "reception_mode",
                    "energy_model",
                    "energy_distribution",
                    "energy_seed",
                    "energy_region_count",
                )
            ],
            "threemind.continuous-memory/5.2": [
                f"config.{k}"
                for k in (
                    "propagation_interval_us",
                    "decay_curve",
                    "novelty_mode",
                    "consolidation_mode",
                    "memory_growth_formula",
                    "propagation_mode",
                    "propagation_phase",
                    "arrival_mode",
                    "reception_mode",
                    "energy_model",
                    "energy_distribution",
                    "energy_seed",
                    "energy_region_count",
                )
            ],
            "threemind.continuous-memory/5.3": [f"config.{k}" for k in (
                "propagation_interval_us", "decay_curve", "decay_transition_age", "reinforcement_age_policy",
                "structure_check_interval_us", "novelty_mode", "consolidation_mode", "memory_growth_formula",
                "propagation_mode", "propagation_phase", "arrival_mode", "reception_mode", "energy_model",
                "energy_distribution", "energy_seed", "energy_region_count")],
            "threemind.lif/1": ["config.rest_mv", "config.reset_mv", "config.threshold_mv"],
            "threemind.continuous-memory/2": ["config.novelty_mode"],
            "threemind.continuous-memory/3": [
                "config.novelty_mode",
                "config.consolidation_mode",
                "config.memory_growth_formula",
            ],
            "threemind.continuous-memory/3.1": [
                "config.novelty_mode",
                "config.consolidation_mode",
                "config.memory_growth_formula",
            ],
        },
        "groups": [
            {"id": k, "label": v}
            for k, v in (
                ("basic", "基础参数"),
                ("legacy", "历史内核原始参数"),
                ("time", "模拟时间与衰减"),
                ("excitation", "刺激与联想传播"),
                ("memory", "学习与巩固"),
                ("inhibition", "局部抑制"),
                ("pruning", "遗忘与修剪"),
                ("optional", "可选内核机制与对照"),
                ("continuous", "连续候选：短时突触与局部上下文"),
                ("retention", "保持、回收与可选唤醒"),
                ("local", "局部事件与资源场"),
                ("lif", "脉冲候选：膜电位、发放与时序学习"),
                ("resources", "模型容量与计算预算"),
                ("energy", "能量与缺能损伤"),
                ("attention", "输入注意与环境竞争"),
                ("spatial", "因果空间实验"),
                ("energy_supply", "外部能量供给适配器"),
                ("senses", "感官与身体"),
                ("ambient_field", "合成环境场"),
                ("body_filter", "环境躯体过滤"),
                ("interoception", "模拟内感受"),
                ("text", "文本感官"),
                ("auditory_sensor", "听觉感官"),
                ("visual_sensor", "视觉感官"),
                ("acoustic_output", "发声器"),
                ("activation_projector", "激活图像投影器"),
                ("host_telemetry", "宿主物理遥测"),
                ("process_telemetry", "工作进程遥测"),
                ("runtime_telemetry", "意识实例执行反馈"),
                ("structural_readout", "截面结构读出"),
                ("temporal_readout", "时序活动读出：活动稳态判定"),
                ("activity_readout", "时序活动读出：活动过程分析"),
                ("live_capture", "连续设备采集"),
                ("transport", "输入总线与资源"),
                ("source_policies", "输入来源与竞争策略"),
                ("recording", "观测与恢复记录"),
                ("identity", "模型身份"),
            )
        ],
    }


def validate_configuration(value, *, current=None, elapsed_us=0, maximum_duration=86400):
    """Return a normalized contract and actionable field errors; never coerce bad input silently."""
    errors = []
    try:
        if isinstance(value, dict):
            if current is None:
                value = {
                    "kernel_id": DEFAULT_KERNEL,
                    "activity_readout": {
                        "enabled": True,
                        "analysis_version": 2,
                        "interval_us": 20000,
                        "periodic_max_samples": 60,
                    },
                    **value,
                }
                for root in ("host_telemetry", "process_telemetry", "runtime_telemetry"):
                    if root in value and not isinstance(value[root], dict):
                        continue
                    value[root] = {
                        "intensity": 0.2,
                        **(
                            {"enabled": True} if root == "host_telemetry" and value.get("environment") == "host" else {}
                        ),
                        **value.get(root, {}),
                    }
            elif "kernel_id" not in value:
                value = {**value, "kernel_id": RunSpec.model_validate(current).kernel_id}
        spec = RunSpec.model_validate_json(json.dumps(value, allow_nan=False), strict=True)
    except (ValidationError, ValueError, TypeError) as exc:
        if isinstance(exc, ValidationError):
            errors = [{"path": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]
        else:
            errors = [{"path": "config", "message": str(exc)}]
        return {"valid": False, "errors": errors}
    data = spec.model_dump()
    data["config"] = asdict(resolve_kernel(spec.kernel_id).configuration(data["config"]))
    if spec.duration_s is not None and spec.duration_s > maximum_duration:
        errors.append({"path": "duration_s", "message": f"运行时长超过当前部署上限 {maximum_duration} 秒。"})
    if current is not None:
        original = RunSpec.model_validate(current).model_dump()
        original["config"] = asdict(resolve_kernel(original["kernel_id"]).configuration(original["config"]))
        locked = list(PROTOCOL_IMMUTABLE) + [f"config.{k}" for k in CORE_IMMUTABLE]
        if original["kernel_id"] == "unified-associative":
            locked += [f"config.{key}" for key in ("tick_seconds", "random_seed", "node_payload", "spatial_embedding",
                                                   "spatial_dimensions", "sensory_encoding")]
        if original["kernel_id"] == "threemind.lif/1":
            locked += ["config.rest_mv", "config.reset_mv", "config.threshold_mv"]
        if original["kernel_id"] in ("threemind.continuous-memory/2", "threemind.continuous-memory/3", "threemind.continuous-memory/3.1"):
            locked += ["config.novelty_mode"]
        if original["kernel_id"] in ("threemind.continuous-memory/3", "threemind.continuous-memory/3.1"):
            locked += ["config.consolidation_mode", "config.memory_growth_formula"]
        if original["kernel_id"] in ("threemind.continuous-memory/4", "threemind.continuous-memory/5", "threemind.continuous-memory/5.1", "threemind.continuous-memory/5.2", "threemind.continuous-memory/5.3"):
            locked += ["config.propagation_interval_us"]
            locked += [
                f"config.{k}"
                for k in (
                    "novelty_mode",
                    "consolidation_mode",
                    "memory_growth_formula",
                    "propagation_mode",
                    "propagation_phase",
                    "arrival_mode",
                    "reception_mode",
                    "energy_model",
                    "energy_distribution",
                    "energy_seed",
                    "energy_region_count",
                )
            ]
        if original["kernel_id"] == "threemind.continuous-memory/5.2":
            locked += ["config.decay_curve"]
        if original["kernel_id"] == "threemind.continuous-memory/5.3":
            locked += [f"config.{k}" for k in ("decay_curve", "decay_transition_age", "reinforcement_age_policy", "structure_check_interval_us")]
        if original["kernel_id"] == "threemind.experimental-weight-decay/1":
            locked += catalogue(original["kernel_id"])["kernel_immutable"][original["kernel_id"]]
        if original.get("study_id"):
            locked = list(data)
        for path in locked:
            before, after = original, data
            for part in path.split("."):
                before, after = before.get(part), after.get(part)
            if before != after:
                errors.append(
                    {
                        "path": path,
                        "message": "创建后不可修改；请创建独立实例或新实验。"
                        if not original.get("study_id")
                        else "实验协议已冻结；请分叉为独立运行后修改。",
                    }
                )
        if (
            spec.duration_s is not None
            and spec.duration_s != original["duration_s"]
            and round(spec.duration_s * 1e6) <= elapsed_us
        ):
            errors.append({"path": "duration_s", "message": "总运行时长必须大于该实例已经运行的模拟时长。"})
    elif any(data.get(k) is not None for k in ("study_id", "condition", "block_seed")):
        errors.append({"path": "study_id", "message": "实验归属只能由实验训练器分配。"})
    adjustments = []
    if data["kernel_id"] in ("threemind.continuous-memory/3", "threemind.continuous-memory/3.1", "threemind.continuous-memory/4", "threemind.continuous-memory/5", "threemind.continuous-memory/5.1", "threemind.continuous-memory/5.2", "threemind.continuous-memory/5.3") and isinstance(
        value, dict
    ):
        requested = value.get("config", {})
        if requested.get("revival_enabled") and not data["config"]["revival_enabled"]:
            adjustments.append({"path": "config.revival_enabled", "message": "休眠已关闭，唤醒已联动关闭。"})
    return {
        "valid": not errors,
        "errors": errors,
        "spec": data,
        **({"adjustments": adjustments} if adjustments else {}),
    }


def require_valid(result):
    if not result["valid"]:
        raise ValueError("；".join(f"{e['path'] or '配置'}：{e['message']}" for e in result["errors"]))
    return result["spec"]
