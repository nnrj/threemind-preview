const kernels: Record<string, string> = {
  "同刻整合是研究选项：内外信号混合时会共用一次接收与来源标志，可能改变新颖量及直接学习冲量；不等价于 /2。/5 默认分别接收。":
    "Coincident integration is a research option: mixed external/internal signals share a reception and source flag, potentially changing novelty attribution and the direct-learning impulse. It is not equivalent to /2. /5 defaults to separate reception.",
  "使用依赖保持 · 修复零响应节点的局部回收排期":
    "Use-dependent retention · fixed local expiry for zero-response nodes",
  局部回收修正版: "Local reclamation correction",
  "沿用 /3 的学习与保持公式；零响应节点也登记局部回收期限。已有 /3 意识保持原版本。":
    "Retains /3 learning and retention formulas, while scheduling local expiry for zero-response nodes. Existing /3 individuals keep their original version.",
  "局部事件内核 · 统一接收与局部能量":
    "Local event kernel · unified reception and local energy",
  局部事件执行版本: "Local event execution kernel",
  "局部事件修订 · 默认采用 /2 接收与学习规则": "Local event revision · /2 reception and learning by default",
  局部事件与学习规则修订: "Local execution and learning revision",
  "局部执行性能修订 · 保持 /5 动力学与配置默认值":
    "Local execution performance revision · preserves /5 dynamics and configuration defaults",
  局部执行性能修订: "Local execution performance revision",
  "保持 /5 的动力学、参数默认值和研究选项，减少对象复制和内部消息开销。已有意识继续使用其原版本，不自动升级。":
    "Preserves /5 dynamics, parameter defaults and research options while reducing object copies and internal message overhead. Existing individuals keep their original version without automatic upgrades.",
  "同刻整合是研究选项：内外信号混合时会共用一次接收与来源标志，可能改变新颖量及直接学习冲量；不等价于 /2。/5、/5.1 默认分别接收。":
    "Coincident integration is a research option: mixed external/internal signals share a reception and source flag, potentially changing novelty attribution and the direct-learning impulse. It is not equivalent to /2. /5 and /5.1 default to separate reception.",
  "统一接收（/4 默认；/5、/5.1 研究选项）": "Unified reception (/4 default; /5 and /5.1 research option)",
  "按 /2 来源规则（/5、/5.1 默认）": "/2 source rules (/5 and /5.1 default)",
  "同刻整合（/4 默认；/5、/5.1 研究选项）": "Coincident integration (/4 default; /5 and /5.1 research option)",
  "分别接收外部输入（/5、/5.1 默认）": "Separate external packets (/5 and /5.1 default)",
  "默认采用 /2 的接收与学习规则，保留局部执行、半衰期和回收；统一接收、同刻整合与异步传播是注明差异的研究选项。旧版不自动升级。":
    "Uses /2 reception and learning by default, retaining local execution, half-life and reclamation. Unified reception, coincident integration and asynchronous propagation are explicit research options. Historical kernels are not upgraded.",
  "统一接收（/4 默认；/5 研究选项）": "Unified reception (/4 default; /5 research option)",
  "按 /2 来源规则（/5 默认）": "/2 source rules (/5 default)",
  "同刻整合（/4 默认；/5 研究选项）": "Coincident integration (/4 default; /5 research option)",
  "分别接收外部输入（/5 默认）": "Separate external packets (/5 default)",
  "节点独立相位（研究选项）": "Node-specific phase (research option)",
  "节点与连接自行结算衰减、安排传播和失效。默认统一接收；可对照独立相位、逐条到达及局部资源场。旧内核继续可用。":
    "Nodes and edges settle their own decay and schedule emissions and expiry. Unified reception is the default; independent phases, sequential reception and energy models are explicit controls. Older kernels remain available.",
  局部事件与资源场: "Local events and resource field",
  传播执行方式: "Emission execution",
  传播相位: "Emission phase",
  到达整合方式: "Arrival integration",
  接收规则: "Reception rule",
  能量模型: "Energy model",
  能量投放随机方式: "Supply randomness",
  能量随机种子: "Energy seed",
  固定局部区域数: "Fixed local regions",
  单节点能量容量: "Per-node energy capacity",
  "局部事件（默认）": "Local events (default)",
  扫描对照: "Scan control",
  对齐模拟时刻: "Aligned simulation phase",
  节点独立相位: "Independent node phase",
  接收端同刻整合: "Coincident receiver integration",
  逐条接收对照: "Sequential reception control",
  "统一接收（默认）": "Unified reception (default)",
  按来源区分对照: "Source-dependent control",
  "局部资源场（默认）": "Local resource field (default)",
  共享能量账本对照: "Shared energy ledger control",
  "计数随机（可重放）": "Counter random (replayable)",
  "独立随机流（可重放）": "Independent random stream (replayable)",
  "模型选择在出生时固定；能量模型不自动开启能量开关。局部区域只在出生时分配，与显示布局无关。":
    "Model choices are fixed at birth. Selecting an energy model does not enable energy constraints. Local regions are assigned at birth and do not depend on display layout.",
  "使用依赖保持 · 可选休眠与唤醒":
    "Use-dependent retention · optional dormancy and awakening",
  活动调节保持版本: "Activity-dependent retention kernel",
  "实际活动延长连接和节点支持度的半衰期，闲置后逐渐回落；休眠与唤醒默认关闭。":
    "Actual activity extends edge and node-support half-lives, which gradually fall during disuse. Dormancy and awakening are off by default.",
  "保持、回收与可选唤醒": "Retention, reclamation and optional awakening",
  连接保持公式: "Edge retention formula",
  "出生时选择半衰期学习或旧稳定度公式；旧内核身份始终可选。":
    "Choose half-life learning or the legacy stability formula at birth. Historical kernel identities remain available.",
  节点回收模式: "Node reclamation mode",
  "自动复用支持度和使用历史半衰期；手动模式才使用支持度阈值或固定等待。":
    "Automatic mode uses support and its activity-dependent half-life. Only manual mode uses a support threshold or fixed wait.",
  不自动删除节点: "Retain nodes without automatic deletion",
  "开启后禁止自动回收；不阻止显式研究删点。":
    "Disables automatic reclamation, while explicit research deletion remains available.",
  死节点保持时间: "Isolated-node retention time",
  "仅手动模式且支持度阈值为0时生效；从最后一条有效边消失开始，实际触达重置。":
    "Active only in manual mode with a zero support threshold. Starts when the last live edge disappears; actual touch resets it.",
  节点回收支持度阈值: "Node reclamation support threshold",
  "与节点活动及连接状态共同决定回收；新版仅手动模式生效，0切换至死节点保持时间。":
    "Combines with activity and connectivity to determine reclamation. Manual mode only in the new kernel; zero selects isolated-node retention time.",
  保留休眠痕迹: "Retain dormant traces",
  "实验选项，默认关闭；关闭会清除工作副本痕迹并联动关闭唤醒。":
    "Experimental, off by default. Disabling clears traces in the working copy and disables awakening.",
  局部唤醒: "Local awakening",
  "默认关闭；真实局部信号达到独立节点/连接阈值时唤醒残余接触。":
    "Off by default. Actual local signals must reach separate node and edge thresholds to awaken residual contacts.",
  节点唤醒阈值: "Node awakening threshold",
  连接唤醒阈值: "Edge awakening threshold",
  有效信号: "Effective signal",
  "启用唤醒时必须显式配置正值；同刻实际到达量可叠加。":
    "Set an explicit positive value before enabling awakening. Actual arrivals at the same time can add up.",
  "启用唤醒时必须显式配置正值；两端同刻信号可叠加，不另赋权。":
    "Set an explicit positive value before enabling awakening. Signals from both ends at the same time can add up; no weight is granted.",
  半衰期增长公式: "Half-life growth formula",
  "出生时固定：对数饱和或起点增益相同的线性饱和对照。":
    "Fixed at birth: log-saturating growth or a linear-saturating control with matching initial gain.",
  "对数饱和（默认）": "Log-saturating (default)",
  线性饱和对照: "Linear-saturating control",
  最短记忆半衰期: "Minimum memory half-life",
  "未充分使用的连接及自动模式节点支持度的半衰期下限。":
    "Half-life floor for little-used edges and node support in automatic mode.",
  最长记忆半衰期: "Maximum memory half-life",
  "反复有效活动可逐渐接近此上限，仍会遗忘。":
    "Repeated effective activity can approach this ceiling; forgetting remains active.",
  半衰期回落速度: "Half-life decrease rate",
  "闲置时每模拟秒减少多少半衰期秒数；0只关闭回落，不关闭权重衰减。":
    "Half-life seconds lost per simulated second of disuse. Zero disables this decrease, but weight still decays.",
  保持时间学习率: "Retention-time learning rate",
  "按实际局部活动剂量延长半衰期，不按输入事件计数奖励。":
    "Extends half-life through actual local activity dose rather than event counts.",
  保留余量学习率: "Node support learning rate",
  "仅控制自动模式节点支持度；连接使用原有正常权重强化。":
    "Controls automatic node support only. Edges keep their ordinary positive weight learning.",
  强刺激疲劳: "Strong-input fatigue",
  "强刺激的实际接受量带来额外消耗与可恢复疲劳。":
    "Actually accepted strong input causes extra consumption and recoverable fatigue.",
  强刺激疲劳恢复时间: "Strong-input fatigue recovery time",
  "疲劳指数恢复的时间常数；疲劳越深，恢复到同一水平越久。":
    "Exponential recovery time constant. Deeper fatigue takes longer to reach the same level.",
  强刺激疲劳增益: "Strong-input fatigue gain",
  "每单位实际接受的超常刺激产生的疲劳量。":
    "Fatigue per unit of actually accepted excess input.",
  休眠痕迹清除下限: "Dormant trace removal floor",
  "休眠残余权重低于此值后彻底清除；须低于活跃边修剪阈值。":
    "Residual dormant weight below this floor is removed. Must be below the live-edge pruning threshold when enabled.",
  活动调节半衰期: "Activity-dependent half-life",
  旧稳定度公式: "Legacy stability formula",
  自动支持度保持: "Automatic support retention",
  手动回收实验: "Manual reclamation experiment",
  "休眠已关闭，唤醒已联动关闭。":
    "Dormancy is off, so awakening has also been disabled.",
  当前模式下不生效: "Inactive in the current mode",
  "激活·s": "activation·s",
  "记忆机制研究 · 耗竭、易化与巩固":
    "Memory research · depletion, facilitation and consolidation",
  记忆机制研究候选: "Memory-mechanism research candidate",
  "分别控制耗竭、易化和既有连接巩固；关闭巩固仍保留遗忘与抑制。":
    "Control depletion, facilitation and existing-edge consolidation independently; disabling consolidation preserves forgetting and inhibition.",
  释放资源耗竭: "Release-resource depletion",
  既有连接正向巩固: "Positive consolidation of existing edges",
  "关闭采用无限补给对照，保持利用率和易化；不会把初始释放系数改为 1。短时突触总开关需开启。":
    "Off uses an unlimited-supply control, preserving utilization and facilitation instead of setting initial release to 1. Requires the short-term synapse master switch.",
  "关闭仅阻断既有边权重、稳定度的增加；保留生边、遗忘、资格迹、节点更新和快痕迹。":
    "Off blocks only positive weight/stability updates of existing edges; preserves birth, forgetting, eligibility, node updates and fast traces.",
  "本地小模型，只输出下一事件概率；可选 GPU，不可用时回退 CPU。数字是对照类别编号，不是意识节点 ID。不会自动回灌或调用云端。":
    "A local model returning next-event probabilities. Optional GPU with CPU fallback. Categories are not consciousness node IDs. No automatic feedback or cloud calls.",
  计算设备: "Compute device",
  本次训练与查询使用: "Device for training and queries",
  "自动（测量收益后选择）": "Auto (measure before selecting)",
  "GPU 优先（失败回退 CPU）": "Prefer GPU (CPU fallback)",
  "显存预算（MiB）": "VRAM budget (MiB)",
  "意识内核仍使用 CPU。自动模式须测得稳定加速；真实执行设备和回退原因保存在任务证据中。":
    "The consciousness kernels use CPU. Auto requires measured, stable speedup; actual device and fallback reasons are recorded with task evidence.",
  执行设备: "Actual device",
  已从初始条件在CPU重试: "Restarted from initial conditions on CPU",
  "已从初始条件在 CPU 重试": "Restarted from initial conditions on CPU",
  意识内核: "Consciousness kernel",
  "科学模型与版本；创建后固定，后端选择不会改变动力学。":
    "Scientific model and version, fixed after creation. Backend selection does not change dynamics.",
  "V3 恢复基线 · causal/9": "Restored V3 baseline · causal/9",
  "连续候选 · 短时突触与局部上下文":
    "Continuous candidate · short-term synapses and local context",
  "脉冲候选 · 膜电位与局部时序学习":
    "Spiking candidate · membrane voltage and local timing plasticity",
  "连续候选：短时突触与局部上下文":
    "Continuous candidate: short-term synapses and local context",
  "脉冲候选：膜电位、发放与时序学习":
    "Spiking candidate: voltage, firing and timing plasticity",
  短时突触资源: "Short-term synaptic resources",
  "释放利用率 U": "Release utilization U",
  突触资源恢复时间: "Synaptic resource recovery time",
  突触活动资源时间: "Active-resource time constant",
  易化恢复时间: "Facilitation recovery time",
  连接快变化迹: "Fast synaptic trace",
  快迹衰减时间: "Fast-trace decay time",
  快迹积累率: "Fast-trace accumulation rate",
  快迹传输增益: "Fast-trace transmission gain",
  接收端局部上下文: "Receiver-local context",
  触达时间特征尺度: "Touch-recency feature timescale",
  局部竞争温度: "Local competition temperature",
  局部分配混合量: "Local allocation mix",
  发放后适应电流: "Post-spike adaptation current",
  阈值检查步长: "Threshold-check interval",
  突触递送延迟: "Synaptic delivery delay",
  绝对不应期: "Absolute refractory period",
  静息死亡宽限期: "Quiescence death grace period",
  膜电位被动泄漏: "Passive membrane leak",
  突触电流衰减: "Synaptic current decay",
  静息电位: "Resting voltage",
  发放复位电位: "Post-spike reset voltage",
  发放阈值: "Spike threshold",
  膜电阻: "Membrane resistance",
  膜时间常数: "Membrane time constant",
  突触电流时间常数: "Synaptic current time constant",
  适应电流时间常数: "Adaptation time constant",
  每次发放的适应增量: "Adaptation increment per spike",
  输入电流增益: "Input current gain",
  突触传输电流增益: "Synaptic transmission gain",
  电位静息容差: "Quiescent voltage tolerance",
  电流静息容差: "Quiescent current tolerance",
  同帧生边系数: "Co-input growth coefficient",
  局部时序可塑性: "Local timing plasticity",
  突触前到达迹常数: "Presynaptic arrival-trace constant",
  突触后发放迹常数: "Postsynaptic spike-trace constant",
  正时序增量: "Causal-order increment",
  反时序减量: "Reverse-order decrement",
  资源恢复常数: "Resource recovery constant",
  释放资源活动常数: "Released-resource time constant",
  易化时间常数: "Facilitation time constant",
  受体容量: "Receptor capacity",
  "启用逐连接释放、耗竭与恢复；关闭后发送幅度不乘释放比例。":
    "Enable per-edge release, depletion and recovery. When disabled, emission is not scaled by the release fraction.",
  "每次合格发射尝试释放的可用资源比例；0 停止释放，不等于关闭算子。":
    "Available-resource fraction used per eligible emission. Zero stops release; it does not disable the operator.",
  "失活资源回到可用池的时间常数。":
    "Time constant for inactive resources returning to the available pool.",
  "已释放资源进入失活池的时间常数。":
    "Time constant for released resources entering the inactive pool.",
  "0 关闭易化；正值为利用率额外增益的衰减时间常数。":
    "Zero disables facilitation; positive values set the decay constant of additional utilization.",
  "实际传播在慢权重之外形成可衰减的局部快迹；不改写慢权重公式。":
    "Actual propagation accumulates a decaying local fast trace, separate from the slow-weight formula.",
  "快迹按经过的模拟时间衰减。":
    "Fast traces decay with elapsed simulation time.",
  "0 停止新增快迹；关闭持续可塑性也停止积累。":
    "Zero stops new trace accumulation; disabling plasticity also stops it.",
  "0 关闭快迹对传输的影响，仍可记录其积累。":
    "Zero removes the trace's transmission effect while accumulation can still be recorded.",
  "只对实际到达同一节点的本批消息分配响应，不筛选被动读出的原始激活。":
    "Allocate responses only among this batch's arrivals at the same node. Do not filter raw passive readouts.",
  "局部特征中距上次触达时间的指数尺度，不改变感官编码。":
    "Exponential recency scale for local features; sensory encoding is unchanged.",
  "正值，越小越强调局部状态相似度；不代表语义重要性。":
    "Positive; lower values emphasize local state similarity, not semantic importance.",
  "0 保留原始幅度总和；1 使用完全局部分配。原始到达量始终保留。":
    "Zero retains the raw amplitude sum; one uses full local allocation. Raw arrivals are always retained.",
  "关闭后停止同帧生边和 STDP，既有电流与发放继续。":
    "Disabling stops co-input growth and STDP. Existing currents and firing continue.",
  "发放产生局部反向电流，减弱后续去极化；不是原核的拓扑抑制。":
    "Spikes add a local opposing current that reduces later depolarization. This differs from baseline topology-based inhibition.",
  "固定格点检查阈值；两点间使用 RC 解析演化。更小步长用于数值收敛对照。":
    "Thresholds are checked on a fixed lattice with analytic RC evolution between checks. Smaller steps support convergence checks.",
  "发放至到达的延迟；更改不影响已经在途的信号。":
    "Delay from emission to arrival. Changes do not affect already-sent signals.",
  "发放后膜电位暂钳于复位值，电流仍接收和衰减；0 关闭。":
    "Clamp voltage at reset after a spike while currents still arrive and decay. Zero disables the interval.",
  "首次物理活动后，电位偏移及两类电流均消退才开始计时；0 立即判定。":
    "After first physical activity, start timing only when voltage displacement and both currents subside. Zero removes the grace period.",
  "保存可复现身份；当前脉冲方程没有随机造边。":
    "Retain reproducible identity; current spiking equations do not create random edges.",
  "关闭仅用于消融，不会关闭突触电流自身衰减。":
    "Disable for ablation only; synaptic current decay remains separate.",
  "关闭时已注入电流保持；属于显式非默认对照。":
    "When disabled, injected current persists; this is an explicit nondefault control.",
  "电位基准。创建后只读。": "Voltage reference. Read-only after creation.",
  "必须不低于静息值且低于阈值。创建后只读。":
    "Must be at least rest and below threshold. Read-only after creation.",
  "跨过阈值在下一个检查格点发放。创建后只读。":
    "Crossing causes a spike at the next threshold check. Read-only after creation.",
  "电流与电位变化的耦合量；与其他参数一起决定响应。":
    "Couples current to voltage changes; determines response with the other parameters.",
  "必须为正；关闭泄漏请使用独立开关。":
    "Must be positive; use the separate switch to disable leak.",
  "必须为正；关闭衰减请使用独立开关。":
    "Must be positive; use the separate switch to disable decay.",
  "发放后的反向电流按此尺度消退。":
    "Post-spike opposing current decays on this timescale.",
  "0 停止增加适应电流；已有适应电流仍衰减。":
    "Zero stops new adaptation increments; existing adaptation still decays.",
  "通道幅度 × 刺激强度 × 此增益；0 关闭直接输入注流。":
    "Channel amplitude × stimulus intensity × this gain. Zero disables direct current injection.",
  "发放按连接权重和短时资源决定电流，不读取目标电位。0 关闭新传输。":
    "Emission uses weight and short-term resources, never target voltage. Zero disables new transmission.",
  "与电流容差共同判断消退；0 撤去此数值截断，可能极长时间不静息。":
    "Used with current tolerance to detect quiescence. Zero removes this numerical cutoff and may greatly prolong activity.",
  "电流、适应电流与电位均消退后才清零。0 撤去电流截断。":
    "Snap to rest only when both currents and voltage subside. Zero removes the current cutoff.",
  "仅实际输入共同触达节点间生边，权重乘两者输入幅度。0 禁止新边。":
    "Grow edges only between receptors contacted by the same input, scaling weight by both amplitudes. Zero disables growth.",
  "使用该连接的到达迹和目标发放迹；无语义奖励。":
    "Uses this edge's arrival trace and the target's spike trace, without semantic rewards.",
  "先到达再发放的影响随此尺度衰减。":
    "Arrival-before-spike influence decays on this timescale.",
  "先发放再到达的影响随此尺度衰减。":
    "Spike-before-arrival influence decays on this timescale.",
  "目标发放时权重增加 A+ × 本连接到达迹；0 关闭增加。":
    "Target firing adds A+ × this edge's arrival trace. Zero disables increases.",
  "输入到达时权重减少 A− × 目标发放迹；0 关闭减少。":
    "Arrival subtracts A− × the target's spike trace. Zero disables decreases.",
  "发放使用逐连接资源的释放与恢复。关闭保留完整发射幅度。":
    "Firing uses per-edge resource release and recovery. Disabling retains full emission amplitude.",
  "0 停止释放；不等于关闭短时算子。":
    "Zero stops release; it does not disable the short-term operator.",
  "失活资源重新进入可用池的尺度。":
    "Timescale for inactive resources returning to the available pool.",
  "资源进入失活池的尺度。":
    "Timescale for resources entering the inactive pool.",
  "0 关闭易化。": "Zero disables facilitation.",
  "达到容量时拒绝新受体并记账；0 禁止新受体，不删除已有受体。":
    "At capacity, reject and count new receptors. Zero forbids growth without deleting existing receptors.",
  "达到容量时拒绝新边并记账；0 禁止新边，不删除已有边。":
    "At capacity, reject and count new edges. Zero forbids growth without deleting existing edges.",
  "外部概率刺激已接收，来源、模型和通道映射已记录。":
    "External probability input accepted. Its source, model and channel mapping are recorded.",
  "可选：作为外部刺激接入": "Optional: connect as external input",
  "这会真实改变所选意识。类别按声明的连续通道逐项映射，不能当作内核自行学到的能力；原文本映射不变。":
    "This changes the selected consciousness. Categories map to the declared consecutive channels. This is external assistance, not a capability learned by Core alone; text encoding stays unchanged.",
  接收意识: "Receiving consciousness",
  起始通道编号: "First channel ID",
  外部刺激强度: "External input intensity",
  发送一次外部概率刺激: "Send one external probability input",
  研究与训练: "Research and training",
  数据与写作: "Evidence and writing",
  参考: "Reference",
  打开导航菜单: "Open navigation menu",
  导航菜单: "Navigation menu",
  内核与对照工具: "Kernels and comparison tools",
  "先选择研究假设，再配置意识。外部 Transformer 工具单独记录贡献。":
    "Choose a research hypothesis, then configure a consciousness. External Transformer contributions are recorded separately.",
  内核工具: "Kernel tools",
  "本地 Transformer": "Local Transformer",
  "保留的 V3 基线": "Preserved V3 baseline",
  "原有激活、抑制、可塑性和生命周期；既有模型继续使用原身份。":
    "Original activation, inhibition, plasticity and lifecycle. Existing models retain their identity.",
  连续增强候选: "Continuous candidate",
  "增加逐连接短时资源、快迹及接收端局部上下文。三个新机制可分别关闭。":
    "Adds short-term synaptic resources, fast traces and receiver-local context. Each new mechanism can be disabled independently.",
  独立脉冲候选: "Independent spiking candidate",
  "使用膜电位、电流、发放和局部时序学习。图中显示去极化投影，不与原核激活混作同一指标。":
    "Uses membrane voltage, current, spikes and local timing plasticity. Graphics show a depolarization projection, distinct from baseline activation.",
  "默认 · 保留基线": "Default · preserved baseline",
  实验候选: "Experimental candidate",
  观测量: "Observed quantity",
  机制与协议: "Mechanisms and protocols",
  导出定义: "Export definition",
  如何比较: "How to compare",
  "同一内核的机制消融可在「比较与消融」配置；不同内核请创建独立意识，使用同源刺激，并分别注明观测量与资源预算。候选通过工程验证，不代表已证实研究收益。":
    "Configure within-kernel ablations in Compare and ablate. Create separate consciousnesses for different kernels, use the same stimulus source, and declare each observation quantity and resource budget. Engineering validation does not establish research gains.",
  机制规范与实施记录: "Mechanism specifications and implementation record",
  "请使用非负整数类别编号，每行一个完整序列。":
    "Use nonnegative integer category IDs, one complete sequence per line.",
  "请提供一个完整的查询序列。": "Provide one complete query sequence.",
  "训练已排队。结果和数值模型将保存为项目证据，不改动现有意识。":
    "Training queued. Results and the numeric model will be saved as project evidence without changing existing consciousnesses.",
  "本地 CPU 小模型，只输出下一事件的概率。数字是此对照模型的类别编号，不是 ThreeMind 节点 ID。不会自动回灌，也不会调用云端服务。":
    "A small local CPU model predicts next-event probabilities. Numbers are comparator category IDs, not ThreeMind node IDs. No automatic feedback or cloud calls.",
  训练对照模型: "Train a comparator",
  "训练序列（每行一条）": "Training sequences (one per line)",
  独立检验与模型参数: "Held-out evaluation and model parameters",
  "保留检验序列（可选）": "Held-out sequences (optional)",
  类别数量: "Vocabulary size",
  特征宽度: "Feature width",
  注意力层数: "Attention layers",
  训练步数上限: "Training step limit",
  "实际用时上限（秒）": "Wall-time limit (seconds)",
  "默认 2 个 CPU 线程、2 GiB 进程内存预算。达到预算会明确记录中止；已有结果保留。":
    "Defaults: 2 CPU threads and a 2 GiB process memory budget. Budget stops are explicit; completed work is retained.",
  开始本地训练: "Start local training",
  查询概率: "Query probabilities",
  对照模型: "Comparator model",
  先完成一次训练: "Complete training first",
  查询序列: "Query sequence",
  计算下一事件概率: "Compute next-event probabilities",
  导出完整概率: "Export all probabilities",
  任务与证据: "Jobs and evidence",
  "尚无任务。所有结果均与意识模型分开保存。":
    "No jobs yet. All results are stored separately from consciousness models.",
  本地训练: "Local training",
  概率查询: "Probability query",
  完成步数: "Completed steps",
  "下载结果 JSON": "Download result JSON",
  下载数值模型: "Download numeric model",
  "首个检查点保存后可查看物理状态。":
    "Physical state is available after the first checkpoint.",
  膜电位与电流: "Membrane voltage and currents",
  "图形和聊天排序使用归一化去极化，不是放电率。下表是当前检查点的原始物理状态。":
    "Graphics and chat rankings use normalized depolarization, not firing rate. The table shows raw physical state at the current checkpoint.",
  "膜电位 (mV)": "Voltage (mV)",
  "电流 (nA)": "Current (nA)",
  "适应电流 (nA)": "Adaptation current (nA)",
  累计发放: "Cumulative spikes",
  导出本页原始数据: "Export raw data on this page",
  发放事件: "Spike events",
  "按真实模拟时间记录的脉冲，与图形采样分开。设置中可关闭记录，关闭不改变发放本身。":
    "Spikes are recorded at their simulation timestamps, independently of graphical sampling. Recording can be disabled without changing firing.",
  "模拟时间（μs）": "Simulation time (μs)",
  发放节点: "Firing nodes",
  "本页没有已记录的脉冲。无脉冲不等于无膜电位活动。":
    "No recorded spikes on this page. No spikes does not mean no membrane activity.",
  "此脉冲候选的图形与读出按去极化投影显示。膜电位、电流和发放次数可在动力学中查看。":
    "This spiking candidate displays a depolarization projection. View raw voltages, currents and spike counts under Dynamics.",
  总归一化去极化: "Total normalized depolarization",
  记录脉冲事件: "Record spike events",
  "脉冲候选保存实际发放时间及节点；关闭只影响记录，不改变动力学。":
    "Record actual spike times and firing nodes for spiking candidates. Disabling recording leaves dynamics unchanged.",
};
export default kernels;
