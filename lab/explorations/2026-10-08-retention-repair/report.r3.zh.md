# continuous-memory/3 局部保持修复：工程通过，默认保持增益仍不足

> **修订 r3 · 2026-10-10**
> 修订原因：原件存储位置已迁移并核验，追加当前位置解析说明，保留原实验结论。
> 原版：[report.zh.md](report.zh.md)；父版本 r2：[report.r2.zh.md](report.r2.zh.md)


> **修订 r2 · 2026-10-10**
> 修订原因：生成证据移出 Git 并完成校验归档；追加位置登记，保留原字节与结论。
> 原版：[report.zh.md](report.zh.md)；父版本 r1：[report.zh.md](report.zh.md)


[English](report.en.md) · [已批准计划与现行规范](../../../docs/zh/plans/memory-retention-v3.md) · [事前登记](protocol.md) · [完整结果](/api/v2/storage/research-artifacts/research-artifact:24b62c00d4dc5658b8570c93/content) · [验证与文件哈希](verification.json)

记录日期：2026-10-08。此次修复及有限机制实验由用户明确授权。没有开展形状/颜色教学，没有改动旧意识、外设、服务及 E64/E65/E66 或原 `/3` 实验资料。

## 结论与决定

本期完成了局部保持、普通学习恢复、局部失效/回收、默认关闭的唤醒、配置及状态兼容边界修复。Python 与 Rust 独立运行的工程检查通过。不过，在此次真实传导剂量下，默认 `memory_learning_gain=0.2` **不足以延长连接保持至本探针的 300 秒观察点**，表现弱于旧稳定度对照。工程完成不等于改善记忆的研究目标已经达成。

登记的增益 2、4 校准对照显示明显的结构保持增益，但只覆盖反复刺激，未覆盖长期背景、错误联结及反转代价。默认继续使用用户批准暂留的 0.2，没有事后改默认或改变成功判据。下一阶段应先做参数与背景/冲突对照，再决定默认，之后才进入完整形色教学。

## 实现与边界

- 节点按实际接受量、边按实际发出量计算 D，各持 H 和模拟时间锚点；固定参考量 0.1 秒，无端点共同激活代算、接收端重复记账或每事件固定奖金。节点强刺激显著性/疲劳保持局部；连接不继承节点 H。
- 删除全图保持更新、普通事件后的状态同步、全边维护列表/排序、奖励撤销转 D、稳定度清零及强置可塑性。恢复普通权重/稳定度强化及新颖性奖励。0.55 剂量学习率只用于自动节点支持度。
- 对象计算下一失效时刻，稀疏队列在既有传播后的结构阶段递送；同刻输入先于失效检查。结构变化局部维护相关索引。图、统计、观察只投影当前值，不改变动力学。
- 默认 H 遗忘不叠加旧稳定度保护；`legacy-stability` 是互斥对照。H 增长有默认对数饱和及线性饱和选项。身份与公式出生固定；数值修改走原明确配置干预流程。
- 默认自动支持度回收，手动阈值优先、零阈值才使用正死节点等待。重触达、重连、再断连、完整恢复均保留正确计时。
- 休眠/唤醒默认关闭。仅残余接触允许局部信号递送，节点和边分别要求显式正幅值阈值；两端同刻信号可叠加。不再搜索两跳候选、轮转、累计跨时刻电荷或固定赋予权重；显式干预不能被抵消。
- `/3` 拒绝传播/学习次数全局配额。宿主速度控制仍不改变模拟节奏。状态升级为 `threemind.continuous-memory-state/3.1`，算子定义更新，内核名不变；旧 `/3` 快照保留作证据并明确拒绝静默续跑。正式旧核的执行、冻结夹具与恢复保持可用。

本次**没有**移除早已存在的激活/抑制等全图循环、传播节奏、旧扫描、资源机制或来源区别。Rust 删节点仍需保序更新 Vec 中后移元素的位置索引；这是实际删除时的存储成本。载入及用户明确参数干预会遍历相关状态，普通局部更新不会执行全图保持同步。不能将此次交付称为完整执行器已完全局部化。

## 条件与连续性

