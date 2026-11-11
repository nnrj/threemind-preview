# /3 方案 1 / 方案 2：文字用例与同源物理遥测背景

2026-10-08，Core 运行前登记。用户要求：“测一下保持的选项设置为方案1和方案2时，连接的保持和消退情况。用物理遥测作为背景。”随后明确：“注意，只是那物理遥测作为背景，仍然需要有文字刺激作为测试用例。实在不行就进行一轮简单的形色测试”。本批实施文字用例，不启动完整形色教学，不修改 Core、默认参数、旧个体或旧实验。

## 问题与完整对象

主问题是在相同文字经历及背景下，方案 1 `adaptive-half-life` 和方案 2 `legacy-stability` 的文字相关连接能否形成、保持及消退。两方案均使用修复后的 `continuous-memory/3`、状态 /3.1；方案 2 不是整套旧内核。H 增长保持默认对数饱和、增益 0.2，节点回收自动，留点/休眠/唤醒默认关闭。普通学习、新颖性、抑制及其他参数相同。唯一共同的非默认 Core 参数是 `quiescence_death_us=10^12`，用于背景停止后的结构测量，不推断普通个体默认寿命。

实验对象为新空白 Core + 固定非学习文字感官 + 只读冻结背景回放及其游标。没有学习型翻译器、优化器、身体或语义输出器；不是完整意识及其感官外设的形色答题实验。各组出生固定公式、各自连续发展。保存 Core、感官配置/接线、输入时间表及游标；提示词测试为显式独立副本，父检查点不接受测试或反馈，不替换/重置旧个体外设。

参照上一批修复探针 `2026-10-08-retention-repair`，保留内核及默认参数，改用真实文字和物理背景，不能把匿名双通道结果当成这批结果。遵守训练规约的身份、教师输入/读出区分、渐疏复习、原始结果和对照保留要求。无学习型读出拟合，因此没有将校准数据冒作正式题的环节。

## 物理背景来源

使用 `.work/language-spaced-20261004/physical-telemetry.jsonl` 的 **host 范围**，来源为 E43 已完成的 840 秒真实 OS 采集；保留原始时间戳、刺激通道、强度 0.2、归一化、平滑及不可用原因。先核对并保存来源文件/元数据哈希，复制压缩证据；两方案重放完全相同的冻结帧。不是本轮实时采集，不循环、不拉伸、不补造样本。process 范围为当时记录器进程，不进入本批；runtime 自反馈和随机背景关闭。

背景在模拟时间 [0,834s) 递送。主保持评价截至 830s，全部有背景；停止背景后的阶段另列“全部外部输入停止诊断”，不能称为物理背景仍在的保持。测试副本使用同一时刻后续两秒背景，且遵守 834s 截止。物理来源单一，结论不能代表不同机器/负载。

## 文字用例与四组配置

既有 `TextSensor`，`literal-character`、NFKC、每帧 1 字、50,000 μs/字、gain=1，接线 seed=20261004；刺激强度 1。此已有非语义编码选项便于只读追踪文字连接；不是更改内核，也未使用 LLM/预训练语义或另造正确答案通路。与 E43 的 Qwen 感官/译器不同，不比较其答题分数。标签留在观察记录，Core 只收匿名数字刺激。

四句为“苹果是红色的。”“树叶是绿色的。”“天空是蓝色的。”“雪花是白色的。”。四组分别是每种保持方案 × 先密后疏重复/单次呈现，全部新空白且使用同一接线及物理背景。

| 阶段 | 每句次数 | 同一句间隔 | 阶段结束（模拟秒） |
| --- | ---: | ---: | ---: |
| 逐句集中后轮换 | 12 | 0.5s | 24 |
| 交错 | 12 | 2s | 48 |
| 渐疏 1 | 8 | 4s | 80 |
| 渐疏 2 | 8 | 8s | 144 |
| 渐疏 3 | 8 | 16s | 272 |
| 渐疏 4 | 8 | 32s | 528 |
| 共同末次呈现 | 1 | 四句依次在 528/528.5/529/529.5s 开始 | 530 |

重复组共每句 57 次，228 句；单次组仅最后共同呈现四句，此前只经历背景。后者是剂量差别明确的“单次对重复”对照，不冒称等剂量排程比较。两保持方案在各自课程下输入逐项一致。无强刺激、正确性驱动追加训练、隐形复习或参数搜索。

## 时点、指标与提示测试

