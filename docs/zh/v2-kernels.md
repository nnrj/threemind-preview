# 多内核、本地 Transformer 与独立部署

## 2026-11-11新增：5.3及保真5.2后端

版本登记现包含独立5.3 Python/Rust和保真5.2 Rust。全局默认仍/3；下方较早的七类概述保留，新增版本、可用构建及实验结果见[5.3交付说明](v2-kernel53.md)。当前运行服务未在本次自动重启。

[English](../en/v2-kernels.md) · [实施与验收](plans/multi-kernel-implementation.md) · [增强原则及原文](kernel-evolution-principles.md)

## 选择意识内核

在「内核与对照工具」查看七类内核，或在「新建意识」第一层选择。新建默认仍采用活动调节保持的 `continuous-memory/3`；新增局部事件 `/4` 可显式选择，原始基线和旧研究版本保留。普通意识依然默认无限时长，标记模式同样位于第一层。内核身份在创建后固定；现有意识不会自动升级或转成其他内核。

| 选择 | 保留或新增什么 | 应观察什么 |
| --- | --- | --- |
| `threemind.causal/9` | 保留 V3 恢复后的动力学、原假设和 `state/6` | 原始激活、时序收敛、支持、稳定度和原有账本 |
| `threemind.continuous/1` | 在原机制上增加短时突触资源、快迹、接收端局部上下文；三个算子分别消融 | 原激活指标，以及新算子的资源、迹和分配记录 |
| `threemind.continuous-memory/1` | 连续候选加上独立的耗竭、易化与连接巩固研究开关 | 各机制独立及组合的短期与长期影响 |
| `threemind.continuous-memory/2` | 保留 memory/1，增加按真实延迟联想触达结算的局部新颖性；立即计算仍可选 | 实际再入、出生增益及完整时序；见[校准说明](v2-memory-calibration.md) |
| `threemind.continuous-memory/3`（新建默认） | 活动调节连接/支持度半衰期；自动回收，强刺激可恢复疲劳；休眠与复活默认关闭 | 结构保持、回收和成本；[公式与参数](plans/memory-retention-v3.md)，[基础验证](../../lab/explorations/2026-10-08-retention-kernel/report.zh.md) |
| `threemind.lif/1` | 独立膜电位、电流、脉冲和局部时序学习；不冒充原核公式 | 原始 mV、nA、脉冲时间；图形使用有明确公式的去极化投影 |
| `threemind.continuous-memory/4`（研究选项） | 对象局部衰减、传播/失效事件；统一接收，局部资源场及显式对照 | [执行与配置约定](local-events-v4.md)；保持收益单独校准，未自动升级旧个体 |

continuous/1 候选全部关闭其三个新算子时，以冻结的原核行为样例验证等价。启用候选不意味着已证明比原核更接近 AGI。膜电位候选的抑制、遗忘、结构保留及生命判据都有明确差别，见[连续候选规范](plans/candidate-mechanisms.md)和[LIF 规范](plans/lif-candidate.md)。不能只凭同名「激活」列混合不同物理量。

基础／高级／JSON 共用配置。切换到不同物理模型时会重置内核参数；连续候选与原核之间保留共有参数。高级项按机制分组，可查看单位、默认值、关闭方式和创建后只读项。性能档位不会改变内核科学参数。宽屏保留分组侧栏，窄屏用带文字的导航菜单；原聊天式刺激、被动读出、时序读出及媒体和器官入口保留。

LIF 的「动力学」页直接提供膜电位、电流、累计发放、实际发放时间及节点的分页查询和 JSON 导出。`record_spikes` 默认开启，仅影响记录；关闭不会改变发放或塑性。原来的 100 ms 显示／读出采样可能错过短脉冲，发放事件独立于它记录。单意识约 4 MiB 脉冲缓冲就提前提交；共同培养、单次种群推进的脉冲缓冲若超过 64 MiB，会明确失败并要求缩小规模或调整记录协议，不能静默丢弃事件。

## 本地小型 Transformer

它是可选的**外部研究工具**。Core 不导入 PyTorch，不需要联网、预训练模型、CUDA 或此工具才能运行。

「内核与对照工具 → 本地 Transformer」提供：

1. 训练序列：每行一条完整的整数类别序列，例如 `1 2 3`、`4 5 6`。数字是该工具词表中的类别编号，不是 ThreeMind 的节点身份。此入口不替换现有文本感官或 NFKC 映射。
2. 可选独立检验集、词表、层数、宽度、训练步数与实际用时上限。检验集不能含与训练完全相同的序列，但去掉精确重复并不能证明没有更隐蔽的数据泄漏。
3. 模型训练完成后，查询下一事件的**完整概率分布**。页面列出前 16 项，导出包含全部项；不生成自然语言答案，不把高概率项写回 Core。
4. 训练协议、语料哈希、损失、准确率、资源消耗和模型哈希进入当前项目证据。原始数值模型采用 JSON 清单＋NumPy 数组 ZIP（`.tmt`），不使用可执行的 pickle。它是 Transformer 模型文件，与意识 `.tmind` 模型严格分开。
5. 如需回灌，展开「可选：作为外部刺激接入」，选择接收意识、起始通道和强度，再点击发送。每个词表槽位映射到声明的连续通道；完整概率不做语义筛选。该输入经正常总线预算和来源策略，记录外部模型、请求、映射与强度。发送后不能把观察到的能力全归于 ThreeMind 内核。