本实验刻意只含 Core，是机制探针，不是意识及个人外设的教学。每一后端/条件独立从空白 Core 开始，曝光、闲置、再次输入保持同一个体；保存完整 Core 状态和后续严格恢复验证。无外设、优化器、身体或语义答案。所有组将静息死亡宽限设置为 `10^12 μs`，使无输入后的结构仍能被观察，其他配置见结果文件；因此不能推断普通个体默认寿命。

四个主条件为修复后 `/3` 默认 H、`/3` 旧稳定度、`/3` 线性 H、完整 `/2`。前三组普通学习和回收设置一致；`/2` 是整版本参照，不是单因素消融。单次普通/强刺激强度分别为 1/4；重复为每 0.1 秒配对输入，持续 120 秒；反转在 60 秒由通道 1+2 改为 1+3；弱背景为 8 秒内 80 次输入，固定八通道或连续新增至八十通道。观察曝光结束与闲置 30/120/300 秒，再给十次普通提醒。

`run-02` 完成 26 个条件对、52 个独立后端运行，保存 260 份阶段检查点。离散状态一致、浮点按相对 `1e-12` / 绝对 `1e-14` 容差比较；每份运行的同后端续跑哈希严格一致。首次 `run-01` 在反复写汇总文件时遇到 `OSError 22`，是不完整的 I/O 运行，已保留其文件；更改写出方式为每对唯一文件及末尾一次汇总，再运行独立空白组得到 `run-02`，没有合并中断个体。

## 保持、遗忘与再次输入

重复 120 秒组（结构量；无答题正确率）：

| 条件 | 曝光结束最大边 H（秒） | 闲置 120 秒平均边权重 | 闲置 300 秒活跃边数 / 平均权重 | 十次提醒后平均权重 |
| --- | ---: | ---: | --- | ---: |
| `/3` 默认，对数 g=0.2 | 40.32753 | 0.080897 | 0 / 无 | 0.423377 |
| `/3` 旧稳定度 | 不参与边遗忘 | 0.781423 | 2 / 0.212558 | 0.524344 |
| `/3` 线性 g=0.2 | 37.28410 | 0.070976 | 0 / 无 | 0.423377 |
| 完整 `/2` | 无 H | 0.781423 | 2 / 0.212558 | 0.524344 |
| `/3` 对数 g=2（校准） | 6910.89890 | 0.988162 | 2 / 0.970532 | 0.990959 |
| `/3` 对数 g=4（校准） | 122342.17967 | 0.999328 | 2 / 0.998316 | 1.000000 |

默认边 H 从约 40 秒回落至 30 秒下限，权重继续指数消退；真正发出量经短时资源与门控后较小。原实现中端点共同激活等来源的剂量已经移除，故原增益数值不能自动代表相同保护强度。重复组节点最大 H 约 114137.75 秒，闲置 300 秒后两个节点仍在、支持度合计约 1.99632，但边已消失。节点和边保护尺度的差距值得后续登记研究；不能以节点还在就声称关联记忆仍可表达。

单次普通刺激在 120 秒观察点、单次强刺激在 300 秒观察点均已无节点/活跃边。强刺激在闲置 120 秒时仍有两条边，默认平均权重 0.010576；该结果证明本条件下有较久保持，不等于一次强刺激形成永久记忆。

反转组在闲置 300 秒后，默认和线性组均无活跃边，旧稳定度及 `/2` 留四条边、平均权重约 0.186314。此处仅观察旧新结构的共存/消退，未设行为决策，不称已学会反转或避免错误固化。

固定背景曝光结束为八节点，无活跃边；三种 `/3` 均在闲置 120 秒时清空。增长背景曝光结束 `/3` 仅七节点，闲置 30 秒时清空；`/2` 曝光结束八十节点、闲置 120 秒时清空。四种主条件闲置 300 秒均无背景节点或休眠痕迹。背景停止后的有限清理不证明持续背景永不堆积；增益 2/4 未在背景组运行。

十次提醒能重新形成边，但不代表“旧记忆恢复”：默认重复组重建后的权重 0.42338，甚至低于单次曝光后已完全清空个体的重建值 0.44429。持续保留的节点稳定度/可塑性及支持状态不同，此处只提出可能解释，未作因果消融，也未统计到达同一行为标准的样本节省。

## 局部访问量与分项成本

