# 机器人任务：配置、运行和观察

[English](../en/robotics.md) · [实施方案](plans/robotics-and-language.md)

工程版本：自定义任务使用 `threemind.robot-task/1`，官方 Playground 任务使用 `/2`；本页的可运行能力与机器人学会完成任务是两回事。内核仍使用创建时选择的版本。

## 从界面开始

进入「世界与躯体 → 机器人任务」，选择自定义机械臂、移动底盘，或已安装的 G1、PiPER、SO-101 资产。配置躯体、控制方式、可观测目标、感官尺度和物理周期。先「校验与预览」，再保存版本或创建意识。图形与 JSON 共用配置，错误不能绕过保存校验。

默认自定义机械臂有三个转动关节和一个夹爪，输入为关节位置、速度、惯性和接触测量，以及可关闭的理想光学信标。信标在感受范围内测量目标相对于端点的方向／距离；当前没有遮挡模型。任务成功与距离评分不作为 Core 的奖励输入。

力矩是默认控制；位置、速度模式使用明确的外部伺服控制器。「外部技能」目前只有固定的关节扫动示例，**不是预训练抓取或行走策略**。输出接线采用现有固定匿名投影，不能把它当成已经自发形成的运动脑区。连续转动关节的位置伺服使用初始位置附近的可配置半范围，不使用近似无限的机械范围作为目标角度。

SO-101 默认位置伺服，也允许在下拉框选择「原始力矩（仿真理想执行器）」。这个选择将 `actuator_variant` 设为 `ideal-torque`，记录在协议和证据中。保留质量、惯性、关节与力矩限值，不代表实体 SO-101 的固件有原始力矩接口。其它型号的模拟控制器同样不能代替实体校准和实测。

已有意识可暂停、按一个感官周期单步，或继续。展开「人工干预与快照」可施力、临时接管执行器、解除干预、请求完整快照和仅复位世界。施力采用世界坐标，单位 N／Nm；动作按执行器 ID 字典序为 -1～1。暂停不会消耗干预的模拟时间。复位只重建外部物理世界，不清空意识，不撤回已经接收或在途的刺激，也不复活死亡实例。

宽屏并排显示世界与配置；窄屏通过「三维观察／配置／感官与动作」切换。转动相机不参与仿真。原始物理值、动作和环境指标直接显示，历史快照、分叉和证据在同一意识的研究页面。

## 独立运行与 Agent 操作

