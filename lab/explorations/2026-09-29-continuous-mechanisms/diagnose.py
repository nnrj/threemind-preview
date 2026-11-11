"""Second-stage local resource trace, with a separately published amendment."""

import argparse
import gzip
import hashlib
import time
from dataclasses import replace
from uuid import UUID, uuid5

from common import HERE, WORK, Case, Study, encoded, load_case, new_json
from run import KERNEL, SEED, TOKENS, Observer, phase_metrics, trace_sample

from threemind_core import Stimulus
from threemind_lab import notebooks
from threemind_lab.database import LOCAL_USER
from threemind_lab.inputs import envelope_record

VARIANTS = {"default": {}, "no-inhibition": {"inhibition": False},
            "recovery-fast": {"stp_recovery_tau_s": 0.08},
            "recovery-slow": {"stp_recovery_tau_s": 8.0},
            "floor-minus10pct": {"activation_floor": 0.0036},
            "floor-plus10pct": {"activation_floor": 0.0044}}

AMENDMENT = """# 连续版机制归因：第二阶段补充方案

此方案在看到第一阶段部分结果后提出，不伪装为最初预注册。第一阶段中，短时资源开启而快痕迹、上下文关闭，仍然有两条提示各自匹配的结尾偏向；快痕迹和上下文都在但短时资源关闭，暂未出现同样的双向偏向。

待检验解释：前缀引起的弱活动，让不同边经历不同次数的资源释放；B 到达时，权重与剩余资源共同决定发送量。传播门槛可能使相近强度落到不同释放分支。因此对原教学正序的同一全开父本增加六组测试时配置，每组 A→B、D→B，共 12 个副本：默认；关闭抑制；资源恢复时间从 0.8 秒改为 0.08 或 8 秒；激活归零/逐边门槛 0.004 改为 0.0036 或 0.0044。

全部通过复制后的公开 reconfigure 接口变更。配置在复制时、等待一秒之前生效；训练父本、主线默认、感官映射、共同输入生边、读出器参数不变。门槛参数同时影响激活归零和逐边发送，不能把这一敏感性检查解释为只改变发送门槛的纯消融。关闭抑制也影响多条路径，需结合真实状态记录解释。

每 10 毫秒保存全部局部状态及公开事件，逐边追踪资源释放时刻、结尾实际到达量、峰值和时间。默认两副本必须复现第一阶段；否则暂停解释。新阶段仍包含在原 2 GiB/4 小时/42% 账户用量上限，不另开预算。不扫参数寻找最好成绩，只报告上述固定六组。已有结果原样保留。

English: This is a prospective amendment after partial factorial observations. Hypothesis: prefix activity changes per-edge release histories, and resource recovery plus learned weights and the existing threshold shape the later B response. Use the same all-on trained parent, 6 explicitly recorded test-time configurations × 2 cues: default, inhibition off, recovery tau 0.08/8 seconds (default 0.8), activation floor 0.0036/0.0044 (default 0.004). The last parameter couples zeroing and transmission thresholds and is not a selective transmission-only intervention. Record all local state every 10 ms and public event deliveries; require default replication. No default/kernel/training/encoding/edge-birth/readout change. These 12 copies remain within the original resource and account budgets. Publish all outcomes, without optimizing settings after seeing results.
"""


def preregister(study):
    path = WORK / "diagnostic-preregistration.json"
    if path.exists():
        raise RuntimeError("already registered")
    note = notebooks.save_note(study.db, study.project, LOCAL_USER, study.identity("diagnostic-plan"), {
        "operation_id": study.identity("diagnostic-plan:write"), "expected_revision": 0, "kind": "note",
        "collection_id": study.meta["notebook_id"], "title": "补充方案：短时资源与门槛的局部作用链",
        "body": {"format": "markdown", "text": AMENDMENT}})
    new_json(path, {"registered_at_epoch": time.time(), "variants": VARIANTS, "note_id": str(note["id"]),
                    "source_sha256": hashlib.sha256((HERE / "diagnose.py").read_bytes()).hexdigest()})
    (HERE / "diagnostic-plan.md").write_text(AMENDMENT, encoding="utf-8")


def run(study):
    from common import read_json
    frozen = read_json(WORK / "diagnostic-preregistration.json")
    assert frozen["source_sha256"] == hashlib.sha256((HERE / "diagnose.py").read_bytes()).hexdigest()
    parent = load_case(study, "factorial/111/swap0-reverse0")
    rows = []
    for variant, patch in VARIANTS.items():
        for name in ("AB", "DB"):
            key = f"diagnostic/{variant}/{name}"
            path = WORK / "cases" / key / "result.json"
            if path.exists():
                rows.append(read_json(path)["extra"])
                continue
            c = Case(study, key, KERNEL, SEED, parent=parent)
            before = c.engine.capture_state().digest
            c.engine.reconfigure(replace(c.engine.config, **patch))
            change = {"method": "public reconfigure", "time_us": str(c.engine.time_us), "patch": patch,
                      "before": before, "after": c.engine.capture_state().digest}
            c.events.append({"key": "study:reconfigure", "time_us": str(c.engine.time_us),
                             "kind": "research_intervention", "payload": change})
            c.advance(c.engine.time_us + 1_000_000)
            start = c.engine.time_us
            observer = Observer(c.engine)
            c.session.engine = observer
            frames = [{"stimulus": Stimulus(start + i * 1_000_000, ((TOKENS[s], 1.0),), 0.5)}
                      for i, s in enumerate(name)]
            item = envelope_record(uuid5(UUID(c.id), "sequence-probe"), "anonymous-frames", "manual-probe",
                                   {"frames": [f["stimulus"].to_dict() for f in frames]}, {"dose": 0.5}, 2, 2)
            c.inputs.changes["envelopes"].append(item)
            c.inputs.schedule(item, frames)
            trace = []
            with gzip.open(c.folder / "states.jsonl.gz", "xb") as out:
                while True:
                    c.guard()
                    c.session.advance_to(c.engine.time_us if not trace else min(start + 12_000_000, c.engine.time_us + 10_000), guard=c.guard)
                    trace.append(trace_sample(c, start))
                    out.write(encoded({"relative_us": c.engine.time_us - start, "state": c.engine.capture_state().to_dict()}) + b"\n")
                    c.sample()
                    if c.engine.time_us >= start + 12_000_000 or c.engine.life == "dead":
                        break
            for filename, values in (("trajectory.jsonl.gz", trace), ("transmissions.jsonl.gz", observer.events)):
                with gzip.open(c.folder / filename, "xb") as out:
                    for value in values:
                        out.write(encoded(value) + b"\n")
            extra = {"variant": variant, "probe": name, "patch": patch, "intervention": change,
                     "post_B": phase_metrics(trace, 1_000_000, 12_000_001), "life": c.engine.life,
                     "pre_B": phase_metrics(trace, 0, 1_000_000), "key": key, "id": c.id}
            result = c.finish(extra)
            if variant == "default":
                ref = read_json(WORK / "cases/factorial/111/swap0-reverse0" / name / "result.json")
                assert result["state_sha256"] == ref["state_sha256"], "diagnostic default state changed"
                assert extra["post_B"] == ref["extra"]["post_B"]
            rows.append(extra)
        print(f"DIAGNOSTIC {variant} complete", flush=True)
    new_json(WORK / "diagnostic.json", rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("preregister", "run"))
    args = parser.parse_args()
    study = Study()
    try:
        preregister(study) if args.phase == "preregister" else run(study)
    finally:
        study.db.close()
