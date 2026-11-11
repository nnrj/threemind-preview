# 研究操作、实验快照与计算设备

[English](../en/v2-research-tools.md) · [实施计划](plans/research-tooling-and-candidate-experiments.md)

## 界面入口

- **设置 → 计算工具与 Agent 接口**：工作进程实际能力、新建 Transformer 任务的设备和显存默认值、操作协议及 MCP 配置。已有意识和实验参数不随工具偏好改变。
- **意识详情 → 研究操作 → 实验计划 → 设计阶段重复实验**：阶段内顺序执行步骤，再完整重复指定次数。图形与 JSON 共用 `research-plan/3`；匿名帧经过普通输入总线。旧 `/2` 计划保留原协议与哈希。
- **模型与证据 → 实验快照**：暂停意识和计划后保存，可附带自己的笔记、研究报告及已完成工具制品。查看器默认展示时序读出。导入只建立档案；明确恢复才创建暂停的新意识，不自动运行。
- **设置 → 实验存储检查**：只读检查引用和占用，包括上传包与恢复谱系。不展开旧大数据、媒体或正文，不自动清理。未发现引用不等于已证明安全，实际清理仍需模型档案的完整预览和用户确认。

WebGL2 不可用或上下文丢失时，画面回退 Canvas 2D，复用显示采样、布局、节点选择和 PNG 导出；可重试 WebGL。回退期间没有三维视角，内核计算不变。显示预算仍可设置，软件绘图不保证大型网络与 GPU 同速。

报告预览支持当前项目的笔记附图和证据制品下载链接。不会自动请求任意远端图片或其他项目的私有附图；公开分享也不继承私有资源访问。当前 Markdown 说明里的附图只在平台预览，HTML/Word/PDF 导出仍以原生数据图表为准，不嵌入这类附图；本轮概览 PNG 同时保存在原始证据包和源码文档中。

## CLI、Agent 和 MCP

目录来自运行中服务的真实 OpenAPI；UI、CLI、MCP 共享权限、修订及业务校验。Core 不依赖可选 MCP SDK，也不调用 LLM。

```powershell
$py = '.\.work\kernel-venv\Scripts\python.exe'
& $py -m threemind_lab.cli ops list
& $py -m threemind_lab.cli ops show bundle.export
& $py -m threemind_lab.cli ops preflight bundle.export --arguments request.json --request-id <UUID>
& $py -m threemind_lab.cli ops call bundle.export --arguments request.json --request-id <同一UUID>
& $py -m threemind_lab.cli ops receipt --project <项目UUID> --request-id <同一UUID>
& $py -m threemind_lab.mcp_server
```

`request.json` 包含 `path`、`query`、`body`，确切字段以 `ops show` 为准。预检只验证 schema，不保证当前权限、修订或预算；`experiment` 是 `ops` 别名。写操作复用 `X-ThreeMind-Request-ID` 可重放已完成回执。**业务提交与通用回执不是同一事务**，崩溃间隙可能留下 pending/unknown；此时核对任务/对象，不换新编号盲目重试。错误响应也属于该编号，纠正参数需新编号。推进与阶段命令另有持久化绝对目标、游标和步骤回执，不重复已完成教学。

MCP 提供六个工具：目录、协议、预检、调用、回执、受限实验包文件交换。清理和账号/凭据管理保留人类操作流程。宿主提供 `THREEMIND_API_URL`、`THREEMIND_API_USERNAME`、`THREEMIND_API_PASSWORD`；不把凭据写进模型生成的参数。文件交换需宿主设置 `THREEMIND_MCP_TRANSFER_DIR`，只能在该目录内交换校验通过的包，默认不暴露任意文件。

## 实验包

`.tmind` 保存 Core 数值状态，`.tmt` 保存独立 Transformer 数值模型，`.tmexperiment` 保存实验上下文和证据。它们均不成为日常运行中反复改写的模型文件。

