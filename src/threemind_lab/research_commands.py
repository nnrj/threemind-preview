"""One typed command catalog for human and external AI research plans."""

from typing import Literal

from pydantic import Field, model_validator

from .protocols import StrictModel

COMMANDS = {
    "observe.summary": ("状态摘要", "固定已提交恢复点的实际指标", {}),
    "observe.output": ("输出引用", "保存该点之前的实际读出与器官事件引用", {}),
    "observe.graph": ("图谱引用", "保存固定恢复点的节点与连接查询引用", {}),
    "history.tail": ("最近操作", "引用该意识此前的操作记录，默认 20 条", {"limit": 20}),
    "stimulus.send": ("发送文本刺激", "通过普通文本感官与输入总线接收，不替代真实递送", {"text": "", "intensity": 1.0}),
    "stimulus.frames": ("发送匿名刺激帧", "复用匿名输入协议，不创建语义映射或预设连接", {"frames": []}),
    "runtime.wait": ("推进模拟时间", "从当前恢复点推进明确微秒数后提交，保留数值格点", {"duration_us": 100000}),
    "snapshot.capture": ("命名状态引用", "命名当前已提交状态，不虚构一个额外时间点", {"label": "研究状态"}),
    "runtime.pause": ("暂停计划", "在当前步骤边界暂停计划，等待用户明确继续", {}),
    "experiment.note": ("实验注记", "记录研究者说明，不输入到意识模型", {"text": ""}),
}


def required_action(command):
    """The concrete action performed by a plan step, never a blanket control grant."""
    if command.startswith("stimulus."):
        return "runs.stimulate"
    if command in ("runtime.wait", "runtime.advance"):
        return "runs.resume"
    if command == "runtime.pause":
        return "runs.pause"
    if command == "snapshot.capture":
        return "runs.checkpoint"
    if command == "experiment.note":
        return "research.write"
    if command.startswith("observe.") or command == "history.tail":
        return "runs.observe"
    raise ValueError("unregistered research action")


class ResearchStep(StrictModel):
    command: Literal[
        "observe.summary",
        "observe.output",
        "observe.graph",
        "history.tail",
        "stimulus.send",
        "stimulus.frames",
        "runtime.wait",
        "snapshot.capture",
        "runtime.pause",
        "experiment.note",
    ]
    parameters: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def command_parameters(self):
        defaults = COMMANDS[self.command][2]
        if set(self.parameters) - set(defaults):
            raise ValueError("命令含未注册的参数。")
        p = defaults | self.parameters
        if self.command == "stimulus.frames":
            from threemind_runtime.sensory import carrier_frames

            if not isinstance(p["frames"], list) or not 1 <= len(p["frames"]) <= 4096:
                raise ValueError("匿名载体须为 1～4096 帧。")
            frames = list(carrier_frames("anonymous-frames", p, 0, {}))
            if sum(len(f["stimulus"].channels) for f in frames) > 100000:
                raise ValueError("单次匿名刺激超过 100,000 通道预算。")
            self.parameters = p
            return self
        for key, default in defaults.items():
            value = p[key]
            if type(default) is int and type(value) is not int:
                raise ValueError(f"{key} 必须为整数。")
            if type(default) is float and (type(value) not in (float, int) or not 0 < value <= 100):
                raise ValueError(f"{key} 必须为大于 0、不超过 100 的有限数。")
            if type(default) is str and not isinstance(value, str):
                raise ValueError(f"{key} 必须为文本。")
        if "text" in p and (not p["text"].strip() or len(p["text"]) > 20000):
            raise ValueError("文本须为 1～20,000 字，不能只有空白。")
        if "label" in p and (not p["label"].strip() or len(p["label"]) > 200):
            raise ValueError("状态名称须为 1～200 字。")
        if "limit" in p and not 1 <= p["limit"] <= 100:
            raise ValueError("历史条数须为 1～100。")
        if "duration_us" in p and not 1 <= p["duration_us"] <= 86400000000:
            raise ValueError("推进时长须为 1 微秒至 24 模拟小时。")
        self.parameters = p
        return self


class PlanLimits(StrictModel):
    max_steps: int = Field(100, ge=1, le=200, strict=True)
    max_stimuli: int = Field(20, ge=0, le=100, strict=True)
    max_text_chars: int = Field(20000, ge=1, le=200000, strict=True)
    max_wait_us: int = Field(60000000, ge=1, le=86400000000, strict=True)


class ResearchProtocol(StrictModel):
    schema_version: Literal["threemind.research-plan/2"] = "threemind.research-plan/2"
    mode: Literal["manual", "confirm", "automatic"] = "confirm"
    limits: PlanLimits = Field(default_factory=PlanLimits)
    steps: list[ResearchStep] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def budgets(self):
        if any(s.command == "stimulus.frames" for s in self.steps):
            raise ValueError("匿名帧命令请使用 research-plan/3 阶段协议。")
        totals = self.totals()
        if len(self.steps) > self.limits.max_steps:
            raise ValueError("计划超过本次步骤数上限。")
        if totals["stimuli"] > self.limits.max_stimuli:
            raise ValueError("计划超过本次刺激数上限。")
        if totals["text_chars"] > self.limits.max_text_chars:
            raise ValueError("计划超过本次文本总量上限。")
        if totals["wait_us"] > self.limits.max_wait_us:
            raise ValueError("计划超过本次模拟时间上限。")
        return self

    @property
    def step_count(self):
        return len(self.steps)

    def step_at(self, index):
        return self.steps[index]

    def cursor_at(self, index):
        return {"step": index, "total": self.step_count}

    def totals(self):
        return {
            "steps": len(self.steps),
            "stimuli": sum(s.command == "stimulus.send" for s in self.steps),
            "text_chars": sum(len(s.parameters.get("text", "")) for s in self.steps),
            "wait_us": sum(s.parameters.get("duration_us", 0) for s in self.steps),
        }


