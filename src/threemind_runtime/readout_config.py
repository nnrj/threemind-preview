"""Scientific observer choices, distinct from Core dynamics and display limits."""

from dataclasses import dataclass

from .media import parameter, validate_parameters

READOUT_VERSION = "threemind.readout/1"


@dataclass(frozen=True)
class StructuralReadoutConfig:
    enabled: bool = parameter(True, "启用截面结构读出", hint="只读分析完整节点输出；不会改变核心动力学。")
    interval_us: int = parameter(100000, "截面采样间隔", 1000, 10000000, unit="μs")
    activation_threshold: float = parameter(0.055, "截面激活阈值", 0, 1)
    min_nodes: int = parameter(3, "结构候选最少节点", 1, 1024)
    max_nodes: int = parameter(
        7, "结构候选最多节点", 1, 1024, hint="科学选择范围；先按激活/联想痕迹排序选取，完整保存选中子图。"
    )
    min_internal_edges: int = parameter(2, "候选最少内部边", 0, 1047552)
    recurrence_window_us: int = parameter(24000000, "复现统计窗口", 1000, 3600000000, unit="μs")
    min_occurrences: int = parameter(4, "最少复现采样数", 1, 100000)
    min_span_us: int = parameter(800000, "复现最短跨度", 0, 3600000000, unit="μs")
    cooldown_us: int = parameter(120000000, "复现提示冷却", 0, 86400000000, unit="μs")
    read_touched_activity: bool = parameter(
        True,
        "记录完整活动截面",
        hint="保存采样时的全部节点，包括弱活动、无触达痕迹及非候选节点。阈值与排序只用于另外的派生分析；完整记录会增加存储量。",
    )
    repeatable_structure_readout: bool = parameter(True, "记录结构复现")
    display_limit: int = parameter(20, "截面默认显示数", 1, 1000, hint="只影响页面，候选与证据范围不变。")
    display_order: str = parameter(
        "activation", "截面展示排序", choices=[("activation", "激活优先"), ("id", "节点 ID")]
    )

    def __post_init__(self):
        validate_parameters(self)
        if self.min_nodes > self.max_nodes or self.min_span_us > self.recurrence_window_us:
            raise ValueError("结构最少节点不能超过最多节点，复现跨度不能超过统计窗口。")


