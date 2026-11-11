# ThreeMind 2 使用与部署

2026-10-11 当前补充：本地库已显式升级至67，平台默认登录；首次启动按页面为原local身份设置密码。默认首页为意识工作台，系统设置不再选择项目。退出登录默认继续运行，可明确选择独立实例暂停后退出。原命令不变，CLI／Agent采用一次初始化的受保护配置。[工作台说明](platform-workbench.md) · [AI访问](platform-access.md) · [验收](plans/platform-hierarchy-delivery.md)。下面较早版本记录保留。

[独立 Runtime 与部署边界](v2-independent-runtime.md) · [时序活动读出](v2-activity-readout.md) · [记忆机制校准内核](v2-memory-calibration.md)
ThreeMind 2 分为无存储依赖的 Core、设备用 Runtime，以及训练研究用 Lab。Lab 的本地与在线模式共用同一套程序和 PostgreSQL schema。本地模式不需要云端账号或云端存储。

## 当前工作站

2026-09-30：Runtime 与 Lab 已更新至 **2.1.0**，原生扩展和前端已重建，`doctor` 确认数据库连接和原生后端可用。新建默认内核为 `continuous-memory/2`；原有四类内核及已存意识不自动转换。新增时序活动读出和机制校准详情见[实施验收](plans/mechanism-calibration-and-readouts.md)。本轮没有清理或转换旧研究数据。

2026-09-10 历史记录：当时升级至 schema 50，新增时序报告来源，Core 为 causal/9、state/6。后续多内核阶段的记录见[多内核说明](v2-kernels.md)。聊天和时序工具的使用见[说明](v2-temporal-research.md)，手动备份与整理见[指引](plans/backup-and-cleanup.md)。下文旧版本记录不代表当前默认内核。

升级后的工作站需整体使用新版 API／worker 与已构建 UI；不要混用旧 worker。本轮验收服务使用独立测试库，正式工作站保持停止状态，按下方命令即可启动。

此机器的 ThreeMind 已配置为连接 `127.0.0.1:5433/threemind`。`postgres` 是初始化时连接的管理数据库，研究数据写入专用的 `threemind`，应用账号是非所有者 `threemind_app`。连接信息留在不受 Git 管理的根目录 `.env`；不要用示例覆盖已配置的文件。

```powershell
.\scripts\start-lab.ps1 -Python .\.work\kernel-venv\Scripts\python.exe
```

打开 <http://127.0.0.1:8877>。此命令启动 API 与本机 worker；前端使用已构建的静态文件。另一个终端可执行健康检查：

```powershell
.\.work\kernel-venv\Scripts\python.exe -m threemind_lab.cli doctor
```

首次使用时创建研究项目，然后新建意识。默认环境是 MuJoCo 平面躯体，其外部力、位置、速度、加速度和约束力构成物理模拟输入；初始核心没有人为构建的认知拓扑。

## 从源码安装新的工作站

### 更换 Python 或卸载 Anaconda 后

虚拟环境绑定创建它的 Python 安装。卸载 Anaconda 后，旧 `.venv` 中即使还留有 `python.exe`，也可能无法启动；这不影响 PostgreSQL 中的实验数据。不需要专门重装 Anaconda，可以用独立 Python 建立新虚拟环境，再按下列流程安装依赖和编译原生扩展。

2026-09-28 开发验证使用独立 Python 3.13 建立了 `.work/kernel-venv`，没有覆盖旧 `.venv`。可显式指定启动解释器：

```powershell
.\scripts\start-lab.ps1 -Python .\.work\kernel-venv\Scripts\python.exe
```

未指定 `-Python` 时仍使用 `.venv\Scripts\python.exe`。不要直接把旧 Python 的 `site-packages` 复制进另一版本，也不要移动已创建的虚拟环境；应在目标路径重建。`.work` 环境是本机忽略目录，其他部署仍按下面的安装步骤创建自己的环境。

### 安装步骤