def catalog():
    from pydantic import TypeAdapter

    return {
        "schema": "threemind.research-plan/2",
        "commands": [
            {"id": k, "label": v[0], "hint": v[1], "defaults": v[2], "plan": True} for k, v in COMMANDS.items()
        ]
        + [
            {
                "id": "runtime.resume",
                "label": "继续已暂停计划",
                "hint": "仅由用户控制入口执行，不接受计划内递归启动",
                "defaults": {},
                "plan": False,
            }
        ],
        "limits": PlanLimits().model_dump(),
        "schema_json": ResearchProtocol.model_json_schema(),
        "stage_schema": StageProtocol.model_json_schema(),
        "supported_schema_json": TypeAdapter(ResearchProtocol | StageProtocol).json_schema(),
        "stage_limits": StageLimits().model_dump(),
    }


class StageLimits(StrictModel):
    max_steps: int = Field(10000, ge=1, le=20000, strict=True)
    max_stimuli: int = Field(5000, ge=0, le=10000, strict=True)
    max_text_chars: int = Field(1000000, ge=1, le=4000000, strict=True)
    max_wait_us: int = Field(86400000000, ge=1, le=86400000000, strict=True)
    max_frames: int = Field(50000, ge=0, le=100000, strict=True)
    max_channels: int = Field(500000, ge=0, le=2000000, strict=True)


class ResearchStage(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    repeat: int = Field(1, ge=1, le=1000, strict=True)
    steps: list[ResearchStep] = Field(min_length=1, max_length=200)


class StageProtocol(StrictModel):
    schema_version: Literal["threemind.research-plan/3"] = "threemind.research-plan/3"
    mode: Literal["manual", "confirm", "automatic"] = "confirm"
    limits: StageLimits = Field(default_factory=StageLimits)
    stages: list[ResearchStage] = Field(min_length=1, max_length=200)

    @property
    def step_count(self):
        return sum(len(stage.steps) * stage.repeat for stage in self.stages)

    def locate(self, index):
        if index < 0 or index >= self.step_count:
            raise IndexError("stage cursor outside frozen protocol")
        for ordinal, stage in enumerate(self.stages):
            size = len(stage.steps) * stage.repeat
            if index < size:
                repeat, step = divmod(index, len(stage.steps))
                return ordinal, stage, repeat, step
            index -= size
        raise AssertionError("unreachable")

    def step_at(self, index):
        _, stage, _, step = self.locate(index)
        return stage.steps[step]

    def cursor_at(self, index):
        if index == self.step_count:
            return {"completed": True, "step": index, "total": self.step_count}
        ordinal, stage, repeat, step = self.locate(index)
        return {
            "stage": ordinal,
            "name": stage.name,
            "repetition": repeat,
            "stage_step": step,
            "stage_repetitions": stage.repeat,
            "step": index,
            "total": self.step_count,
        }

    def totals(self):
        result = {"steps": self.step_count, "stimuli": 0, "text_chars": 0, "wait_us": 0, "frames": 0, "channels": 0}
        for stage in self.stages:
            for step in stage.steps:
                p, repeat = step.parameters, stage.repeat
                result["stimuli"] += repeat * (step.command in ("stimulus.send", "stimulus.frames"))
                result["text_chars"] += repeat * len(p.get("text", ""))
                result["wait_us"] += repeat * p.get("duration_us", 0)
                frames = p.get("frames", [])
                result["frames"] += repeat * len(frames)
                result["channels"] += repeat * sum(len(f["channels"]) for f in frames)
        return result

    @model_validator(mode="after")
    def bounded(self):
        totals = self.totals()
        for name, value in totals.items():
            if value > getattr(self.limits, "max_" + name):
                raise ValueError(f"阶段计划超过 {name} 预算。")
        # Bound the serialized protocol as well as its expanded execution count.
        import json

        if len(json.dumps(self.model_dump(), ensure_ascii=False).encode()) > 4 * 1024 * 1024:
            raise ValueError("冻结阶段协议超过 4 MiB。")
        return self


def parse_protocol(value):
    if isinstance(value, (ResearchProtocol, StageProtocol)):
        return value
    if value.get("schema_version") == "threemind.research-plan/3":
        return StageProtocol.model_validate(value)
    return ResearchProtocol.model_validate(value)


def template(name, *, first="甲", second="乙", repeats=3, wait_us=100000):
    if name not in ("free", "repeat", "association", "forgetting", "order"):
        raise ValueError("未知实验模板。")
    if type(repeats) is not int or not 1 <= repeats <= 12:
        raise ValueError("重复数须为 1～12。")

    def step(command, **parameters):
        return {"command": command, "parameters": parameters}

    wait = step("runtime.wait", duration_us=wait_us)
    observe = step("observe.summary")
    steps = [observe]
    if name == "free":
        steps += [step("experiment.note", text="请填写本次实验目的与预期比较，再添加步骤。")]
    elif name == "order":
        for text in (first, second):
            steps += [step("stimulus.send", text=text), wait, step("observe.output")]
    else:
        for _ in range(repeats):
            steps += [step("stimulus.send", text=first), wait]
            if name == "association":
                steps += [step("stimulus.send", text=second), wait]
        if name == "forgetting":
            steps += [observe, step("runtime.wait", duration_us=wait_us * 10), observe]
        if name == "association":
            steps += [step("stimulus.send", text=first), wait, step("observe.output")]
    steps += [observe, step("snapshot.capture", label="实验结束状态")]
    return ResearchProtocol.model_validate({"steps": steps}).model_dump()