@dataclass(frozen=True)
class TemporalReadoutConfig:
    enabled: bool = parameter(
        True, "启用活动稳态判定", hint="保留原算法：集合、相对分布与总幅度同时稳定；不改变历史分类。"
    )
    interval_us: int = parameter(100000, "时序采样间隔", 1000, 10000000, unit="μs")
    trigger_manual: bool = parameter(True, "人工／文件／重放触发窗口")
    trigger_ai: bool = parameter(False, "AI 来源触发窗口")
    trigger_ambient: bool = parameter(
        False, "背景／设备来源触发窗口", hint="连续背景输入会产生重叠窗口；重叠关系显式记录。"
    )
    baseline_us: int = parameter(1200000, "刺激前基线窗口", 0, 60000000, unit="μs")
    min_response_us: int = parameter(1200000, "输入结束后最短观察", 1000, 600000000, unit="μs")
    max_response_us: int = parameter(
        12000000,
        "单个响应窗口上限",
        1000,
        3600000000,
        unit="μs",
        hint="从首帧起计；超限且输入未结束也会标记删失，避免无限窗口。",
    )
    settle_us: int = parameter(800000, "尾段判定窗口", 1000, 600000000, unit="μs")
    activation_threshold: float = parameter(0.055, "时序激活阈值", 0, 1)
    excess_activation_min: float = parameter(0.005, "超基线最小激活", 0, 1)
    baseline_noise_gain: float = parameter(1.0, "基线波动扣除倍数", 0, 100)
    candidate_scope: str = parameter(
        "associative-or-persistent",
        "时序候选范围",
        choices=[
            ("associative-or-persistent", "有联想痕迹或尾段持续"),
            ("associative-only", "仅有联想痕迹"),
            ("all-active", "全部超基线活动"),
        ],
    )
    consider_activation_strength: bool = parameter(True, "综合排序考虑激活强度")
    ranking_mode: str = parameter(
        "composite",
        "时序排序方式",
        choices=[("composite", "综合"), ("duration", "持续时间"), ("activation-integral", "超基线激活积分")],
    )
    comparison_top_k: int = parameter(
        7, "集合比较候选数", 1, 1024, hint="参与 Jaccard/分布漂移的科学参数，与页面显示数分开。"
    )
    convergence_jaccard_min: float = parameter(0.8, "集合稳定最低 Jaccard", 0, 1)
    convergence_drift_max: float = parameter(0.12, "最大分布漂移", 0, 1)
    convergence_amplitude_drift_max: float = parameter(
        0.12, "最大总幅度相对变化", 0, 1, hint="避免单纯保持比例的衰减被误称为收敛。"
    )
    decay_final_ratio_max: float = parameter(0.35, "衰减尾值／峰值阈值", 0, 1)
    display_limit: int = parameter(20, "时序默认显示数", 1, 1000, hint="只影响页面，完整候选指标都会保存。")
    max_active_windows: int = parameter(
        64, "同时观察窗口预算", 1, 4096, hint="超限生成未观察记录，不会静默丢弃或截断模型。"
    )
    max_node_entries: int = parameter(
        100000, "每窗累计节点预算", 1, 10000000, hint="超限显式删失窗口，保留已测数据与原因；不限制核心节点。"
    )
    max_history_samples: int = parameter(
        10000, "每窗轨迹采样预算", 24, 1000000, hint="达到预算后显式删失窗口；完整保留已采集轨迹，不抽稀科研证据。"
    )

    def __post_init__(self):
        validate_parameters(self)
        if (
            not self.interval_us <= self.settle_us <= self.max_response_us
            or self.min_response_us > self.max_response_us
        ):
            raise ValueError("时序采样间隔 ≤ 尾段判定窗口 ≤ 响应窗口上限，最短观察不能超过窗口上限。")


@dataclass(frozen=True)
class ActivityReadoutConfig(TemporalReadoutConfig):
    analysis_version: int = parameter(
        1,
        "活动过程分析版本",
        choices=[(1, "V1：历史响应判定"), (2, "V2：完整过程与响应判定")],
        hint="省略版本仍恢复 V1；V2 保存整个有界观察过程，增加弱活动、减弱及时间变化测量。",
    )
    process_epsilon: float = parameter(
        1e-12, "过程变化报告容差", 0, 1, hint="只用于变化计数与标识；不裁剪原始轨迹，不是内核门槛。"
    )
    enabled: bool = parameter(True, "启用活动过程分析", hint="独立记录响应模式收敛、幅度变化、周期活动及响应结束。")
    activation_threshold: float = parameter(0.0, "分析激活下限", 0, 1)
    excess_activation_min: float = parameter(1e-9, "分析超基线下限", 0, 1)
    candidate_scope: str = parameter("all-active", "模式分析范围", choices=[("all-active", "全部超基线活动")])
    pattern_enabled: bool = parameter(True, "分析响应模式收敛")
    amplitude_enabled: bool = parameter(True, "分析幅度变化")
    periodic_enabled: bool = parameter(True, "分析周期活动")
    response_end_enabled: bool = parameter(True, "分析响应结束")
    pattern_drift_max: float = parameter(
        0.08,
        "模式最大分布距离",
        0,
        1,
        hint="判定尾段内任一采样与末样本的总变差距离；使用全部超基线活动，不截取前几名。",
    )
    response_floor: float = parameter(
        1e-8, "响应总量下限", 0, 1, hint="总超基线量不超过此值时不进行比例归一化；不是内核死亡阈值。"
    )
    periodic_max_samples: int = parameter(12, "周期最大采样数", 2, 256)
    periodic_tolerance: float = parameter(0.03, "周期重复误差", 0, 1)
    max_series_values: int = parameter(
        2000000, "完整轨迹数值预算", 1, 100000000, hint="达到预算显式删失；不抽样丢弃节点。"
    )


READOUT_CONFIGS = {
    "structural_readout": StructuralReadoutConfig,
    "temporal_readout": TemporalReadoutConfig,
    "activity_readout": ActivityReadoutConfig,
}