安装 Runtime 的 `world` 可选依赖后，不需要 Lab 或 PostgreSQL：

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
& $py -m threemind_runtime.robot_cli template custom-arm-reach --output arm.json
& $py -m threemind_runtime.robot_cli run --task arm.json --store arm.sqlite --until-us 1000000 --evidence arm-first.jsonl
& $py -m threemind_runtime.robot_cli run --store arm.sqlite --resume --until-us 2000000 --evidence arm-next.jsonl
```

SQLite 保存 Core 与外部世界的完整继续状态，包括物理积分状态、感官截止时间和在途输入。`--model` 可导入独立意识模型；`--export` 导出的是脑模型，**不包含完整机器人继续状态**。输出文件使用独占创建，避免覆盖旧证据。`--action` 接收归一化执行器数组，属于显式人工对照，不会假称 Core 动作。`--wall-seconds` 和 `--evidence-mib` 为运行预算；死亡即停止继续演化。

真实型号资产须显式安装，缓存默认 `.work/robot-assets-cache`，可用 `THREEMIND_ROBOT_ASSETS` 调整。安装固定版本、大小及 Git 文件哈希，保留许可证；运行和打开页面不会触发下载：

```powershell
& $py -m threemind_runtime.robot_cli assets install so101
& $py -m threemind_runtime.robot_cli template so101 --output so101.json
```

Lab 的 REST 操作目录同时供通用 CLI 与 MCP 使用：`robot.catalogue`、`robot.validate`、`robot.asset_template`、`world.observe`、`world.protocol`，以及既有的意识创建、`consciousness.command`、研究步进、快照和分叉。`robot_control` 命令携带 `force`、`actuators`、`release` 或 `reset_world`；服务端和独立协议使用同一校验。已冻结的配对实验拒绝插入未登记干预。

## 本阶段验收与未结项

已实际验证自定义机械臂／底盘四种控制、G1/PiPER/SO-101 装载、SO-101 理想力矩选择、感官、任务指标、只读观察、完整继续、Python/Rust 后端及旧版本身份保持；1440/390 像素浏览器走通配置、保存、创建、干预、单步和快照请求。旧物理世界回归保留。

公开 Playground 任务适配、真实硬件通信、URDF/CAD 制造文件和机器人学习成绩仍需分别交付与验证。当前自定义场景不是重命名的公开 benchmark；三类躯体接口可运行，不等于已经学会抓取、导航或行走。

## 2026-10-02 续交付：官方 Playground 任务

上节关于 Playground 尚待接入的记载是此前阶段状态；现在已接通官方 **PandaPickCube**。在「世界与躯体 → 机器人任务 → 选择机器人模板」选择它，配置感官与计算后端，校验后保存或创建意识。Windows 页面不需要安装 JAX：相应 Linux worker 保存检查点后，页面取得同一场景的几何、位置、感官、动作和评分。1440/390 像素均已验收。

这是独立 `threemind.robot-task/2`，不是把自定义力矩任务改名。固定官方源码 `ef4fefc13033c0468af4ef651847f5348af0c7d7`、Menagerie `1b86ece576591213e2b666ebf59508454200ca97`，源码和 79 个 Panda 文件逐件校验；运行时不下载。保留官方位置增量伺服、5 ms 物理步长、20 ms 动作周期、150 步回合和原评分函数。本次实际验收的是 **JAX/CPU**；与上游默认 Warp 后端明确区分，不声称两者逐位等价。JAX/CUDA 与 Warp/CUDA 有显式配置和能力匹配，本轮未做实际 GPU 验收；CPU 镜像不会假装提供 GPU。

默认输入是关节位置/速度、接触和可关闭的局部理想光学信标；信标无遮挡模型。可另选含全局信息的「官方状态向量」，明确标为特权观测。评分、任务结束和正确动作不送入 Core；固定匿名输出投影的增益可调。评分可以作为环境选择指标，不能由它反推 Core 学会了任务。回合结束暂停的是实验，不是意识死亡；不自动重新出生、不自动复活。仅重置世界后可续接，Core 时间和记忆继续。

快照保存官方状态的完整数组树（包括随机状态）、控制/感官时刻、Core、在途输入、依赖与后端身份。不同身份拒绝静默续跑。初始场景的姿态在独立观察副本上计算，官方 reset 状态不被改写。三维网格以有大小上限和 SHA-256 的压缩载体保存，API 无需启动物理仿真即可还原显示。当前 Panda 场景原 JSON 约 26.1 MiB，保存载体约 4.24 MiB；长实验仍须给检查点与证据设预算，跨检查点去重尚未实现。

### Docker Desktop 接入现有本地工作站

不需要重装 CUDA。以下镜像使用 CPU，普通 Windows worker 可继续负责原有任务。先完成代码环境更新和数据库迁移，再由用户启动专用 worker；本轮验收没有启动或接管用户的工作站服务。

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
docker build --target lab -f deploy/Dockerfile -t threemind-lab:local .
docker build -f deploy/Dockerfile.playground -t threemind-playground:local .
& $py -m threemind_lab.cli migrate
& $py scripts/playground-worker.py --check
& $py scripts/playground-worker.py
```

启动器只把应用数据库连接传入容器；不挂载 `.env`、管理密码、项目源码或 Docker socket。本机地址转换为 `host.docker.internal`，端口仍取现有配置（本机为 5433）；可用 `--database-host` 指定其它可达地址。`--check` 仅检查源码、CPU 与数据库 schema，不领取任务。若 PostgreSQL 拒绝容器地址，按错误配置该数据库的网络访问，不把它当成模型问题。专用进程使用 `--task-family playground`，不会领取普通意识任务；默认 6 GiB、2 CPU、只读根目录。首次任务需要编译，后续同进程复用编译结果；不把编译等待算成模拟时间。

独立命令仍是 `python -m threemind_runtime.robot_cli`，模板名 `playground-panda`，`run --store ... --resume` 保留完整继续状态。API/MCP 复用机器人、世界、研究步进与快照操作。原 `/1` 不升级、不改哈希。

### 实际验收与限制

离线容器验证了官方 reset/step、只读观察、状态恢复、完整意识与世界恢复；真实 API → 数据库 → Linux worker 执行一整个 150 步回合，并验证终点暂停、无重置不能暗续、仅重置世界后单步、场景 API 不重建物理。修改初始观察和压缩载体前后，完整回合 Core 哈希保持相同。原机器人/API/CLI、专用任务分派、宽窄屏分别回归。本机数据库已迁移至 schema 57，容器启动器的 `--check` 已通过现有 PostgreSQL 的实际连接检查，没有领取任务。[验收摘要](../benchmarks/2026-10-02-playground-validation.json)

首次联调的临时数据库 256 MiB 上限触发 OOM，该次记为失败；之后将该测试库限制改为 1 GiB，并压缩观察网格后重验通过。旧实验库未受影响。此处是工程验收，不增加 E26 的样本或成功率；未进行新一轮抓取训练，也未验证实体机器人迁移。上游参考：[源码](https://github.com/google-deepmind/mujoco_playground/tree/ef4fefc13033c0468af4ef651847f5348af0c7d7)、[JAX 安装](https://docs.jax.dev/en/latest/installation.html)。
