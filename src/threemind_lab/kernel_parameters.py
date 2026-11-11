"""UI descriptions for versioned candidate parameters; defaults stay executable."""

from threemind_kernels.continuous import KERNEL_ID, ContinuousConfig
from threemind_kernels.lif import LifConfig
from threemind_kernels.local import KERNEL_ID as LOCAL_ID
from threemind_kernels.local import LocalConfig
from threemind_kernels.local5 import KERNEL_ID as LOCAL5_ID
from threemind_kernels.local51 import KERNEL_ID as LOCAL51_ID
from threemind_kernels.local52 import KERNEL_ID as LOCAL52_ID
from threemind_kernels.local53 import KERNEL_ID as LOCAL53_ID
from threemind_kernels.memory import KERNEL_ID as MEMORY_ID
from threemind_kernels.novelty import KERNEL_ID as NOVELTY_ID
from threemind_kernels.registry import kernel_catalog, resolve_kernel
from threemind_kernels.retention import KERNEL_ID as RETENTION_ID
from threemind_kernels.retention import RetentionConfig
from threemind_kernels.retention31 import KERNEL_ID as RETENTION31_ID

CONTINUOUS_FIELDS = (
    ("stp_enabled", "短时突触资源", "", "启用逐连接释放、耗竭与恢复；关闭后发送幅度不乘释放比例。", None, None),
    (
        "stp_utilization",
        "释放利用率 U",
        "比例",
        "每次合格发射尝试释放的可用资源比例；0 停止释放，不等于关闭算子。",
        0,
        1,
    ),
    ("stp_recovery_tau_s", "突触资源恢复时间", "s", "失活资源回到可用池的时间常数。", 0.000001, 1e9),
    ("stp_active_tau_s", "突触活动资源时间", "s", "已释放资源进入失活池的时间常数。", 0.000001, 1e9),
    ("stp_facilitation_tau_s", "易化恢复时间", "s", "0 关闭易化；正值为利用率额外增益的衰减时间常数。", 0, 1e9),
    ("fast_enabled", "连接快变化迹", "", "实际传播在慢权重之外形成可衰减的局部快迹；不改写慢权重公式。", None, None),
    ("fast_tau_s", "快迹衰减时间", "s", "快迹按经过的模拟时间衰减。", 0.000001, 1e9),
    ("fast_learning_rate", "快迹积累率", "每次发射量", "0 停止新增快迹；关闭持续可塑性也停止积累。", 0, 1),
    ("fast_gain", "快迹传输增益", "比例", "0 关闭快迹对传输的影响，仍可记录其积累。", 0, 1),
    (
        "context_enabled",
        "接收端局部上下文",
        "",
        "只对实际到达同一节点的本批消息分配响应，不筛选被动读出的原始激活。",
        None,
        None,
    ),
    ("context_tau_s", "触达时间特征尺度", "s", "局部特征中距上次触达时间的指数尺度，不改变感官编码。", 0.000001, 1e9),
    ("context_temperature", "局部竞争温度", "", "正值，越小越强调局部状态相似度；不代表语义重要性。", 0.000001, 1e6),
    ("context_mix", "局部分配混合量", "比例", "0 保留原始幅度总和；1 使用完全局部分配。原始到达量始终保留。", 0, 1),
)


def candidate_fields():
    defaults = ContinuousConfig().to_dict()
    return (
        [
            {
                "path": f"config.{key}",
                "label": label,
                "unit": unit,
                "hint": hint,
                "group": "continuous",
                "kernels": [
                    KERNEL_ID,
                    MEMORY_ID,
                    NOVELTY_ID,
                    RETENTION_ID,
                    RETENTION31_ID,
                    LOCAL_ID,
                    LOCAL5_ID,
                    LOCAL51_ID,
                    LOCAL52_ID,
                    LOCAL53_ID,
                ],
                "default": defaults[key],
                "immutable": False,
                "type": "boolean" if type(defaults[key]) is bool else "number",
                **({"minimum": low, "maximum": high} if low is not None else {}),
            }
            for key, label, unit, hint, low, high in CONTINUOUS_FIELDS
        ]
        + memory_fields()
        + retention_fields()
        + decay52_fields()
        + decay53_fields()
        + local_fields()
        + [
            {
                "path": "config.novelty_mode",
                "label": "局部新颖性结算",
                "unit": "",
                "hint": "保留旧公式；默认等候真实联想触达，也可选择旧顺序。出生时固定结算期限；创建后只读，增益为 0 时关闭。",
                "group": "memory",
                "kernels": [NOVELTY_ID, RETENTION_ID, RETENTION31_ID, LOCAL_ID, LOCAL5_ID, LOCAL51_ID, LOCAL52_ID, LOCAL53_ID],
                "default": resolve_kernel(NOVELTY_ID).configuration().novelty_mode,
                "immutable": True,
                "type": "string",
                "choices": [
                    ["arrival-window", "延迟触达结算（默认）"],
                    ["immediate", "出生时立即计算（旧顺序）"],
                ],
            }
        ]
        + lif_fields()
    )


