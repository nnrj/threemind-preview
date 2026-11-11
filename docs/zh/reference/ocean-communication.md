# 海洋个体交流工具

[English](../../en/reference/ocean-communication.md) · [研究计划](../plans/embodied-communication.md)

这套装置把已有振荡器嘴巴接到模拟环境，其他躯体通过双耳接收匿名频带。没有Transformer、人工词典、食物答案或Core改动。它提供可检验的交流通路，不预先宣称信号已经构成语言。

## 命令行与Python

在项目根目录使用已配置的Python环境。以下另建演示目录，不会改动E53实验：

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
New-Item -ItemType Directory -Force .work/communication-demo
& $py -m lab.tools.ocean_communication_cli template > .work/communication-demo/protocol.json
# 可先编辑协议，再初始化。init创建空白意识，不会自动装入E53历史候选。
& $py -m lab.tools.ocean_communication_cli init .work/communication-demo/protocol.json .work/communication-demo/source
& $py -m lab.tools.ocean_communication_cli run .work/communication-demo/source .work/communication-demo/live --seconds 5
& $py -m lab.tools.ocean_communication_cli run .work/communication-demo/source .work/communication-demo/muted --seconds 5 --hearing muted
& $py -m lab.tools.ocean_communication_view .work/communication-demo/replay.html --case .work/communication-demo/live --case .work/communication-demo/muted
```

每次运行必须使用新的输出目录；续跑用前一阶段的`final`作为输入。`--wall-seconds`限制计算墙钟时间，`--seconds`是观察长度，不是个体的寿命。状态保存原有遗传结构、动态活动、身体、随机环境、在途声音及输入总线，恢复不会清空当前活动。

Python调用使用`CommunicationOcean`、`CommunicationProtocol`、`load`及`ocean_communication_cli.run_recorded`；与CLI使用同一执行代码。完整状态保存复用`ocean_contact_cli.save`。协议和状态分别为`threemind.ocean-communication/1`与`threemind.ocean-communication-state/1`。

### 同次身体采样：显式选择 /2

`template --joint-body-sample`产生`threemind.ocean-communication/2`，对应`JointCommunicationOcean`、`JointCommunicationProtocol`和状态`/2`。它把**同一躯体同一次采样**的身体与实际到达的听觉测量组成一个刺激组；匿名通道和数值不变。不同身体不合并，也不注入词义、身份或食物答案。原`/1`仍分别递送身体和听觉，不自动升级。

E53发现，原装置的分别递送使这一配置下的听觉与其他感官没有形成跨感官连接。`/2`修复的是环境共同观测的表达能力，不是修改内核生边规则。研究者应明确选用哪种装置，不能混称为同一实验。

相同通道值不代表两种分组在动力学上等价：共同触达候选及既有局部输入竞争都会受到分组影响。因此新版表现若变化，不能仅凭变化就全部归因于跨感官新连接；仍需独立的连接干预。

## 可调选项与解释

| 配置 | 含义 |
| --- | --- |
| `sound_interval_us` | 发声采样周期；不修改Core传播节律 |
| `sound_range_m`、`sound_reference_m`、`sound_speed_m_s` | 听觉范围、距离衰减尺度和传播速度；延迟向上取整到环境采样步 |
| `sound_bands`、`hearing_gain` | 频带数量和固定感官转换增益 |
| `voice_cost_per_s` | 发声身体耗能，受可用储备限制 |
| `self_hearing` | 是否听见自身发声 |
| `hearing_mode` | `live`正常；`muted`只屏蔽他者；`scrambled`逐次打乱他者频带，保留当次总功率 |
| `intake_share_fraction`、`association_gap_m`、`association_dwell_us` | 相容躯体接触后的摄入分享比例、间距和持续时间 |

同源相容、禁止同类吞食、接触分享均是公开的环境规则。它们不代表已经出现自主合作。现有嘴巴把局部较强活动变为声音，并非已经训练出的自主语言门控。

## 回放与证据

在浏览器打开生成的HTML，可切换完整海洋分支、拖动时间、播放、选择个体、查看双耳频带和导出PNG。宽屏并排、窄屏上下排列。回放固定展示每200ms记录的身体状态，不插入猜测轨迹；声音连线来自该时间窗实际记录的投递。静音对照仍可能显示环境中的声波连线，双耳值则是研究干预后的实际输入功率。声波不是神经连接，也不是语义标记。

`inputs/`保存实际提交的感官刺激，`communication.jsonl.gz`保存声音发出、接收、听觉分量与动作过程。**`/1`复原需要身体和听觉两路；`/2`的`inputs/`已含共同递送的听觉，不得把日志中的听觉分量再投一次。**日志以`delivery_group`及`combined_stimulus`说明组合依据。早期E53记录保存频带功率，后续还保存原嘴巴`voices`；缺失字段不回填为伪造的观测。`events.json`保存摄食、吞食、分享及出生等事件；`initial`、`checkpoints`、`final`是完整状态。

两版本的个体都可通过`ocean_species save`另存候选，再通过`seed_founders`用于新的同协议实验。复制保留结构与映射、清空活动并给予普通出生能量；它不是自然繁殖或学会交流的证明。新工具不会自动删除旧数据。

E53回放和双语报告发布到同一个研究项目的“记录与报告”；HTML作为可下载证据打开。本期未把新的海洋世界构建器加入生产UI菜单，完整世界的图形化编排仍属于研究总表中的工具待办。
