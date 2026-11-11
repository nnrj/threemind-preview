# E55 execution notes / 执行记录

- 2026-10-06，事前：回应用户背景与复习纠正。读取E43实测报告及E54代码，确认二者差别。新增环境外设和逐概念课程，原内核、旧世界/1和旧证据不变。起始账户62%，可用RAM10.68GiB、C9.43GiB、E40.12GiB。主问题为严格指向下的形状/颜色表达，非重复仅有总体命中率的测量。
- 开始前工程失败：CLI显式内核标识遗漏`threemind.`前缀，被注册表拒绝；尚未创建Core或推进模拟。修正为完整标识，原启动记录保存在`s223-spaced-teaching-preflight-failed`，不计为阴性实验、不覆盖。
- 课程序列核对：168次，各概念21次，句长最多13字符，完整占用1.5秒，末课516秒结束。教学位置0～3的次数分别为46、36、34、52；因此“平衡”严格适用于每个场景的属性频次、所有测试/校准的指向覆盖，不能称教学四角次数精确相等。各条件保持同一内容/位置序列，不在看到结果后重排。正式新视角测试每个位置等量出现；这是课程局限，非模型结果。
- 首个正常组完成：教学23.08墙钟分钟；96校准＋64测试恢复与推进合计约17.72分钟。校准96/96，熟悉组合的新视角29/48，未见组合6/16（形状0/8、颜色6/8）。在查看其他组结果前登记：保持三组主要比较；第二来源因2小时总预算后置。由于正常组已经出现高于打乱11/48的可用表现，即使另训的无学习表达器也可答题，仍应在同一个正常表达器下检查已有连接静默及恢复，避免把外设补偿能力误当作原模型未使用连接。追加已见视角的新位置排列对照，用于分开视角外推与指代问题；不加入测试答案训练。
- 2026-10-06，执行次序修订：用户再次明确主目标是辨认形色组合并实际移动肢体指出对象，背景和复习是条件，上一轮遗留问题可在适当阶段验证。正常与无学习课堂已完成；相同表达器静默原有连接为27/48，原正常29/48；先恢复8题的原始活动完全一致。保留原定等间隔组和第二来源为未执行待办，不将其记为完成或取消。当前剩余预算优先用于已见视角的新排列对照，以及下述实际运动课程。此修订发生在运动课程和新排列检验之前；不改变原课堂判据。

## 运动课程与读取时间范围对照：运行前登记

从正常间隔复习来源的516秒快照继续，全部身体/环境感官持续开启，内核与映射不变。十二种非对角形色组合各先连续示范12次，再逐项复习3轮；初始同项间隔3秒，后续循环间隔36、72、144秒。每次包含完整“请指出XX的YY。”以及2秒实际受教师引导的指针移动，余下时间仍采样。教师只在示范期间施加外部力，不在Core内写入目标或奖励；测试时没有教师标记、教师力或答案坐标输入。全部12种组合各15课，共180课，684模拟秒。背景空隙保留四物体和实际身体。每组合初轮的四个位置各3次，视角0～3各3次；不同课有独立身体起点。

每个场景同时含同色异形、同形异色干扰物。两种运动Transformer使用完全相同的示范和回归目标，只比较输入过程：最近4帧，或从本次完整请求到当前时刻均匀取16帧；均为实际输出总线的原始场，不减基线、不输入目标标签。后者保留更长的活动过程，但这是外部工具记忆，不能冒称Core新增长期记忆。两者固定同种小模型和训练步数。

正式32次闭环测试覆盖16组合、每组合2个布局/视角（0和5）；四个对角组合未接受该组合的教学。每次2秒动作：分别报告末端最近对象、进入0.15米范围、最终停留，以及正确切换请求。对完整过程头另做同场景/同起点改问另一对象、原有连接静默、零活动；恢复4次核查干预可逆。先完成正常和最近4帧；若预算不足，对照按改请求、静默、零活动、恢复顺序执行并明确未完成项。读头训练与测试不允许用实际测试答案补课。本轮预算仍是原900分支、2小时累计计算、6/8GiB证据阈值，不无声提高。

