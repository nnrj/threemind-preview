# 顺序材料与分析细节补充登记 / Additional prospective details

2026-09-30。校准完成后、尚未运行顺序、迁移或闭环实验，也未查看正式记忆结果时登记。

1. 顺序材料 AB／BA 中，每一帧物理输入都同时含一个固定、无顺序答案的参照 C（幅度 0.5，强度仍为已校准 0.3）。结尾仍是 C＋X 或 C＋Y；检验结尾只有 C。这样默认共同刺激生边规则有机会将物理历史与结果通道连起来，不用互不连通的子图去检验组合能力。C 是明确的合成实验标记，可理解为共同观察到的固定提示，并非内核中的“时间”或“逻辑”原语。AB、BA 及无对应关系的对照包含完全相同的 C 总量。
2. 迁移读出直接登记末次物理输入，不为了开启观察窗口添加 C 或其他额外刺激。训练标记 A／B 在迁移检验中缺席。
3. 主要评分基于判定时的完整激活排序。两个预先指定目标的差小于等于 1e-6 记为并列，均不超过 1e-8 记为未唤起；没有模式收敛时记为未收敛。分别报告覆盖率、可判读时的正确比例及全体测试中实际正确表达的比例，不能藏掉无输出。
4. 记忆的提示效果同时与同父本、同时段无提示副本配对。将采样时不存在的节点视为零（完整节点采样前提），不对缺测时间补零。提示相对无提示的目标激活增加大于 1e-5 才标记为可测唤起；正确目标比另一目标更高的原始排名，不能单独证明提示引起了该活动。
5. 顺序与迁移同时报告正反两例均正确的比例，避免总是输出一个结果也被称为已经会区分。时间轨迹的样本不当作独立实验个体。

Registered after calibration and before sequence/transfer/closed-loop execution or inspection of substantive memory results. A fixed anonymous context marker C accompanies every physical A/B frame, connecting opportunities through ordinary co-stimulus learning without giving the order answer. C dose is identical across order controls. Transfer registers the actual last physical input without an extra observation stimulus. Primary target ties use 1e-6, absent response 1e-8; non-convergence is separate. Memory cue/no-cue comparisons require >1e-5 sampled target change for measurable elicitation and never fill missing times with zero. Report both directional examples correct, coverage and conditional accuracy separately.
