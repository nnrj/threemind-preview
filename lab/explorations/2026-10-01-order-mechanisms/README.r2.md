# 顺序信息与感官机制定位

> **修订 r2 · 2026-10-10**
> 修订原因：生成证据移出 Git 并完成校验归档；追加位置登记，保留原字节与结论。
> 原版：[README.md](README.md)；父版本 r1：[README.md](README.md)


本批保留强刺激额外项及全部产品默认，不探索其替代。执行依据：[中文设计](design.zh.md)、[English](design.en.md)、[时间节奏补充登记](timing-addendum.zh.md)。补充登记在时间扫描开始前完成，总登记 2,880 实例；尚未完成的阶段不能当成结果。

从项目根目录使用既有隔离环境。只有首次可执行 `prepare`；后续按阶段恢复，完成案例不覆盖：

```powershell
$env:PYTHONUTF8 = '1'
$py = '.work/kernel-venv/Scripts/python.exe'
$study = 'lab/explorations/2026-10-01-order-mechanisms'
& $py "$study/run.py" status
& $py "$study/run.py" swap
& $py "$study/run.py" phase
& $py "$study/run.py" cadence
& $py "$study/run.py" reference
& $py "$study/run.py" sensory
& $py "$study/analyze.py" --name final --tables
& $py "$study/audit.py"
& $py "$study/figures.py"
& $py "$study/publish.py"
```

CLI 的 `--block` 可限定事前登记材料块；中途失败原样留证，不用同一个 key 覆写重跑。账户用量必须由真实查询更新到专用 `.work/order-mechanisms-20261001/usage.json`，30 分钟过期后停止。不是让脚本自行猜测额度。审计完成后 STOP 阻止新增模拟，之后只制作和发布报告。

`status` 在实验关闭后仍可读取完成情况。`publish` 只应在中英文报告完成、图表核对及 `audit.json` 验收后执行；它不会执行其他项目排队的作业。完整结果见[中文报告](report.zh.md)及 [English report](report.en.md)。

## 可复用的状态交换工具

开发态命令：

```powershell
& $py -m lab.tools.state_exchange recipient.json.gz donor.json.gz new-copy.json.gz --groups W
```

W 交换边权，S 交换边历史，N 交换节点历史，D 交换活动与快速状态；允许多项或空集合。协议仅支持 `continuous-memory-state/2`，要求同配置、同时间、同匿名通道拓扑、无在途与未决事件。按通道对应并保留受体实例的节点 ID，不按节点创建顺序错配。输出必须为新文件，旁边必有 `intervention.json` 收据，列出原状态、供体、新状态哈希和所有变化。支持 `native` 与 `reference` 恢复验证。

此工具不修改运行中的意识、旧快照、内核公式或默认参数。它是人为因果研究操作，不是自然学习或遗传。UI 可查看本批报告、记录与快照证据；状态交换的新表单尚未加入 UI，不能称作已具备对应的图形操作。

The study uses a dedicated database project and work directory. Exact sources, inputs, state-exchange receipts and observations remain separate evidence. The reusable development-only CLI aligns by anonymous channels, refuses mismatched or unsettled states, preserves source files and requires a new output with an explicit intervention receipt. It does not modify Core dynamics or silently upgrade historic instances.


## 数据位置修订

选定的生成证据已逐字节校验归档。原报告、评判标准、结论及数据内 source_commit 均保留。以下逻辑下载需要当前主机管理员身份，数据目录未整体公开。

`data/experiments/2026-10-01-order-mechanisms/`

[Location and hash index / 位置及哈希登记](../../artifact-index/2026-10-09-relocations.json)

- [tables/paired-orders.csv](/api/v2/storage/research-artifacts/research-artifact:a7969cfdaca691aeabc89c03/content) — 98613 B; SHA-256 `f14ca4415bb4d615a174d84a1919ea3dbf058b3af59cc8f0eb9b0edd67071fc1`.
- [tables/windows.csv](/api/v2/storage/research-artifacts/research-artifact:ca8aecdc89a80b90f140d885/content) — 884551 B; SHA-256 `db9ecb635c3681d0d05556beacf93b915414724a46ff9a87c49b6235cd9be45f`.
