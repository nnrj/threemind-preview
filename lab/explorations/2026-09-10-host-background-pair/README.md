# 宿主背景与10秒间隔配对 / Host-background pairing

[中文报告](report.md) · [English report](report.en.md) · [完整节点排名](rankings.html) · [事先方案](protocol.md) · [验收](acceptance.json)

新项目ID与所有笔记、记录、报告、来源、导出及附件ID保存在`platform.json`。原始物理记录`host-recording.jsonl`、完整`node-rankings.jsonl`、实现快照`implementation-source.zip`作为附件落库，Git中保留研究脚本、报告、分析摘要和索引。本轮工作副本在`.work/host-background-pair-20260910/`。

复现必须使用新目录与新项目，不能覆盖已有证据。`capture.py`连续采集415秒真实宿主计数；`run.py prepare`冻结计划、课程、映射、源码和记录摘要并保存设计笔记；`supervise.py 41701`及`supervise.py 41702`依次执行，分别有150秒硬期限。`analyze.py`仅分析固定证据；`verify.py`检查实际输入、强度、时间、背景继承和旧数据；`make_report.py`生成全节点查看器和图；`publish.py`只认领本项目归档／报告作业。

宿主帧强度0.25，训练0.9，检验0.5。Core和两个感官编码均未变。新增可选CLI强度参数不改变省略时的行为；见[来源与CLI说明](../../../docs/zh/v2-source-policies.md)。继承的研究工具路径及其字节摘要见`preflight.json`与`instrumentation-dependencies.json`，可由同一Git状态取得。

源码验收和报告归档属于不同时间点；归档前资源记在`acceptance.json`，归档后记在`closure.json`及平台的结项核验笔记。两个无背景对照自然死亡而中止，只进行了各一次教学，不当作完成训练的配对失败。
