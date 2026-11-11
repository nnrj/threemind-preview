# 机械臂有限供能与幸存者繁殖

[English](../../en/plans/robot-survival-selection.md) · [研究进度](research-backlog.md) · [E27 执行登记](../../../lab/explorations/2026-10-02-survival-transfer/design.zh.md)

2026-10-03。此页保存用户决定和工具边界；实验结果另在 E27 报告记录，不用后来的工具改写早期样本。

## 为什么改变上一轮选择方式

E26 的候选只活动数秒，之后按独立评估副本的目标距离筛选。用户要求更长的、发生在运行期间的选择：有限出生能量；物理任务成功带来摄入；没有获得补给的个体通过内核已有的能量限制和活动消失规则死亡；幸存者再繁殖。到观察期限按剩余能量选父本，不把没有入选但仍活着的个体伪记为死亡。

本轮首先必须自行抓起自由杯，再把其中的颗粒倒进另一只杯。可使用视觉、触觉、关节和本体感官；不向 Core 输入物体名、正确动作或任务答案。不先固定杯子；只有自由杯没有效果后，才做固定杯子的简化对照。真实液体和玻璃破裂另待流体/断裂仿真，不把刚性颗粒叫作水。不引入抢夺其他个体能量。

## 能量和死亡的边界

- Core 能量使用实验单位；机械功另记为 J，不能混作同一个账本。当前不把电机机械功从 Core 余额再扣一次。
- 出生能量来自实验环境。任务按实际完成量增加外部可供给量，定时通过现有 `supply_energy` 入队。满容量时，已提供和实际接收可能不同，都要保留。
- 能量用尽不清空激活。内核自己限制可支付的输入/传播，按既有规则衰减和死亡。首次从未激活、用尽能量、任务失败、停止观察、技术故障和内核死亡分开。
- 抓握/提起只作为完成抓杯任务的物理证据，不单独给能量。每批每颗颗粒只计一次；接收杯内需停留200ms，避免把路过算成完成。这里是任务计量，不是意识收敛条件。
- 固定时间补料是明示的外部环境操作；不复位机械臂、活动或连接。没有按个体表现临时救济。
- 繁殖用既有 `birth/1`：继承结构，重置即时活动和出生能量。每个新生个体获得同样出生储备；当前没有模拟从父本扣能支付生育，不宣称这是封闭守恒的生态系统。
- 没有幸存父本就停止该谱系，不复活死亡个体。未获繁殖资格的活体保留完整快照；超时或资源停止也不伪记为饿死。

## 本轮的装置与数值

固定 Menagerie Panda 资产；真实三维关节、夹爪联动、重力、惯性、摩擦、接触。原始力矩接口，不给意识加入 IK、动作脚本或自动抓握。独立工程控制器先证明物理任务可做；其动作不向候选示教，其结果不算 ThreeMind 学习成绩。

物理步长2ms、控制与非视觉感官20ms、视觉100ms。视觉为16×12实际渲染图像的固定亮度转换，保留原像素值与映射；它是低分辨率实验感官，没有物体检测或语义标签，不代表已达到真实机器人的视觉精度。实际能量储备可作为内感官；CPU/宿主遥测关闭。

出生40300单位、容量161200、每颗合格转移提供10100单位、每1秒结算，每30秒补料。数值由30秒工程耗能校准的末10秒均值167.589854单位/秒确定：约240秒出生储备、每颗约60秒。实际寿命取决于个体行为与活动，不能把这些折算当作保证。

每个候选观察上限600模拟秒，首批16个，预算允许才扩到32；最多两代后续。简化对照8个。资源执行补记允许最多三个独立进程、合计4GiB内存，其耗时相加计入4小时预算。来源、种子、参数、原始测量、动作、能量、模型与物理状态、谱系都保存。[设计](../../../lab/explorations/2026-10-02-survival-transfer/design.zh.md) [执行调整](../../../lab/explorations/2026-10-02-survival-transfer/execution-amendment.zh.md)