模型采用因果掩码自注意力、位置向量、前馈层、残差和层归一化，以下一事件交叉熵训练。依据为 [Attention Is All You Need](https://arxiv.org/abs/1706.03762)；实现使用 [PyTorch TransformerEncoder](https://docs.pytorch.org/docs/2.14/generated/torch.nn.TransformerEncoder.html)。这类端到端反向传播是**对照工具自己的学习方法**，没有混入 ThreeMind 的局部更新规则。

当前上限：词表 4096，序列上下文 128，宽度 128，3 层、8 头；整个训练／检验语料不超过 20 万类别项。默认 2 个 CPU 线程、2 GiB 进程内存预算、200 步／30 秒，最多 5000 步／300 秒／4 GiB。内存与时间在步骤之间检查，因此不是操作系统硬隔离；一次张量运算可能跨过预算检查点。Lab 子进程另有超时保护，不保证超时中断时仍能导出尚未序列化的模型。训练正常遇到预算时保存已完成部分并明确报告原因。

安装和 CLI（示例使用当前恢复的独立 Python 环境，不需要 Anaconda）：

```powershell
$py = '.\.work\kernel-venv\Scripts\python.exe'
& $py -m pip install torch --index-url https://download.pytorch.org/whl/cpu
& $py -m threemind_transformer.cli train protocol.json --output comparator.tmt
& $py -m threemind_transformer.cli predict comparator.tmt --tokens '[1,2]'
& $py -m threemind_transformer.cli contract
```

`protocol.json` 最小例子：

```json
{"architecture":{"vocabulary":8,"context":8,"width":16,"heads":2,"layers":1,"seed":17},"sequences":[[1,2,3],[4,5,6]],"steps":30,"wall_seconds":30,"threads":2,"memory_mib":2048}
```

输出路径已存在时拒绝覆盖。Lab 使用现有数据库任务租约、项目权限和证据存储，不新增数据库或 MQ。未安装 PyTorch 的 worker 不会领取这类任务；任务等待可用 worker，在系统任务中查看阻塞原因。

## 可选远程工具，而非分布式大脑

独立概率服务与客户端可用：

```powershell
& $py -m threemind_transformer.cli serve comparator.tmt --host 127.0.0.1 --port 8997
& $py -m threemind_transformer.cli remote http://127.0.0.1:8997/probabilities --tokens '[1,2]' --model-hash <完整SHA256>
```

非回环访问必须显式 `--allow-remote`；非回环服务必须配置 `THREEMIND_TRANSFORMER_TOKEN`。客户端从同名环境变量读取令牌，验证模型哈希和请求哈希，限制超时和响应体。远程原始文本、凭据不会被偷偷代入请求；此协议只发送已声明的类别编号。公网部署应在 TLS 反向代理后运行。GUI 首版只管理本地任务；远程调用用 CLI／Python API，其分布式协调不进入 Core。

`probability_frame` 只准备帧和外部来源元数据，不自动递送。独立设备可把该帧显式提交给自己的 InputBus；Lab 接口为 `POST /api/v2/projects/{project}/transformer/predictions/{job}/inputs`，必须提供接收意识、独立请求编号、完整通道表和强度。不能把一次未知是否成功的发送无条件重试为新请求编号。

## 独立 Rust 程序与声明式构造

「导出定义」保存可信算子顺序、身份和初始参数，不包含训练后的意识。训练后完整意识使用既有模型导出。定义不执行任意脚本；增加新的物理机制需要实现、验证并注册新版本。

```powershell
& $py -m threemind_kernels.cli validate definition.json
& $py -m threemind_kernels.cli build definition.json --output .work/device-build
.\.work\device-build\threemind-runtime.exe --inspect-definition
```

构建需要 Rust、C++ 链接工具及已缓存依赖，默认离线。首次缺少依赖时可显式 `--allow-download`。产物带固定构造定义、源码／二进制哈希清单，可复制到相同平台设备，运行时不需要 Python、数据库或网页。不同平台须在对应工具链构建；没有声称一份 Windows 程序可直接运行于所有机器人。

固定的是创建规则与内核身份，**网络仍然可塑**。独立程序可直接读取模型、接受刺激、演化和保存更新后的状态，也可选 SQLite。恢复时不能伪装成另一内核，且不会用默认参数覆盖已保存的配置、快变量和在途消息。现有 `threemind-runtime --help` 与[部署文档](v2-operations.md)说明完整命令。

## 更新当前工作站

停止旧工作站与 worker，重建原生扩展和前端后，用专用迁移账号执行 `python -m threemind_lab.cli migrate`。本阶段 schema 51 只更新任务能力匹配，不迁移旧意识或扫描 `data/`。业务库应用情况见实施记录，不能把独立测试库验收等同于业务库已更新。

```powershell
.\scripts\start-lab.ps1 -Python .\.work\kernel-venv\Scripts\python.exe
```

普通系统 Python 3.13 加隔离 venv 已可用；无需重新安装 Anaconda。2026-09-30 已更新 `.work/kernel-venv` 中的 Runtime、Lab 与原生扩展。旧 `.venv` 仍指向已卸载的 Anaconda，本机请使用上面带 `-Python` 的启动命令。`.work/kernel-venv` 是本机恢复环境，不应复制给其他设备。标准新安装仍按[部署文档](v2-operations.md)创建 `.venv`。