def memory_fields():
    return [
        {
            "path": f"config.{key}",
            "label": label,
            "unit": "",
            "hint": hint,
            "group": "continuous",
            "kernels": [
                MEMORY_ID,
                NOVELTY_ID,
                RETENTION_ID,
                RETENTION31_ID,
                LOCAL_ID,
                LOCAL5_ID,
                LOCAL51_ID,
                LOCAL52_ID,
                LOCAL53_ID,
            ],
            "default": True,
            "immutable": False,
            "type": "boolean",
        }
        for key, label, hint in (
            (
                "depletion_enabled",
                "释放资源耗竭",
                "关闭采用无限补给对照，保持利用率和易化；不会把初始释放系数改为 1。短时突触总开关需开启。",
            ),
            (
                "edge_consolidation_enabled",
                "既有连接正向巩固",
                "关闭仅阻断既有边权重、稳定度的增加；保留生边、遗忘、资格迹、节点更新和快痕迹。",
            ),
        )
    ]


RETENTION_FIELDS = (
    ("consolidation_mode", "连接保持公式", "", "出生时选择半衰期学习或旧稳定度公式；旧内核身份始终可选。"),
    ("node_retention_mode", "节点回收模式", "", "自动复用支持度和使用历史半衰期；手动模式才使用支持度阈值或固定等待。"),
    ("retain_nodes", "不自动删除节点", "", "开启后禁止自动回收；不阻止显式研究删点。"),
    (
        "dead_node_retention_us",
        "死节点保持时间",
        "μs",
        "仅手动模式且支持度阈值为0时生效；从最后一条有效边消失开始，实际触达重置。",
    ),
    ("dormant_traces_enabled", "保留休眠痕迹", "", "实验选项，默认关闭；关闭会清除工作副本痕迹并联动关闭唤醒。"),
    ("revival_enabled", "局部唤醒", "", "默认关闭；真实局部信号达到独立节点/连接阈值时唤醒残余接触。"),
    ("node_wake_threshold", "节点唤醒阈值", "有效信号", "启用唤醒时必须显式配置正值；同刻实际到达量可叠加。"),
    ("edge_wake_threshold", "连接唤醒阈值", "有效信号", "启用唤醒时必须显式配置正值；两端同刻信号可叠加，不另赋权。"),
    ("memory_growth_formula", "半衰期增长公式", "", "出生时固定：对数饱和或起点增益相同的线性饱和对照。"),
    ("memory_half_life_min_s", "最短记忆半衰期", "s", "未充分使用的连接及自动模式节点支持度的半衰期下限。"),
    ("memory_half_life_max_s", "最长记忆半衰期", "s", "反复有效活动可逐渐接近此上限，仍会遗忘。"),
    (
        "memory_half_life_decay_rate",
        "半衰期回落速度",
        "s/s",
        "闲置时每模拟秒减少多少半衰期秒数；0只关闭回落，不关闭权重衰减。",
    ),
    ("memory_learning_gain", "保持时间学习率", "1/s", "按实际局部活动剂量延长半衰期，不按输入事件计数奖励。"),
    ("memory_weight_learning_rate", "保留余量学习率", "1/s", "仅控制自动模式节点支持度；连接使用原有正常权重强化。"),
    ("strong_fatigue_enabled", "强刺激疲劳", "", "强刺激的实际接受量带来额外消耗与可恢复疲劳。"),
    ("strong_fatigue_tau_s", "强刺激疲劳恢复时间", "s", "疲劳指数恢复的时间常数；疲劳越深，恢复到同一水平越久。"),
    ("strong_fatigue_gain", "强刺激疲劳增益", "", "每单位实际接受的超常刺激产生的疲劳量。"),
    ("dormant_prune_weight", "休眠痕迹清除下限", "", "休眠残余权重低于此值后彻底清除；须低于活跃边修剪阈值。"),
)


