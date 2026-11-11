# 多内核增强实施记录

[English](../../en/plans/multi-kernel-implementation.md) · [原则及原文](../kernel-evolution-principles.md)

状态日期：2026-09-28。已获准实施；按实际验收更新，不把计划等同于完成。

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| 0 | 冻结 causal/9 源码、行为样例与假设 | 已实现：固定历史源码、双后端行为样例、原假设哈希 |
| 1 | 内核注册、声明式定义、状态身份、配置和 CLI | 三个内核已接通；模型包和独立设备恢复已验证 |
| 2 | 连续候选：短时突触、快慢权重、接收端局部上下文寻址；Python/Rust | 已实现并完成工程验收；研究收益尚未测定 |
| 3 | 独立膜电位／脉冲候选，独立部署打包 | 已实现：解析 RC、发放、不应期、STDP、独立构建及真实产物验收 |
| 4 | 本地小型 Transformer 对照及可选模型适配器 | 已实现：本地训练／概率、数值模型、可选 HTTP、显式输入与外部贡献审计 |
| 5 | 配置／研究界面、宽窄屏交互验收、小型比较 | 已实现：六项浏览器验收，九组有界匿名工程比较；不等同于认知能力验证 |

## 不变边界

首批验证：原核与相关测试 55 项通过（12 项数据库测试因独立测试服务未启动而跳过），Rust Core 2 项通过。冻结样例同时核对 Python 与 Rust；未把数据库跳过项记作通过。后续新功能另行验收。

- Git `b53fba1` 保留 `threemind.causal/9` / `threemind.state/6`。冻结脚本 `scripts/freeze-causal9.py` 执行固定历史文件，不读取 `data/`。样例涵盖出生、重复触达、传播、抑制、饱和耗能、遗忘、死亡、断连与删点。
- `kernel_id` 是科学模型，`reference/native` 是实现。后端缺失不能静默换核。参数消融与基本动力学的类型分开。
- 新状态绑定独立定义、机制版本和哈希；旧模型不自动转换。保留输入映射、无限时长默认值和活动死亡定义。
- Core 不依赖数据库、UI 或网络。沿用 Lab PostgreSQL 和独立运行时可选 SQLite；不建 MQ 或分布式共享脑求解器。
- JSON 选择可信算子，独立构建不冻结塑性网络。远程模型可选且须记录外部贡献。

## 机制与验收

注册基础验证 28 项通过、3 项独立数据库测试跳过。提供 

```powershell
.\.work\kernel-venv\Scripts\python.exe -m threemind_kernels.cli list
.\.work\kernel-venv\Scripts\python.exe -m threemind_kernels.cli inspect threemind.causal/9
.\.work\kernel-venv\Scripts\python.exe -m threemind_kernels.cli validate definition.json
```

Python 及独立 Rust 运行时均可用 `--kernel threemind.continuous/1 --config config.json` 或 `--definition definition.json` 创建；恢复时按状态身份派发，禁止用创建参数覆盖已存状态。配置目录、RunSpec 和 worker 来源记录已带内核身份。默认仍为 causal/9；连续候选显式选择，不自动升级现有意识。独立环境和 `start-lab.ps1 -Python` 用法见[部署文档](../v2-operations.md)。重建环境后发现的 NumPy `trapz` 移除问题改用已依赖 SciPy 的同一梯形积分公式，既有统计测试通过。

连续候选早期验收：冻结基线、配置、发育和探针相关 159 项通过；独立 Rust 模型／SQLite 互操作及无效模型拒绝 13 项通过。当时仅使用 `127.0.0.1:55439` 独立测试库。新算子状态完整进入模型包。继承出生保留慢连接，清空短时资源历史、快迹、活动与在途消息；精确恢复不清空这些状态。机制方程、阶段和局限见[候选规范](candidate-mechanisms.md)。最终验收与业务部署记录如下。

## 本轮最终验收与部署

