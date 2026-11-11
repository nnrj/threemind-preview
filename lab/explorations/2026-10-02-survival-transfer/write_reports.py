"""Generate bilingual E27 summaries from verified, immutable case results."""

import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORK = ROOT / ".work/survival-transfer-20261002"


def main():
    summary = json.loads((WORK / "analysis/summary.json").read_bytes())
    free, attached = (summary["groups"][k] for k in ("free", "attached"))
    # This report's narrative is for the observed extinct cohorts, not a template
    # that silently calls a later successful/censored cohort a failure.
    assert free["count"] == 16 and attached["count"] == 8
    assert free["statuses"] == {"starved": 16} and attached["statuses"] == {"starved": 8}
    assert not free["transferred"] and not attached["transferred"] and not free["physical_grasps"]
    f0, fm, f1 = free["duration_seconds_min_mean_max"]
    a0, am, a1 = attached["duration_seconds_min_mean_max"]
    energy_share = sum(g["spent"]["consumed_associative"] for g in (free, attached)) / sum(
        sum(g["spent"].values()) for g in (free, attached)
    )
    density = [r["density_at_1s"] for r in summary["cases"]]
    node_counts = [r["nodes_at_1s"] for r in summary["cases"]]
    count_frames = sum(r["frames"] for r in summary["cases"])
    total_sim = sum(g["simulated_seconds"] for g in (free, attached))
    hours = summary["formal_wall_seconds"] / 3600
    figure_dir = HERE / "figures"
    figure_dir.mkdir(exist_ok=True)
    for source, name in (
        (WORK / "analysis/survival.png", "survival.png"),
        (WORK / "visuals/free-g0-000-v2/sequence.png", "free-sequence.png"),
        (WORK / "visuals/attached-g0-000-v2/sequence.png", "attached-sequence.png"),
    ):
        shutil.copy2(source, figure_dir / name)
    core_checks = [json.loads(p.read_bytes()) for p in sorted((WORK / "verification").glob("*/verification.json"))]
    assert len(core_checks) == 2 and all(r["final_state_matches"] for r in core_checks)
    zh = f"""# E27：运行中生存淘汰已接通，但这批意识没有学会抓杯或倾倒

2026-10-03 完成。对应[事前设计](design.zh.md)、[并行执行补记](execution-amendment.zh.md)与[工具及规则](../../../docs/zh/plans/robot-survival-selection.md)。本轮保留 `continuous-memory/2`，没有修改内核公式、旧意识或旧实验。

## 最直接的结果

按照用户要求，先让意识自己抓自由杯，再转移颗粒；没有效果后才进行固定杯子对照。**16 个自由杯候选和 8 个固定杯候选都没获得任务食物，最终因能量耗尽、活动消失而死亡。没有幸存父本，所以没有伪造第二代。**

| 条件 | 个体数 | 生存时间：最短／平均／最长（模拟秒） | 自行抓杯 | 合格颗粒转移 | 存活到600秒 |
| --- | ---: | --- | --- | ---: | ---: |
| 自由杯主实验 | 16 | {f0:.2f}／{fm:.2f}／{f1:.2f} | 0个 | 0颗 | 0 |
| 固定杯子对照 | 8 | {a0:.2f}／{am:.2f}／{a1:.2f} | 不适用，抓握要求被移除 | 0颗 | 0 |

活动时间由上一轮数秒延长到了数分钟。600秒是本次研究的观察上限，不是新加给普通意识的运行期限；本轮个体都在此之前由原有动力学死亡，没有一个因为到时或排名被程序杀死。全部24例完成，没有正式样本因异常或计算超时被截断。

**本轮没有证明具备实用的机械臂能力，也没有产生可用的预训练模型。** 生存筛选流程跑通与学会任务是两件事。固定杯对照仍无转移，说明单独拿掉抓握要求，在当前条件下还不够；不能只把失败归结为“抓杯太难”。

![生存、能量、网络与消耗](figures/survival.png)

## 观察到了什么

1. **视觉与身体输入很快形成了非常稠密的网络。** 第1模拟秒，{min(node_counts)}～{max(node_counts)}个节点之间，连接占可用有向连接的{min(density):.1%}～{max(density):.1%}。此感官把一次图像及身体共同采样中的非零分量一同提交，已有共同触达规则会大量生边；这不是本轮新增的强制接网代码。
2. **大部分能量用于内部传播。** 两组总消耗中，联想传播占{energy_share:.1%}。这并不把内部活动叫作“无效”或“错误”，但它说明本次食物储备主要供给了什么。能量账目逐个闭合，原始记录分别保存直接输入、联想、抑制和维持消耗。
3. **存在持续的运动偏向，但没有变成这项任务所需的协调动作。** 预先选取编号000作为可视化样例，可以看到自由杯个体很快把机械臂弯向桌面一侧，长时间停留在有限姿态范围。完整关节与力矩数据保存，不能把这个样例夸大成24个体都完全不动；局部关节仍有运动，也不能把偏好本身定义为异常。
4. **全灭导致本轮没有发生跨代改进。** 我们没有用死者中“相对好一点”的个体充当幸存父本。出生和选择工具已验证可用，科学实验中的繁殖样本数则明确为0。

![自由杯000号的实测动作物理回放](figures/free-sequence.png)

![固定杯000号的实测动作物理回放](figures/attached-sequence.png)

高分辨率画面只给研究者看。意识接收的是实际16×12灰度视觉，以及关节位置/速度、接触力、加速度、角速度与能量储备；不是这些全景图，也没有对象名称、目标答案、逆运动学或动作脚本。全景相机使用独立物理数据副本。

## 实验到底做了什么

- 固定的 MuJoCo 3.14.0、Menagerie Panda 资产，7轴机械臂和夹爪；原始力矩，重力、惯性、摩擦与接触。12颗可碰撞刚性颗粒，**不是液体**，未模拟玻璃断裂。
- 物理步长2ms，动作及非视觉感官20ms，视觉100ms。未改 Core 传播节律。没有宿主或CPU遥测输入。
- 出生40300单位，容量161200。每颗合格转移提供10100单位，每1秒结算；每批每颗只结算一次。数值来自事前30秒工程耗能校准，不是看候选结果后调出来的。
- 自由杯需物理双指夹持、提起后，颗粒在接收杯内停留200ms。抓握/提起本身不供能；固定杯组明确取消此要求。每30秒环境重新放置杯和补料，机械臂、连接、活动都不复位。这项外部安排也限制了单次未完成尝试的连续时间，后续应单独检验更长补料周期。
- Core 能量是实验单位；机械功另以焦耳记录，没有冒充同一个物理账本。外部供能没有清空或修改节点活动，死亡仍由已有能量与生命周期机制发生。
- 到时的幸存者才按剩余能量选择繁殖；活着却不入选的应暂停保存。工具使用既有 `birth/1`，不复活死亡个体。本轮两组谱系记录均为灭绝、0子代。

## 不是装置根本无法完成，但校准不等于学习

独立工程控制器通过读取物体位置、IK/PD及预设动作，曾在自由杯完成9/12颗转移，固定杯完成3/12颗。它证明这套物理装置可完成任务，**不是 ThreeMind 的成绩，没有向候选示教**。自由杯早期两次校准分别暴露控制步长问题，以及计量下界排除了静置颗粒的问题；修正都在正式候选前完成，失败记录保留。

工程控制器使用2ms反馈控制，意识动作是20ms，不把它当作同资源的算法优劣比较。它也没有证明当前低分辨率感官和哈希运动投影已经足够学会该任务。当前输出仍是固定的匿名活动→正负力矩投影；不能说自然运动分工已被验证。

## 复现核查与失败留档

24例共保存{count_frames:,}条完整输入/动作记录，以及初末Core模型、物理状态、每秒轨迹、任务事件、种子、供能和实现摘要。自由杯000和固定杯000按**实际记录的刺激与供能**重新执行，逐次动作前的激活和完整最终Core哈希都与原件一致。原始文件没有被复算覆盖。

固定杯000的物理回放中，全部物理测量、任务事件和最终物理状态一致，但4帧内共15个亮度值相差1/255。严格检查先报错，后来明确启用“披露像素差异的物理回放”，没有把它标成感官精确复现。自由杯一次后续严格回放全部通过。**种子与重新渲染不能替代原始刺激留证**；像素差异的具体底层原因尚未定位，也没有证明它在所有任务中都无影响。最初失败回放没有留全差异细节，因此不补造原因。

18项相关测试通过，3项因隔离PostgreSQL测试库未启动而跳过。新增工具最后5项复测通过，包含账目、非法繁殖拒绝、提炼前后等价、恢复、只读回放与像素差异披露。数据库报告/证据写入另有读回哈希核验，不用单元测试代替它。

## 这次失败暴露的下一步重点

**当前最需要解决的是怎样让生存选择开始产生差异，而不是再盲目扩大相同任务。** 这批个体都没碰到第一次有效供能，选择无法积累“成功完成任务”的代际优势。以下是建议，未作为本轮偷偷加入的新实验：

1. 比较完整图像共同输入与有物理依据的局部/变化感官编码，检查静态背景、共同生边和运动投影的关系。保留原映射作对照，不用物体答案替代视觉，也不先修改内核来稀疏化。
2. 将环境难度分阶段：先在更少自由度、较宽的可摄入区域中允许简单动作获得能量；幸存谱系再进入接近、抓握、提升、转移等更难环境。供能由显式物理结果决定，仍不往Core写正确动作。每个阶段的产出单独报告，不能把接触就叫作会倒水。
3. 单独比较出生储备、补料周期与运动接线增益，查明个体是否有机会完成较长动作链。更多时间/个体也有价值，但应先出现偶发食物摄入，否则成本随种群增大而结论未必变清楚。

这是对本轮训练设计与外设表示的诊断，**不是已经通过消融定位的内核缺陷，也不能据此否定环境选择路线**。原始假设、额外强刺激默认、易化预设、遗忘和抑制均未被改动。

## 资源、交付和边界

正式24例累计{total_sim / 60:.2f}模拟分钟，各进程计算墙钟相加{hours:.2f}小时，低于4小时预算。原计划32个自由杯仅为条件扩展；在16个自由杯全灭后，把剩余预算用于事先允许的8个固定杯对照，没有耗尽机器或继续无目标扩展。工程校准、回放和工具测试另记，不充当新的独立学习样本。

供能结算、生存筛选、配置校验、保存/继续、`birth/1`出生及回放已提炼为Python/CLI工具。完整启动参数与命令见[工具文档](../../../docs/zh/plans/robot-survival-selection.md)。**该新颗粒任务尚没有完整UI群体编排**；现有实验笔记、记录与报告用于查看本次设计、图表、报告及证据包。最终数据库编号、存储量及归档校验见交付记录；旧数据不清理、不覆盖。本轮没有推送。
"""
    en = f"""# E27: survival selection works as a process; these individuals did not learn grasping or pouring

Completed 2026-10-03. See the [registration](design.en.md), [execution amendment](execution-amendment.en.md), and [tools and boundaries](../../../docs/en/plans/robot-survival-selection.md). Core remains `continuous-memory/2`; no dynamics, historical individuals or evidence were changed.

## Main result

The primary task required independently grasping a free cup and transferring grains. Only after failure did the authorized attached-cup control run. **All 16 free-cup and all 8 attached-cup individuals earned no food and died through energy exhaustion and the existing activity lifecycle. There were no surviving parents and no invented second generation.**

| Task | Individuals | Lifetime minimum / mean / maximum, simulated seconds | Independent grasp | Qualified grains | Alive at 600 s |
| --- | ---: | --- | --- | ---: | ---: |
| Free cup | 16 | {f0:.2f} / {fm:.2f} / {f1:.2f} | 0 | 0 | 0 |
| Attached cup | 8 | {a0:.2f} / {am:.2f} / {a1:.2f} | Requirement removed | 0 | 0 |

Lifetimes increased from seconds in E26 to minutes. The 600-second study horizon is not a new default consciousness lifetime; every individual died before it, with no rank-based killing. All 24 formal cases completed, without technical or budget censoring. **No useful grasping/pouring controller or pretrained model was obtained.** Removing grasping alone was insufficient in this setup; the failure cannot be assigned solely to grasp difficulty.

![Survival, reserve, connectivity and consumption](figures/survival.png)

## Process findings

At one simulated second, {min(node_counts)}–{max(node_counts)} nodes already occupied {min(density):.1%}–{max(density):.1%} of possible directed edges. Whole-image/body co-observation invokes existing joint-arrival connection rules; no forced-connection mechanism was added. Associative propagation accounted for {energy_share:.1%} of all consumed Core energy. This identifies expenditure, not a judgement that internal activity is intrinsically useless.

The prespecified number-000 visualization shows a persistent movement bias and limited posture range, without task coordination. Other joints can keep moving; the sample does not establish that every individual was motionless, nor that stationary preferences are abnormal. Full per-individual motor statistics remain available. With no surviving parent, cross-generation improvement was not tested: zero descendants is the scientific result, even though birth/selection tools passed engineering checks.

![Free-cup individual 000, recorded-action physical replay](figures/free-sequence.png)

![Attached-cup individual 000, recorded-action physical replay](figures/attached-sequence.png)

These overview images are for researchers. Core received actual 16×12 luminance images, joint position/velocity, contacts, acceleration, angular velocity and reserve fraction. It received neither overview images, object labels, correct actions, inverse kinematics nor scripts. The observer renderer uses an independent physics-data copy.

## Methods and boundaries

Pinned MuJoCo 3.14.0 and Menagerie Panda assets; seven arm joints and coupled gripper; raw torque, gravity, inertia, friction and contacts. Twelve colliding rigid grains are not liquid, and glass fracture is not modeled. Physics uses 2 ms; action/nonvisual sensing 20 ms; vision 100 ms. Core timing remains unchanged; no live host telemetry is injected.

Initial reserve 40300 experimental units, capacity 161200, 10100 per qualified grain, settled each second. Values were frozen from a 30-second engineering cost calibration, not tuned to candidate success. Free-cup qualification requires physical bilateral grasp, lifting, and 200 ms grain residence in the receiver. Grasp/lift alone earns no food. Attached trials waive grasp/lift requirements. Every 30 seconds the external environment resets vessels and restocks material, without resetting the arm or Core; this also limits continuity of unfinished attempts and merits a separate longer-restock comparison.

Core energy and measured actuator work in joules are separate ledgers. Depletion does not directly clear activation. Existing affordability, decay and lifecycle determine death. Horizon survivors would be ranked by remaining energy; living nonparents would remain saved. Existing `birth/1` would preserve structure and clear immediate activity. Both recorded lineages are extinct with zero children.

## Apparatus feasibility is not learning

A privileged engineering controller using object positions, IK/PD and an action sequence transferred 9/12 grains with a free cup and 3/12 with an attached cup. These are **not ThreeMind scores or demonstrations to candidates**. Earlier failed engineering runs exposed a control-period problem and a receiver-floor measurement bound that excluded settled grains. Both fixes preceded formal trials; failed records remain.

That controller used 2 ms feedback versus 20 ms candidate actions. It is a feasibility check, not an equal-resource algorithm comparison, and does not prove that low-resolution vision plus the fixed anonymous activation-to-torque projection is sufficient to learn this task. Emergent motor specialization was not established.

## Reproduction and evidence

The 24 cases retain {count_frames:,} full input/action records, initial/final Core artifacts, physical states, second-by-second trajectories, events, seeds and implementation identities. Free-cup 000 and attached-cup 000 were re-executed from the **recorded stimuli and food**; every recorded pre-action activation and complete final Core hash matched. Original cases were not overwritten.

Attached-cup 000 physical replay reproduced all physical measurements, task events and final physical state, while 15 luminance values across 4 frames differed by 1/255. Strict validation first failed. An explicit physical-replay mode then disclosed the differences; it was not reported as exact sensory reproduction. A subsequent strict free-cup replay passed completely. Seeds and rerendering do not replace original stimulus evidence. The image-rendering/brightness-conversion cause remains unresolved and these differences are not proven irrelevant to all tasks. The first failed free-cup replay lacked a detailed mismatch receipt; its cause is not invented afterward.

Eighteen relevant tests passed; three PostgreSQL integration cases were skipped because the isolated cluster was not running. The final five-tool-test rerun passed, including energy accounting, invalid-parent rejection, extraction equivalence, continuation, replay isolation and explicit pixel-difference disclosure. Database archive/report readback is verified separately.

## Recommended next work, not unannounced experiments

The immediate challenge is to make the environment yield selectable differences. None of these individuals reached its first task-derived meal; success cannot accumulate across generations without a survivor. Compare whole-frame input against physically motivated local/change sensing, keeping the original mapping and avoiding object-answer leakage. Separately consider an easier physical survival environment with fewer degrees of freedom and a wider feeding opportunity, then progressively harder approach, grasp, lift and transfer tasks. Explicit environmental food rules can shape selection without putting correct actions into Core; stage achievements must not be mislabeled as pouring.

Also compare initial reserve, restock period and motor projection gain under independent registrations. Increasing population/time may help, but first establishing occasional food acquisition would make expansion more informative. These are hypotheses about training and peripheral representation, not ablation-proven Core defects or a rejection of environmental selection. Existing intensity, novelty, forgetting, inhibition and facilitation defaults were preserved.

## Resources and delivery

Formal trials total {total_sim / 60:.2f} simulated minutes and {hours:.2f} summed process-wall hours, below the four-hour budget. Expansion from 16 to 32 free-cup founders was conditional; the remaining budget instead funded the preregistered eight attached-cup controls. Calibration, replay and tool tests are separately recorded and are not independent learning samples.

Reusable Python/CLI tools cover food accounting, survivor selection, protocol validation, snapshots, continuation, birth and replay. [Commands](../../../docs/en/plans/robot-survival-selection.md). Full graphical cohort launch for this new granular task is still pending; existing notebook/report UI presents this study and evidence. Final database identifiers, storage and archive verification are in the delivery receipt. Historical data were not removed or overwritten. No push was performed.
"""
    for lang, text in (("zh", zh), ("en", en)):
        p = HERE / f"report.{lang}.md"
        if p.exists():
            raise ValueError("report already generated; append a dated correction rather than silently overwriting")
        p.write_text(text, encoding="utf-8")
        (WORK / f"report.{lang}.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
