# 用户追加授权后的当前系统校准

2026-10-08，北京时间。用户要求：“既然已经找到差别，就把它运用到当前实验中。如果有明显改善，就把这套流程写道docs作为ThreeMind假设同级别的实验流程规范（可在实验都完成后验证确实有效的时候再总结）。”本登记写于原定纠错完成之前，校准尚未开始。

## 已核实差别，不预先写成根因

E56从各自来源快照复制采集真实提问活动，均匀取覆盖整个提问的8帧，再离线校准读取器1200步；当前系统在正确陈述后的问答过程中逐次学习，读取最后16帧（0.8秒）。另外，E56是4位置选择并由伺服执行，当前B分支是8词回答；视觉、课程时长、读取结构和连续测试条件亦不同。不能只由代码差别断定哪一个造成低分。

## 当前分支采用的办法

完成原定纠错后先测实际回答；再由该完整个体的独立副本采集48项基础提问：8种已教基础例子，各6种小幅摆放（不含正式测试的位移）。问句不包含正确答案，不教正式未见形色组合。每项从同一个完整来源复制，保持其自己的外设和全部学习状态。副本教学/测量活动不反写来源Core。

采样保留16帧，但在2秒提问过程中均匀取真实活动，包含问题刚进入时的变化。数值不变、不减无提示活动、不按期望答案筛选节点。先在这些活动及教师标签上，对来源本人的表达器继续1200步集中校准；延续原权重、Adam、学习随机状态和历史缓存，使用最后状态，不更换新头或回滚最佳检查点。当前48项覆盖全部8个基础概念；训练集不含未教组合。

这是用户明确授权的**外设校准分支**，不是额外的意识教学，也不冒称一直共同演化。Core与身体在校准期间保持来源状态；原完整组合继续保留。新采样配置存入personal-vocabulary/2，旧/1仍按末窗读法恢复。新分支正式回答采用相同整段提问采样，未改原B分支评分；旧逐窗输出仍保留，回放区分两种记录。

使用已登记的位移后32题连续提问：题数、末时计分、目标标准不改，成绩与纠错前/后实际回答并列。未校准读头在同一采样下的结果可由保存数据只读计算，明确为读出器对照，不冒充新意识实验。若取得可用分数，再优先验证固定读头的连接静默和恢复；若仍失败，按用户请求进入E64空白四视场复现。样本/计算/磁盘及账户仍受E63上限约束；不足时说明未执行项。

若效果可靠，整理一份与假设文档同级的实验流程规范，说明数据边界、教师教学、个体外设、采样时序、校准/独立评估及恢复。规范不会把此处的实验方法升级为内核公理，也不会将本次未验证的建议列为已证实。

English: The user explicitly requested applying the recovered successful procedure to the current system. After corrective teaching and its test, collect48 answer-free basic question windows from independent complete copies of the same corrected individual. Sample16 raw frames across the whole2-second question, instead of the trailing0.8seconds. Continue the original personal peripheral's weights, Adam and RNG for1200 supervised calibration updates; preserve historical cache and take the last state. No Core evolution during this instrument fitting, no new head, hidden labels at inference, raw-value normalization or unseen-combination answers. Save the changed sampling as vocabulary/2; preserve old/1. Evaluate the same32 changed-position questions continuously, then attribute any useful result with fixed-reader interventions. This applies several declared procedure differences, so improvement alone cannot uniquely identify one cause. If still unsuccessful, prioritize the authorized blank E56 reproduction. A formal method document follows demonstrated effectiveness, not before.
