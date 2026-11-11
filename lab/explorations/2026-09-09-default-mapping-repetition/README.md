# 默认映射复验

发送完整原句，由未经修改的默认文本感官执行NFKC与编码。每句先连续20次，完成3轮后才减少重复。全部家系陈述采用用户补全的句号；本轮所有源码、状态和证据独立保存。

`protocol.md`与`pair-control-plan.md`为教学前方案；`curriculum.json`为实际完整清单；`implementation.json`冻结产品源码和原生二进制摘要；`preflight.json`记录原句与感官规范化结果的明确边界。`run.py`与`paired_control.py`只使用现有内核、感官、输入和测量服务。`verify.py`逐条核验数据库中的原句、完整默认配置及实际帧。

在项目根目录可运行只读校验代码：

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe lab/explorations/2026-09-09-default-mapping-repetition/analyze.py --check
```

初始化顺序为`run.py init`、`paired_control.py init`，然后依次执行4个`run.py seed --seed ...`和2个`paired_control.py seed --seed ...`。完成后分析、核验、制作和发布报告。不得重新初始化或覆盖已执行的种子，也不得在初始化后重新生成冻结清单。新的复验必须使用新目录和项目。

原始全部节点活动在数据库探针ZIP中，`evidence-index.json`提供索引。报告、记录与笔记会落在本轮独立项目中；旧数据保留，禁止自动清理。本目录研究代码是从前轮工具复制后明确调整作用域、原句标点和默认配置，未修改产品源码。