def retention_fields():
    defaults = RetentionConfig().to_dict()
    choices = {
        "consolidation_mode": [["adaptive-half-life", "活动调节半衰期"], ["legacy-stability", "旧稳定度公式"]],
        "node_retention_mode": [["automatic", "自动支持度保持"], ["manual", "手动回收实验"]],
        "memory_growth_formula": [["log-saturating", "对数饱和（默认）"], ["linear-saturating", "线性饱和对照"]],
    }
    return [
        {
            "path": f"config.{key}",
            "label": label,
            "unit": unit,
            "hint": hint,
            "group": "retention",
            "kernels": [RETENTION_ID, RETENTION31_ID, LOCAL_ID, LOCAL5_ID, LOCAL51_ID],
            "default": defaults[key],
            "immutable": key in ("consolidation_mode", "memory_growth_formula"),
            "type": {bool: "boolean", int: "integer", float: "number", str: "string", type(None): "number"}[
                type(defaults[key])
            ],
            **(
                {"nullable": True, "null_label": "未设置", "exclusiveMinimum": 0}
                if key.endswith("wake_threshold")
                else {}
            ),
            **({"choices": choices[key]} if key in choices else {}),
            **({"minimum": 1 if type(defaults[key]) is int else 0} if type(defaults[key]) in (int, float) else {}),
        }
        for key, label, unit, hint in RETENTION_FIELDS
    ]


LOCAL_IMMUTABLE = (
    "propagation_mode",
    "propagation_phase",
    "arrival_mode",
    "reception_mode",
    "energy_model",
    "energy_distribution",
    "energy_seed",
    "energy_region_count",
)


def local_fields():
    defaults = LocalConfig().to_dict()
    choices = {
        "propagation_mode": [["local-events", "局部事件（默认）"], ["scan-control", "扫描对照"]],
        "propagation_phase": [["aligned", "对齐模拟时刻"], ["asynchronous", "节点独立相位（研究选项）"]],
        "arrival_mode": [
            ["coincident", "同刻整合（/4 默认；/5、/5.1 研究选项）"],
            ["sequential", "分别接收外部输入（/5、/5.1 默认）"],
        ],
        "reception_mode": [
            ["unified", "统一接收（/4 默认；/5、/5.1 研究选项）"],
            ["legacy-source", "按 /2 来源规则（/5、/5.1 默认）"],
        ],
        "energy_model": [["local-field", "局部资源场（默认）"], ["global-ledger", "共享能量账本对照"]],
        "energy_distribution": [["counter-random", "计数随机（可重放）"], ["stream-random", "独立随机流（可重放）"]],
    }
    labels = {
        "propagation_mode": "传播执行方式",
        "propagation_phase": "传播相位",
        "arrival_mode": "到达整合方式",
        "reception_mode": "接收规则",
        "energy_model": "能量模型",
        "energy_distribution": "能量投放随机方式",
        "energy_seed": "能量随机种子",
        "energy_region_count": "固定局部区域数",
        "energy_node_capacity": "单节点能量容量",
    }
    return [
        dict(
            path=f"config.{key}",
            label=label,
            unit="",
            hint=(
                "同刻整合是研究选项：内外信号混合时会共用一次接收与来源标志，可能改变新颖量及直接学习冲量；不等价于 /2。/5、/5.1 默认分别接收。"
                if key == "arrival_mode"
                else "模型选择在出生时固定；能量模型不自动开启能量开关。局部区域只在出生时分配，与显示布局无关。"
            ),
            group="local",
            kernels=[LOCAL_ID, LOCAL5_ID, LOCAL51_ID, LOCAL52_ID, LOCAL53_ID],
            default=defaults[key],
            immutable=key in LOCAL_IMMUTABLE,
            type={str: "string", int: "integer", float: "number"}[type(defaults[key])],
            **(
                {"choices": choices[key]}
                if key in choices
                else {"minimum": 0 if key == "energy_seed" else 1e-12 if key == "energy_node_capacity" else 1}
            ),
        )
        for key, label in labels.items()
    ]


