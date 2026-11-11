# 感官恢复、维护时机与共同参照 / Recovery and references

> **修订 r2 · 2026-10-10**
> 修订原因：生成证据移出 Git 并完成校验归档；追加位置登记，保留原字节与结论。
> 原版：[README.md](README.md)；父版本 r1：[README.md](README.md)


E22: [中文事前设计](design.zh.md) · [English registration](design.en.md).

已完成：1,520/1,520 个登记案例。[中文报告](report.zh.md) · [English report](report.en.md) · [交付与休眠核查](delivery.zh.md) · [Delivery and recovery check](delivery.en.md)。后两份补记在原报告发布后追加，不改写原归档。

通过既有 Runtime/Lab API 运行；Core、旧数据及产品默认保持不变。来源按哈希冻结，所有副本进入独立项目。

```powershell
$env:PYTHONUTF8 = '1'
$py = '.work/kernel-venv/Scripts/python.exe'
$study = 'lab/explorations/2026-10-01-recovery-reference'
& $py "$study/run.py" prepare
& $py "$study/run.py" cut
& $py "$study/run.py" recovery
& $py "$study/run.py" timing
& $py "$study/run.py" jitter
& $py "$study/run.py" reference
& $py "$study/run.py" status
& $py "$study/analyze.py" --name final --tables
& $py "$study/audit.py"
& $py "$study/figures.py"
& $py "$study/publish.py"
```

`prepare` 只执行一次。`--block` 限定已登记材料块，恢复命令不覆盖完成案例；失败须另行登记，不删除重跑。用真实查询更新专用 `.work/recovery-reference-20261001/usage.json`，30 分钟过期即停。审核结束写入 STOP 后不再模拟。

新工具只用于研究副本：

```powershell
& $py -m lab.tools.state_exchange_cut recipient.json.gz donor.json.gz new-copy.json.gz --groups W S
```

W 是边权，S 是边历史，N 是节点历史。源文件只读，输出和收据必须不存在。按匿名通道对应，不交换节点身份；接收方活动、抑制、局部能量、快迹、所有在途信号及已传出记录完整保留。旧 `state_exchange` 仍要求空队列，不改协议。没有新增 UI 干预表单；平台展示设计、报告和原始读出。

The new CLI explicitly permits an in-flight causal cut only for the named persistent fields. All ongoing receiver state stays unchanged. It requires matching configurations, time, topology and no pending novelty. Artificial interventions are audited, not represented as natural learning or inheritance.

`analyze` 只读轨迹，`audit` 核对实际输入、状态、原始来源与无观察工具的重演；全部登记案例完成后关闭模拟。`figures` 根据已保存的结果绘图，`publish` 使用平台服务保存双语笔记、报告、八个固定读出示例和可下载的完整证据。它不调用外部 AI，不执行其他项目的排队作业。因预算停止时，审核须显式填写 `--partial-reason`，保留缺项；不能把部分结果写成全部完成。

Analysis reads recorded trajectories. Audit checks exact inputs, checkpoints, source identities and observer-disabled replays. Publication uses the existing Lab services and only its own jobs. Stage guards reserve memory and disk and honor the registered shared-account limits; no historical evidence is overwritten or removed.


## 数据位置修订

选定的生成证据已逐字节校验归档。原报告、评判标准、结论及数据内 source_commit 均保留。以下逻辑下载需要当前主机管理员身份，数据目录未整体公开。

`data/experiments/2026-10-01-recovery-reference/`

[Location and hash index / 位置及哈希登记](../../artifact-index/2026-10-09-relocations.json)

- [tables/paired-orders.csv](/api/v2/storage/research-artifacts/research-artifact:9cf56ab15ca1d9d52df3f25d/content) — 34911 B; SHA-256 `471bc71f86b6c410df0038fccb0e4e481bb6d5a1d75476964a3f40dde48dde97`.
- [tables/windows.csv](/api/v2/storage/research-artifacts/research-artifact:76406547c776efe9791582ed/content) — 625234 B; SHA-256 `a77a01e3a8b64744949f14683de1811e5d9b5d958c48e67ab67b452384d0e07a`.
