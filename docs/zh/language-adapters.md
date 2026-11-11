# 语言感官与外置 Transformer

[English](../en/language-adapters.md) · [批准方案](plans/robotics-and-language.md)

本工具让语言经可选的 Transformer 感官进入 ThreeMind，也让真实的 Core 活动经可选的 Transformer 转换为文字。Transformer 是外设；Core 的方程、学习规则和匿名通道原则没有改动。

## 三条可独立选择的通路

输入可用原文本感官、Qwen3-Embedding-0.6B，或从随机权重开始的字节级 Transformer。输出可直接显示活动、使用 Qwen3-0.6B，或使用独立的字节级 Transformer。两侧选择互不绑定：例如随机 Transformer 输入配合原始活动输出，不需要解码器。

随机模型使用 UTF-8 字节和两个边界符号，默认宽度 128、4 个注意力头、2 层、512 字节上下文。没有预训练权重，也没有训练好的分词器。固定随机种子产生可复现的初始模型；仅用研究者实际提供的语料训练。它起初可能输出乱码，不能据此宣称 ThreeMind 没有活动或已懂语言。

输入向量按固定维数、L2 归一化和正负通道规则进入现有输入总线，不读取图结构来选择刺激目标。原文本感官继续使用原来的规范化、分帧和映射。输出先保存整个有界活动过程，再做时间分段和匿名投影；完整轨迹、原有被动/时序读出仍保留，投影抵消不等于没有活动。

## 转换与知识辅助

严格模式的独立解码进程只得到声明的活动向量、冻结的转换器和固定提示，不收到输入问题、教学记录或答案。预训练 Qwen 的语言先验仍然存在；严格隔离只防止直接偷看，不能单凭这点证明经验来自 Core。知识辅助模式允许看到原问题，并在结果中列出可见信息。

没有校准映射时，严格模式显示实际活动及“尚未校准”，不让语言模型凭空代答。通过 UI 的“活动到语言的校准”可选择已记录的活动，填写对应文字。此文字是外置转换器的监督目标，不是 Core 已理解的事实。Qwen 基础权重冻结；随机输出模型可以显式选择连同映射头一起训练。

随机输入或输出模型也可单独用逐句语料训练下一字节预测。一次训练保存新的 `safetensors` 文件、语料/参数摘要、来源版本及损失；不替换旧意识绑定的权重。正式对照前固定转换器。采用新版本时，从原意识检查点创建一个新对照意识，保留旧实例。

## 操作

UI 使用“对话实验”：创建意识 → 选择输入/输出 → 发送刺激 → 同窗查看实际活动和可选语言输出。训练、版本与证据各有标签页。当前语言实验按轮推进模拟，等待输入时暂停；每轮观察长度是工具参数，不是意识总寿命上限。死亡不会自动复活。

REST 路径是 `/api/v2/projects/{project}/language`；操作目录提供 `language.catalogue/create/send/turns/train_scratch/train_head`，CLI 与 MCP 调相同接口。后台计算用原有作业租约和 worker，无需另建分布式服务。任务会核查 worker 的 Torch 和固定模型资产能力；不会在推理过程中自动下载模型。

“版本与证据”可以导出/导入完整 `.tmlanguage` 设备包，对应 `language.export/import`。它保存 Core、在途输入、读出状态、感官版本、随机 Transformer 权重及输出映射头。原始活动不会被解码文字替代。Qwen 基础权重只登记固定版本和文件哈希，目标设备另行安装，避免每个快照重复存放 2.6 GiB 模型。导入创建独立、暂停的意识，保留原 Core 身份及死亡状态；不会覆写当前意识。设备包上限 256 MiB，导入核验所有成员及哈希；这不是整个科研项目的长期归档格式。

独立运行无需 PostgreSQL：

```powershell
$py = ".work/kernel-venv/Scripts/python.exe"
& $py -m threemind_transformer.language_cli template | Set-Content -Encoding utf8 language.json
& $py -m threemind_transformer.language_cli turn --protocol language.json --store language.sqlite --text "甲是松子。" --output first.json
& $py -m threemind_transformer.language_cli turn --protocol language.json --store language.sqlite --resume --text "乙是铃铛。" --output second.json
& $py -m threemind_transformer.language_cli export --store language.sqlite --output saved.tmlanguage
& $py -m threemind_transformer.language_cli import saved.tmlanguage --store restored.sqlite --assets-dir restored-assets
```

随机输入例：把协议的 `input_model` 改为 `scratch`，输出保持 `raw`。使用新 SQLite 文件或新实例名，不能给旧恢复状态换协议。训练命令为 `language_cli train training.json --kind scratch --output learned.safetensors`；映射头训练改为 `--kind head`。训练 JSON 使用与 API 同一 `ScratchTraining` / `LanguageTraining` 结构。输出文件不能覆盖已有文件。SQLite 是设备恢复库，保留有限恢复窗口；长期科研证据另存每次输出文件或使用 Lab。

新建时 CLI 可传 `--kernel`、`--config`；恢复保持原参数。使用已训练权重的设备在导出时同时传 `--head`、`--input-checkpoint`、`--output-checkpoint` 中实际使用的项；缺失或版本不符会拒绝导出。导入后的 `restored-assets/protocol.json` 和各权重文件用于后续 `turn --resume`。

