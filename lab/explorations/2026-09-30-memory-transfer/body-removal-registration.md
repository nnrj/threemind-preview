# 全部本体感官移除对照 / Complete proprioceptive removal

2026-09-30，在闭环实验尚未启动时补充登记。最初的 `no_imu` 只移除了加速度计和陀螺仪，仍保留关节位置和速度，因此不能用它回答“完全没有本体感官”的问题。

增加 `no_proprioception`：移除本场景的全部身体测量输入，即三轴加速度、三轴角速度、关节位置、关节速度；保留同一外部弱维持刺激、相同身体和既有输出映射，不凭空添加可替代位置／速度的信息。未送入内核的原始测量仍作为观察证据保存。其余全部机制与主实验相同。

范围：普通默认、四个原定种子、正负两种外力、巩固开启／关闭，各一个三轮训练父本，分叉相同／相反外力各一次评估，共 48 个新增实例。本轮预计总数 1528（含 96 个定点记忆验证），仍低于 1536。这个补充不扩展到易化预设，不据此给易化作无感官时的结论。

身体动力学与电机的既有非语义投影保持不变。此对照是研究干预；正常运行不建议关闭整个身体反馈。没有身体反馈不预设个体必须表现更差，如果维持背景偶然驱动出较小误差，同样如实报告。适应目标“停留在轨道中央”仅用于外部评价，本轮没有奖励信号或人为修改连接来追求这个目标。

Registered before any closed-loop test. The initial no-IMU condition retains joint position/velocity and is not absence of all proprioception. Add 48 ordinary-preset cases removing all inertial and joint measurements, while retaining identical maintenance input, physics and output projection. Four seeds, two forces, consolidation on/off, three training episodes and same/reversed-force forked evaluations. Total planned cases become 1528. Raw removed measurements remain evidence. No conclusion about facilitation without all proprioception is claimed. The centre-of-track objective is an observer evaluation, not a reward or Core preference.
