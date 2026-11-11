# 内核选择、配置模板与新建层次修复交付记录

[English](../../en/plans/kernel-creation-hierarchy-delivery.md) · [原计划及追加实施记录](platform-hierarchy-navigation-workbench.md) · [工作台用法](../platform-workbench.md) · [此前平台交付](platform-hierarchy-delivery.md)

2026-10-11。用户指出内核名称隐藏版本、旧版及 `/4` 缺席，参数来源又高于内核。修复恢复实际版本目录，以“内核 → 同核模板 → 参数”组织同一页面。下文分别记录实现、隔离工程验收及真实库迁移；不将临时工程测试当作正式科研实验。

## 实现范围

| 实际内核身份 | 数量 | 可用后端 |
|---|---:|---|
| `threemind.causal/1`～`threemind.causal/9` | 9 | Python reference、Rust native |
| `threemind.continuous/1` | 1 | Python reference、Rust native |
| `threemind.continuous-memory/1`～`threemind.continuous-memory/4` | 4 | Python reference、Rust native |
| `threemind.lif/1` | 1 | Python reference、Rust native |
| `unified-associative` | 1 | Python reference |

合计 16 个实际身份，默认仍为 `threemind.continuous-memory/3`。显示名包含版本，简述与后端能力单独显示。所有正式旧版可新建；不把研究 preset 当成内核。按用户讨论后的决定，本期没有按版本号强拆连续家族共享 Rust 实现；兼容的代码继续复用，不兼容历史路径隔离。

系统默认与模板按所选内核获取。一个内核可保存多份具备修订的模板；当前参数、已有实例保存参数均可成为模板。采用模板后可以继续修改同核参数；配置来源用于追溯起点，不能替代最终实际配置。模板后续修订不能换核，已有历史跨核修订不重写。实例转模板只读配置及元数据版本，清除 `study_id`、`condition`、`block_seed`，不触碰检查点、运行任务或模拟状态。

后端选择是宿主元数据 `execution.backend`，保存在 `spec` 之外。显式选择不支持的后端报错；默认选择按宿主配置和内核声明能力解析。既有记录的空后端元数据保留，不补造其历史运行来源。调度匹配内核与后端；Python 历史工作进程可独立运行。

## 历史实现与完整原包

`unified-associative` 从 `97d8592` 的原 Python 实现恢复，保留环境输入 epoch 与 Core tick 的区别及原感官规则。其 V1/V2/V3 内置模板来自历史界面 `0c5e64a114fa33ca18c7106724388a8b3d0e352d`：标签特征、匿名感官、匿名空间三种配置。它们属于同一个内核；`legacy-labeled` 不被现代匿名或逐字编码静默替换。

完整包保留原 package、随机状态和宿主待递送输入。检查点使用显式 `threemind.unified-state-json/1` 标识的 `state.json` 完整容器，不通过现代 Node/Arrow 字段转换，也不采用现代增量补丁。节点／连接的 JSON 查询投影单独保存；原 64 位感受器通道和未知历史字段保留。现代内核的原容器和恢复路径不因此改写。

历史 causal `/1`～`/7` 的结构出生沿用 `5a5f0dd` 的原 `birth/1`，`/8` 使用 `304ef25` 的原规则，不挪用现代出生规则。unified 尚无可确认的对应结构出生规则时明确拒绝，不臆造规则；空白新建、完整恢复及原样分叉仍可用。此限制不能解读为拒绝旧内核新建。

## 共用接口

| 操作 | 接口／入口 |
|---|---|
| 内核目录 | 现有内核目录，返回实际身份、说明、后端与版本参数 |
| 所选内核的新建默认 | `GET /api/v2/configuration/defaults?kernel_id=...` |
| 同核已存／内置模板 | `GET /api/v2/configuration/templates?kernel_id=...`，分别返回 `items`、`builtins` |
| 保存参数模板 | `POST /api/v2/configuration/templates` |
| 实例参数转模板 | `POST /api/v2/projects/{project}/runs/{run_id}/configuration-template`，接受名称和可选 `expected_metadata_revision` |
| Agent／CLI 操作目录 | `configuration.template_from_run`；共用上述保存服务及回执 |

新建与模板来源必须同核，过时修订、冲突和不支持的后端明确报错。同核参数修改不被禁止。实例转模板要求 `system.write` 及源实例 `runs.read`，不额外要求暂停、配置或刺激权；幂等回执重试仍核验当前权限。

## 显式迁移与真实库见证

本部署已确认无运行服务或任务后，建立结构及受影响配置的小快照，并显式执行 schema 67 → 68。新增宿主执行元数据、模板来源和独立历史图查询投影，未修改科学状态。快照位于忽略目录 `.work/kernel-hierarchy-20261011/`；结构快照 906,353 字节，配置快照 7,518 字节，不新增一次全量原件副本。

