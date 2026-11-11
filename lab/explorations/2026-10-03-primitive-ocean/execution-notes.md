# E28 执行记录 / Execution record

## 2026-10-03：工程验证与登记

正式世界前，工程实现曾违反32位通道范围，及在零免费能量出生时未更新配置绑定摘要。均在正式登记前修正，新增测试覆盖。Python/Rust的在途浮点值有约1ULP差别；以1e-12相对容差验证全部状态，不能称跨后端逐字节一致。同后端完整1500步校准重放通过，输入、动作、事件及最后群体状态逐项一致。

首版校准保留在 `.work/ocean-engineering-20261003`，含当时工具源码。仅格式整理后，在 `-02` 目录重复校准与完整重放，两次耗能标定完全相同：10.746435597741012 单位/秒。未删除旧校准，也未把它当第二个独立模型结果。

正式项目：`e53a833e-6566-463c-90c2-a94a8fe2a8ef`。设计中英文本、源代码身份、工具源码和校准在首次正式运行前冻结。入口省略预设不更改普通内核参数；三个操作模式只在输出驱动外设处不同。

## 2026-10-03：存储预算修订，不更改判据

首个900秒世界的完整输入与快照约168MiB。全部预定世界，再加本地证据包和数据库副本，预计超过初定4GiB。遵循用户允许合理放宽资源的授权，在第二阶段及共同环境评估前，追加 `budget-amendment.json`：本轮新增存储软限6GiB、硬限8GiB。原登记3/4GiB保留；不减少证据、不删旧数据、不修改结果判据。运行时长、账户预算、内存和磁盘余量边界不变。修订时 C盘约9GiB、E盘约100GiB，实际值由交付测量给出。

## Prospective clarifications

The common-garden inherited/blank comparison disables reproduction equally in both arms to isolate the same four bodies' feeding and survival. Donors prefer distinct founder lineages, then the latest living generation and stable ID; intake scores are not used to choose donors. The operational runner was added before these comparisons, without changing the frozen ocean apparatus.

Storage was amended from3/4GiB to6/8GiB because the first complete world retained168MiB and archive/database copies count toward the budget. Original registration and evidence remain intact. No scientific criterion, Core mechanism or time/account limit changed.

## 2026-10-03：账户刷新保护暂停与接续

`phase1-1-random` 在808模拟秒触发“30分钟未刷新账户用量”保护，标为 `paused_error` 并保存全体16个体。工具确认账户仍为15%后，从其 `final` 检查点在 `continuations/01` 中续完余下92秒。原结果、原输入和快照不改，用 `completion.json` 连接两段。末态15个存活、1个实际死亡；暂停本身不作死亡或独立样本。完整世界墙钟统计合并两段。

## 共同环境对照的接线核查

固定输出投影使用节点身份。直接新建空脑会按新一轮到达次序分配节点身份，可能同时换掉运动接线。因此在评估前补充 `naive_same_receptors`：保留感官通道、节点身份、下一个身份号和原配置，用 Core 原有空白节点默认值清除节点经历，并移除边。只操作新的研究副本，有独立测试。继承与空白的感官和运动接线由此一致；没有改正式环境工具或已产生数据。节点存在本身保留，因此此对照准确称为“同受体、无经历网络”，不是字面上连受体也不存在的空无模型。


## 2026-10-03：墙钟预算修订

完整群体实测单世界约10～17分钟，比独立个体校准的外推高。为完成原定对照，在第二阶段开始前将累计模拟墙钟从2小时明确修订至4小时，单世界墙钟保护从1200秒到1800秒；每世界仍为900模拟秒，账户、内存和余量边界不变。原登记保留，新增 wall-budget-amendment.json。正在执行的第一阶段批次保留其已加载的原保护设置，不把其后续一次保护暂停视为实验失败。冻结的 ocean.py/ocean_cli.py 从正式登记至此完全未变；修改的只是研究编排、接续和未来评估准备。

The aggregate simulation wall budget was prospectively increased from2hours to4hours and per-world protection to1800seconds, based on measured full-population overhead. Original records remain; no900second observation horizon or scientific criterion changes. The already-running phase-one batch retains its loaded original guards. Frozen apparatus files remained byte-identical throughout formal simulation.

## 2026-10-03：后续保护暂停与账户窗口变化

第一阶段旧进程按原1200秒墙钟保护，在 `phase1-2-core` 的887模拟秒暂停；最后一个停止驱动世界在810秒触发账户观测过期保护。两者沿用独立 continuation 分段继续，原文件保留。意识驱动在900秒结束，16个体存活。资源保护不计为自然死亡或独立重复。

