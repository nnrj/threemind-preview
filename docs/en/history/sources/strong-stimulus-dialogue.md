# Strong-input primary sources: request, discussion and implementation reply

> Public edition, 2026-11-11: private conversation locators and manuscript/submission discussions are omitted where present. Scientific records retain their original dates; the complete source remains unchanged.


[简体中文](../../../zh/history/sources/strong-stimulus-dialogue.md) · [English](strong-stimulus-dialogue.md)


> **Public-edition edit (2026-11-11; source lines 5-5):** Private conversation IDs and locators are omitted; scientific quotations and records are retained. The complete source remains unchanged.



Source: the Codex conversation ThreeMind项目, ID `[private locator omitted]`. All 314 retrievable turns were read through a read-only interface on 2026-10-01. Times below are **turn start times in UTC+8**, not precise timestamps for every message within a turn. Only selected project-history messages are published, not tool logs, internal reasoning or the full private cache. Original wording and typos are retained. Attachments were not retrieved.

Hashes cover the displayed original text before Markdown quotation prefixes. Both language editions retain the same Chinese primary source. English introductions are editorial summaries, not original English utterances.

## Evidence note

The three exchanges below document a request for stronger persistence after intense input, content-neutral local consolidation, and a finite single-event cap. The assistant reports implementation and tests at that time; this is not a claim that those tests were rerun during compilation. Existing historical code separately verifies the formula. These messages do not derive the exact reference 1 or coefficient 0.075.

### 2026-07-25T14:10:09+08:00 · user


> **Public-edition edit (2026-11-11; source lines 15-15):** Private conversation IDs and locators are omitted; scientific quotations and records are retained. The complete source remains unchanged.



`turn: [private locator omitted]` · `SHA-256: ec1654d6ce09aa33309bcfb5dfeeea24afb66d7480c8897d704dd2a971dd4c16`

原文 / Verbatim Chinese source

> 补充：遗忘不是固定速率的，越强烈的刺激会越难遗忘，对于强烈的刺激会直接固化很难遗忘。特别注意遗忘不是代码的主动裁剪，而是刺激导致连接或改变连接状态的适合，就改变了连接的属性，连接的某个决定是否强烈的数值随时间掉落到一定程度则断开。我记得旧版BlueBox大概就是这么实现的吧（也可能没有这么实现）。你可以核查、评估，然后看这样改进是否合理（也可能现状已经如此或者更优而无需改进）。

### 2026-07-25T14:10:09+08:00 · assistant


> **Public-edition edit (2026-11-11; source lines 23-23):** Private conversation IDs and locators are omitted; scientific quotations and records are retained. The complete source remains unchanged.



`turn: [private locator omitted]` · `SHA-256: 21734d1e386dad4ec5bbf01a89c0ebefd155866f03ff259b4066a69fb4c0a878`

原文 / Verbatim Chinese source

> 你的理解基本正确，而且旧版与刚恢复的 new runtime 都采用了这个方向：
>
> - 每个连接有 `weight`、`stability`、`eligibility`。
> - 未被传播触达的连接，`weight` 会随 tick 自然衰减。
> - `stability` 越高，实际衰减越慢。
> - 连接并非被“定时直接删除”；只有 `weight < prune_threshold` 才断开并从图中移除。
> - 重复直接触达、联想传播和共同激活会增强 `weight / eligibility / stability`。
> - 节点只在无连接、无激活且长期未触达时才清除；这更接近失去一切结构支持后的消退。
>
> 旧版核心公式与现在恢复的公式一致：
>
> ```text
> weight *= 1 - edge_decay * (1 - (0.08 + 0.92 * stability))
> ```
>
> 所以它不是固定速率：高稳定度连接的遗忘显著更慢；`eligibility` 也会影响稳定度随时间下降的速度。
>
> 不过，你提出的“强烈刺激可直接或近乎直接固化”在当前实现中还不够充分。现在高强度刺激会提高直接激活、共同激活概率和连接增强速度，但新生连接的 `stability` 仍然从较低值开始，主要依赖随后重复触达巩固。
>
> 我认为应改进为：
>
> - 将一次刺激的原始能量、首见性、直接触达强度形成一个 `consolidation_impulse`。
> - 强刺激或高度新颖刺激可在连接诞生时就给予有限但明显的初始稳定度。
> - 这个初始固化应是饱和且有阈值的，避免任何一次普通输入都永久化。
> - 节点清除也可进一步改为“结构支持度/存在度”自然衰减到零，而非仅以 `node_prune_after` 作为技术性时间条件。
>
> 因此：当前遗忘机制方向正确，也已与旧版对齐；但“强刺激首次固化”和“节点存在度自然衰退”值得作为下一次内核改进。


### 2026-07-25T14:14:12+08:00 · user


> **Public-edition edit (2026-11-11; source lines 58-58):** Private conversation IDs and locators are omitted; scientific quotations and records are retained. The complete source remains unchanged.



`turn: [private locator omitted]` · `SHA-256: e59549a3d1baba29709098f76beb9a5f14935aa194466d7e9ab43878cd98065b`

原文 / Verbatim Chinese source

> 好的，可以按照你说的改进有关强烈刺激。不过所以改进应当谨慎，避免连接本身受到代码写死的东西影响，导致出现不由刺激决定的某种倾向。此外，联想、固化和遗忘的某些参数，应该支持在UI的设置中设置（底层是core的某些API接收并执行某些设置项或参数调整），默认的这些参数值，应该接近人类大脑的联想、固化和遗忘规律。本次仅评估和建议。

