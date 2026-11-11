# E60工具与复用 / Reusable tools

## 操作

从项目根目录使用 `.work/kernel-venv/Scripts/python.exe`。研究项目已存在时不要重复prepare；完成case会读取原结果，未完成case不会覆盖。下面是命令形状，不代表每种参数组合均已执行，已执行清单以results.json为准。

```powershell
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-07-eye-hand-learning/experiment.py teach
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-07-eye-hand-learning/experiment.py validation
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-07-eye-hand-learning/experiment.py fit --organization shared --reader-version 2 --steps 4000
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-07-eye-hand-learning/experiment.py evaluate --model C-fit-B-teach-shared-activity-fit2-v2-s4000
```

`--organization separate`使用独立眼/手表示；`--kind incoming`是明确的绕核对照，不是意识控制。`--nose`仅用于另建带鼻子的教学实例。`--mode empty/silence/rescue`分别切断输出、静默既有边、静默后恢复；Core仍接收完整感官。`--source`指定保留的学习状态，`--model`指定外设，二者可交叉验证。`--split confirmation`是最终留出布局，不得用于拟合。

`--world-reference B-teach`显式重放同一外部世界初态，不改源Core状态和时钟；用于隔离身体姿态与天气影响。`--mixed-validation --correction E-correct-B-teach`使用补课前后独立教师验证示范合并选择检查点，验证数据不参加梯度训练。`continue_study.py`记录单worker后续阶段，不能拿已看过的confirmation再次调参。`fit2`是修复空批次训练错误后的身份，不是新的Core版本。

## Python及命令行

- `EyeHandWorld`：/5完整视野环境，可选头部固定球面鼻部；无鼻时实际输入与/4一致。眼位、眼速、功率及其他身体环境感觉沿用，旧类和旧状态可恢复。
- `ContinuousMotor`：从原始活动时序产生眼手四个有限力分量，共同/独立版本。/2只改善外设隐藏层与初始化，原/1保留；不预设意识内部器官分区。`action(values)`不接受任务或答案。
- `python -m lab.tools.continuous_motor --model ... --observations recorded-rows.json`：只返回力值，不执行世界动作，供Agent或其他程序调用。模型声明使用入射旁路时会明确返回incoming。
- `motor_metrics`：清晰区覆盖、视线速度、连续稳定时长、转移、手部距离与到达比例；停在错误处不算注视成功。该测量不改变Core收敛读出。
- `gaze_events`：只读完整记录，按真实目标变化分段，给出首次进入、最长停留、是否起点已对准；短暂经过也保留。`python -m lab.tools.gaze_events recorded-process.jsonl.gz --output gaze-events.json`。目标只用于观察者评分，绝不传入控制器。
- `SensorimotorSession`：/5通过已有输入队列、Core及原始输出流接入；只扩充世界恢复注册，不改动力学。
- `active_vision_replay`：接受/4和/5完整记录，显示每段动作来源，支持逐帧、倍速、截图及WebM录制；新来源字段缺省时保留原展示。回放不运行Core。

## 可复用边界

教学、验证标签和评分可使用真实场景坐标；推理只接收匿名Core活动。整个输入/输出记录保留。外设训练成功只证明该接口可读，不自动证明意图或概念来自Core。所有干预在研究副本执行。生产世界编辑器没有因此自动获得新的训练按钮；本轮是实验CLI、Python与回放交付。

English: the runner exposes bounded teaching, fitting, correction, testing and causal controls. `ContinuousMotor.action` takes raw recorded activity only; the CLI predicts without executing a world. `/5`adds an optional physically rendered head-fixed nose while preserving `/4`. Replay keeps all trials and explicitly labels who controlled the actions. These are research interfaces, not a claim that production editor controls have been added.

Common-world replay retains each Core's own clock and state; mixed validation uses separate teacher clones. `gaze_events` measures first entry and duration without imposing a dwell gate. The `fit2` suffix identifies the corrected training procedure, not Core dynamics.
