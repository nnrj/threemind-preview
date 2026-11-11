# E59工具与复用 / Reusable tools

本批工具位于 `lab/tools/`，使用现有输入总线、Core和原始输出流；不改Core动力学。它们是开发态实验工具，尚未接入生产世界编辑器。所有命令在项目根目录执行。

These are laboratory tools using the existing input bus, Core and raw output stream. They do not change Core dynamics and are not yet controls in the production world editor. Run from the repository root.

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
# 纯物理眼睛：输出目录必须不存在。无Core实例被创建。
& $py -m lab.tools.active_eye --output .work/my-eye-observations --seconds 10 --gaze scan
# 对既有/4记录生成完整回放；不推进Core。
& $py -m lab.tools.active_vision_replay RECORDING.jsonl.gz --output .work/my-eye-replay.html
# 眼动、联想和目标光学覆盖的只读过程统计。
& $py -m lab.tools.gaze_activity RECORDING.jsonl.gz --output .work/my-eye-metrics.json
```

- `active_eye.ActiveEyeClassroom`：完整场景、固定非均匀受体、可见自身、两轴惯性眼球、实测眼位/速度/功率反馈、完整状态恢复。`stimulus()`只读取实际测量值。`execute_eye_selection()`和`execute_hand_selection()`依据被选受体在**采样时刻**的光学方向执行，不接收目标对象或答案。手部使用已校准位置伺服，不冒称重新学会关节运动。
- `sensorimotor_session.SensorimotorSession`：50ms采样、普通逐字符教学、输入队列、连续内核、原始活动及物理动作记录。允许直接调用Python，不需要UI或另起服务器。
- `foveal_choice.FovealChoice`：共享的局部外部读取器；输入为原始激活、抑制、直接触达、联想触达过程。几何邻域由固定受体位置定义。CPU/CUDA及保存恢复均可用。它接受监督标签训练，必须另做归因对照；高分不自动证明Core独立识别。全零输入会停止发命令；其他状态的主动不表达尚未训练。
- `gaze_activity`：只分析已记录过程。扫描与联想的相关性只能定位候选时间段，不自动判定内部决策。
- `active_vision_replay`：完整场景与实际视网膜并排；所有问题和错误均保留；支持逐帧、变速、PNG、WebM。录像来自画布实际重放，不补画成功行为。原始活动的全节点证据另存，画面显示汇总只是显示选择。

The reader is a supervised external selector, not a proven intention translator. Fixed retinal neighborhoods are geometric, never semantic crops. Motor execution uses the optical direction at acquisition time; hand mechanics use a calibrated servo. All-zero reader input stops commands, while learned voluntary abstention is still unimplemented. Replay and analysis are read-only; motion/activity correlation alone is not causal attribution.

- `foveal_sequence.FovealSequence`：独立版本的较长原始过程读取器，默认最多64个样本，支持分批CUDA/CPU拟合、验证及恢复。本轮只读比较使用60帧与16帧；没有验证成绩增益，不能写成推荐默认。 / Separately versioned full-process reader, 64-sample default capacity, batched CPU/CUDA fitting and restore. The 60-versus-16-sample comparison did not establish a performance benefit.
- 回放可同时打包多个记录文件，`--case-labels labels.json`提供人类可读的组名；原case身份仍保留。全记录读取，不按正确率挑选片段。`check_replay.mjs`检查桌面/窄屏、PNG及真实WebM解码。 / Multiple recordings and optional display labels retain original case identity. All records are packed, without success-based selection; the browser check verifies actual video decoding.

本批演示可打开 `.work/active-vision-20261007/active-vision.html`，或在E59研究项目的“完整证据与回放”文档打开同一归档HTML。它包含所有正式闭环条件的全部12题、两种完整104课教学，以及三个装置对照。场景为物理记录示意，右侧颜色来自实际视网膜量；所显示的汉字形状名仅供观察者，不作为Core答案输入。

Open the local HTML or its archived artifact in the E59 project. It contains all twelve questions in every formal closed-loop condition, both complete 104-lesson courses and three apparatus controls. Shape names in the visualization are observer labels, not Core input answers.

E59复现按 `experiment.py --help` 的独立阶段进行；已完成case只读返回，未完成目录不覆盖，失败另登记新尝试。`prepare`会通过Lab服务创建本轮研究项目和笔记；不得对旧项目重复登记以改写历史。

E59 stages are resumable. Completed cases are read-only; incomplete cases are retained and require a new attempt identity. `prepare` creates the registered study via Lab services and must not be used to rewrite an old study.
