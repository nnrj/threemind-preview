# E56 execution record / 执行登记

- 2026-10-06，主模拟前：光学诊断显示旧4×4没有完全相同的形状输入，固定简单近邻新视角7/8，6×6和8×8为8/8。不能据此把意识的形状错误全部归于分辨率。Core比较采用4×4与6×6，8×8只做感官诊断，避免未经定位先扩大到千节点网络。
- 精化：每种灰色形状、颜色初教10次，逐项复习3次，共104课、180模拟秒；中间间隔6、18秒，加上交错8项目使同项复习间隔增加。每次1.5秒。课程内不提供正确/错误奖励给Core。
- 每个来源48次输出头校准（颜色/形状/组合各16）、正式24次（各8）、另12次练习（各4）。同场景所有四个请求均测，位置不能猜答案。正式视角5/6、练习视角4、初始校准0～3；校准包括组合，故组合检验为新布局/视角上的复合选择，不宣称全部是未见颜色形状配对。
- 纠错对每个错误练习项给5次示范（3轮密集+6/18秒间隔），包含重新指认、正确描述及身体运动；匹配分支用完全相同练习项、场景、身体初态、时长与背景，但不提供教师光点/答案描述/外力示范。**两个分支都使用新练习活动及相同的外部正确标签重训读头**，从而避免把仅有外设得到更多标签的收益归于意识受教。完整纠错仍包含多种教学，不把收益仅归于一个动作。
- 执行器明确改为“活动读头选空间端点，伺服执行所选端点”，目标评分坐标仅在结果端使用。测试2模拟秒，不供教师光点、不依据正确答案纠正当前动作。此前直接两轴力读头保留原记录；两种路线的变化不归于Core机制修改。先查清选物，再研究更直接运动技能。
- 光学守恒指固定视场全部采样的总增益；物体占据不同采样比例，实际入射量仍会随几何与密度不同。不同分辨率不是数学上完全相同的Core刺激，因此不能声称纯粹增加像素而其余动力学输入完全相同。

English: before Core runs, the legacy sampler has no identical shape signatures and achieves7/8 in a small sensor-only held-view diagnostic;6×6 and8×8 achieve8/8. Compare4×4 and6×6 in Core. Each source gets104lessons/180simulated seconds,48external-head calibration trials,24formal trials and12separate practice trials. Correct every erroneous practice item with five teacher demonstrations versus time/scene/background-matched exposure. Both branch heads receive identical practice labels and fitting steps, on their respective raw activities. Servo executes the decoded endpoint, never the scoring answer. Composite tests are unseen layouts/views, not an entirely untaught-combination test. Total optical gain is fixed but geometry-dependent sampled input can differ.

## 颜色首批结果后的外设候选（事后提出、训练前登记）

4×4组首8道颜色题只选对1道，执行器8道均抵达其选中的位置。因此增加一个**探索性外设对照**：让四个固定光学区域使用同一个读取函数，避免每个位置都要重新学一套颜色/形状译法。读取的是既有Core输出通道中的局部视觉活动与同一批非视觉活动，不向它输入对象身份、问题文本或正确位置；没有改Core或自然输入。相当于在适配器中沿用同一台眼睛的物理布局，不在意识里指定脑区。

先只用已有48个校准记录训练并重读已有正式活动，不能将这次后验选法称为独立确认。如果候选改善，再用事前排除旧布局的24个新题验收，并保留零活动及旧边静默对照。不覆盖正在运行的原读头、课程或错误清单。它是输出工具变化，其增益须与密采样、纠错分别列，不冒称意识独自学会或高分证明联想必需。

Post-hoc hypothesis registered before adapter training: a shared decoder across physical optical fields may reduce calibration-layout memorization. It reads raw Core activities only, shares the same field rule, and receives no query text, object identity or correct coordinate. Existing formal records are development data for this choice; a disjoint-layout confirmation set is required before a confirmation claim. Original branches/heads remain unchanged.

- 工程补记：4×4阶段进程约1.74GiB，运行时观察订阅使用绑定方法，可能延后回收已结束副本。后续新进程的研究包装器改成弱引用回调；只解决观察者持有对象的生命周期，不改变采样内容、推进、输入或Core。已启动的4×4进程仍使用加载时的原包装器，不能声称运行中热改内核。模拟背景不读取CPU/内存负载。本轮原始签名与后续源码版本均保留。

