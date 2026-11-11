# E38 结项补记：转弯摄食候选 / Turning candidates and closeout

2026-10-04。这是本轮末尾的新增观察，不改写先前阶段记录。

## 找到了什么

**不是所有个体都只会直冲。** E37与E38中，10个试验内身份留下了转向后更对准食物、随后实际摄入的记录，已保存14份观察后的活体快照。其中E38的44号和59号在相隔数百秒后再次出现这种过程，适合优先作为后续试验的来源。**兼具转弯摄食与包裹吞食的候选，本轮仍未找到。**

| 试验 / 个体 | 摄食时刻（模拟秒） | 前5秒方向变化（度） | 物种库快照数 |
| --- | --- | --- | --- |
| E37 / 12 | 292.30 | 44.7 | 1 |
| E37 / 35 | 236.28 | 139.0 | 1 |
| E37 / 46 | 228.04 | 106.5 | 1 |
| E38 / 16 | 335.78 | 31.0 | 1 |
| E38 / 20 | 104.12 | 50.7 | 1 |
| E38 / 27 | 255.28 | 30.9 | 1 |
| E38 / 28 | 414.92 | 30.2 | 1 |
| E38 / 44 | 324.20、752.66 | 31.6、35.2 | 3 |
| E38 / 59 | 243.12、522.90、870.60 | 39.9、47.0、41.4 | 3 |
| E38 / 63 | 96.04 | 31.9 | 1 |

E38/44的324.20秒过程在两个同源分支都出现，但不是两次独立复现。E38/59与E37中吞食过其他个体的59号不是同一个体，也不属于后者的11个复制体谱系。14份快照涉及10个原试验身份及其分支副本，不是14个已经证明稳定能力的新物种。

筛查检查相对水流的移动方向、实际转向命令、角速度、局部营养梯度及摄入事件，排除窗口内碰撞。食物已经消失的摄入帧不用于估算靠近方向。5秒内至少30度转向等条件只用于寻找候选，**没有给意识增加转向控制策略或动作限制**；较慢或不同形式的转弯也可能被本轮筛查漏掉。自身绕圈恰好吃到食物仍是需要对照排除的解释，不能仅由此认定学会了追寻食物。

保存的是观察后最近的存活检查点，不冒充事件瞬间；身体、意识状态、结构、映射、谱系、来源环境和观察证据一并保留。跨段核对了全部成功吞食事件，避免漏掉早期转弯候选后来才吞食的情形；仍未发现兼有两类证据的身份。[机器可读清单及库内编号](turning-results.json)。

## 去哪里查看和使用

选择项目 **E38 物种候选复用与营养选择**：

- **模型与证据 → 物种库**：查阅、导入、导出候选；名称含“转弯摄食候选”。详情中可见证据和身体信息。
- **记录与报告**：中英文报告，以及“E38 候选谱系全景录像”。转弯片段为原速10秒，完整海洋加局部放大；长录像为6倍速全景。没有重新构造单个体、单个食物的演示环境。
- 本地片段：`.work/ocean-species-20261004/media/e37-turning-35.mp4`、`e38-turning-20.mp4`。
- Python/CLI可以从`.tmspecies`建立新海洋的创始者；通用的图形化海洋投放编排仍未完成。界面导入物种包不等于已自动创建实验。

## 供给对照完成到哪里

本轮新增账户用量从24%到27%，达到事前登记的停止扩展线。正在执行的原供给段完成900模拟秒；减半供给的600～900秒段没有启动。程序以`extension account budget`结束批次，这是资源停止，不是模拟器崩溃或个体死亡。比较统一使用两边都有的600秒。

| 600秒完整海洋 | 营养摄入 | 末存躯体 | 其中身体储备>0 | 出生 | 分叉后新增吞食 |
| --- | --- | --- | --- | --- | --- |
| 原供给 | 858 | 42 | 27 | 24 | 0 |
| 减半供给 | 740 | 38 | 15 | 21 | 0 |

