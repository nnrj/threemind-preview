# 刺激与本体感官：实现和使用

[English](../../en/plans/stimulus-spacetime-implementation.md) · [决策与原始讨论](stimulus-intensity-and-spacetime.md)

2026-09-30。本轮没有改动 Python／Rust 内核及候选内核公式。基线 `6241016` 的输入／状态样例保存在 `tests_v2/fixtures/stimulus-6241016.json`，回归验证其原结果。

## 入口

- 聊天输入：普通 1／强刺激 4／自定义；滑条 0–4，数值框 0–100。预设不改变文本规范化、标点编码、分帧或通道身份。自定义强度优先于预设。
- 创建意识：普通默认不启用额外易化；“耗竭＋易化＋巩固”按钮**显式应用普通内核默认＋1 秒易化**。新颖性仍为 arrival-window，0.018／0.2，不是易化开关。
- 新建意识的宿主／进程／实例遥测，各自强度 0.2，开关仍独立。历史省略强度按 1 恢复；新运行时配置协议 `/6` 与遥测 `/3` 显式记录强度，旧版本仍按原规则读取。
- “感官与输入”中选择刺激体，可以编辑共同观测、生成三类随机对照；生成不等于递送，相同种子与序列位置重复使用会产生相同通道。
- 展开递送选项可运行“副本诊断”：在最近检查点副本上观察 0.5 秒，显示触达、激活增量、巩固分量、新颖性原因及哈希验证。它不经过环境／躯体过滤，不能冒充线上状态的完整预测。
- 世界工具：载入惯性滑车或重力摆体，编辑加速度计／陀螺仪的位置、朝向、尺度和开关。宽屏配置和预览并排，窄屏切换“配置／观察”。旧世界不会静默升级；可显式升级草稿为 `/2` 后保存新版本。
- 世界观测显示原始单位、转换尺度、匿名编码及共同刺激组。预览是已校验的物理姿态，不是浏览器自行模拟的训练证据。

## 无界面操作

以下以已安装项目的 Python 为 `python`；PowerShell 可先将 `python` 替换为 `.work/kernel-venv/Scripts/python.exe`。所有新输出均使用新路径，不覆盖输入模型。

```powershell
python -m threemind_lab.cli input-text --project <project-id> --run <run-id> --file carrier.txt --preset strong
python -m threemind_runtime.cli --text-input carrier.txt --text-preset strong --clock unbounded --export result.tmind
python -m threemind_runtime.random_stimuli --mode fresh-group --channels 2 --seed 42 --count 20 --intensity 0.2 --output units.jsonl --save-state source-state.json
python -m threemind_runtime.cli --stimulus-units units.jsonl --clock unbounded --until-us 3000000 --export random-result.tmind
python -m threemind_lab.stimulus_diagnostics --model model.tmind --stimulus-units units.jsonl --until-us 500000 --output diagnosis.json
python -m threemind_runtime.world_cli --template gravity-pendulum --write-example pendulum.json
```

诊断时间是模型的绝对模拟时间，必须在检查点后一秒内；示例 `500000` 仅适用于起始时间合适的模型。诊断 CLI 限模型 32 MiB、输入 4 MiB、300 节点／5000 连接，超出即报错，不截断状态。API 为 `POST /api/v2/projects/{project}/runs/{id}/input-diagnostics`；随机工具为 `POST .../input-fixtures/random`；刺激体沿既有 `POST .../inputs` 递送，`adapter_id=stimulus-units`、`payload={"units":[...]}`。完整校验通过同一个 `unit_frames` 转换。Runtime 不依赖 Lab 数据库。

刺激体示例：

```json
{"schema_id":"threemind.stimulus-unit/1","kind":"group","time_us":"0","source":"body-sample","mapping_version":"adapter/1","grouping_basis":"same body, same sample","intensity":1,"elements":[{"channel":17,"value":0.4},{"channel":31,"value":0.2}]}
```

不同刺激体即使同一时间戳也不合并。来源、坐标系、单位、采样时间是证据，不作为内核语义。世界 `/2` 保持原有端口匿名身份算法；新版本扩展了感官种类及证据字段，不重编码旧端口。

## 背景核查结论

Git `97d8592` 的 `core/threemind/runtime.py` 默认 `edge_birth_policy=local-coactivation`、`homeostasis_enabled=False`。`_adapt_edges` 默认按每个感官事件内部的共同触达生边；仅显式时序策略使用此前触达集合。`_homeostasis` 是总量过高时缩减激活，不负责生边。当前对应规则为共同刺激生边，可选时间窗口关联；没有发现“新节点必须接入大网络”的分支。

当前合成场绝非独立噪声：慢变化使用 8 个身份，快速变化使用 11 个身份，漂移使用 13 个身份；扰动在 0.2–1.4 秒寿命内重复采样。遥测同样重用物理指标的水平／上升／下降通道，并含平滑历史。**这些重复和共同观测足以提供巩固条件；形成连接本身不是 BUG。** 独立随机工具才用于检查一次性输入；偶然共同触达仍遵循正常学习规则。

全局激活钳制与输入竞争默认关闭。躯体过滤由显式配置控制。显示抽样不改变 Core 连边；报告直接读取完整状态与实际输入，不以画面亮点数量代替结构。单通道和独立小网络无强制接网已有回归覆盖，实际背景对照结果另见研究报告。未对“背景”标签采取删点、删边或禁止学习。

## 验收

先后两组回归为 54 项通过、59 项通过（有重叠，不能相加当作独立测试数）。覆盖状态样例、旧遥测、API、独立 CLI、Rust/Python 模型互通、世界恢复和参数配置。第二组包括独立测试数据库上的浏览器测试，实际运行 1440 与 390 两种宽度；强度预设真实提交值、成功清空输入、世界图形／JSON、窄屏标签页及无横向溢出通过。前端构建通过；仍存在已有的大 chunk 提示。

加速度计检验区分支撑静置和自由落体；匀速平移本身不产生加速度，旋转角速度与感官坐标旋转正确，两个模板可恢复相同后续物理状态。神经信号传播节律没有因物理采样变快而变化。

沙箱曾拒绝访问测试临时目录；以授权执行权限重跑通过。没有为绕过测试更改内核、关闭遗忘或删除旧数据。