北京时间05:14工具报告账户使用率从此前16%降至0%。无法仅凭这一读数确定是账户窗口重置还是其他账户操作；本轮保守保留已观察的1个百分点增量，并把新窗口的使用量加在16这一有效读数上继续检查预算。原始读数与有效预算读数分开记录，不把下降解释为本轮消耗消失。

The already-running first-stage process paused the third Core world at887 simulated seconds under its old1200-second wall guard, and the passive world at810seconds because account observation became stale. Append-only continuations preserve all original evidence. At05:14 local time the account tool reported0% after16%; the study carries forward prior observed consumption and adds new-window usage, without claiming to know the cause of that account change.

## 2026-10-03：用户报告网络中断后的核查

用户告知网络恢复后，检查了正在执行的 `phase2-0`：进程未退出，输入和轨迹仍持续写入；240模拟秒完整检查点可恢复18个脑状态，能量账本绝对差约2.35e-8；PostgreSQL实际执行 `SELECT 1` 返回1。随后360秒检查点继续形成，没有把网络断连或保护暂停计为意识死亡。此场景不调用远程模型，不把网络状态作为感官输入。工具连接中断不等于本机模拟中断。

After the user reported a network outage, the phase2-0 process and evidence files were still advancing. Its240-second checkpoint restored all18Core states; energy error was about2.35e-8 and an actual PostgreSQL SELECT1 succeeded. The360-second checkpoint followed. This apparatus has no remote model call or network-status sensor. No evidence of a simulation interruption was found.

### 后续更正：数据库连接确实触发了一次暂停

上述检查之后，`phase2-0` 在731模拟秒资源检查时收到 PostgreSQL 连接关闭错误，重连日志包含本机5433端口 Permission denied/10013。完整19个脑状态（13存活）已保存为 `paused_error`，不是意识死亡。05:40重新通过实际SELECT1检查，随后从完整末态接续余下169秒。无法仅据这些日志确定是网络恢复、宿主机权限切换还是数据库连接重建引起；可以确认故障发生在存储预算检查，未改变已执行的Core步或输入。

**Correction:** after the successful checks above, the database connection closed during a resource check at731simulated seconds. Reconnection logged local port5433 Permission denied/10013. All19Core states (13alive) were saved, then resumed after a fresh SELECT1 succeeded at05:40. The exact host/network cause is unconfirmed. This was a protected orchestration pause, not a neural death, lost checkpoint or new independent trial. The earlier check describes its own time and is not proof that the entire later run was uninterrupted.

## 2026-10-03：资源检查频率修正，内核与物理装置不变

共同环境评估开始后，发现编排层 `guard()` 虽调用每秒检查一次的 Study.guard，却仍在每个20ms感官采样后重新读取所有已完成结果来数个体。结果数量增长使外部记账变慢。通过已支持的STOP文件，将 `evaluation-0-inherited` 在180模拟秒保存暂停，然后把整个外部检查统一为每秒一次。原完整源版本、256.041秒墙钟、输入与脑状态保留；后续在独立接续目录运行余下120秒。

这不改变资源阈值、任何已登记的模拟期限、Core、感官、物理步骤、随机数或传播调度。海洋不接入实时宿主机遥测，外部检查速度不是刺激变量。之前的慢速结果仍是有效原结果；后续用原输入和检查点重放验证，不把提速当作模型学习增益。为操作留下的STOP文件也保留在原段。

The study wrapper redundantly recounted individuals from every completed result at every20ms tick, despite Study.guard's one-second cadence. The first common-garden inherited case was explicitly saved at180seconds using its supported STOP file. Only this external accounting check was throttled to the same one-second cadence. Original sources,256.041wall seconds and evidence remain; a new segment continues the remaining120seconds. No thresholds, simulation horizons, Core equations, apparatus source, sensory mapping, RNG or delivery schedule changed. There is no live host telemetry in these worlds, and runtime speed is not a learning result.

### 实测性能与最后一次有限预算追加

接续120模拟秒耗时170.071秒，与前180秒/256.041秒的比例基本相同。因此不能声称这次外部记账改动已显著加速实验；它消除了重复工作，但没有定位当前主要耗时。首个300秒共同环境评估合计426.112秒。基于此实测，在其余五项评估及重放前追加 `wall-budget-amendment-02.json`，累计模拟与重放墙钟上限改为16200秒（4.5小时）。原2小时、4小时登记都保留。只补足原定比较和验收，不增加世界数、样本、模拟时长，也不放宽账户/存储/内存边界。