保存 24、48、80、144、272、530s 的教学进展；530s 为固定保持基线。保持观察 560/650/830s（+30/+120/+300s），背景仍在。834s 停背景；继续观察 864/954/1134/2034s（背景停止后 +30/+120/+300/+1200s）。没有结论驱动的无限延长。

主指标：文字—文字边（TT）、文字—遥测边（TB，两方向）、遥测—遥测边（BB）的活跃数量、权重总量及平均量。固定跟踪 530s 出生世代的连接，报告存活数/占比、留存权重与基线比；后来重建的边不冒充原边保留。节点按受体对应，边按端点节点 ID 加出生时间追踪。另列八个提示字与对应颜色字间的定向连接、H、稳定度及节点支持度；未形成的边不能记成“后来遗忘”。

在 530/560/650/830/1134/2034s 从各保存点分出“苹果”“树叶”“天空”“雪花”、未教提示“石桥”和无新文字六种副本，各观察 2s，每 20ms 只读记录全部节点激活。提示不含颜色，强度 1，颜色没有被直接提示。普通学习继续生效；测试副本不回写父线，避免测试强化影响后续保持时点。

所有既定输入在出生时入队，观察时点包含该时刻已排定的输入；各阶段边界的教学统计因此可能已包含下一阶段首字，530s 及随后保持时点没有此重叠。测试副本的新提示从保存点后 1 μs 开始，无提示副本采用同一观察原点，避免将新事件追加入父线已经结算完的事件阶段。方案 2 保存的 H 仅为共同状态字段，不解释为其遗忘保护。

只读联想诊断：对“红/绿/蓝/白”各自字通道的激活积分，主窗为提示后 0.5–1.0s；同时保留 0–2s 全窗。扣除同一来源、同时间无提示副本，保留有符号差值；仅最大值 > 1e-6 且相对第二名 > 1e-6 才记为可分辨，否则未分辨，不强行挑答案。报告原始量、差值、配对命中、未知提示偏向，不称自然语言回答或概念理解。完全未学组没有强制“正确颜色”。主终点是连接保持，不能用联想排名替代。没有学会与学会后遗忘分开。

## 执行、验证与停止

生产 Rust release 独立运行四条完整主线和测试副本。Python 参考后端对两保持方案重复课程前 24s 完整输入/状态及一次恢复续跑做同源核对；若有超过相对 1e-12、绝对 1e-14 的状态差异，停止解释实验，保留失败证据。同后端恢复必须严格一致。文字感官/背景映射不重建或跨个体移植；回放游标完整保存。

所有输入清单、接线、原始背景、源代码/native 哈希、主线与副本快照、父哈希、读出轨迹和分项 Core/观察/存储耗时留存。观察频率不得写回状态。无连接数/传播次数/学习次数配额；宿主仅在超过 30 分钟实验总墙钟或 512 MiB 新证据时明确停止实验并保存状态，不通过跳过内部事件改变动力学。单进程执行，不启动数据库/用户服务，不调用外部 AI，不 push。途中失败保留独立目录，不能覆盖或算作阴性。

## English registration summary

Preregistered before Core execution, October 8, 2026. Four new subjects compare repaired /3 adaptive-half-life versus legacy-stability, each under expanding repetition (57 presentations per sentence) or a single matched final presentation. The sentences pair apple/red, leaf/green, sky/blue and snow/white through the existing literal-character sensor (NFKC, one character per 50 ms, intensity 1). This is a Core/text-sensor/recorded-input mechanism study, without a learned language decoder or body.

Replay the same host-only portion of the archived E43 840-second real OS recording at intensity 0.2 with exact timing, no looping/stretching and no process/runtime self-feedback. Background remains through the primary +300-second retention endpoint and stops at 834s for a separately labelled no-external-input diagnostic. All Core defaults remain except the common extended quiescence-death grace (10^12 μs) needed for structural observation.

Track text/text, text/background and background/background edges, plus the fixed edge cohort at 530s, without counting recreated edges as retained originals. Read-only two-second cue probes fork from frozen checkpoints and never rehearse the parent. Color-character activity and matched no-cue subtraction are diagnostic projections, not natural-language answers. State/adapter/cursor continuity and independent Python/Rust agreement are mandatory. Stop and preserve evidence on mismatch or explicit host wall/storage limits; never impose internal dynamics quotas or silently change defaults. Full shape/color testing is outside this batch.
