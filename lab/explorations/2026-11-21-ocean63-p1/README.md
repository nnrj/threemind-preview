# OCEAN63-P1　营养变得稀缺后，捕食者会留下更多后代吗？

本批使用 `threemind.continuous-memory/6.3`。两个独立水域各有两个供给条件。每个世界从 53 个个体、53 颗营养开始。正常供给每 1 内部秒补充一颗，低供给每 8 内部秒补充一颗。体积较大者首次接触较小者即可吞食，亲代一次产生两个子代，并为两者支付能量。我们统计各代的捕食率、曾经捕食的亲代与其他亲代所留下的存活子代，以及转弯摄入颗粒、转弯捕食和转弯躲避的实例。研究者观察自然出生、死亡和捕食的个体。实验结论以实际世代、观察机会和原件重算结果为据。

[中文实验方案](protocol.zh.md) · [English protocol](protocol.en.md) · [前一批水域实验](../2026-11-21-ocean63/README.md)

## 存储与进度

作者指定本批完整存放于 `I:\ThreeMindData\experiments\ocean63-p1-20261121`。程序等待 OCEAN63-30、28、38 和 39C 全部完成原件核验，再给四项报告分别追加带日期的中英文第二版。每份修订保留原文，并回查转弯前五秒的记录。E28 未记录身体碰撞，只能列出符合可核查条件的候选。其余三项均能检验含碰撞在内的完整筛选条件。

报告核验后，程序在 I 盘为新实验申请 22 GiB，并在本机科研页面登记本批原件目录。每份正式世界记录包含输入、运动指令、身体轨迹、事件和完整世界快照。每 60 内部秒封存一段。一次宿主机暂停消耗的墙钟时间不计入个体的内部时间。空间尚不足时，队列等候 I 盘可用空间。

仓库根目录下的进度查询只读当前状态。

```powershell
.work/kernel-venv/Scripts/python.exe -B lab/explorations/2026-11-21-ocean63-p1/dispatch.py status
```

本机队列状态位于 `.work/ocean63-p1-20261121/status.json`。模拟开始后，I 盘批目录下的 `evidence/progress.json` 给出当前世界、内部时刻、存活数、出生数和捕食数。全部完成后，此源码目录的 `results/` 收录双语报告和核验回执，I 盘的 `evidence/analysis/findings.json` 保存逐代统计、亲子随访和可按时刻回查的运动实例。需要在已封存边界接续时，使用同一 Python 和脚本运行 `queue`。

2026 年 11 月 21 日，正式世界启动前，我们核对了科研平台的两种回执。程序先逐文件核验内容，再读取结项状态。后一项查询返回 `indexed`；队列现同时核对结项状态为 `completed` 且问题数为零。原登记程序和修订程序各有独立摘要。[修订记录](coordinator-correction.json)

## English summary

Two independent habitat pairs start with identical individuals and food stocks within each pair. Only the rate of food replenishment differs between the paired worlds. We test whether predation becomes more frequent in later generations and whether early hunters leave more surviving offspring. We also look for observed turns towards food or live prey and turns that avoid a larger individual. The local queue revises the four earlier feeding reports before it admits this experiment to its reserved directory on drive I. Each recording segment includes the actual stimuli and actions and a complete world checkpoint. The final reports link the claims to the observed denominators.

## 2026-11-22　运行顺序调整 / Revised running order

作者决定先运行 P1。39C 已经保存当前世界。P1 完成原件核验后，队列接续 39C，再给四份旧报告追加转弯分析。P1 的只读状态查询方法见上文。此顺序下的续跑入口为 `scheduling/priority.py`。[登记说明及英文版](scheduling/priority.md)

The author prioritized P1. The queue resumes 39C from its complete checkpoint after verification of the P1 originals and then adds the turn analyses to the four earlier reports. The status command above also covers this queue. Use `scheduling/priority.py` to resume under the revised order. [Scheduling amendment](scheduling/priority.md)

P1 首次载入时停在第 0 秒。保存前，程序把个体编号按数字排序。读回 JSON 后，编号成为文本，10 排在 2 前面。我们逐个核对了 53 份内核状态，确认差异仅在序列化顺序。修订后的记录程序以同一种顺序校验世界快照和各段边界。在隔离副本中，连续运行 50 步与分段保存、读回后的内核和世界状态逐项相同，分段记录也通过了正式分析程序的校验。正式水域接着使用原先的第 0 秒快照。[修订与校验摘要](scheduling/checkpoint-correction.json)

The first P1 load stopped at simulated time zero. Integer identifiers were sorted numerically in memory, but the JSON reader sorted their string forms with 10 before 2. We compared the state of every founder with its saved bytes. The revised recorder uses the same key order for complete world comparisons and segment digests. In an isolated test with all 53 founders, 50 uninterrupted ticks and a run with an intervening save and reload produced identical world and Core states. The original analysis also verified the segment boundaries. The formal run uses the original time-zero snapshot. [Recorder amendment and verification](scheduling/checkpoint-correction.json)
