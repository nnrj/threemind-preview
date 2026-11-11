"""Scientific source admission and frame-local competition policy; no display state."""

from dataclasses import asdict, dataclass, replace

from .media import parameter, validate_parameters

POLICY_VERSION = "threemind.source-policy/1"
# Exact logical sources, with category-wide controls above them.
SOURCES = (
    ("ui_text", "界面文本", "manual", ("manual-text", "ui-text")),
    ("cli_text", "命令行文本", "manual", ("manual-cli-text", "cli-text")),
    ("anonymous", "人工匿名帧", "manual", ("manual-anonymous", "anonymous-frames")),
    ("replay", "记录重放", "manual", ("replay",)),
    ("ai_environment", "AI 环境载体", "ai", ("ai-environment",)),
    ("ai_debug", "AI 调试载体", "ai", ("ai-debug",)),
    ("audio", "音频文件", "manual", ("upload-audio",)),
    ("image", "图片文件", "manual", ("upload-image",)),
    ("video", "视频文件", "manual", ("upload-video",)),
    ("microphone", "实时麦克风", "background", ("live-microphone",)),
    ("camera", "实时摄像头", "background", ("live-camera",)),
    ("remote", "网络设备", "background", ()),
    ("environment", "物理／合成环境", "background", ("mujoco", "ambient-fixture", "ambient-disturbance")),
    ("host", "宿主物理遥测", "background", ("host-physical", "host-telemetry")),
    ("process", "工作进程遥测", "background", ("process-telemetry",)),
    ("runtime", "意识实例反馈", "background", ("runtime-telemetry",)),
    ("interoception", "模拟内感受", "background", ("simulated-interoception",)),
)
CATEGORIES = (("manual", "人工载体"), ("ai", "AI 来源"), ("background", "环境与设备"))
ALIASES = {alias: (key, category) for key, _, category, aliases in SOURCES for alias in aliases}


def identity(source):
    if not isinstance(source, str) or not source or len(source) > 128:
        raise ValueError("invalid logical input source")
    if source.startswith("remote:"):
        return "remote", "background"
    category = (
        "ai"
        if source.startswith("ai-")
        else "manual"
        if source.startswith(("manual-", "upload-")) or source == "text-sensor"
        else "background"
    )
    return ALIASES.get(source, (None, category))