LIF_FIELDS = (
    ("plasticity", "持续可塑性", "", "关闭后停止同帧生边和 STDP，既有电流与发放继续。"),
    ("inhibition", "发放后适应电流", "", "发放产生局部反向电流，减弱后续去极化；不是原核的拓扑抑制。"),
    ("step_us", "阈值检查步长", "μs", "固定格点检查阈值；两点间使用 RC 解析演化。更小步长用于数值收敛对照。"),
    ("delay_us", "突触递送延迟", "μs", "发放至到达的延迟；更改不影响已经在途的信号。"),
    ("refractory_us", "绝对不应期", "μs", "发放后膜电位暂钳于复位值，电流仍接收和衰减；0 关闭。"),
    ("quiescence_death_us", "静息死亡宽限期", "μs", "首次物理活动后，电位偏移及两类电流均消退才开始计时；0 立即判定。"),
    ("seed", "内核身份种子", "", "保存可复现身份；当前脉冲方程没有随机造边。"),
    ("leak_enabled", "膜电位被动泄漏", "", "关闭仅用于消融，不会关闭突触电流自身衰减。"),
    ("current_decay_enabled", "突触电流衰减", "", "关闭时已注入电流保持；属于显式非默认对照。"),
    ("rest_mv", "静息电位", "mV", "电位基准。创建后只读。"),
    ("reset_mv", "发放复位电位", "mV", "必须不低于静息值且低于阈值。创建后只读。"),
    ("threshold_mv", "发放阈值", "mV", "跨过阈值在下一个检查格点发放。创建后只读。"),
    ("resistance_mohm", "膜电阻", "MΩ", "电流与电位变化的耦合量；与其他参数一起决定响应。"),
    ("membrane_tau_s", "膜时间常数", "s", "必须为正；关闭泄漏请使用独立开关。"),
    ("current_tau_s", "突触电流时间常数", "s", "必须为正；关闭衰减请使用独立开关。"),
    ("adaptation_tau_s", "适应电流时间常数", "s", "发放后的反向电流按此尺度消退。"),
    ("adaptation_jump_na", "每次发放的适应增量", "nA", "0 停止增加适应电流；已有适应电流仍衰减。"),
    ("input_gain_na", "输入电流增益", "nA", "通道幅度 × 刺激强度 × 此增益；0 关闭直接输入注流。"),
    ("spike_gain_na", "突触传输电流增益", "nA", "发放按连接权重和短时资源决定电流，不读取目标电位。0 关闭新传输。"),
    ("voltage_epsilon_mv", "电位静息容差", "mV", "与电流容差共同判断消退；0 撤去此数值截断，可能极长时间不静息。"),
    ("current_epsilon_na", "电流静息容差", "nA", "电流、适应电流与电位均消退后才清零。0 撤去电流截断。"),
    ("birth_weight", "同帧生边系数", "比例", "仅实际输入共同触达节点间生边，权重乘两者输入幅度。0 禁止新边。"),
    ("stdp_enabled", "局部时序可塑性", "", "使用该连接的到达迹和目标发放迹；无语义奖励。"),
    ("stdp_tau_pre_s", "突触前到达迹常数", "s", "先到达再发放的影响随此尺度衰减。"),
    ("stdp_tau_post_s", "突触后发放迹常数", "s", "先发放再到达的影响随此尺度衰减。"),
    ("stdp_a_plus", "正时序增量", "每次发放", "目标发放时权重增加 A+ × 本连接到达迹；0 关闭增加。"),
    ("stdp_a_minus", "反时序减量", "每次到达", "输入到达时权重减少 A− × 目标发放迹；0 关闭减少。"),
    ("stp_enabled", "短时突触资源", "", "发放使用逐连接资源的释放与恢复。关闭保留完整发射幅度。"),
    ("stp_utilization", "释放利用率 U", "比例", "0 停止释放；不等于关闭短时算子。"),
    ("stp_recovery_tau_s", "资源恢复常数", "s", "失活资源重新进入可用池的尺度。"),
    ("stp_active_tau_s", "释放资源活动常数", "s", "资源进入失活池的尺度。"),
    ("stp_facilitation_tau_s", "易化时间常数", "s", "0 关闭易化。"),
    ("max_nodes", "受体容量", "个", "达到容量时拒绝新受体并记账；0 禁止新受体，不删除已有受体。"),
    ("max_edges", "连接容量", "条", "达到容量时拒绝新边并记账；0 禁止新边，不删除已有边。"),
)


def lif_fields():
    from dataclasses import asdict

    defaults = asdict(LifConfig())
    return [
        {
            "path": f"config.{key}",
            "label": label,
            "unit": unit,
            "hint": hint,
            "group": "basic" if key in ("plasticity", "inhibition") else "lif",
            "kernels": ["threemind.lif/1"],
            "default": defaults[key],
            "immutable": key in ("step_us", "seed", "rest_mv", "reset_mv", "threshold_mv"),
            "type": {bool: "boolean", int: "integer", float: "number"}[type(defaults[key])],
            **(
                {"minimum": -1000 if key.endswith("_mv") and key != "voltage_epsilon_mv" else 0}
                if type(defaults[key]) is not bool
                else {}
            ),
        }
        for key, label, unit, hint in LIF_FIELDS
    ]


