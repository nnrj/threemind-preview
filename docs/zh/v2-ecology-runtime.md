# 独立生态训练器、整组恢复与交换包

`threemind-ecology` 是不依赖 Lab、PostgreSQL、账号或浏览器的生态训练入口。它复用工作站的世界求解、生态规则、身体状态感官、出生、Core、输入总线和读出宿主。模型在内存中持续塑形；只有明确指定存储或导出参数时才保存数据。

## 使用

安装当前项目及世界适配器依赖后，执行 `threemind-ecology`，或使用等价的 `python -m threemind_runtime.ecology_cli`。本仓库 Windows 环境可以用 `.venv/Scripts/python.exe` 替换 `python`。

```powershell
python -m threemind_runtime.ecology_cli --write-example ecology.json
python -m threemind_runtime.ecology_cli --protocol ecology.json --store population.sqlite --until-us 10000000 --clock unbounded
python -m threemind_runtime.ecology_cli --store population.sqlite --resume --until-us 20000000 --clock unbounded --export population.zip
python -m threemind_runtime.ecology_cli --bundle population.zip --until-us 30000000 --clock unbounded --export continued.zip
```

示例文件包含完整默认协议，可编辑世界、身体、生态规则、三个分别启用的身体状态感官、Core 参数和 Runtime 工具。`--until-us` 是全局模拟时间的绝对终点，不是再运行多少微秒。恢复到 20 秒后，若要再运行 10 秒，应指定 30000000。

默认 `--clock realtime` 用宿主单调时钟限制模拟推进；`scaled --speed 10` 以十倍目标速度推进；`unbounded` 不等待墙钟。硬件不足时计算会落后，不跳过动力学或刺激来追赶。改变宿主速度不修改冻结协议或模拟时间戳。

没有 `--store` 时不要求任何数据库。`--store` 使用一个本地 SQLite 文件，`--instance` 可选择其中的种群名字，默认 `ecology`。`--resume` 才会继续已有种群；使用相同名字新建不会覆盖它。

## 继承脑与继续种群

单个 `.tmind` 或等价 JSON 脑模型通过 `--founder` 作为父本，创建经过 `threemind.birth/1` 重置的新生个体，不继续父本当前活动，也不携带父本所在环境。

```powershell
python -m threemind_runtime.ecology_cli --write-example inherited.json --founder trained.tmind
python -m threemind_runtime.ecology_cli --protocol inherited.json --founder trained.tmind --store inherited.sqlite --until-us 10000000 --clock unbounded
```

第一条命令保留模型携带的感官身份与完整 Runtime profile，并将对应工具配置带入协议。随后可配置新的环境。若使用不匹配的感官 profile，创建会拒绝，而不会悄悄替换已学习的接线。导入父本时其 Core 参数来自模型；协议的 `core_config` 只用于空白创始脑。

`--bundle` 读取的是 `threemind.population-bundle/1` 整组交换包。它保留全部模型、全局及个体时间、世界积分状态、资源账本、谱系、待递送刺激和读出工具状态，按同一个固定恢复点继续。包括死亡个体，不只包含仍存活的个体。

单脑 `.tmind` 仍是脑模型本体；整组包是多个脑和实验环境的容器，没有另造一种脑模型格式。当前 Lab 导出的 `threemind.ecology-evidence/1` 是研究证据包，协议还包含 Lab 阶段、命令与遥测，不能冒充这个可移植恢复包。CLI 会明确拒绝混用。可取其中的脑模型进行新出生，不能声称这等于原种群的精确恢复。

## 协议与宿主边界

独立协议为 `threemind.ecology-job/1`，严格拒绝未知字段、重复 JSON 键、不合法类型、端口冲突和不一致的 profile。整个协议在首次持久化时固定，继续已有种群不能换入另一份协议。参考和原生 Core 可明确选择，但恢复验证结果不外推为任意硬件、物理求解器版本都能逐位一致。

此入口覆盖 Runtime 的输入总线、来源策略、身体过滤、内感受、能量供应、输出器官、被动读出及记录参数。不包含 Lab 的账号、任务队列、远程命令、阶段调度或宿主遥测。CLI 不是对 Lab 协议做静默删减的转换器。需要这些能力时使用工作站，或通过 Runtime 工厂与回调接入明确的宿主实现。

## 数据保存与证据

本地存储复用 SQLite WAL 和完整同步模式。一次事务提交协议、世界、资源、全部脑哈希映射以及本次新增的原始事件；脑状态按哈希去重，并以 1 MiB 块保存。修订号检查拒绝两个写入者覆盖同一个种群。读取会校验协议、清单、块大小与模型哈希；损坏或缺失会报错，不能用部分状态继续。

`--checkpoint-us` 配置周期，默认 1000000。出生后在新生脑第一次获得经验前保存；开启 `participant.trace` 后还会保存每个实际数值边界，并要求配置 `--store`。待提交证据达到 8 MiB 时也触发提交，但单个采样本身仍可能大于此值。这是提交触发值，不是严格进程内存上限。

死亡且已脱离身体的脑在成功提交后释放可变实例，保留可验证的存储引用。原始模型、弱活动记录和工具状态不按语义删减。历史恢复点与事件不会自动清理，长期记录会持续占用磁盘。

可选 `--evidence observation.jsonl` 输出本次进程的完整观察回调事件，首行记录协议、起点和后端；它是明确请求的导出流，不是运行所必需的模型文件。恢复时不会把之前进程的事件伪装成本次事件。SQLite 内保存的是全部已提交调用的证据，可通过 `PopulationStore.evidence(instance, revision)` 顺序读取。

整组交换包保存完整恢复状态，不包含所有历史恢复点、输入和读出的证据流。需要完整实验历史时保留数据库或另行导出事件。证据文件和最终包均拒绝覆盖已有文件。

为避免导入时失控分配，当前单脑及本地单脑状态上限 512 MiB、整组包展开文件合计上限 2 GiB、种群元数据上限 64 MiB、协议上限 8 MiB。超过上限会明确失败，不丢弃个体来适配。这些是当前交换实现的限制，不是 Core 理论规模限制；大型分块流式交换仍需后续实现。

SQLite 在这里属于独立 Runtime 的可选本地宿主，不是多用户 Lab 的第二种数据库后端。二者不自动双写、不自动同步，也没有要求本地训练依赖云端。工作站数据继续以 PostgreSQL 为唯一事实来源，模型与交换包用于用户明确的导入导出。

## 验证范围

自动验证覆盖整组事务回滚、并发修订冲突、冻结协议、模型损坏检测、部分物理区间恢复、SQLite／交换包／不中断运行的最终状态一致、完整出生证据、非默认感官 profile 继承和数值边界记录。独立 CLI 子进程同时断言没有导入任何 `threemind_lab` 模块。工程验收详情见[可移植种群验证](../benchmarks/2026-09-07-ecology-portable-validation.json)。

这些验证不构成意识存在或演化效果的结论，也不代表分布式生态计算已经实现。研究界面与生态时间、出生公式见[生态训练说明](v2-ecology.md)。