@dataclass(frozen=True)
class SourcePolicies:
    manual_enabled: bool = parameter(
        True, "人工载体总开关", hint="与具体来源开关同时开启才接收新输入；已排入内核的帧保留原承诺。"
    )
    manual_bypass_attention: bool = parameter(
        False, "人工载体绕过竞争筛选", hint="只绕过感官帧的通道竞争，仍保留外部增益和其他感官／物理约束。"
    )
    ai_enabled: bool = parameter(
        True, "AI 来源总开关", hint="与具体来源开关同时开启才接收新输入；已排入内核的帧保留原承诺。"
    )
    ai_bypass_attention: bool = parameter(
        False, "AI 来源绕过竞争筛选", hint="只绕过感官帧的通道竞争，仍保留外部增益和其他感官／物理约束。"
    )
    background_enabled: bool = parameter(
        True, "环境与设备总开关", hint="与具体来源开关同时开启才接收新输入；已排入内核的帧保留原承诺。"
    )
    background_bypass_attention: bool = parameter(
        False, "环境与设备绕过竞争筛选", hint="只绕过感官帧的通道竞争，仍保留外部增益和其他感官／物理约束。"
    )
    ui_text_enabled: bool = parameter(
        True, "界面文本 · 启用", hint="来源所属总开关也须开启；更改只影响之后准入和排队的载体。"
    )
    ui_text_bypass_attention: bool = parameter(
        False, "界面文本 · 绕过竞争", hint="与所属类别的绕过开关取或；不会关闭全局竞争或覆盖其他来源。"
    )
    cli_text_enabled: bool = parameter(
        True, "命令行文本 · 启用", hint="来源所属总开关也须开启；更改只影响之后准入和排队的载体。"
    )
    cli_text_bypass_attention: bool = parameter(
        False, "命令行文本 · 绕过竞争", hint="与所属类别的绕过开关取或；不会关闭全局竞争或覆盖其他来源。"
    )
    anonymous_enabled: bool = parameter(
        True, "人工匿名帧 · 启用", hint="来源所属总开关也须开启；更改只影响之后准入和排队的载体。"
    )
    anonymous_bypass_attention: bool = parameter(
        False, "人工匿名帧 · 绕过竞争", hint="与所属类别的绕过开关取或；不会关闭全局竞争或覆盖其他来源。"
    )
    replay_enabled: bool = parameter(
        True, "记录重放 · 启用", hint="来源所属总开关也须开启；更改只影响之后准入和排队的载体。"
    )
    replay_bypass_attention: bool = parameter(
        False, "记录重放 · 绕过竞争", hint="与所属类别的绕过开关取或；不会关闭全局竞争或覆盖其他来源。"
    )
    ai_environment_enabled: bool = parameter(
        True, "AI 环境载体 · 启用", hint="来源所属总开关也须开启；更改只影响之后准入和排队的载体。"
    )
    ai_environment_bypass_attention: bool = parameter(
        False, "AI 环境载体 · 绕过竞争", hint="与所属类别的绕过开关取或；不会关闭全局竞争或覆盖其他来源。"
    )
    ai_debug_enabled: bool = parameter(
        True, "AI 调试载体 · 启用", hint="来源所属总开关也须开启；更改只影响之后准入和排队的载体。"
    )
    ai_debug_bypass_attention: bool = parameter(
        False, "AI 调试载体 · 绕过竞争", hint="与所属类别的绕过开关取或；不会关闭全局竞争或覆盖其他来源。"
    )
    audio_enabled: bool = parameter(
        True, "音频文件 · 启用", hint="来源所属总开关也须开启；更改只影响之后准入和排队的载体。"
    )
    audio_bypass_attention: bool = parameter(
        False, "音频文件 · 绕过竞争", hint="与所属类别的绕过开关取或；不会关闭全局竞争或覆盖其他来源。"
    )
    image_enabled: bool = parameter(
        True, "图片文件 · 启用", hint="来源所属总开关也须开启；更改只影响之后准入和排队的载体。"
    )
    image_bypass_attention: bool = parameter(
        False, "图片文件 · 绕过竞争", hint="与所属类别的绕过开关取或；不会关闭全局竞争或覆盖其他来源。"
    )
    video_enabled: bool = parameter(
        True, "视频文件 · 启用", hint="来源所属总开关也须开启；更改只影响之后准入和排队的载体。"
    )
    video_bypass_attention: bool = parameter(
        False, "视频文件 · 绕过竞争", hint="与所属类别的绕过开关取或；不会关闭全局竞争或覆盖其他来源。"
    )
    microphone_enabled: bool = parameter(
        True, "实时麦克风 · 启用", hint="来源所属总开关也须开启；更改只影响之后准入和排队的载体。"
    )
    microphone_bypass_attention: bool = parameter(
        False, "实时麦克风 · 绕过竞争", hint="与所属类别的绕过开关取或；不会关闭全局竞争或覆盖其他来源。"
    )
    camera_enabled: bool = parameter(
        True, "实时摄像头 · 启用", hint="来源所属总开关也须开启；更改只影响之后准入和排队的载体。"
    )
    camera_bypass_attention: bool = parameter(
        False, "实时摄像头 · 绕过竞争", hint="与所属类别的绕过开关取或；不会关闭全局竞争或覆盖其他来源。"
    )
    remote_enabled: bool = parameter(
        True, "网络设备 · 启用", hint="来源所属总开关也须开启；更改只影响之后准入和排队的载体。"
    )
    remote_bypass_attention: bool = parameter(
        False, "网络设备 · 绕过竞争", hint="与所属类别的绕过开关取或；不会关闭全局竞争或覆盖其他来源。"
    )
    environment_enabled: bool = parameter(
        True, "物理／合成环境 · 启用", hint="来源所属总开关也须开启；更改只影响之后准入和排队的载体。"
    )
    environment_bypass_attention: bool = parameter(
        False, "物理／合成环境 · 绕过竞争", hint="与所属类别的绕过开关取或；不会关闭全局竞争或覆盖其他来源。"
    )
    host_enabled: bool = parameter(
        True, "宿主物理遥测 · 启用", hint="来源所属总开关也须开启；更改只影响之后准入和排队的载体。"
    )
    host_bypass_attention: bool = parameter(
        False, "宿主物理遥测 · 绕过竞争", hint="与所属类别的绕过开关取或；不会关闭全局竞争或覆盖其他来源。"
    )
    process_enabled: bool = parameter(
        True, "工作进程遥测 · 启用", hint="来源所属总开关也须开启；更改只影响之后准入和排队的载体。"
    )
    process_bypass_attention: bool = parameter(
        False, "工作进程遥测 · 绕过竞争", hint="与所属类别的绕过开关取或；不会关闭全局竞争或覆盖其他来源。"
    )
    runtime_enabled: bool = parameter(
        True, "意识实例反馈 · 启用", hint="来源所属总开关也须开启；更改只影响之后准入和排队的载体。"
    )
    runtime_bypass_attention: bool = parameter(
        False, "意识实例反馈 · 绕过竞争", hint="与所属类别的绕过开关取或；不会关闭全局竞争或覆盖其他来源。"
    )
    interoception_enabled: bool = parameter(
        True, "模拟内感受 · 启用", hint="来源所属总开关也须开启；更改只影响之后准入和排队的载体。"
    )
    interoception_bypass_attention: bool = parameter(
        False, "模拟内感受 · 绕过竞争", hint="与所属类别的绕过开关取或；不会关闭全局竞争或覆盖其他来源。"
    )

    def __post_init__(self):
        validate_parameters(self)

    def resolve(self, source):
        key, category = identity(source)
        category_enabled = getattr(self, f"{category}_enabled")
        source_enabled = getattr(self, f"{key}_enabled") if key else True
        return {
            "schema": POLICY_VERSION,
            "source": source,
            "key": key,
            "category": category,
            "enabled": category_enabled and source_enabled,
            "bypass_attention": getattr(self, f"{category}_bypass_attention")
            or (getattr(self, f"{key}_bypass_attention") if key else False),
            "reason": None
            if category_enabled and source_enabled
            else ("source_category_disabled" if not category_enabled else "source_disabled"),
        }

    def rows(self):
        return [
            {
                "key": key,
                "label": label,
                "category": category,
                "aliases": list(aliases),
                "configuration": {
                    "enabled": getattr(self, f"{key}_enabled"),
                    "bypass_attention": getattr(self, f"{key}_bypass_attention"),
                },
                "effective": self.resolve(aliases[0] if aliases else "remote:device"),
            }
            for key, label, category, aliases in SOURCES
        ]

    def frame(self, stimulus, source):
        policy = self.resolve(source)
        if not policy["enabled"]:
            raise ValueError(f"input source disabled: {source} ({policy['reason']})")
        return replace(stimulus, bypass_attention=policy["bypass_attention"])

    def to_dict(self):
        return asdict(self)