- 6×6尚未开始时的资源排序：4×4前置教学/校准/正式/练习已花21.1分钟，等时观察90模拟秒又花约6分钟；完整6×6两分支可能超过总150分钟。先完成4×4纠错及匹配对照，再确保6×6同课程的视觉比较；6×6补课按实测成本和余量决定，不能让硬限在中途打断而冒称全交叉已完成。共享区域读头先用已有记录拟合，只有出现增益才使用新确认题。未执行分支必须明确保留。

- 用户补充在E55录像中观察到画圈、猜测吸引教师注意。已另存[讨论与可行对照](../../../docs/zh/plans/vision-correction.md)，请求具体时间以核对教师/自主控制来源。此后续观测不打断当前视觉与纠错主实验；不把外部伺服轨迹当成主动表达。

- 用户已给录像时间2:27–2:35、12:28–12:38及附件，随后明确画圈核查在本轮指向实验之后进行。按此顺序执行；附件只定位，不增设额外模拟抢占主实验资源。

## 4×4完成后的后续选择（独立确认前登记）

原读头补课前/等时观察/纠错共5/24、6/24、8/24；纠错颜色1/8→6/8，形状仍2/8，组合2/8→0/8。三个共享区域读头分别重读为21/24、23/24、21/24，均只用了对应组既有校准/练习标签训练，正式记录未入拟合；但根据正式记录发现瓶颈及挑选候选，这些分数须记作后验开发成绩。

6×6已开始只执行同课程的初始教学/校准/正式题。其后预算优先给得分最高的4×4等时观察共享读头，在已登记24个新布局上闭环验收及旧连接静默；若有余量，再测纠错共享读头同题，不能只展示开发成绩最高者。共享读头的零活动、错配活动对照保留。无论准确率如何，外设自身也有监督学习能力，不能仅因其输入来自Core就认定答案必须由Core的可塑性学得。没有重训Core，没有修改Core输入/输出，也没有把正确坐标喂给执行器。

资源顺序与150分钟上限不变；6×6纠错两分支及第二独立来源仍待成本评估，不自动开展。

English: the shared-field candidates score21/24,23/24,21/24on previously recorded development trials. Select the exposure candidate before disjoint confirmation. After the6×6initial comparison, prioritize its24registered confirmation tasks and pre-existing-edge silencing; compare the corrected candidate on the same new tasks if resources permit. Supervised adapter skill remains a competing explanation, not evidence of Core learning by itself.

- 用户后续确认共享读取可能是关键原因，要求继续完成当前实验后重点验证新题成绩及选择是否来自记忆/联想。因此归因对照优先于扩大纠错范围：固定读头的零/错配活动、旧边静默与解除静默，以及不允许形成学习连接但经历相同课堂、获得同等外设校准的来源。最后一项不能用“空白意识配已经训练的别人的读头”的不公平失败代替。
- 用户明确：6×6若无明显增益，后续回到原4×4。不把提升采样密度作为强制默认升级；旧内核、世界和实例不改。

- 无结构学习对照在运行前登记：独立4×4来源，从创建时用现有`plasticity=false`，经历相同104课、相同174秒等时观察和原练习错误项顺序；自身原始活动另做48+12条、1200步的同构共享读头训练，再验同一24个确认题。不关闭激活、抑制、恢复或身体背景，不声称抹除了全部短时历史；另记录边数。旧边救援在同源副本上先静默、立即解除，再递送问题；如静默未影响结果，恢复不作为独立新发现。所有新增控制仍服从本批预算，优先于6×6补课和第二教学种子。

- 回放工程：一次预览导出因局部变量与输出路径同名而失败；排他写入保护阻止覆盖原始过程文件。已改名输出变量，保留该次派生JSON为`preview-before-output-path-fix.json`，修复后60个已完成试次预览的宽/窄屏、播放、定位、截图通过。此失败不涉及模拟或Core数据。

- 用户告知正在把与ThreeMind无关的文件移至移动硬盘，因此E盘可用空间可能增加。本实验仍执行15GiB余量检查，不据空间增加推断实验清理过数据，不操作其搬移任务。
- 回放/导出区分本期全部指向试次与完整教学证据：影片保留各组所有正确和错误，显示控制来源、问题、最终评分和实测感官/活动；全课次仍存于原始过程。输出只复用记录，不重新推理或运行Core。新增通用逐帧合成接口，既有E55完整教学影片不替换。

