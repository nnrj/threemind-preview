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
        }
    ]
