# 完整视野课堂工具

[English](../../en/reference/whole-scene-classroom.md) · [E58计划](../plans/embodied-memory-content.md)

`lab.tools.whole_scene_classroom.WholeSceneClassroom` 是 `threemind.grounded-classroom/3` 外设世界。一个固定相机采样整张桌面，物体、教师标记、自身有色指针都是真实几何。支持1～8个物体及连续位置；只有四个物体时允许省略位置使用旧布局。Core输入是RGB/距离像素、位置速度、身体/天气量、边界反力。场景名称、物体列表、教师标签只作外部证据，不交给Core或选择器。

这是二维滑动指针，不是关节机械臂。边界接触是导轨反作用力，并非已经实现任意物体碰撞、皮肤摩擦。固定模拟风和天气持续存在，不依赖本机CPU负载。

教师指示物是实际成像的球形标记，`teacher_radius_m`默认0.12米并随状态保存。原0.065米标记在16×16视网膜的两个远端教学位置未被采到，故在正式教学前修复可见性；早期未保存该字段的/3状态仍按0.065米恢复。坐标仅用于摆放真实物体，不作为额外感官端口送入Core。

```powershell
& .work/kernel-venv/Scripts/python.exe -m lab.tools.whole_scene_classroom --output .work/my-eye-recording --seconds 3 --force 0.4 -0.2
```

目录必须全新。命令保存逐帧原始测量、统一Stimulus和完整世界状态；不启动Core、不运行用户服务。`--state <state.json>`可恢复；Python接口为`observe / stimulus / advance_physics / state / restore`，可由Agent或UI复用。UI的史书与文档已能阅读本期记录；本工具尚未接入生产世界编辑器，不能把实验接口称为已有交互UI。

`RetinalChoice`读取规则像素邻域的活动过程，所有像素使用相同权重，输出一个像素位置。没有物体裁框、物体ID或答案推理参数；教师标签只在fit使用。它是有监督选择器，不能仅凭高分称为忠实意图翻译。普通输入与Core活动对照采用同一类模型。训练批大小可显式缩小，原工具默认仍为32。

`sensory_replay`仅供研究：以录制的参照帧替换视觉和/或全部运动相关身体量，记录替换范围；不改Core状态，也不成为正常世界默认。保持背景并不等于保持动作感觉，两个因果方向应分开检验。
