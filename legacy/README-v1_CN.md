# ThreeMind

[中文](README_CN.md) | [English](README.md)

ThreeMind 是一个本地研究环境，用于实验持续运行、可塑的联想网络。它的最终工程目标是实现人工意识；但它不宣称当前实现已经达成或证明了这一目标。项目让动力学、输入边界、类似记忆的巩固、遗忘、结构读出与实验控制都能够被检查和复现。

[意识假设](docs/zh/consciousness-hypothesis.md) · [架构边界](docs/zh/architecture-boundaries.md) · [多模态感官与输出器官](docs/zh/multimodal-sensory-and-output-adapters.md) · [研究备忘](docs/zh/research-notes.md) · [实验与调试工作台](docs/zh/experiment-debugger.md)

## 快速启动

ThreeMind 的 Core 与 UI 是解耦的两个项目：Python Core 负责模型包、运行时、API、CLI、适配器与持久化；`threemind-ui/` 中的 React + Vite UI 只是 API 客户端，不包含意识动力学规则。

可编辑安装会同时安装正式命令 `threemind` 和简写别名 `mind`；二者调用完全相同的 CLI 实现。文档和自动化脚本统一使用不易冲突的正式名称 `threemind`。

在本目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m threemind serve
```

如需磁盘、网络、电池和整个 ThreeMind 进程的完整实测指标，可安装可选遥测依赖：

```powershell
python -m pip install -e ".[telemetry]"
```

如需上传压缩音频、常见图片或视频，可安装不含语义模型的媒体编解码依赖。标准 PCM WAV、浏览器实时 PCM 与灰度像素不安装该扩展也能工作：

```powershell
python -m pip install -e ".[media]"
```

然后在第二个终端执行：

```powershell
cd threemind-ui
npm install
npm run dev
```

Core 默认监听 `http://127.0.0.1:8877`；浏览器打开 Vite 显示的地址（通常为 `http://127.0.0.1:3001`）。生产构建可在 `threemind-ui/` 中运行 `npm run build`，再使用任意静态服务器托管 `dist/`。

## 核心边界

```text
外界载体 / 环境 / 远端设备
  → 感官或躯体适配器
  → 匿名 SensoryFrame 与输入总线
  → 注意 / 竞争门
  → 联想 Core 运行时
  → 匿名 OutputFrame 与输出总线
  → 读出器、可视化器、解读器、工具或远端输出适配器
```

- 匿名 Core 的节点与连接不保存输入文字；文字只是实验载体之一。
- 听觉与视觉适配器可把上传或实时采集的音频、图像和视频编码成匿名感官帧；声音输出器官与激活图像投影器只读取匿名 OutputBus，不执行语音识别、OCR、TTS 或目标识别。
- 适配器负责采样、编码和前置过滤。默认背景来自每秒一次的宿主物理遥测，并按每个意识的感官种子映射为不同匿名通道；随机环境与整个进程的自体遥测分别默认关闭。
- 可选躯体适配器仍可对随机环境场进行阈值、适应与噪声过滤。
- 注意/竞争门与可选插件只能处理匿名通道的增益、优先级和预算，不能写入图状态或指定语义目标。
- 默认开启的拓扑局部抑制可让有限、衰减、延迟的抑制势沿物理邻接传播，而不反转原有有向兴奋连接；它仍可关闭，以与旧式全局稳态钳制独立对照。
- 默认关闭的能量记账没有内部恢复；只有显式初始储备和外部有限能量适配器能增加该实验性标量。实测 CPU、内存、磁盘、网络与供电状态只是普通外部感官刺激，绝不作为 Core 能量。
- 输出适配器读取有界的匿名活动投影。可读字符或 AI 解读是外部观察，不能作为 Core 内有文字/意义的证据。

## 基本操作

1. 在 **意识图像** 页面点击 **开启新意识**；默认可创建启用空间嵌入的 V3 匿名模型。
2. 常规实验直接使用默认参数；需要时再在 **高级设置** 调整注意、联想、传播、学习、遗忘、巩固和容量。
3. 右侧面板用于观测、控制生命周期/快照和发送刺激；宿主物理遥测默认开启，随机环境与整个进程的自体遥测均为独立的可选输入。`＋`、耳朵和眼睛用于上传载体或显式开启实时采集；嘴巴与图像按钮订阅匿名输出投影。
4. **设置** 中可配置可视化、刺激来源、躯体与注意插件、模型参数、AI、被动读出、持久化、通知和网络传输。
5. 顶部管理页用于实例、模型包、刺激及解读历史。
6. **统计与证据** 页面用于动力学曲线、重复结构目录、时间区间收敛、配对消融和带校验和的研究数据导出。逐 tick 曲线需要在实验前开启详细动力学记录。

重复结构、延迟活动、聚类或类似语言的读出，都只是需要对照实验的观测结果，不单独构成意图、理解或意识的证据。

## 模型包与持久化

