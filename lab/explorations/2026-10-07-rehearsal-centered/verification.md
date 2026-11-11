# E63 工具验收记录

2026-10-08（北京时间）。实验统计、实际回答与结论另见报告；本页只说明工具验证。

- 16项定向测试通过（28.27秒）：旧FIFO与显式recent策略行为相同；三种缓存策略保留权重、优化器、随机状态并恢复下一次学习；旧代表样本保留；整体意识、身体、表达器和近期活动完整恢复；教师信息不经对象元数据泄漏到感官；原连续发育与课程流程测试保持通过。
- 首次最终测试15项通过、1项失败，定位到“全部输入都是视觉通道”这一小型测试中空的其他通道索引被PyTorch推为浮点型。显式改为整数索引后16项通过。实际实验都含非视觉通道，原先这些索引已经是整数；该修正不改变本轮实际输入、活动或学习，未重跑已完成实验。
- Python编译检查、回放脚本JavaScript语法检查通过。回放只打包已记录场景、答案和活动，原始完整活动另存；教师期望只供监督/事后评分，不作为推理输入。
- 本期Core源码、动力学、映射、普通默认和旧实验数据未修改。缓存策略是明示外设训练条件，旧motor/1路径保留；新motor/2、centered-system/1保存完整状态。
- 这里没有把前端语法检查当作真实浏览器交互验收。最终回放如成功打包，将单列记录数；尚未完成真实浏览器观看或录制的视频不得标为已验收。

命令：

```powershell
& .work/kernel-venv/Scripts/python.exe -m pytest tests/test_rehearsal_memory.py tests/test_centered_recognition.py tests/test_developmental_system.py tests/test_developmental_curriculum.py --basetemp=.work/pytest-e63-final2 -q
node --check .work/rehearsal-centered-20261007/replay-syntax.js
```

English: 16 targeted tests pass, including whole-system continuation and the next optimizer update, policy persistence, legacy FIFO equivalence, physical observation and no object-metadata answer leakage. An empty-index dtype issue in an all-visual synthetic test was fixed; actual study indices were already integer-valued. Python compilation and replay JavaScript syntax pass. These are engineering checks, not proof of recognition or browser visual QA. Core dynamics/defaults/mappings and historical evidence remain unchanged.

## 用户追加整段提问校准后的定向验证

新增校准保留同一个Adam对象和权重，whole-question采样配置以vocabulary/2保存，恢复后下一次校准更新一致。对应3项测试通过（14.48秒，包含之前2项），累计覆盖17个不同测试。更新后的回放脚本语法检查通过；窗口末正式回答与逐窗表达分开展示。尚未用工具验证浏览器实际画面。

English: Three centered-system tests pass after question calibration was added (14.48s, two repeated and one new:17 distinct tests across the targeted runs). The calibration retains the original Adam and restores whole-question vocabulary/2 plus the next exact update. Revised replay syntax passes; formal whole-question answers are labeled separately from instantaneous trailing-window expressions.
# 2026-10-08交付补记

本批通用回放已打包482段、28,050个原始采样帧，包含全部已完成教学、间隔及成功/失败测试；未完成的校准采样只在证据归档保留，未混入“完成”回放。HTML为182,065,833字节，未压缩；这不是新录制的影片，也未完成真实浏览器视觉验收。分析累计91.83计算分钟，15次创建/恢复。后续若继续原个体，归入E64独立分支，E63 STOP保留。
