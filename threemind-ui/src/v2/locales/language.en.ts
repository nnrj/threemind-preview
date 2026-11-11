const language: Record<string, string> = {
  导入完整语言意识: "Import complete language consciousness",
  导出完整语言意识: "Export complete language consciousness",
  "语言设备包不能超过 256 MiB":
    "Language device bundle must not exceed 256 MiB",
  "包括 Core、适配器状态和已训练权重；Qwen 基础模型按固定版本另行安装。":
    "Includes Core, adapter state and trained weights; install pinned Qwen base models separately.",
  "格式化 JSON": "Format JSON",
  "编辑时检查 JSON 语法，创建时校验完整协议及模型版本。":
    "JSON syntax is checked while editing; creation validates the full protocol and model identity.",
  对话实验: "Dialogue experiments",
  语言感官与输出: "Language input and output",
  活动转换特征: "Activity projection",
  "有符号平均 · 原协议": "Signed average · original protocol",
  "无符号峰值 · 新观察协议": "Unsigned peak · new observation protocol",
  "只改变外部活动投影；切换后需要重新校准转换头，已有意识保持原协议。":
    "Changes the external projection only. Recalibrate the conversion head after switching; existing instances keep their protocol.",
  图形配置: "Visual configuration",
  "JSON 编辑": "Edit JSON",
  语言适配协议: "Language adapter protocol",
  "JSON 尚未通过语法校验": "JSON syntax is not yet valid",
  "请保留 protocol 与 compute 配置对象":
    "Keep the protocol and compute configuration objects",
  输入路径: "Input route",
  输出路径: "Output route",
  现有文本感官: "Existing text sense",
  "从零开始的 Transformer": "Transformer from scratch",
  原始活动读出: "Raw activity readout",
  转换方式: "Conversion mode",
  "严格转换：只看 Core 活动": "Strict: Core activity only",
  "知识辅助：同时看到原问题": "Assisted: also sees the question",
  "响应观察长度（模拟毫秒）": "Response window (simulation ms)",
  "输入 Transformer 权重": "Input Transformer weights",
  "输出 Transformer 权重": "Output Transformer weights",
  "未经训练 · 按种子随机初始化": "Untrained · seeded random initialization",
  活动到语言的映射: "Activity-to-language mapping",
  "未校准：保留原始读出": "Uncalibrated: keep raw activity",
  "随机权重模型没有预先学过语言。原始读出始终保留，语言转换的结果需要通过对照实验检验。":
    "A random model has not learned language. Raw activity is always retained; converted language needs controlled validation.",
  随机种子: "Random seed",
  感官维数: "Sensory dimensions",
  "活动采样间隔（微秒）": "Activity sampling interval (µs)",
  活动投影维数: "Activity projection dimensions",
  时间分段数: "Time bins",
  活动前缀长度: "Activity prefix length",
  输出长度上限: "Maximum output tokens",
  随机模型宽度: "Scratch model width",
  注意力头数: "Attention heads",
  "Transformer 层数": "Transformer layers",
  字节上下文长度: "Byte context length",
  "模型结构、感官映射和权重在意识创建时绑定。使用训练后的新版本时，从原意识检查点建立新的对照意识。":
    "Architecture, sensory mapping and weights are bound at creation. Branch from a checkpoint to use a newly trained version.",
  "对话、转换器与训练证据按项目保存。":
    "Conversations, converters and training evidence belong to the project.",
  "让语言经过感官适配器进入意识，观察其实际活动，再选择是否转换为语言。":
    "Pass language through a sensory adapter, observe actual activity, and optionally convert it to language.",
  选择语言实验意识: "Select a language consciousness",
  从此意识建立对照: "Branch a comparison",
  对话与活动: "Dialogue and activity",
  训练转换器: "Train converters",
  版本与证据: "Versions and evidence",
  对话与原始读出: "Dialogue and raw readouts",
  更早记录: "Older records",
  较新记录: "Newer records",
  "创建一个意识，开始对话实验": "Create a consciousness to begin",
  "输入可选原文本感官、随机权重 Transformer 或预训练模型，输出可独立选择。":
    "Choose a text sense, random Transformer or pretrained model. Choose the output independently.",
  "输入第一句话。未经训练的转换器可能只产生不可读的输出，原始活动仍可观察。":
    "Send the first sentence. An untrained converter may produce unreadable output; raw activity remains observable.",
  输入刺激: "Input stimulus",
  意识活动: "Consciousness activity",
  "本轮已记录活动，尚无完成的时序读出窗口。":
    "Activity recorded; no temporal window has completed yet.",
  "本轮未观察到激活。": "No activation observed in this turn.",
  "观察提前结束，未补造后续状态。":
    "Observation ended early; later states were not fabricated.",
  外部语言辅助: "External language assistance",
  活动的语言转换: "Activity converted to language",
  "尚未训练活动到语言的映射，请在训练转换器中校准。":
    "No activity-to-language mapping is trained. Use converter training to calibrate it.",
  "没有可读的语言输出；原始活动见上方。":
    "No readable language output; see raw activity above.",
  "输入语言刺激…": "Enter a language stimulus…",
  当前实验: "Current experiment",
  "查看意识图像、结构与检查点": "View network, structure and checkpoints",
  "这里按轮推进模拟；等待输入时暂停。墙钟等待不会偷偷消耗模型的模拟生命。":
    "Simulation advances per turn and pauses between inputs. Wall-clock waiting does not consume simulated lifetime.",
  语言适配器说明: "Language adapter guide",
  请先选择意识: "Select a consciousness first",
  从随机权重学习文本: "Learn text from random weights",
  "只训练外置 Transformer。每行是一个完整样本，不改标点，不改 Core 参数。":
    "Train only the external Transformer. Each line is one complete example; punctuation and Core parameters are preserved.",
  训练输入或输出模型: "Train input or output model",
  "训练文本（每行一句）": "Training text (one sentence per line)",
  训练并保存新版本: "Train and save a new version",
  活动到语言的校准: "Activity-to-language calibration",
  "选择本页已测活动并填写期望表达。这是外置转换器的监督目标，不能当作 Core 已经理解的证据。":
    "Pair measured activity on this page with desired text. These supervise the external converter; they are not evidence of Core understanding.",
  "希望转换成的文字（留空不参加）": "Desired text (leave blank to exclude)",
  至少选择两次活动并填写对应的校准文字:
    "Select at least two activity records and supply calibration text",
  同时训练随机输出模型的权重: "Also train scratch decoder weights",
  训练输出映射: "Train output mapping",
  "训练不会替换现有会话的权重；完成后建立对照意识并选择新版本。":
    "Training does not replace existing session weights. Create a comparison branch and select the new version.",
  模型版本: "Model versions",
  最近任务: "Recent jobs",
  本页对话证据: "Evidence for displayed turns",
  下载完整过程: "Download complete process",
  创建语言实验意识: "Create a language consciousness",
  内核与来源: "Kernel and origin",
  "来源意识编号（空白表示新建）":
    "Source consciousness ID (blank for a new one)",
  "最近八条读出；完整记录可下载。":
    "Latest eight readouts; download the complete record.",
  "末次采样的前十二个激活节点，仅作显示；完整过程已保存。":
    "Top twelve active nodes at the last sample, for display only. The complete process is saved.",
  "无新输入 · 内部活动观察": "No new input · internal activity observation",
  "正常推进意识，未发送提示。已经在途的输入仍正常递送。":
    "Advance normally without sending a prompt. Inputs already in flight still arrive as scheduled.",
  连续观察内部活动: "Observe ongoing activity",
  停止观察: "Stop observing",
  本窗计算耗时: "Window computation time",
  "按轮推进模拟，也可连续观察无新输入活动。未开启观察时等待输入会暂停；计算耗时与模拟时间分别显示。":
    "Advance by turns or observe ongoing activity without new input. Otherwise pause between inputs; computation time and simulated time are shown separately.",
  "逐窗显示；无新输入。停止后当前窗口完成，每次最多120窗。":
    "Display each window without new input. Stopping finishes the current window; at most 120 windows per session.",
};
export default language;