The continuation took170.071wall seconds for120simulated seconds, essentially the same ratio as256.041/180 before it. Removing duplicate bookkeeping did **not** demonstrate a material speedup or locate the main cost. The first common-garden world took426.112seconds in total. Before the remaining five comparisons and replay, a second append-only wall amendment allowed16200seconds (4.5hours). Original2/4hour records remain; no additional scientific cases, longer horizons or other relaxed limits.

## 2026-10-03：辅助过程图

首组无经历对照尚未完成时，追加完整0～300秒摄食与储能差值曲线的辅助分析，利用既有每秒观测。保留300秒末态主比较，不以事后选择的峰值替代。所有三组、整个窗口一并展示，区分早期变化与持续优势，不新增模拟或调整刺激。

Before the first experience-erased comparison completed, full0–300second intake and energy difference curves were added as secondary analysis using existing one-second observations. All three pairs and the full window are shown. The300-second primary comparison stays unchanged; no peak replaces it and no simulation/input changes were made.

### 性能诊断更正：检查原本并非每20ms调用

继续检查冻结的 `ocean_cli.run` 调用点后确认，外层已有 `(time_us - start_us) % 1000000 == 0` 条件。因此上文“每20ms重读结果”的诊断不成立：只看了guard函数体，没有同时核查调用频率。这是实施者的定位错误，不能当成已确认的性能缺陷或已获提速。已撤回研究编排中无必要的限频行；正在运行的评估批次保留已加载的版本，它只可能跳过部分外部检查，不影响任何模拟步骤或阈值。完整源版本均保留。

为这次错误定位而主动暂停的180秒原段和120秒接续也保留，不抹去过程。重放仍要验证它们的输入、事件和末态；其结果与性能解释分开。4.5小时预算依据实际测得的426.112秒执行成本，仍成立，不以错误诊断作为理由。

**Correction of the diagnosis:** the frozen ocean_cli.run caller already invokes the guard only once per simulated second. The earlier claim of20ms result recounting was incorrect; the implementer inspected the function body without its caller. The unnecessary wrapper throttle was reverted. The already-running batch retains its loaded external-check version, which cannot change simulation steps or thresholds. Preserve the180/120second segments and their source versions, and verify replay. No material speedup or root performance defect was established. The4.5hour budget is justified by measured execution cost, independently of that mistaken diagnosis.

## 首组结果后的解释性分析追加

第一组共同环境结果为摄入207/206颗，剩余能量50640.647/51186.048，储存溢出16827.010/15617.189（继承/无经历）。因此增加全部三组的内核实际耗能、外部储存溢出分解，不把更多摄入、更多剩余和更少消耗混为一谈。此分解为看到首组结果后的解释性分析，不能冒称预登记主终点；其他两组同样呈现，不按效果选择。

After the first common-garden pair showed207/206particles,50640.647/51186.048remaining energy and16827.010/15617.189storage overflow (inherited/erased), Core expenditure and external storage overflow were added for explanation across all pairs. This was outcome-informed secondary analysis, not a preregistered primary endpoint, and is reported for every pair.

## 2026-10-03：会话意外中断后的交付恢复

北京时间08:41重新核查：原执行会话已不可连接，但18个正式世界的最终结果和完整保存目录都存在，最后一组也已正常到达300模拟秒。未发现因这次会话中断造成的模拟缺口；未完成的是正式重放、汇总、报告及入库。不重跑已完成样本，不把会话恢复算作新实验。

独立运行核验/分析脚本时暴露了 `cases.py` 对工作目录隐含导入路径的依赖，尚未开始核验便报 ModuleNotFoundError。将该纯JSON辅助模块改为独立读取，随后继续。此为交付脚本修复，冻结的环境和Core没有改变。用户新增的大海域、身体耗能、种群/融合/合作要求另立新版本，不回改E28。

At08:41 local time the old process session was unavailable, but all18formal worlds had final results and snapshots, including the last300-second evaluation. No simulation gap from this conversation interruption was found. Formal replay, reporting and database publication remained. A standalone script-import error was repaired in the JSON-only continuation helper before replay; frozen apparatus and Core were untouched. The newly requested larger ocean, body costs and population variants belong to a separate study.

## 2026-10-03：正式核验完成

18世界所有初末状态和接续边界通过；5个续段完整重放及首世界6000步部分重放全部匹配。核验耗时与准确范围保存在formal-verification.json。未改冻结装置，没有额外独立样本。

All initial/final states and continuation boundaries verified. Five continuations replayed fully and6000steps of the first world partially; all matched. Exact scope/timing is in formal-verification.json. No new independent samples.