| 科学对象 | 前后数量 | 前后哈希 |
|---|---:|---|
| 意识／运行 | 20,581 | 一致 |
| 检查点 | 24,821 | 一致 |
| 正式实验索引 | 84 | 一致 |
| 报告修订 | 629 | 一致 |
| 笔记修订 | 719 | 一致 |
| 通知配置修订 | 23 | 一致 |
| 通知 | 16 | 一致 |
| AI 调用 | 41 | 一致 |

新增 `legacy_graph_rows` 为 0 行，既有 `runs.execution` 均为 `{}`；应用账号的新表 CRUD 授权已核验。迁移后 `doctor` 通过。此前 65 → 67 的交付证据保留，不与本轮合并或覆写。

其他部署须显式执行，启动应用不偷偷升级旧库：

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli migrate
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli doctor
```

若独立部署 Python 历史执行进程：`python -m threemind_lab.cli worker --backend reference --task-family kernel-reference`。这些是宿主操作，不更改内核时钟或动力学。

## 验收证据与限度

以下是不同范围的实测批次，不重复相加为一个总数：

| 范围 | 结果 |
|---|---|
| 历史 Lab 双后端全链与 unified 原包编码 | 17 通过，109.9 秒 |
| 旧版及现代内核回归 | 270 通过 |
| 历史出生完整回归 | 60 通过，含新增 16 项出生及 1 项缺规则拒绝；现代出生另 2 项通过 |
| Rust 回归 | 4 通过 |
| 调度、操作权限 | 14 项及 3 项通过 |
| UI 回归 | 40/40 通过；字符串／执行复验 3 项通过；构建成功 |
| 观察与实际导出／分叉 | 观察 3 项通过；实际三种格式导出及原样分叉 1 项通过；UI 补充 5 项通过并再次构建成功 |
| 现代 artifact／检查点／继承／Runtime 互通 | 36 通过 |
| 模板服务专项 | 5 通过；操作目录专项 3 通过 |
| unified 编码、检查点流水线、原件校验专项 | 15 通过 |

日常虚拟环境已安装离线 release wheel，15 个 native 内核及 unified reference 的 capture 身份检查通过。上述验证分别证明版本路由、参数来源、权限、保存／恢复及兼容路径；不证明新内核优于旧版，也不代替完整形色教学。未开展新的正式训练或参数调优。无法确认的历史规则明确拒绝，不能以现代近似实现冒充历史恢复。

收尾补充：study 双后端来源 2 项通过，父体与子体均保存实际执行后端；后续继续不回落为宿主默认。此修复只补宿主来源，不改变成对实验的模拟输入或动力学。

## 2026-10-11 同日更正：/4 实际启动与观察契约

用户在 `意识测试_2026101101` 点击启动得到 `KeyError: 'parameters'`，授权修复该测试意识。核查时个体仍为模拟时间0、科学修订0，无检查点；失败来自宿主能量端点读取旧版观测格式，而 /4 只输出原始能量账本。此前空白创建／capture 验收没有覆盖此实际 Lab 启动路径，原验收不能解释为这一路径已经通过。

本次只修只读观察契约：Python／Rust 的 /4 能量指标补齐真实配置与结算时间；保存边界正确汇总局部区域及节点储备，原 checkpoint 账本不增加这些字段。能量递送回执报告当次实际接收量，不以累计值相减推算；未知启用状态的历史观测保留缺失值。空间观察使用 /4 已有时间字段；空间及当前／历史节点分页包含合法ID0，显式后续游标仍保持原义。局部能量面板明确“总储备”和“单区域容量”，不把它误说成全局容量。

没有修改学习、遗忘、能量分配、求解时钟、内核身份或默认参数；没有迁移数据库，schema仍68。用户测试个体仅恢复宿主状态为 `paused＋revision=0`（UI“未启动”），保留原失败任务及恢复审计事件，未创建 Core 或递送刺激。忽略目录 `.work/startup-local4-20261011/` 保存初始行、回执及工程证据，不进入Git。

新增20项验收覆盖两后端、两能量模式、能量开关、与用户相同的实时MuJoCo配置、启动／暂停／完整宿主恢复、能量原件保真、CSV、空间及节点0分页。最终已安装原生扩展和前端构建配套核验。一次扩大回归为89通过、1失败；失败项是既存 /3 能量耗尽后零响应节点缺回收期限，纯内存在两后端可复现，相关 /3 源码与修复前提交相同。它列入T12，不放宽校验、不改写旧状态来宣称通过。以上工程测试不作为新的正式研究实验或学习增益证据。

界面完整批次39项通过，包含空间节点0、只读切换及原工作台／配置／授权回归；前端构建通过。修改后的Python文件Ruff、Rust单文件格式检查通过；全工作区格式检查仍有本轮之前的历史代码格式差异，不借本修复重排它们。
