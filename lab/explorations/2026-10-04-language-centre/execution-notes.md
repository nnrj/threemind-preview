# E42 execution notes / 执行补记

2026-10-04，第一组正式教学与提示测试之前：

- Qwen 输入编码首次调用被 Windows 沙箱的临时目录 ACL 拒绝，发生在模型启动前。原 request/failure 留存，另名 `encoded-material-approved-retry` 在批准的本地进程重试成功。未更换输入或映射。
- 校准先记录完整四窗。首个种子显示后两窗已无激活，故同时保存原16窗分母、8个有活动窗的翻译准确率及8个无活动窗的静默正确率。原 `selection-*.json` 中全窗75%字段保持原义；后续判据用有活动准确率75%，加上静默正确率，不把静默算作翻译错误。此澄清见双语计划追加条目。
- 空白组等长无输入等待42模拟秒，之后与教学组一样分别测试每个提示；绝不为了等长而注入维持刺激。
- `analyse.py` 在正式教学之前固定；主要窗口仍是提示后0.5–1秒。全轨迹最近词只作次要诊断，无输入轨迹中的激活上升、归零后再入用于区分单纯衰减。任何这种现象都不能直接代替关系问答正确率。
- 校准80步的首个接线种子，有活动8/8译对、无活动8/8静默，是首个即时结果；600步和其他种子尚待实际计算。不能外推为新配对或逻辑已通过。

English: before any formal teaching/probe tests, the initial sandbox ACL failure was retained and encoding retried under a separate key in an approved local process. Calibration retains its original all-window count while distinguishing translation on active windows from correct silence on inactive windows. Blank controls wait without input for the same42s. The fixed second500ms cue window is unchanged. `analyse.py` is frozen before formal testing; nearest-word similarity and no-input increases/re-entry are secondary diagnostics. The first80-step seed translated8/8 active held-out windows and remained silent on8/8 inactive windows; this does not yet establish learned pairings or logic.

## 首个种子完成后、第二种子开始前：有限停止规则

种子17普通/反转/空白/关闭学习的主要文字正确数为4/2/3/4（各8次提示），未通过经历反转条件。先完整完成第二个预登记种子29。如果前两个均不通过，则初始四种子至少三个通过的门槛已经不可能达到，本轮停止余下两种子的昂贵头训练，把时间用于原始证据定位和报告。未运行的43、71不记作阴性，不声称四种子复现了失败；既有门槛不降低，也不据此判定整条路线不可行。若29通过，则仍按原顺序继续43、71。这是根据已见17结果作出的资源停止决定，非四种子结论。

English: after seed17, before starting seed29, register a futility boundary. Primary correct counts for17 were4/2/3/4 of8 for ordinary/reversed/blank/frozen learning, failing reversal. Complete seed29. If both first seeds fail, the original at-least-three-of-four gate is unreachable, so stop expensive training for43 and71 and diagnose the recorded evidence. Unrun seeds are not negative results. Do not lower the gate or conclude that the entire route is impossible. If29 passes, continue43 and71 as planned. This resource decision is explicitly informed by17, not presented as a four-seed outcome.

## 传递损失定位后登记：强度／易化的有限诊断

种子17训练阶段，普通/反转组 `sent-discarded` 仅为0.07071/0.19741；`sent` 为49.91087/53.20213。源码表明这里 `discarded` 是局部释放后低于原逐边门槛的量，并非接收目标饱和。停止输入后通过门槛的传递量均为0；20ms采样未见激活上升或归零后再入。不得将这些衰减窗口称为已经证实的持续内部循环。

在完成第二种子的原对照之后，用种子17增加普通／强刺激（1/4）×易化恢复常数（0/1秒）的诊断。1、0条件复用已完成轨迹，其余三组各普通/反转教学，并保留八个独立提示和最多20秒无新输入观察，最多60个额外实例。仅使用现有参数，额外强刺激项保持默认开启，故强度4不被解释为纯粹放大。核心目标是传递量、内部活动及经历区别是否改变，主要提示窗保持0.5–1秒；所有提示强度仍为0.5。输出使用原冻结转换头，明确存在超出校准状态的风险；不凭其单项分数宣布新的可行性门槛通过，不用本诊断取代原组结果。本次不新增校准训练。若资源停止线先到，未做部分留待后续。