- 最终受影响 Python／Rust、数据库及真实独立构建测试 **259 项通过**，另有 3 项适配器注册测试通过。包括保留 V3、跨后端完整状态、原始发放与记录关闭不改状态、模型继承／导入导出、项目隔离、稳定请求编号、显式概率输入、种群恢复和文档。没有把跳过项记成通过。
- 前端 TypeScript／Vite 构建通过，6 项 Edge 浏览器测试通过。覆盖基础／高级／JSON 同源与只读、内核切换、默认无限时长、聊天混合输入与时序读出、发送清空、历史滚动和有界可视消息、390／320 像素布局、文本导航、Transformer 训练／查询／显式接入及物理状态分页。1440 像素宽屏、390 像素窄屏截图已人工查看；图片保留在忽略的 `.work/kernel-browser-acceptance`。
- [九组小规模比较](../../../lab/validations/2026-09-28-kernel-candidates/README.md)全部通过跨后端核对和自身精确恢复。原始证据约 1.02 MiB；没有新增长时间语言训练或 GPU 实验。
- 业务库 `127.0.0.1:5433/threemind` 已从 schema 50 更新到 **51**。更新前确认没有运行中的工作站／worker 或任务租约；迁移只改变任务能力匹配。旧意识、实验和 `data/` 没有转换、扫描或清理。随后 `doctor` 确认数据库连接和原生基线内核可用，未启动旧意识。
- 系统 Python 3.13 的 `.work/kernel-venv` 已恢复开发／媒体依赖和原生扩展；可选 CPU PyTorch 已安装，没有下载预训练模型。无需 Anaconda。E 盘验收后剩余约 51.9 GiB。业务服务保持停止，按[使用指南](../v2-kernels.md)启动。
- 已确认的普通构建提示仍有部分绘图／编辑器分块超过 500 kB；按需加载依然有效。测试环境另有 Starlette TestClient 弃用提示，未造成失败。本轮没有据此声称所有大规模运行性能均已验证。

本轮实现范围已闭合。尚未开展的是新的科学探索：保持、干扰、反转、顺序、环境适应和关系组合；需要独立校准刺激单位与读出尺度后再设计，不能用工程测试或外部 Transformer 的成功替代。独立远程协议已经实现，本轮未部署公网服务，也未实现分布式共享脑求解器。连续候选的快迹是局部标量，不冒充完整 Transformer 矩阵。

本地阶段提交：`4f39b9a` 固定基线；`f306d04` 注册和身份；`b422040` 连续候选；`691a499` 脉冲内核、独立构建与 Transformer 后端。界面与最终记录另作本地提交，不 push。

每项先固定状态、单位、方程、消息阶段、默认值依据及消融。短时突触与长期权重分开；连续发射不是生物脉冲。接收端竞争不能让发送者读取目标瞬时状态，不能抹掉实际到达证据或撤销已发生的传输消耗。膜电位、脉冲及生长迹须有各自语义。

原核冻结样例、既有 V3 测试、Python/Rust 一致性、分段／暂停／恢复、截止到达与死亡、逐算子关闭、错误定义和状态拒绝都须验证。模型包保留在途消息和历史。新机制不能通过默认隐藏回灌改善答案。

参考依据：[Tsodyks–Markram 1997（需核对勘误）](https://pmc.ncbi.nlm.nih.gov/articles/PMC19580/)、[Markram 等 1998](https://pubmed.ncbi.nlm.nih.gov/9560274/)、[Brian2 的短时突触模型](https://brian2.readthedocs.io/en/stable/examples/frompapers.Tsodyks_Uziel_Markram_2000.html)、[LIF](https://neuronaldynamics.epfl.ch/online/Ch1.S3.html)、[Bi–Poo 1998](https://pubmed.ncbi.nlm.nih.gov/9852584/)、[线性 Transformer 与快权重](https://proceedings.mlr.press/v139/schlag21a.html)。文献示例里的随机连线、用于可见爆发的背景电流调整不自动成为 ThreeMind 假设。

## 资源与界面

先原语与无语义控制，再做保持、干扰、反转、顺序及简单环境适应；关系组合和扩规模由证据决定。连续核主要判据为时序收敛结束强度排序，保留原始证据；膜电位核须明确自己的排序量。

默认单 CPU 作业、目标内存 ≤4 GiB，GPU 可选且目标显存 ≤2 GiB，新增研究证据 ≤4 GiB；另监控 E 盘构建缓存。实验沿用账户额度约定，不自动扩样。资源停止不冒充死亡。现有数据不清理、不扫描和自动升级。

创建时内核和标记模式可见，基础／高级／JSON 同源。图形、聊天、媒体、器官行为保持；宽屏突出当前对象，窄屏降低同时显示量但不丢功能。菜单、反馈及保存流程实测，构建成功不等于交互验收。