### 2026-07-25T14:14:12+08:00 · assistant


> **Public-edition edit (2026-11-11; source lines 66-66):** Private conversation IDs and locators are omitted; scientific quotations and records are retained. The complete source remains unchanged.



`turn: [private locator omitted]` · `SHA-256: 5797d1add5e8ce9303415c45d5bde31730eb28e46ad2fb3d905df4b4be7f683d`

原文 / Verbatim Chinese source

> 这个改进值得做，但要把“代码决定倾向”限制在机制层，不把任何内容、概念或行为偏好写进内核。
>
> 建议的原则是：
>
> - Core 只知道数值状态：能量、触达、共同激活、时间、连接权重、稳定度、可塑性。
> - 不允许代码识别“这是什么文字”“是否重要概念”“是否正面/负面”等语义。
> - 强烈刺激的作用只能来自其输入能量与网络当时状态，而不是刺激内容。
> - 联想只能由已存在连接、近期触达与当前激活的局部传播产生。
>
> 建议增加一个中性的“巩固脉冲”：
>
> ```text
> consolidation_impulse =
>   输入强度
>   × 首见性
>   × 直接触达程度
>   × 共同激活程度
>   × 当前可塑性
> ```
>
> 它只影响新生或被触达连接的初始 `weight / stability / eligibility`。高强度、首次、集中触达的刺激会更容易留下强痕迹；重复刺激仍是最可靠的长期固化来源。它应采用饱和曲线，避免一次极强输入把连接变成绝对永久记忆。
>
> UI 设置建议放在“模型与空间”下新增“联想、固化与遗忘”分组，并由 `/api/model/parameters` 写入当前模型包：
>
> - 联想窗口：近期多少 tick 内的触达可互相关联。
> - 注意力预算：每 tick 最多保留多少感官特征。
> - 传播增益与传播阈值：联想的扩散强度与触发门槛。
> - 学习率：重复共同激活增强连接的速度。
> - 首次刺激巩固增益：首次触达形成初始痕迹的程度。
> - 强度巩固增益：外界输入能量对初始固化的影响。
> - 稳定度增益/衰减：长期巩固和淡化速度。
> - 遗忘速率、裁剪阈值：连接自然消退速度与断开点。
> - 节点存在支持衰减：孤立且无激活节点的消退速度。
> - 稳态总激活：控制整体网络不长期饱和。
>
> “接近人类大脑”应理解为定性机制，而不是声称数值上模拟真实大脑。比较合适的默认倾向是：
>
> - 大多数低强度、一次性输入迅速模糊。
> - 重复且相近的触达逐步稳定。
> - 首次强烈输入留下明显但仍可被后续经验修正的痕迹。
> - 已高度固化连接很难消失，但不是不可消失。
> - 联想是局部、预算受限、有衰减的，而非全图搜索。
>
> 我建议默认采用保守的“可塑但不轻易永久化”参数；强刺激只提高长期保留概率，不制造任何固定语义或行为倾向。


### 2026-07-25T14:15:39+08:00 · user


> **Public-edition edit (2026-11-11; source lines 118-118):** Private conversation IDs and locators are omitted; scientific quotations and records are retained. The complete source remains unchanged.



`turn: [private locator omitted]` · `SHA-256: f85852a7a3b8df9214cabcfa07905677cafaa550391b83ee3d8e95644f2b481e`

原文 / Verbatim Chinese source

> 好的，开始改进。

### 2026-07-25T14:15:39+08:00 · assistant


> **Public-edition edit (2026-11-11; source lines 126-126):** Private conversation IDs and locators are omitted; scientific quotations and records are retained. The complete source remains unchanged.



`turn: [private locator omitted]` · `SHA-256: df4e53c01eac7bfe9b6d7a3c78f8d60eb9b6b41abe231079fc3ea0b8cd37eadf`

原文 / Verbatim Chinese source

> 已完成这项改进。
>
> 现在强刺激不会因语义而得到特殊待遇，只通过以下中性数值进入巩固过程：
>
> - 输入能量
> - 首见性
> - 直接触达强度
> - 节点当前可塑性
> - 同时触达的连接端点状态
>
> 新增的 `consolidation_impulse` 会影响新连接与既有连接的 `weight / stability / eligibility`。因此：
>
> - 强烈刺激可在首次出现时留下更稳定的初始痕迹。
> - 强刺激再次触达既有结构时，会更明显地加固。
> - 普通重复刺激仍是长期固化的主要来源。
> - 单次固化有上限，避免一次输入变成绝对永久记忆。
> - 任何刺激内容本身不参与判断。
>
> 遗忘机制仍然是连接状态自然衰减到阈值后断开；没有改回“定时直接删除”。另外，孤立节点已改为通过 `support`（存在支持度）自然衰退至阈值后消退，替代原先的固定存活 tick 条件。
>
> 设置页“模型与空间 → 关联、遗忘与生命循环”已增加：
>
> - 首次触达固化增益
> - 强刺激固化增益
> - 单次固化上限
> - 节点存在支持增益 / 衰减 / 消退阈值
> - 原有联想、传播、遗忘、稳定度与稳态参数
>
> 验证完成：
>
> - Core：27 项测试通过
> - UI：生产构建通过
>
> 需重启 Core 后生效。


---

Compiled on 2026-10-01, covering the record available on that date. Original evidence is retained separately from later interpretation.