契约检查把无关图从 2 扩大到 202 个节点，在禁止生边的同一配置下对一个旧节点输入：两个后端新增节点保持结算都是 **1**，边结算 **0**、到期处理 **0**。静默双边夹具推进 300 秒（30,000 个既有求解步）没有新增边保持结算。队列增删有 O(log N) 索引开销，不能据此宣称总耗时与全图规模绝对无关。

以下为四主条件各六案例的单次运行总墙钟秒；纯 Core 指 inject/advance，观察指 metrics/graph，保存指捕获状态/规范哈希，压缩项包含 gzip 和文件写出。Rust 使用 release 构建；均为小图，无重复计时分布，不能外推大图生产性能。

| 条件 / 后端 | Core | 观察 | 保存/哈希 | gzip/写盘 |
| --- | ---: | ---: | ---: | ---: |
| 默认 / Python | 1.65646 | 0.00364 | 0.05372 | 0.04304 |
| 默认 / Rust | 0.15645 | 0.00648 | 0.01679 | 0.03743 |
| 旧稳定度 / Python | 1.56994 | 0.00375 | 0.05111 | 0.03186 |
| 旧稳定度 / Rust | 0.13141 | 0.00572 | 0.01459 | 0.03579 |
| 线性 / Python | 1.59760 | 0.00347 | 0.04920 | 0.03353 |
| 线性 / Rust | 0.13050 | 0.00529 | 0.01400 | 0.03674 |
| `/2` / Python | 1.95676 | 0.00354 | 0.04399 | 0.04024 |
| `/2` / Rust | 0.15047 | 0.00631 | 0.01364 | 0.03240 |

不同条件的图生存时间/规模不同，因此表格是实际工作量记录，不是相同图上的内核速度排名；旧报告混合保存成本的时长也不能直接相除。

## 工程验收与限制

- Python/Rust 修复契约、旧版回归、原生读出、配置与独立 Runtime 互通：**233 通过、2 跳过**；[最终测试记录](engineering-tests-final.xml)。跳过原因是独立 PostgreSQL 测试端口 55439 未运行，未启动服务。
- 包含旧 `/2` 冻结见证、多内核 JSON/TMIND 与 SQLite 互通、出生定义、旧 `/3` 状态拒绝、跨后端恢复、同后端严格续跑、观察/分批和宿主三种时钟一致、局部访问量、手动等待/重连、残余唤醒及再次消退、配额拒绝。
- `cargo test -p threemind-core`：5 通过；原生模块及独立 Runtime release 构建通过；修改文件 Ruff 与 Rust 格式检查通过；TypeScript/Vite 构建通过（既有大分块提示）。没有进行真实浏览器交互或部署验收。
- 原项目虚拟环境指向已不存在的 Python；本次使用隔离 Python 3.12.14、独立原生库及工作目录测试依赖，未更换原虚拟环境。完整 `test_continuous_duration.py` 初次收集缺 anyio，未把它算入通过数；完整服务/API 集成未验证。运行初次亦缺 PyArrow，补齐后检查点互通全部通过。
- [较早测试记录](engineering-tests.xml)保留两项失败：新加测试错误要求已强化的唤醒边在 2 秒内删除。改为短 H 夹具及正常 300 秒闲置后通过，两后端动力学未为迎合断言而修改。

旧保持报告的 0.99533 不再是当前默认有效性的证据。R07/R40/R41、双语现代史与文言两书已追加更正；保留原结果及其当时解释。下一期参数选择、长期背景及行为验证均需要独立登记，不由此次结构探针代替。


## 数据位置修订

选定的生成证据已逐字节校验归档。原报告、评判标准、结论及数据内 source_commit 均保留。以下逻辑下载需要当前主机管理员身份，数据目录未整体公开。

`data/experiments/2026-10-08-retention-repair/`

[Location and hash index / 位置及哈希登记](../../artifact-index/2026-10-09-relocations.json)

