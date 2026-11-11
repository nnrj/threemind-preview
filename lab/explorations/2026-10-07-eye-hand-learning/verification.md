# E60 工程验证 / Engineering verification

2026-10-07；只验证本批工具，不重算历史实验。

- `tests/test_continuous_motor.py`、`tests/test_active_eye.py`、`tests/test_gaze_events.py`：**21 passed**。含原/新运动外设保存恢复、零输入、真实大批次学习、原始输入不被修改、世界/4与/5无鼻输入一致、鼻部实体投影、眼睛转向保持、过程评分与双时钟回放。
- 已保存的主运动外设在8段实际教学活动上分别用CPU及GTX1650/CUDA推理，最大绝对输出差`1.4156103134155273e-7`，低于登记检查容差`1e-5`。记录在证据`device-check.json`。这不宣称跨硬件闭环轨迹必然逐位相同。
- 回放脚本做语法检查，科学汇总图已目视核查文字、坐标与零命令解释。实际浏览器播放、录制与窄屏视觉验收未完成：浏览器安全策略拒绝本地文件，未绕过该限制。可由用户打开本地HTML查看。
- 旧Core、默认值和历史实验未改；现有服务未启停。本轮使用本地Core、MuJoCo、CUDA和已运行的数据库，没有依赖Docker或调用付费外部模型。

English: 21 relevant tests pass, covering compatibility, genuine learning, round trips, optical/proprioceptive tools, scoring and replay. The saved reader's CPU/CUDA predictions differ by at most `1.42e-7` on eight real windows. This is not a claim of bitwise-identical closed-loop behavior across hardware. Script syntax and the static scientific figure were checked. Browser playback, recording and narrow-screen visual acceptance remain unverified because local-file browser access was denied; no bypass was used. Core, defaults, historical evidence and user services remain unchanged.

史书目录校验通过：4种体例、65章，中英文覆盖和本地链接均有效。完整回放21章、400段、39,840帧；章节路径和字节数检查通过，最终脚本`node --check`通过。没有为了此检查重新哈希大型证据。入库结果见[报告](report.zh.md)和`delivery.json`。

History validation passes for four editions and 65 chapters. All 21 replay chapter links and file sizes are verified, accounting for 400 clips and 39,840 frames. The final JavaScript passes `node --check`. No repeated large-evidence hashing is performed.