English: measured `sent-discarded` was only0.07071/0.19741 of49.91087/53.20213 emitted after local release in the ordinary/reversed17 courses. Source inspection identifies rejection below the existing per-edge floor, not target saturation. No accepted transmission followed the final lesson; no rising/re-entering node at20ms sampling. After the seed29 baseline, register a bounded intensity1/4 × facilitation time0/1s diagnostic, reusing1/0. The other three conditions have ordinary/reversed courses, eight cue forks each and up to20s without new input: at most60 new instances. All cues remain0.5; existing Core parameters only. The separate strong-intensity term remains enabled, so intensity4 is not called pure amplification. Reuse the frozen head and explicitly report out-of-calibration-state risk. This diagnostic does not replace baseline scores or independently pass the scratch-training gate; no new head training is added.

Provenance clarification: original case definitions' `intensity` means teaching intensity; probe intensity was fixed0.5 in the runner and design. New definitions additionally store `probe_intensity` explicitly. Old files remain intact.

## 第二种子峰值布局的数值错误

`s29-unsigned-peak-80` 在CUDA半精度输出模型的校准中抛出 `nonfinite mapping-head loss`。原请求和失败保存，不将其作为科学阴性。明确登记从相同种子、同一校准集、相同步数以CPU float32重新开始；不从损坏权重继续。CPU重试请求和成功/失败分别保存，设备精度差异在报告中单列。现有正式Core轨迹不重算。

English: `s29-unsigned-peak-80` failed with nonfinite loss using the FP16 CUDA decoder. Keep the original request/failure and retry from initial conditions using CPU float32 with the same seed, samples and steps. Record this numerical precision difference and separate retry artifacts; it is not a negative scientific result or a Core rerun.

CPU80步重试完成，有活动词准确5/8。600步同布局的CUDA运行再次在相同数值问题处失败。由于有符号平均600步已经达到留出8/8、按既定平分规则优先旧布局，峰值布局继续花约20分钟CPU训练不会改变本次选用的输出器，故暂不重试600步。保留其状态为“数值失败/未完成”，不填0分，不把它说成峰值方法本身无效。分析只增加失败状态的容纳，不改任何准确率、主要窗口或通过门槛；原分析源码仍保留。

English: CPU80 steps completed at5/8 active-window accuracy. The600-step FP16 attempt failed numerically again. Signed-average600 is already8/8 and wins ties by registration; another roughly20-minute CPU peak-layout run cannot change decoder selection. Defer that retry, retain an explicit failed/incomplete status (not zero accuracy), and do not infer that peak observation is intrinsically ineffective. Analysis only adds a numerical-failure entry; original analysis source, metrics, window and gate remain unchanged.


## 两个种子完成后的执行边界

17与29均未通过事前经历反转条件，故按已登记有限停止规则不运行43、71，不开展从零和家系训练。正常/空白/关闭学习为4/3/4和3/3/3（各8个提示），成对随反转教学都答对为1/8、2/8。后续只完成已登记的强度×易化定位，不追加训练轮数或改主要窗口。

诊断启动时，显式设置PYTHONPATH意外优先读到旧egg-info的包版本2.0.0，身份守卫在创建任何实例前停止。核查显示所有源码和内核身份均未变，仅包元数据不同。恢复原已安装环境的路径后继续；没有修改登记的实现签名，也未放宽守卫。

English: both17 and29 failed the preregistered experience-reversal condition. Apply the registered futility boundary: do not execute43/71, scratch training or family logic. Ordinary/blank/frozen are4/3/4 and3/3/3 of8; matched ordinary-and-reversed correctness is1/8 and2/8. Complete only the already registered intensity/facilitation diagnostic. Its first launch was stopped before case creation because an explicit PYTHONPATH preferred stale2.0.0 egg-info metadata. All source and kernel identities were unchanged. Restoring the original installed environment resolved this without modifying the frozen identity or guard.
