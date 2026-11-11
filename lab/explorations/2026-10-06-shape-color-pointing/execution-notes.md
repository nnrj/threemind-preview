# E54 execution notes / 执行补充

## 2026-10-06，首次模拟前

用户补充追问动作动机：能量/耗竭形成方向偏好，还是教师和 Transformer 灌入移动模式。决定将机械接口校准与有目的选择分开：本轮教师示范只证明外设有无执行能力，不能证明动机。通过运动门槛后才考虑撤去示范的语言/能量目标；未通过则先做用户允许的内部辨别及属性表达，不用一次短失败否定演化路线。环境供能实验不是修改 Core 使之服从方向奖励。

User adds the motivation question. A supervised tracking controller is an apparatus calibration, not evidence of endogenous intention. Language/energy goal following requires a separate unprompted and causal test after reliable mechanics. Failure permits the explicitly authorised discrimination fallback.

颜色基础课使用薄色卡，不用四种待测三维形状之一，避免把留出的颜色-形状组合提前展示。组合训练中所有干扰物也排除四个留出组合。灰色形状、色卡均是公开教师材料；有名称的课程元数据不进入刺激。

Colour foundations use thin cards rather than a tested solid; all training distractors also exclude the four held-out combinations. This is fixed before simulation.

校准中的 2 秒是操纵器检验时窗，另有 150 ms共同观察；不是意识寿命或内核限制。肌肉控制器和命名外设只接收经 OutputBus 复制的原始节点字段。固定端口布局无语义分区；激活或抑制均为零的节点对这套外设产生零值，没有读出全部结构状态。

Two seconds is a motor evaluation window after150ms observation, not a lifetime limit. Both adapters receive raw fields via OutputBus; the layout is anonymous wiring, not semantic cortical assignments. This reader does not expose the stored structural graph.

## 运动校准完成、形色教学开始前

可见标记闭环28/32，零活动0/32，无关活动1/32，通过预定24/32。继续语言指向；训练标签可用教师力控制，测试时目标标记消失。目标名只由教师原句经过输入感官进入Core，不直接传给运动头。问答外设训练覆盖四个视角及每种配对的四个位置；测试使用另外两个视角。首次灰形/色卡教学不包含留出组合，组合训练干扰物也排除它们。

Visible-marker loop28/32, zero0/32, unrelated activity1/32: passed24/32. Proceed to language-directed pointing without a goal marker. Only the teacher utterance through Core carries the requested object; no target name/coordinate is passed to the motor head. Attribute training spans four views/positions per pair; two other views are held out.

## 用户补充2、首次颜色教学期间

新增独立模仿对照，不中断已通过的标记指向方案。教师肢体与自身肢体有不同的匿名感官接线；同时运动十次/方向，运动头只训练读取自身端口，不直接读取教师肢体端口。随后教师独自移动，比较正常、教师→自身连接静默、解除静默、教师不动。此工具先验证是否能由共同经历转入自身运动；即使成功，也不等同理解“我/他”或有模仿动机。反之短试失败也不否定演化训练。

An independent imitation assay preserves the successful marker route. Teacher and self have disjoint sensory wiring. They move together ten times per direction; the motor reader is restricted to self ports. Teacher-only movement tests normal/cross-edge mute/rescue/hidden-teacher conditions. This tests transfer through acquired connections, not semantic self/other understanding or subjective intention.

首次执行模仿前补充：上述“只读自身端口”是定位连接作用的限制性对照，不作为部署规则；并行训练另一运动头，允许读取教师与自身端口的所有实际活动。两者都只接收Core输出；全端口头可以直接利用教师感官引起的响应，不能因模仿成功就把作用全归于Core学到的连接。为自身端口对照另加同数量、近似边权的其他连接屏蔽。

Before imitation execution: own-port-only is a restrictive causal control, not a deployment rule. Also train an all-ports head on the same demonstrations; both receive only Core output. The latter can exploit direct teacher-sensory responses, so success alone does not establish learned Core mediation. Add equal-count, nearest-weight other-edge masking to the restricted reader.

组合课程的干扰物有相同形状或颜色，可能使外设利用场景统计作答。因此另加严格换指向检验：同一完整场景不变，仅换教师指向及属性问题，答案应随被指物变化；不能把上述普通问答准确率直接视为会使用指示关系。干预和未教组合均使用未参与拟合的证据。

Repeated-attribute distractors may allow a scene-statistics shortcut. Add a strict pointing-reference test: keep the full scene fixed, change only the teacher pointer and requested attribute, and require the answer to follow the pointed object. Ordinary QA accuracy alone is insufficient for deictic understanding.

## 首个问答结果后的修订

