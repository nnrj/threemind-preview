# E57执行与讨论记录

## 2026-10-06：A阶段完成后的澄清与补测登记

用户质疑为何没有意识活动时运动中枢仍会动，要求核查正常设计是否被绕过。解释：A阶段的感官直接输入是明确的新排除对照，正常E56路径仍从Core观察总线读活动；没有发现正常路径把原始问句或正确答案偷传给伺服。真正的归属问题是选择器能从直接感官响应中自行学会分类，且四选一模型没有“无意图/不动作”结果。E56的伺服只是执行选择器选定的位置，尚未证明它解读了内核自主形成的运动意图。

补充登记C：冻结原E56读取器，使用原24个确认场景和完整物理背景，不创建Core。比较：①全零8帧仍调用读取器，然后伺服执行其选择；②不递送帧、不调用读取器、不发动作命令，仍推进身体和风。每题1秒等待+2秒运动/静置，记录选择、动作命令、轨迹和物理漂移。零帧与没有帧不能混为一谈。②是明确的无调用物理对照，不冒称现行UI已经实现无意图门控。上限60墙钟秒、10MiB，纳入原总预算，在当前模拟进程完成后串行执行。

本补充不改B的判据、不重训A以改变结果、不修改Core或部署中的控制逻辑。外设单独认图的成功是本任务归属排查的工程证据，不包装为新的智能机制发现；过去E50/海洋的经历、联想干预证据保留。

English: the user asked whether normal motor control secretly bypassed Core. The direct-input route is an explicit new baseline, not the normal E56 path. The selector reads sensory responses in Core and is trained on correct positions; forced four-way selection does not establish a Core-originating motor intention. Supplement C freezes the original head, creates no Core, preserves all24physical scenes and wind, and compares zero-valued frames plus servo execution with no frame/no decoder call/no motor command. Record commands separately from passive drift. This is not a deployed intent gate.60wall seconds/10MiBwithin existing bounds, sequential after current simulation; B criteria/dynamics unchanged.

## 2026-10-06：外设熟练反应与共同决定（D，执行前补充）

用户提出积极解释：反复训练后运动中枢可能记住响应模式，形成类似条件反射的快速反应；允许内核和中枢共同决定，并要求检查减少训练是否使意识作用更强。

本轮先操作**外设优化步数**，不同时减少意识教学。固定同样60条监督、Core经历、三个种子和同架构，比较100/300/1200步。1200步直接复用A，不重复训练。正常活动头除原24题外，还读E56同源旧边静默和救援的记录，固定权重比较答对数、改变选择数、正常正确而静默失去的数量以及逆向改善，避免只看净差；直接感官与无结构学习头做同预算基线。没有额外Core模拟，不因想要更大消融差而选择“最好”训练量。

这检验的是外设优化熟练度，**不是减少Core教学次数，也不是临床意义的条件反射证明**。若较少训练使正常成绩下降而消融差增大，不能单独叫意识决策变强；若正常与原始感官差距扩大且固定头对连接的依赖上升，可作为协同线索。模型优化时长和推理时延分别记录，训练更多不预设推理更快。追加计算上限10分钟、模型及结果100MiB，仍在原总预算内，与正在进行的Core模拟串行。

English: the user proposes a functional conditioned-response interpretation and accepts joint Core/adapter contribution. Supplement D varies external optimization steps100/300/1200 with identical60training examples, Core experiences, architecture and three seeds. Reuse A's1200models. Evaluate the frozen learned-activity heads on original normal/silenced/rescued E56 inputs; report lost and gained correct answers and changed choices, not only net accuracy. Equally fitted direct-input and nonplastic-Core baselines retain the same budgets. No new Core simulation or selection of the dose with the largest lesion effect. This varies optimization practice, not Core teaching repetitions; larger lesion differences with degraded normal accuracy do not alone show stronger Core decisions.10minutes/100MiBwithin the registered total, sequential.

## 执行顺序与归因范围