def kernel_defaults():
    from dataclasses import asdict

    return {k["kernel_id"]: asdict(resolve_kernel(k["kernel_id"]).configuration()) for k in kernel_catalog()}


def decay52_fields():
    result = []
    labels = {
        "memory_half_life_min_s": (
            "最短衰减时间尺度",
            "指数模式为半衰期；非指数模式为一份新贡献在固定尺度下的首次半值时间。",
        ),
        "memory_half_life_max_s": ("最长衰减时间尺度", "经历可以延长到此上限；时间尺度与连接权重分别更新。"),
        "memory_half_life_decay_rate": (
            "衰减时间尺度回落速度",
            "回落开启时每模拟秒减少的尺度秒数；关闭回落后该速率不生效，权重仍按所选曲线衰减。",
        ),
        "memory_growth_formula": ("衰减时间尺度增长公式", "按实际局部经历延长时间尺度；与三种衰减曲线分别选择。"),
        "consolidation_mode": (
            "连接保持规则",
            "非指数曲线要求 adaptive-half-life；该历史字段表示使用依赖的时间尺度规则。",
        ),
        "node_retention_mode": ("节点回收模式", "非指数曲线要求 automatic，节点支持度沿用同一衰减曲线。"),
        "memory_learning_gain": ("保持时间学习率", "按实际局部活动剂量延长衰减时间尺度。"),
    }
    for old in retention_fields():
        item = dict(old, kernels=[LOCAL52_ID])
        key = item["path"].split(".", 1)[1]
        if key in labels:
            item.update(label=labels[key][0], hint=labels[key][1])
        result.append(item)
    result.extend(
        [
            {
                "path": "config.decay_curve",
                "label": "衰减机制",
                "unit": "",
                "group": "retention",
                "hint": "出生时固定。对数选项使用 1/[1+ln(1+(e−1)a)]，幂律使用 1/(1+a)；a 是经历后的无量纲年龄。",
                "kernels": [LOCAL52_ID],
                "default": "exponential",
                "immutable": True,
                "type": "string",
                "choices": [
                    ["exponential", "指数衰减"],
                    ["inverse-logarithmic", "对数衰减"],
                    ["power-law", "幂律衰减"],
                ],
            },
            {
                "path": "config.retention_relaxation_enabled",
                "label": "衰减时间尺度回落",
                "unit": "",
                "group": "retention",
                "hint": "开启时沿用线性回落；关闭只阻止时间尺度随时间缩短，仍允许学习延长和连接权重衰减。",
                "kernels": [LOCAL52_ID],
                "default": True,
                "immutable": False,
                "type": "boolean",
            },
        ]
    )
    return result


