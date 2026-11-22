# 6.3 水域摄食、繁殖与环境选择

2026 年 11 月 21 日，四项实验分别取得本机科研平台的登记回执。运行顺序是 OCEAN63-30、28、38、39C。前三项使用论文中的旧环境规则及新出生的 6.3 个体，第四项另建允许食腐的水域。

| 实验 | 对应的问题 | 科研记录编号 |
|---|---|---|
| OCEAN63-30 | 两个水域初态下，内核控制、直接感官响应及两种随机动作如何影响摄食？每个世界有 31 个创始个体。 | ccafb6be-a64d-5c95-8ae9-5095f55ecad2 |
| OCEAN63-28 | 三个初态下，摄食能否持续供能并支持繁殖？后续共同环境比较检验继承既有网络的收益。 | 27cadd53-97fb-5d33-ab06-5ba25fa66368 |
| OCEAN63-38 | 选择自身实际完成过捕食的 6.3 亲代。减少营养颗粒是否增加捕食？候选亲代的后代中是否还有捕食者？ | daf2ad8c-532f-595f-8664-ce6b85c3b685 |
| OCEAN63-39C | 遗体可食时，减少颗粒是否增加食腐或活体捕食？早期取食所得不足以覆盖运动及外壳开销的个体是否留下较少后代？ | 8fa2ed65-6de0-5c48-be98-b714fd4e93d3 |

前两项来自论文第 4.8 节。第三项来自第 4.11 节，先按 E37 条件培养合格亲代，再按 E38 建立供给对照。第四项有两个独立水域，每个水域在 300 内部秒分成原供给和减半供给两个分支，观察至 2400 内部秒或群体灭绝。出生使用 `threemind.birth/2`，保留节点、连接、持久状态及衰减年龄，重置即时活动和内部时钟。亲代支付子代的建造和启动能量。[前三项方案](protocol.zh.md) · [新水域方案](carrion-protocol.zh.md)

原件所在的存储分配名为 `ocean63-20261121`。本机根目录为 `I:\ThreeMindData\experiments\ocean63-20261121`。四项原件依次位于 `study-30`、`study-28`、`study-38` 和 `study-39c`。每个正式世界都保留了逐步刺激、实际动作、事件和完整快照。每个世界拥有自己的个体、环境及随机状态。相同世界的研究分支、个体和后代按其所属世界统计。

作者确认本机科研页面可直接读取本批原件。项目已登记上述四个目录，并分别通过 API 读回了一份文件，核对长度与 SHA-256。E30 读回的是首个世界第 60 内部秒的完整快照，39C 读回的是装置校验地图。四份回执分别存于各批 `publication/first-verified-readback.json`。整项实验结束时再核验完整归档。

## 查看进度与结果

在仓库根目录可随时读取即时进度。该命令读取已有文件，不推进水域时间。

```powershell
.work/kernel-venv/Scripts/python.exe lab/explorations/2026-11-21-ocean63/followthrough.py --observe-only
```

批目录中的 `queue.json` 记录当前工作，`results-status.json` 记录各批的核验进度。每项的 `progress.json` 给出正在运行的世界及内部时刻，已结束的世界有 `cases/<世界名>/result.json`。一项全部结束后，`analysis/findings.json` 汇总原始事件重算的分子、分母、各代数据和判据，`analysis/report.zh.md` 与 `analysis/report.en.md` 给出中英文报告。本目录下的 `results/` 会随各项结束收录小型报告。科研 API 的完整原件读回记录为 `publication/complete.json`。本机磁盘上的原件、装置校验和快照均不入 Git。

装置验收采用独立的小世界。前四种旧环境和控制配置完成了从完整快照恢复后逐项比对下一步的检查。新水域的自然死亡、遗体漂移与接触、部分取食、吃尽移除、短时接触进度恢复、活体捕食后避免重复计账及亲代供能出生均有校验证据，位于 `study-39c/engineering`。其中的 `engineering-map.html` 可离线查看装置校验中的实际坐标和遗体。正式水域的地图保存于相应结果目录。

## 历史数值与 6.3 的比较

每份复跑报告都会并列原批与本批的同口径数值。E30 按相同水域和动作规则比较颗粒数与每存活身体分钟摄食率。E28 比较三个水域合计的摄食、出生及期末存活。E38 以两个旧分支都有记录的 600 内部秒为共同终点，同时区分从世界建立起累计的摄食与出生，以及改变供给后的新增捕食。旧 E38 使用 59 号完成捕食后、300 秒时保存的状态，本次使用 6.3 亲代本人首个符合条件事件当步的状态。[E30 原报告](../2026-10-03-ocean-causality/report.r2.zh.md) · [E28 原报告](../2026-10-03-primitive-ocean/report.r2.zh.md) · [E38 原报告](../2026-10-04-ocean-species/report.r2.zh.md)

## English summary

The first three registrations repeat the historical feeding and food-supply comparisons with genuine `threemind.continuous-memory/6.3` subjects. Study 38 selects a parent on its own observed predation. A separate fourth registration follows two new environments with paid body material, edible carcasses and an explicit energy ledger. It tracks live predation, scavenging, reproduction and descendants through the common observation horizon or extinction. Each study has its own frozen protocol, simulation files, original data, scientific endpoints and reports. The read-only command above shows live progress. Final verification includes a re-count of all input ticks and feeding and birth events, living-body time, archive hashes and an authenticated readback from the research platform.
