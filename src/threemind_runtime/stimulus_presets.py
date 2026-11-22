"""Input presets, independent of sensory encoding and Core configuration."""

import math

TEXT_INTENSITY_PRESETS = {"normal": 1.0, "strong": 4.0}


def resolve_intensity(intensity=None, preset=None):
    if preset is not None and preset not in TEXT_INTENSITY_PRESETS:
        raise ValueError("unknown text intensity preset")
    value = intensity if intensity is not None else TEXT_INTENSITY_PRESETS[preset or "normal"]
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100:
        raise ValueError("text intensity must be finite and between 0 and 100")
    return float(value)


def research_presets():
    # This is an explicit experiment override, never a restoration default.
    return [
        {
            "id": "depletion-facilitation-consolidation/1",
            "label": "耗竭＋易化＋巩固",
            "kernel_id": "threemind.continuous-memory/2",
            "config": {"stp_facilitation_tau_s": 1.0},
            "hint": "易化恢复时间 1 秒；其余参数采用普通默认。不是新颖性开关。",
        },
        {
            "id": "inertial-reversal/6.2", "label": "惯性感官反向研究",
            "kernel_id": "threemind.continuous-memory/6.2",
            "config": {"signal_threshold_enabled": True, "signal_threshold": 0.004,
                       "activation_signal_threshold": None, "inhibition_signal_threshold": None},
            "hint": "把两类连接信号量门槛设为0.004；不直接改变响应方向。闭环行为收益仍需检验。",
        },
        {
            "id": "short-inhibition/6.2", "label": "短抑制消退时间研究",
            "kernel_id": "threemind.continuous-memory/6.2",
            "config": {"inhibition": True, "inhibition_tau": 0.0580338705786432},
            "hint": "保留抑制，消退时间常数设为0.0580338705786432秒；持续时间与决策收益分别评价。",
        },
        {
            "id": "stability-retention/6.2", "label": "稳定度保持研究",
            "kernel_id": "threemind.continuous-memory/6.2",
            "config": {"consolidation_mode": "stability", "stability_growth_enabled": True,
                       "stability_relaxation_enabled": True, "retention_growth_enabled": False,
                       "retention_relaxation_enabled": False},
            "hint": "使用稳定度保持，增长与回落开启；不叠加单年龄曲线的H时间尺度规则。",
        }
    ]