def decay53_fields():
    from threemind_kernels.local53 import Local53Config
    defaults = Local53Config().to_dict()
    result = []
    for original in decay52_fields():
        item = dict(original, kernels=[LOCAL53_ID])
        key = item["path"].split(".", 1)[1]
        item["default"] = defaults[key]
        if key == "decay_curve":
            item["hint"] = "每个连接仅保存当前权重和一个衰减年龄。强化默认保持年龄；不保存各次强化的贡献列表。"
            item["choices"] = [*original["choices"], ["power-exponential", "先幂律、后指数衰减"]]
        elif key == "memory_half_life_min_s":
            item.update(label="基础衰减时间尺度", hint="控制年龄增长速度；30秒尺度不是每30秒才衰减一次。指数模式对应半衰期。")
        elif key == "consolidation_mode":
            item.update(label="连接衰减规则", hint="/5.3使用单年龄曲线；保留历史配置字段名。", choices=[["adaptive-half-life", "单年龄衰减"]])
        elif key == "node_retention_mode":
            item.update(hint="节点支持度采用同一单年龄曲线。", choices=[["automatic", "自动"]])
        result.append(item)
    descriptions = (
        ("decay_transition_age", "幂律转指数年龄", "达到此无量纲年龄后连续转入指数尾段。", True),
        ("reinforcement_age_policy", "强化时的年龄处理", "keep继续累计；reset仅在实际增加权重或支持度时重新计龄。", True),
        ("retention_growth_enabled", "经历延长衰减时间尺度", "关闭时仍正常增强权重，仅停止延长时间尺度。", False),
        ("structure_check_interval_us", "结构检查间隔", "按内部时钟直接比较当前权重与删除门槛。", True),
        ("signal_threshold_enabled", "启用联合传导门槛", "按连接有效权重、信号量和突触资源计算后统一判断两类信号。", False),
        ("signal_threshold", "联合传导最小量", "低于此量时不送达；节点发送消耗的能量不退还。", False),
        ("weight_gate_enabled", "启用连接权重门槛", "独立可选的权重门槛，默认关闭。", False),
        ("weight_gate", "连接权重门槛", "启用时不得小于连接删除门槛。", False),
        ("inhibitory_learning_enabled", "抑制传导参与强化", "关闭时抑制仍传导，但不贡献权重、短时增强或保持增长。", False),
        ("inhibition_sender_gate_enabled", "启用旧抑制发送门槛", "旧发送端门槛的独立对照开关，默认关闭。", False),
    )
    for key, label, hint, immutable in descriptions:
        value = defaults[key]
        item = dict(path=f"config.{key}", label=label, hint=hint, unit="µs" if key.endswith("_us") else "",
                    group="retention", kernels=[LOCAL53_ID], default=value, immutable=immutable,
                    type={bool:"boolean",str:"string",int:"integer",float:"number"}[type(value)])
        if key == "reinforcement_age_policy":
            item["choices"] = [["keep", "继续累计"], ["reset", "实际强化后重新计龄"]]
        result.append(item)
    return result


def weight_decay_fields(existing):
    """R48 is a separate research candidate, never a new /5.3 default."""
    from threemind_kernels.weight_decay import KERNEL_ID as identity, CandidateConfig, RULES
    defaults = CandidateConfig().to_dict()
    result = []
    fixed = {"decay_curve", "reinforcement_age_policy", "retention_growth_enabled", "retention_relaxation_enabled"}
    for original in existing:
        if LOCAL53_ID not in original.get("kernels", ()):
            continue
        item = dict(original, kernels=[identity])
        if item["path"].startswith("config."):
            key = item["path"][7:]
            item["default"] = defaults[key]
            if key in fixed:
                item.update(immutable=True, choices=[[defaults[key], str(defaults[key])]])
            if key == "decay_curve":
                item.update(label="节点支持度衰减曲线", hint="R48节点固定逆对数；连接另用下方连接衰减规则。")
            if key == "memory_half_life_min_s":
                item.update(hint="用于节点支持度及逆对数连接对照；权重依赖连接和匹配指数连接使用各自速率。")
            if key == "consolidation_mode":
                item.update(label="连接衰减方式", hint="保留历史配置字段名；R48的具体连接公式由edge_rule指定。",
                            choices=[["adaptive-half-life", "R48研究用连接衰减"]])
            if key == "node_retention_mode":
                item.update(hint="R48节点支持度固定采用逆对数年龄曲线。")
            if key == "reinforcement_age_policy":
                item.update(hint="年龄继续累计。权重依赖公式不使用此年龄；节点和逆对数对照仍使用。")
            if key in ("retention_growth_enabled", "retention_relaxation_enabled"):
                item.update(hint="R48保持关闭；实际强化仍直接增加当前权重。")
        result.append(item)
    for key, label, hint in (
        ("edge_rule", "研究用连接衰减规则", "R48独立候选与对照；快慢档的数值由extra_rate显式规定，名称不会自动改参。"),
        ("minimum_rate", "最小相对衰减率", "单位每内部秒；连接权重接近1时仍有此衰减率。"),
        ("extra_rate", "弱连接额外衰减率", "权重依赖项乘以(1−w)；R48快档0.06、慢档0.012。"),
        ("matching_weight", "指数对照的匹配权重", "只用于恒定指数对照，将其速率匹配到此权重的候选瞬时速率。"),
    ):
        value = defaults[key]
        item = dict(path=f"config.{key}", label=label, hint=hint, unit="s⁻¹" if key.endswith("rate") else "",
                    group="retention", kernels=[identity], default=value, immutable=True,
                    type="string" if key == "edge_rule" else "number")
        if key == "edge_rule":
            item["choices"] = [[r, r] for r in RULES]
        elif key == "extra_rate":
            item["minimum"] = 0
        else:
            item["exclusiveMinimum"] = 0
            if key == "matching_weight":
                item["exclusiveMaximum"] = 1
        result.append(item)
    return result
