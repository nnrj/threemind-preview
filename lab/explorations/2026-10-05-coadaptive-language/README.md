# E52：个体化语言外设、实际自听与忠实翻译

[中文报告](report.zh.md) · [English report](report.en.md) · [事前设计与分期补充](design.zh.md)

本批使用 `continuous-memory/2` 原内核和原感官编码。源实例持续接受教学，新的小 Transformer 外设分批继续学习；可选自听将它**实际说出的**词语送回原感官。教师答案不进入测试读出，监督记录与Core输入分别留证。

实验计划、笔记、报告和原始回答保存在研究项目 `7d5d5fa6-d84b-47b2-b788-1cdec68a3aca`。交付详情见 `delivery.json`。`.work/coadaptive-language-20261005` 保存原始轨迹、检查点、教学记录和外设版本，数据库另存证据归档。

## 文件和复用

- `experiment.py`：教学、实际反馈、阶段测试；`prepare`只能创建新批次一次，已登记本批不要再次调用。
- `transcription.py`：只教词语转写，不教物体—名字答案；识字与问后回答分别评分。
- `linear_transcription.py`：同样资料、有限词表线性读出，以及未训练强度的听词对照；不是句子生成器。
- `aligned_calibration.py`：同快照均衡校准的定位对照，仍为任务答案监督，不作为纯翻译证明。
- `attribution.py`：固定外设的相关/匹配通路屏蔽、恢复及旧阶段快照对照。是否实际执行以报告为准。
- `summarize.py`、`activity_summary.py`、`plot.py`：本批有限资料的重分析，不推进Core；活动差异用于诊断，不改变表达器的实际输入。
- `sampling_diagnostic.py`：用原始密集轨迹与实际局部采样核对听词差异，没有重新教学或修改状态。
- `publish.py`：通过现有Lab接口保存报告和证据，不执行其他任务；`verify_tool.py`是一次性小型CLI验收。

运行使用项目 `.work/kernel-venv/Scripts/python.exe`。续接已有结果会跳过已完成项，未完成目录保留并明确报错，不无声覆盖。GPU训练与CPU验证均见 `verification.json`。复现另一批须使用新的工作目录与项目登记，不能更改本批快照、标签或停止规则。

通用能力不依赖本实验脚本：[外设Python/CLI](../../../docs/zh/reference/adaptive-expression.md)。普通使用无需继承本次物体、名字或任务设置。
