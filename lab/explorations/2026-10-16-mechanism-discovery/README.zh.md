# 机制发现研究准备包

**2026-10-16报告修订入口：** 本批11组已补齐科学分析、明确结论及对ThreeMind的意义，原分数与原件保留。[最新修订索引](report-revisions-20261016.zh.md) · [全历史核查](../../../docs/zh/plans/report-conclusion-audit-20261016.md)。旧报告链接仍对应其历史原版，不触发重复计算。

2026-10-16追加验证已结项：X1局部经历及二门选择转移达标（6/8来源，供体目标0/48→44/48，无关题44/48不变）；X2在30/60秒各8/8实现保存与提示依赖表达分离，1/30/60秒各8/8实现瞬时/持续表达分离，重学节省均0轮、目标未达标；X3 ThreeMind四项各8/8全过，四个登记对照均未全过，区分目标达标。80完整单位、5,568完整快照，原件审计及API全包回读通过，verified/pending0。所有判据冻结于b574881；旧原件、E15及失败分数保留，不改Core/作者论文，不恢复E69。 [Report](closure-report.zh.md) · [Contract](../../../docs/zh/plans/experiment-conclusion-contract.md)

2026-10-16首批探索交付：七个子批完成、一装置批按失败结项，八记录当前verified/pending0；原件包均经API完整回读。M1定位选择性短窗表达通路，M3表明经历依赖组件也由简单记忆对照实现；M2保留时序预测失败，随后新相位/强度/23秒保持材料的首周期预测通过。只读移植审计确认/5.1不能直接套用旧state/2同拓扑工具。M1—M3大问题仍开放，未完成确认或整个计划。本夜不再扩展M2，首批自动接续按范围PAUSED，旧E67/E68/E69全程PAUSED。 [First-batch report](first-batch-report.zh.md) · [Phase report](report-phase.zh.md) · [Graft readiness](exchange-readiness.zh.md)

**2026-10-16约05:03追加：** M2接收汇合预测已完成8新来源/448因果副本；单路可测6来源的联合/单路比正常1、求和2，另外2来源保留为零。逐路门限及汇合近似在提示前保存，224嵌套预测均判断对零/非零，N仍为8；只支持对称同时到达的新材料，不是普遍记忆定律。API全包读回verified/pending0。前v1仅装置白名单未过，科学来源未生，失败原件保留。下一项有界时序探索检验同步假设，不扩大确认，不改Core或恢复E69。 [Report](report-fusion.zh.md) · [Theory map](m3-theory-map.zh.md)

**2026-10-16 04:35更新：** 本目录已从准备转入有界探索，以下准备版原文保留。M1、M2首批、M3经历依赖组件及独立采样校准均已API回读、verified/pending0结项；研究总计划未完成。[M1](report-m1.zh.md) · [M2及更正](report-m2.zh.md) · [M3-C1](report-m3-c1.zh.md) · [采样校准](report-sampling-calibration.zh.md) · [实时接续](HANDOFF.md)。原E69仍暂停，不重复运行已结项批次。

[English](README.en.md) · [总方案](../../../docs/zh/plans/mechanism-discovery-20261016.md) · [实施协议](protocols.zh.md) · [证据矩阵](evidence.zh.md) · [验证](verification.zh.md)

2026-10-16。已实施阶段0的资料准备与离线工具；七个工作包均未运行。本目录没有创建个体、运行实验、恢复E69、启用定时任务或发布结项的入口。暂停仍有效，正式装置、8来源探索及确认另待执行条件满足。

从仓库根目录执行以下只读命令：

```powershell
$prepPython = '.work/kernel-venv/Scripts/python.exe'
& $prepPython -X utf8 lab/tools/mechanism_preflight.py validate lab/explorations/2026-10-16-mechanism-discovery/program.json
& $prepPython -X utf8 lab/tools/mechanism_preflight.py audit lab/explorations/2026-10-16-mechanism-discovery/evidence-manifest.json
& $prepPython -X utf8 lab/tools/mechanism_preflight.py power --effect 0.5 --family-size 3
& $prepPython -X utf8 lab/tools/mechanism_preflight.py power --kind paired-binary --effect 0.1 --family-size 4 --baseline-success 0.5 --discordance 0.3
& $prepPython -X utf8 -m pytest lab/explorations/2026-10-16-mechanism-discovery/test_preflight.py -q
```

