# E63：完整个体的新旧复习与中央单物体认识

[中文登记](design.zh.md) · [English registration](design.en.md)

实验只使用本地研究项目，不接管Lab/UI服务。旧证据和Core不改。工作目录`.work/rehearsal-centered-20261007`；独立项目ID记录在该目录`platform.json`。

本项目Python环境执行：

```powershell
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-07-rehearsal-centered/experiment.py prepare
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-07-rehearsal-centered/experiment.py rehearsal --policy recent
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-07-rehearsal-centered/batch.py motor-rest
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-07-rehearsal-centered/batch.py recognition-primary
& .work/kernel-venv/Scripts/python.exe lab/explorations/2026-10-07-rehearsal-centered/batch.py recognition-controls
```

这些命令是登记实验的执行记录。已完成组不会覆盖，日志存在时批处理拒绝重跑；中断后读原状态与登记，再通过单阶段CLI恢复，不删除旧目录来逃过检查。扩展和纠错需看本轮结果与剩余预算，不能无条件把所有命令重跑。`analyze.py`只读完成的证据，一次生成`results.json`；通用回放工具保留所有帧。项目中`STOP`存在时不得继续新模拟。

复习策略为外设训练配置，不是Core新颖性、遗忘或生理规则。`developmental-motor/1`照旧恢复；显式使用缓存策略的新快照为`/2`。中央诊断有独立`centered-observation/1`、`personal-vocabulary/1`、`centered-system/1`，整套状态及学习状态可保存恢复，不把单个权重文件当完整个体。

English: these are registered execution commands, not permission to overwrite completed cases. One sequential worker; stop on budget/partial failures and preserve evidence. Rehearsal changes only peripheral training. The centered system has its own complete versioned state and an eight-word vocabulary; no claim of unrestricted speech or learned fixation.
