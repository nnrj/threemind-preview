# 容器资源与部署隔离

Docker 是 Lab 的可选部署方式；原生工作站和独立 Runtime 仍可离线运行。本页的配置属于服务部署，不改变科学参数、模型格式或界面的显示档位。2026-09-08 已完成 schema 46 的 Linux x86-64 镜像和独立 Compose 整合验收，覆盖内核、媒体、种群、研究导出、观察／评估、AI／通知队列及故障恢复，详见[最新记录](v2-integration-acceptance.md)。下方保留早期 schema 29／40 的历史结果。这些是功能与恢复验收，不是大规模并发、24 小时耐久或公网安全评估。

## 资源上限

`deploy/compose.yaml` 给每个容器设置上限。CPU 值是 CPU 时间配额；内存上限按需消耗，不在启动时预留整块内存。通过不受 Git 管理的 `deploy/compose.env` 调整后，重新创建对应容器生效；不向 API 挂载 Docker socket 来实现网页修改宿主机资源。

| 服务 | 默认 CPU 配额 | 内存上限 | 环境变量前缀 |
| --- | --- | --- | --- |
| API | 2 | 2 GiB | `THREEMIND_API_CPUS` / `THREEMIND_API_MEMORY` |
| 每个 Runtime worker | 2 | 4 GiB | `THREEMIND_WORKER_CPUS` / `THREEMIND_WORKER_MEMORY` |
| 每个 AI worker | 1 | 512 MiB | `THREEMIND_AI_CPUS` / `THREEMIND_AI_MEMORY` |
| 每个通知 worker | 0.5 | 256 MiB | `THREEMIND_NOTIFICATION_CPUS` / `THREEMIND_NOTIFICATION_MEMORY` |
| PostgreSQL | 2 | 4 GiB | `THREEMIND_DATABASE_CPUS` / `THREEMIND_DATABASE_MEMORY` |
| 一次性初始化 | 1 | 1 GiB | `THREEMIND_CONTAINER_CPUS` / `THREEMIND_CONTAINER_MEMORY` |

默认是一个有限资源的起点，不是模型可支持规模的上限或设备配置要求。大模型和服务器训练可提高额度；增加 worker 副本时，每个副本有独立上限，需按副本数量计算总预算。数据库中的部署／项目并发额度只控制领取数量，两者共同决定压力。CPU 限流可增加真实时间滞后，不能把滞后伪造成新的物理采样。

容器进程数默认 256，Lab 使用 `THREEMIND_CONTAINER_PIDS`，PostgreSQL 使用 `THREEMIND_DATABASE_PIDS`。PostgreSQL 的共享内存默认 256 MiB，可用 `THREEMIND_DATABASE_SHM` 调整。