`threemind.experiment-bundle/1` 使用 ZIP64、4 MiB 内容寻址块、SHA-256 与压缩。包含内核、运行时、在途输入、感官/读出、随机状态、原始媒体、阶段协议与重复游标；可选笔记/报告包括版本和来源引用。上限为压缩 8 GiB、逻辑展开 20 GiB、4096 条目、32768 块；临时盘保留 15 GiB。`THREEMIND_SCRATCH_DIR` 可替代默认 `.work/bundle-temp`。

导入验证路径、大小、摘要，不解压任意路径或执行代码。恢复再次检查状态、实现指纹、依赖、协议及待执行命令，不支持的版本只读。恢复保留数值状态和时钟，重建实验/载体身份与项目归属；不重编码通道或原始载荷。现实遥测条件变化需明确确认；不打包外设凭据或自动重连。死亡意识不能通过恢复复活。

一个包对应一个已提交意识边界。种群、生态、冻结对照及评估中的个体可导出证据，但不当作完整协调器恢复。未提交研究操作、活动采集、待处理实时设备块或不支持的命令阻止续行。Transformer 只支持已完成任务制品，不支持训练中途优化器续接。实现指纹严格绑定代码与依赖，因此工具升级也可能使旧包只能查看；不静默近似恢复。大包预览当前先在临时盘重建并校验整包，速度与包大小有关。

```powershell
& $py -m threemind_lab.cli bundle download --project <UUID> --bundle <UUID> --file experiment.tmexperiment
& $py -m threemind_lab.cli bundle upload --project <UUID> --file experiment.tmexperiment --request-id <UUID>
& $py -m threemind_lab.cli bundle copy --project <源UUID> --bundle <UUID> --target-url https://your-service.example --target-project <目标UUID> --request-id <UUID>
```

文件不覆盖已有证据；上传复用校验通过的分块。浏览器同文件重试复用本地请求号；禁用持久存储时，跨重载续传需 CLI 的稳定请求号。对等复制也只建立只读档案。

可选 OCI 使用单独的 [ORAS CLI](https://oras.land/docs/commands/oras_push/) 和本地 `oras login` 凭据：

```powershell
& $py -m threemind_lab.cli bundle push-oci --file experiment.tmexperiment --reference registry.example/research/run:trial-1
& $py -m threemind_lab.cli bundle pull-oci --file received.tmexperiment --reference registry.example/research/run@sha256:<摘要>
```

传输的是单个数据层，不执行容器。拉取核对 OCI 层和包内摘要；推送先冻结副本再核对远端清单。目前已测试本地包、模拟 registry 协议与有界子进程，真实 registry 往返尚未验收。

## 设备策略与验证边界

协议默认 `cpu`，保留旧脚本行为；界面新任务默认 `auto`。自动 CUDA 要求三次含传输成本的代表性配对测量均至少加速 20%，且显存允许。手动 `cuda` 覆盖速度建议，资源不足或识别到 GPU 故障仍记录并回退。GPU 中途失败时，在剩余预算内从相同初始条件开启一次全新 CPU 尝试，保留两次证据，不拼接轨迹。

默认显存预算 2048 MiB、预留 512 MiB，一次一个 GPU 工具任务；FP32、禁用 TF32。预算属于分配与监测约束，不是操作系统硬隔离。实际设备、Torch/CUDA/驱动、用时、失败与回退写入证据。可选工具与 Core 分进程；三个意识内核继续用 CPU。

```powershell
& $py -m threemind_lab.cli compute
& $py -m threemind_transformer.cli predict model.tmt --tokens '[1,2]' --compute-device auto --gpu-memory-mib 2048
```

概率服务保留原七字段协议；`/compute` 单独提供最近一次执行设备证据。本机当前 CPU 版 Torch，真实 GPU 的速度、峰值显存与数值一致性待安装 CUDA 环境后验证。

数据、临时目录、模型和包默认不进 Git。`python scripts/check-git-data.py` 检查暂存文件类型及单文件 10 MiB 上限，只读暂存区，不扫旧数据、不改历史。源码、方案、汇总和证据定位可提交；大证据保存在数据库或校验过的包中。