- [run-01/results.json](/api/v2/storage/research-artifacts/research-artifact:ab7e4316ac277b87fc35eb51/content) — 3672909 B; SHA-256 `0d4e08d0658883f4e7e3c5d555e2c16a4c18a1986ccc381d12ed4739a3e39297`.
- [run-02/result-adaptive-fixed-background.json](/api/v2/storage/research-artifacts/research-artifact:a7ce9aa291413785846841d6/content) — 41943 B; SHA-256 `2ed349f545a5ed89cc260b313b8bddcbd603789384c8641b1da16c120ffd8a06`.
- [run-02/result-adaptive-growing-background.json](/api/v2/storage/research-artifacts/research-artifact:144943aa3326618e17749fd2/content) — 41961 B; SHA-256 `240f2ccc40a28336719cc5b87446e910e25ce8c239d25b4565ddca4e26653964`.
- [run-02/result-adaptive-repeat.json](/api/v2/storage/research-artifacts/research-artifact:e3a6b57ac5673f702b26d7c9/content) — 553922 B; SHA-256 `408fcafd6e6c513251ef0e2f707e87145e8f96cddb432ce7db50ee718e604f94`.
- [run-02/result-adaptive-reversal.json](/api/v2/storage/research-artifacts/research-artifact:89e78ad014d31bc0cf3ed729/content) — 558115 B; SHA-256 `bda5a6002d756f4f534b98c7594f3f01f91b0d06060423339027464a4c702957`.
- [run-02/result-adaptive-single.json](/api/v2/storage/research-artifacts/research-artifact:20f290100332143b2e88c3ca/content) — 20760 B; SHA-256 `3b3c54afd75711852c56cccfa22a6d597907e17445e3fd0864e9a87c97b23efd`.
- [run-02/result-adaptive-strong.json](/api/v2/storage/research-artifacts/research-artifact:60ab660ed37773e0b81daf61/content) — 22175 B; SHA-256 `65ef393546a2bc95158be27daed6a3b17d59240ee35fb0ab2f33567c43f4e3e2`.
- [run-02/result-gain-2-repeat.json](/api/v2/storage/research-artifacts/research-artifact:ac0d5b084b8b740cde78dfc7/content) — 555188 B; SHA-256 `e74f92626364e6b520ba4a6d04dfe9973d8e8929ea50495fc1ae0aa46a10e1c9`.
- [run-02/result-gain-4-repeat.json](/api/v2/storage/research-artifacts/research-artifact:6743690a194db497a4e2dfa3/content) — 555091 B; SHA-256 `03c23d458ee7e24767daf6d63416f220dc28e241c1bce999de918ae56abffab6`.
- [run-02/result-legacy-fixed-background.json](/api/v2/storage/research-artifacts/research-artifact:a8723976c82474a4af9e6325/content) — 41897 B; SHA-256 `d2eadf98c6c46c7a0a0f00338c031c5aa25fbbe2b61363476d9c98c149b5316e`.
- [run-02/result-legacy-growing-background.json](/api/v2/storage/research-artifacts/research-artifact:827a1cbe6fdd2ea4e654e97f/content) — 41914 B; SHA-256 `68d69bf16708985ecf151ca8bc2e20a03e1418fa8622710104ab371acaea51af`.
- [run-02/result-legacy-repeat.json](/api/v2/storage/research-artifacts/research-artifact:d03c0a7ad4e305a96781e356/content) — 555063 B; SHA-256 `58694dc7a17f6718d313752e0742a25b00569bf85ac1645fa818c19932abf8ef`.
- [run-02/result-legacy-reversal.json](/api/v2/storage/research-artifacts/research-artifact:0c4117a03e035d2494f20ab0/content) — 561954 B; SHA-256 `86b4935a0b113990e2cd54b6c410667decce589294b2b290b6dffe9b78c1b9ea`.
- [run-02/result-legacy-single.json](/api/v2/storage/research-artifacts/research-artifact:5ecea94e251edb6418d62656/content) — 20683 B; SHA-256 `48613ff3daa7b99701fe7f170fa707ff84585e8eca2ed44dea4c39d0f384cc02`.
- [run-02/result-legacy-strong.json](/api/v2/storage/research-artifacts/research-artifact:d66a8e7abec168ce5cdc516c/content) — 22145 B; SHA-256 `bd71f6e7aec2c9ac6086831c9aa3db7cb56a0daeaa585a1e323ed730ee899567`.
- [run-02/result-linear-fixed-background.json](/api/v2/storage/research-artifacts/research-artifact:a420c6f5a3b7fccbcec8b6fd/content) — 41936 B; SHA-256 `aa48c19d8726da22ecf2f8118d1a7539712efc678fab8321908c8335ee66f606`.
- [run-02/result-linear-growing-background.json](/api/v2/storage/research-artifacts/research-artifact:62f46dfc4eac49bb9f3b987f/content) — 41932 B; SHA-256 `ad3a1e79f1e003467b05d3905406a5c34ae68f11f97740c0fb06c6f28923ca56`.
- [run-02/result-linear-repeat.json](/api/v2/storage/research-artifacts/research-artifact:8fc00d16fa03ca28da96556d/content) — 553897 B; SHA-256 `607409b7a34300ba6a50277a7850befd77cecc1de65cf6dbab9fda310aded8f5`.
- [run-02/result-linear-reversal.json](/api/v2/storage/research-artifacts/research-artifact:0646a8eae953165c13711469/content) — 558116 B; SHA-256 `c0c2b77476c31104d14d24048993d0a1bda6f4a4205e857799dce062777e5164`.
- [run-02/result-linear-single.json](/api/v2/storage/research-artifacts/research-artifact:e3d76c75a94785f37468a37f/content) — 20746 B; SHA-256 `59a83027f2c7cc72dc79e1d25c0ab58cf1e3c3132ffef8ee77b0293ef1714e14`.
- [run-02/result-linear-strong.json](/api/v2/storage/research-artifacts/research-artifact:dcd60e7d402de8d60ee1548e/content) — 22149 B; SHA-256 `02cabf9dbc540a85b0f49267069a9f57f98281c261b4a0c31ee8324eb8aa0c4d`.
- [run-02/result-memory2-fixed-background.json](/api/v2/storage/research-artifacts/research-artifact:e293b44edc9df019cf2fa18f/content) — 36178 B; SHA-256 `a2c23152e7e403f8fb08e42ed7618afac43630bfdbb946e5b57188eb540b639a`.
- [run-02/result-memory2-growing-background.json](/api/v2/storage/research-artifacts/research-artifact:e0aeb96f58ad0ea79b8e7c23/content) — 36201 B; SHA-256 `ae988e316cb9287d35c2a9e021ce6a2ae5da99aa76d4750964947ccb23f26d1b`.
- [run-02/result-memory2-repeat.json](/api/v2/storage/research-artifacts/research-artifact:f3b5df0690796df383caeb40/content) — 549089 B; SHA-256 `4ceb6ae19d0dd079dc3ffb3fb13669f9510dd55d1a18509d460a4c66ab8b729d`.
- [run-02/result-memory2-reversal.json](/api/v2/storage/research-artifacts/research-artifact:8e9720330408f567bf270dbf/content) — 555977 B; SHA-256 `c74d36141a284b2e2880bf5f4841eb1e00b1748739ab3fd267b0b343ad655c37`.
- [run-02/result-memory2-single.json](/api/v2/storage/research-artifacts/research-artifact:aef0ec6f491428daf54885d8/content) — 14962 B; SHA-256 `2dae76d428163628b596fd1f11b6badb59d9fc85e2f50767ed0deed9cbc617c4`.
- [run-02/result-memory2-strong.json](/api/v2/storage/research-artifacts/research-artifact:04c6839bf8f77c23801a7a7e/content) — 16360 B; SHA-256 `6e2fe388cd783bf94033a7be59eab532a9a6a962a74716f11a4932cc83ececf3`.
- [run-02/results.json](/api/v2/storage/research-artifacts/research-artifact:24b62c00d4dc5658b8570c93/content) — 6030254 B; SHA-256 `69e4ad9c5f99dfe88f08ad979ae66bfb058f830f27441c638265681cef910c15`.


> **存储位置修订 · 2026-10-10**
> 本版追加已核验的原件迁移说明：本次清单中的原件迁至 `E:\ThreeMindData`，科学身份、哈希、原实验日期、测量与结论不变。保留正文中的路径表示历史来源，当前位置通过已登记的证据引用解析。仓库文档与冻结夹具留在原处，源副本保留；结构化查询数据及运行中的检查点仍存数据库。本说明不表示缺失的历史资料已恢复。