输出只到stdout。详细审计／功效结果保存在忽略的`.work/mechanism-preparation-20261016/`，不得把它们或旧原件强制加入Git。工具不访问服务、网络、数据库或Core，只有`validate / audit / power / compare-witnesses`四命令。结构检查通过只说明准备格式符合本版范围；所有运行闸门仍pending，输出始终`execution_authorized=false`。

`audit`流式核验大小和SHA256，不解压或载入个体，不遍历全部磁盘。清单冻结的是本次选择；HANDOFF等活文档以后改变会报告mismatch，应保留旧清单并另立审阅版本，不能自动刷新哈希掩盖变化。原件缺失、无法读取、哈希不符分别报告。旧迁移登记仍是权威来源，此清单是跨材料审阅索引，不另建存储系统。

`power`是统计抽样模拟。连续模型为独立来源的正态配对差、双侧t检验；二元模型为每来源一个配对二元结果、精确McNemar检验。多题结果不得当独立来源塞入此模型。二元规划必须声明基线概率和不一致配对比例。候选N为48至128、步长16；10,000次固定种子模拟，功效Monte Carlo 95%区间下界达0.8才推荐条件性N。区间只描述模拟误差，不覆盖真实方差估计的不确定性。超过范围仍不足时返回重设计，不自动增加样本或换终点。正式统计若改用分层／稳健估计器，必须重新规划。

`compare-witnesses first.json second.json`要求`threemind.observation-witness/1`，并核对subject_id、kernel、canonicalization、boundary、simulated_time_us、input_sha256、event_order_sha256，以及10个组件SHA256：core、peripheral_weights、optimizer、random_state、body、mappings、recent_activity、actuators、environment、input_cursor。规范化方案须事前固定并保留动态字段，不能通过删掉差异使见证相同。无优化器的系统也应对明确的空组件编码取哈希而非省略。比较器只核对提交的见证，不产生真实引擎验收；原生完整保存／恢复仍使用既有工具。

后续顺序：原件／谱系回读 → 文献及干预字段核对 → 真实装置验收 → 解除相应暂停后8来源探索 → 具体功效和题表冻结 → 确认 → 新来源复验。实际运行前通过统一科研API登记，保留独立幂等请求及回执；不调用历史E69宿主或旧报告发布脚本来启动本计划。


2026-10-16时序批追加：8新来源/288因果副本完成，原独立到达近似失败，主MAE0.002061211；错开1ms的经历差微降约0.164%，并非预想增强。源码与轨迹提示输入仍按同一周期发放，事后相位解释不冒作预先验证。API全包回读verified/pending0，旧预测/评分不改。另冻结本夜最后一项M2跨周期新材料检验：8新来源、672副本、23秒保持及新教学强度，尚未运行；之后汇总首批，不扩大确认。 [Report](report-timing.zh.md) · [Next frozen protocol](pilot-m2-phase.zh.md)

## M5 — 2026-10-16

2026-10-16 M5 已完成并结项：8 个独立来源、两种相反教学历史，固定端口读取器的新对应 64/64；目标连接静默降至 0/64，匹配静默保持 64/64，恢复为 64/64，旧题保持。端口固定表达、因果归因及读取范围优势各 8/8 来源达标。全活动固定表达与其因果归因各 0/8，未达标；全活动续校准的新剂量成绩 0/128→128/128，收益目标 8/8 达标；端口续校准前后均满分，增益目标 0/8，未改门槛。1,824 道测验、2,024 份科学完整快照审计通过，原件 API 全包回读 verified、pending=0。旧 E69 和自动化仍暂停，Core、旧报告及作者论文不改。

[Report](m5-report.zh.md) · [Delivery](m5-delivery.zh.md)