## 提炼出的研究工具

这些是开发/研究工具，没有改变独立 Runtime 或历史意识的动力学。`lab.tools.granular_session.SurvivalSession` 提供 Python 操作接口；`granular_survival` 提供命令接口和同一 JSON 校验。协议参数可复用，输出目录只能新建，不能覆盖旧证据。

在项目根目录执行：

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
& $py -m threemind_runtime.playground_assets install
& $py -m lab.tools.granular_survival template --output .work/my-survival.json
& $py -m lab.tools.granular_survival validate .work/my-survival.json
& $py -m lab.tools.granular_survival run --protocol .work/my-survival.json --seconds 600 --output .work/my-individual
```

E27在MuJoCo 3.14.0验收；精确恢复要求相同仿真版本和固定资产，不能假定任意MuJoCo版本都给出相同轨迹。资产安装是显式命令；运行过程不下载。已有固定资产时无需再下载。模板不会启动仿真；只有 `run` 开始计算。`schema` 输出配置规范。`core` 使用已有内核参数，`world` 配置物理/采样间隔、视觉尺寸、力矩范围、投影增益、补料周期、种子和是否固定杯子；`energy_per_grain` 与 `food_interval_us` 配置供给。固定杯子是另一项任务，不与自由抓杯成功率混算。

```powershell
# 仅对未死亡的个体继续；保存到新目录，保留原结果。
& $py -m lab.tools.granular_survival run --protocol .work/my-survival.json --seconds 60 --resume .work/my-individual --output .work/my-continuation

# 先选择，再对选中的幸存者明确创建出生副本。
& $py -m lab.tools.granular_survival select .work/individual-a .work/individual-b --parents 1 --offspring 4 --output .work/selection.json
& $py -m lab.tools.granular_survival run --protocol .work/my-survival.json --seconds 600 --birth-from .work/individual-a --output .work/child-a
```

`select` 读取真实模型中的生命状态和能量，并结合是否到达观察期限；失败或中途停止不能入选。它只生成分配表，不自动删除或启动实例。`--birth-from` 要求活着且已完成观察窗口，保留父本；`--resume` 是同一个体继续，不是新生。Ctrl+C在本次物理/内核步结束后保存；也可用 `--stop-file` 请求暂停。运行时故障单列，不能伪称可精确恢复。

`lab.tools.survival.TaskFood` 是可复用任务供能账本，支持重复收据去重、定时供给、账目校验和保存恢复；`select_survivors` 只生成幸存者繁殖计划，不改变内核或亲本。它们可用于后续其他物理任务，任务本身仍须提供可信的测量与对象去重。

回放区分原始刺激复算和画面重建：

```powershell
# 用已记录的实际刺激和供能重新计算，核对逐步活动与完整最终 Core 哈希。
& $py -m lab.tools.granular_replay .work/my-individual --core-only --output .work/my-core-replay
# 按实际动作重放物理过程，导出视频、时间图和校验收据。
& $py -m lab.tools.granular_replay .work/my-individual --output .work/my-video
```

默认要求严格重现。部分长期回放出现少量像素亮度相差1/255、物理测量仍完全相同的情况；原始记录不改动。确有需要时可明确加 `--allow-pixel-variation`，只放行并逐项报告渲染差异，仍严格检查物理测量、事件与末态；此结果**不叫完整感官精确复现**。高分辨率观察相机使用独立数据副本。Core 复算以录下来的刺激为准，不以重新渲染的画面代替；每种回放都另建输出目录。当前视频工具从出生状态重放，接续段须与其起点物理状态配套，未宣称可以单独渲染任意接续段。

E27 的笔记、报告和证据归档进入现有「实验笔记／记录与报告」。本轮新颗粒任务的完整群体启动尚使用上述研究命令/Python接口；未宣称已接入现有机器人页面的完整图形编排。正式 UI 接入需复用同一协议和生存规则，不能误用 E26 的结束评分来冒充运行中淘汰。
