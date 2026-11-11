# E60执行记录 / Execution notes

2026-10-07。原设计登记在所有实验前；旧Core、默认和证据保留。

- 初始资源：可用RAM9.01GiB、C10.07GiB、E72.69GiB；GTX1650/CUDA可用；账户用量0%。
- 注册研究项目：5a6ba1f4-0906-4603-8a85-e625785dfb66。基础工具与登记本地提交6e69547，无push。
- 默认pytest临时目录受沙箱权限限制；改用获准的项目内临时目录运行15项工具、旧眼兼容、过程评分及回放检查，全部通过。没有为此访问或清理旧pytest目录。
- 器械8项校准通过；/5无鼻输入与/4保持一致，鼻子只改变真实光线相交。眼手无须强制连续注视时长就能停稳。
- 基础教学52课/288模拟秒，1768个外设监督样本。四技能实际开课间隔均为3秒九次，随后6/12/24秒。此处技能是看、指、同时动、保持，不把不同布局说成同一个固定对象概念的重复。
- 采集前向因果顺序：外设训练特征只包含动作前已观测的Core过程，不把该动作引起的感觉变化倒填为先前意图。首采样不发运动命令，不收取缺少当前提示的监督样本。
- 教学是教师引导的身体示范；其成功不算意识自主控制。控制器接受16个最近采样，初期不足时重复最早可用帧作固定外设填充（不改Core或原记录），无整题历史压缩，无逐例归一化。
- 独立验证示范用于外设权重选择，不能代替Core教学；最终闭环问题不用于外设拟合。

English: resource and registration facts above were recorded during execution. The52lesson schedule gives each of four motor skills exact3s early onset intervals followed by6/12/24s. Assisted performance is not autonomous success. Training features precede their actions; first-sample commands/labels are omitted. Readers use the last16actual samples with fixed prefix repetition when insufficient, never changing Core or evidence. Separate demonstrations select adapter weights; final tests do not.

## 同日：训练器故障、更正与重训

详见[外设更正记录](reader-amendment.md)。原批次抽样错误导致大样本时抽到0个样本；损失NaN、梯度0，只剩权重衰减。原三次拟合、两次闭环保留为工具失败，不用于意识能力或中枢组织比较。修正后，新大样本回归测试通过，11项运动/光学/恢复/回放测试通过。原共同结构无需改变，训练MSE从0.1569降至0.0071，独立验证MSE从0.2046降至0.0456；这仅说明外设开始学到示范，尚不是自主注视结论。CPU和CUDA单步梯度均正常，不是显卡或Core故障。所有重训用`fit2`身份；没有重新输入或修改旧教学记录。

浏览器自动验收限制：内置浏览器安全策略拒绝本地`file:`HTML。未使用其他浏览器、localhost代理或截图脚本绕过；继续静态脚本检查及数据打包测试。本轮回放可供用户本地打开，但自动视觉验收尚未完成。

English: preserve the initial large-batch sampler failure and mark it invalid for capability comparisons. Fixed fits use `fit2`; shared training/validation errors improve to0.0071/0.0456 on the same unchanged data. Normal CPU/CUDA gradients rule out a general accelerator failure. This is adapter fitting, not yet autonomous fixation. Local-file browser preview was blocked by the browser security policy; no alternate route was used. Static and packing checks continue, automated visual validation remains unavailable.

## 同日：确认比较与教学信号核查

52课之后实际执行12次练习和24次纠正示范。确认比较按[追加登记](comparison-amendment.md)统一外部世界，用补课前后各12次独立教师示范校准外设。每组12题，四类各3题，每题6秒且3秒时改变目标；题目和标签不用于拟合。

另做纯器械光学核查：24个目标在共同初始眼位全部改变实际视网膜输入，正视时24/24仍可见。外围有些目标仅改变1个受体，正视后改变6～10个；所以不存在本组目标完全未入眼的情况，但信号稀疏与其内核响应强弱仍应区分。该核查不运行Core、不更改实验输入。`marker-visibility.json`留存逐项结果。

English:12student practices and24corrective demonstrations were actually executed. Final comparisons use12balanced held-out questions, common external initial state, and mixed old/new teacher validation on separate clones. An apparatus-only audit finds all24targets optically visible at the common initial pose and after alignment; some peripheral markers affect only one receptor. This rules out total optical absence at those poses, not inadequate neural salience. No Core or experimental input is modified by the audit.

## 同日：固定外设干预结果

正常/空命令/既有边静默/恢复，各12道相同留出题。静默使12题眼手终点全部改变；恢复后与正常组全部控制命令一致，无须重复哈希大文件即可从已记录数值核查。正常转眼题低速对准8.47%，静默5.00%；手部距离正常0.706米、静默0.685米，没有一致的正确性收益。空命令25%的对准时间全来自该目标阶段起点已对准，不能当作转向能力。原本未对准的阶段，正常2/11转入、静默4/11转入、空命令0/9转入。分母随先前行为变化，不能视为独立抽样的显著性比较。

回归检查：21项运动、旧眼输入兼容、鼻部光学、保存恢复、评分、回放与时钟分列测试通过。采样训练修复后数据仍使用原记录；未写入新Core规则。补充的过程分析只读取证据，不回写。

English: with the updated reader fixed, silencing changes every eye/hand endpoint in twelve held-out questions; restoration reproduces all original commands. Numerical recorded trajectories suffice; no redundant evidence hashing is needed. Correctness effects are mixed. Zero-command alignment arises from already-aligned starts, not acquired turning. Twenty-one relevant regression tests pass; process analysis only reads evidence and never changes Core.

## 同日：有界实验结束

鼻子组52课、12次验证示范和16题完成；相同原型转眼题低速对准时间由无鼻17.81%变为有鼻7.60%，本组没有增益。全部34阶段、206次创建/恢复、126.14计算分钟。有效闭环168题，原错误外设32题保留。所有记录进入21章/400段/39,840帧回放，Core/default/旧数据不改。

实际已存外设CPU/CUDA推理最大差约1.42e-7，账户用量到模拟结束约增加3个百分点；未发生资源门限停止。新补充的环境选择/能量反馈/教学三路线只入文档R37，没有加入本轮。史书四体65章和链接校验通过；浏览器视觉验收限制仍如上，不能把静态检查当作已观看。

English: the bounded nose comparison completes without benefit in this setting. Totals are 34 stages, 206 creations/restores and 126.14 compute minutes. Preserve all valid and tooling-failure trials in 21 replay chapters. CPU/CUDA predictions agree within 1.42e-7; account usage rises by about 3 percentage points through simulation completion. R37 remains a memo, not an added reward group. Historical editions and links pass validation; the browser visual-validation limitation remains explicit.