`.tmind` 是包含声明式 `manifest.json` 和运行时状态的 ZIP 模型包；它不包含可执行模型代码。模型包可以描述匿名/标记载荷、加权连接、空间嵌入和运行参数。当前支持本地文件、SQLite、MySQL 与 Cloudflare D1 持久化适配器；默认数据目录为本项目下的 `data/`，可通过 `THREEMIND_DATA` 或 `threemind serve --data-dir <path>` 修改。

后端首次启动时，仅在 `data/ui-settings.json` 不存在的情况下，才会按完整默认值创建该文件；启动过程绝不会覆盖已经存在的用户配置。受版本控制的 `data/ui-settings.example.json` 列出了可配置的公开选项与适配器默认值，凭据仍单独保存在加密存储中。

改名前生成的 `.bbx` 工件仍可读取和建立索引，避免既有实验丢失；导入后会统一写成 `.tmind`，ThreeMind 新建的模型包也只使用 `.tmind`。

为了让本地档案管理保持响应，ThreeMind 使用专用的本地 SQLite 元数据目录（`data/archive-index.sqlite3`），同时仍以 `.tmind` 保存完整、可移植的实验状态。历史模型包会在后台建立索引，而不会被实时控制接口逐个扫描。详见[归档目录与非阻塞持久化](docs/zh/archive-catalog.md)。

## 文档

| 主题 | English | 中文 |
| --- | --- | --- |
| 操作 | [operations](docs/en/operations.md) | [操作指南](docs/zh/operations.md) |
| 架构与网络协议 | [architecture boundaries](docs/en/architecture-boundaries.md) | [架构边界](docs/zh/architecture-boundaries.md) |
| 多模态感官与输出器官 | [multimodal senses and outputs](docs/en/multimodal-sensory-and-output-adapters.md) | [多模态感官与输出器官](docs/zh/multimodal-sensory-and-output-adapters.md) |
| 物理遥测感官 | [physical telemetry](docs/en/physical-telemetry-sensory-adapters.md) | [物理遥测感官适配器](docs/zh/physical-telemetry-sensory-adapters.md) |
| 归档目录 | [archive catalogue](docs/en/archive-catalog.md) | [归档目录与非阻塞持久化](docs/zh/archive-catalog.md) |
| 空间基底决策 | [spatial embedding](docs/en/spatial-embedding-decision.md) | [空间基底决策](docs/zh/spatial-embedding-decision.md) |
| 基础假设 | [consciousness hypothesis](docs/en/consciousness-hypothesis.md) | [意识假设纲要](docs/zh/consciousness-hypothesis.md) |
| 假说、实验纪律与解释边界 | [research notes](docs/en/research-notes.md) | [研究笔记](docs/zh/research-notes.md) |
| 实验与调试工作台 | [experiment debugger](docs/en/experiment-debugger.md) | [实验与调试工作台](docs/zh/experiment-debugger.md) |
| 时间帧传输与流量控制 | [temporal frame transport](docs/en/temporal-frame-transport.md) | [时间帧传输与流量控制](docs/zh/temporal-frame-transport.md) |
| 截面与时间区间读出 | [temporal-window readout](docs/en/temporal-window-readout.md) | [时间区间收敛读出](docs/zh/temporal-window-readout.md) |
| 局部抑制、能量与动力学追踪 | [inhibition, energy & dynamics](docs/en/local-inhibition-energy-and-dynamics.md) | [局部抑制、能量与动力学追踪](docs/zh/local-inhibition-energy-and-dynamics.md) |
| 统计、证据与数据导出 | [statistics and evidence](docs/en/statistics-and-evidence.md) | [统计与证据](docs/zh/statistics-and-evidence.md) |
| 干预与配对消融 | [intervention and ablation](docs/en/intervention-and-ablation.md) | [干预与消融](docs/zh/intervention-and-ablation.md) |
| 研究定位与文献备忘 | [literature memo](docs/en/literature-positioning.md) | [研究定位与文献备忘](docs/zh/literature-positioning.md) |
| 与既有网络的机制对比 | [algorithmic comparison](docs/en/algorithmic-comparison.md) | [算法机制对比](docs/zh/algorithmic-comparison.md) |
| Transformer 对比与研究路径 | [assessment](docs/en/transformer-comparison-and-research-assessment.md) | [比较与研究路径评估](docs/zh/transformer-comparison-and-research-assessment.md) |
| 研究自省与证据边界 | [self-assessment](docs/en/research-self-assessment.md) | [研究自省与证据边界](docs/zh/research-self-assessment.md) |
| 实验日志与跨实验备忘 | [lab notebook](lab/README.md)、[memos](lab/memos/README.md) | [实验日志](lab/README_CN.md)、[备忘](lab/memos/README_CN.md) |
| 论文工作区与术语表 | [paper workspace](docs/paper/README.md)、[terminology](docs/en/terminology.md) | [论文工作区](docs/paper/README_CN.md)、[术语表](docs/zh/terminology.md) |

新版文档已吸收旧版中仍有效的实验纪律：保护因果边界、保持真实连续的外界接触、采用可解释的局部动力学、显式记录生命周期、保存可恢复实验状态，并把负结果视作数据。旧版已过时的 UI、API 与存储操作则不再沿用。