- 6×6校准完成后，实测该48项已耗19.96分钟；正式题还各有2模拟秒动作。为保留关键归因，后续顺序细化为：4×4共享读头新题确认、独立关闭结构学习且等量外设训练、旧边静默；恢复控制按剩余预算和静默影响执行。此排序在新题结果产生前登记。6×6纠错、纠错共享头的第二套确认不优先占用归因预算，未执行者明确列出。

## 用户降低分辨率对照优先级（2026-10-06）

> 本次实验的资源和时长可以放宽。此外既然共享读取规则明显增益，分辨率的实验可降权，不必再进行与低分辨率的反复对照和验证，因为根因明显定位到了，不是分辨率问题。

据此在6×6正式检验尚未完成时，以既有STOP检查正常退出，保存已完成的教学、48项校准、拟合及已写出的试次。停止由研究优先级决定，不是根据6×6最终成绩择取结果；不将其标为失败或完整的分辨率比较。随后恢复4×4共享读取的新题与因果控制。暂不提高现有硬预算；若必须扩展，另行明示登记。已中止的计算时间仍计入本批消耗。

## 共同读取器下比较经历（运行前追加）

正常及关闭结构学习的来源各自校准后同为24/24；固定正常读头，旧边静默为19/24，恢复尚在执行。为进一步区分“意识经历改变”与“给每个来源重训外设”，追加一组：用已经固定的等时观察读取器解读纠错来源，测试同一24题，不再训练外设。两来源都从354模拟秒进入**同一个等时观察世界状态**，再按同一任务重置场景/位置，避免教师移动造成的躯体温度等物理差别冒充过去经历的作用。仅统一当前测试世界，不修改两者的Core历史或动力学。完整记录此世界迁置，不把它说成自然连续教学。原先各用自身读头的开发分数不改写。这组仍在现有150分钟预算内，因果归因优先于再跑分辨率。

## 真正停用Core的课间轨迹对照（物理重算前登记，2026-10-06）

用户指出：

> 你得测一下，屏蔽掉意识的时候，课间的那段活动轨迹是否还会出现。”轨迹逐点相同“不足以证明意识没有作用，意识本身也是动力学，重复的环境刺激产生重复的轨迹是正常的。

接受这一纠正：此前关闭结构学习仍有Core，并非停用意识的对照。主实验和录像完成后，使用同一初始身体状态、风场种子、50毫秒物理步长和完整原教学场景时序，运行不创建Core的物理世界。位置、速度、温度都从初态演算；不把记录中的轨迹或活动写回控制，不删环境对象。独立物理轨迹生成并保存后，才读取原录像采样作比较。比较全课程及用户指出的两段；无需重复运行大型意识。上限120秒墙钟、11000物理步、16MiB新增轨迹，沿用内存及磁盘余量。此结果只回答这两段已有画圈的动作来源，不改意识自主活动的一般判定。

English: learning disabled is not Core disabled. After the main experiment and video, rerun only the physical world from its original initial state with the same weather, objects, teacher scene schedule and 50ms step; create no Core. Recorded motion/activity is never fed to control. Freeze the newly computed trajectory before loading reference frames. Compare the full course and both user-specified windows. Bound:120wall seconds,11000physical steps,16MiB trajectory plus existing memory/disk reserves. This tests the provenance of these specific circles, not autonomy in general.

## 主实验完成后的补测与媒体结果

2026-10-06：停用Core的独立物理重算已执行，516模拟秒、10320步，两个用户窗口及全课程位置差0米，10项物理量差0；场景和标记时序无差异。用时5.20秒，轨迹1,229,086字节。没有创建Core，没有输入旧轨迹。结果见circle-core-disabled.json；这不是又一次大型意识模拟。

新影片为852秒、213个已完成指向试次，1600×900、20fps、H.264、无声、18,869,367字节；导出391.23秒。原始教学过程完整保存，影片仅展示各组指向检验及练习，包含对错与对照。1440/390宽度播放、拖动、截图通过；检查实际MP4并观看第420秒解码帧。原E55完整教学影片不覆盖。

English: the Core-absent physical rerun reproduces all10,320positions over516simulated seconds, both user windows and all ten physical measurements, with no scene/marker mismatch. It takes5.20seconds and1,229,086trajectory bytes; no Core or recorded-motion control is used. The new852-second/213-trial movie preserves all completed pointing outcomes, not the entire teaching course, whose raw evidence remains. Responsive viewing and actual MP4 decoding have been verified.
