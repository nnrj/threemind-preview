# 默认映射复验

> **修订 r2 · 2026-10-10**
> 修订原因：生成证据移出 Git 并完成校验归档；追加位置登记，保留原字节与结论。
> 原版：[README.md](README.md)；父版本 r1：[README.md](README.md)


发送完整原句，由未经修改的默认文本感官执行NFKC与编码。每句先连续20次，完成3轮后才减少重复。全部家系陈述采用用户补全的句号；本轮所有源码、状态和证据独立保存。

`protocol.md`与`pair-control-plan.md`为教学前方案；`curriculum.json`为实际完整清单；`implementation.json`冻结产品源码和原生二进制摘要；`preflight.json`记录原句与感官规范化结果的明确边界。`run.py`与`paired_control.py`只使用现有内核、感官、输入和测量服务。`verify.py`逐条核验数据库中的原句、完整默认配置及实际帧。

在项目根目录可运行只读校验代码：

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe lab/explorations/2026-09-09-default-mapping-repetition/analyze.py --check
```

初始化顺序为`run.py init`、`paired_control.py init`，然后依次执行4个`run.py seed --seed ...`和2个`paired_control.py seed --seed ...`。完成后分析、核验、制作和发布报告。不得重新初始化或覆盖已执行的种子，也不得在初始化后重新生成冻结清单。新的复验必须使用新目录和项目。

原始全部节点活动在数据库探针ZIP中，`evidence-index.json`提供索引。报告、记录与笔记会落在本轮独立项目中；旧数据保留，禁止自动清理。本目录研究代码是从前轮工具复制后明确调整作用域、原句标点和默认配置，未修改产品源码。


## 数据位置修订

选定的生成证据已逐字节校验归档。原报告、评判标准、结论及数据内 source_commit 均保留。以下逻辑下载需要当前主机管理员身份，数据目录未整体公开。

`data/experiments/2026-09-09-default-mapping-repetition/`

[Location and hash index / 位置及哈希登记](../../artifact-index/2026-10-09-relocations.json)

- [measurements.json](/api/v2/storage/research-artifacts/research-artifact:dbfff82fe099b76a2bd3de00/content) — 683222 B; SHA-256 `cf7e579516363d0af8efaa2d1050586a51078fc602dd6e0e2c87cca8b1ed568b`.
- [raw-activity-differences.json](/api/v2/storage/research-artifacts/research-artifact:ee9d13d05f5136dd41cac98d/content) — 176450 B; SHA-256 `99ce5441b9563dde3045f63f7b7eb1b65ca0eec5bfbd6692606e5d225e2f4dd2`.
- [time-courses.json](/api/v2/storage/research-artifacts/research-artifact:943f9d7ab9ccc620ab61f098/content) — 967982 B; SHA-256 `8c4d20babadaf773793c4128ebf1dc1bdf024e66b3d3446418c68e1a2b9122b1`.
- [training-traces.json](/api/v2/storage/research-artifacts/research-artifact:181fcc88fa99d7496f49f41e/content) — 1988076 B; SHA-256 `b0c110b1d394729042b1c271c5aca78dd48772dae977d521745bc3ef04babed9`.
