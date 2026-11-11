# 逐句重复教学实验

完整保留用户的10条对话和4条家系例句。每句连续20次后才换句，前3轮均保持20次。Core默认配置不变，感官规范化显式设为none以保留全角标点。新的独立项目，不修改以前的实验。

- `protocol.md`：训练前冻结并落库的方案。
- `curriculum.json`：所有完整载体、重复块、时间和测量协议。
- `preflight.json`：逐字、标点、单帧、重复次数及观察通道检查。
- `run.py`：训练执行器，复用既有Lab服务；每个种子阶段输出只能写入一次。
- `pair-control-plan.md` / `paired_control.py`：原方案完成后先登记再执行的两个名词互换对照，完整保持20次重复；两阶段分开记录。
- `analyze.py`：完整候选及分阶段得分、固定时间窗口和图表。
- `structure.py`：只读区分原出生连接和同端点重建；由连接计数现象引出的补充诊断。
- `raw_activity.py`：直接比较既有ZIP中的全部匿名激活向量，不使用词评分掩码，不进行新的模拟。
- `verify.py`：逐条核对实际数据库输入、顺序、时间、通道以及恢复点和探针证据摘要。
- `report.md` / `report.en.md`：中英文报告；平台内另有方案笔记、三份实验记录和关联报告。
- `evidence-index.json`：数据库中的原始ZIP、结果和输入审计索引。
- `acceptance.json`：最终验证、存储和旧项目保持情况。

在项目根目录运行：

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe lab/explorations/2026-09-09-blocked-sentence-teaching/run.py preflight
.venv/Scripts/python.exe lab/explorations/2026-09-09-blocked-sentence-teaching/analyze.py --check
```

重新实验须复制到新的实验目录，修改WORK/META作用域并创建新项目，不能直接覆盖本目录的冻结证据或现有平台记录。`run.py init`创建项目和方案笔记；`run.py seed --seed 41701`等按顺序执行4个种子，每个种子含完整主教学及同源交叉家系对照。`.work/blocked-sentence-teaching-20260909`保存本轮局部执行日志，报告发布时同时归档结果文件。不会启动通用worker领取其他任务。

观察模板只用于研究读出，不是Core内部语义。主测量继续现有活动且允许学习，辅助出生副本清空活动。所有测量使用独立副本，原教学意识保持不变。原始数据保存所有零/非零节点活动，评分掩码不剪裁原始状态。