**减粮未带来更多吞食。** 原供给延长到900秒，候选谱系的11个创始者累计产生18个后代，末存15体；其余42个创始者累计产生15个后代，末存17体，但候选谱系吞食仍为零。繁殖表现值得进一步分离躯体、映射和经历的作用，不能据此说捕食能力复现。

E38实际模拟共122.18墙钟分钟，4段完成，reduced-02未开始；E37另有1200模拟秒的完整录像。全部旧证据及完整结束状态保留。未继续无限延长，也未把缺失的900秒对照补写成阴性结果。

## 下一次最有针对性的工作

1. 用已有候选重复完整海洋，而不是再从空白等待。优先比较E38/44、E38/59的转弯表现以及E37/59、E38/15的吞食表现。
2. 在你已批准的独立`enclosure/2`环境内，对比可消化身体材料比例0与0.5。两边都支付同样的身体建设成本，仅改变留在材料中的比例，以区分“捕获了空腹猎物却无营养”的影响。当前23项相关工程测试通过，53创始体完整模板的CLI初始化也已验证；**尚未进行该新环境的长期种群对照**。
3. 对重复转弯候选做同源全海、感官和内部通路的配对干预，检验转弯是否跟随营养变化及是否由经历/内部活动促成。该归因尚未做，不能把筛选条件本身当作证明。

这些是后续建议，不记为本轮已完成实验。[设计](design.zh.md) · [主报告](report.zh.md) · [新环境与筛查说明](../../../docs/zh/plans/ocean-material-and-turning.md)

---

## English record

Ten source identities across E37 and E38 yielded fourteen archived living snapshots after motor turns followed by nutrient ingestion. The table above gives the measured times and angles. E38 individuals44 and59 repeated such episodes hundreds of simulation seconds apart. E38/59 is not E37's predator59, and is not in its copied lineage. The shared324.20s episode in two branches is not independent replication. No identity matched both this turning screen and complete-enclosure consumption, including a join against later capture events across all completed segments.

The passive screen checks water-relative heading, rotation output, angular velocity, local nutrient gradients and actual ingestion, with no collision during the five-second window. It excludes the ingestion frame from gradient estimation because the particle has already been removed. Screening thresholds do not constrain the controller. These records show actual turning and feeding, but do not yet exclude incidental circling or establish learned pursuit. Slower turns may be missed. Archives are the nearest subsequent living checkpoint, not an invented event-time state, and include brain, body, mapping, provenance and evidence.

All fourteen assets are in project **E38 物种候选复用与营养选择**, Models & evidence → Species library. Reports & records contains bilingual findings and measured videos. Two ten-second original-speed clips retain the full habitat beside a magnified view; longer population videos run at6×. CLI/Python deployment is available; universal graphical habitat deployment remains unfinished.

The registered account extension threshold was reached at27% from a24% baseline. The active original-supply segment completed900s; reduced600–900s never started. The common600s comparison is858/740 nutrient ingestions,42/38 physical survivors,27/15 bodies with positive storage,24/21 births and zero new enclosure consumptions after the fork. The control-only900s extension records18 births from11 candidate founders, compared with15 births from42 other founders, but no candidate-lineage capture. This is a reproductive observation, not replicated predation ability. Total E38 simulation wall time was122.18minutes. All actual endpoints and raw states are retained; a budget stop is not a biological or simulator failure.

Useful follow-ups are matched full-habitat reuse of the turning and predation candidates, body-material fraction0 versus0.5 under the new enclosure/2 rules with equal construction payments, and paired sensory/internal-pathway interventions for repeated turns. The approved material apparatus passed23 relevant tests and the53-founder full-template CLI initialization. Its long population-selection benefit has not been tested. No additional long experiment was started after the resource threshold.

[Main English report](report.en.md) · [Detailed inventory](turning-results.json) · [Material and screening boundaries](../../../docs/en/plans/ocean-material-and-turning.md)
