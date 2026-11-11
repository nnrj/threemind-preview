# 2026-11-09：新授权批次已登记并运行

> 公开存档说明：下文是该日期的交接记录，不是当前运行指令或启动授权。运行任何实验须先核对当前状态与协议。


## 2026-11-09 13:52：首批已完整交付，勿重跑

8独立个体、112条正式序列、2,688题全部结束。G2为8/8达标；G1/G3/G4均0/8。冲突题联合正确4/64→62/64，新单路首窗40/128；混合题自主出口102/192，反馈阻断84/192，强制提供信息184/192。2,856完整边界、136连续链、全部原件哈希和另一份计数实现通过。

本机科研record `4159a847-5671-504a-b0dc-800fca835e96`已completed/verified/pending0；573,213,406字节原包完整API读回，SHA256 `d615b82cea65085458331e84438dc6c7ea15528722690b96a7ac38855dfc46b9`。报告、回执入口见[delivery.md](delivery.md)。status的awaiting-analysis/8和automatic-analysis的awaiting-report-review均为旧阶段快照，不能据此重跑。

正式适配器一直读取1秒20帧中均匀选取的8帧，包含激活、抑制、直接/联想四项及位置编码。作者质疑“只看最亮”时，已澄清那只是另行登记并在计算结束后运行的均值诊断。384个参照首窗的记录帧中，七个输出端口正向活动字段为0而抑制非零。目标正向阻断改变768/768窗口端口数据，768次类别输出仍全同。signal_audit为见到均值诊断结果后追加的只读解释；不得冒充预登记预测。

本批结束，不新增教学、不自动扩48来源或启动身体反馈/睡眠样重组。后续优先另定激活/抑制、双向通路与动作时序表达的检验。Core、默认、旧个体、作者论文及旧自动任务保持原状。下方启动信息、旧PID仅作历史记录。

## 2026-11-09 12:27：继续至完整结果交付

用户追问实验结果，明确不接受只报协议或启动。此次继续完成8来源、复算、双语明确结论、API完整读回与结项，不重复启动。用户另允许按预计时长定期检查；本次仍持续核查当前唯一运行宿主。当前快照完成5/8，最新origins/o5/h1/sham/trial-014。按近期边界速度仍需约一小时，4小时科学宿主预算未触及。

原audit_corrections --watch重复读取已提交原件，12:12以watch_corrections_cached.py替换，只在出现新完整开发记录时检查。旧观察器按PID/创建时间/命令精确停止；科学host36548一直未动。替换回执在postprocessing/observer-replacement.json，新日志correction-monitor-20261109-121132.out.log/.err.log，资源守卫仍每秒执行。

前4来源阶段数据（不是全批结项）：G2均过，冲突题后窗联合正确31/32；G1新单路联合19/64；G1/G3/G4各0/4。未据此改样本、课程或阈值。查看前4来源后单独登记posthoc-projection-plan.md：对完整1秒20帧的声明端口取平均激活，按原教师映射取唯一最大者；并列或全零算无明确输出。port_diagnostic.py必须等8来源结束再运行。它是事后解释，不替换原适配器或主分数。API note 10e2982a-95ec-56cf-8876-2472540e0471已同步，规则和源码原件位于postprocessing/declared/。

结束后的after_run.py会自动analyze→audit_integrity→summarize；检查其回执和日志，避免并行重复分析。之后人工式助手审阅原数据、另跑port_diagnostic.py，写report.zh.md/en.md和review.json，再用publish.py本机API归档、全包读回、pending0结项。所有报告必须明确回答G1—G4及对ThreeMind的意义，按原协议区分未达与测量无效。历史与R43目前只记启动，结束后追加真实结果。

11:36续记：前2来源714个完整边界、28条连续测验序列已另用纯JSON/哈希路径核对，全态及连续链一致。只读后处理 `after_run.py` 已单次后台启动，launcher30400，日志postprocess-20261109-113253.out.log/.err.log。它等待本次准确host身份退出且8来源全部完成，再依次analyze/audit_integrity/summarize；失败保留现场，成功写postprocessing/automatic-analysis.json并停于awaiting-report-review。不重启科学宿主、不生成结论性文字或自动发布。核查该回执，勿因旧awaiting-analysis快照重复计算。

准备提交0f271c4为本地记录，运行源/协议哈希和真实实现复核未变。双语API协议读回全文相等，pending=0；科学记录当前仍为running，未结项。两种文言、双语通史、列传和R43条目已记录本阶段启动，尚无新增成绩声明。

最新核查：约11:17（北京时间），首个来源全部完成，第二个来源h1测验进行中；真实宿主PID36548，创建epoch1794193587.2453048，guard为同宿主独立每秒监视线程。日志 `science-20261109-110627.out.log/.err.log`。这些是历史观察，继续前核对实际进程与 `host.json/status.json/current.json/in-flight.json/STOP`。不得重复启动。

科研project `09e358fa-b05a-4bc0-93b2-643148fb72ab`，record `4159a847-5671-504a-b0dc-800fca835e96`，登记pending=0。源码 `experiment.py` SHA256 `ac70709d0c37a0220e6fb33aed7e1d04554a9732f7c9488f165f94997c5fa697`；完整哈希见数据目录runner-manifest.json和registration.json。正式源为26110900—26110907；验收源26110802不计入N。

只读 `audit_corrections.py --watch` 同时检查已提交的开发记录：若出现第一窗口正确而第二窗口错误、且下一轮选择器未涵盖的情况，会请求完整边界STOP，不能将其遗漏当成机制失败。当前已审的阶段无该遗漏。此观察器不载入或推进个体。

计算完成停在awaiting-analysis。依次运行 `analyze.py`、`audit_integrity.py`，再审阅双语报告并用本目录publish.py完整归档/API读回/pending0结项。报告还须核验基础权重与包含快速增益的有效权重，明确匹配残差。运行源和冻结协议不改。若新死亡in-flight或需要改变规约，保全现场并询问。

API-only是本任务启动的127.0.0.1:8877，launcher36796；准确创建身份见api-20261109-110506.json与实际子进程。没有启动队列worker。外部数据目录写入需环境授权；不结束用户数据库或其他进程。

## 启动前记录

作者批准情境判断、证据修正与主动观察实验，遵守训练规约，实质冲突先询问。首批8独立来源；先培养个人时序Transformer输出接口，随后冻结并教Core新对应。完整连续课程、先密后疏复习、最多两轮纠错；必要因果分支单列完整父体。只运行本新批，旧实验与自动任务保持暂停。

先读 protocol.zh.md/en.md、最新 status/host/STOP/in-flight/日志及真实进程。此段记录准备时的状态：当时尚无科学成绩、平台登记或正式启动。Core、默认、旧原件和作者论文不改。原件 E:/ThreeMindData/experiments/2026-11-09-context-revision/v1，冻结、仪器验收和平台登记均在正式启动前完成。

当前实查（历史快照）：2026-11-09约10:35本地，未发现实验Python宿主，E盘103.97GiB，提交17.27GiB、物理14.02GiB、C盘16.68GiB。禁止把这些数值作永久启动依据。保留5/4/5/25GiB，每秒守卫，完整边界暂停。
