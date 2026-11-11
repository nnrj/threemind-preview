# E61 工具与操作 / Tools and operations

本批是可恢复的研究工具，不修改生产意识或Core默认。执行前读取`design.*.md`及各份补登记。案例一旦产生结果即只读；中断案例保留，不原位覆盖。运行路径均相对于仓库根。

PowerShell：

```powershell
$studyPython = '.work/kernel-venv/Scripts/python.exe'
$studyRunner = 'lab/explorations/2026-10-07-body-exploration/experiment.py'
& $studyPython $studyRunner --help
# 以下命令会跳过本批已完成案例；不是启动无界训练。
& $studyPython $studyRunner source-batch --source 0 --development gain01
& $studyPython $studyRunner source-batch --source 1 --development gain01
& $studyPython $studyRunner evaluate --source 0 --group explore --mode silence --development gain01
& $studyPython $studyRunner evaluate --source 0 --group explore --mode rescue --development gain01
& $studyPython $studyRunner evaluate --source 0 --group quiet --model-group explore --development gain01
& $studyPython lab/explorations/2026-10-07-body-exploration/caregiver.py --help
# 保留学前身体接线，只配平独立运动波动；对应更正后的W2。
& $studyPython lab/explorations/2026-10-07-body-exploration/caregiver.py probe --source 0 --group guided --preserve-wiring
& $studyPython lab/explorations/2026-10-07-body-exploration/caregiver.py probe --source 0 --group guided --cut --preserve-wiring
```

账户用量必须由实际账户读数更新到本批`usage.json`，不能伪造或绕开到期保护。预算已冻结，运行器只连接`localhost:5433/threemind`。`STOP`文件能停止本批计算，但不会删除已保存证据，也不会替用户终止其他服务。

共同环境撤去引导的主比较须显式加`--preserve-wiring`。未加时保留的是原W行为/结果，不应误当成保留学前接线的W2；详见[接线更正](withdrawal-correction.md)。有界收尾使用`finish_study.py`，只跳过已完成结果，不覆盖中断案例；所有计算仍累计计入本批补登记预算。

## 可复用组件

- `lab/tools/body_playground.py`：完整可转动视野、眼手本体、可推动弹性玩具、触力、声音频带、发声与自听。外部角色施力或发声只影响物理测量，不向Core注入目标。模型是平面接触力学/频带声学近似，不模拟完整婴儿、真实语音或骨传导。
- `lab/tools/sensorimotor_session.py`：版本化世界恢复、普通输入、原始输出及身体动作串联。新增可选mouth命令；不支持嘴部的旧世界会明确拒绝该命令，旧命令保持原义。
- `ExploratoryMotor`：固定匿名接线及独立记录的无目标运动波动，可保存随机状态。`activity_gain`是外设到物理力的增益；默认1保留，E61另登记0.1。它不对Core活动减基线或归一化。
- `lab/tools/active_vision_replay.py`：支持新世界记录，逐帧展示真实玩具位置、身体动作、感官输入及声音/接触量。截图及WebM按钮复用既有功能。耳朵频带不自动合成为音轨，图形也不是内核再模拟。
- `caregiver.py`：母亲环境角色和共同环境撤去引导对照。教师短句通过原文字感官；模拟声响通过双耳。角色不读取婴儿Core内部状态来决定正确动作。
- `pose_control.py`：已登记的可选姿态读出＋物理伺服诊断。专用模型版本与力输出模型区分，不能交换使用。是否执行见报告，不因代码存在就标为已验证。

## GUI 与命令的范围

完整记录可由独立HTML回放，提供章节、逐帧、倍速、截图、录制；实验设计与报告存入ThreeMind笔记/报告。Python/CLI可以精确复现操作。本期没有新增生产世界编辑器的玩具参数表单，也没有实现完整成人NPC或机器人。浏览器自动化此前拒绝本地文件预览，不换通道绕过；本批视觉交互验收如未完成会明确列出。

English: the versioned playground, session and replay are reusable. Explicit physical actions/feedback are separate from Core, and observer labels never affect input encoding. Runs are append-only, locally bounded, and resumable at completed case boundaries. The caregiver acts on the environment only. The optional posture/servo tool is not interchangeable with force models. Production toy-editor forms, full NPCs, bone conduction and synthesized soundtracks are outside this delivery. See reports for actual execution and UI validation, rather than inferring completion from code availability.

## 证据归档与训练缓存

`lab/tools/streaming_evidence.py`把新证据一次读入、分块上传到已授权的本机数据库，不额外在本地生成同样大的ZIP。原记录完整保留；归档CRC与上传SHA在读写中产生，不再重复遍历大文件验证。

原始输入、完整活动与动作、状态、模型、程序和失败记录均归档。可重建的`features.npz`训练缓存仍留在本地，但不在数据库再复制；归档清单逐项注明遗漏的是派生缓存。`rebuild_features.py`可从`process.jsonl.gz`与`layout.json`重新生成，既不运行Core，也不改变证据。

```powershell
& $studyPython lab/explorations/2026-10-07-body-exploration/rebuild_features.py --help
```

English: archives stream directly to local database storage. Original records remain intact. Derived NPZ caches are retained locally and explicitly excluded from the database ZIP; the recorded raw process, layout and reconstruction script reproduce them without running Core. There is no silent removal of original evidence.

2026-10-07交付补充：47章HTML已分别作为平台工件保存，ZIP不再重复包含同一批派生HTML；`replay-artifacts.json`列出其工件身份，原过程、渲染脚本和章节清单仍在ZIP中。此去重保持8GiB总预算，不删除本地文件，也不删减原始采样。完整系统连续性缺口及下一期修复见[R40](../../../docs/zh/plans/system-continuity-audit.md)，不能将本工具当前的分段恢复描述为完整个体持续学习。

English: each of the 47 HTML chapters is stored separately on the platform. The ZIP avoids a second copy of these derived pages and includes `replay-artifacts.json`, original processes, renderer and chapter manifest. This retains the 8 GiB total budget without deleting local files or samples. Complete developmental continuity is pending R40, not provided by current segmented restoration.