English amendment: after the user's renewed emphasis on actual limb pointing, defer the unstarted equal-interval and second-source groups. Keep their questions open. Prioritize novel-layout reference tests and 180 grounded motor demonstrations (12 initially consecutive + 3 expanding reviews for each of 12 taught colour/shape pairs; 684 simulated seconds). Compare otherwise identical motor heads reading the recent four raw frames versus sixteen samples spanning the current request/action episode. Teacher forces are training-only; test targets and object identities are never inputs. Test actual closed-loop reach, request switching and same-head edge silencing/zero-activity controls under the original resource ceilings. Longer observer history is an external adapter capability, not evidence of newly added Core memory.

- 运动教学尚在执行、测试尚未开始时发现评分分层细节：同场景改问另一物体后，该物体是否属于留出组合，应按实际请求对象重新计算，不能沿用原问题的`held_out`。运行中的Python已载入原代码，主得分不受影响；原始结果保留，`analyze.py`按真实请求对象作权威分层，后续CLI实现也已修正。不是看到阴性/阳性结果后的判据更换。
- 运动测试前另登记外设校准候选：旧工具按训练误差选取权重，没有按完整新示范段验证；相邻动作样本不能代替独立示范段。新增可选验证集参数，旧调用行为不变。预算允许时，将每组合最后一次复习整段留出（12段/120样本），用其误差选择完整过程头；其余168段/1680样本训练。最多另训一个头，不用正式测试答案；验证误差若大于0.05或不足训练均值恒定动作基线的20%改善，停止扩大该候选。若通过且余下计算足够一套32题再加20%余量，另做相同实际指向检验。它改变了外设的样本划分/选模，须与主窗口对照单列，不能归为内核增强。前述两主头按原注册照常完成。
- 主完整窗口测试完成后：180示范全部到达，但自主终点到达0/32、最近选择10/32、途中经过2/32；单套32题耗7.77分钟。两小时预算已用约101分钟，尚有最近4帧、三个整套对照和恢复。决定完整保留正在执行的短窗测试，在其完成处通过本研究STOP文件暂停自动后续段，优先执行此前登记的整段留出外设验证。原计划改请求/连接静默/零活动/恢复保留为未执行，不冒称已完成。若验证不通过，不以低质控制器的大批消融代替改善实际指向。没有改动当前运行的Core或正在评分的试次。
- 两主窗口均完成：完整过程终点0/32、短窗1/32，最近对象均10/32。按段留出候选的误差0.07872，未通过原0.05绝对门槛；相对恒定动作0.23895已降低约67%。**后验执行偏离，明确单列**：原绝对误差门槛未按实际肢体精度校准，不能代替用户要求的真实动作测试。保留`passed_registered_gate=false`，不宣布验证达标；尚余约11分钟计算，另运行唯一一套32题实际指向作为探索性复测，仍按原0.15米/正确对象标准评分，不再换头、不再扩样。原定大批消融仍不扩张，预算不提高。这不是原事前门槛通过后的确认实验。
- 2026-10-06结项：唯一复测最终到达1/32、最近正确6/32、经过4/32，未改善指向。全批25完成阶段、583创建尝试、116.77分钟模拟/拟合，停止新增实验；未执行项目原样保留。账户实测62%→66%，共享增量不能全部计为本研究。主问题未解决，不改Core默认，不以“更多背景”继续旁支扩张。记录下一步拆分所指选择与运动执行的建议。
- Closeout: the exploratory head reaches 1/32, selects 6/32 correctly and enters four targets. Total completed compute is116.77 minutes/25 stages/583 creation attempts. Stop new simulation; preserve unexecuted controls and the failed validation gate. Recommend separating target selection from motor execution before expanding attribution. This recommendation is not a completed or newly started study.