资源约束使用 Compose 的 `cpus`、`mem_limit`、`pids_limit` 等服务字段，语义见 [Docker Compose 官方说明](https://docs.docker.com/reference/compose-file/services/)。超过内存上限可能由操作系统终止进程；已提交的数据库恢复点仍保留，过期任务按租约规则恢复或报告失败。进程被终止不等于意识在科学模型中死亡。

## 文件、网络与凭据

Lab 容器使用镜像中的非 root 用户，只读根文件系统、全部删除 Linux capabilities，并开启 `no-new-privileges`。只有 `/tmp` 是可写临时文件系统，带 `nosuid,noexec`。API 和 Runtime worker 默认临时空间上限为 1 GiB，分别通过 `THREEMIND_API_TMP_BYTES`、`THREEMIND_WORKER_TMP_BYTES` 调整；AI、通知和初始化默认 512 MiB，使用 `THREEMIND_CONTAINER_TMP_BYTES`。临时空间按字节指定。

tmpfs 的实际占用计入内存压力；处理较大媒体或导出时，临时空间和容器内存都需要足够。临时文件不是模型存储，也不替代数据库持久卷。PostgreSQL 使用自己的可写数据库卷；不要把其数据目录改成 tmpfs。日志按每份 10 MiB、最多三份轮转，避免无限增长。

数据库、初始化和 Runtime worker 只连接内部数据网络。API、AI 和通知 worker 同时连接外部网络，以接收请求或访问明确配置的供应商。数据库不映射宿主端口，API 默认仍只映射 `127.0.0.1:8878`。公开部署通过 HTTPS 反向代理进入在线模式，并设置明确的域名、来源和安全 Cookie。

加密供应商与邮件凭据的密钥仅传给 API、AI worker 和通知 worker，不传给纯 Runtime worker 或初始化容器。研究数据库凭据仍由受信任 Lab 服务使用；该网络划分不是不同项目之间的虚拟机隔离，也不是把数据库凭据分发给公众 worker 的授权机制。

## 无显示器运行与视觉感官

世界物理和无 RGB 的感官不需要桌面。声明了 `camera_rgb` 时，图像本身属于进入意识的物理刺激，关闭网页预览不能停止它。MuJoCo 在 Linux 上支持 OSMesa 无显示器软件渲染和 EGL 硬件渲染，详见 [MuJoCo 官方 OpenGL 说明](https://mujoco.readthedocs.io/en/3.8.0/programming/#using-opengl)。

Lab 镜像安装 OSMesa／EGL 库，默认 `MUJOCO_GL=osmesa`，所以普通 Docker 部署不要求 X11 或 GPU。已有 GPU 驱动和容器设备映射的服务器可在自己的 `deploy/compose.env` 中设置 `THREEMIND_MUJOCO_GL=egl` 并重新创建服务。选择 EGL 并不自动安装驱动或分配 GPU；实际 RGB 能力以对应 worker 的探针结果为准。这里的渲染后端是实验部署条件，不是网页显示档位；不能为了加快预览而偷偷降低相机的分辨率或频率。

RGB 能力检查在独立子进程中执行，最长 20 秒。缺少上下文、原生库异常、驱动进程崩溃或超时会记为 RGB 不可用，其他能力仍可发布和领取匹配任务。不捕获用户中断作为“能力缺失”，也不自动改用另一种渲染后端。所有实际视觉状态继续保留渲染校准；换设备或渲染实现不宣称像素逐位相同，精确恢复仍检查原来的校准约束。

## 构建依赖与重复初始化

容器的 Linux CPython 3.12 运行依赖固定在 `deploy/constraints-linux-py312.txt`，与原生工作站的兼容版本范围分开。Docker 先安装这些依赖，再复制应用源码；修改 Python 业务代码不再使整层科学计算／媒体依赖重新下载。原生扩展仍从本仓库和 `Cargo.lock` 构建，网页依赖使用 `package-lock.json`。更新固定依赖后应重新验收镜像，不能把可安装误当作研究结果等价。操作系统包、构建工具与基础镜像标签尚未全部按摘要固定，因此这份约束不是逐字节可重建镜像的承诺；保存验收镜像的实际摘要仍有必要。

直接构建 Lab 时须明确选择目标：`docker build --target lab -f deploy/Dockerfile -t threemind-lab:local .`。同一 Dockerfile 还提供独立 Rust Runtime 目标；省略目标不能假设得到 Lab。Compose 已明确选择 `lab`。

初始化可以对已经完成升级的数据库再次执行。迁移器只使用显式登记的 SQL 清单，由同一清单确定支持版本和执行顺序，最后核对完整版本历史；发现缺口或比代码更新的数据库时拒绝修改。新建、旧版本升级和已经升级后的重复启动是不同路径，均应验证。

## 已验证与待验证

2026-09-07 的 Compose 规范化输出验证了内存／CPU／进程上限、只读文件系统、临时挂载、日志轮转、内部网络、端口绑定与密钥作用域，检查输出省略所有连接配置和秘密。在一个不联网的临时容器内，实际读取 cgroup 限额并验证非 root、根目录拒写、`/tmp` 可写、能力集合为 0 和 `NoNewPrivs=1`。该探针使用本机已有的镜像，结束后容器已删除，没有连接研究数据库。

此前构建在 `auth.docker.io` 超时；本次验证发现 Windows 网页请求能够访问，而构建进程没有沿用系统代理。只在构建命令的进程环境中设置现有代理对应的 `HTTP_PROXY`／`HTTPS_PROXY` 后，认证、镜像下载、Rust 编译与应用构建成功，没有修改全局 Docker 配置。遇到同类问题应分别检查浏览器、命令行和构建器的网络路径；网页能访问不代表它们使用同一代理。

首轮验收镜像来源为提交 `908595e`、schema 29，项目名为 `threemind-acceptance-20260907`，API 仅绑定 `127.0.0.1:18878`。这份历史验收不代表后续功能已验证。使用新生成的测试凭据和独立 PostgreSQL 卷，没有连接原生研究库、PoemHaven 或 daydream。实际检查包括：

- 初始化专用数据库／非所有者角色、匿名私有 API 拒绝、在线账号登录，以及浏览器桌面和 390 px 页面。
- 原生内核与 MuJoCo 闭环、WAV／PNG 原件哈希往返、感官递送及器官读出。
- Markdown、HTML、Word、PDF，中文、公式、表格及折线图。Word 三页和 PDF 三页逐页渲染检查；生产容器不依赖 Word 或 LibreOffice。
- AI 实际 HTTP 队列和证书校验的 TLS SMTP 队列；均连接隔离网络中的模拟服务，没有外部付费调用或真实外发邮件。
- 在已提交 300000 μs 后以 `SIGKILL` 结束测试 worker，重新启动并等待真实 60 秒租约到期；第 2 代领取恢复成功，最终状态哈希与无故障对照一致。二进制模型导出、再导入同样保持状态哈希。
- 实际 Lab 容器 UID 10001、根目录拒写、临时目录可写、有效 capabilities 为 0、禁止提权，以及 CPU／内存／PID／端口约束。

两次初期脚本失败分别来自验收夹具误写 AI 完成状态和指标键，修正后完整链路通过，没有为通过验收放宽产品契约。完整记录见[应用验收数据](../benchmarks/2026-09-07-container-application-validation.json)。后续源码更新应重新构建镜像；该次已验证镜像不会自动包含更新的代码。

## schema 40 生态与完整研究导出验收

同日使用新的专用项目 `threemind-ecology-acceptance-20260907`，从空测试卷完成 schema 40 初始化。全链路验收对应 `f285808`；导出修复后用 `62a0b6b` 重新生成相同固定修订；最后在 `2d447e3` 镜像中复验独立恢复、完整记录的种群和实际容器隔离。每个阶段的镜像配置摘要与 OCI 索引摘要分别保存，不把最后一张镜像冒充此前所有检查的执行环境。

- 重复初始化、在线登录、真实 MuJoCo 闭环、WAV／PNG 原件往返、器官输出、模拟 AI HTTP 和校验证书的 TLS 邮件队列通过。没有外部付费调用或真实收件人。
- 普通意识在提交 700000 μs 后强制终止 worker，实际等待 60 秒租约到期，第二代领取恢复与连续对照哈希一致。
- 共享生态种群在提交 40000 μs 后强制终止，恢复后的全部 6 个脑状态及完整资源账本摘要与连续对照一致；还验证了独立栖息地、两代定向训练和隔离评估副本。
- 无桌面容器中实际执行 8×8 RGB 视觉感官；独立生态 CLI 的 SQLite、交换包恢复与连续计算在非整物理边界保持一致，且没有导入 Lab。
- 完整种群证据包核对全部模型哈希；整组 62 条轨迹及 6 个体来源进入固定记录，Markdown、HTML、Word、PDF 和全部数据 JSONL 成功导出。桌面 1440 px／手机 390 px 的图表无横向溢出或页面错误。
- 最终 Word 的基础／轨迹／个体报告分别为 2／19／5 页，PDF 为 2／18／5 页。全部最终 PDF 逐页检查；Word 已检查全部页面，重新导出后只对 PNG 哈希完全相同的页面复用原检查，其余两页重新检查。修复了窄分布标签精度和 PDF 长表分页，不改原始数据。
- 最后镜像重新运行的完整记录种群与前一镜像的全部脑哈希、完整账本摘要一致。非 root、只读根目录、可写临时目录、零 capabilities、禁止提权和实际服务资源约束再次通过。

冻结结果见[生态容器验收数据](../benchmarks/2026-09-07-ecology-container-validation.json)。相关回归分四批记录：渲染隔离 14 项、数据库迁移 13 项、报告导出 13 项、种群观察／独立运行／读出保真 27 项，均通过；它们存在覆盖重叠，不能相加当成独立用例数，也不宣称本阶段重跑了全量测试。验收完成后只移除了该项目的容器与专用卷，保留构建镜像，其他项目容器身份未变。

公开的只读研究材料分享已随 [E2e 固定修订分享](v2-research-sharing.md)交付，必须显式发布。匿名执行、付费配额、跨不可信网络的 worker 协议、长期耐久、成熟大种群容量和跨平台逐位等价，继续属于另外的设计与验证范围。