需要 Python 3.11 或更新版本、Rust stable、Node.js 24 和 PostgreSQL 17。Windows 编译 Rust 原生扩展需要 MSVC C++ Build Tools。依赖安装需要联网，安装完成后的基础研究流程可离线使用。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pip install -e packages/runtime -e packages/transformer -e ".[dev]"
.\.venv\Scripts\python.exe -m maturin develop --release --manifest-path crates/threemind-native/Cargo.toml
```

`maturin develop` 要求当前虚拟环境已激活。PowerShell 不允许执行激活脚本时，可在当前终端设置 `$env:VIRTUAL_ENV=(Resolve-Path .venv).Path`，然后使用上述虚拟环境 Python 路径执行。

```powershell
cd threemind-ui
npm ci
npm run build
cd ..
```

仅在没有 `.env` 的新安装上，将 `.env.example` 复制为 `.env`，填写本机 PostgreSQL 管理账号与端口，再执行：

```powershell
.\.venv\Scripts\python.exe -m threemind_lab.cli setup-local
```

初始化只创建专用数据库和两个专用角色；不会扫描或迁移旧 `data/`。成功后清除 `.env` 中的一次性管理员密码，写入应用和迁移连接配置。以后安装 schema 更新使用 `threemind migrate`，应用服务本身不持有超级用户权限。

增量检查点使用 schema 版本 2。升级已有部署时，先停下旧 worker，执行迁移并更新所有 Lab worker 后再恢复领取任务；旧 worker 不能读取新的行增量格式。标准 `.tmind` 与独立 Runtime 格式不受这次数据库迁移影响。本机的迁移已完成。

## 运行、暂停、继续与导出

| 操作 | 含义 |
| --- | --- |
| 新建运行 | 从空核心或明确导入/继承的状态开始接收刺激 |
| 暂停 | 提交状态，释放运行作业；不等于模型死亡 |
| 继续 | 从数据库完整恢复点继续，保留时间相位及待递送事件 |
| 关闭输入 | 停止该实例接收新刺激，已排队事件仍按时间递送；内部活动归零后可进入死亡状态 |
| 时长结束 | 停止此次实验的计算并提交状态，不宣称意识死亡 |
| 精确分支 | 复制模型状态、队列和可恢复的模拟环境，保留父运行谱系 |
| 先天继承 | 显式出生新实例，保留慢结构，重置活动、抑制、短迹、时钟和队列 |
| 导出最新模型 | 请求 worker 提交一致状态，将导出绑定到该次确认的恢复点 |
| 导出历史版本 | 绑定用户选定的不可变恢复点 |

运行界面的网络来自已提交的数据库版本，底部显示 `rN`；这不是逐个积分步骤的即时神经活动视频。显示刷新率与科研采样率分别设置。未显示全部节点时会标明“部分显示”；模型导出始终读取完整恢复点。

## 独立 Runtime

```powershell
cargo build --release -p threemind-runtime
.\target\release\threemind-runtime.exe --model learned.tmind --input sensory.jsonl --clock unbounded --until-us 1000000 --export continued.tmind
```

生成的原生可执行文件不依赖 Python、PostgreSQL、Lab、网络或账号。默认保留可塑性。文件读写属于 CLI 宿主，Core 没有文件路径接口。输入文件按行包含：

```json
{"time_us":"20000","channels":[[17,0.6],[42,0.2]],"intensity":1.0}
```

通道只是匿名整数，不能将图中位置当作脑区或语义。`--until-us` 是绝对模拟时间。输入已全部装入队列后，可用 `--close-inputs` 声明不再接收新输入。

可选设备恢复库：

```powershell
.\target\release\threemind-runtime.exe --model learned.tmind --store device.sqlite --instance robot-a --clock realtime --until-us 60000000
.\target\release\threemind-runtime.exe --store device.sqlite --instance robot-a --resume --until-us 120000000
```

恢复库保留最近 8 个恢复版本，并用事务和版本检查拒绝多个写入者覆盖同一实例；它不是完整科研历史。原生 Runtime 使用随依赖构建的 SQLite。Python 包也提供 `threemind-runtime` CLI，适用于已有 Python 环境的扩展开发。

## Docker 是可选部署方式

Docker 适合统一 Linux 依赖、团队复现、API/worker 分离和服务器部署；不会让同一计算自动变快。在 Windows 本地研究时，直接使用已有 PostgreSQL 和原生程序更简单，也更方便接入设备。机器人可直接分发 Runtime 二进制，不必安装 Docker。

Compose 用同一个配置管理服务、私有网络和持久卷，并可通过项目名隔离部署；这里采用这一能力组织可选服务器环境。参见 [Docker Compose 官方模型说明](https://docs.docker.com/compose/intro/compose-application-model/)。

```powershell
python scripts/init-compose.py
docker compose --env-file deploy/compose.env -f deploy/compose.yaml up --build -d
docker compose --env-file deploy/compose.env -f deploy/compose.yaml exec api python -m threemind_lab.cli create-admin your-name
```

密码在终端交互输入；配置脚本只创建一次 `deploy/compose.env`，不打印凭据。默认访问 <http://127.0.0.1:8878>，使用在线模式账号登录。Compose 使用独立的 `threemind-v2` 项目和命名卷，数据库不映射到宿主端口，避免与已有数据库容器冲突。

Linux x86-64 镜像和独立部署已通过[应用及故障恢复验收](v2-container-isolation.md)。Windows 使用系统代理时，构建器可能需要当前命令环境中的 `HTTP_PROXY`／`HTTPS_PROXY`；应填写自己已有的可用代理，不要把示例端口或代理凭据提交到仓库。数据库卷需要单独保存；更新代码后重新构建服务镜像，镜像不能替代研究数据备份。

扩大 worker 数量时，先在“管理 → 执行队列与额度”调整同库并发上限，再使用 `docker compose ... up -d --scale worker=4` 等方式增加执行进程。schema 23 后，环境变量仅用于首次初始化额度；本地工作站的进程数量仍由相应环境变量控制。任务以 PostgreSQL 作业表为准，worker 用租约代次取得单写入权。

对公网提供服务前，需要配置自己的域名、明确的 `THREEMIND_HOSTS` / `THREEMIND_ORIGINS`、HTTPS 反向代理及 `THREEMIND_SECURE_COOKIE=true`。数据库和 worker 只放在受控私网。当前提供账号、项目成员、角色和管理页面；没有开放自助注册、任意代码执行或付费算力服务。

## 数据备份与验证边界

数据库卷必须单独备份，Docker 镜像不是研究数据备份。使用 PostgreSQL 的 `pg_dump` / `pg_restore` 或部署者的物理备份方案；备份应包含整个专用数据库，而不是只复制某张连接表。SQLite 运行时使用 SQLite 在线备份接口或正常关闭后复制主文件，不能只拷走正在写入的主文件而遗漏 WAL。

专用应用账号受项目行级隔离约束，不适合做全库备份。备份使用具备全库读取权限的管理账号；恢复到新集群前先准备所有者和应用角色，并另行安全保存本地连接配置。`pg_dump` 提供事务一致的快照，归档格式由 `pg_restore` 恢复，详见 [PostgreSQL 官方备份说明](https://www.postgresql.org/docs/current/backup-dump.html)。本项目已在独立测试库验证完整备份、还原、连接查询和续跑一致性。

受控私网 worker 可以连接同一个 PostgreSQL；跨不可信网络的 worker 协议、公开匿名算力服务、跨平台逐位确定性和 24 小时容量验收属于单独发布门槛。当前支持范围和实测记录见 [实现与验证记录](v2-validation.md)。

## 创建与修改意识参数

“新建意识”默认打开图形配置，基础参数有明确默认值，高级参数默认折叠并按时间、传播、学习、抑制、修剪、感官、记录等分组。可以搜索中文名称、参数键或说明，也可以在参数区右上角切换 JSON。JSON 编辑支持行号、高亮、格式化和校验；切回图形配置前会检查内容，错误草稿不会被悄悄覆盖。帧序列、通道和初始干预支持分页图形编辑。

意识列表右侧或意识详情的“参数配置”可查看、编辑已有配置。正在运行时先暂停并等待检查点提交，再载入最新配置；已结束的对象先分叉，冻结实验的协议只读。创建后不可更改的参数有标记；JSON 中可以写出修改草稿，但校验和保存都会拒绝违反规则的修改。所有保存都重新进行服务端校验，并用版本号阻止覆盖其他窗口的新版本。

“设置 → 项目默认参数”使用同一套编辑器，保存到当前项目的数据库，仅影响以后新建的意识；修改已有意识不会反写项目默认值。显示/交互性能档位仍属于当前设备偏好，不能改变内核参数。

参数修改与新检查点在同一事务保存，可以在因果事件中查看 `configuration_changed` 的前后值及模拟时间。该记录不会改写旧检查点；从旧检查点分叉会采用当时的核心配置。具体生效边界见[内核说明](v2-kernel.md)。

JSON 只接受当前配置目录实际支持的字段，不能用旧参数名隐式启用功能；旧参数替代关系及本轮交付状态以[功能完整性清单](v2-capability-restoration.md)和[最新整合验收](v2-integration-acceptance.md)为准。


## 工作站退出与旧 worker 清理

工作站启动的 worker 使用专用父进程管道（`--parent-watch`）。正常停止时关闭管道，worker 在因果边界提交暂停检查点后退出；父进程意外退出也会产生 EOF。独立部署的 `worker` 默认不启用这一约束，生命周期仍由部署者管理。极慢倍速的等待循环同样响应停机，不能为停止而提前推进模拟时间。

Windows 的 Python 虚拟环境启动器可能再创建真实解释器进程。过去只结束启动器会遗留实际 worker，新旧代码可能同时领取任务；本次验收实际发现并清理了这些旧进程。第一次从旧版升级时，应先暂停运行并确认没有待执行/租用中的作业，再核对本项目进程的命令行、父子关系与启动时间后停止旧 worker。不要按 `python.exe` 名称批量结束其他项目的进程。

工作站正常退出最多等待每个子进程 30 秒。外部强制终止或无法完成写入时，恢复以最后成功提交的检查点为准；不会把未提交状态伪装成已保存。公开部署仍建议使用服务管理器或容器监督 API 与 worker 的生命周期。


## 媒体能力升级（schema 005）

升级前停止旧工作站及 worker，再执行 `threemind migrate`，更新全部 worker 后启动。005 只创建媒体原件／转换帧表及相关索引、处理版本，不读取或迁移旧 `data/`。

PCM WAV 无需额外解码依赖。图片、压缩音频和视频使用 `python -m pip install -e packages/runtime -e packages/transformer -e ".[media]"` 安装 Pillow／PyAV；新页面在缺少对应依赖时会说明能力范围。服务与接收端需要这些解码器，处理已经冻结的匿名帧的 worker 不需要重新解码原件。

`THREEMIND_MAX_MEDIA_DECODERS` 设置每个 API 进程的并发接收／解码数量，默认 2。单载体原件／时长和输入总线预算属于意识参数，可在界面修改。服务器槽位、部署资源配额、显示性能档位与科学采样率是不同设置，不应混成一个会偷偷修改实验协议的开关。器官输出累计约 8 MiB 时提前提交并背压，不静默丢弃记录。

大媒体默认通过[数据库分块上传](v2-media-uploads.md)。`THREEMIND_MAX_MEDIA_UPLOADS` 默认每项目 4 个未完成上传，`THREEMIND_MAX_STAGED_MEDIA_MB` 默认每项目预约 16384 MiB 原件暂存容量。运行时感官参数可将单件上限提高到 8192 MiB，解码时长、分辨率与输入预算仍独立约束。schema 12 增加同库暂存表，迁移后需重启服务；可运行 `python scripts/benchmark-media-upload.py` 在测试 PostgreSQL 55439 上测量生成原件缓冲，不会连接实际项目库。

使用步骤与限制见[媒体与器官](v2-media.md)。本地工作站仍连接原来的 5433 专用数据库。
# 物理遥测升级（006）

停止旧工作站及 worker，执行 `threemind migrate` 后启动更新后的版本。006 增加遥测采样查询索引；不会读取旧 data。Lab 已依赖 psutil；独立 Python Runtime 的纯遥测编码器不依赖操作系统探针，探针不可用时保留明确原因。三组感官只在显式启用和实时调度下采样，详见[使用与边界](v2-telemetry.md)。
## 消息索引

[刺激与读出](v2-conversation.md)使用 schema 13 的同库指针索引。迁移以 SQL 为现有输入／读出补建索引，历史顺序显式标记为重建；不扫描 `data/`，不修改原始载荷。完成迁移后重启服务。列表按游标分页，显示偏好保存在浏览器；完整科学数据仍在对应输入、读出与检查点中。


## 来源策略升级（014）

停止旧工作站／worker，执行 `threemind migrate` 并安装新的 Rust 扩展及前端后再启动。schema 14 增加逐帧策略 JSONB 证据列；旧帧保持 NULL。新建 causal/7，模型 profile/5 保存策略；旧模型可以按原状态继续。工作站真实端口仍为 8877、专用 PostgreSQL 为 5433。策略使用共用配置编辑器，暂停保存；CLI 使用方法及在途事件规则见[来源策略](v2-source-policies.md)。


## 模型档案升级（015）

停止旧工作站与 worker 后执行 `threemind migrate`，再启动更新版本。015 在同一库加入档案注释、独立编辑版本、精确恢复来源和清理回执，并用外键保护输入载体引用的媒体原件。现有档案的未知来源保持未知，不按相同哈希猜测；不扫描或迁移旧 data。实际本地 ThreeMind 专用库已升级至 schema 15。

归档可撤销，永久清理须在[模型档案库](v2-model-library.md)预览并输入名称确认。清理整份无引用档案，不单独剪断差量恢复链；PostgreSQL 逻辑空间回收不保证磁盘文件立即缩小。


## 人工研究控制升级（016）

停止旧 worker 后执行 `threemind migrate`，再启动更新版本。016 增加项目隔离的操作日志及恢复点引用。迁移显式设置 schema 搜索路径，同时覆盖新安装和已有库增量升级；应用账号沿用同库权限。实际本地 ThreeMind 专用库已升级至 schema 16。具体操作、重试与恢复规则见[人工实验控制台](v2-research-console.md)。


## 受控实验计划升级（017）

停止旧 worker，执行 `threemind migrate` 后再启动。schema 17 在同库保存受控协议、步骤及尝试引用，单 worker 可以完成计划，无需 MQ。原界面暂停分支现在可以明确选择暂停新背景来源。已完成模型与协议版本不变，实际本地专用库已升级至 17。详情进度使用轻量 `/research/plans/{id}/status`，不反复传整份冻结协议；见[受控计划](v2-research-plans.md)。

## AI 供应商升级（018）

安装更新的 Lab 依赖，停止旧 worker 后执行 `threemind migrate`，再启动工作站。实际专用数据库已升级至 schema 18，仍使用本地 PostgreSQL 5433。工作站启动器在忽略的 `.env` 中生成缺失的凭据加密钥，并启动独立 AI worker；没有创建或调用外部收费供应商。

手动部署运行 `threemind worker --queue ai`；`THREEMIND_MAX_AI_JOBS` 默认 2，独立于模拟 worker 并发。所有 API／AI worker 配置一致的 `THREEMIND_SECRET_KEYS`。服务器还需配置允许的供应商／代理来源 `THREEMIND_AI_ALLOWED_ORIGINS`。Compose 增加 `ai-worker`，已有配置用 `python scripts/init-compose.py --ensure-ai-key` 补齐密钥；不要打印包含真实密码的 Compose 展开内容。

数据库备份之外应单独安全备份加密钥。凭据轮换、网络范围、费用不确定性及发送后中断规则见[AI 工具说明](v2-ai-tools.md)。新队列失败不会把仍可运行的意识标记为死亡或资源阻塞。

## AI 运行工具升级（019）

专用数据库已升级至 schema 19。停旧服务后使用 `threemind migrate`，再启动工作站，或使用 `python -m threemind_lab.cli` 的同名命令。三类工具默认停用，意识详情“AI 工具”分别配置；服务器按项目身份和共享授权执行，仍使用 D3a 的独立 AI worker 与原有 PostgreSQL 队列。

新表只保存工具配置、调度与证据引用，不需要新数据库或 MQ。未知来源修订的旧采样不回填、不迁移旧 data。自动请求不追赶错过的所有周期，不自动重发结果不确定的收费调用。需要长时间自动生成时，先设定相应供应商的请求和费用预算；页面可查看每类工具的排队、应用、去重与错误计数。

## 通知与邮件升级（021）

停止旧工作站及 worker 后执行 `threemind migrate`，再启动新版。实际本地专用库已升级至 schema 21。通知开关默认关闭，项目所有者在“设置 → 通知与邮件”选择事件；站内已读状态按项目成员分开。

工作站自动启动独立通知 worker，手动部署使用 `threemind worker --queue notification`，并发由 `THREEMIND_MAX_NOTIFICATION_JOBS` 控制，默认 1。服务器配置 `THREEMIND_NOTIFICATION_ALLOWED_ENDPOINTS`，例如 `api.resend.com:443,smtp.example.org:587`；API／通知 worker 共用 `THREEMIND_SECRET_KEYS`，不在页面暴露部署密钥。

Compose 已增加 `notification-worker`，复用现有数据库队列。已有 Compose 配置缺少加密钥时使用 `python scripts/init-compose.py --ensure-ai-key`。本次只验证 Compose 配置，没有重建其他应用的容器或发送外部邮件。来源事务、投递状态与限流的完整规则见[通知与邮件](v2-notifications.md)。

## 命名状态捕获升级（022）

本地专用库已升级至 schema 22。停止旧 worker 后执行 `threemind migrate`，再启动新版本。“恢复与版本”可以捕获并命名运行中的状态；默认询问名称，可在设置中关闭并选择自动命名方式。请求回执、独立注释和真实恢复点在同一事务提交，网络确认丢失时重试原请求编号。

这次升级只增加同库回执表，不需要新服务、MQ 或模型格式。保留标记仍参与档案清理保护；暂停及终态对象直接编辑已有版本。使用和失败边界见[命名状态捕获](v2-state-captures.md)。

## 界面语言更新（D5c）

重新构建前端并刷新页面即可使用中英文及跟随浏览器选项，无数据库迁移。已有设备默认保持中文，顶部和设置均可切换。后台通知规则的参考语言仍由项目配置明确保存，个人语言切换不会改写它。文档正文、模型、协议和用户内容保持原文，详见[界面语言](v2-interface-language.md)。

## 集中执行额度升级（023）

专用库已升级至 schema 23。停止旧 API／worker，执行 `threemind migrate`，安装新版本后再启动全部服务。三类队列并发首次从环境变量初始化，此后在管理页统一保存，重启不会覆盖数据库策略。工作站启动进程数仍由原环境变量决定；改变并发额度不会自动创建或停止 worker。

“设置 → 执行队列与额度”显示当前项目的执行／等待／过期数量，管理员可配置部署和项目上限。0 只暂停领取新任务，正在执行的租约继续工作。不能混用忽略新策略的旧 worker；不增加 MQ、模型格式或数据迁移。详见[执行资源说明](v2-execution-resources.md)。

## 执行能力升级（024）

在停止旧 API／worker 后迁移至 schema 24，再整体启动新版。任务根据协议及实际启用的遥测来源匹配节点；无能力报告的旧 worker 不得混用。设置／管理中的执行队列可查看等待原因、实际节点和各次领取回执，并导出 JSON。暂停后改参数会刷新待执行任务需求；旧已结束任务不补造执行身份。详见[执行节点匹配](v2-worker-scheduling.md)。

## 容器资源与网络隔离（D6c）

Compose 提供按服务配置的 CPU／内存／进程上限、Lab 只读根目录、有界临时空间和日志轮转。数据库与 Runtime worker 仅连接内部数据网络，API／AI／通知按需连接外部网络；解密密钥不传给纯 Runtime worker。参数、默认值与完整应用镜像尚未完成验证的原因见[容器隔离说明](v2-container-isolation.md)。网络恢复前继续使用已验证的原生工作站，不能把配置解析及引擎探针通过称为 ThreeMind 容器部署通过。

## V3 恢复版本（2026-09-08）

当前内核为 causal/9，状态为 state/6，Lab schema 为 48。本机已完成原生扩展、CLI、UI 构建及增量数据库迁移，`doctor` 通过；运行 `scripts/start-lab.ps1` 即可启动。旧意识保留只读，不能按旧版本继续或自动切换动力学，应新建意识验收。本节覆盖上文各历史升级记录中的“旧模型可以继续”说明。普通意识默认不限时长，出生后连续无激活满 1 模拟秒才死亡；2026-09-09 已撤去可选独立能量强制判死，保留缺能结构损伤，所有死亡统一按活动宽限期判定。本次无需数据库迁移，更新原生扩展、CLI、UI 后使用新建意识；causal/8 也保留只读。

此次恢复状态、公式及验收证据见[V3 实施记录](plans/v3-restoration.md)。未来更新的通用步骤仍是：暂停任务、按父进程停止流程关闭工作站／worker，执行 `.venv/Scripts/python.exe -m threemind_lab.cli migrate`，更新扩展与 UI 后再启动。不要对运行中的原生扩展重复安装，也不要按进程名批量终止其他项目。

## 2026-10-10 本地更新补记

日常环境使用 `.work/kernel-venv`；数据库 migrate 与 Rust 安装分别进行。旧 `.pyd` 曾漏装 /3、/4，现已从当前源码重建安装，当前 schema/native doctor 通过，原版本及个体不转换。完整命令和故障定位见[数据管理指南](data-management.md#本机数据库与原生扩展更新)。本次没有启动工作站。
