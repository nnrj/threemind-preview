# E59执行记录 / Execution notes

## 2026-10-07：登记与工程检查

共享额度起点80%；本机GTX1650，PyTorch2.14.0+cu130可用，RAM余量11.04GiB，C盘约10.7GiB/E盘约74.8GiB。未操作其他服务。研究项目9f3df121-3a48-4117-b2bf-bc6f9b867852已通过现有Lab服务建立，双语设计已入笔记。

新眼睛68受体：中央6×6，外围6×6去中央2×2。各受体固定四子射线平均，大外围单元覆盖更大角面积；中央半宽.075、全角平面半宽.38。眼角上限.35rad、速度.9rad/s、单位惯量加速度8rad/s²、阻尼4/s。314感官端口包括272视觉、既有32身体/天气/接触、10有符号眼部量。眼转动不新建端口。全图及旧眼保留。

首轮pytest的9个无临时目录测试通过，2个被受限执行器对pytest目录的权限阻断；项目内临时目录也受同类问题。申请正常本机权限后11项全部通过（6.72秒），不是修改测试绕过失败。检查覆盖固定身份、真实输入变化、完整状态继续、无元数据泄露、物理界限、读头输入不被训练改写、旧眼恢复。

English: registered before results; existing services untouched. CUDA available. The68-receptor eye retains fixed ports and measured motor feedback. Eleven meaningful tests passed after ordinary host permission resolved pytest temporary-directory access; optical and legacy behavior were not changed to accommodate the permission error.

## 正式辨识前：教学与外设训练细节

两种教学眼动分别为固定与按时间的连续扫描，扫描角轨迹(.22sin(2πt/2.6),.18sin(2πt/4.1+.7))，不查询物体或正确答案。教师实体指示用于教学，测试移除。104课及持续背景沿预登记执行。

每种眼动各72条外设训练问题、24条验证问题、24条测试问题；不同布局种子，无测试反馈。各问题记录1/2/3秒三个过程，主计分为3秒，另报告前两个时间点。过程16个等距原始采样，无减基线或幅度归一。固定相机/眼位几何只用于校准执行及外部评分。每个布局都问全部四个对象，题序预先随机。外设1200步、batch4，验证集损失选检查点；训练和验证使用同协议原始活动及直接入射两种来源。眼动/手部外设如继续使用，须分别记录监督与权重。

每问题的全部场景、原始活动和错例保留。闭环眼动必须另在真实动作后重新采样，不能把离线选择当作已经完成了主动观察。本阶段外设是有监督选择器，不能称已经忠实解读运动意图。

English: train/validation/test comprise72/24/24questions per gaze policy; separate scenes,all four requests per scene,randomized order,no test feedback. Samples at1/2/3seconds,3seconds primary. Reader sees16raw temporal samples,not baseline differences.1200steps,batch4,validation-only model selection. Closed-loop gaze requires fresh physical observations; offline choice is not an active-vision result.

## 外设拟合及闭环测试前：有限分辨率与录像

工程检查发现，6×6中央受体没有恰在光轴的中心点；若把所选像素的中心机械地当成精确点，会在已看向该像素时仍不断修正半个像素。闭环执行采用固定的受体范围校准：光轴位于该受体覆盖范围时维持采样时的轴向，其余按选中射线执行。不读取对象、题目或答案，不改变光学采样、教学过程或Core；不是按语义设注意门。首次闭环实验前登记，旧过程不重写。

回放修复了浏览器录屏只有容器头而无视频帧的问题，显式提交画布帧并检查真实解码。1440/390宽度检查包含播放、截图与WebM解码；窄屏改成场景、视网膜上下排列，避免文字过小。

English: before any reader fitting or closed-loop result, pixel-footprint motor calibration was registered. A 6×6 center has no exactly centered sample; selecting a footprint containing the optical axis holds its acquisition direction, avoiding endless half-pixel correction. Sensing, teaching and Core are unchanged; no object/answer is consulted. Replay recording now explicitly submits canvas frames and validates decoded video, with stacked narrow-screen panels.

## 基础读取未过门槛后的闭环小样本

原固定Core/入射留出为8/24、6/24，原扫描均5/24，未达到18/24扩展门槛。按初始登记允许的少量定位实验，闭环采用新的holdout顺序中每类最先出现的四题（颜色/形状/组合共12题），不按得分挑选。保留原先已学过1/2/3秒过程的16帧外设作为闭环基线；新完整过程读法另报，只学过3秒窗口，不能直接把其短前缀控制失败当作Core失败。

比较固定、预设扫描、独立学习眼动；学习眼动另作空动作、既有边静默/恢复、直接感官读取。每题独立恢复同一教学末态，仍有完整场景、自身可见、风/温度/湿度/重力与身体反馈。眼动和手部外设各自独立权重。结果用于定位当前控制链路与连接贡献，不把低分情况下任意改变动作称为有益自主判断。缺少可靠基础辨识时，本批不开展变形、多指或否定课程。

English: baseline scores fail the18/24 expansion gate. Use a bounded closed-loop diagnostic: the first four holdout questions per category in the predetermined order,12total, with no score-based selection. Keep the original reader trained at1/2/3seconds for this controller; the full-sequence comparison trained only3second windows and is reported separately. Compare fixed/prescribed/learned gaze plus empty commands, existing-edge silence/rescue and direct-input reading. Identical restored starting state, intact environment and independent eye/hand weights. Arbitrary changed movement is not counted as useful autonomous judgment. Deformation/plural/negation tasks remain gated by basic recognition.

## 2026-10-07：结项与教学措辞更正

全部39个登记阶段完成，98次实例创建/恢复，累计阶段耗时76.10分钟；没有预算中断的Core模拟。新眼边数大幅下降，形色与闭环识别未可靠。完整过程读取未改善新留出；现有连接静默/恢复确实改变/恢复终点，但没有正确性收益。详细数据见[报告](report.zh.md)及[完整结果](results.json)。

教师教学确实进行，两组各104课。`teaching_audit.py`按每课固定中点核查光学，并从原记录计算每个概念的实际复习间隔：第一次复习12～106.5秒，随后18、30秒。故原“先密后疏”只准确描述初始重复和后面整轮等待，不能描述每概念都严格扩展；这是本期课表缺陷，待修。没有错后Core补课，不能把这轮失败称为充分教学后的能力极限。教师部分遮挡约15.5%子射线，没有出现教师完全挡住原可见目标的中点。

只读汇总脚本首次读取中文JSON时受到Windows默认GBK解码影响，明确指定UTF-8后继续；已产生的眼动分析文件保留，未重跑Core。最终完整回放299段、12,840帧、78,377,880字节，1440/390检查、截图与164,702字节WebM实际解码通过。临时回放版本保留并标为工程检查，不当作额外实验样本。14项工具与旧装置回归通过。最终一次证据归档/正常上传后记录数据库增量，不反复通读旧数据。

English: all 39 registered stages completed, 98 creation/restoration branches and 76.10 cumulative stage minutes. No Core simulation stopped on a budget guard. The eye lowers graph cost; recognition is unreliable. Existing-edge silence/rescue changes/restores endpoints without a correctness benefit. The item-level audit corrects the broad review description: first review intervals range from 12 to 106.5 seconds, followed by 18 and 30. Error-specific Core correction remains undone. A Windows-default GBK read error in read-only analysis was corrected to explicit UTF-8 without rerunning Core. Full replay: 299 clips/12,840 frames, all conditions and errors retained; wide/narrow playback, screenshots and actual WebM decoding pass. Fourteen affected tests pass. Temporary viewer versions are engineering records, not additional experimental samples.
