"""Research protocol editing. No mutations or private alternative runtime rules."""

import hashlib
import json

from pydantic import ValidationError

from .configuration import CORE_IMMUTABLE, PROTOCOL_IMMUTABLE, default_spec, validate_configuration
from .protocols import ARM_LEGACY_ROOTS, ARM_RUNTIME_ROOTS, StudySpec


def study_catalogue():
    base = default_spec() | {"clock": "unbounded", "duration_s": 10}
    defaults = StudySpec(
        name="持续可塑性配对实验",
        base=base,
        arms=[
            {"name": "完整可塑性"},
            {"name": "关闭可塑性", "config_patch": {"plasticity": False}},
            {"name": "关闭局部抑制", "config_patch": {"inhibition": False}},
        ],
    ).model_dump()
    # The graphical condition editor keeps common design choices read-only.
    shared = [
        "environment",
        "clock",
        "speed",
        "duration_s",
        "seed",
        "environment_seed",
        "replay",
        "study_id",
        "condition",
        "block_seed",
        *[f"config.{key}" for key in sorted(CORE_IMMUTABLE)],
        *sorted(path for path in PROTOCOL_IMMUTABLE if "." in path),
    ]
    return {
        "defaults": defaults,
        "runtime_roots": sorted(ARM_RUNTIME_ROOTS),
        "legacy_roots": list(ARM_LEGACY_ROOTS),
        "shared_paths": shared,
        "max_arms": 12,
        "max_seeds": 64,
    }


def validate_study(value, *, maximum_duration=86400):
    try:
        protocol = StudySpec.model_validate_json(json.dumps(value, allow_nan=False), strict=True)
        # New/editing requests must not carry silently ignored design inputs.
        # Frozen historical jobs retain their previous replay selection behavior.
        if protocol.base.intervention is not None:
            raise ValueError("共同培养不接受未定义时点的结构干预；请在条件组设置分叉后的干预。")
        if protocol.base.replay:
            raise ValueError("配对实验的重放必须按种子放入 replay_blocks；base.replay 在旧配对执行中未生效。")
        if protocol.replay_blocks and protocol.base.environment != "replay":
            raise ValueError("replay_blocks 仅在重放环境生效，请明确选择重放或移除这些区组。")
        normalized = protocol.model_dump()
        base = validate_configuration(normalized["base"], maximum_duration=maximum_duration)
        errors = [{"path": "base." + e["path"], "message": e["message"]} for e in base["errors"]]
        if protocol.warmup_s > maximum_duration:
            errors.append({"path": "warmup_s", "message": f"共同培养超过部署上限 {maximum_duration} 秒。"})
        if errors:
            return {"valid": False, "errors": errors}
        normalized["base"] = base["spec"]
        warnings = []
        if protocol.base.environment == "replay":
            fingerprints = [
                hashlib.sha256(json.dumps(block, sort_keys=True).encode()).hexdigest()
                for block in protocol.replay_blocks.values()
            ]
            if len(set(fingerprints)) < len(fingerprints):
                warnings.append("存在完全相同的重放区组。不同种子编号不能证明独立重复；统计解释须核对采集来源。")
            warnings.append("重放时间从共同培养开始计量；条件起点为共同培养结束时刻，区组应覆盖整个实验。")
        return {"valid": True, "errors": [], "protocol": normalized, "warnings": warnings}
    except (ValidationError, ValueError, TypeError) as exc:
        errors = (
            [{"path": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]
            if isinstance(exc, ValidationError)
            else [{"path": "protocol", "message": str(exc)}]
        )
        return {"valid": False, "errors": errors}


def require_study(value, *, maximum_duration=86400):
    result = validate_study(value, maximum_duration=maximum_duration)
    if not result["valid"]:
        raise ValueError("；".join(f"{e['path'] or '协议'}：{e['message']}" for e in result["errors"]))
    return result["protocol"]