来源223：外设拟合96/96，新视角已教组合42/48；未教组合6/16（形状0/8、颜色6/8）。严格同场景换指向8/32，只有1/8场景×属性组的输出随指向变化。因而42/48不能证明会使用“这个”。保留全部原结果，按原登记允许的一次外设纠错：补灰色形状/色卡的校准，以及固定完整场景中轮流指认的均衡材料，共64条。仍使用原Core快照，不声称重教了Core。旧留出重测标为探索性复验，另用新场景检验指向；不将测试答案加入训练。

Source223: fit96/96, familiar-combination new views42/48, unseen combinations6/16(shape0/8,colour6/8), strict pointer-swap8/32 and only1/8scene/category groups changed output. Preserve this shortcut failure. The allowed one calibration correction adds64grey/card and balanced-reference examples, using the same Core snapshot. It is not Core re-education. Repeated held-out scores are exploratory retests; new scenes test reference separately. Test answers never enter training.

语言指向开始前，四对象改为均衡2×2形状/颜色组合，所有属性各出现两次。训练排除全部留出组合；测试可只包含一个未教组合。换指令对照会改问场上确实存在的另一个对象，分别记录原目标和新请求是否到达。此规则在任何语言指向训练/测试前固定，未改已登记问答证据。

Before any goal-directed motor training/testing: use balanced2x2shape/colour distractors, each attribute occurring twice. Training excludes held-out combinations; a held-out test includes only its one new pair. Changed-request controls name another physically present object and retain both original/requested target scores.

模仿首次尝试在第4帧（0.2模拟秒）因观测布局未显式允许排除教师端口而报错，未得到有效结果；原目录保留。修复的是研究工具的显式排除契约，未知通道仍报错，完整原始活动仍记录；另用imitation-retry执行。核心与刺激未变。

First imitation attempt failed at its fourth frame(0.2simulated seconds): the observer had not declared its intentional teacher-port exclusion. The partial directory remains. The repaired observer permits explicit exclusions only, still rejects unknown ports, and preserves raw evidence. The separately named retry uses unchanged Core and stimuli.

关闭Core可塑性组同样为42/48、6/16，严格指向6/32。这使旧课堂第二个完整有学习来源的盲目重复暂后置：先校准同场景换指向，并运行均衡语言指向。若修正材料形成可靠差异，再做第二来源；若前置不成立，停止扩大，不把未运行部分写成阴性。对关闭可塑性组也应用同一外设纠错材料，以免只修正一个组。

No-Core-plasticity also scores42/48 and6/16, strict reference6/32. Defer duplicating the flawed curriculum on a second learned source until corrected reference/goal tests warrant it. Unexecuted work is not a negative result. Apply identical external calibration correction to the no-plasticity control.

语言运动训练尚未开始（`s223-goal-teaching`尚不存在）时，检查出计划代码把训练视角与目标位置同时设为`rep%4`，可能给出视角捷径。执行前改为各自独立的带种子平衡排列，仍每对十次、120次示范；记录每次实际位置和视角。已完成属性数据不改，独立留出视角仍为5、6。

Before the first goal-training case existed, code inspection found that camera view and target position both used`rep%4`, a possible view shortcut. Randomise them with independent seeded balanced schedules before running; retain ten demonstrations per pair and120total. Record both actual view and position. Existing attribute evidence remains intact; held-out views stay5/6.

语言运动训练期间，追加离线感官校准：固定观察槽已知，用训练视角0～3的灰形距离模板识别视角5/6的不同颜色/位置形状。这是明确知道观察槽的工具校准，不接Core，不作为模型答案，不把其结果算作意识迁移；用途只限于检查低分辨率测量中是否包含可辨形状信息。无新的意识实例。

During motor teaching, add an offline sensor calibration with an explicitly known optical slot: depth templates from grey shapes at views0–3are tested at views5/6across colours and positions. This instrument oracle never connects to Core and is not a deployed answer generator or consciousness-transfer result. It only checks whether the measurement contains distinguishable geometry. No new Core instances.

120次语言运动示范完成后，正式检验到达2/32、最近选择正确10/32。此时不增加第二来源或盲目扩大教学；完成已登记的同场景换请求及既有连接静默对照，之后结项。无学习组相同外设补课已完成：新场景指向9/32，尚未形成学习组优势。静默仅针对分叉时已有边，不关闭测试中正常的新学习。

After120guided episodes,free language-directed testing reaches2/32targets and selects the correct nearest object10/32. Do not expand to another source or blindly add lessons; finish the registered changed-request and existing-edge-silence controls,then report. Identical external correction for the no-plasticity source gives9/32new reference trials,without a learned-source advantage. Masking addresses edges present at the fork and does not disable subsequent normal learning.