第一来源223的固定读头新题25/32，达到24/32扩展门槛。先在这个预定首来源完成局部屏蔽、匹配、恢复和移植，第二来源279复核主效应和冻结头补课；第二来源结果产生前即明确此资源分配，不按哪一来源成绩更好挑选消融对象。原600副本与90分钟预算保持；不自动把两来源全部条件再翻倍。用户后续强调“共同决定仍须排除ThreeMind只是附庸”，本批继续完整执行归因，不取消对照、不把系统分数冒称Core贡献。

English: source223qualifies25/32. Complete selective controls in this preregistered first source, while279replicates the main effect and frozen-reader correction. This allocation precedes source279results, respects600instances/90minutes, and does not select the better source post hoc. User clarification retains all attribution goals despite accepting joint control.

## E：只读外设敏感性诊断，执行前登记

首历史目标边静默后仍13/16，提示固定读取器未必主要使用这些边。本批额外定位读取器依赖哪些**已有观测字段**：按物理端口分视觉、文字、教师标记、本体/环境；在复制的离线观察数组中分别置零，或把某组字段在两相反历史之间交换，再用固定读取器评分。并分别检查激活/抑制/直接/联想字段。遍历全部预定组，不挑最漂亮结果。上限30秒/5MiB；不推进Core，不把派生数组当成真实活动，不写回原证据，更不会用于日常表达。置零会造成分布变化，交换也可能产生不自然组合；这些只定位外设敏感性，不能代替Core中的因果干预。教师标记只来自过去真实示范，测试时标记已移除；若读取器利用其残留区分历史，须明记，不能冒称已经掌握物体概念。

English: first-history target-edge silence retains13/16. Supplement E probes fixed-reader sensitivity to physical port groups (vision, text, teacher marker, body/environment) and four activity fields, using zeroing and cross-history swaps in copied offline arrays only. Evaluate all predetermined groups;30seconds/5MiB,no Core advancement. Keep derived controls explicitly separate from original activity and production expression. Distribution-shift caveats apply. This cannot substitute for Core causal interventions; residual teacher-marker history is not current-answer leakage but could serve as a history shortcut rather than an object concept.

## F：在真实Core副本中验证标记活动（执行前登记）

E的离线诊断：标记字段置零25→16；标记字段换为另一历史后按原历史仅3/32、按供体历史25/32。交换视觉/文字字段不改变25/32。为避免把人造读出数组当内核因果证据，追加F：在102秒Core快照的副本中，①仅清零教师标记受体节点的activation；②仅把这些节点的activation换为另一历史的值；③交换等数量自身指针受体节点的activation作匹配控制。其余节点字段、所有边/快状态、能量、时钟、在途信号原样保留。此后照常递送完整物理环境和问句、运行Core、读取真实总线帧，外设固定且不修改输出。每种干预两历史各16题，共96分支。保存字段级收据和原/供体分数；互換不是自然发生过程，也不声称已经消除了全部标记历史。上限15分钟/150MiB，仍在600实例/90分钟总预算内。该试验优先于重复跑第二来源。

## 第二来源运行前的设计修正

核查原生代码发现当前Core的seed只用于可选空间坐标；普通配置未用该空间计算。仅把223改成279而保持所有感官/环境完全相同，不能作为有意义的独立复核。因此第二来源在运行前明确增加**天气种子47→103**，视觉/文字通道映射仍91、课程与判据不变。两历史及其关学习对照仍共享同一环境。223已完成结果不重跑、不改；279不是在看到成绩后选择天气。只称两个环境来源复核，不称两个独立总体或多个独立受试者。本修改只在实验世界构造参数生效，不改变内核、生产默认或冻结登记原文。

English: E suggests residual teacher-marker activation mediates history selection. F intervenes in copied102sCore states, not decoder inputs: clear marker-node activation, transfer just marker activation from the opposite history, or transfer the same count of own-pointer node activations. All other state is retained; run the unchanged query/world/Core and fixed reader.96forks,15minutes/150MiBwithin the registered total. Before source279is run, fix a design flaw: Core seed alone only changes optional spatial coordinates here, so it would not provide an independent variation. Source279uses weather seed103instead of47, retaining sensory map91and curriculum; paired controls share that world. Source223is untouched. This is preregistered environmental replication, not post-result seed selection.
