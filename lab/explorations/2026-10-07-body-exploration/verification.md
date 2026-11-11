# E61 验证记录 / Verification

2026-10-07。区分工程验证、实测结果和未验收项目；最终执行范围见报告。

| 检查 | 实际结果 |
| --- | --- |
| 玩具力学、眼手与声音状态恢复，固定通道 | 通过受影响回归 |
| 母亲只改变环境，嘴部声音到达耳朵 | 通过；改观察者标签不改变实际输入 |
| 旧眼手感官协议与既有连续运动外设 | 受影响回归通过；没有改Core |
| 完整回放保留新增感官与动作来源 | 打包测试通过；引导与撤去引导分段保留 |
| 流式ZIP完整性、读取失败及取消 | 通过；没有生成重复本地ZIP |
| 合并回归 | `test_body_playground.py`、`test_active_eye.py`、`test_continuous_motor.py`、`test_streaming_evidence.py`：27项，10.43秒 |
| Python语法编译 | 新工具与本批脚本通过 |
| 回放JavaScript语法 | `node --check`通过；不等于浏览器交互验收 |
| 派生训练缓存重建 | 第一来源训练记录的前8个活动窗口、入射窗口和动作标签与缓存逐值相等；未重复全量重算 |
| 实际GPU任务 | 三组×两来源的完成情况见结果；记录包含真实device与训练曲线，不仅检查CUDA可见性 |

最初受沙箱临时目录权限影响的pytest调用没有作为通过证据；随后在授权的独立测试目录中重跑通过。一个只读进程信息查询被宿主权限拒绝，与仿真或数据写入无关，没有用它推断Docker故障。

浏览器自动化此前拒绝本地文件预览。本轮没有通过换成本地HTTP、其他浏览器或隐蔽控制接口绕过。**实际浏览器播放、截图/录制，以及窄屏视觉验收未完成**；只能报告静态检查与记录打包测试。未修改主前端，因此没有把旧前端构建结果当作新交互已通过。

最终回放帧数、史书链接、数据库报告回读与归档完成情况在交付时追加。旧实验不重算、不清理；CRC与数据库上传SHA随单次归档产生，不反复哈希大文件。

English:27affected tests passed; Python and replay JavaScript syntax passed. Tests cover restored physics/acoustics, unchanged legacy inputs, observer-only metadata, caregiver separation, replay provenance and bounded archive streaming. The first8derived training samples exactly reconstruct from original records. Actual GPU fits are evidenced by each completed case. Browser playback, screen recording and narrow-screen visual QA remain unverified because local-file automation was denied; no alternate channel was used to bypass it. Final publication checks are appended below.

## 2026-10-07：连续性更正后的收尾核查

- 54个完成阶段，179次新建/恢复，累计198.73计算分钟；无完成案例的失败标记。没有新增模拟。
- 全部47章、571段、85,760帧过程已打包；核对章节存在及小型清单，没有重新扫描大型原始轨迹。实际生成HTML的JavaScript语法通过，流程更正出现在索引与画布。
- 修改脚本的Python语法通过。史书验证：4部、69章，中英对应与本地链接通过。
- E52、E54—E60共8个旧项目追加16条中英文连续性核查记录，并逐条回读匹配。旧数据库报告及工件没有覆盖。
- E56参考组合检查了代码、保存状态身份、模型元数据和小型成绩；没有重算全部旧实验、复制或哈希旧归档。完整学习状态仍缺失，已明确记录。
- 收尾时账户周窗口已用13%，实验登记起点为4%；共享账户变化计入，不声称均为本实验消耗。此后只交付，不扩模拟。
- 打包后本地证据约4.066GiB，可用内存约10.09GiB，C盘10.04GiB、E盘64.75GiB。HTML已作独立工件的章节不再装入ZIP第二份，原过程、渲染代码和工件引用均保留，8GiB硬上限不变。

English: post-correction checks confirm 47 chapters, 571 clips and 85,760 frames; actual generated JavaScript and changed Python parse. History validates 4 editions/69 chapters. Sixteen bilingual correction records were appended and read back in eight old projects without replacing reports. E56 metadata and small results were inspected, not rerun or rehashed. Account usage was 13% against a 4% initial reading, including shared use. No new simulation followed. Duplicate derived HTML is omitted from the evidence ZIP because those chapters are separate platform artifacts; raw processes and reconstruction sources remain.

## 最终入库结果 / Final publication

已完成：项目`07d72fc7-a289-4dc6-9bb0-f3c31052082b`，中英文报告逐条回读一致。原证据ZIP为2,913,315,113字节、733个文件；47份原始过程全部在归档清单中，47章回放分别作为工件保存。上传返回值、清单和数据库元数据一致，没有重复整包读取或哈希。合计存储7.067GiB，小于8GiB硬限。本期的完整系统修复和重试**未执行**。

[中文交付记录](delivery-summary.zh.md) · [English delivery record](delivery-summary.en.md) · [机器可读清单](delivery.json)

This post-upload addendum is stored separately from the already frozen ZIP; the original archived verification file is not rewritten. / 本段在上传后追加，另作平台交付记录；不重写已冻结ZIP中的原验证文件。