需要 Qwen 时，显式安装固定资产：`python -m threemind_transformer.language_assets install embedding` 和 `install decoder`。约 2.6 GiB 缓存在 E 盘项目 `.work/language-models`，每个文件核验哈希；也可配置 `THREEMIND_LANGUAGE_MODELS`。随机路线只需要 Torch 与 safetensors。CPU 始终可用；明确选择 CUDA 时，设备故障在新进程从原输入回退 CPU。语义错误、预算耗尽不会假装计算成功。

## 验证状态与尚未回答的问题

2026-10-02：随机模型初始化、训练、版本恢复、严格解码信息隔离以及原文本总线继续状态已有单元验证；独立数据库/worker 与 1440/390 像素界面已完成创建、发送、训练和证据下载验收。Qwen 输入模型已在本机 GTX 1650 实际编码两句话，峰值显存约 1.13 GiB。这是工程能力验证，没有把两句话包装成语言学习实验。完整机械臂与语言归因实验仍按批准计划执行，结果另记。

## 用户补充原话（2026-10-02）

> 补充：关于语言部分，注意到你引入了 Qwen 小模型，这是好的。但我希望也支持一种形式，支持把未经训练的原始的Transformer接入，使之通过适配器与 ThreeMind 连接，使得 Transformer 成为 ThreeMind 的一个感官或者外置的中枢，语言刺激可以经过Transformer 再经过适配器作再经过输入总线作为刺激到达内核，内核对语言刺激的响应也可通过输出总线经过或者不经过 Transformer  输出（是否经过可能需要实验测试）。也就是说，我希望有一种利用 Transformer 架构的感官适配器，尝试能通过它与 ThreeMind 进行自然语言训练和交流。注意，这不侵入内核，作为适配器 ，Transformer  适配器与其他适配器没什么本质区别。

以上按当前会话原话收录；实现选择与实验结论不混入引文。


2026-10-02 追加：固定 Qwen 模型的 CUDA 编码、两步映射头训练、严格解码均实际完成，峰值预留显存分别约 1.13 / 1.32 / 1.14 GiB。短训练仅作工程验收，不作语言准确率结论。部署新增独立 `threemind-transformer` 包：仅安装 Runtime 时不会加载 Torch、语言模型或 Lab；按需安装 `packages/transformer[scratch]` 或 `[language]`。

同日复验：故意将该独立任务的显存预算设为 128 MiB，实际触发 CUDA 分配失败，继而从原输入在全新 CPU 进程完成编码。修正 Windows 虚拟环境启动器导致的内存漏计后，CPU 进程树峰值约 3.82 GiB；早先只计启动器的内存值无效。终止预算超限任务时连同其子进程终止，不涉及其他程序。完整设备包恢复前后的下一次输入产生相同 Core 状态哈希；数据库导入、继续输入与界面导入导出均通过隔离验证。


E26 科研初验已完成：原文本、随机 Transformer 两种输入路线均能用从零训练的输出器还原四个校准词；新对应尚未可靠表达。活动干预确实改变输出，但不据此宣称已会自然语言。[完整报告及限制](../../lab/explorations/2026-10-02-robot-language/report.zh.md)

## 2026-10-04：无新输入活动观察

“对话实验”新增**连续观察内部活动／停止观察**。每窗正常推进意识，记录完整过程、原有读出及可选文字，不发送空字符串、假问题或唤醒刺激。已在途事件仍正常递送，原始结果列明待递送输入数量；因此“本窗无新输入”和“已无外部事件待到达”可区分。死亡后停止，不自动复活。

UI每次最多120窗，CLI每次最多256窗；这是单次观察任务的资源边界，不是意识寿命。停止后完成当前窗口并保留状态。每个窗口的模拟时间与实际计算耗时分开显示；本机逐窗独立加载Qwen可能慢于实时。批量离线比较可复用冻结权重，但不会继承上一窗口的生成词或KV缓存。

```powershell
& .work/kernel-venv/Scripts/python.exe -m threemind_transformer.language_cli observe --store language.sqlite --windows 20 --output activity.jsonl --compute-device cuda
```

已有校准器时增加 `--head head.safetensors`；从零输出权重使用 `--output-checkpoint`。协议与内核从保存的实例恢复，不另换映射。每窗保存SQLite新修订并立即输出JSONL；拒绝覆盖已有结果文件。Python使用 `LanguageSession.observe()` 或 `.stream(windows=20)`；REST为 `POST .../language/sessions/{run_id}/observations`，正文是 `request_id`、`expected_revision`；通用CLI/MCP目录名为 `language.observe`。

无输入观察的输出强制使用严格模式：只看本窗活动、固定提示和冻结转换器；即使原会话允许知识辅助，也不把上一句提问传给它，输出不会回灌。全零投影保持静默；有活动而投影抵消仍应查原始轨迹。

新增可选 `threemind.language-adapter/2` 的 `feature_layout="unsigned-peak"`，保存每时间段、每桶的激活峰值，避免正负投影相消，仍可能存在桶碰撞。旧 `/1` 的有符号平均、序列化字段和映射身份保持不变，新布局不能静默替换旧头。它是观察工具版本，不是Core版本；[E42](plans/scratch-language-centre.md)比较两种布局。

### 2026-10-05：中枢适配器 / Central adapters

[面向任务的功能分类与边界 / Task-facing roles and boundaries](reference/central-adapters.md)。协议和Core权限不因名称改变；不是预设脑区。 / The name changes neither protocol nor Core privileges and creates no predefined brain region.
