# E59追加登记：完整过程读取 / Full-sequence control

2026-10-07，已知原扫描B阶段结果、尚未拟合本追加模型。

原16帧读取中，扫描Core和直接入射的3秒测试均5/24，验证分别7/24、5/24。原始采样全部保留，但等距选16帧有可能丢掉短问句的若干字符输入帧。此问题在输出工具，不是Core没有经历这些刺激；也未确认它是失败唯一原因。

追加只读重分析，不重新教学Core或修改任何输入/活动：每题3秒的60个真实采样完整交给新版有界过程读取器；另以同一新读取器抽16帧、相同72训练/24验证问题，控制数据量和参数数目。均1200步、batch4、相同种子，按验证损失选检查点。CPU/CUDA均可；分批验证避免一次性大显存分配。

原测试已见，因此改进后的原测试成绩仅作为重复诊断，不充作全新盲测。另用此前未用的布局种子偏移21000生成24道holdout。完成选型之前不读取它的成绩。若后续需要选择用于闭环的采样方式，按验证最近对象正确数，平局按验证损失，不能按新holdout选择。额外眼动读头独立种子501，其余相同。新读法是否有用，必须报告与同量16帧对照的实际差别。

还需报告：固定眼的辨识；目标落入中央/外围/视野外的时间比例；像素方向能否实际到达对象。变形与否定多指继续以可靠基础辨识为前提，不因为额外工具而自动扩展Core实验。

English: after the initial scanning readers scored5/24, add a readout-only comparison of all60actual samples versus16equally spaced samples. Both new readers use the same72training/24validation questions, architecture,seed and1200steps; no Core/input is changed. Old test scores are reused diagnostics. A previously unused layout offset21000 supplies24fresh holdout questions. Choose a later closed-loop method only by validation correctness, then validation loss on ties. This tests temporal information loss without assuming it is the sole failure cause. Original results are retained.

核查例子：“请指出红色的物体。”与“请指出蓝色的物体。”在既有文本协议的第3、4帧（从0计）不同；16帧读法遗漏3、保留4。因此它丢了一部分过程，但不能说所有颜色差异都丢了：协议原有的相邻字节组合保留了部分差异。不得为解释失败而夸大这一诊断。

The existing anonymous text mapping differs at frames3and4 for red-versus-blue requests. The sparse reader misses3but keeps4, so some distinguishing information survives through the unchanged byte-transition encoding. Temporal omission is a candidate, not a claim that the entire query was lost.
