"""Explicitly registered no-cue controls and historical two-pulse dose matrix."""

import argparse
import hashlib
import importlib
import json
import sys

from common import HERE, WORK, Study, new_json
from experiment import SEEDS, done, probe

from threemind_lab import notebooks
from threemind_lab.database import LOCAL_USER

TEXT = """# 补充对照登记 / Additional controls

初始新颖性执行脚本遗漏了设计文字要求的独立无提示副本。本补充为已完成的 72 个新颖性训练状态各加一个 5 秒无提示副本，用于区分增益形成的背景活动差异与提示产生的额外响应；不改已有结果，不重训。

旧源码三个等幅 AB→AC 小样例没有新颖性增益。源码显示目标饱和及逐路门槛可以阻止 A 接到真实联想，虽然 B 收到联想。追加第一帧幅度 × 第二帧幅度的 .2/.4/.8 全 3×3 矩阵，不改其他默认参数，完整报告九项，保留最初三项。

追加 72 个平台副本及 9 个历史小样例；原计划 714 个平台实例变为 786 个，另保存一个输入前失败的空白实例。保留原 1000 实例、120 分钟、4 GiB 和账户额度预算。

The novelty runner omitted the design's independent no-cue controls. Add one five-second no-cue sibling for each of the 72 already trained states, without retraining or overwriting. Add a complete 3×3 historical first/second pulse-amplitude matrix (.2/.4/.8), since source-level saturation and per-edge thresholds can prevent local reentry. Keep all nine outcomes and the original three witnesses. No other parameters change. The platform plan becomes 786 completed instances plus one preserved pre-input startup failure, within the existing budgets.
"""


def register(s):
    raw = (HERE / "supplement.py").read_bytes()
    new_json(
        WORK / "supplement-registration.json",
        {"platform_cases": 72, "historical_cases": 9, "source_sha256": hashlib.sha256(raw).hexdigest(), "design": TEXT},
    )
    (WORK / "frozen-supplement.py").write_bytes(raw)
    notebooks.save_note(
        s.db,
        s.project,
        LOCAL_USER,
        s.identity("supplement-design"),
        {
            "operation_id": s.identity("supplement-design-write"),
            "expected_revision": 0,
            "kind": "note",
            "collection_id": s.meta["notebook_id"],
            "title": "新颖性无提示对照与旧源码输入矩阵",
            "body": {"format": "markdown", "text": TEXT},
        },
    )


def run(s):
    assert (WORK / "supplement-registration.json").exists()
    for seed in SEEDS:
        for dose in (0.2, 0.4, 0.8):
            for phase in (70_000, 110_000, 170_000):
                for mode in ("immediate", "arrival-window"):
                    for gain in (0.0, 0.018):
                        key = f"novelty/s{seed}/i{dose}/p{phase}/{mode}/g{gain}"
                        parent = done(s, key + "/train")
                        ch = parent["extra"]["channels"]
                        probe(
                            s,
                            key + "/probe-no-cue",
                            parent,
                            0,
                            [ch[0]],
                            family="novelty",
                            mode=mode,
                            gain=gain,
                            dose=dose,
                            phase_us=phase,
                            pattern_channels=ch,
                        )
        print(json.dumps({"supplement_seed": seed, "done": True}), flush=True)
    sys.path.insert(0, str(WORK))
    legacy = importlib.import_module("historical_v3.runtime")
    Frame = importlib.import_module("historical_v3.frames").SensoryFrame
    cases = []
    for first in (0.2, 0.4, 0.8):
        for second in (0.2, 0.4, 0.8):
            e = legacy.ConsciousnessRuntime(config=legacy.RuntimeConfig())
            e._advance([Frame("manual", {1: first, 2: first})])
            e._advance([Frame("manual", {1: second, 3: second})])
            cases.append(
                {"first": first, "second": second, "nodes": list(e.nodes.values()), "edges": list(e.edges.values())}
            )
    new_json(WORK / "historical-amplitude-matrix.json", {"revision": "97d8592", "cases": cases})


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("register", "run"))
    args = p.parse_args()
    study = Study()
    try:
        register(study) if args.command == "register" else run(study)
    except Exception as exc:
        if study.active_case:
            study.active_case.finish({"budget_stop": True, "error": str(exc)})
        raise
    finally:
        study.db.close()
